# Agent Setup Showcase

This repository is a sanitized snapshot of my agent-related configuration folders, copied from `origin/main`:

- `.codex`
- `.gemini`
- `.github`
- `.claude`

## Notes
- This was created from the latest `origin/main` commit in `C:\Code\agent-setup-main`.
- I scrubbed obvious hardcoded secrets I could identify in the copied files (for example inline test/example values).
- References to platform secret providers (e.g. `${{ secrets.* }}` / `${{ vars.* }}` / `${{ inputs.* }}` / runtime env lookups) are intentionally retained because they are not in plaintext.

## Homelab MCP (Paperless + Immich)

Global MCP client fragments for **Codex**, **Grok**, and **Antigravity (agy) / Gemini** live under [`mcp/`](mcp/README.md).

- **No secrets in git** — only URLs + `${HOMELAB_MCP_API_KEY}` / `bearer_token_env_var`.
- Install on a workstation: `pwsh -File scripts/install-homelab-mcp.ps1 -LoadKeyFromCluster`

## Update source
If you need a refreshed copy later, recreate it from the same source path (`C:\Code\agent-setup-main`) and re-run the same copy step.
