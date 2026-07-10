# Agent Setup Showcase

This repository is a sanitized snapshot of my agent-related configuration folders, copied from `origin/main`:

- `.codex`
- `.gemini`
- `.github`
- `.claude`

## Delegation

The repository includes a Codex skill for delegating work to Grok Build and
Antigravity (`agy`), including dependency-aware multi-agent plans. See
[`docs/grok-agy-delegation.md`](docs/grok-agy-delegation.md).

## Notes
- This was created as a sanitized snapshot of agent-related configuration folders from a larger home repository.
- Obvious hardcoded secrets were scrubbed where identified (for example inline test/example values).
- References to platform secret providers (e.g. `${{ secrets.* }}` / `${{ vars.* }}` / `${{ inputs.* }}` / runtime env lookups) are intentionally retained because they are not in plaintext.
- Multi-agent run artifacts land under `.agent-runs/` (gitignored).

## Local validation for agent surfaces
```bash
python3 scripts/sync_agent_surfaces.py --check
python3 -m unittest discover -s scripts/tests -v
```

## Install delegation globally

Run this once to make the delegation skill available to Codex sessions across
projects. It symlinks the skill into `~/.codex/skills/` and adds an idempotent
startup marker to `~/.zshrc`:

```bash
python3 scripts/setup_global_delegation.py
```

Restart the shell or open a new ChatGPT/Codex session afterward.

## Agent Delegation

This repository includes a delegation capability allowing Codex to offload execution workloads to **Grok Build** and **Antigravity**.
- See the [Agent Architecture map](AGENTS.md) for canonical roles and model equivalences.
- See the [Grok & Antigravity Delegation Guide](docs/grok-agy-delegation.md) for setup, CLI invocation examples, JSON plan schemas, and safety boundaries.
