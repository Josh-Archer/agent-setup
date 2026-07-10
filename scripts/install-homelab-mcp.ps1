#Requires -Version 5.1
<#
.SYNOPSIS
  Install Paperless + Immich MCP servers into global Codex, Grok, and Antigravity/Gemini configs.

.DESCRIPTION
  - Never writes secret values into config files or this repo.
  - Expects HOMELAB_MCP_API_KEY in the environment (User or Process).
  - Optionally loads the key from the cluster secret paperless-mcp-secret (API_KEY) into User env.

.PARAMETER LoadKeyFromCluster
  If set, read mcp/paperless-mcp-secret API_KEY via kubectl and store as User env HOMELAB_MCP_API_KEY.

.PARAMETER SkipCodex
.PARAMETER SkipGrok
.PARAMETER SkipGemini
  Skip installing for a specific client.
#>
[CmdletBinding()]
param(
  [switch]$LoadKeyFromCluster,
  [switch]$SkipCodex,
  [switch]$SkipGrok,
  [switch]$SkipGemini
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$FragDir = Join-Path $RepoRoot 'mcp\fragments'

function Test-EnvKey {
  $k = [Environment]::GetEnvironmentVariable('HOMELAB_MCP_API_KEY', 'Process')
  if ([string]::IsNullOrWhiteSpace($k)) {
    $k = [Environment]::GetEnvironmentVariable('HOMELAB_MCP_API_KEY', 'User')
  }
  if ([string]::IsNullOrWhiteSpace($k)) {
    return $false
  }
  $env:HOMELAB_MCP_API_KEY = $k
  return $true
}

function Import-KeyFromCluster {
  Write-Host 'Loading HOMELAB_MCP_API_KEY from cluster secret mcp/paperless-mcp-secret ...'
  $b64 = kubectl -n mcp get secret paperless-mcp-secret -o jsonpath='{.data.API_KEY}'
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($b64)) {
    throw 'Failed to read paperless-mcp-secret.API_KEY (is kubectl context set and secret present?)'
  }
  $key = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String([string]$b64))
  if ($key.Length -lt 8) { throw 'API_KEY from cluster looks empty/short' }
  [Environment]::SetEnvironmentVariable('HOMELAB_MCP_API_KEY', $key, 'User')
  $env:HOMELAB_MCP_API_KEY = $key
  Write-Host "Set User env HOMELAB_MCP_API_KEY (length=$($key.Length)). Restart agent apps to pick it up."
}

function Merge-TomlFragment {
  param(
    [string]$TargetPath,
    [string]$FragmentPath,
    [string[]]$ServerNames
  )
  $frag = Get-Content -Raw -Path $FragmentPath
  $existing = if (Test-Path $TargetPath) { Get-Content -Raw -Path $TargetPath } else { '' }
  # Strip prior blocks for these servers so re-runs are idempotent
  foreach ($name in $ServerNames) {
    $pattern = "(?ms)^\[mcp_servers\.$([regex]::Escape($name))\](?:\r?\n(?!\[).*)*"
    $existing = [regex]::Replace($existing, $pattern, '')
    $patternEnv = "(?ms)^\[mcp_servers\.$([regex]::Escape($name))\.[^\]]+\](?:\r?\n(?!\[).*)*"
    $existing = [regex]::Replace($existing, $patternEnv, '')
  }
  $existing = $existing.TrimEnd() + "`n`n" + $frag.Trim() + "`n"
  $dir = Split-Path -Parent $TargetPath
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
  # backup
  if (Test-Path $TargetPath) {
    Copy-Item $TargetPath "$TargetPath.bak-homelab-mcp-$(Get-Date -Format yyyyMMddHHmmss)" -Force
  }
  [System.IO.File]::WriteAllText($TargetPath, $existing)
  Write-Host "Updated $TargetPath"
}

function Merge-JsonMcpServers {
  param(
    [string]$TargetPath,
    [string]$FragmentPath,
    [string]$RootKey  # empty = fragment is root mcpServers object; or 'mcpServers'
  )
  $fragObj = Get-Content -Raw $FragmentPath | ConvertFrom-Json
  $servers = if ($fragObj.mcpServers) { $fragObj.mcpServers } else { $fragObj }

  $target = [ordered]@{}
  if (Test-Path $TargetPath) {
    $raw = Get-Content -Raw $TargetPath
    if (-not [string]::IsNullOrWhiteSpace($raw)) {
      $target = $raw | ConvertFrom-Json
    }
  } else {
    $dir = Split-Path -Parent $TargetPath
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
  }

  if ($RootKey -eq 'mcpServers' -or $null -ne $target.mcpServers -or $TargetPath -match 'mcp_config') {
    if (-not $target.mcpServers) {
      $target | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) -Force
    }
    $hash = @{}
    if ($target.mcpServers) {
      $target.mcpServers.PSObject.Properties | ForEach-Object { $hash[$_.Name] = $_.Value }
    }
    $servers.PSObject.Properties | ForEach-Object { $hash[$_.Name] = $_.Value }
    $target.mcpServers = [pscustomobject]$hash
  } else {
    # Gemini settings.json top-level mcpServers
    if (-not $target.mcpServers) {
      $target | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) -Force
    }
    $hash = @{}
    if ($target.mcpServers) {
      $target.mcpServers.PSObject.Properties | ForEach-Object { $hash[$_.Name] = $_.Value }
    }
    $servers.PSObject.Properties | ForEach-Object { $hash[$_.Name] = $_.Value }
    $target.mcpServers = [pscustomobject]$hash
  }

  if (Test-Path $TargetPath) {
    Copy-Item $TargetPath "$TargetPath.bak-homelab-mcp-$(Get-Date -Format yyyyMMddHHmmss)" -Force
  }
  $json = $target | ConvertTo-Json -Depth 20
  [System.IO.File]::WriteAllText($TargetPath, $json)
  Write-Host "Updated $TargetPath"
}

