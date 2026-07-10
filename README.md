# Agent Setup Showcase

Sanitized snapshot of agent-related configuration folders (from `origin/main` of the homelab workspace):

- `.codex` — Codex agents
- `.gemini` — Gemini / Antigravity agents + skills
- `.github` — GitHub agent definitions + workflows
- `.claude` — Claude Code agents
- `mcp/` — Homelab MCP client fragments (Paperless + Immich)
- `shell/` — Shell profile snippets (zsh/bash + PowerShell)
- `scripts/` — Bootstrap + validate

## Notes

- Obvious hardcoded secrets were scrubbed from the snapshot.
- Platform secret references (`${{ secrets.* }}`, env lookups, `${HOMELAB_MCP_API_KEY}`) are intentional and not plaintext credentials.

## One-command bootstrap (agents + skills + MCP)

Same idea as installing agent/skill definitions: run once per machine.

### Windows

```powershell
cd path\to\agent-setup-showcase
powershell -ExecutionPolicy Bypass -File .\scripts\setup_agents.ps1 -LoadKeyFromCluster
powershell -ExecutionPolicy Bypass -File .\scripts\validate-homelab-mcp.ps1
```

This:

1. Syncs agent/skill trees into `~/.codex`, `~/.claude`, `~/.gemini`
2. Installs PowerShell profile hooks that load `HOMELAB_MCP_API_KEY` (from User env, cache file, or kubectl)
3. Registers Paperless + Immich MCP for **Codex**, **Grok**, and **Antigravity (agy) / Gemini**

### Linux / macOS / WSL

```bash
cd path/to/agent-setup-showcase
chmod +x scripts/setup_agents.sh
./scripts/setup_agents.sh
# new shell or:
source ~/.zshrc   # or ~/.bashrc
```

Hooks are idempotent blocks in `~/.zshrc` and `~/.bashrc` marked:

```text
# >>> homelab-mcp (agent-setup-showcase) >>>
...
# <<< homelab-mcp (agent-setup-showcase) <<<
```

## Homelab MCP (no secrets in git)

| Server | URL | Auth |
|--------|-----|------|
| Paperless | `http://paperless-mcp.archer.casa` | `HOMELAB_MCP_API_KEY` → Bearer |
| Immich | `http://immich-mcp.archer.casa/mcp` | LAN/Tailscale allowlist only |

Fragments live under `mcp/fragments/`. See [mcp/README.md](mcp/README.md).

**Never commit** `~/.config/homelab/mcp-api-key` or real token values.

## Update source

Refresh agent snapshots from `C:\Code\agent-setup-main` (or the homelab `home` repo agent trees) and re-run setup.
