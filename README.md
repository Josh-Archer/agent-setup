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

## Update source
If you need a refreshed copy later, recreate it from the same source path (`C:\Code\agent-setup-main`) and re-run the same copy step.