if ($LoadKeyFromCluster) {
  Import-KeyFromCluster
}

if (-not (Test-EnvKey)) {
  Write-Warning @'
HOMELAB_MCP_API_KEY is not set. Paperless MCP will fail auth until you set it.
Re-run with -LoadKeyFromCluster or set the User env var from Vaultwarden/cluster.
'@
} else {
  Write-Host "HOMELAB_MCP_API_KEY is present (length=$($env:HOMELAB_MCP_API_KEY.Length))."
}

$names = @('paperless', 'immich')

if (-not $SkipCodex) {
  # Prefer CLI when available (writes bearer_token_env_var cleanly)
  if (Get-Command codex -ErrorAction SilentlyContinue) {
    Write-Host 'Installing Codex MCP servers via CLI...'
    try { & codex mcp remove paperless 2>&1 | Out-Null } catch {}
    try { & codex mcp remove immich 2>&1 | Out-Null } catch {}
    & codex mcp add paperless --url 'http://paperless-mcp.archer.casa' --bearer-token-env-var HOMELAB_MCP_API_KEY
    if ($LASTEXITCODE -ne 0) { throw "codex mcp add paperless failed ($LASTEXITCODE)" }
    & codex mcp add immich --url 'http://immich-mcp.archer.casa/mcp'
    if ($LASTEXITCODE -ne 0) { throw "codex mcp add immich failed ($LASTEXITCODE)" }
    Write-Host 'Codex MCP servers registered.'
  } else {
    Merge-TomlFragment -TargetPath (Join-Path $env:USERPROFILE '.codex\config.toml') `
      -FragmentPath (Join-Path $FragDir 'codex.homelab-mcp.toml') -ServerNames $names
  }
}

if (-not $SkipGrok) {
  if (Get-Command grok -ErrorAction SilentlyContinue) {
    Write-Host 'Installing Grok MCP servers via CLI...'
    try { & grok mcp remove paperless 2>&1 | Out-Null } catch {}
    try { & grok mcp remove immich 2>&1 | Out-Null } catch {}
    & grok mcp add --transport http paperless 'http://paperless-mcp.archer.casa' --header 'Authorization: Bearer ${HOMELAB_MCP_API_KEY}'
    if ($LASTEXITCODE -ne 0) { throw "grok mcp add paperless failed ($LASTEXITCODE)" }
    & grok mcp add --transport http immich 'http://immich-mcp.archer.casa/mcp'
    if ($LASTEXITCODE -ne 0) { throw "grok mcp add immich failed ($LASTEXITCODE)" }
    Write-Host 'Grok MCP servers registered.'
  } else {
    Merge-TomlFragment -TargetPath (Join-Path $env:USERPROFILE '.grok\config.toml') `
      -FragmentPath (Join-Path $FragDir 'grok.homelab-mcp.toml') -ServerNames $names
  }
}

if (-not $SkipGemini) {
  Merge-JsonMcpServers -TargetPath (Join-Path $env:USERPROFILE '.gemini\settings.json') `
    -FragmentPath (Join-Path $FragDir 'gemini.mcpServers.json') -RootKey 'mcpServers'
  Merge-JsonMcpServers -TargetPath (Join-Path $env:USERPROFILE '.gemini\antigravity\mcp_config.json') `
    -FragmentPath (Join-Path $FragDir 'antigravity.mcp_config.json') -RootKey 'mcpServers'
  # Enable in mcp-server-enablement if file exists
  $enablePath = Join-Path $env:USERPROFILE '.gemini\mcp-server-enablement.json'
  if (Test-Path $enablePath) {
    try {
      $en = Get-Content -Raw $enablePath | ConvertFrom-Json
      $en | Add-Member -NotePropertyName paperless -NotePropertyValue @{ enabled = $true } -Force
      $en | Add-Member -NotePropertyName immich -NotePropertyValue @{ enabled = $true } -Force
      # ConvertTo-Json may flatten oddly; rewrite carefully
      $hash = @{}
      $en.PSObject.Properties | ForEach-Object {
        if ($_.Name -in @('paperless', 'immich')) {
          $hash[$_.Name] = @{ enabled = $true }
        } else {
          $hash[$_.Name] = $_.Value
        }
      }
      $hash['paperless'] = @{ enabled = $true }
      $hash['immich'] = @{ enabled = $true }
      Copy-Item $enablePath "$enablePath.bak-homelab-mcp-$(Get-Date -Format yyyyMMddHHmmss)" -Force
      ($hash | ConvertTo-Json -Depth 10) | Set-Content -Path $enablePath -Encoding utf8
      Write-Host "Updated $enablePath"
    } catch {
      Write-Warning "Could not update mcp-server-enablement.json: $_"
    }
  }
}

Write-Host ''
Write-Host 'Done. Restart Codex / Grok / Antigravity (agy) so they reload MCP config and User env.'
Write-Host 'Smoke (from LAN/Tailscale):'
Write-Host '  curl -sS -o NUL -w "%{http_code}" -H "Authorization: Bearer $env:HOMELAB_MCP_API_KEY" http://paperless-mcp.archer.casa/docs'
Write-Host '  curl -sS http://immich-mcp.archer.casa/health'
