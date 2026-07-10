# Homelab MCP env bootstrap for Windows PowerShell profiles.
# - Never prints secret values
# - Loads HOMELAB_MCP_API_KEY for Paperless mcpo (Codex/Grok/Gemini/agy)
#
# Installed by scripts/setup_agents.ps1 into the user profile as:
#   . "$HOME\.config\homelab\homelab-mcp.ps1"

function Import-HomelabMcpApiKey {
  if (-not [string]::IsNullOrWhiteSpace($env:HOMELAB_MCP_API_KEY)) {
    return
  }

  $userKey = [Environment]::GetEnvironmentVariable('HOMELAB_MCP_API_KEY', 'User')
  if (-not [string]::IsNullOrWhiteSpace($userKey)) {
    $env:HOMELAB_MCP_API_KEY = $userKey
    return
  }

  $cache = if ($env:HOMELAB_MCP_KEY_FILE) { $env:HOMELAB_MCP_KEY_FILE } else {
    Join-Path $env:USERPROFILE '.config\homelab\mcp-api-key'
  }
  if (Test-Path -LiteralPath $cache) {
    try {
      $key = (Get-Content -LiteralPath $cache -Raw -ErrorAction Stop).Trim()
      if ($key.Length -ge 8) {
        $env:HOMELAB_MCP_API_KEY = $key
        return
      }
    } catch {
      # ignore
    }
  }

  if (Get-Command kubectl -ErrorAction SilentlyContinue) {
    try {
      $b64 = kubectl -n mcp get secret paperless-mcp-secret -o jsonpath='{.data.API_KEY}' 2>$null
      if (-not [string]::IsNullOrWhiteSpace([string]$b64)) {
        $key = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String([string]$b64))
        if ($key.Length -ge 8) {
          $env:HOMELAB_MCP_API_KEY = $key
          [Environment]::SetEnvironmentVariable('HOMELAB_MCP_API_KEY', $key, 'User')
          $dir = Split-Path -Parent $cache
          if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
          if (Test-Path -LiteralPath $cache) {
            try { icacls $cache /grant:r "${env:USERNAME}:(F)" 2>$null | Out-Null } catch {}
          }
          Set-Content -LiteralPath $cache -Value $key -Encoding ascii -NoNewline
          # Restrict ACL when possible (best-effort; keep RW for refresh)
          try {
            icacls $cache /inheritance:r 2>$null | Out-Null
            icacls $cache /grant:r "${env:USERNAME}:(R,W)" 2>$null | Out-Null
          } catch {}
        }
      }
    } catch {
      # kubectl unavailable / secret missing — leave unset
    }
  }
}

Import-HomelabMcpApiKey
