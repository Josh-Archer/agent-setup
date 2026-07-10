# shellcheck shell=bash
# Homelab MCP env bootstrap (safe for .zshrc / .bashrc).
# - Never prints secret values
# - Never embeds secrets in this file
# - Loads HOMELAB_MCP_API_KEY (mcpo Bearer) and PAPERLESS_API_KEY (stdio MCP token)
#
# Sourced by: scripts/setup_agents.sh → appends:
#   source "$HOME/.config/homelab/homelab-mcp.env.sh"

_homelab_mcp_load_one() {
  # $1 = env var name, $2 = cache path, $3 = kubectl jsonpath for secret data key
  local name="$1"
  local cache="$2"
  local jsonpath="$3"
  local cur
  cur="$(eval "echo \"\${$name:-}\"")"

  if [ -n "$cur" ]; then
    return 0
  fi

  if [ -f "$cache" ] && [ -r "$cache" ]; then
    cur="$(tr -d '\r\n' <"$cache" 2>/dev/null || true)"
    if [ -n "$cur" ]; then
      eval "export $name=\"\$cur\""
      return 0
    fi
  fi

  if command -v kubectl >/dev/null 2>&1; then
    local b64
    b64="$(kubectl -n mcp get secret paperless-mcp-secret -o jsonpath="$jsonpath" 2>/dev/null || true)"
    if [ -n "$b64" ]; then
      if command -v base64 >/dev/null 2>&1; then
        cur="$(printf '%s' "$b64" | base64 --decode 2>/dev/null || printf '%s' "$b64" | base64 -d 2>/dev/null || true)"
      fi
      if [ -n "$cur" ]; then
        eval "export $name=\"\$cur\""
        mkdir -p "$(dirname "$cache")" 2>/dev/null || true
        if [ -d "$(dirname "$cache")" ]; then
          umask 077
          printf '%s' "$cur" >"$cache"
          chmod 600 "$cache" 2>/dev/null || true
        fi
        return 0
      fi
    fi
  fi

  return 0
}

_homelab_mcp_load_one HOMELAB_MCP_API_KEY \
  "${HOMELAB_MCP_KEY_FILE:-$HOME/.config/homelab/mcp-api-key}" \
  '{.data.API_KEY}'

_homelab_mcp_load_one PAPERLESS_API_KEY \
  "${PAPERLESS_API_KEY_FILE:-$HOME/.config/homelab/paperless-api-key}" \
  '{.data.PAPERLESS_API_TOKEN}'

if [ -z "${PAPERLESS_URL:-}" ]; then
  export PAPERLESS_URL="${PAPERLESS_URL:-https://paperless.archer.casa}"
fi

unset -f _homelab_mcp_load_one
