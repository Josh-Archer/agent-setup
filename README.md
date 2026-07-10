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
- This was created from the latest `origin/main` commit in `C:\Code\agent-setup-main`.
- I scrubbed obvious hardcoded secrets I could identify in the copied files (for example inline test/example values).
- References to platform secret providers (e.g. `${{ secrets.* }}` / `${{ vars.* }}` / `${{ inputs.* }}` / runtime env lookups) are intentionally retained because they are not in plaintext.

## Update source
If you need a refreshed copy later, recreate it from the same source path (`C:\Code\agent-setup-main`) and re-run the same copy step.

## Agent Delegation

This repository includes a delegation capability allowing Codex to offload execution workloads to **Grok Build** and **Antigravity**.
- See the [Agent Architecture map](AGENTS.md) for canonical roles and model equivalences.
- See the [Grok & Antigravity Delegation Guide](docs/grok-agy-delegation.md) for setup, CLI invocation examples, JSON plan schemas, and safety boundaries.
