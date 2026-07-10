#!/usr/bin/env bash
# Bootstrap agent definitions, skills, shell env, and Homelab MCP clients.
# Safe for public repos: no secret values written into git-tracked files.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/homelab"
SHELL_SNIPPET_SRC="$REPO_ROOT/shell/homelab-mcp.env.sh"
SHELL_SNIPPET_DST="$CONFIG_DIR/homelab-mcp.env.sh"
KEY_CACHE="$CONFIG_DIR/mcp-api-key"

log() { printf '[setup_agents] %s\n' "$*"; }

ensure_link_or_copy() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [ -L "$dst" ] || [ -e "$dst" ]; then
    if [ -L "$dst" ] && [ "$(readlink "$dst" 2>/dev/null || true)" = "$src" ]; then
      log "ok link $dst"
      return 0
    fi
    # Prefer replace symlink; back up foreign trees once
    if [ ! -L "$dst" ]; then
      local bak="${dst}.bak-setup-agents-$(date +%Y%m%d%H%M%S)"
      log "backing up $dst -> $bak"
      mv "$dst" "$bak"
    else
      rm -f "$dst"
    fi
  fi
  ln -s "$src" "$dst"
  log "linked $dst -> $src"
}

install_agent_trees() {
  # Project-style trees live in this repo; mirror into user global homes when useful.
  if [ -d "$REPO_ROOT/.codex/agents" ]; then
    mkdir -p "$HOME/.codex"
    # Copy agent defs (not full config.toml — user keeps local settings)
    rsync -a --delete "$REPO_ROOT/.codex/agents/" "$HOME/.codex/agents/" 2>/dev/null \
      || { mkdir -p "$HOME/.codex/agents"; cp -R "$REPO_ROOT/.codex/agents/." "$HOME/.codex/agents/"; }
    log "synced Codex agents -> ~/.codex/agents"
  fi
  if [ -d "$REPO_ROOT/.claude/agents" ]; then
    mkdir -p "$HOME/.claude"
    rsync -a --delete "$REPO_ROOT/.claude/agents/" "$HOME/.claude/agents/" 2>/dev/null \
      || { mkdir -p "$HOME/.claude/agents"; cp -R "$REPO_ROOT/.claude/agents/." "$HOME/.claude/agents/"; }
    log "synced Claude agents -> ~/.claude/agents"
  fi
  if [ -d "$REPO_ROOT/.gemini/agents" ]; then
    mkdir -p "$HOME/.gemini"
    rsync -a --delete "$REPO_ROOT/.gemini/agents/" "$HOME/.gemini/agents/" 2>/dev/null \
      || { mkdir -p "$HOME/.gemini/agents"; cp -R "$REPO_ROOT/.gemini/agents/." "$HOME/.gemini/agents/"; }
    log "synced Gemini agents -> ~/.gemini/agents"
  fi
  if [ -d "$REPO_ROOT/.gemini/skills" ]; then
    rsync -a --delete "$REPO_ROOT/.gemini/skills/" "$HOME/.gemini/skills/" 2>/dev/null \
      || { mkdir -p "$HOME/.gemini/skills"; cp -R "$REPO_ROOT/.gemini/skills/." "$HOME/.gemini/skills/"; }
    log "synced Gemini skills -> ~/.gemini/skills"
  fi
}

install_shell_snippet() {
  mkdir -p "$CONFIG_DIR"
  cp "$SHELL_SNIPPET_SRC" "$SHELL_SNIPPET_DST"
  chmod 644 "$SHELL_SNIPPET_DST"
  log "installed shell snippet $SHELL_SNIPPET_DST"

  local marker='# >>> homelab-mcp (agent-setup-showcase) >>>'
  local end_marker='# <<< homelab-mcp (agent-setup-showcase) <<<'
  local block
  block=$(cat <<EOF
$marker
# Homelab MCP env (Paperless/Immich). No secrets in this line.
[ -f "$SHELL_SNIPPET_DST" ] && . "$SHELL_SNIPPET_DST"
$end_marker
EOF
)

  for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
    touch "$rc"
    if grep -qF "$marker" "$rc" 2>/dev/null; then
      # Replace existing block
      local tmp
      tmp="$(mktemp)"
      awk -v m="$marker" -v e="$end_marker" '
        $0 == m {skip=1; next}
        $0 == e {skip=0; next}
        !skip {print}
      ' "$rc" >"$tmp"
      printf '%s\n' "$block" >>"$tmp"
      mv "$tmp" "$rc"
      log "refreshed MCP hook in $rc"
    else
      printf '\n%s\n' "$block" >>"$rc"
      log "appended MCP hook to $rc"
    fi
  done
}

