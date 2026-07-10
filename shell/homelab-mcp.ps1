# Homelab MCP env bootstrap for Windows PowerShell profiles.
# - Never prints secret values
# - Loads HOMELAB_MCP_API_KEY (mcpo Bearer) and PAPERLESS_API_KEY (Paperless-NGX token for stdio MCP)
#
# Installed by scripts/setup_agents.ps1 into the user profile as:
#   . "$HOME\.config\homelab\homelab-mcp.ps1"

function Import-HomelabEnvVar {
  param(
    [Parameter(Mandatory)][string]$Name,
    [string]$CacheFile,
    [string]$KubectlJsonPath
  )
  $cur = [Environment]::GetEnvironmentVariable($Name, 'Process')
  if (-not [string]::IsNullOrWhiteSpace($cur)) { return }

  $userKey = [Environment]::GetEnvironmentVariable($Name, 'User')
  if (-not [string]::IsNullOrWhiteSpace($userKey)) {
    Set-Item -Path "Env:$Name" -Value $userKey
    return
  }

  if ($CacheFile -and (Test-Path -LiteralPath $CacheFile)) {
    try {
      $key = (Get-Content -LiteralPath $CacheFile -Raw -ErrorAction Stop).Trim()
      if ($key.Length -ge 8) {
        Set-Item -Path "Env:$Name" -Value $key
        return
      }
    } catch {}
  }

  if ($KubectlJsonPath -and (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    try {
      $b64 = kubectl -n mcp get secret paperless-mcp-secret -o jsonpath=$KubectlJsonPath 2>$null
      if (-not [string]::IsNullOrWhiteSpace([string]$b64)) {
        $key = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String([string]$b64))
        if ($key.Length -ge 8) {
          Set-Item -Path "Env:$Name" -Value $key
          [Environment]::SetEnvironmentVariable($Name, $key, 'User')
          if ($CacheFile) {
            $dir = Split-Path -Parent $CacheFile
            if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
            if (Test-Path -LiteralPath $CacheFile) {
              try { icacls $CacheFile /grant:r "${env:USERNAME}:(F)" 2>$null | Out-Null } catch {}
            }
            Set-Content -LiteralPath $CacheFile -Value $key -Encoding ascii -NoNewline
            try {
              icacls $CacheFile /inheritance:r 2>$null | Out-Null
              icacls $CacheFile /grant:r "${env:USERNAME}:(R,W)" 2>$null | Out-Null
            } catch {}
          }
        }
      }
    } catch {}
  }
}

$configDir = Join-Path $env:USERPROFILE '.config\homelab'
Import-HomelabEnvVar -Name 'HOMELAB_MCP_API_KEY' `
  -CacheFile (Join-Path $configDir 'mcp-api-key') `
  -KubectlJsonPath '{.data.API_KEY}'
Import-HomelabEnvVar -Name 'PAPERLESS_API_KEY' `
  -CacheFile (Join-Path $configDir 'paperless-api-key') `
  -KubectlJsonPath '{.data.PAPERLESS_API_TOKEN}'
if ([string]::IsNullOrWhiteSpace($env:PAPERLESS_URL)) {
  $pu = [Environment]::GetEnvironmentVariable('PAPERLESS_URL', 'User')
  if ([string]::IsNullOrWhiteSpace($pu)) { $pu = 'https://paperless.archer.casa' }
  $env:PAPERLESS_URL = $pu
}
