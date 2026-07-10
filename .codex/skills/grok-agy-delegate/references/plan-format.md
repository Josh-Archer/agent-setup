# Delegation plan format

Pass a JSON file to `.codex/skills/grok-agy-delegate/scripts/orchestrate.py`:

```json
{
  "goal": "Investigate and fix the failing deployment check.",
  "provider": "agy",
  "manager_role": "manager",
  "tasks": [
    {
      "id": "diagnose",
      "role": "debugger",
      "prompt": "Find the root cause. Do not edit files."
    },
    {
      "id": "validate",
      "role": "testing",
      "depends_on": ["diagnose"],
      "prompt": "Review the diagnosis handoff and run the narrowest confirming test."
    }
  ]
}
```

Each task may override `provider`, `model`, `role`, `output_format`, or
`timeout_seconds`. Optional plan-level fields include `manager_provider`,
`manager_model`, and `manager_timeout_seconds`. If `provider` is omitted, the
orchestrator defaults to `agy`.

Task output and prompts are written under the run directory (default
`.agent-runs/<run-id>/`), which lets later tasks and the manager communicate
through durable handoff files. A dependent runs only when every `depends_on`
entry finished with `completed` or `dry-run`; otherwise it is marked `skipped`
and is not executed.