refresh_key_cache() {
  if [ -n "${HOMELAB_MCP_API_KEY:-}" ]; then
    umask 077
    printf '%s' "$HOMELAB_MCP_API_KEY" >"$KEY_CACHE"
    chmod 600 "$KEY_CACHE"
    log "refreshed key cache from existing env (not printed)"
    return 0
  fi
  if command -v kubectl >/dev/null 2>&1; then
    local b64 key
    b64="$(kubectl -n mcp get secret paperless-mcp-secret -o jsonpath='{.data.API_KEY}' 2>/dev/null || true)"
    if [ -n "$b64" ]; then
      key="$(printf '%s' "$b64" | base64 --decode 2>/dev/null || printf '%s' "$b64" | base64 -d 2>/dev/null || true)"
      if [ -n "$key" ]; then
        umask 077
        printf '%s' "$key" >"$KEY_CACHE"
        chmod 600 "$KEY_CACHE"
        export HOMELAB_MCP_API_KEY="$key"
        log "loaded key from cluster into cache (not printed)"
        return 0
      fi
    fi
  fi
  log "warning: HOMELAB_MCP_API_KEY not available (Paperless MCP auth may fail until set)"
}

install_mcp_clients() {
  # Prefer PowerShell installer when available for Codex/Grok CLIs; else pure shell fragment merge.
  if command -v powershell.exe >/dev/null 2>&1 || command -v pwsh >/dev/null 2>&1; then
    local ps
    ps="$(command -v pwsh 2>/dev/null || command -v powershell.exe 2>/dev/null)"
    # On pure Linux, use bash-side MCP install via grok/codex if present
    :
  fi

  # Source env so CLIs see the key
  # shellcheck disable=SC1090
  [ -f "$SHELL_SNIPPET_DST" ] && . "$SHELL_SNIPPET_DST"

  if command -v codex >/dev/null 2>&1; then
    codex mcp remove paperless >/dev/null 2>&1 || true
    codex mcp remove immich >/dev/null 2>&1 || true
    codex mcp add paperless --url 'http://paperless-mcp.archer.casa' --bearer-token-env-var HOMELAB_MCP_API_KEY
    codex mcp add immich --url 'http://immich-mcp.archer.casa/mcp'
    log "Codex MCP: paperless + immich"
  else
    log "codex CLI not found; skip Codex MCP CLI registration"
  fi

  if command -v grok >/dev/null 2>&1; then
    grok mcp remove paperless >/dev/null 2>&1 || true
    grok mcp remove immich >/dev/null 2>&1 || true
    grok mcp add --transport http paperless 'http://paperless-mcp.archer.casa' \
      --header 'Authorization: Bearer ${HOMELAB_MCP_API_KEY}'
    grok mcp add --transport http immich 'http://immich-mcp.archer.casa/mcp'
    log "Grok MCP: paperless + immich"
  else
    log "grok CLI not found; writing fragment to ~/.grok/config.toml if missing"
    mkdir -p "$HOME/.grok"
    if [ -f "$REPO_ROOT/mcp/fragments/grok.homelab-mcp.toml" ]; then
      # Append once
      if ! grep -q '\[mcp_servers.paperless\]' "$HOME/.grok/config.toml" 2>/dev/null; then
        printf '\n' >>"$HOME/.grok/config.toml"
        cat "$REPO_ROOT/mcp/fragments/grok.homelab-mcp.toml" >>"$HOME/.grok/config.toml"
      fi
    fi
  fi

  # Gemini / Antigravity JSON fragments via python for portability
  REPO_ROOT="$REPO_ROOT" python3 - <<'PY' || true
import json, os, pathlib
home = pathlib.Path.home()
repo = pathlib.Path(os.environ["REPO_ROOT"])
frag = json.loads((repo / "mcp/fragments/gemini.mcpServers.json").read_text(encoding="utf-8"))
settings_path = home / ".gemini" / "settings.json"
settings_path.parent.mkdir(parents=True, exist_ok=True)
settings = {}
if settings_path.exists():
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8") or "{}")
    except Exception:
        settings = {}
servers = settings.get("mcpServers") or {}
if not isinstance(servers, dict):
    servers = {}
servers.update(frag)
settings["mcpServers"] = servers
settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
for sub_path in ["antigravity/mcp_config.json", "antigravity-cli/mcp_config.json"]:
    agy = home / ".gemini" / sub_path
    agy.parent.mkdir(parents=True, exist_ok=True)
    agy_doc = {"mcpServers": dict(frag)}
    if agy.exists():
        try:
            existing = json.loads(agy.read_text(encoding="utf-8") or "{}")
            base = existing.get("mcpServers") if isinstance(existing.get("mcpServers"), dict) else {}
            base.update(frag)
            existing["mcpServers"] = base
            agy_doc = existing
        except Exception:
            pass
    agy.write_text(json.dumps(agy_doc, indent=2) + "\n", encoding="utf-8")
print("[setup_agents] synced Gemini/Antigravity mcpServers")
PY
}

main() {
  export REPO_ROOT
  log "repo=$REPO_ROOT"
  install_agent_trees
  install_shell_snippet
  refresh_key_cache
  install_mcp_clients
  log "done. Open a new shell (or: source ~/.zshrc) and restart Codex/Grok/Antigravity."
}

main "$@"
