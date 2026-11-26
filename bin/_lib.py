"""Shared helpers for bin/doctor and bin/install."""

from __future__ import annotations

import hashlib
import os
import shlex
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


IGNORED_DIRS = {"bin", "tests", "__pycache__"}


@dataclass(frozen=True)
class System:
    """A discoverable configuration system under the repository root."""

    name: str
    path: Path
    manifest_path: Path | None
    hooks_dir: Path | None

    def hook(self, hook_name: str) -> Path | None:
        if self.hooks_dir is None:
            return None
        candidate = self.hooks_dir / hook_name
        if candidate.exists():
            return candidate
        return None


@dataclass(frozen=True)
class ManifestEntry:
    """A single file mapping declared in a system's manifest."""

    mode: int
    source: Path
    target: Path
    kind: str  # "sync" or "seed"
    rel_source: str
    raw_target: str


class Style:
    """Minimal ANSI color formatter that disables itself for non-TTYs."""

    def __init__(self, stream=None) -> None:
        stream = stream or sys.stdout
        self.enabled = (
            hasattr(stream, "isatty")
            and stream.isatty()
            and os.environ.get("NO_COLOR", "") == ""
        )

    def _wrap(self, code: str, text: str) -> str:
        if not self.enabled:
            return text
        return f"\033[{code}m{text}\033[0m"

    def bold(self, text: str) -> str:
        return self._wrap("1", text)

    def green(self, text: str) -> str:
        return self._wrap("32", text)

    def red(self, text: str) -> str:
        return self._wrap("31", text)

    def yellow(self, text: str) -> str:
        return self._wrap("33", text)

    def cyan(self, text: str) -> str:
        return self._wrap("36", text)

    def dim(self, text: str) -> str:
        return self._wrap("2", text)


def find_repo_root() -> Path:
    """Return the repository root directory containing bin/."""
    return Path(__file__).resolve().parent.parent


def discover_systems(repo_root: Path) -> list[System]:
    """Discover top-level system directories containing a manifest or hooks/."""
    systems: list[System] = []
    for entry in sorted(repo_root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir():
            continue
        if entry.name.startswith(".") or entry.name in IGNORED_DIRS:
            continue
        manifest = entry / "manifest"
        hooks = entry / "hooks"
        has_manifest = manifest.is_file()
        has_hooks = hooks.is_dir()
        if not has_manifest and not has_hooks:
            continue
        systems.append(
            System(
                name=entry.name,
                path=entry,
                manifest_path=manifest if has_manifest else None,
                hooks_dir=hooks if has_hooks else None,
            )
        )
    return systems


def select_systems(repo_root: Path, requested: Iterable[str]) -> list[System]:
    """Filter discovered systems by name, raising ValueError on unknown names."""
    all_systems = discover_systems(repo_root)
    names = list(requested)
    if not names:
        return all_systems

    by_name = {s.name: s for s in all_systems}
    unknown = [name for name in names if name not in by_name]
    if unknown:
        available = ", ".join(by_name.keys()) or "(none)"
        raise ValueError(
            f"Unknown system(s): {', '.join(unknown)}. Available systems: {available}"
        )

    seen: set[str] = set()
    selected: list[System] = []
    for name in names:
        if name not in seen:
            seen.add(name)
            selected.append(by_name[name])
    return selected


def parse_manifest(system: System) -> list[ManifestEntry]:
    """Parse a system's manifest file into ManifestEntry objects."""
    if system.manifest_path is None:
        return []

    entries: list[ManifestEntry] = []
    lines = system.manifest_path.read_text(encoding="utf-8").splitlines()
    for lineno, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        tokens = shlex.split(stripped, comments=True)
        if not tokens:
            continue
        if len(tokens) not in (3, 4):
            raise ValueError(
                f"{system.manifest_path}:{lineno}: expected '<mode> <source> <target> [sync|seed|sync-or-seed]', got {len(tokens)} fields"
            )

        mode_str, raw_source, raw_target = tokens[0], tokens[1], tokens[2]
        kind = tokens[3] if len(tokens) == 4 else "sync"
        if kind not in ("sync", "seed", "sync-or-seed"):
            raise ValueError(
                f"{system.manifest_path}:{lineno}: invalid kind '{kind}' (expected 'sync', 'seed', or 'sync-or-seed')"
            )

        try:
            mode = int(mode_str, 8)
        except ValueError as exc:
            raise ValueError(
                f"{system.manifest_path}:{lineno}: invalid octal mode '{mode_str}'"
            ) from exc
        if not (0 <= mode <= 0o777):
            raise ValueError(
                f"{system.manifest_path}:{lineno}: mode '{mode_str}' out of range 0000..0777"
            )

        system_root = system.path.resolve()

        def _resolve_source(rel: str) -> Path:
            candidate = (system.path / rel).resolve()
            if candidate != system_root and system_root not in candidate.parents:
                raise ValueError(
                    f"{system.manifest_path}:{lineno}: source '{rel}' escapes system directory"
                )
            return candidate

        if kind == "sync-or-seed":
            parts = raw_source.split("|")
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise ValueError(
                    f"{system.manifest_path}:{lineno}: sync-or-seed source '{raw_source}' must be '<primary>|<seed>'"
                )
            primary_rel, seed_rel = parts
            primary_source = _resolve_source(primary_rel)
            seed_source = _resolve_source(seed_rel)
            primary_unexpanded = system.path / primary_rel
            if primary_unexpanded.exists() or primary_unexpanded.is_symlink():
                rel_source = primary_rel
                source = primary_source
                resolved_kind = "sync"
            else:
                rel_source = seed_rel
                source = seed_source
                resolved_kind = "seed"
        else:
            if "|" in raw_source:
                raise ValueError(
                    f"{system.manifest_path}:{lineno}: '|' source syntax requires kind 'sync-or-seed'"
                )
            rel_source = raw_source
            source = _resolve_source(rel_source)
            resolved_kind = kind

        expanded_target = os.path.expanduser(os.path.expandvars(raw_target))
        target = Path(expanded_target)
        if not target.is_absolute():
            raise ValueError(
                f"{system.manifest_path}:{lineno}: target '{raw_target}' must resolve to an absolute path"
            )

        entries.append(
            ManifestEntry(
                mode=mode,
                source=source,
                target=target,
                kind=resolved_kind,
                rel_source=f"{system.name}/{rel_source}",
                raw_target=raw_target,
            )
        )
    return entries


def sha256_file(path: Path) -> str:
    """Compute hex SHA-256 digest for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def file_mode(path: Path) -> int:
    """Return permission bits (e.g. 0o644) for path."""
    return stat.S_IMODE(path.stat().st_mode)


def format_mode(mode: int) -> str:
    """Format integer mode as 4-digit octal string."""
    return f"{mode:04o}"


def run_hook(hook_path: Path, env: dict[str, str], indent: str = "  ") -> int:
    """Execute a system hook script and stream its output indented."""
    if not os.access(hook_path, os.X_OK):
        raise PermissionError(f"Hook is not executable: {hook_path}")

    proc = subprocess.Popen(
        [str(hook_path)],
        cwd=str(hook_path.parent.parent),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        print(f"{indent}{line.rstrip()}")
    return proc.wait()
