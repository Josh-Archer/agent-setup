#!/usr/bin/env python3
"""Install this repository's delegation surfaces for local agent harnesses."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


SKILL_NAME = "grok-agy-delegate"
MARKER = "# >>> agent-setup-showcase delegation >>>"
END_MARKER = "# <<< agent-setup-showcase delegation <<<"


def shell_block(repo_root: Path) -> str:
    return f'''{MARKER}
# Keep the global Codex delegation skill tied to this checkout.
export CODEX_DELEGATION_REPO={repo_root}
# Link any new repository skills when a new zsh starts.
python3 "$CODEX_DELEGATION_REPO/scripts/setup_global_delegation.py" --sync-skills --quiet 2>/dev/null || true
{END_MARKER}'''


def install_skill(repo_root: Path, codex_home: Path) -> Path:
    source = repo_root / ".codex" / "skills" / SKILL_NAME
    if not source.is_dir():
        raise SystemExit(f"Delegation skill not found: {source}")

    destination = codex_home / "skills" / SKILL_NAME
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.is_symlink() or destination.exists():
        if destination.is_symlink() and destination.resolve() == source.resolve():
            return destination
        raise SystemExit(
            f"Refusing to replace existing global skill: {destination}. "
            "Move it aside and rerun."
        )
    destination.symlink_to(source, target_is_directory=True)
    return destination


def install_link(source: Path, destination: Path, label: str) -> Path:
    if not source.exists():
        raise SystemExit(f"{label} source not found: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink() or destination.exists():
        if destination.is_symlink() and destination.resolve() == source.resolve():
            return destination
        raise SystemExit(
            f"Refusing to replace existing global {label}: {destination}. "
            "Move it aside and rerun."
        )
    destination.symlink_to(source, target_is_directory=source.is_dir())
    return destination


def sync_skills(repo_root: Path, codex_home: Path) -> list[Path]:
    source_root = repo_root / ".codex" / "skills"
    destination_root = codex_home / "skills"
    destination_root.mkdir(parents=True, exist_ok=True)
    installed: list[Path] = []
    for source in sorted(source_root.iterdir()):
        if source.is_dir() and not source.name.startswith("."):
            installed.append(install_link(source, destination_root / source.name, "Codex skill"))
    return installed


def install_harness_surfaces(repo_root: Path, home: Path) -> list[Path]:
    """Expose generated role/plugin surfaces to Grok CLI and Antigravity."""
    links = [
        (repo_root / ".grok" / "agents", home / ".grok" / "agents", "Grok agents"),
        (repo_root / ".grok" / "roles", home / ".grok" / "roles", "Grok roles"),
        (
            repo_root / ".agents" / "plugins" / "home-codex-agents",
            home / ".agents" / "plugins" / "home-codex-agents",
            "Antigravity plugin",
        ),
    ]
    return [install_link(source, destination, label) for source, destination, label in links]


def install_shell_hook(shell_file: Path, repo_root: Path) -> None:
    existing = shell_file.read_text() if shell_file.exists() else ""
    block = shell_block(repo_root)
    if MARKER in existing:
        start = existing.index(MARKER)
        end = existing.find(END_MARKER, start)
        if end < 0:
            raise SystemExit(f"Found incomplete delegation block in {shell_file}")
        end += len(END_MARKER)
        existing = existing[:start] + block + existing[end:]
    else:
        separator = "\n" if existing and not existing.endswith("\n") else ""
        existing += separator + "\n" + block + "\n"
    shell_file.parent.mkdir(parents=True, exist_ok=True)
    shell_file.write_text(existing)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser())
    parser.add_argument("--shell-file", type=Path, default=Path("~/.zshrc").expanduser())
    parser.add_argument("--sync-skills", action="store_true", help="Link all repository skills and exit")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    if args.sync_skills:
        sync_skills(repo_root, args.codex_home.expanduser())
        return 0
    destination = install_skill(repo_root, args.codex_home.expanduser())
    harness_links = install_harness_surfaces(repo_root, Path.home())
    install_shell_hook(args.shell_file.expanduser(), repo_root)
    print(f"Installed global Codex skill: {destination} -> {repo_root / '.codex/skills' / SKILL_NAME}")
    for link in harness_links:
        print(f"Installed global harness surface: {link} -> {link.resolve()}")
    print(f"Updated shell startup: {args.shell_file.expanduser()}")
    print("Restart the shell or open a new Codex/ChatGPT session to load it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
