"""Integration tests for bin/doctor and bin/install."""

from __future__ import annotations

import http.server
import json
import os
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

    def test_list_and_unknown_system(self) -> None:
        res = self._run(BIN_DOCTOR, ["--list"])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.splitlines(), ["litellm-proxy", "safehouse"])

        bad = self._run(BIN_DOCTOR, ["does-not-exist"])
        self.assertEqual(bad.returncode, 2)
        self.assertIn("Unknown system(s): does-not-exist", bad.stderr)

    def test_litellm_install_doctor_and_drift_repair(self) -> None:
        self._install_fake_docker()

        # Before install, doctor fails on missing files.
        pre = self._run(BIN_DOCTOR, ["litellm-proxy"])
        self.assertEqual(pre.returncode, 1)
        self.assertIn("missing: ~/litellm-proxy/config.yaml", pre.stdout)

        # Dry run must not write files or invoke docker.
        self.docker_log.unlink(missing_ok=True)
        dry = self._run(BIN_INSTALL, ["--dry-run", "litellm-proxy"])
        self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
        self.assertFalse((self.home / "litellm-proxy").exists())
        self.assertFalse((self.home / ".bash_profile").exists())
        self.assertFalse(self.docker_log.exists())
        self.assertIn("hook=dry-run", dry.stdout)

        # Real install creates files, seeds .env (0600), syncs ~/.bash_profile, and runs compose workflow.
        inst = self._run(BIN_INSTALL, ["litellm-proxy"])
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

        reinst = self._run(BIN_INSTALL, ["--no-hooks", "litellm-proxy"])
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
                BIN_DOCTOR,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(doc_stale.returncode, 1)
            self.assertIn(
                "~/.bash_profile LITELLM_MASTER_KEY does not match ~/litellm-proxy/.env",
                doc_stale.stdout,
            )

            # Running bin/install updates ~/.bash_profile to match .env.
            sync_inst = self._run(BIN_INSTALL, ["litellm-proxy"])
            self.assertEqual(sync_inst.returncode, 0, sync_inst.stdout + sync_inst.stderr)
            self.assertIn("[UPDATED] ~/.bash_profile", sync_inst.stdout)
            self.assertEqual(
                bash_profile.read_text(encoding="utf-8"),
                "export LITELLM_MASTER_KEY=sk-real-master\n",
            )

            doc_ok = self._run(
                BIN_DOCTOR,
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
                BIN_DOCTOR,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(doc_bad.returncode, 1)
            self.assertIn("sha256 mismatch: ~/litellm-proxy/config.yaml", doc_bad.stdout)

            # Repair via bin/install --no-hooks and re-check.
            repair = self._run(BIN_INSTALL, ["--no-hooks", "litellm-proxy"])
            self.assertEqual(repair.returncode, 0)
            self.assertIn("updated=1", repair.stdout)

            doc_fixed = self._run(
                BIN_DOCTOR,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(doc_fixed.returncode, 0, doc_fixed.stdout + doc_fixed.stderr)

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
                BIN_DOCTOR,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(doc_unhealthy.returncode, 1)
            self.assertIn("service 'gemini-decision-adapter' is unhealthy", doc_unhealthy.stdout)
        finally:
            server.shutdown()
            server.server_close()

    def test_safehouse_install_and_doctor(self) -> None:
        inst = self._run(BIN_INSTALL, ["safehouse"])
        self.assertEqual(inst.returncode, 0, inst.stdout + inst.stderr)
        self.assertIn("installed=3", inst.stdout)

        wrapper = self.home / "bin" / "junie-safehouse"
        self.assertEqual(stat.S_IMODE(wrapper.stat().st_mode), 0o755)

        # Create prerequisite binaries under fake HOME.
        for rel in (".homebrew/bin/safehouse", ".local/bin/junie"):
            p = self.home / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            p.chmod(0o755)

        # Point ACP config in fake HOME or verify if real /Users/esmith/bin/junie-safehouse exists;
        # make mode wrong on wrapper and confirm doctor catches mode mismatch & install fixes it.
        wrapper.chmod(0o644)
        doc_mode = self._run(BIN_DOCTOR, ["safehouse"])
        self.assertEqual(doc_mode.returncode, 1)
        self.assertIn("mode mismatch: ~/bin/junie-safehouse", doc_mode.stdout)

        repair = self._run(BIN_INSTALL, ["safehouse"])
        self.assertEqual(repair.returncode, 0)
        self.assertEqual(stat.S_IMODE(wrapper.stat().st_mode), 0o755)

    def test_symlink_replacement_does_not_clobber_target(self) -> None:
        sentinel = self.tmp / "sentinel.txt"
        sentinel.write_text("do-not-overwrite\n", encoding="utf-8")
        target = self.home / ".config" / "safehouse" / "junie-local.sb"
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
            pre_sync = self._run(BIN_INSTALL, ["--no-hooks", "litellm-proxy"])
            self.assertEqual(pre_sync.returncode, 0, pre_sync.stdout + pre_sync.stderr)

            doc_missing = self._run(
                BIN_DOCTOR,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(doc_missing.returncode, 1)
            self.assertIn(
                "~/.bash_profile is missing export LITELLM_MASTER_KEY",
                doc_missing.stdout,
            )

            # Install appends export on a new line, preserving existing content and mode.
            inst_add = self._run(BIN_INSTALL, ["litellm-proxy"])
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
            inst_ok = self._run(BIN_INSTALL, ["litellm-proxy"])
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
                BIN_DOCTOR,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(doc_quoted.returncode, 0, doc_quoted.stdout + doc_quoted.stderr)
            inst_quoted = self._run(BIN_INSTALL, ["litellm-proxy"])
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
                BIN_DOCTOR,
                ["litellm-proxy"],
                extra_env={"LITELLM_HEALTH_URL": health_url},
            )
            self.assertEqual(doc_dup.returncode, 1)

            inst_dedup = self._run(BIN_INSTALL, ["litellm-proxy"])
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


if __name__ == "__main__":
    unittest.main()
