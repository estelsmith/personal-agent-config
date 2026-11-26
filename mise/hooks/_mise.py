"""Helpers for managing ~/bin/mise, ~/.bash_profile activation, and global Mise tools."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import stat
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = None  # type: ignore[assignment]


MISE_RELEASES_LATEST_URL = "https://github.com/jdx/mise/releases/latest"
MISE_RELEASES_DOWNLOAD_BASE = "https://github.com/jdx/mise/releases/download"
MISE_ACTIVATE_LINE = 'eval "$(mise activate bash)"'
_MISE_ACTIVATE_RE = re.compile(r"\bmise\s+activate\s+bash\b")
_DIRENV_HOOK_RE = re.compile(r"\bdirenv\s+hook\s+bash\b")


@dataclass(frozen=True)
class ToolSpec:
    """Normalized global Mise tool specification from [tools]."""

    version: str
    options: tuple[tuple[str, str], ...] = ()

    def to_cli_spec(self, tool: str) -> str:
        if self.options:
            opts = ",".join(f"{k}={v}" for k, v in self.options)
            return f"{tool}[{opts}]@{self.version}"
        return f"{tool}@{self.version}"


def _normalize_tool_spec(raw: object) -> ToolSpec:
    if isinstance(raw, dict):
        version = str(raw.get("version", "")).strip()
        opts: dict[str, str] = {}
        for k, v in raw.items():
            if k == "version":
                continue
            key = str(k).strip()
            if not key:
                continue
            if isinstance(v, list):
                val_str = ",".join(str(item).strip() for item in v if str(item).strip())
            elif isinstance(v, bool):
                val_str = "true" if v else "false"
            elif key == "extras":
                val_str = ",".join(part.strip() for part in str(v).split(",") if part.strip())
            else:
                val_str = str(v).strip()
            if val_str:
                opts[key] = val_str
        return ToolSpec(version=version, options=tuple(sorted(opts.items())))
    return ToolSpec(version=str(raw).strip())


def _parse_fallback_toml_value(raw_val: str) -> object:
    val = raw_val.strip()
    if val.startswith("{") and val.endswith("}"):
        inner = val[1:-1].strip()
        table: dict[str, object] = {}
        # Split on commas outside [...] brackets
        parts: list[str] = []
        buf: list[str] = []
        depth = 0
        for ch in inner:
            if ch == "[":
                depth += 1
            elif ch == "]" and depth > 0:
                depth -= 1
            if ch == "," and depth == 0:
                parts.append("".join(buf))
                buf = []
            else:
                buf.append(ch)
        if buf:
            parts.append("".join(buf))
        for part in parts:
            if "=" not in part:
                continue
            tk, tv = part.split("=", 1)
            tk = tk.strip().strip('"').strip("'")
            tv = tv.strip()
            if tv.startswith("[") and tv.endswith("]"):
                items = [
                    x.strip().strip('"').strip("'")
                    for x in tv[1:-1].split(",")
                    if x.strip().strip('"').strip("'")
                ]
                table[tk] = items
            else:
                table[tk] = tv.strip('"').strip("'")
        return table
    return val.strip('"').strip("'")


def parse_toml_tools(toml_path: Path) -> dict[str, ToolSpec]:
    """Read the [tools] table from a TOML file as {tool_name: ToolSpec}."""
    raw = toml_path.read_text(encoding="utf-8")
    if tomllib is not None:
        data = tomllib.loads(raw)
        tools = data.get("tools", {})
        if not isinstance(tools, dict):
            return {}
        return {str(k): _normalize_tool_spec(v) for k, v in tools.items()}

    # Minimal fallback parser for [tools] section if tomllib is unavailable.
    tools_out: dict[str, ToolSpec] = {}
    in_tools = False
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            in_tools = stripped[1:-1].strip() == "tools"
            continue
        if in_tools and "=" in stripped:
            key, val = stripped.split("=", 1)
            key = key.strip().strip('"').strip("'")
            if key:
                tools_out[key] = _normalize_tool_spec(_parse_fallback_toml_value(val))
    return tools_out


def load_desired_tools(system_dir: Path) -> dict[str, ToolSpec]:
    """Load global tool specifications from mise/tools.toml."""
    tools_file = system_dir / "tools.toml"
    if not tools_file.is_file():
        raise FileNotFoundError(f"missing {tools_file}")
    tools = parse_toml_tools(tools_file)
    if not tools:
        raise ValueError(f"no tools defined in {tools_file}")
    return tools


def _atomic_write_text(path: Path, content: str, mode: int) -> None:
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


def _has_active_mise_activate(content: str) -> bool:
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Strip trailing comment if unquoted
        code_part = stripped.split("#", 1)[0]
        if _MISE_ACTIVATE_RE.search(code_part):
            return True
    return False


def check_bash_profile(bash_profile: Path) -> tuple[bool, str]:
    """Verify ~/.bash_profile contains an active `mise activate bash` hook."""
    if bash_profile.is_symlink() and not bash_profile.exists():
        return False, f"[FAIL] ~/.bash_profile is a broken symlink -> {os.readlink(bash_profile)}"
    if bash_profile.is_dir():
        return False, "[FAIL] ~/.bash_profile is a directory"
    if not bash_profile.is_file():
        return (
            False,
            f'[FAIL] ~/.bash_profile does not exist (expected `{MISE_ACTIVATE_LINE}`)',
        )

    content = bash_profile.read_text(encoding="utf-8")
    if _has_active_mise_activate(content):
        return True, f"[OK] ~/.bash_profile includes `{MISE_ACTIVATE_LINE}`"
    return (
        False,
        f"[FAIL] ~/.bash_profile is missing `{MISE_ACTIVATE_LINE}` (run bin/install mise to add it)",
    )


def sync_bash_profile(bash_profile: Path) -> tuple[str, str]:
    """Ensure ~/.bash_profile contains `eval \"$(mise activate bash)\"`.

    Returns (status, message) where status is 'ok', 'added', or 'error'.
    """
    if bash_profile.is_symlink() and not bash_profile.exists():
        return "error", f"[FAIL] ~/.bash_profile is a broken symlink -> {os.readlink(bash_profile)}"
    if bash_profile.is_dir():
        return "error", "[FAIL] ~/.bash_profile is a directory"

    if not bash_profile.exists():
        _atomic_write_text(bash_profile, f"{MISE_ACTIVATE_LINE}\n", 0o644)
        return "added", f"[ADDED] ~/.bash_profile: created with `{MISE_ACTIVATE_LINE}`"

    mode = stat.S_IMODE(bash_profile.stat().st_mode)
    content = bash_profile.read_text(encoding="utf-8")
    if _has_active_mise_activate(content):
        return "ok", f"[OK] ~/.bash_profile already includes `{MISE_ACTIVATE_LINE}`"

    lines = content.splitlines(keepends=True)
    insert_idx: int | None = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _DIRENV_HOOK_RE.search(stripped):
            insert_idx = idx
            break

    if insert_idx is not None:
        new_lines = lines[:insert_idx] + [f"{MISE_ACTIVATE_LINE}\n"] + lines[insert_idx:]
        updated = "".join(new_lines)
    else:
        sep = "" if (not content or content.endswith("\n")) else "\n"
        updated = f"{content}{sep}{MISE_ACTIVATE_LINE}\n"

    _atomic_write_text(bash_profile, updated, mode)
    return "added", f"[ADDED] ~/.bash_profile: added `{MISE_ACTIVATE_LINE}`"


def detect_platform() -> tuple[str, str]:
    """Return (os_name, arch_name) matching jdx/mise release asset naming."""
    sys_name = platform.system().lower()
    if sys_name == "darwin":
        os_name = "macos"
    elif sys_name == "linux":
        os_name = "linux"
    else:
        raise RuntimeError(f"Unsupported OS for mise download: {platform.system()}")

    machine = platform.machine().lower()
    arch_map = {
        "arm64": "arm64",
        "aarch64": "arm64",
        "x86_64": "x64",
        "amd64": "x64",
    }
    arch_name = arch_map.get(machine)
    if arch_name is None:
        raise RuntimeError(f"Unsupported architecture for mise download: {platform.machine()}")
    return os_name, arch_name


def _resolve_latest_tag() -> str:
    override = os.environ.get("MISE_RELEASE_TAG", "").strip()
    if override:
        return override

    latest_url = os.environ.get("MISE_RELEASES_LATEST_URL", MISE_RELEASES_LATEST_URL).strip()
    if shutil.which("curl"):
        res = subprocess.run(
            ["curl", "-fsSLI", "-o", "/dev/null", "-w", "%{url_effective}", latest_url],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0 and res.stdout.strip():
            effective = res.stdout.strip().rstrip("/")
            tag = effective.rsplit("/", 1)[-1]
            if tag and tag != "latest":
                return tag

    req = urllib.request.Request(latest_url, method="HEAD")
    with urllib.request.urlopen(req, timeout=30) as resp:
        effective = resp.geturl().rstrip("/")
        tag = effective.rsplit("/", 1)[-1]
        if not tag or tag == "latest":
            raise RuntimeError(f"Could not determine latest mise release tag from {effective}")
        return tag


def _download_file(url: str, dst: Path) -> None:
    if shutil.which("curl"):
        res = subprocess.run(
            ["curl", "-fsSL", "-o", str(dst), url],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            return
        err = res.stderr.strip() or f"curl exited {res.returncode}"
        raise RuntimeError(f"Failed to download {url}: {err}")

    try:
        with urllib.request.urlopen(url, timeout=60) as resp, dst.open("wb") as out_fh:
            shutil.copyfileobj(resp, out_fh)
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to download {url}: {exc}") from exc


def check_mise_binary(mise_bin: Path) -> tuple[bool, str]:
    """Check that ~/bin/mise exists, is executable, and reports --version."""
    if mise_bin.is_symlink() and not mise_bin.exists():
        return False, f"[FAIL] ~/bin/mise is a broken symlink -> {os.readlink(mise_bin)}"
    if mise_bin.is_dir():
        return False, "[FAIL] ~/bin/mise is a directory"
    if not mise_bin.is_file():
        return False, "[FAIL] missing ~/bin/mise (run bin/install mise to download from GitHub releases)"
    if not os.access(mise_bin, os.X_OK):
        return False, "[FAIL] ~/bin/mise is not executable"

    res = subprocess.run([str(mise_bin), "--version"], capture_output=True, text=True)
    if res.returncode != 0:
        err = res.stderr.strip() or f"exit {res.returncode}"
        return False, f"[FAIL] ~/bin/mise --version failed: {err}"
    version = res.stdout.strip().splitlines()[0] if res.stdout.strip() else "unknown"
    return True, f"[OK] ~/bin/mise ({version})"


def ensure_mise_binary(mise_bin: Path) -> tuple[str, str]:
    """Ensure ~/bin/mise exists and is executable; download from GitHub releases if missing."""
    if mise_bin.is_symlink() and not mise_bin.exists():
        return "error", f"[FAIL] ~/bin/mise is a broken symlink -> {os.readlink(mise_bin)}"
    if mise_bin.is_dir():
        return "error", "[FAIL] ~/bin/mise is a directory"

    if mise_bin.is_file() and os.access(mise_bin, os.X_OK):
        res = subprocess.run([str(mise_bin), "--version"], capture_output=True, text=True)
        if res.returncode == 0:
            version = res.stdout.strip().splitlines()[0] if res.stdout.strip() else "unknown"
            return "ok", f"[OK] ~/bin/mise already installed ({version})"

    download_url = os.environ.get("MISE_DOWNLOAD_URL", "").strip()
    if not download_url:
        os_name, arch_name = detect_platform()
        tag = _resolve_latest_tag()
        base = os.environ.get("MISE_RELEASES_DOWNLOAD_BASE", MISE_RELEASES_DOWNLOAD_BASE).rstrip("/")
        download_url = f"{base}/{tag}/mise-{tag}-{os_name}-{arch_name}"

    mise_bin.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".mise.", dir=str(mise_bin.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        _download_file(download_url, tmp_path)
        os.chmod(tmp_path, 0o755)
        verify = subprocess.run([str(tmp_path), "--version"], capture_output=True, text=True)
        if verify.returncode != 0:
            err = verify.stderr.strip() or f"exit {verify.returncode}"
            raise RuntimeError(f"Downloaded binary failed --version check: {err}")
        version = verify.stdout.strip().splitlines()[0] if verify.stdout.strip() else "unknown"
        os.replace(tmp_path, mise_bin)
        return "installed", f"[INSTALLED] ~/bin/mise from {download_url} ({version})"
    except Exception as exc:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return "error", f"[FAIL] could not install ~/bin/mise: {exc}"


def _installed_versions_by_tool(mise_bin: Path, home: Path) -> tuple[bool, dict[str, list[dict]], str]:
    res = subprocess.run(
        [str(mise_bin), "ls", "--global", "--json"],
        cwd=str(home),
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        err = res.stderr.strip() or f"exit {res.returncode}"
        return False, {}, f"[FAIL] mise ls --global --json failed: {err}"
    try:
        parsed = json.loads(res.stdout or "{}")
    except json.JSONDecodeError as exc:
        return False, {}, f"[FAIL] invalid JSON from mise ls --global --json: {exc}"
    if not isinstance(parsed, dict):
        return False, {}, "[FAIL] unexpected JSON shape from mise ls --global --json"
    return True, parsed, ""


def check_global_tools(
    mise_bin: Path,
    config_toml: Path,
    desired_tools: dict[str, ToolSpec],
    home: Path,
) -> tuple[bool, list[str]]:
    """Verify global ~/.config/mise/config.toml has desired tools and mise reports them installed."""
    messages: list[str] = []
    if not config_toml.is_file():
        return False, [
            f"[FAIL] missing {config_toml} (run bin/install mise to configure global tools)"
        ]

    configured = parse_toml_tools(config_toml)
    config_ok = True
    for tool, expected_spec in desired_tools.items():
        actual_spec = configured.get(tool)
        if actual_spec is None:
            messages.append(
                f"[FAIL] {config_toml} is missing global tool '{tool}' ({expected_spec.to_cli_spec(tool)})"
            )
            config_ok = False
        elif actual_spec != expected_spec:
            messages.append(
                f"[FAIL] {config_toml} global tool '{tool}' is "
                f"'{actual_spec.to_cli_spec(tool)}', expected '{expected_spec.to_cli_spec(tool)}'"
            )
            config_ok = False

    ls_ok, ls_data, ls_err = _installed_versions_by_tool(mise_bin, home)
    if not ls_ok:
        messages.append(ls_err)
        return False, messages

    install_ok = True
    for tool, expected_spec in desired_tools.items():
        entries = ls_data.get(tool, [])
        matched = [
            item
            for item in entries
            if isinstance(item, dict)
            and str(item.get("requested_version", "")) == expected_spec.version
            and item.get("installed") is True
        ]
        if not matched:
            messages.append(
                f"[FAIL] mise global tool '{expected_spec.to_cli_spec(tool)}' is not installed (run bin/install mise)"
            )
            install_ok = False

    if config_ok and install_ok:
        summary = ", ".join(spec.to_cli_spec(k) for k, spec in desired_tools.items())
        messages.append(f"[OK] Global mise tools configured and installed: {summary}")
        return True, messages

    return False, messages


def _is_version_installed(ls_data: dict[str, list[dict]], tool: str, version: str) -> bool:
    for item in ls_data.get(tool, []):
        if (
            isinstance(item, dict)
            and str(item.get("requested_version", "")) == version
            and item.get("installed") is True
        ):
            return True
    return False


def sync_global_tools(
    mise_bin: Path,
    config_toml: Path,
    desired_tools: dict[str, ToolSpec],
    home: Path,
) -> tuple[bool, list[str]]:
    """Configure and install desired global tools via `mise use --global`."""
    already_ok, _ = check_global_tools(mise_bin, config_toml, desired_tools, home)
    if already_ok:
        summary = ", ".join(spec.to_cli_spec(k) for k, spec in desired_tools.items())
        return True, [f"[OK] Global mise tools already configured and installed: {summary}"]

    configured = parse_toml_tools(config_toml) if config_toml.is_file() else {}
    ls_ok, ls_data, _ = _installed_versions_by_tool(mise_bin, home)

    # `mise use --global` skips reinstalling when the target version is already on disk
    # even if tool options (such as pipx extras) changed; force-reinstall those tools.
    force_reinstall: list[str] = []
    if ls_ok:
        for tool, expected_spec in desired_tools.items():
            actual_spec = configured.get(tool)
            options_changed = (
                actual_spec is not None and actual_spec.options != expected_spec.options
            ) or (actual_spec is None and bool(expected_spec.options))
            if options_changed and _is_version_installed(ls_data, tool, expected_spec.version):
                force_reinstall.append(f"{tool}@{expected_spec.version}")

    specs = [spec.to_cli_spec(tool) for tool, spec in desired_tools.items()]
    res = subprocess.run(
        [str(mise_bin), "use", "--global", *specs],
        cwd=str(home),
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        err = res.stderr.strip() or res.stdout.strip() or f"exit {res.returncode}"
        return False, [f"[FAIL] mise use --global failed: {err}"]

    if force_reinstall:
        reinstall_res = subprocess.run(
            [str(mise_bin), "install", "--force", *force_reinstall],
            cwd=str(home),
            capture_output=True,
            text=True,
        )
        if reinstall_res.returncode != 0:
            err = (
                reinstall_res.stderr.strip()
                or reinstall_res.stdout.strip()
                or f"exit {reinstall_res.returncode}"
            )
            return False, [f"[FAIL] mise install --force failed: {err}"]

    return True, [f"[UPDATED] Configured and installed global mise tools: {', '.join(specs)}"]
