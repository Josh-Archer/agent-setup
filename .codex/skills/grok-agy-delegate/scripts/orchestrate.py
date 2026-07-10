#!/usr/bin/env python3
"""Run a dependency-aware multi-agent plan through Grok and/or Antigravity."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DELEGATE = SCRIPT_DIR / "delegate.py"
SUCCESS_STATUSES = frozenset({"completed", "dry-run"})
BLOCKING_STATUSES = frozenset({"failed", "timed-out", "skipped"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-file", type=Path, required=True)
    parser.add_argument("--provider", choices=("grok", "agy"), help="Override the plan's default provider")
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--max-parallel", type=int, default=3)
    parser.add_argument("--task-timeout-seconds", type=int, default=600)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def load_plan(path: Path) -> dict[str, Any]:
    plan = json.loads(path.read_text())
    if not isinstance(plan, dict) or not plan.get("goal") or not isinstance(plan.get("tasks"), list):
        raise SystemExit("Plan must contain a non-empty 'goal' and a 'tasks' array")
    ids = [task.get("id") for task in plan["tasks"]]
    if any(not isinstance(task, dict) or not task.get("id") or not task.get("prompt") for task in plan["tasks"]):
        raise SystemExit("Each task needs non-empty 'id' and 'prompt' fields")
    if len(set(ids)) != len(ids):
        raise SystemExit("Task ids must be unique")
    known = set(ids)
    for task in plan["tasks"]:
        for dependency in task.get("depends_on", []):
            if dependency not in known:
                raise SystemExit(f"Task {task['id']} depends on unknown task {dependency}")
    # Validate the dependency graph can be ordered (cycle detection).
    batches(plan["tasks"])
    return plan


def batches(tasks: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Topological batches for cycle detection and dry planning.

    Runtime execution does not use this alone: dependents of failed or
    timed-out tasks are skipped even when the DAG is otherwise valid.
    """
    pending = {task["id"]: task for task in tasks}
    completed: set[str] = set()
    result: list[list[dict[str, Any]]] = []
    while pending:
        ready = [task for task in pending.values() if set(task.get("depends_on", [])) <= completed]
        if not ready:
            raise SystemExit("Task dependency cycle detected")
        result.append(ready)
        for task in ready:
            completed.add(task["id"])
            pending.pop(task["id"])
    return result


def task_prompt(plan: dict[str, Any], task: dict[str, Any], run_dir: Path, handoffs: list[Path]) -> str:
    prior = "\n".join(f"- {path}" for path in handoffs) or "- none"
    return f"""You are worker {task['id']} in a coordinated agent run.

Overall goal:
{plan['goal']}

Your assigned task:
{task['prompt']}

Shared run directory: {run_dir}
Read completed dependency handoffs before starting:
{prior}

Stay within the requested scope. If you edit files, report the exact paths and validation. End with a concise handoff summary for the manager."""


