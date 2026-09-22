#!/usr/bin/env python3
"""Contract tests: unslop skill and OMP harness are fully integrated."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class UnslopSkillContractTests(unittest.TestCase):
    def test_unslop_skill_exists_in_all_harness_trees(self) -> None:
        skill_paths = [
            ROOT / ".codex" / "skills" / "unslop" / "SKILL.md",
            ROOT / ".claude" / "skills" / "unslop" / "SKILL.md",
            ROOT / ".gemini" / "skills" / "unslop" / "SKILL.md",
            ROOT / ".omp" / "skills" / "unslop" / "SKILL.md",
        ]
        for path in skill_paths:
            self.assertTrue(path.is_file(), f"Missing skill definition: {path}")
            content = path.read_text(encoding="utf-8")
            self.assertIn("name: unslop", content)
            self.assertIn("Core Anti-Slop Principles", content)
            self.assertIn("Slop Taxonomy", content)

    def test_instruction_files_reference_unslop(self) -> None:
        instruction_files = [
            ROOT / "AGENTS.md",
            ROOT / "CLAUDE.md",
            ROOT / "COPILOT.md",
            ROOT / ".github" / "copilot-instructions.md",
        ]
        for path in instruction_files:
            self.assertTrue(path.is_file(), f"Missing instruction file: {path}")
            content = path.read_text(encoding="utf-8")
            self.assertIn("unslop", content.lower(), f"{path} must reference unslop")


class OmpHarnessContractTests(unittest.TestCase):
    def test_omp_agents_generated_for_all_codex_roles(self) -> None:
        codex_roles = {
            p.name.removesuffix(".agent.md")
            for p in (ROOT / ".codex" / "agents").glob("*.agent.md")
        }
        omp_agents = {
            p.name.removesuffix(".md")
            for p in (ROOT / ".omp" / "agents").glob("*.md")
        }
        self.assertEqual(codex_roles, omp_agents)

    def test_omp_agents_have_valid_frontmatter_tools_and_astra_default(self) -> None:
        for path in (ROOT / ".omp" / "agents").glob("*.md"):
            content = path.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---\n"), f"{path} must have YAML frontmatter")
            self.assertIn("tools:", content)
            self.assertIn("model:", content)
            # Check that model list contains multiple providers for fallback
            lines = content.splitlines()
            model_indices = [i for i, line in enumerate(lines) if line.strip() == "model:"]
            self.assertTrue(model_indices, f"{path} missing model: block")
            m_idx = model_indices[0]
            model_entries = []
            for line in lines[m_idx + 1:]:
                if line.startswith("  - "):
                    model_entries.append(line.strip().strip('- "'))
                else:
                    break
            self.assertEqual(len(model_entries), 1, "Provider alternatives require explicit selection")
            self.assertRegex(model_entries[0], r"^openai-codex/gpt-6-astra:(low|medium|high)$")

    def test_security_auditor_omp_tools_exclude_shell(self) -> None:
        path = ROOT / ".omp" / "agents" / "security-auditor.md"
        content = path.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("---\n"), f"{path} must have YAML frontmatter")
        lines = content.splitlines()
        tools_indices = [i for i, line in enumerate(lines) if line.strip() == "tools:"]
        self.assertTrue(tools_indices, f"{path} missing tools: block")
        tools: list[str] = []
        for line in lines[tools_indices[0] + 1 :]:
            if line.startswith("  - "):
                tools.append(line.strip()[2:].strip())
            else:
                break
        self.assertIn("read", tools)
        self.assertIn("grep", tools)
        self.assertIn("glob", tools)
        self.assertIn("lsp", tools)
        self.assertNotIn("bash", tools)
        self.assertNotIn("edit", tools)
        self.assertNotIn("write", tools)


class SecurityAuditorToolPolicyTests(unittest.TestCase):
    def test_codex_security_auditor_is_read_search_only(self) -> None:
        content = (ROOT / ".codex" / "agents" / "security-auditor.agent.md").read_text(
            encoding="utf-8"
        )
        self.assertRegex(content, r"(?m)^tools: \[read, search\]$")

    def test_agy_security_auditor_has_no_shell(self) -> None:
        content = (
            ROOT / ".agents" / "plugins" / "home-codex-agents" / "agents" / "security-auditor.md"
        ).read_text(encoding="utf-8")
        self.assertRegex(content, r"(?m)^tools: \[read_file, grep_search, glob, list_directory\]$")
        self.assertNotIn("run_shell_command", content.split("---", 2)[1])

    def test_grok_security_auditor_is_read_only(self) -> None:
        content = (ROOT / ".grok" / "roles" / "security-auditor.toml").read_text(encoding="utf-8")
        self.assertIn('default_capability_mode = "read-only"', content)

    def test_claude_security_auditor_has_no_shell(self) -> None:
        content = (ROOT / ".claude" / "agents" / "security-auditor.md").read_text(encoding="utf-8")
        self.assertRegex(content, r"(?m)^tools: \[Read, Grep, Glob\]$")

    def test_github_security_auditor_is_read_search_only(self) -> None:
        content = (ROOT / ".github" / "agents" / "security-auditor.agent.md").read_text(
            encoding="utf-8"
        )
        self.assertRegex(content, r"(?m)^tools: \[read, search\]$")

    def test_gemini_security_auditor_has_no_shell(self) -> None:
        content = (ROOT / ".gemini" / "agents" / "security-auditor.md").read_text(encoding="utf-8")
        self.assertRegex(content, r"(?m)^tools: \[read_file, grep_search\]$")


if __name__ == "__main__":
    unittest.main()
