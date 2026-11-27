"""Helpers for rendering `safehouse/policies/*.sb` and `safehouse/acp.json`.

Keeping `.sb` snippets split per tool makes sandbox overrides easy to review,
and `acp.json` needs `${HOME}` expanded at install time because JetBrains ACP
expects concrete paths rather than shell variables.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path


ACP_MODE = 0o644
POLICY_MODE = 0o644
POLICY_BANNER = (
    ";; ---------------------------------------------------------------------------\n"
    ";; Machine-local Agent Safehouse appended profile for junie-safehouse\n"
    ';; Appended via: safehouse --append-profile="$HOME/.config/safehouse/junie-local.sb"\n'
    ";; Generated from safehouse/policies/*.sb by safehouse/hooks/post-install\n"
    ";; ---------------------------------------------------------------------------"
)


def discover_policy_files(policies_dir: Path) -> list[Path]:
    """Return sorted `*.sb` policy files inside `safehouse/policies/`."""
    if not policies_dir.is_dir():
        raise FileNotFoundError(f"missing policies directory: {policies_dir}")
    policy_files = sorted(
        (p for p in policies_dir.iterdir() if p.is_file() and p.suffix == ".sb"),
        key=lambda p: p.name,
    )
    if not policy_files:
        raise ValueError(f"no *.sb policy files found in {policies_dir}")
    return policy_files


def render_local_profile(policies_dir: Path) -> tuple[str, list[Path]]:
    """Concatenate `safehouse/policies/*.sb` under the local-profile banner.

    Fails on empty policy files so a blank `.sb` stub can't slip into the active
    sandbox profile.
    """
    policy_files = discover_policy_files(policies_dir)
    chunks: list[str] = []
    for path in policy_files:
        raw = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        cleaned = raw.strip("\n")
        if not cleaned.strip():
            raise ValueError(f"policy file is empty: {path.name}")
        chunks.append(cleaned)
    return POLICY_BANNER + "\n\n" + "\n\n".join(chunks) + "\n", policy_files


def render_acp_json(system_dir: Path, home: Path | None = None) -> str:
    """Expand `${HOME}` in `safehouse/acp.json` and validate the resulting JSON."""
    src_path = system_dir / "acp.json"
    if not src_path.is_file():
        raise FileNotFoundError(f"missing ACP template: {src_path}")

    resolved_home = str(home if home is not None else Path.home())
    escaped_home = json.dumps(resolved_home)[1:-1]
    raw = src_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    rendered = raw.replace("${HOME}", escaped_home)
    json.loads(rendered)
    return rendered


def sha256_bytes(data: bytes) -> str:
    """Compute the hex SHA-256 digest for raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Compute the hex SHA-256 digest for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_text(dst: Path, content: str, mode: int = ACP_MODE) -> None:
    """Write UTF-8 text to `dst` through a temp file and `os.replace`."""
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


def sync_acp_json(
    system_dir: Path, target: Path, home: Path | None = None
) -> tuple[bool, str]:
    """Render `safehouse/acp.json` and sync `~/.jetbrains/acp.json` if missing or stale."""
    try:
        rendered = render_acp_json(system_dir, home=home)
    except (OSError, ValueError) as exc:
        return False, f"[FAIL] {exc}"

    if target.is_dir() and not target.is_symlink():
        return False, f"[FAIL] target is a directory: ~/.jetbrains/acp.json ({target})"

    expected_sha = sha256_bytes(rendered.encode("utf-8"))
    exists = target.exists() or target.is_symlink()

    if not exists:
        try:
            atomic_write_text(target, rendered, ACP_MODE)
        except OSError as exc:
            return False, f"[FAIL] could not install ~/.jetbrains/acp.json: {exc}"
        return True, f"[INSTALLED] ~/.jetbrains/acp.json (mode {ACP_MODE:04o})"

    if target.is_symlink():
        reason = "broken symlink replaced" if not target.exists() else "symlink replaced"
        try:
            atomic_write_text(target, rendered, ACP_MODE)
        except OSError as exc:
            return False, f"[FAIL] could not update ~/.jetbrains/acp.json: {exc}"
        return True, f"[UPDATED] ~/.jetbrains/acp.json ({reason})"

    try:
        actual_sha = sha256_file(target)
        actual_mode = stat.S_IMODE(target.stat().st_mode)
    except OSError as exc:
        return False, f"[FAIL] cannot inspect ~/.jetbrains/acp.json: {exc}"

    if actual_sha != expected_sha:
        try:
            atomic_write_text(target, rendered, ACP_MODE)
        except OSError as exc:
            return False, f"[FAIL] could not update ~/.jetbrains/acp.json: {exc}"
        return (
            True,
            f"[UPDATED] ~/.jetbrains/acp.json (sha256 {actual_sha[:12]} -> {expected_sha[:12]})",
        )

    if actual_mode != ACP_MODE:
        try:
            os.chmod(target, ACP_MODE)
        except OSError as exc:
            return False, f"[FAIL] could not chmod ~/.jetbrains/acp.json: {exc}"
        return (
            True,
            f"[UPDATED] ~/.jetbrains/acp.json (mode {actual_mode:04o} -> {ACP_MODE:04o})",
        )

    return True, "[OK] ~/.jetbrains/acp.json (unchanged)"


