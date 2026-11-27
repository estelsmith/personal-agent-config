#!/usr/bin/env python3
"""Helpers to check and sync `LITELLM_MASTER_KEY` between `.env` and `~/.bash_profile`.

`junie-safehouse` passes `LITELLM_MASTER_KEY` into the sandbox from the
caller's shell env, so keeping `~/.bash_profile` in sync with `.env` keeps
clients and the Compose stack using the same key.
"""

from __future__ import annotations

import os
import re
import shlex
import stat
import sys
import tempfile
from pathlib import Path


EXPORT_LINE_RE = re.compile(
    r"^(?P<indent>[ \t]*)export[ \t]+LITELLM_MASTER_KEY(?:=(?P<rhs>.*)|[ \t]*(?:#.*)?)?$"
)


def parse_dotenv(path: Path) -> dict[str, str]:
    """Parse `key=value` pairs from a dotenv file (handling optional `export` and quotes)."""
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        values[key] = val
    return values


def _extract_exported_value(rhs: str | None) -> str | None:
    """Extract the assigned value from the right-hand side of an `export` line."""
    if rhs is None:
        return None
    stripped = rhs.strip()
    if not stripped or stripped.startswith("#"):
        return ""
    try:
        tokens = shlex.split(rhs, comments=True)
    except ValueError:
        return None
    if len(tokens) != 1:
        return None
    return tokens[0]


def _atomic_write_text(path: Path, content: str, mode: int) -> None:
    """Write `content` atomically beside `path` and preserve the target mode."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def _read_master_key(env_path: Path) -> tuple[str | None, str | None]:
    """Read `LITELLM_MASTER_KEY` from `env_path`, returning `(value, error_message)`."""
    if not env_path.is_file():
        return None, f"missing {env_path}"
    env_values = parse_dotenv(env_path)
    master_key = env_values.get("LITELLM_MASTER_KEY", "").strip()
    if not master_key:
        return None, f"{env_path} is missing non-empty LITELLM_MASTER_KEY"
    return master_key, None


def _validate_profile_target(profile_path: Path) -> str | None:
    """Return an error if `profile_path` is a broken symlink or a directory."""
    if profile_path.is_symlink() and not profile_path.exists():
        return f"~/.bash_profile is a broken symlink -> {os.readlink(profile_path)}"
    if profile_path.exists() and profile_path.is_dir():
        return "~/.bash_profile is a directory"
    return None


def check_bash_profile(env_path: Path, profile_path: Path) -> tuple[bool, str]:
    """Verify `~/.bash_profile` exports a single `LITELLM_MASTER_KEY` matching `env_path`."""
    master_key, err = _read_master_key(env_path)
    if err is not None:
        return (
            False,
            f"[FAIL] cannot verify ~/.bash_profile LITELLM_MASTER_KEY ({err})",
        )
    assert master_key is not None

    target_err = _validate_profile_target(profile_path)
    if target_err is not None:
        return False, f"[FAIL] {target_err}"

    if not profile_path.exists():
        return (
            False,
            "[FAIL] ~/.bash_profile does not exist (missing export LITELLM_MASTER_KEY; run bin/install to add it)",
        )

    lines = profile_path.read_text(encoding="utf-8").splitlines()
    matches = [m for line in lines if (m := EXPORT_LINE_RE.match(line)) is not None]

    if not matches:
        return (
            False,
            "[FAIL] ~/.bash_profile is missing export LITELLM_MASTER_KEY (run bin/install to add it)",
        )

    values = [_extract_exported_value(m.group("rhs")) for m in matches]
    if len(matches) == 1 and values[0] == master_key:
        return (
            True,
            "[OK] ~/.bash_profile exports LITELLM_MASTER_KEY matching ~/litellm-proxy/.env",
        )

    if len(matches) > 1 and all(v == master_key for v in values):
        return (
            False,
            "[FAIL] ~/.bash_profile has duplicate export LITELLM_MASTER_KEY lines (run bin/install to clean up)",
        )

    return (
        False,
        "[FAIL] ~/.bash_profile LITELLM_MASTER_KEY does not match ~/litellm-proxy/.env (run bin/install to update it)",
    )


def sync_bash_profile(env_path: Path, profile_path: Path) -> tuple[bool, str]:
    """Update or append `export LITELLM_MASTER_KEY` in `~/.bash_profile` (deduping extras)."""
    master_key, err = _read_master_key(env_path)
    if err is not None:
        return (
            False,
            f"[FAIL] cannot sync ~/.bash_profile LITELLM_MASTER_KEY ({err})",
        )
    assert master_key is not None

    target_err = _validate_profile_target(profile_path)
    if target_err is not None:
        return False, f"[FAIL] {target_err}"

    desired_line = f"export LITELLM_MASTER_KEY={shlex.quote(master_key)}"

    if not profile_path.exists():
        _atomic_write_text(profile_path, f"{desired_line}\n", 0o644)
        return (
            True,
            "[ADDED] ~/.bash_profile: added export LITELLM_MASTER_KEY (from ~/litellm-proxy/.env)",
        )

    write_target = profile_path.resolve() if profile_path.is_symlink() else profile_path
    existing_mode = stat.S_IMODE(write_target.stat().st_mode)
    raw_text = write_target.read_text(encoding="utf-8")
    lines = raw_text.splitlines()

    match_indices = [
        idx for idx, line in enumerate(lines) if EXPORT_LINE_RE.match(line) is not None
    ]

    if not match_indices:
        if not raw_text:
            new_text = f"{desired_line}\n"
        elif raw_text.endswith("\n"):
            new_text = f"{raw_text}{desired_line}\n"
        else:
            new_text = f"{raw_text}\n{desired_line}\n"
        _atomic_write_text(write_target, new_text, existing_mode)
        return (
            True,
            "[ADDED] ~/.bash_profile: added export LITELLM_MASTER_KEY (from ~/litellm-proxy/.env)",
        )

    first_idx = match_indices[0]
    first_match = EXPORT_LINE_RE.match(lines[first_idx])
    assert first_match is not None
    if (
        len(match_indices) == 1
        and _extract_exported_value(first_match.group("rhs")) == master_key
    ):
        return (
            True,
            "[OK] ~/.bash_profile: export LITELLM_MASTER_KEY already matches ~/litellm-proxy/.env",
        )

    indent = first_match.group("indent")
    duplicate_indices = set(match_indices[1:])
    new_lines: list[str] = []
    for idx, line in enumerate(lines):
        if idx == first_idx:
            new_lines.append(f"{indent}{desired_line}")
        elif idx not in duplicate_indices:
            new_lines.append(line)

    _atomic_write_text(write_target, "\n".join(new_lines) + "\n", existing_mode)
    return (
        True,
        "[UPDATED] ~/.bash_profile: updated export LITELLM_MASTER_KEY (from ~/litellm-proxy/.env)",
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for `litellm-proxy/hooks/post-install` (`sync`) and `doctor` (`check`)."""
    args = sys.argv[1:] if argv is None else argv
    action = args[0] if args else "check"
    home = Path.home()
    env_path = home / "litellm-proxy" / ".env"
    profile_path = home / ".bash_profile"

    if action == "sync":
        ok, message = sync_bash_profile(env_path, profile_path)
    elif action == "check":
        ok, message = check_bash_profile(env_path, profile_path)
    else:
        print(f"Usage: {Path(sys.argv[0]).name} [check|sync]", file=sys.stderr)
        return 2

    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
