#!/usr/bin/env python3
"""Tests for agent tree bootstrap idempotency and machine-only file preservation (Issue #28)."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
SETUP_AGENTS_SH = SCRIPTS / "setup_agents.sh"
SETUP_AGENTS_PS1 = SCRIPTS / "setup_agents.ps1"


class SetupAgentsSourceContractTests(unittest.TestCase):
    def test_setup_agents_sh_does_not_contain_rsync_delete(self) -> None:
        text = SETUP_AGENTS_SH.read_text(encoding="utf-8")
        self.assertNotIn(
            "rsync -a --delete",
            text,
            "install_agent_trees must not use --delete when syncing agent/skill trees",
        )
        self.assertNotIn(
            "--delete",
            text,
            "setup_agents.sh must not purge machine-only files",
        )
        self.assertIn("rsync -a", text)

    def test_setup_agents_ps1_does_not_use_robocopy_mir(self) -> None:
        text = SETUP_AGENTS_PS1.read_text(encoding="utf-8")
        self.assertNotIn(
            "/MIR",
            text,
            "setup_agents.ps1 Sync-Tree must not use /MIR (which purges destination-only files)",
        )
        self.assertIn("/E", text, "setup_agents.ps1 Sync-Tree should use /E to copy subtrees")

    def test_setup_agents_sh_does_not_expand_inherited_repo_root(self) -> None:
        text = SETUP_AGENTS_SH.read_text(encoding="utf-8")
        self.assertNotIn(
            'REPO_ROOT="${REPO_ROOT:-',
            text,
            "setup_agents.sh must not allow REPO_ROOT to be overridden from environment",
        )



class SetupAgentsBootstrapExecutionTests(unittest.TestCase):
    def test_install_agent_trees_preserves_machine_only_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_home_str:
            tmp_home = Path(tmp_home_str)

            # Pre-populate machine-only skills in destination harness directories
            destinations = [
                tmp_home / ".codex" / "skills" / "machine-only-codex-skill",
                tmp_home / ".claude" / "skills" / "machine-only-claude-skill",
                tmp_home / ".gemini" / "skills" / "machine-only-gemini-skill",
                tmp_home / ".omp" / "agent" / "skills" / "machine-only-omp-skill",
            ]
            for skill_dir in destinations:
                skill_dir.mkdir(parents=True, exist_ok=True)
                (skill_dir / "SKILL.md").write_text(
                    f"Machine-only skill content in {skill_dir.name}\n", encoding="utf-8"
                )

            # Run install_agent_trees against the isolated temp home
            cmd = [
                "bash",
                "-c",
                f'. "{SETUP_AGENTS_SH}" && install_agent_trees',
            ]
            env = dict(os.environ, HOME=str(tmp_home))
            result = subprocess.run(
                cmd,
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"install_agent_trees failed: stdout={result.stdout}\nstderr={result.stderr}",
            )

            # Verify that all machine-only skills still exist and are untouched
            for skill_dir in destinations:
                skill_file = skill_dir / "SKILL.md"
                self.assertTrue(
                    skill_file.is_file(),
                    f"Expected machine-only skill to survive bootstrap: {skill_file}",
                )
                self.assertEqual(
                    skill_file.read_text(encoding="utf-8"),
                    f"Machine-only skill content in {skill_dir.name}\n",
                )

            # Verify repo skills were also copied
            self.assertTrue(
                (tmp_home / ".codex" / "skills" / "unslop" / "SKILL.md").is_file(),
                "Repo skill 'unslop' should be installed to ~/.codex/skills",
            )
            self.assertTrue(
                (tmp_home / ".claude" / "skills" / "unslop" / "SKILL.md").is_file(),
                "Repo skill 'unslop' should be installed to ~/.claude/skills",
            )

    def test_install_agent_trees_preserves_machine_only_agents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_home_str:
            tmp_home = Path(tmp_home_str)

            # Pre-populate machine-only agents in destination harness directories
            custom_agents = [
                (tmp_home / ".codex" / "agents" / "local-custom-agent.toml", "name = 'local'\n"),
                (tmp_home / ".claude" / "agents" / "local-custom-agent.md", "# Local Claude\n"),
                (tmp_home / ".gemini" / "agents" / "local-custom-agent.md", "# Local Gemini\n"),
                (tmp_home / ".omp" / "agent" / "agents" / "local-custom-agent.md", "# Local OMP\n"),
            ]
            for file_path, content in custom_agents:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")

            cmd = [
                "bash",
                str(SETUP_AGENTS_SH),
                "--trees-only",
            ]
            env = dict(os.environ, HOME=str(tmp_home))
            result = subprocess.run(
                cmd,
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"setup_agents.sh --trees-only failed: stdout={result.stdout}\nstderr={result.stderr}",
            )

            # Verify that all machine-only agents still exist
            for file_path, content in custom_agents:
                self.assertTrue(
                    file_path.is_file(),
                    f"Expected machine-only agent to survive bootstrap: {file_path}",
                )
                self.assertEqual(file_path.read_text(encoding="utf-8"), content)

            # Verify repo agents were also copied
            self.assertTrue(
                (tmp_home / ".codex" / "agents" / "lead.agent.md").is_file(),
                "Repo agent 'lead.agent.md' should be installed to ~/.codex/agents",
            )

    def test_install_agent_trees_fallback_when_rsync_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            tmp_home = tmp_path / "home"
            tmp_home.mkdir()
            mock_bin = tmp_path / "bin"
            mock_bin.mkdir()

            # Create a mock rsync that exits non-zero to force cp -R fallback
            mock_rsync = mock_bin / "rsync"
            mock_rsync.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            mock_rsync.chmod(mock_rsync.stat().st_mode | stat.S_IEXEC)

            # Pre-populate machine-only skill
            custom_skill = tmp_home / ".codex" / "skills" / "machine-only-fallback-skill"
            custom_skill.mkdir(parents=True, exist_ok=True)
            (custom_skill / "SKILL.md").write_text("Fallback preserve\n", encoding="utf-8")

            cmd = [
                "bash",
                str(SETUP_AGENTS_SH),
                "install_agent_trees",
            ]
            new_path = f"{mock_bin}:{os.environ.get('PATH', '')}"
            env = dict(os.environ, HOME=str(tmp_home), PATH=new_path)
            result = subprocess.run(
                cmd,
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"Fallback install_agent_trees failed: stdout={result.stdout}\nstderr={result.stderr}",
            )

            # Destination-only file should still exist
            self.assertTrue(
                (custom_skill / "SKILL.md").is_file(),
                "Fallback copy path must not remove machine-only skills",
            )
            # Repo skills should still be copied via fallback cp -R
            self.assertTrue(
                (tmp_home / ".codex" / "skills" / "unslop" / "SKILL.md").is_file(),
                "Repo skill 'unslop' should be copied via fallback path",
            )

    def test_setup_agents_sh_derives_repo_root_and_ignores_inherited_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_home_str:
            tmp_home = Path(tmp_home_str)
            env = dict(
                os.environ,
                HOME=str(tmp_home),
                REPO_ROOT="/tmp/untrusted-spoofed-repo-root",
            )

            # Sourced in bash
            cmd_sourced = [
                "bash",
                "-c",
                f'. "{SETUP_AGENTS_SH}" && printf "%s" "$REPO_ROOT"',
            ]
            result_sourced = subprocess.run(
                cmd_sourced,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(result_sourced.returncode, 0)
            self.assertEqual(result_sourced.stdout, str(ROOT))

            # Executed directly (check log output repo=...)
            cmd_exec = [
                "bash",
                str(SETUP_AGENTS_SH),
                "--trees-only",
            ]
            result_exec = subprocess.run(
                cmd_exec,
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result_exec.returncode, 0)
            self.assertIn(f"[setup_agents] repo={ROOT}", result_exec.stdout)
            self.assertNotIn("/tmp/untrusted-spoofed-repo-root", result_exec.stdout)


if __name__ == "__main__":
    unittest.main()