def check_acp_json(
    system_dir: Path, target: Path, home: Path | None = None
) -> tuple[bool, str]:
    """Verify `~/.jetbrains/acp.json` is a regular file matching rendered `acp.json`."""
    try:
        rendered = render_acp_json(system_dir, home=home)
    except (OSError, ValueError) as exc:
        return False, f"[FAIL] {exc}"

    if not target.exists() and not target.is_symlink():
        return False, f"[FAIL] missing: ~/.jetbrains/acp.json ({target})"

    if target.is_symlink():
        link_target = os.readlink(target)
        if not target.exists():
            return False, f"[FAIL] broken symlink: ~/.jetbrains/acp.json -> {link_target}"
        return (
            False,
            f"[FAIL] symlink (expected regular file): ~/.jetbrains/acp.json -> {link_target}",
        )

    if target.is_dir():
        return (
            False,
            f"[FAIL] expected file, found directory: ~/.jetbrains/acp.json ({target})",
        )

    expected_sha = sha256_bytes(rendered.encode("utf-8"))
    try:
        actual_sha = sha256_file(target)
        actual_mode = stat.S_IMODE(target.stat().st_mode)
    except OSError as exc:
        return False, f"[FAIL] cannot inspect ~/.jetbrains/acp.json: {exc}"

    if actual_sha != expected_sha:
        return (
            False,
            f"[FAIL] sha256 mismatch: ~/.jetbrains/acp.json "
            f"(expected {expected_sha[:12]} != local {actual_sha[:12]})",
        )

    if actual_mode != ACP_MODE:
        return (
            False,
            f"[FAIL] mode mismatch: ~/.jetbrains/acp.json "
            f"(expected {ACP_MODE:04o}, got {actual_mode:04o})",
        )

    return (
        True,
        f"[OK] ~/.jetbrains/acp.json (sha256 {expected_sha[:12]}, mode {ACP_MODE:04o})",
    )


