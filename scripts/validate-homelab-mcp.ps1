#Requires -Version 5.1
<#
.SYNOPSIS
  Validate Homelab MCP connectivity without printing secrets.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Continue'
$failed = 0

function Ok($m) { Write-Host "OK  $m" -ForegroundColor Green }
function Bad($m) { Write-Host "FAIL $m" -ForegroundColor Red; $script:failed++ }

# Load env from profile snippet if needed
$snip = Join-Path $env:USERPROFILE '.config\homelab\homelab-mcp.ps1'
if (Test-Path $snip) { . $snip }

if ([string]::IsNullOrWhiteSpace($env:HOMELAB_MCP_API_KEY)) {
  Bad 'HOMELAB_MCP_API_KEY is not set in this process'
} else {
  Ok "HOMELAB_MCP_API_KEY present (len=$($env:HOMELAB_MCP_API_KEY.Length))"
}

# Config presence
foreach ($pair in @(
  @('codex paperless', (Select-String -Path "$env:USERPROFILE\.codex\config.toml" -Pattern 'mcp_servers\.paperless' -Quiet)),
  @('codex immich', (Select-String -Path "$env:USERPROFILE\.codex\config.toml" -Pattern 'mcp_servers\.immich' -Quiet)),
  @('grok paperless', (Select-String -Path "$env:USERPROFILE\.grok\config.toml" -Pattern 'mcp_servers\.paperless' -Quiet)),
  @('grok immich', (Select-String -Path "$env:USERPROFILE\.grok\config.toml" -Pattern 'mcp_servers\.immich' -Quiet))
)) {
  if ($pair[1]) { Ok $pair[0] } else { Bad $pair[0] }
}

try {
  $gs = Get-Content "$env:USERPROFILE\.gemini\settings.json" -Raw | ConvertFrom-Json
  if ($gs.mcpServers.paperless -and $gs.mcpServers.immich) { Ok 'gemini mcpServers' } else { Bad 'gemini mcpServers' }
} catch { Bad "gemini settings: $_" }

try {
  $agy = Get-Content "$env:USERPROFILE\.gemini\antigravity\mcp_config.json" -Raw | ConvertFrom-Json
  if ($agy.mcpServers.paperless -and $agy.mcpServers.immich) { Ok 'antigravity mcp_config' } else { Bad 'antigravity mcp_config' }
} catch { Bad "antigravity: $_" }

# In-cluster health (works even if DNS for archer.casa fails on this host)
if (Get-Command kubectl -ErrorAction SilentlyContinue) {
  $imm = kubectl -n mcp exec deploy/immich-mcp -- curl -sS http://127.0.0.1:5000/health 2>$null
  if ("$imm" -match 'healthy') { Ok 'immich-mcp /health in-cluster' } else { Bad "immich-mcp health: $imm" }

  if (-not [string]::IsNullOrWhiteSpace($env:HOMELAB_MCP_API_KEY)) {
    $code = kubectl -n mcp run "curl-pl-val-$([guid]::NewGuid().ToString('N').Substring(0,8))" --rm -i --restart=Never --image=curlimages/curl:8.5.0 --quiet -- `
      curl -sS -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $($env:HOMELAB_MCP_API_KEY)" `
      http://paperless-mcp.mcp.svc.cluster.local:8080/docs 2>$null
    # kubectl noise may wrap output
    if ("$code" -match '200') { Ok 'paperless-mcp /docs Bearer auth 200' } else { Bad "paperless-mcp auth code=$code" }
  }
} else {
  Bad 'kubectl not available for in-cluster smoke'
}

# CLI lists
if (Get-Command codex -ErrorAction SilentlyContinue) {
  $list = codex mcp list 2>&1 | Out-String
  if ($list -match 'paperless' -and $list -match 'immich') { Ok 'codex mcp list has paperless+immich' } else { Bad 'codex mcp list missing entries' }
}
if (Get-Command grok -ErrorAction SilentlyContinue) {
  $list = grok mcp list 2>&1 | Out-String
  if ($list -match 'paperless' -and $list -match 'immich') { Ok 'grok mcp list has paperless+immich' } else { Bad 'grok mcp list missing entries' }
}

# Secret leakage quick audit of local configs
$leakPatterns = @(
  'Bearer [A-Za-z0-9_\-]{20,}',
  'API_KEY\s*=\s*["''][A-Za-z0-9]{16,}',
  'Authorization"\s*:\s*"Bearer [A-Za-z0-9]'
)
$scanFiles = @(
  "$env:USERPROFILE\.codex\config.toml",
  "$env:USERPROFILE\.grok\config.toml",
  "$env:USERPROFILE\.gemini\settings.json",
  "$env:USERPROFILE\.gemini\antigravity\mcp_config.json"
)
foreach ($f in $scanFiles) {
  if (-not (Test-Path $f)) { continue }
  $raw = Get-Content -Raw $f
  $hit = $false
  foreach ($p in $leakPatterns) {
    if ($raw -match $p -and $raw -notmatch '\$\{HOMELAB_MCP_API_KEY\}' -and $raw -notmatch 'bearer_token_env_var') {
      # Allow env var forms only
      if ($raw -match 'Bearer \$\{' -or $raw -match 'bearer_token_env_var') { continue }
      # If literal long bearer present without ${
      if ($raw -match 'Bearer [A-Za-z0-9_\-]{20,}' -and $raw -notmatch 'Bearer \$\{') {
        Bad "possible secret in $f"
        $hit = $true
        break
      }
    }
  }
  if (-not $hit) { Ok "no literal secrets in $f" }
}

if ($failed -gt 0) {
  Write-Host "`n$failed check(s) failed" -ForegroundColor Red
  exit 1
}
Write-Host "`nAll validation checks passed" -ForegroundColor Green
exit 0
