# shellcheck shell=bash
# Homelab MCP env bootstrap (safe for .zshrc / .bashrc).
# - Never prints secret values
# - Never embeds secrets in this file
# - Loads HOMELAB_MCP_API_KEY for Paperless mcpo (Codex/Grok/Gemini/agy)
#
# Sourced by: scripts/setup_agents.sh → appends:
#   source "$HOME/.config/homelab/homelab-mcp.env.sh"

_homelab_mcp_load_key() {
  # Prefer already-exported process env
  if [ -n "${HOMELAB_MCP_API_KEY:-}" ]; then
    return 0
  fi

  # Optional local cache (mode 600). Created by setup_agents / install-homelab-mcp.
  local cache="${HOMELAB_MCP_KEY_FILE:-$HOME/.config/homelab/mcp-api-key}"
  if [ -f "$cache" ] && [ -r "$cache" ]; then
    # shellcheck disable=SC2162
    HOMELAB_MCP_API_KEY="$(tr -d '\r\n' <"$cache" 2>/dev/null || true)"
    if [ -n "${HOMELAB_MCP_API_KEY:-}" ]; then
      export HOMELAB_MCP_API_KEY
      return 0
    fi
  fi

  # Best-effort: pull from cluster if kubectl works (silent on failure)
  if command -v kubectl >/dev/null 2>&1; then
    local b64
    b64="$(kubectl -n mcp get secret paperless-mcp-secret -o jsonpath='{.data.API_KEY}' 2>/dev/null || true)"
    if [ -n "$b64" ]; then
      if command -v base64 >/dev/null 2>&1; then
        HOMELAB_MCP_API_KEY="$(printf '%s' "$b64" | base64 --decode 2>/dev/null || printf '%s' "$b64" | base64 -d 2>/dev/null || true)"
      fi
      if [ -n "${HOMELAB_MCP_API_KEY:-}" ]; then
        export HOMELAB_MCP_API_KEY
        # Refresh local cache for offline shells
        mkdir -p "$(dirname "$cache")" 2>/dev/null || true
        if [ -d "$(dirname "$cache")" ]; then
          umask 077
          printf '%s' "$HOMELAB_MCP_API_KEY" >"$cache"
          chmod 600 "$cache" 2>/dev/null || true
        fi
        return 0
      fi
    fi
  fi

  return 0
}

_homelab_mcp_load_key
unset -f _homelab_mcp_load_key