def sync_local_profile(system_dir: Path, target: Path) -> tuple[bool, str]:
    """Render `safehouse/policies/*.sb` and sync `~/.config/safehouse/junie-local.sb`."""
    policies_dir = system_dir / "policies"
    try:
        rendered, policy_files = render_local_profile(policies_dir)
    except (OSError, ValueError) as exc:
        return False, f"[FAIL] {exc}"

    if target.is_dir() and not target.is_symlink():
        return (
            False,
            f"[FAIL] target is a directory: ~/.config/safehouse/junie-local.sb ({target})",
        )

    expected_sha = sha256_bytes(rendered.encode("utf-8"))
    exists = target.exists() or target.is_symlink()

    if not exists:
        try:
            atomic_write_text(target, rendered, POLICY_MODE)
        except OSError as exc:
            return (
                False,
                f"[FAIL] could not install ~/.config/safehouse/junie-local.sb: {exc}",
            )
        return (
            True,
            f"[INSTALLED] ~/.config/safehouse/junie-local.sb (mode {POLICY_MODE:04o}, "
            f"from {len(policy_files)} policy file(s))",
        )

    if target.is_symlink():
        reason = "broken symlink replaced" if not target.exists() else "symlink replaced"
        try:
            atomic_write_text(target, rendered, POLICY_MODE)
        except OSError as exc:
            return (
                False,
                f"[FAIL] could not update ~/.config/safehouse/junie-local.sb: {exc}",
            )
        return (
            True,
            f"[UPDATED] ~/.config/safehouse/junie-local.sb ({reason}, "
            f"from {len(policy_files)} policy file(s))",
        )

    try:
        actual_sha = sha256_file(target)
        actual_mode = stat.S_IMODE(target.stat().st_mode)
    except OSError as exc:
        return (
            False,
            f"[FAIL] cannot inspect ~/.config/safehouse/junie-local.sb: {exc}",
        )

    if actual_sha != expected_sha:
        try:
            atomic_write_text(target, rendered, POLICY_MODE)
        except OSError as exc:
            return (
                False,
                f"[FAIL] could not update ~/.config/safehouse/junie-local.sb: {exc}",
            )
        return (
            True,
            f"[UPDATED] ~/.config/safehouse/junie-local.sb "
            f"(sha256 {actual_sha[:12]} -> {expected_sha[:12]}, "
            f"from {len(policy_files)} policy file(s))",
        )

    if actual_mode != POLICY_MODE:
        try:
            os.chmod(target, POLICY_MODE)
        except OSError as exc:
            return (
                False,
                f"[FAIL] could not chmod ~/.config/safehouse/junie-local.sb: {exc}",
            )
        return (
            True,
            f"[UPDATED] ~/.config/safehouse/junie-local.sb "
            f"(mode {actual_mode:04o} -> {POLICY_MODE:04o})",
        )

    return (
        True,
        f"[OK] ~/.config/safehouse/junie-local.sb (unchanged, {len(policy_files)} policy file(s))",
    )


def check_local_profile(system_dir: Path, target: Path) -> tuple[bool, str]:
    """Verify `~/.config/safehouse/junie-local.sb` is a regular file matching `policies/*.sb`."""
    policies_dir = system_dir / "policies"
    try:
        rendered, policy_files = render_local_profile(policies_dir)
    except (OSError, ValueError) as exc:
        return False, f"[FAIL] {exc}"

    if not target.exists() and not target.is_symlink():
        return (
            False,
            f"[FAIL] missing: ~/.config/safehouse/junie-local.sb ({target})",
        )

    if target.is_symlink():
        link_target = os.readlink(target)
        if not target.exists():
            return (
                False,
                f"[FAIL] broken symlink: ~/.config/safehouse/junie-local.sb -> {link_target}",
            )
        return (
            False,
            f"[FAIL] symlink (expected regular file): ~/.config/safehouse/junie-local.sb -> {link_target}",
        )

    if target.is_dir():
        return (
            False,
            f"[FAIL] expected file, found directory: ~/.config/safehouse/junie-local.sb ({target})",
        )

    expected_sha = sha256_bytes(rendered.encode("utf-8"))
    try:
        actual_sha = sha256_file(target)
        actual_mode = stat.S_IMODE(target.stat().st_mode)
    except OSError as exc:
        return (
            False,
            f"[FAIL] cannot inspect ~/.config/safehouse/junie-local.sb: {exc}",
        )

    if actual_sha != expected_sha:
        return (
            False,
            f"[FAIL] sha256 mismatch: ~/.config/safehouse/junie-local.sb "
            f"(expected {expected_sha[:12]} != local {actual_sha[:12]})",
        )

    if actual_mode != POLICY_MODE:
        return (
            False,
            f"[FAIL] mode mismatch: ~/.config/safehouse/junie-local.sb "
            f"(expected {POLICY_MODE:04o}, got {actual_mode:04o})",
        )

    return (
        True,
        f"[OK] ~/.config/safehouse/junie-local.sb (sha256 {expected_sha[:12]}, "
        f"mode {POLICY_MODE:04o}, {len(policy_files)} policy file(s))",
    )