def skipped_task_result(
    task: dict[str, Any],
    run_dir: Path,
    blocked_by: list[str],
    results_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    task_dir = run_dir / "tasks" / task["id"]
    task_dir.mkdir(parents=True, exist_ok=True)
    output_file = task_dir / "output.txt"
    error_file = task_dir / "stderr.txt"
    reasons = []
    for dep in blocked_by:
        status = results_by_id[dep]["status"]
        reasons.append(f"{dep} ({status})")
    message = (
        "SKIPPED: dependency did not succeed: "
        + ", ".join(reasons)
        + "\nDependents are not executed after failed, timed-out, or skipped prerequisites.\n"
    )
    output_file.write_text(message)
    error_file.write_text(message)
    return {
        "id": task["id"],
        "status": "skipped",
        "blocked_by": blocked_by,
        "output": str(output_file),
        "stderr": str(error_file),
        "started": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def blocking_dependencies(task: dict[str, Any], results_by_id: dict[str, dict[str, Any]]) -> list[str]:
    blocked: list[str] = []
    for dep in task.get("depends_on", []):
        result = results_by_id.get(dep)
        if result is not None and result["status"] in BLOCKING_STATUSES:
            blocked.append(dep)
    return blocked


def dependencies_ready(task: dict[str, Any], results_by_id: dict[str, dict[str, Any]]) -> bool:
    for dep in task.get("depends_on", []):
        result = results_by_id.get(dep)
        if result is None or result["status"] not in SUCCESS_STATUSES:
            return False
    return True


def run_task(plan: dict[str, Any], task: dict[str, Any], cwd: str, run_dir: Path, outputs: dict[str, Path], default_timeout: int) -> dict[str, Any]:
    task_dir = run_dir / "tasks" / task["id"]
    task_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = task_dir / "prompt.txt"
    output_file = task_dir / "output.txt"
    error_file = task_dir / "stderr.txt"
    handoffs = [outputs[dep] for dep in task.get("depends_on", []) if dep in outputs]
    prompt_file.write_text(task_prompt(plan, task, run_dir, handoffs))
    command = [sys.executable, str(DELEGATE), "--provider", task.get("provider", plan.get("provider", "agy")), "--cwd", cwd, "--prompt-file", str(prompt_file)]
    if task.get("role"):
        command += ["--role", task["role"]]
    if task.get("model"):
        command += ["--model", task["model"]]
    if task.get("output_format"):
        command += ["--output-format", task["output_format"]]

    started = dt.datetime.now(dt.timezone.utc).isoformat()
    if task.get("dry_run"):
        output_file.write_text("DRY RUN\n" + json.dumps(command))
        return {"id": task["id"], "status": "dry-run", "output": str(output_file), "command": command}
    try:
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=task.get("timeout_seconds", default_timeout))
        output_file.write_text(result.stdout)
        error_file.write_text(result.stderr)
        status = "completed" if result.returncode == 0 else "failed"
        return {"id": task["id"], "status": status, "returncode": result.returncode, "output": str(output_file), "stderr": str(error_file), "started": started}
    except subprocess.TimeoutExpired as exc:
        output_file.write_text(exc.stdout or "")
        error_file.write_text((exc.stderr or "") + "\nTask timed out")
        return {"id": task["id"], "status": "timed-out", "output": str(output_file), "stderr": str(error_file), "started": started}


def execute_plan(
    plan: dict[str, Any],
    cwd: str,
    run_dir: Path,
    max_parallel: int,
    default_timeout: int,
) -> list[dict[str, Any]]:
    """Run tasks with dependency awareness; skip dependents of non-success tasks."""
    pending = {task["id"]: task for task in plan["tasks"]}
    results_by_id: dict[str, dict[str, Any]] = {}
    outputs: dict[str, Path] = {}
    results: list[dict[str, Any]] = []

    while pending:
        ready = [task for task in pending.values() if dependencies_ready(task, results_by_id)]
        if ready:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as pool:
                futures = [
                    pool.submit(run_task, plan, task, cwd, run_dir, outputs, default_timeout)
                    for task in ready
                ]
                for future in futures:
                    result = future.result()
                    results.append(result)
                    results_by_id[result["id"]] = result
                    outputs[result["id"]] = Path(result["output"])
                    pending.pop(result["id"])
            continue

        skipped_any = False
        for task_id, task in list(pending.items()):
            blocked_by = blocking_dependencies(task, results_by_id)
            if not blocked_by:
                continue
            result = skipped_task_result(task, run_dir, blocked_by, results_by_id)
            results.append(result)
            results_by_id[result["id"]] = result
            outputs[result["id"]] = Path(result["output"])
            pending.pop(task_id)
            skipped_any = True
        if skipped_any:
            continue

        raise SystemExit("Task dependency cycle detected")

    return results


def main() -> int:
    args = parse_args()
    plan = load_plan(args.plan_file)
    if args.provider:
        plan["provider"] = args.provider
    if args.dry_run:
        for task in plan["tasks"]:
            task["dry_run"] = True
    cwd = str(Path(args.cwd).resolve())
    run_dir = args.run_dir or (Path(cwd) / ".agent-runs" / (dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]))
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")

    results = execute_plan(plan, cwd, run_dir, args.max_parallel, args.task_timeout_seconds)

    manager_provider = plan.get("manager_provider", plan.get("provider", "agy"))
    manager_dir = run_dir / "manager"
    manager_dir.mkdir(parents=True, exist_ok=True)
    manager_prompt = manager_dir / "prompt.txt"
    result_lines = "\n".join(f"- {item['id']}: {item['status']} ({item.get('output')})" for item in results)
    manager_prompt.write_text(f"""You are the manager for a coordinated agent run.

Goal:
{plan['goal']}

Completed task handoffs:
{result_lines}

Read the task output files, reconcile conflicts, and return:
1. a concise outcome summary,
2. files changed or recommended,
3. validation evidence,
4. unresolved risks or follow-ups.
Do not redo completed work unless a handoff is missing or contradictory.""")

    manager_result: dict[str, Any]
    if args.dry_run:
        manager_result = {"status": "dry-run", "output": str(manager_dir / "output.txt")}
        (manager_dir / "output.txt").write_text("DRY RUN\n")
    else:
        manager_command = [sys.executable, str(DELEGATE), "--provider", manager_provider, "--role", plan.get("manager_role", "manager"), "--cwd", cwd, "--prompt-file", str(manager_prompt)]
        if plan.get("manager_model"):
            manager_command += ["--model", plan["manager_model"]]
        manager_output = manager_dir / "output.txt"
        manager_error = manager_dir / "stderr.txt"
        try:
            manager_process = subprocess.run(manager_command, cwd=cwd, text=True, capture_output=True, timeout=plan.get("manager_timeout_seconds", args.task_timeout_seconds))
            manager_output.write_text(manager_process.stdout)
            manager_error.write_text(manager_process.stderr)
            manager_result = {"status": "completed" if manager_process.returncode == 0 else "failed", "returncode": manager_process.returncode, "output": str(manager_output), "stderr": str(manager_error)}
        except subprocess.TimeoutExpired as exc:
            manager_output.write_text(exc.stdout or "")
            manager_error.write_text((exc.stderr or "") + "\nManager timed out")
            manager_result = {"status": "timed-out", "output": str(manager_output), "stderr": str(manager_error)}

    manifest = {"run_dir": str(run_dir), "tasks": results, "manager": manager_result}
    (run_dir / "run.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0 if all(item["status"] in SUCCESS_STATUSES for item in results) and manager_result["status"] in SUCCESS_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main())
