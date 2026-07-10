# Grok & Antigravity (agy) Delegation Guide

This guide details the setup, configuration, safety protocols, and invocation options for delegating repository tasks from Codex to Grok Build (`grok`) and Antigravity (`agy`).

---

## Setup & Pre-requisites

### 1. CLI Executables
Both CLI tools must be installed and available on the system `PATH`.
```bash
# Verify CLI accessibility
command -v grok
command -v agy
```
If a CLI is missing or unauthenticated, the delegation scripts will exit immediately with an error rather than falling back silently.

### 2. Synchronizing Agent Surfaces
Agent definitions are authored under `.codex/agents/*.agent.md`. To update the provider roles, run the sync script:
```bash
python3 scripts/sync_agent_surfaces.py
```
This script generates:
- `.grok/roles/*.toml` and `.grok/agents/*.md` for Grok.
- `.agents/plugins/home-codex-agents/agents/*.md` and configuration rules for the Antigravity plugin.

---

## Invocation Examples

### Single Agent Handoff (`delegate.py`)
Run a single agent role on a target directory:
```bash
python3 .codex/skills/grok-agy-delegate/scripts/delegate.py \
  --provider grok \
  --role debugger \
  --cwd "$PWD" \
  --prompt "Investigate why the test suite fails on gitops config files."
```

#### CLI Arguments
- `--provider`: Choose `grok` or `agy` (Required).
- `--role`: The named agent role (e.g. `debugger`, `devops`, `testing`).
- `--model`: Explicit provider-specific model override (optional).
- `--cwd`: Working directory path for the delegated execution (default: `.`).
- `--prompt` / `--prompt-file`: The prompt text or path to a file containing the prompt (mutually exclusive, required).
- `--dry-run`: Prints the generated command instead of executing it.
- `--output-format`: Output mode (`plain` (default), `json`, or `streaming-json`).

### Coordinated Multi-Agent Plan (`orchestrate.py`)
Run a dependency-aware plan across multiple agents:
```bash
python3 .codex/skills/grok-agy-delegate/scripts/orchestrate.py \
  --plan-file /tmp/my-agent-plan.json \
  --cwd "$PWD" \
  --max-parallel 3
```

#### CLI Arguments
- `--plan-file`: Path to the plan JSON file (Required).
- `--provider`: Optional provider override for the plan (`grok` or `agy`).
- `--cwd`: Active working directory (default: `.`).
- `--run-dir`: Override the default output folder (default: `.agent-runs/<timestamp>-<shortuuid>`).
- `--max-parallel`: Maximum number of concurrent workers (default: `3`).
- `--task-timeout-seconds`: Default timeout for each worker and the manager (default: `600`). A task can override this with `timeout_seconds` in the plan.
- `--dry-run`: Performs dry-run setup, writes prompt files, but runs no LLMs.

---

## JSON Plan Shape

Plans are loaded as JSON. Below is the schema structure and description:

```json
{
  "goal": "Reorganize the deployment manifests and test CI pipeline",
  "provider": "agy",
  "manager_role": "manager",
  "tasks": [
    {
      "id": "generate-manifests",
      "role": "gitops-architect",
      "prompt": "Create kustomize overlays for staging and production under grok-servaar/media."
    },
    {
      "id": "validate-linting",
      "role": "testing",
      "depends_on": ["generate-manifests"],
      "prompt": "Run yaml linting and validation on the newly generated overlays.",
      "provider": "grok"
    },
    {
      "id": "dry-run-deploy",
      "role": "devops",
      "depends_on": ["validate-linting"],
      "prompt": "Execute dry-run deploy checks on the target node."
    }
  ]
}
```

### JSON Fields Glossary
- **`goal`** *(string, required)*: The overall target outcome.
- **`provider`** *(string, optional)*: Default CLI provider (`grok` or `agy`) for tasks in the plan.
- **`manager_role`** *(string, optional)*: Reconciling agent role (default: `manager`).
- **`manager_provider`** *(string, optional)*: Override provider for the manager reconciliation phase (defaults to root `provider`).
- **`manager_model`** *(string, optional)*: Override model for the manager role.
- **`tasks`** *(array, required)*: Chronological and dependency-linked tasks.
  - **`id`** *(string, required)*: Unique identifier within the plan.
  - **`role`** *(string, required)*: Agent role definition to load.
  - **`prompt`** *(string, required)*: Specific task instructions.
  - **`depends_on`** *(array, optional)*: Task IDs that must successfully finish before this task starts.
  - **`provider`** *(string, optional)*: Override default provider for this task.
  - **`model`** *(string, optional)*: Override default model for this task.
  - **`output_format`** *(string, optional)*: Override output format.
  - **`timeout_seconds`** *(number, optional)*: Execution timeout in seconds.

---

## Provider Model Overrides

Model selection is determined dynamically by the complexity of the requested agent role. Mappings are defined as follows:

| Role Complexity Tier | Codex Model Class | Grok Equivalent | Antigravity Equivalent |
| :--- | :--- | :--- | :--- |
| **High / Reasoning** | `gpt-5.4`, `gpt-5.4-extended` | `grok-4.5` | `Claude Opus 4.6 (Thinking)` |
| **Medium / Fast** | `gpt-5.4-mini` | `grok-composer-2.5-fast` | `Gemini 3.5 Flash (Medium)` |
| **Low / Spark** | `gpt-5.3-codex-spark` | `grok-composer-2.5-fast` | `Gemini 3.5 Flash (Low)` |

### How to Override Models
1. **At the CLI Level**: Pass the `--model` parameter to `scripts/delegate.py`.
2. **At the Plan level**: Define a task-specific `"model"` key inside the plan JSON.

---

## Safety Boundaries

- **Local Permissions**: Execution operates under the active developer shell session permissions. The CLI has access to read and write files where the active shell does.
- **No Shared Secrets**: Never pass credentials, API keys, or browser sessions to delegation prompts.
- **Read-Only Safeties**: For tasks meant strictly for analysis (e.g. debugging, security scans), employ read-only roles like `security-auditor` or `gitops-architect` to prevent unintended code edits.
- **Code Change Inspection**: Delegated write operations are performed locally in the workspace. Run `git diff` to inspect changes before staging or committing them.

---

## Run Validation

### Exit Codes
The plan orchestrator yields:
- `0` if all tasks and the manager reconcile successfully.
- `1` if any task fails, times out, or the manager reconciliation reports failure.

### The Manifest (`run.json`)
At the end of an execution, a manifest JSON file is written to `.agent-runs/<run-id>/run.json` containing the metadata for audits:
```json
{
  "run_dir": "/path/to/repo/.agent-runs/20260710T124500Z-8b2a3c7d",
  "tasks": [
    {
      "id": "generate-manifests",
      "status": "completed",
      "returncode": 0,
      "output": "/path/to/repo/.agent-runs/20260710T124500Z-8b2a3c7d/tasks/generate-manifests/output.txt",
      "stderr": "/path/to/repo/.agent-runs/20260710T124500Z-8b2a3c7d/tasks/generate-manifests/stderr.txt",
      "started": "2026-07-10T16:45:00.123456Z"
    }
  ],
  "manager": {
    "status": "completed",
    "returncode": 0,
    "output": "/path/to/repo/.agent-runs/20260710T124500Z-8b2a3c7d/manager/output.txt",
    "stderr": "/path/to/repo/.agent-runs/20260710T124500Z-8b2a3c7d/manager/stderr.txt"
  }
}
```
