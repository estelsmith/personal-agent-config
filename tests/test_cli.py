"""Integration tests for bin/doctor and bin/install."""

from __future__ import annotations

import http.server
import json
import os
import pty
import shutil
import stat
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
BIN_DOCTOR = REPO_ROOT / "bin" / "doctor"
BIN_INSTALL = REPO_ROOT / "bin" / "install"


class _OkHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"I'm alive!")

    def log_message(self, format, *args):
        return


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-cfg-test-"))
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.fake_bin = self.tmp / "fake_bin"
        self.fake_bin.mkdir()
        self.docker_log = self.tmp / "docker.log"
        self.docker_state = self.tmp / "docker_state.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _base_env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["NO_COLOR"] = "1"
        env["PATH"] = f"{self.fake_bin}:{env.get('PATH', '')}"
        env["FAKE_DOCKER_LOG"] = str(self.docker_log)
        env["FAKE_DOCKER_STATE"] = str(self.docker_state)
        if extra:
            env.update(extra)
        return env

    def _install_fake_docker(
        self,
        *,
        daemon_ok: bool = True,
        containers: list[dict] | None = None,
    ) -> None:
        if containers is None:
            containers = [
                {"Service": "litellm", "State": "running", "Health": ""},
                {
                    "Service": "gemini-decision-adapter",
                    "State": "running",
                    "Health": "healthy",
                },
                {"Service": "db", "State": "running", "Health": "healthy"},
            ]
        self.docker_state.write_text(
            json.dumps({"daemon_ok": daemon_ok, "containers": containers}),
            encoding="utf-8",
        )
        script = self.fake_bin / "docker"
        script.write_text(
            """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

log_path = Path(os.environ["FAKE_DOCKER_LOG"])
with log_path.open("a", encoding="utf-8") as fh:
    fh.write(" ".join(sys.argv[1:]) + "\\n")

state = json.loads(Path(os.environ["FAKE_DOCKER_STATE"]).read_text(encoding="utf-8"))
args = sys.argv[1:]

if args == ["info"]:
    if state.get("daemon_ok", True):
        sys.exit(0)
    print("Cannot connect to the Docker daemon", file=sys.stderr)
    sys.exit(1)

if len(args) >= 1 and args[0] == "compose":
    if "config" in args and "--services" in args:
        print("litellm\\ngemini-decision-adapter\\ndb")
        sys.exit(0)
    if "ps" in args and "--format" in args and "json" in args:
        for item in state.get("containers", []):
            print(json.dumps(item))
        sys.exit(0)
    if "ps" in args:
        print("NAME  STATUS")
        sys.exit(0)
    sys.exit(0)

sys.exit(0)
""",
            encoding="utf-8",
        )
        script.chmod(0o755)

    def _run(
        self, cmd: Path, args: list[str], extra_env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(cmd), *args],
            env=self._base_env(extra_env),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def _run_tty(
        self, cmd: Path, args: list[str], extra_env: dict[str, str] | None = None
    ) -> tuple[int, str]:
        env = self._base_env(extra_env)
        env.pop("NO_COLOR", None)
        master_fd, slave_fd = pty.openpty()
        try:
            proc = subprocess.Popen(
                [str(cmd), *args],
                env=env,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
            )
        finally:
            os.close(slave_fd)

        chunks: list[bytes] = []
        try:
            while True:
                try:
                    data = os.read(master_fd, 4096)
                except OSError:
                    break
                if not data:
                    break
                chunks.append(data)
        finally:
            os.close(master_fd)

        rc = proc.wait()
        return rc, b"".join(chunks).decode("utf-8", errors="replace")

    def _make_isolated_repo(self, *, repo_env_content: str | None = None) -> Path:
        repo = self.tmp / "repo"
        shutil.copytree(
            REPO_ROOT / "bin",
            repo / "bin",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        shutil.copytree(
            REPO_ROOT / "litellm-proxy",
            repo / "litellm-proxy",
            ignore=shutil.ignore_patterns(".env", "__pycache__", "*.pyc"),
        )
        shutil.copytree(
            REPO_ROOT / "safehouse",
            repo / "safehouse",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        if repo_env_content is not None:
            env_path = repo / "litellm-proxy" / ".env"
            env_path.write_text(repo_env_content, encoding="utf-8")
            env_path.chmod(0o600)
        return repo

    def test_list_and_unknown_system(self) -> None:
        res = self._run(BIN_DOCTOR, ["--list"])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(
            res.stdout.splitlines(),
            ["docmancer", "junie", "litellm-proxy", "mise", "safehouse"],
        )

        bad = self._run(BIN_DOCTOR, ["does-not-exist"])
        self.assertEqual(bad.returncode, 2)
        self.assertIn("Unknown system(s): does-not-exist", bad.stderr)

    def test_litellm_install_doctor_and_drift_repair(self) -> None:
        self._install_fake_docker()
        repo = self._make_isolated_repo(repo_env_content=None)
        bin_doctor = repo / "bin" / "doctor"
        bin_install = repo / "bin" / "install"

        # Before install, doctor fails on missing files.
        pre = self._run(bin_doctor, ["litellm-proxy"])
        self.assertEqual(pre.returncode, 1)
        self.assertIn("missing: ~/litellm-proxy/config.yaml", pre.stdout)

        # Dry run must not write files or invoke docker.
        self.docker_log.unlink(missing_ok=True)
        dry = self._run(bin_install, ["--dry-run", "litellm-proxy"])
        self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
        self.assertFalse((self.home / "litellm-proxy").exists())
        self.assertFalse((self.home / ".bash_profile").exists())
        self.assertFalse(self.docker_log.exists())
        self.assertIn("hook=dry-run", dry.stdout)

        # Real install creates files, seeds .env (0600), syncs ~/.bash_profile, and runs compose workflow.
        inst = self._run(bin_install, ["litellm-proxy"])
        self.assertEqual(inst.returncode, 0, inst.stdout + inst.stderr)
        self.assertIn("installed=5", inst.stdout)
        self.assertIn("seeded=1", inst.stdout)
        self.assertIn("hook=ok", inst.stdout)
        self.assertIn("[ADDED] ~/.bash_profile", inst.stdout)

        bash_profile = self.home / ".bash_profile"
        self.assertTrue(bash_profile.is_file())
        self.assertEqual(
            bash_profile.read_text(encoding="utf-8"),
            "export LITELLM_MASTER_KEY=sk-local-change-me\n",
        )

        env_file = self.home / "litellm-proxy" / ".env"
        self.assertTrue(env_file.is_file())
        self.assertEqual(stat.S_IMODE(env_file.stat().st_mode), 0o600)

        docker_cmds = self.docker_log.read_text(encoding="utf-8").splitlines()
        self.assertTrue(any("pull --ignore-buildable" in c for c in docker_cmds))
        self.assertTrue(any("compose" in c and " build" in c for c in docker_cmds))
        self.assertTrue(any("compose" in c and " down" in c for c in docker_cmds))
        self.assertTrue(any("compose" in c and " up -d --wait" in c for c in docker_cmds))

        # Customize .env and verify re-install preserves it.
        custom_env = (
            "LITELLM_MASTER_KEY=sk-real-master\n"
            "ANTHROPIC_API_KEY=sk-ant-real\n"
            "GEMINI_API_KEY=real-gemini-key\n"
        )
        env_file.write_text(custom_env, encoding="utf-8")

        reinst = self._run(bin_install, ["--no-hooks", "litellm-proxy"])
        self.assertEqual(reinst.returncode, 0, reinst.stdout + reinst.stderr)
        self.assertEqual(env_file.read_text(encoding="utf-8"), custom_env)
        self.assertIn("seed exists, preserved", reinst.stdout)

        # Start ephemeral HTTP server to satisfy litellm liveliness probe.
        server = http.server.HTTPServer(("127.0.0.1", 0), _OkHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            health_url = f"http://127.0.0.1:{server.server_port}/health/liveliness"

            # Doctor catches that ~/.bash_profile still has the old seed key.
            doc_stale = self._run(
                bin_doctor,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(doc_stale.returncode, 1)
            self.assertIn(
                "~/.bash_profile LITELLM_MASTER_KEY does not match ~/litellm-proxy/.env",
                doc_stale.stdout,
            )

            # Running bin/install with unchanged manifest files and a healthy stack updates
            # ~/.bash_profile and skips docker compose pull/build/down/up.
            self.docker_log.unlink(missing_ok=True)
            sync_inst = self._run(
                bin_install,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(sync_inst.returncode, 0, sync_inst.stdout + sync_inst.stderr)
            self.assertIn("[UPDATED] ~/.bash_profile", sync_inst.stdout)
            self.assertIn(
                "Stack is already running and healthy; skipping image pull, build, and stack start.",
                sync_inst.stdout,
            )
            self.assertEqual(
                bash_profile.read_text(encoding="utf-8"),
                "export LITELLM_MASTER_KEY=sk-real-master\n",
            )
            unchanged_docker_cmds = self.docker_log.read_text(encoding="utf-8").splitlines()
            self.assertFalse(any("pull --ignore-buildable" in c for c in unchanged_docker_cmds))
            self.assertFalse(any("compose" in c and " build" in c for c in unchanged_docker_cmds))
            self.assertFalse(any("compose" in c and " down" in c for c in unchanged_docker_cmds))
            self.assertFalse(any("compose" in c and " up -d --wait" in c for c in unchanged_docker_cmds))
            self.assertTrue(any("compose" in c and " ps" in c for c in unchanged_docker_cmds))

            doc_ok = self._run(
                bin_doctor,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(doc_ok.returncode, 0, doc_ok.stdout + doc_ok.stderr)
            self.assertIn(
                "[OK] ~/.bash_profile exports LITELLM_MASTER_KEY matching ~/litellm-proxy/.env",
                doc_ok.stdout,
            )

            # Corrupt config.yaml and verify doctor catches SHA-256 mismatch.
            cfg = self.home / "litellm-proxy" / "config.yaml"
            cfg.write_text("tampered: true\n", encoding="utf-8")
            doc_bad = self._run(
                bin_doctor,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(doc_bad.returncode, 1)
            self.assertIn("sha256 mismatch: ~/litellm-proxy/config.yaml", doc_bad.stdout)

            # Repair via bin/install --no-hooks and re-check.
            repair = self._run(bin_install, ["--no-hooks", "litellm-proxy"])
            self.assertEqual(repair.returncode, 0)
            self.assertIn("updated=1", repair.stdout)

            doc_fixed = self._run(
                bin_doctor,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(doc_fixed.returncode, 0, doc_fixed.stdout + doc_fixed.stderr)

            # Force reinstall marks files updated (FILES_CHANGED=1) and runs pull/build/down/up.
            self.docker_log.unlink(missing_ok=True)
            forced = self._run(bin_install, ["--force", "litellm-proxy"])
            self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)
            self.assertIn("updated=5", forced.stdout)
            forced_docker_cmds = self.docker_log.read_text(encoding="utf-8").splitlines()
            self.assertTrue(any("pull --ignore-buildable" in c for c in forced_docker_cmds))
            self.assertTrue(any("compose" in c and " build" in c for c in forced_docker_cmds))
            self.assertTrue(any("compose" in c and " down" in c for c in forced_docker_cmds))
            self.assertTrue(any("compose" in c and " up -d --wait" in c for c in forced_docker_cmds))

            # Unhealthy container fails doctor.
            self._install_fake_docker(
                containers=[
                    {"Service": "litellm", "State": "running", "Health": ""},
                    {
                        "Service": "gemini-decision-adapter",
                        "State": "running",
                        "Health": "unhealthy",
                    },
                    {"Service": "db", "State": "running", "Health": "healthy"},
                ]
            )
            doc_unhealthy = self._run(
                bin_doctor,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(doc_unhealthy.returncode, 1)
            self.assertIn("service 'gemini-decision-adapter' is unhealthy", doc_unhealthy.stdout)

            # With unchanged manifest files and an unhealthy stack, bin/install skips
            # pull/build/down but still runs `compose up -d --wait`.
            self.docker_log.unlink(missing_ok=True)
            unhealthy_inst = self._run(
                bin_install,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(unhealthy_inst.returncode, 0, unhealthy_inst.stdout + unhealthy_inst.stderr)
            self.assertIn("Stack is not running or is unhealthy", unhealthy_inst.stdout)
            unhealthy_docker_cmds = self.docker_log.read_text(encoding="utf-8").splitlines()
            self.assertFalse(any("pull --ignore-buildable" in c for c in unhealthy_docker_cmds))
            self.assertFalse(any("compose" in c and " build" in c for c in unhealthy_docker_cmds))
            self.assertFalse(any("compose" in c and " down" in c for c in unhealthy_docker_cmds))
            self.assertTrue(any("compose" in c and " up -d --wait" in c for c in unhealthy_docker_cmds))

            # With unchanged manifest files and stopped/missing containers, bin/install starts stack.
            self._install_fake_docker(containers=[])
            self.docker_log.unlink(missing_ok=True)
            stopped_inst = self._run(
                bin_install,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(stopped_inst.returncode, 0, stopped_inst.stdout + stopped_inst.stderr)
            self.assertIn("Stack is not running or is unhealthy", stopped_inst.stdout)
            stopped_docker_cmds = self.docker_log.read_text(encoding="utf-8").splitlines()
            self.assertFalse(any("pull --ignore-buildable" in c for c in stopped_docker_cmds))
            self.assertFalse(any("compose" in c and " build" in c for c in stopped_docker_cmds))
            self.assertFalse(any("compose" in c and " down" in c for c in stopped_docker_cmds))
            self.assertTrue(any("compose" in c and " up -d --wait" in c for c in stopped_docker_cmds))

            # With healthy containers but unreachable HTTP endpoint, bin/install starts stack.
            self._install_fake_docker()
            self.docker_log.unlink(missing_ok=True)
            server.shutdown()
            server.server_close()
            dead_http_inst = self._run(
                bin_install,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(dead_http_inst.returncode, 0, dead_http_inst.stdout + dead_http_inst.stderr)
            self.assertIn("Stack is not running or is unhealthy", dead_http_inst.stdout)
            dead_http_cmds = self.docker_log.read_text(encoding="utf-8").splitlines()
            self.assertFalse(any("pull --ignore-buildable" in c for c in dead_http_cmds))
            self.assertFalse(any("compose" in c and " build" in c for c in dead_http_cmds))
            self.assertFalse(any("compose" in c and " down" in c for c in dead_http_cmds))
            self.assertTrue(any("compose" in c and " up -d --wait" in c for c in dead_http_cmds))
        finally:
            server.shutdown()
            server.server_close()

    def test_safehouse_install_and_doctor(self) -> None:
        acp_path = self.home / ".jetbrains" / "acp.json"
        local_profile = self.home / ".config" / "safehouse" / "junie-local.sb"
        wrapper = self.home / "bin" / "junie-safehouse"
        policy_files = sorted(
            (REPO_ROOT / "safehouse" / "policies").glob("*.sb"),
            key=lambda p: p.name,
        )
        expected_acp = (REPO_ROOT / "safehouse" / "acp.json").read_text(
            encoding="utf-8"
        ).replace("${HOME}", str(self.home))

        # Dry run must not create manifest targets, ~/.config/safehouse/junie-local.sb, or ~/.jetbrains/acp.json.
        dry = self._run(BIN_INSTALL, ["--dry-run", "safehouse"])
        self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
        self.assertFalse(wrapper.exists())
        self.assertFalse(local_profile.exists())
        self.assertFalse(acp_path.exists())
        self.assertIn("hook=dry-run", dry.stdout)

        # Install syncs manifest files, compiles policies/*.sb, and renders ~/.jetbrains/acp.json.
        inst = self._run(BIN_INSTALL, ["safehouse"])
        self.assertEqual(inst.returncode, 0, inst.stdout + inst.stderr)
        self.assertIn("installed=1", inst.stdout)
        self.assertIn("[INSTALLED] ~/.config/safehouse/junie-local.sb", inst.stdout)
        self.assertIn("[INSTALLED] ~/.jetbrains/acp.json", inst.stdout)
        self.assertEqual(stat.S_IMODE(wrapper.stat().st_mode), 0o755)
        self.assertTrue(local_profile.is_file())
        self.assertFalse(local_profile.is_symlink())
        self.assertEqual(stat.S_IMODE(local_profile.stat().st_mode), 0o644)
        profile_text = local_profile.read_text(encoding="utf-8")
        self.assertIn('(subpath "/Applications")', profile_text)
        self.assertIn('(subpath "/Applications/Docker.app/Contents/Resources/bin")', profile_text)
        self.assertIn('(home-literal "/Applications/PhpStorm.app/Contents/MacOS/phpstorm")', profile_text)
        self.assertIn('(home-subpath "/Applications/PhpStorm.app/Contents/jbr")', profile_text)
        self.assertIn('(home-subpath "/.docmancer")', profile_text)
        self.assertIn('(home-subpath "/.homebrew")', profile_text)
        self.assertTrue(acp_path.is_file())
        self.assertFalse(acp_path.is_symlink())
        self.assertEqual(stat.S_IMODE(acp_path.stat().st_mode), 0o644)
        self.assertEqual(acp_path.read_text(encoding="utf-8"), expected_acp)
        self.assertNotIn("${HOME}", acp_path.read_text(encoding="utf-8"))
        acp_data = json.loads(acp_path.read_text(encoding="utf-8"))
        self.assertEqual(
            acp_data["agent_servers"]["junie-safehouse"]["command"],
            str(wrapper),
        )

        # Create prerequisite binaries under fake HOME.
        for rel in (".homebrew/bin/safehouse", ".local/bin/junie"):
            p = self.home / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            p.chmod(0o755)

        # Doctor passes cleanly with compiled junie-local.sb and ${HOME}-rendered ACP config.
        doc_ok = self._run(BIN_DOCTOR, ["safehouse"])
        self.assertEqual(doc_ok.returncode, 0, doc_ok.stdout + doc_ok.stderr)
        self.assertIn("[OK] ~/.config/safehouse/junie-local.sb", doc_ok.stdout)
        self.assertIn("[OK] ~/.jetbrains/acp.json", doc_ok.stdout)
        self.assertIn(f"[OK] ACP server command executable: {wrapper}", doc_ok.stdout)

        # Re-running install is idempotent.
        reinst = self._run(BIN_INSTALL, ["safehouse"])
        self.assertEqual(reinst.returncode, 0, reinst.stdout + reinst.stderr)
        self.assertIn(
            f"[OK] ~/.config/safehouse/junie-local.sb (unchanged, {len(policy_files)} policy file(s))",
            reinst.stdout,
        )
        self.assertIn("[OK] ~/.jetbrains/acp.json (unchanged)", reinst.stdout)

        # Mode drift on wrapper is caught by doctor and repaired by install.
        wrapper.chmod(0o644)
        doc_mode = self._run(BIN_DOCTOR, ["safehouse"])
        self.assertEqual(doc_mode.returncode, 1)
        self.assertIn("mode mismatch: ~/bin/junie-safehouse", doc_mode.stdout)

        repair = self._run(BIN_INSTALL, ["safehouse"])
        self.assertEqual(repair.returncode, 0, repair.stdout + repair.stderr)
        self.assertEqual(stat.S_IMODE(wrapper.stat().st_mode), 0o755)

        # Content drift in ~/.config/safehouse/junie-local.sb triggers doctor failure and install repair.
        local_profile.write_text(";; stale\n", encoding="utf-8")
        doc_profile_drift = self._run(BIN_DOCTOR, ["safehouse"])
        self.assertEqual(doc_profile_drift.returncode, 1)
        self.assertIn("sha256 mismatch: ~/.config/safehouse/junie-local.sb", doc_profile_drift.stdout)

        fix_profile = self._run(BIN_INSTALL, ["safehouse"])
        self.assertEqual(fix_profile.returncode, 0, fix_profile.stdout + fix_profile.stderr)
        self.assertIn("[UPDATED] ~/.config/safehouse/junie-local.sb", fix_profile.stdout)
        self.assertEqual(local_profile.read_text(encoding="utf-8"), profile_text)

        # Mode drift in ~/.config/safehouse/junie-local.sb triggers doctor failure and install repair.
        local_profile.chmod(0o600)
        doc_profile_mode = self._run(BIN_DOCTOR, ["safehouse"])
        self.assertEqual(doc_profile_mode.returncode, 1)
        self.assertIn("mode mismatch: ~/.config/safehouse/junie-local.sb", doc_profile_mode.stdout)

        fix_profile_mode = self._run(BIN_INSTALL, ["safehouse"])
        self.assertEqual(fix_profile_mode.returncode, 0, fix_profile_mode.stdout + fix_profile_mode.stderr)
        self.assertIn("mode 0600 -> 0644", fix_profile_mode.stdout)
        self.assertEqual(stat.S_IMODE(local_profile.stat().st_mode), 0o644)

        # Symlink target in ~/.config/safehouse/junie-local.sb is rejected and replaced without clobbering target.
        profile_sentinel = self.tmp / "profile-sentinel.sb"
        profile_sentinel.write_text("keep-profile-sentinel\n", encoding="utf-8")
        local_profile.unlink()
        local_profile.symlink_to(profile_sentinel)
        doc_profile_sym = self._run(BIN_DOCTOR, ["safehouse"])
        self.assertEqual(doc_profile_sym.returncode, 1)
        self.assertIn(
            "symlink (expected regular file): ~/.config/safehouse/junie-local.sb",
            doc_profile_sym.stdout,
        )

        fix_profile_sym = self._run(BIN_INSTALL, ["safehouse"])
        self.assertEqual(fix_profile_sym.returncode, 0, fix_profile_sym.stdout + fix_profile_sym.stderr)
        self.assertIn("symlink replaced", fix_profile_sym.stdout)
        self.assertFalse(local_profile.is_symlink())
        self.assertEqual(local_profile.read_text(encoding="utf-8"), profile_text)
        self.assertEqual(profile_sentinel.read_text(encoding="utf-8"), "keep-profile-sentinel\n")

        # Content drift in ~/.jetbrains/acp.json triggers doctor failure and install repair.
        acp_path.write_text('{"agent_servers": {}}\n', encoding="utf-8")
        doc_acp_drift = self._run(BIN_DOCTOR, ["safehouse"])
        self.assertEqual(doc_acp_drift.returncode, 1)
        self.assertIn("sha256 mismatch: ~/.jetbrains/acp.json", doc_acp_drift.stdout)

        fix_acp = self._run(BIN_INSTALL, ["safehouse"])
        self.assertEqual(fix_acp.returncode, 0, fix_acp.stdout + fix_acp.stderr)
        self.assertIn("[UPDATED] ~/.jetbrains/acp.json", fix_acp.stdout)
        self.assertEqual(acp_path.read_text(encoding="utf-8"), expected_acp)

        # Mode drift in ~/.jetbrains/acp.json triggers doctor failure and install repair.
        acp_path.chmod(0o600)
        doc_acp_mode = self._run(BIN_DOCTOR, ["safehouse"])
        self.assertEqual(doc_acp_mode.returncode, 1)
        self.assertIn("mode mismatch: ~/.jetbrains/acp.json", doc_acp_mode.stdout)

        fix_acp_mode = self._run(BIN_INSTALL, ["safehouse"])
        self.assertEqual(fix_acp_mode.returncode, 0, fix_acp_mode.stdout + fix_acp_mode.stderr)
        self.assertIn("mode 0600 -> 0644", fix_acp_mode.stdout)
        self.assertEqual(stat.S_IMODE(acp_path.stat().st_mode), 0o644)

        # Symlink target in ~/.jetbrains/acp.json is rejected and replaced without clobbering target.
        sentinel = self.tmp / "acp-sentinel.json"
        sentinel.write_text("keep-me\n", encoding="utf-8")
        acp_path.unlink()
        acp_path.symlink_to(sentinel)
        doc_acp_sym = self._run(BIN_DOCTOR, ["safehouse"])
        self.assertEqual(doc_acp_sym.returncode, 1)
        self.assertIn("symlink (expected regular file): ~/.jetbrains/acp.json", doc_acp_sym.stdout)

        fix_acp_sym = self._run(BIN_INSTALL, ["safehouse"])
        self.assertEqual(fix_acp_sym.returncode, 0, fix_acp_sym.stdout + fix_acp_sym.stderr)
        self.assertIn("symlink replaced", fix_acp_sym.stdout)
        self.assertFalse(acp_path.is_symlink())
        self.assertEqual(acp_path.read_text(encoding="utf-8"), expected_acp)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep-me\n")

    def test_symlink_replacement_does_not_clobber_target(self) -> None:
        sentinel = self.tmp / "sentinel.txt"
        sentinel.write_text("do-not-overwrite\n", encoding="utf-8")
        target = self.home / "bin" / "junie-safehouse"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(sentinel)

        res = self._run(BIN_INSTALL, ["--no-hooks", "safehouse"])
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertFalse(target.is_symlink())
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "do-not-overwrite\n")

    def test_custom_system_autodiscovery(self) -> None:
        # Build an isolated copy of bin/ plus a custom system to verify extensibility.
        mini_repo = self.tmp / "mini_repo"
        shutil.copytree(REPO_ROOT / "bin", mini_repo / "bin")
        custom = mini_repo / "my-agent"
        (custom / "hooks").mkdir(parents=True)
        (custom / "settings.json").write_text('{"ok": true}\n', encoding="utf-8")
        (custom / "manifest").write_text(
            "0644 settings.json ~/.my-agent/settings.json\n", encoding="utf-8"
        )
        hook_out = self.tmp / "hook_env.txt"
        post_hook = custom / "hooks" / "post-install"
        post_hook.write_text(
            f"#!/bin/sh\necho \"installed=$FILES_INSTALLED changed=$FILES_CHANGED\" > {hook_out}\n",
            encoding="utf-8",
        )
        post_hook.chmod(0o755)
        doc_hook = custom / "hooks" / "doctor"
        doc_hook.write_text("#!/bin/sh\necho 'custom check ok'\n", encoding="utf-8")
        doc_hook.chmod(0o755)

        inst = self._run(mini_repo / "bin" / "install", [])
        self.assertEqual(inst.returncode, 0, inst.stdout + inst.stderr)
        self.assertEqual(
            hook_out.read_text(encoding="utf-8").strip(), "installed=1 changed=1"
        )

        doc = self._run(mini_repo / "bin" / "doctor", [])
        self.assertEqual(doc.returncode, 0, doc.stdout + doc.stderr)
        self.assertIn("custom check ok", doc.stdout)

    def test_litellm_bash_profile_edge_cases(self) -> None:
        self._install_fake_docker()
        repo = self._make_isolated_repo(repo_env_content=None)
        bin_doctor = repo / "bin" / "doctor"
        bin_install = repo / "bin" / "install"
        env_dir = self.home / "litellm-proxy"
        env_dir.mkdir(parents=True, exist_ok=True)
        env_file = env_dir / ".env"
        env_file.write_text(
            "LITELLM_MASTER_KEY=sk-real-master\n"
            "ANTHROPIC_API_KEY=sk-ant-real\n"
            "GEMINI_API_KEY=real-gemini-key\n",
            encoding="utf-8",
        )
        env_file.chmod(0o600)

        # Existing ~/.bash_profile without trailing newline, with comments & similar var name.
        bash_profile = self.home / ".bash_profile"
        bash_profile.write_text(
            "# export LITELLM_MASTER_KEY=commented-out\n"
            "export LITELLM_MASTER_KEY_BACKUP=keep-this\n"
            "export PATH=\"$HOME/bin:$PATH\"",
            encoding="utf-8",
        )
        bash_profile.chmod(0o600)

        server = http.server.HTTPServer(("127.0.0.1", 0), _OkHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            health_url = f"http://127.0.0.1:{server.server_port}/health/liveliness"

            # Install syncs all manifest files first, then adds export to ~/.bash_profile.
            # Run doctor before install to verify missing export detection (install manifest first).
            pre_sync = self._run(bin_install, ["--no-hooks", "litellm-proxy"])
            self.assertEqual(pre_sync.returncode, 0, pre_sync.stdout + pre_sync.stderr)

            doc_missing = self._run(
                bin_doctor,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(doc_missing.returncode, 1)
            self.assertIn(
                "~/.bash_profile is missing export LITELLM_MASTER_KEY",
                doc_missing.stdout,
            )

            # Install appends export on a new line, preserving existing content and mode.
            inst_add = self._run(
                bin_install,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(inst_add.returncode, 0, inst_add.stdout + inst_add.stderr)
            self.assertIn("[ADDED] ~/.bash_profile", inst_add.stdout)
            self.assertEqual(stat.S_IMODE(bash_profile.stat().st_mode), 0o600)
            self.assertEqual(
                bash_profile.read_text(encoding="utf-8"),
                "# export LITELLM_MASTER_KEY=commented-out\n"
                "export LITELLM_MASTER_KEY_BACKUP=keep-this\n"
                "export PATH=\"$HOME/bin:$PATH\"\n"
                "export LITELLM_MASTER_KEY=sk-real-master\n",
            )

            # Second install reports already matches.
            inst_ok = self._run(
                bin_install,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(inst_ok.returncode, 0, inst_ok.stdout + inst_ok.stderr)
            self.assertIn(
                "[OK] ~/.bash_profile: export LITELLM_MASTER_KEY already matches",
                inst_ok.stdout,
            )

            # Quoted matching value is accepted by doctor and untouched by install.
            bash_profile.write_text(
                "export LITELLM_MASTER_KEY=\"sk-real-master\"\n",
                encoding="utf-8",
            )
            doc_quoted = self._run(
                bin_doctor,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(doc_quoted.returncode, 0, doc_quoted.stdout + doc_quoted.stderr)
            inst_quoted = self._run(
                bin_install,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(inst_quoted.returncode, 0, inst_quoted.stdout + inst_quoted.stderr)
            self.assertIn("already matches", inst_quoted.stdout)
            self.assertEqual(
                bash_profile.read_text(encoding="utf-8"),
                "export LITELLM_MASTER_KEY=\"sk-real-master\"\n",
            )

            # Duplicate export lines are flagged by doctor and cleaned up by install.
            bash_profile.write_text(
                "export LITELLM_MASTER_KEY=sk-old\n"
                "export PATH=\"$HOME/bin:$PATH\"\n"
                "export LITELLM_MASTER_KEY=sk-real-master\n",
                encoding="utf-8",
            )
            doc_dup = self._run(
                bin_doctor,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(doc_dup.returncode, 1)

            inst_dedup = self._run(
                bin_install,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(inst_dedup.returncode, 0, inst_dedup.stdout + inst_dedup.stderr)
            self.assertIn("[UPDATED] ~/.bash_profile", inst_dedup.stdout)
            self.assertEqual(
                bash_profile.read_text(encoding="utf-8"),
                "export LITELLM_MASTER_KEY=sk-real-master\n"
                "export PATH=\"$HOME/bin:$PATH\"\n",
            )
        finally:
            server.shutdown()
            server.server_close()

    def test_litellm_repo_env_syncs_and_updates_bash_profile(self) -> None:
        self._install_fake_docker()
        initial_env = (
            "LITELLM_MASTER_KEY=sk-initial-key\n"
            "ANTHROPIC_API_KEY=sk-ant-real\n"
            "GEMINI_API_KEY=real-gemini-key\n"
        )
        repo = self._make_isolated_repo(repo_env_content=initial_env)
        bin_doctor = repo / "bin" / "doctor"
        bin_install = repo / "bin" / "install"
        repo_env = repo / "litellm-proxy" / ".env"

        server = http.server.HTTPServer(("127.0.0.1", 0), _OkHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            health_url = f"http://127.0.0.1:{server.server_port}/health/liveliness"

            # Initial install syncs repo litellm-proxy/.env (not .env.example) and updates ~/.bash_profile.
            inst = self._run(
                bin_install,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(inst.returncode, 0, inst.stdout + inst.stderr)
            self.assertIn("installed=6", inst.stdout)
            self.assertIn("seeded=0", inst.stdout)
            self.assertIn("[ADDED] ~/.bash_profile", inst.stdout)

            target_env = self.home / "litellm-proxy" / ".env"
            self.assertEqual(target_env.read_text(encoding="utf-8"), initial_env)
            self.assertEqual(stat.S_IMODE(target_env.stat().st_mode), 0o600)
            bash_profile = self.home / ".bash_profile"
            self.assertEqual(
                bash_profile.read_text(encoding="utf-8"),
                "export LITELLM_MASTER_KEY=sk-initial-key\n",
            )

            doc_ok = self._run(
                bin_doctor,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(doc_ok.returncode, 0, doc_ok.stdout + doc_ok.stderr)

            # Rotate LITELLM_MASTER_KEY in repo's litellm-proxy/.env.
            rotated_env = (
                "LITELLM_MASTER_KEY=sk-rotated-key\n"
                "ANTHROPIC_API_KEY=sk-ant-real\n"
                "GEMINI_API_KEY=real-gemini-key\n"
            )
            repo_env.write_text(rotated_env, encoding="utf-8")

            # Doctor catches the sha256 mismatch on ~/litellm-proxy/.env.
            doc_drift = self._run(
                bin_doctor,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(doc_drift.returncode, 1)
            self.assertIn("sha256 mismatch: ~/litellm-proxy/.env", doc_drift.stdout)

            # Install updates ~/litellm-proxy/.env, updates ~/.bash_profile, and restarts compose.
            self.docker_log.unlink(missing_ok=True)
            inst_rotate = self._run(
                bin_install,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(
                inst_rotate.returncode, 0, inst_rotate.stdout + inst_rotate.stderr
            )
            self.assertIn("updated=1", inst_rotate.stdout)
            self.assertIn("[UPDATED] ~/litellm-proxy/.env", inst_rotate.stdout)
            self.assertIn("[UPDATED] ~/.bash_profile", inst_rotate.stdout)
            self.assertNotIn("already matches", inst_rotate.stdout)
            self.assertEqual(target_env.read_text(encoding="utf-8"), rotated_env)
            self.assertEqual(
                bash_profile.read_text(encoding="utf-8"),
                "export LITELLM_MASTER_KEY=sk-rotated-key\n",
            )
            rotated_cmds = self.docker_log.read_text(encoding="utf-8").splitlines()
            self.assertTrue(any("compose" in c and " down" in c for c in rotated_cmds))
            self.assertTrue(
                any("compose" in c and " up -d --wait" in c for c in rotated_cmds)
            )

            # Re-running install when nothing changed skips compose restart and reports already matches.
            self.docker_log.unlink(missing_ok=True)
            inst_noop = self._run(
                bin_install,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(
                inst_noop.returncode, 0, inst_noop.stdout + inst_noop.stderr
            )
            self.assertIn("unchanged=6", inst_noop.stdout)
            self.assertIn(
                "[OK] ~/.bash_profile: export LITELLM_MASTER_KEY already matches",
                inst_noop.stdout,
            )
            noop_cmds = self.docker_log.read_text(encoding="utf-8").splitlines()
            self.assertFalse(any("compose" in c and " down" in c for c in noop_cmds))
            self.assertFalse(
                any("compose" in c and " up -d --wait" in c for c in noop_cmds)
            )
        finally:
            server.shutdown()
            server.server_close()

    def test_install_status_line_colors_under_tty(self) -> None:
        mini_repo = self.tmp / "color_repo"
        shutil.copytree(
            REPO_ROOT / "bin",
            mini_repo / "bin",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

        alpha = mini_repo / "alpha"
        alpha.mkdir(parents=True)
        (alpha / "a.conf").write_text("a=1\n", encoding="utf-8")
        (alpha / "manifest").write_text(
            "0644 a.conf ~/.alpha/a.conf\n", encoding="utf-8"
        )

        beta = mini_repo / "beta"
        (beta / "hooks").mkdir(parents=True)
        (beta / "b.conf").write_text("b=1\n", encoding="utf-8")
        (beta / "manifest").write_text(
            "0644 b.conf ~/.beta/b.conf\n", encoding="utf-8"
        )
        fail_hook = beta / "hooks" / "post-install"
        fail_hook.write_text("#!/bin/sh\necho 'Error: hook boom'\nexit 1\n", encoding="utf-8")
        fail_hook.chmod(0o755)

        bin_install = mini_repo / "bin" / "install"

        # --dry-run with changes: yellow status line for alpha.
        rc_dry, out_dry = self._run_tty(bin_install, ["--dry-run", "alpha"])
        self.assertEqual(rc_dry, 0, out_dry)
        self.assertIn(
            "\033[33m  - alpha: installed=1, updated=0, seeded=0, unchanged=0, failed=0, hook=none\033[0m",
            out_dry,
        )

        # Real install with changes: also yellow status line for alpha.
        rc_inst, out_inst = self._run_tty(bin_install, ["alpha"])
        self.assertEqual(rc_inst, 0, out_inst)
        self.assertIn(
            "\033[33m  - alpha: installed=1, updated=0, seeded=0, unchanged=0, failed=0, hook=none\033[0m",
            out_inst,
        )
        self.assertNotIn("Failed Checks:", out_inst)

        # Second run with no changes for alpha (green) and failing hook for beta (red even with install change).
        rc_both, out_both = self._run_tty(bin_install, [])
        self.assertEqual(rc_both, 1, out_both)
        self.assertIn(
            "\033[32m  - alpha: installed=0, updated=0, seeded=0, unchanged=1, failed=0, hook=none\033[0m",
            out_both,
        )
        self.assertIn(
            "\033[31m  - beta: installed=1, updated=0, seeded=0, unchanged=0, failed=1, hook=failed (exit 1)\033[0m",
            out_both,
        )
        self.assertIn("Failed Checks:", out_both)
        self.assertIn("hooks/post-install failed (exit 1): Error: hook boom", out_both)

    def test_doctor_and_install_failed_checks_summary_at_bottom(self) -> None:
        self._install_fake_docker(
            containers=[
                {"Service": "litellm", "State": "running", "Health": ""},
                {
                    "Service": "gemini-decision-adapter",
                    "State": "running",
                    "Health": "unhealthy",
                },
                {"Service": "db", "State": "running", "Health": "healthy"},
            ]
        )
        repo = self._make_isolated_repo(repo_env_content=None)
        bin_doctor = repo / "bin" / "doctor"
        bin_install = repo / "bin" / "install"

        # Add a custom third system with a failing doctor hook that prints no [FAIL] tag.
        gamma = repo / "gamma"
        (gamma / "hooks").mkdir(parents=True)
        (gamma / "g.conf").write_text("ok\n", encoding="utf-8")
        (gamma / "manifest").write_text(
            "0644 g.conf ~/.gamma/g.conf\n", encoding="utf-8"
        )
        gamma_doc = gamma / "hooks" / "doctor"
        gamma_doc.write_text("#!/bin/sh\necho 'gamma daemon down'\nexit 2\n", encoding="utf-8")
        gamma_doc.chmod(0o755)

        # Install litellm-proxy and gamma cleanly, leaving safehouse missing its binaries.
        inst_ok = self._run(bin_install, ["gamma"])
        self.assertEqual(inst_ok.returncode, 0, inst_ok.stdout + inst_ok.stderr)
        self.assertNotIn("Failed Checks:", inst_ok.stdout)

        inst_lp = self._run(bin_install, ["litellm-proxy"])
        self.assertEqual(inst_lp.returncode, 0, inst_lp.stdout + inst_lp.stderr)

        # Doctor across gamma, litellm-proxy, and safehouse shows Failed Checks at the bottom after Summary.
        doc = self._run(bin_doctor, [])
        self.assertEqual(doc.returncode, 1)
        summary_idx = doc.stdout.index("Summary:")
        failed_idx = doc.stdout.index("Failed Checks:")
        self.assertGreater(failed_idx, summary_idx)

        failed_section = doc.stdout[failed_idx:]
        self.assertIn("  - gamma:", failed_section)
        self.assertIn("    - hooks/doctor failed (exit 2): gamma daemon down", failed_section)
        self.assertIn("  - litellm-proxy:", failed_section)
        self.assertIn(
            "    - hooks/doctor: service 'gemini-decision-adapter' is unhealthy (state=running, health=unhealthy)",
            failed_section,
        )
        self.assertIn("  - safehouse:", failed_section)
        self.assertIn("    - missing: ~/bin/junie-safehouse", failed_section)
        self.assertIn("    - hooks/doctor: missing safehouse binary:", failed_section)

        # Install failure across multiple systems (directory target conflict + docker daemon down).
        (self.home / ".gamma" / "g.conf").unlink()
        (self.home / ".gamma" / "g.conf").mkdir()
        self._install_fake_docker(daemon_ok=False)
        inst_fail = self._run(bin_install, ["--force", "gamma", "litellm-proxy"])
        self.assertEqual(inst_fail.returncode, 1)
        status_idx = inst_fail.stdout.index("Install Status:")
        inst_failed_idx = inst_fail.stdout.index("Failed Checks:")
        self.assertGreater(inst_failed_idx, status_idx)

        inst_failed_section = inst_fail.stdout[inst_failed_idx:]
        self.assertIn("  - gamma:", inst_failed_section)
        self.assertIn("    - target is a directory: ~/.gamma/g.conf", inst_failed_section)
        self.assertIn("  - litellm-proxy:", inst_failed_section)
        self.assertIn(
            "    - hooks/post-install failed (exit 1): Error: Docker daemon is not running or not reachable",
            inst_failed_section,
        )

    def _fake_mise_script(self, log_path: Path, *, installed_tools: bool = True) -> str:
        return f"""#!/usr/bin/env python3
import json
import os
import sys
import tomllib
from pathlib import Path

log_file = Path({str(log_path)!r})
with log_file.open("a", encoding="utf-8") as fh:
    fh.write(" ".join(sys.argv[1:]) + "\\n")

args = sys.argv[1:]
home = Path.home()
cfg_path = home / ".config" / "mise" / "config.toml"
conf_d = home / ".config" / "mise" / "conf.d"
state_path = home / ".fake_mise_installed.json"

def load_tools():
    if not cfg_path.is_file():
        return {{}}
    data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    out = {{}}
    for k, v in data.get("tools", {{}}).items():
        if isinstance(v, dict):
            ver = str(v.get("version", ""))
            opts = {{str(ok): (",".join(ov) if isinstance(ov, list) else str(ov)) for ok, ov in v.items() if ok != "version"}}
            out[str(k)] = {{"version": ver, "options": opts}}
        else:
            out[str(k)] = {{"version": str(v), "options": {{}}}}
    return out

def write_tools(tools):
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[tools]"]
    for k, spec in sorted(tools.items()):
        key_fmt = f'"{{k}}"' if ":" in k else k
        if spec["options"]:
            opts_parts = [f'version = "{{spec["version"]}}"']
            for ok, ov in sorted(spec["options"].items()):
                opts_parts.append(f'{{ok}} = "{{ov}}"')
            lines.append(f'{{key_fmt}} = {{{{ {{", ".join(opts_parts)}} }}}}')
        else:
            lines.append(f'{{key_fmt}} = "{{spec["version"]}}"')
    cfg_path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")

def load_state():
    if state_path.is_file():
        return json.loads(state_path.read_text(encoding="utf-8"))
    return {{"installed": {installed_tools!r}, "installed_tools": {{}}}}

def save_state(state):
    state_path.write_text(json.dumps(state), encoding="utf-8")

def ensure_docmancer_bins(ver, extras, with_pkgs=""):
    base = home / ".local" / "share" / "mise" / "installs" / "pipx-docmancer" / ver
    py_bin = base / "docmancer" / "bin" / "python"
    doc_bin = base / "bin" / "docmancer"
    marker = base / "extras.txt"
    with_marker = base / "with.txt"
    py_bin.parent.mkdir(parents=True, exist_ok=True)
    doc_bin.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(extras, encoding="utf-8")
    with_marker.write_text(with_pkgs, encoding="utf-8")
    py_bin.write_text(
        f'''#!{{sys.executable}}
import sys
from pathlib import Path
extras = Path({{str(marker)!r}}).read_text(encoding="utf-8").split(",")
with_pkgs = [p.lower() for p in Path({{str(with_marker)!r}}).read_text(encoding="utf-8").split(",") if p]
if len(sys.argv) >= 3 and sys.argv[1] == "-c" and "import openai" in sys.argv[2]:
    if "embeddings-openai" in extras:
        sys.exit(0)
    print("ModuleNotFoundError: No module named 'openai'", file=sys.stderr)
    sys.exit(1)
if len(sys.argv) >= 3 and sys.argv[1] == "-c" and "import socks" in sys.argv[2]:
    if "pysocks" in with_pkgs:
        sys.exit(0)
    print("ModuleNotFoundError: No module named 'socks'", file=sys.stderr)
    sys.exit(1)
sys.exit(0)
''',
        encoding="utf-8",
    )
    py_bin.chmod(0o755)
    doc_bin.write_text(f"#!{{py_bin}}\\n", encoding="utf-8")
    doc_bin.chmod(0o755)
    return doc_bin

def parse_cli_spec(spec):
    name_part, ver = spec.rsplit("@", 1)
    opts = {{}}
    if "[" in name_part and name_part.endswith("]"):
        name, opt_str = name_part[:-1].split("[", 1)
        for item in opt_str.split(","):
            if "=" in item:
                ok, ov = item.split("=", 1)
                opts[ok.strip()] = ov.strip()
        return name, ver, opts
    return name_part, ver, opts

def load_conf_d_env():
    env_map = {{}}
    if conf_d.is_dir():
        for p in sorted(conf_d.glob("*.toml")):
            data = tomllib.loads(p.read_text(encoding="utf-8"))
            for k, v in data.get("env", {{}}).items():
                env_map[str(k)] = str(v)
    return env_map

if args == ["--version"]:
    print("2026.11.14 macos-arm64 (fake)")
    sys.exit(0)

if args[:2] == ["use", "--global"]:
    tools = load_tools()
    state = load_state()
    state["installed"] = True
    inst_map = state.setdefault("installed_tools", {{}})
    for spec in args[2:]:
        name, ver, opts = parse_cli_spec(spec)
        tools[name] = {{"version": ver, "options": opts}}
        # Mimic real mise: only install if not already installed at that version.
        if name not in inst_map or inst_map[name].get("version") != ver:
            inst_map[name] = {{"version": ver, "extras": opts.get("extras", ""), "with": opts.get("with", "")}}
            if name == "pipx:docmancer":
                ensure_docmancer_bins(ver, opts.get("extras", ""), opts.get("with", ""))
    write_tools(tools)
    save_state(state)
    sys.exit(0)

if args[:2] == ["install", "--force"]:
    tools = load_tools()
    state = load_state()
    inst_map = state.setdefault("installed_tools", {{}})
    for spec in args[2:]:
        name, ver, _ = parse_cli_spec(spec)
        cfg_spec = tools.get(name, {{"version": ver, "options": {{}}}})
        extras = cfg_spec["options"].get("extras", "")
        with_pkgs = cfg_spec["options"].get("with", "")
        inst_map[name] = {{"version": cfg_spec["version"], "extras": extras, "with": with_pkgs}}
        if name == "pipx:docmancer":
            ensure_docmancer_bins(cfg_spec["version"], extras, with_pkgs)
    save_state(state)
    sys.exit(0)

if args == ["ls", "--global", "--json"]:
    tools = load_tools()
    state = load_state()
    is_installed = state.get("installed", {installed_tools!r})
    out = {{}}
    for name, spec in tools.items():
        ver = spec["version"]
        out[name] = [{{"version": ver, "requested_version": ver, "installed": is_installed, "active": is_installed}}]
    print(json.dumps(out))
    sys.exit(0)

if args == ["env", "--json"]:
    print(json.dumps(load_conf_d_env()))
    sys.exit(0)

if args == ["which", "docmancer"]:
    tools = load_tools()
    if "pipx:docmancer" not in tools:
        print("docmancer not installed", file=sys.stderr)
        sys.exit(1)
    spec = tools["pipx:docmancer"]
    ver = spec["version"]
    state = load_state()
    inst_info = state.get("installed_tools", {{}}).get("pipx:docmancer")
    extras = inst_info["extras"] if inst_info else spec["options"].get("extras", "")
    with_pkgs = inst_info.get("with", "") if inst_info else spec["options"].get("with", "")
    doc_bin = ensure_docmancer_bins(ver, extras, with_pkgs)
    print(str(doc_bin))
    sys.exit(0)

if len(args) >= 3 and args[0] == "exec" and args[1] == "--":
    cmd = args[2:]
    if cmd == ["docmancer", "--version"]:
        tools = load_tools()
        if "pipx:docmancer" not in tools:
            print("docmancer not installed", file=sys.stderr)
            sys.exit(1)
        print("docmancer 0.9.17")
        sys.exit(0)

sys.exit(0)
"""

    def test_mise_install_downloads_binary_syncs_bash_profile_and_global_tools(self) -> None:
        mise_log = self.tmp / "mise.log"
        fake_binary_bytes = self._fake_mise_script(mise_log).encode("utf-8")

        class _MiseReleaseHandler(http.server.BaseHTTPRequestHandler):
            def do_HEAD(self):
                if self.path == "/releases/latest":
                    self.send_response(302)
                    self.send_header("Location", "/releases/tag/v2026.11.14")
                    self.end_headers()
                    return
                if self.path == "/releases/tag/v2026.11.14":
                    self.send_response(200)
                    self.end_headers()
                    return
                self.send_response(404)
                self.end_headers()

            def do_GET(self):
                if self.path == "/releases/latest":
                    self.send_response(302)
                    self.send_header("Location", "/releases/tag/v2026.11.14")
                    self.end_headers()
                    return
                if self.path == "/releases/tag/v2026.11.14":
                    self.send_response(200)
                    self.end_headers()
                    return
                if self.path.startswith("/releases/download/v2026.11.14/mise-v2026.11.14-"):
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(fake_binary_bytes)))
                    self.end_headers()
                    self.wfile.write(fake_binary_bytes)
                    return
                self.send_response(404)
                self.end_headers()

            def log_message(self, format, *args):
                return

        server = http.server.HTTPServer(("127.0.0.1", 0), _MiseReleaseHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        extra_env = {
            "MISE_RELEASES_LATEST_URL": f"{base_url}/releases/latest",
            "MISE_RELEASES_DOWNLOAD_BASE": f"{base_url}/releases/download",
        }
        try:
            # Pre-install doctor fails because ~/bin/mise and ~/.bash_profile are missing.
            pre = self._run(BIN_DOCTOR, ["mise"], extra_env=extra_env)
            self.assertEqual(pre.returncode, 1)
            self.assertIn("missing ~/bin/mise", pre.stdout)
            self.assertIn("~/.bash_profile does not exist", pre.stdout)

            # Seed ~/.bash_profile with commented hook + direnv hook to verify placement.
            bash_profile = self.home / ".bash_profile"
            bash_profile.write_text(
                '# eval "$(mise activate bash)"\n'
                'eval "$(/opt/homebrew/bin/brew shellenv)"\n'
                'eval "$(direnv hook bash)"\n',
                encoding="utf-8",
            )
            bash_profile.chmod(0o600)

            inst = self._run(BIN_INSTALL, ["mise"], extra_env=extra_env)
            self.assertEqual(inst.returncode, 0, inst.stdout + inst.stderr)
            self.assertIn("[INSTALLED] ~/bin/mise", inst.stdout)
            self.assertIn("[ADDED] ~/.bash_profile", inst.stdout)
            self.assertIn("Configured and installed global mise tools", inst.stdout)

            mise_bin = self.home / "bin" / "mise"
            self.assertTrue(mise_bin.is_file())
            self.assertEqual(stat.S_IMODE(mise_bin.stat().st_mode), 0o755)

            profile_lines = bash_profile.read_text(encoding="utf-8").splitlines()
            self.assertEqual(stat.S_IMODE(bash_profile.stat().st_mode), 0o600)
            self.assertIn('eval "$(mise activate bash)"', profile_lines)
            self.assertLess(
                profile_lines.index('eval "$(mise activate bash)"'),
                profile_lines.index('eval "$(direnv hook bash)"'),
            )

            cfg_toml = self.home / ".config" / "mise" / "config.toml"
            cfg_text = cfg_toml.read_text(encoding="utf-8")
            self.assertIn('python = "3.15"', cfg_text)
            self.assertIn('uv = "0.13.10"', cfg_text)
            self.assertIn(
                '"pipx:docmancer" = { version = "0.9.17", extras = "embeddings-openai", with = "pysocks" }',
                cfg_text,
            )

            # Doctor passes now.
            doc_ok = self._run(BIN_DOCTOR, ["mise"], extra_env=extra_env)
            self.assertEqual(doc_ok.returncode, 0, doc_ok.stdout + doc_ok.stderr)

            # Re-running install is idempotent and skips re-downloading or re-running mise use.
            mise_log.unlink(missing_ok=True)
            reinst = self._run(BIN_INSTALL, ["mise"], extra_env=extra_env)
            self.assertEqual(reinst.returncode, 0, reinst.stdout + reinst.stderr)
            self.assertIn("already installed", reinst.stdout)
            self.assertIn("already includes", reinst.stdout)
            self.assertIn("already configured and installed", reinst.stdout)
            logged_cmds = mise_log.read_text(encoding="utf-8").splitlines()
            self.assertFalse(any(c.startswith("use --global") for c in logged_cmds))

            # Simulating an older install without the embeddings-openai extra triggers forced reinstall.
            cfg_toml.write_text(
                '[tools]\n"pipx:docmancer" = "0.9.17"\npython = "3.15"\nuv = "0.13.10"\n',
                encoding="utf-8",
            )
            state_path = self.home / ".fake_mise_installed.json"
            state_path.write_text(
                json.dumps(
                    {
                        "installed": True,
                        "installed_tools": {
                            "pipx:docmancer": {"version": "0.9.17", "extras": ""},
                            "python": {"version": "3.15", "extras": ""},
                            "uv": {"version": "0.13.10", "extras": ""},
                        },
                    }
                ),
                encoding="utf-8",
            )
            doc_old = self._run(BIN_DOCTOR, ["mise"], extra_env=extra_env)
            self.assertEqual(doc_old.returncode, 1)
            self.assertIn(
                "expected 'pipx:docmancer[extras=embeddings-openai,with=pysocks]@0.9.17'",
                doc_old.stdout,
            )

            mise_log.unlink(missing_ok=True)
            upgrade_inst = self._run(BIN_INSTALL, ["mise"], extra_env=extra_env)
            self.assertEqual(upgrade_inst.returncode, 0, upgrade_inst.stdout + upgrade_inst.stderr)
            upgrade_cmds = mise_log.read_text(encoding="utf-8").splitlines()
            self.assertTrue(any(c.startswith("use --global") for c in upgrade_cmds))
            self.assertTrue(
                any(c == "install --force pipx:docmancer@0.9.17" for c in upgrade_cmds),
                upgrade_cmds,
            )
            doc_after_upgrade = self._run(BIN_DOCTOR, ["mise"], extra_env=extra_env)
            self.assertEqual(doc_after_upgrade.returncode, 0, doc_after_upgrade.stdout + doc_after_upgrade.stderr)

            # Removing mise activate from ~/.bash_profile makes doctor fail.
            bash_profile.write_text('eval "$(direnv hook bash)"\n', encoding="utf-8")
            doc_missing_hook = self._run(BIN_DOCTOR, ["mise"], extra_env=extra_env)
            self.assertEqual(doc_missing_hook.returncode, 1)
            self.assertIn('missing `eval "$(mise activate bash)"`', doc_missing_hook.stdout)
        finally:
            server.shutdown()
            server.server_close()

    def test_docmancer_install_and_doctor(self) -> None:
        mise_log = self.tmp / "docmancer_mise.log"
        mise_bin = self.home / "bin" / "mise"
        mise_bin.parent.mkdir(parents=True, exist_ok=True)
        mise_bin.write_text(self._fake_mise_script(mise_log), encoding="utf-8")
        mise_bin.chmod(0o755)

        # Install docmancer files (--no-hooks first to test doctor before global tools exist).
        inst_no_hooks = self._run(BIN_INSTALL, ["--no-hooks", "docmancer"])
        self.assertEqual(inst_no_hooks.returncode, 0, inst_no_hooks.stdout + inst_no_hooks.stderr)
        self.assertIn("installed=3", inst_no_hooks.stdout)

        yaml_path = self.home / ".docmancer" / "docmancer.yaml"
        conf_d_path = self.home / ".config" / "mise" / "conf.d" / "docmancer.toml"
        skill_path = self.home / ".junie" / "skills" / "docmancer" / "SKILL.md"
        self.assertTrue(yaml_path.is_file())
        self.assertTrue(conf_d_path.is_file())
        self.assertTrue(skill_path.is_file())

        yaml_text = yaml_path.read_text(encoding="utf-8")
        self.assertIn('db_path: "./docmancer.db"', yaml_text)
        self.assertIn('provider: "openai"', yaml_text)
        self.assertIn('model: "embeddinggemma-2:740m"', yaml_text)

        conf_d_text = conf_d_path.read_text(encoding="utf-8")
        self.assertIn('OPENAI_BASE_URL = "http://localhost:11434/v1"', conf_d_text)
        self.assertIn('OPENAI_API_KEY = "ollama"', conf_d_text)

        skill_text = skill_path.read_text(encoding="utf-8")
        self.assertIn("mise exec -- docmancer", skill_text)
        self.assertIn("docmancer docs query", skill_text)
        self.assertIn("docmancer docs sync", skill_text)
        self.assertIn("--format json", skill_text)
        self.assertIn("--expand page", skill_text)
        self.assertNotIn(".estel-local", skill_text)
        self.assertNotIn("docmancer section", skill_text)
        self.assertNotIn("docmancer page", skill_text)
        self.assertNotIn("docs refresh", skill_text)
        self.assertNotIn("--source ", skill_text)
        self.assertNotIn("--name ", skill_text)

        # Doctor fails because pipx:docmancer is not yet configured in ~/.config/mise/config.toml.
        doc_before_tools = self._run(BIN_DOCTOR, ["docmancer"])
        self.assertEqual(doc_before_tools.returncode, 1)
        self.assertIn("mise exec -- docmancer --version failed", doc_before_tools.stdout)

        # Configure global tools without embeddings-openai extra or pysocks: doctor fails on both.
        cfg_toml = self.home / ".config" / "mise" / "config.toml"
        cfg_toml.write_text(
            '[tools]\n"pipx:docmancer" = "0.9.17"\npython = "3.15"\nuv = "0.13.10"\n',
            encoding="utf-8",
        )
        doc_missing_extra = self._run(BIN_DOCTOR, ["docmancer"])
        self.assertEqual(doc_missing_extra.returncode, 1)
        self.assertIn("missing the 'embeddings-openai' extra", doc_missing_extra.stdout)
        self.assertIn("missing the 'pysocks' dependency", doc_missing_extra.stdout)

        # Configure global tools with embeddings-openai extra only: doctor fails on missing pysocks.
        cfg_toml.write_text(
            '[tools]\n"pipx:docmancer" = { version = "0.9.17", extras = "embeddings-openai" }\npython = "3.15"\nuv = "0.13.10"\n',
            encoding="utf-8",
        )
        doc_missing_socks = self._run(BIN_DOCTOR, ["docmancer"])
        self.assertEqual(doc_missing_socks.returncode, 1)
        self.assertIn("[OK] docmancer embeddings-openai extra (openai) is installed", doc_missing_socks.stdout)
        self.assertIn("missing the 'pysocks' dependency", doc_missing_socks.stdout)

        # Configure global tools with embeddings-openai extra and pysocks: docmancer doctor passes.
        cfg_toml.write_text(
            '[tools]\n"pipx:docmancer" = { version = "0.9.17", extras = "embeddings-openai", with = "pysocks" }\npython = "3.15"\nuv = "0.13.10"\n',
            encoding="utf-8",
        )
        doc_ok = self._run(BIN_DOCTOR, ["docmancer"])
        self.assertEqual(doc_ok.returncode, 0, doc_ok.stdout + doc_ok.stderr)
        self.assertIn("OPENAI_BASE_URL=http://localhost:11434/v1", doc_ok.stdout)
        self.assertIn("[OK] mise exec -- docmancer (docmancer 0.9.17)", doc_ok.stdout)
        self.assertIn("[OK] docmancer embeddings-openai extra (openai) is installed", doc_ok.stdout)
        self.assertIn("[OK] docmancer pysocks dependency (socks) is installed", doc_ok.stdout)

        # If conf.d env vars are removed, docmancer doctor detects the missing env vars.
        conf_d_path.write_text("[env]\n", encoding="utf-8")
        doc_no_env = self._run(BIN_DOCTOR, ["docmancer"])
        self.assertEqual(doc_no_env.returncode, 1)
        self.assertIn("Mise environment missing OPENAI_BASE_URL, OPENAI_API_KEY", doc_no_env.stdout)

    def test_junie_install_and_doctor(self) -> None:
        agents_path = self.home / ".junie" / "AGENTS.md"
        rule_files = sorted(
            (REPO_ROOT / "junie" / "rules").glob("*.md"),
            key=lambda p: p.name,
        )
        rule_path = rule_files[0]
        expected_text = (
            "\n\n".join(
                p.read_text(encoding="utf-8").replace("\r\n", "\n").strip("\n")
                for p in rule_files
            )
            + "\n"
        )

        # Pre-install doctor fails because ~/.junie/AGENTS.md is missing.
        pre = self._run(BIN_DOCTOR, ["junie"])
        self.assertEqual(pre.returncode, 1)
        self.assertIn("missing: ~/.junie/AGENTS.md", pre.stdout)

        # Dry run must not create ~/.junie/AGENTS.md.
        dry = self._run(BIN_INSTALL, ["--dry-run", "junie"])
        self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
        self.assertFalse(agents_path.exists())
        self.assertIn("hook=dry-run", dry.stdout)

        # Install creates ~/.junie/AGENTS.md from junie/rules/*.md with mode 0644.
        inst = self._run(BIN_INSTALL, ["junie"])
        self.assertEqual(inst.returncode, 0, inst.stdout + inst.stderr)
        self.assertIn("[INSTALLED] ~/.junie/AGENTS.md", inst.stdout)
        self.assertTrue(agents_path.is_file())
        self.assertFalse(agents_path.is_symlink())
        self.assertEqual(stat.S_IMODE(agents_path.stat().st_mode), 0o644)
        self.assertEqual(agents_path.read_text(encoding="utf-8"), expected_text)

        # Doctor passes now.
        doc_ok = self._run(BIN_DOCTOR, ["junie"])
        self.assertEqual(doc_ok.returncode, 0, doc_ok.stdout + doc_ok.stderr)
        self.assertIn("[OK] ~/.junie/AGENTS.md", doc_ok.stdout)

        # Re-running install is idempotent.
        reinst = self._run(BIN_INSTALL, ["junie"])
        self.assertEqual(reinst.returncode, 0, reinst.stdout + reinst.stderr)
        self.assertIn(
            f"[OK] ~/.junie/AGENTS.md (unchanged, {len(rule_files)} rule(s))",
            reinst.stdout,
        )

        # Content drift triggers doctor failure and install repair.
        agents_path.write_text("# stale\n", encoding="utf-8")
        doc_drift = self._run(BIN_DOCTOR, ["junie"])
        self.assertEqual(doc_drift.returncode, 1)
        self.assertIn("sha256 mismatch: ~/.junie/AGENTS.md", doc_drift.stdout)

        fix_content = self._run(BIN_INSTALL, ["junie"])
        self.assertEqual(fix_content.returncode, 0, fix_content.stdout + fix_content.stderr)
        self.assertIn("[UPDATED] ~/.junie/AGENTS.md", fix_content.stdout)
        self.assertEqual(agents_path.read_text(encoding="utf-8"), expected_text)

        # Mode drift triggers doctor failure and install repair.
        agents_path.chmod(0o600)
        doc_mode = self._run(BIN_DOCTOR, ["junie"])
        self.assertEqual(doc_mode.returncode, 1)
        self.assertIn("mode mismatch: ~/.junie/AGENTS.md", doc_mode.stdout)

        fix_mode = self._run(BIN_INSTALL, ["junie"])
        self.assertEqual(fix_mode.returncode, 0, fix_mode.stdout + fix_mode.stderr)
        self.assertIn("mode 0600 -> 0644", fix_mode.stdout)
        self.assertEqual(stat.S_IMODE(agents_path.stat().st_mode), 0o644)

        # Symlink target is rejected by doctor and replaced with regular file by install.
        agents_path.unlink()
        agents_path.symlink_to(rule_path)
        doc_sym = self._run(BIN_DOCTOR, ["junie"])
        self.assertEqual(doc_sym.returncode, 1)
        self.assertIn("symlink (expected regular file): ~/.junie/AGENTS.md", doc_sym.stdout)

        fix_sym = self._run(BIN_INSTALL, ["junie"])
        self.assertEqual(fix_sym.returncode, 0, fix_sym.stdout + fix_sym.stderr)
        self.assertIn("symlink replaced", fix_sym.stdout)
        self.assertFalse(agents_path.is_symlink())
        self.assertEqual(agents_path.read_text(encoding="utf-8"), expected_text)

    def test_junie_multiple_rules_concatenation(self) -> None:
        repo = self.tmp / "junie_repo"
        shutil.copytree(
            REPO_ROOT / "bin",
            repo / "bin",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        shutil.copytree(
            REPO_ROOT / "junie",
            repo / "junie",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        bin_doctor = repo / "bin" / "doctor"
        bin_install = repo / "bin" / "install"
        rules_dir = repo / "junie" / "rules"
        base_rules = sorted(rules_dir.glob("*.md"), key=lambda p: p.name)
        total_rules = len(base_rules) + 2

        (rules_dir / "00-first.md").write_text("# First Rule\n\nAlpha.\n\n", encoding="utf-8")
        (rules_dir / "zz-last.md").write_text("# Last Rule\n\nOmega.", encoding="utf-8")
        (rules_dir / "ignored.txt").write_text("should not be included\n", encoding="utf-8")

        inst = self._run(bin_install, ["junie"])
        self.assertEqual(inst.returncode, 0, inst.stdout + inst.stderr)
        self.assertIn(f"from {total_rules} rule(s)", inst.stdout)

        agents_path = self.home / ".junie" / "AGENTS.md"
        content = agents_path.read_text(encoding="utf-8")
        base_text = "\n\n".join(
            p.read_text(encoding="utf-8").replace("\r\n", "\n").strip("\n")
            for p in base_rules
        )
        expected = f"# First Rule\n\nAlpha.\n\n{base_text}\n\n# Last Rule\n\nOmega.\n"
        self.assertEqual(content, expected)
        self.assertNotIn("should not be included", content)

        doc_ok = self._run(bin_doctor, ["junie"])
        self.assertEqual(doc_ok.returncode, 0, doc_ok.stdout + doc_ok.stderr)
        self.assertIn(f"{total_rules} rule(s)", doc_ok.stdout)

        # Updating a rule file causes doctor to fail until install re-syncs.
        (rules_dir / "zz-last.md").write_text("# Last Rule\n\nUpdated.\n", encoding="utf-8")
        doc_stale = self._run(bin_doctor, ["junie"])
        self.assertEqual(doc_stale.returncode, 1)
        self.assertIn("sha256 mismatch: ~/.junie/AGENTS.md", doc_stale.stdout)

        reinst = self._run(bin_install, ["junie"])
        self.assertEqual(reinst.returncode, 0, reinst.stdout + reinst.stderr)
        self.assertIn("Updated.\n", agents_path.read_text(encoding="utf-8"))

        # Empty rules directory fails cleanly.
        for md in rules_dir.glob("*.md"):
            md.unlink()
        doc_empty = self._run(bin_doctor, ["junie"])
        self.assertEqual(doc_empty.returncode, 1)
        self.assertIn("no *.md rule files found", doc_empty.stdout)
        inst_empty = self._run(bin_install, ["junie"])
        self.assertEqual(inst_empty.returncode, 1)
        self.assertIn("no *.md rule files found", inst_empty.stdout)

    def test_safehouse_multiple_policies_concatenation(self) -> None:
        repo = self.tmp / "safehouse_repo"
        shutil.copytree(
            REPO_ROOT / "bin",
            repo / "bin",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        shutil.copytree(
            REPO_ROOT / "safehouse",
            repo / "safehouse",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        bin_doctor = repo / "bin" / "doctor"
        bin_install = repo / "bin" / "install"
        policies_dir = repo / "safehouse" / "policies"
        base_policies = sorted(policies_dir.glob("*.sb"), key=lambda p: p.name)
        total_policies = len(base_policies) + 2

        for rel in (".homebrew/bin/safehouse", ".local/bin/junie"):
            p = self.home / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            p.chmod(0o755)

        (policies_dir / "00-first.sb").write_text(";; First Policy\n(deny lsopen)\n\n", encoding="utf-8")
        (policies_dir / "zz-last.sb").write_text(";; Last Policy\n(allow network-outbound)", encoding="utf-8")
        (policies_dir / "ignored.txt").write_text("should not be included\n", encoding="utf-8")

        inst = self._run(bin_install, ["safehouse"])
        self.assertEqual(inst.returncode, 0, inst.stdout + inst.stderr)
        self.assertIn(f"from {total_policies} policy file(s)", inst.stdout)

        profile_path = self.home / ".config" / "safehouse" / "junie-local.sb"
        content = profile_path.read_text(encoding="utf-8")
        self.assertNotIn("should not be included", content)
        self.assertLess(content.index(";; First Policy"), content.index('(subpath "/Applications")'))
        self.assertLess(content.index('(home-subpath "/.homebrew")'), content.index(";; Last Policy"))

        doc_ok = self._run(bin_doctor, ["safehouse"])
        self.assertEqual(doc_ok.returncode, 0, doc_ok.stdout + doc_ok.stderr)
        self.assertIn(f"{total_policies} policy file(s)", doc_ok.stdout)

        # Updating a policy file causes doctor to fail until install re-syncs.
        (policies_dir / "zz-last.sb").write_text(";; Last Policy\n;; Updated\n", encoding="utf-8")
        doc_stale = self._run(bin_doctor, ["safehouse"])
        self.assertEqual(doc_stale.returncode, 1)
        self.assertIn("sha256 mismatch: ~/.config/safehouse/junie-local.sb", doc_stale.stdout)

        reinst = self._run(bin_install, ["safehouse"])
        self.assertEqual(reinst.returncode, 0, reinst.stdout + reinst.stderr)
        self.assertIn(";; Updated\n", profile_path.read_text(encoding="utf-8"))

        # Empty policy file fails cleanly.
        (policies_dir / "zz-last.sb").write_text("\n   \n", encoding="utf-8")
        doc_blank = self._run(bin_doctor, ["safehouse"])
        self.assertEqual(doc_blank.returncode, 1)
        self.assertIn("policy file is empty: zz-last.sb", doc_blank.stdout)

        # Empty policies directory fails cleanly.
        for sb in policies_dir.glob("*.sb"):
            sb.unlink()
        doc_empty = self._run(bin_doctor, ["safehouse"])
        self.assertEqual(doc_empty.returncode, 1)
        self.assertIn("no *.sb policy files found", doc_empty.stdout)
        inst_empty = self._run(bin_install, ["safehouse"])
        self.assertEqual(inst_empty.returncode, 1)
        self.assertIn("no *.sb policy files found", inst_empty.stdout)


if __name__ == "__main__":
    unittest.main()
