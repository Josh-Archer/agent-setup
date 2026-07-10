#!/usr/bin/env python3
"""Generate Grok and Antigravity agent definitions from the repo's Codex agents."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / ".codex" / "agents"
GROK_DIR = ROOT / ".grok" / "roles"
GROK_AGENT_DIR = ROOT / ".grok" / "agents"
AGY_PLUGIN_DIR = ROOT / ".agents" / "plugins" / "home-codex-agents"
AGY_AGENT_DIR = AGY_PLUGIN_DIR / "agents"


def frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", text, re.DOTALL)
    if not match:
        return {}, text
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values, match.group(2).lstrip()


def value(meta: dict[str, str], key: str, default: str = "") -> str:
    return meta.get(key, default)


def grok_model(codex_model: str) -> str:
    if "5.3-codex-spark" in codex_model or "mini" in codex_model:
        return "grok-composer-2.5-fast"
    return "grok-4.5"


def agy_model(codex_model: str) -> str:
    if "5.3-codex-spark" in codex_model:
        return "Gemini 3.5 Flash (Low)"
    if "mini" in codex_model:
        return "Gemini 3.5 Flash (Medium)"
    return "Claude Opus 4.6 (Thinking)"


def capability(tools: str) -> str:
    if "edit" in tools or "execute" in tools or "agent" in tools:
        return "all"
    return "read-only"


def agy_tools(tools: str) -> str:
    mapped: list[str] = ["read_file", "grep_search", "glob", "list_directory"]
    if "edit" in tools:
        mapped += ["write_file", "replace"]
    if "execute" in tools:
        mapped += ["run_shell_command"]
    if "todo" in tools:
        mapped += ["todo"]
    if "agent" in tools:
        mapped += ["invoke_subagent"]
    return "[" + ", ".join(mapped) + "]"


def main() -> None:
    GROK_DIR.mkdir(parents=True, exist_ok=True)
    GROK_AGENT_DIR.mkdir(parents=True, exist_ok=True)
    AGY_AGENT_DIR.mkdir(parents=True, exist_ok=True)
    (AGY_PLUGIN_DIR / "rules").mkdir(parents=True, exist_ok=True)

    agents = sorted(SOURCE_DIR.glob("*.agent.md"))
    if not agents:
        raise SystemExit(f"No Codex agents found in {SOURCE_DIR}")

    for source in agents:
        meta, body = frontmatter(source.read_text())
        name = source.name.removesuffix(".agent.md")
        description = value(meta, "description", name).replace('"', '\\"')
        model = value(meta, "model", "gpt-5.5")
        reasoning = value(meta, "reasoning_effort", "medium")
        tools = value(meta, "tools", "")

        grok = (
            f'description = "{description}"\n'
            f'default_capability_mode = "{capability(tools)}"\n'
            f'model = "{grok_model(model)}"\n'
            f'reasoning_effort = "{("high" if reasoning == "extra high" else reasoning)}"\n'
            f'prompt_file = ".codex/agents/{source.name}"\n'
        )
        (GROK_DIR / f"{name}.toml").write_text(grok)

        grok_agent = (
            "---\n"
            f"name: {name}\n"
            f"description: {description}\n"
            f"model: {grok_model(model)}\n"
            "prompt_mode: full\n"
            "permission_mode: default\n"
            "agents_md: true\n"
            "---\n"
            + body
        )
        (GROK_AGENT_DIR / f"{name}.md").write_text(grok_agent)

        agy = (
            "---\n"
            f"name: {name}\n"
            f"description: {description}\n"
            f"model: {agy_model(model)}\n"
            f"tools: {agy_tools(tools)}\n"
            "---\n"
            + body
        )
        (AGY_AGENT_DIR / f"{name}.md").write_text(agy)

    (AGY_PLUGIN_DIR / "plugin.json").write_text(
        '{\n'
        '  "$schema": "https://antigravity.google/schemas/v1/plugin.json",\n'
        '  "name": "home-codex-agents",\n'
        '  "description": "Repository-specific agent roles synchronized from Codex."\n'
        '}\n'
    )
    (AGY_PLUGIN_DIR / "rules" / "model-equivalence.md").write_text(
        "# Home agent model equivalence\n\n"
        "These mappings preserve role intent across local agent surfaces:\n\n"
        "- High/extra-high Codex roles: Grok `grok-4.5`; Antigravity `Claude Opus 4.6 (Thinking)`.\n"
        "- Medium Codex roles: Grok `grok-composer-2.5-fast`; Antigravity `Gemini 3.5 Flash (Medium)`.\n"
        "- Spark/low-risk Codex roles: Grok `grok-composer-2.5-fast`; Antigravity `Gemini 3.5 Flash (Low)`.\n"
    )

    print(f"Generated {len(agents)} Grok roles in {GROK_DIR}")
    print(f"Generated {len(agents)} Grok agents in {GROK_AGENT_DIR}")
    print(f"Generated {len(agents)} Antigravity agents in {AGY_PLUGIN_DIR}")


if __name__ == "__main__":
    main()
