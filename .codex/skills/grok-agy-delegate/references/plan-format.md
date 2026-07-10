# Delegation plan format

Pass a JSON file to `scripts/orchestrate.py`:

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
`timeout_seconds`. Task output and prompts are written under the run directory,
which lets later tasks and the manager communicate through durable handoff files.
