---
name: grok-agy-delegate
description: Delegate repository work from Codex to the installed Grok Build or Antigravity (agy) CLI using the repo's named agent roles and equivalent provider models. Use when the user explicitly asks to use Grok, Grok Build, agy, Antigravity, or an external coding model, or wants a second-agent implementation, review, research, or validation pass.
---

# Grok and Antigravity delegation

Use the bundled `scripts/delegate.py` wrapper to run a named repository agent through `grok` or `agy`. Keep the provider choice explicit when the user names one. If the user asks for a second opinion without choosing a provider, prefer Grok for a code review or architecture pass and agy for a fast implementation or validation pass.

## Workflow

1. Confirm the target repository and the requested role. Available roles are the files in `.codex/agents/` and are mirrored into `.grok/agents/`, `.grok/roles/`, and the Antigravity workspace plugin.
2. Check the selected CLI is available with `command -v grok` or `command -v agy`. If it is unavailable or unauthenticated, report that instead of silently switching providers.
3. Delegate through the wrapper:

   ```bash
   python3 .codex/skills/grok-agy-delegate/scripts/delegate.py \
     --provider grok --role debugger --cwd "$PWD" \
     --prompt "Investigate the failing test and report the root cause without editing files."
   ```

4. Use `--dry-run` first when constructing a new invocation or when the prompt contains shell-sensitive text.
5. Return the provider, selected role/model, exit status, and the complete delegated result. Clearly distinguish provider output from Codex's own conclusions.

## Safety and scope

- The wrapper runs the provider CLI locally with the current user's credentials and filesystem permissions.
- Do not pass API keys, browser tokens, passwords, or unrelated private files unless the user explicitly asks for that exact data to be sent to the selected provider.
- Read-only tasks should use `--no-write` where the provider supports it, or a read-only role such as `gitops-architect` or `security-auditor`.
- Do not use auto-approval or dangerous permission flags unless the user explicitly requests that execution mode.
- A delegated agent's edits are local workspace changes. Inspect `git diff` before reporting them as accepted.

## Provider defaults

- Grok: named agents resolve their model from `.grok/agents/*.md`; high-complexity roles use Grok 4.5 and fast roles use Composer 2.5 Fast.
- agy: named agents resolve their model from the Antigravity workspace plugin; high-complexity roles use Claude Opus 4.6 Thinking and fast roles use Gemini 3.5 Flash.
- Pass `--model` only when the user requests a specific provider model or when overriding the role's configured equivalent is part of the task.

## Common uses

- `architect` or `gitops-architect`: ask for a design or rollout plan.
- `development` or `devops`: implement a scoped change.
- `debugger`: isolate a failure without changing files.
- `security-auditor`: review a diff for concrete security issues.
- `testing` or `validation-runner`: run focused checks and report evidence.
- `manager`: coordinate a multi-step task when the provider supports subagents.
