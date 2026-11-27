#!/usr/bin/env python3
"""Helpers to check Docker Compose stack and LiteLLM endpoint health.

Shared by `doctor` (which fails on stopped containers) and `post-install`
(which passes `--fail-prefix` to decide whether to restart Compose).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_HEALTH_URL = "http://127.0.0.1:4000/health/liveliness"


def parse_compose_ps_json(output: str) -> list[dict]:
    """Parse either a JSON array or NDJSON lines from `docker compose ps --format json`."""
    text = output.strip()
    if not text:
        return []
    if text.startswith("["):
        data = json.loads(text)
        return [item for item in data if isinstance(item, dict)]
    items: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parsed = json.loads(line)
        if isinstance(parsed, dict):
            items.append(parsed)
    return items


def check_http_endpoint(url: str, *, fail_prefix: str = "[FAIL]") -> tuple[bool, str]:
    """Probe LiteLLM's liveliness URL and accept any non-5xx HTTP response.

    An auth 4xx still proves the proxy is up and serving, whereas 5xx or a
    connection error means the stack isn't healthy.
    """
    try:
        with urllib.request.urlopen(url, timeout=3.0) as resp:
            return True, f"[OK] litellm endpoint {url} responded HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        if exc.code < 500:
            return True, f"[OK] litellm endpoint {url} reachable (HTTP {exc.code})"
        return False, f"{fail_prefix} litellm endpoint {url} returned HTTP {exc.code}"
    except Exception as exc:
        return False, f"{fail_prefix} litellm endpoint {url} unreachable: {exc}"


def check_compose_stack(
    target_dir: Path,
    compose_file: Path,
    *,
    health_url: str | None = None,
    fail_prefix: str = "[FAIL]",
) -> tuple[bool, list[str]]:
    """Verify every service in `docker-compose.yml` is running/healthy and LiteLLM answers HTTP."""
    if not compose_file.is_file():
        return False, [f"{fail_prefix} missing {compose_file}"]

    base_cmd = [
        "docker",
        "compose",
        "--project-directory",
        str(target_dir),
        "-f",
        str(compose_file),
    ]

    svc_proc = subprocess.run(
        [*base_cmd, "config", "--services"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if svc_proc.returncode != 0:
        return False, [
            f"{fail_prefix} docker compose config failed: {svc_proc.stderr.strip()}"
        ]

    expected_services = [
        line.strip() for line in svc_proc.stdout.splitlines() if line.strip()
    ]

    ps_proc = subprocess.run(
        [*base_cmd, "ps", "--all", "--format", "json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if ps_proc.returncode != 0:
        return False, [
            f"{fail_prefix} docker compose ps failed: {ps_proc.stderr.strip()}"
        ]

    try:
        containers = parse_compose_ps_json(ps_proc.stdout)
    except json.JSONDecodeError as exc:
        return False, [
            f"{fail_prefix} could not parse docker compose ps JSON output: {exc}"
        ]

    by_service = {c.get("Service"): c for c in containers if c.get("Service")}

    ok = True
    messages: list[str] = []
    litellm_running = False
    for svc in expected_services:
        container = by_service.get(svc)
        if container is None:
            messages.append(
                f"{fail_prefix} service '{svc}' has no container (stack not running)"
            )
            ok = False
            continue

        state = str(container.get("State", "")).lower()
        health = str(container.get("Health", "")).lower()

        if state != "running":
            messages.append(
                f"{fail_prefix} service '{svc}' is not running (state={state or 'unknown'})"
            )
            ok = False
            continue

        if health and health != "healthy":
            messages.append(
                f"{fail_prefix} service '{svc}' is unhealthy (state={state}, health={health})"
            )
            ok = False
            continue

        health_label = health if health else "no healthcheck"
        messages.append(f"[OK] service '{svc}' running ({health_label})")
        if svc == "litellm":
            litellm_running = True

    if litellm_running:
        url = health_url or os.environ.get("LITELLM_HEALTH_URL", DEFAULT_HEALTH_URL)
        http_ok, http_msg = check_http_endpoint(url, fail_prefix=fail_prefix)
        messages.append(http_msg)
        if not http_ok:
            ok = False

    return ok, messages


def main(argv: list[str] | None = None) -> int:
    """CLI wrapper for checking `~/litellm-proxy` Compose health from shell hooks."""
    parser = argparse.ArgumentParser(
        description="Check litellm-proxy Docker Compose stack health."
    )
    parser.add_argument(
        "--fail-prefix",
        default="[FAIL]",
        help="Prefix for unhealthy/missing service messages (default: [FAIL]).",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    target_dir = Path.home() / "litellm-proxy"
    compose_file = target_dir / "docker-compose.yml"
    ok, messages = check_compose_stack(
        target_dir,
        compose_file,
        fail_prefix=args.fail_prefix,
    )
    for msg in messages:
        print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
