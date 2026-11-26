"""Helpers for concatenating junie/rules/*.md and syncing ~/.junie/AGENTS.md."""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from pathlib import Path


AGENTS_MODE = 0o644


def discover_rule_files(rules_dir: Path) -> list[Path]:
    """Return sorted *.md rule files inside junie/rules/."""
    if not rules_dir.is_dir():
        raise FileNotFoundError(f"missing rules directory: {rules_dir}")
    rule_files = sorted(
        (p for p in rules_dir.iterdir() if p.is_file() and p.suffix == ".md"),
        key=lambda p: p.name,
    )
    if not rule_files:
        raise ValueError(f"no *.md rule files found in {rules_dir}")
    return rule_files


def render_agents_md(rules_dir: Path) -> tuple[str, list[Path]]:
    """Concatenate junie/rules/*.md into a single markdown document."""
    rule_files = discover_rule_files(rules_dir)
    chunks: list[str] = []
    for path in rule_files:
        raw = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        cleaned = raw.strip("\n")
        if not cleaned.strip():
            raise ValueError(f"rule file is empty: {path.name}")
        chunks.append(cleaned)
    return "\n\n".join(chunks) + "\n", rule_files


def sha256_bytes(data: bytes) -> str:
    """Compute hex SHA-256 digest for bytes."""
    return hashlib.sha256(data).hexdigest()


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


def atomic_write_text(dst: Path, content: str, mode: int = AGENTS_MODE) -> None:
    """Write UTF-8 text to dst atomically with exact permissions."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{dst.name}.", dir=str(dst.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(content.encode("utf-8"))
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, dst)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def sync_agents_md(system_dir: Path, target: Path) -> tuple[bool, str]:
    """Render junie/rules/*.md and sync ~/.junie/AGENTS.md."""
    rules_dir = system_dir / "rules"
    try:
        rendered, rule_files = render_agents_md(rules_dir)
    except (OSError, ValueError) as exc:
        return False, f"[FAIL] {exc}"

    if target.is_dir() and not target.is_symlink():
        return False, f"[FAIL] target is a directory: ~/.junie/AGENTS.md ({target})"

    expected_sha = sha256_bytes(rendered.encode("utf-8"))
    exists = target.exists() or target.is_symlink()

    if not exists:
        try:
            atomic_write_text(target, rendered, AGENTS_MODE)
        except OSError as exc:
            return False, f"[FAIL] could not install ~/.junie/AGENTS.md: {exc}"
        return (
            True,
            f"[INSTALLED] ~/.junie/AGENTS.md (mode {AGENTS_MODE:04o}, from {len(rule_files)} rule(s))",
        )

    if target.is_symlink():
        reason = "broken symlink replaced" if not target.exists() else "symlink replaced"
        try:
            atomic_write_text(target, rendered, AGENTS_MODE)
        except OSError as exc:
            return False, f"[FAIL] could not update ~/.junie/AGENTS.md: {exc}"
        return (
            True,
            f"[UPDATED] ~/.junie/AGENTS.md ({reason}, from {len(rule_files)} rule(s))",
        )

    try:
        actual_sha = sha256_file(target)
        actual_mode = stat.S_IMODE(target.stat().st_mode)
    except OSError as exc:
        return False, f"[FAIL] cannot inspect ~/.junie/AGENTS.md: {exc}"

    if actual_sha != expected_sha:
        try:
            atomic_write_text(target, rendered, AGENTS_MODE)
        except OSError as exc:
            return False, f"[FAIL] could not update ~/.junie/AGENTS.md: {exc}"
        return (
            True,
            f"[UPDATED] ~/.junie/AGENTS.md (sha256 {actual_sha[:12]} -> {expected_sha[:12]}, "
            f"from {len(rule_files)} rule(s))",
        )

    if actual_mode != AGENTS_MODE:
        try:
            os.chmod(target, AGENTS_MODE)
        except OSError as exc:
            return False, f"[FAIL] could not chmod ~/.junie/AGENTS.md: {exc}"
        return (
            True,
            f"[UPDATED] ~/.junie/AGENTS.md (mode {actual_mode:04o} -> {AGENTS_MODE:04o})",
        )

    return (
        True,
        f"[OK] ~/.junie/AGENTS.md (unchanged, {len(rule_files)} rule(s))",
    )


def check_agents_md(system_dir: Path, target: Path) -> tuple[bool, str]:
    """Verify ~/.junie/AGENTS.md exists, is a regular file, and matches rendered rules."""
    rules_dir = system_dir / "rules"
    try:
        rendered, rule_files = render_agents_md(rules_dir)
    except (OSError, ValueError) as exc:
        return False, f"[FAIL] {exc}"

    if not target.exists() and not target.is_symlink():
        return False, f"[FAIL] missing: ~/.junie/AGENTS.md ({target})"

    if target.is_symlink():
        link_target = os.readlink(target)
        if not target.exists():
            return False, f"[FAIL] broken symlink: ~/.junie/AGENTS.md -> {link_target}"
        return (
            False,
            f"[FAIL] symlink (expected regular file): ~/.junie/AGENTS.md -> {link_target}",
        )

    if target.is_dir():
        return (
            False,
            f"[FAIL] expected file, found directory: ~/.junie/AGENTS.md ({target})",
        )

    expected_sha = sha256_bytes(rendered.encode("utf-8"))
    try:
        actual_sha = sha256_file(target)
        actual_mode = stat.S_IMODE(target.stat().st_mode)
    except OSError as exc:
        return False, f"[FAIL] cannot inspect ~/.junie/AGENTS.md: {exc}"

    if actual_sha != expected_sha:
        return (
            False,
            f"[FAIL] sha256 mismatch: ~/.junie/AGENTS.md "
            f"(expected {expected_sha[:12]} != local {actual_sha[:12]})",
        )

    if actual_mode != AGENTS_MODE:
        return (
            False,
            f"[FAIL] mode mismatch: ~/.junie/AGENTS.md "
            f"(expected {AGENTS_MODE:04o}, got {actual_mode:04o})",
        )

    return (
        True,
        f"[OK] ~/.junie/AGENTS.md (sha256 {expected_sha[:12]}, mode {AGENTS_MODE:04o}, "
        f"{len(rule_files)} rule(s))",
    )
