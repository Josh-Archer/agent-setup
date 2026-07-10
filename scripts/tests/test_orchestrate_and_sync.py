#!/usr/bin/env python3
"""Focused unit tests for orchestration dependency policy and surface sync helpers."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATE_PATH = ROOT / ".codex" / "skills" / "grok-agy-delegate" / "scripts" / "orchestrate.py"
SYNC_PATH = ROOT / "scripts" / "sync_agent_surfaces.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OrchestrateDependencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.orch = load_module("orchestrate_under_test", ORCHESTRATE_PATH)

    def test_batches_orders_dependencies(self) -> None:
        tasks = [
            {"id": "b", "depends_on": ["a"], "prompt": "b"},
            {"id": "a", "prompt": "a"},
            {"id": "c", "depends_on": ["b"], "prompt": "c"},
        ]
        batches = self.orch.batches(tasks)
        self.assertEqual([t["id"] for t in batches[0]], ["a"])
        self.assertEqual([t["id"] for t in batches[1]], ["b"])
        self.assertEqual([t["id"] for t in batches[2]], ["c"])

    def test_batches_detects_cycle(self) -> None:
        tasks = [
            {"id": "a", "depends_on": ["b"], "prompt": "a"},
            {"id": "b", "depends_on": ["a"], "prompt": "b"},
        ]
        with self.assertRaises(SystemExit):
            self.orch.batches(tasks)

    def test_failed_prerequisite_skips_dependents(self) -> None:
        plan = {
            "goal": "test skip policy",
            "provider": "agy",
            "tasks": [
                {"id": "upstream", "role": "debugger", "prompt": "fail me"},
                {"id": "downstream", "role": "testing", "depends_on": ["upstream"], "prompt": "should skip"},
                {"id": "cascade", "role": "testing", "depends_on": ["downstream"], "prompt": "should skip too"},
            ],
        }

        def fake_run_task(plan_arg, task, cwd, run_dir, outputs, default_timeout):
            task_dir = run_dir / "tasks" / task["id"]
            task_dir.mkdir(parents=True, exist_ok=True)
            output = task_dir / "output.txt"
            if task["id"] == "upstream":
                output.write_text("boom")
                return {
                    "id": "upstream",
                    "status": "failed",
                    "returncode": 1,
                    "output": str(output),
                    "stderr": str(task_dir / "stderr.txt"),
                }
            self.fail(f"dependent task {task['id']} should not have been executed")
            return {}

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            with mock.patch.object(self.orch, "run_task", side_effect=fake_run_task):
                results = self.orch.execute_plan(plan, cwd=tmp, run_dir=run_dir, max_parallel=2, default_timeout=30)

            by_id = {item["id"]: item for item in results}
            self.assertEqual(by_id["upstream"]["status"], "failed")
            self.assertEqual(by_id["downstream"]["status"], "skipped")
            self.assertEqual(by_id["cascade"]["status"], "skipped")
            self.assertEqual(by_id["downstream"]["blocked_by"], ["upstream"])
            self.assertEqual(by_id["cascade"]["blocked_by"], ["downstream"])
            self.assertIn("SKIPPED", Path(by_id["downstream"]["output"]).read_text())

    def test_timed_out_prerequisite_skips_dependents(self) -> None:
        plan = {
            "goal": "test timeout skip",
            "tasks": [
                {"id": "slow", "prompt": "timeout"},
                {"id": "after", "depends_on": ["slow"], "prompt": "skip"},
            ],
        }

        def fake_run_task(plan_arg, task, cwd, run_dir, outputs, default_timeout):
            task_dir = run_dir / "tasks" / task["id"]
            task_dir.mkdir(parents=True, exist_ok=True)
            output = task_dir / "output.txt"
            if task["id"] == "slow":
                output.write_text("partial")
                return {"id": "slow", "status": "timed-out", "output": str(output), "stderr": str(task_dir / "stderr.txt")}
            self.fail("dependent should not run after timeout")
            return {}

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            with mock.patch.object(self.orch, "run_task", side_effect=fake_run_task):
                results = self.orch.execute_plan(plan, cwd=tmp, run_dir=run_dir, max_parallel=1, default_timeout=1)

        by_id = {item["id"]: item for item in results}
        self.assertEqual(by_id["slow"]["status"], "timed-out")
        self.assertEqual(by_id["after"]["status"], "skipped")

    def test_successful_chain_runs_dependents(self) -> None:
        plan = {
            "goal": "happy path",
            "tasks": [
                {"id": "a", "prompt": "a"},
                {"id": "b", "depends_on": ["a"], "prompt": "b"},
            ],
        }
        seen: list[str] = []

        def fake_run_task(plan_arg, task, cwd, run_dir, outputs, default_timeout):
            seen.append(task["id"])
            task_dir = run_dir / "tasks" / task["id"]
            task_dir.mkdir(parents=True, exist_ok=True)
            output = task_dir / "output.txt"
            output.write_text(f"ok {task['id']}")
            return {"id": task["id"], "status": "completed", "returncode": 0, "output": str(output)}

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            with mock.patch.object(self.orch, "run_task", side_effect=fake_run_task):
                results = self.orch.execute_plan(plan, cwd=tmp, run_dir=run_dir, max_parallel=1, default_timeout=30)

        self.assertEqual(seen, ["a", "b"])
        self.assertTrue(all(item["status"] == "completed" for item in results))


class SyncSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sync = load_module("sync_under_test", SYNC_PATH)

    def test_model_mapping_tiers(self) -> None:
        self.assertEqual(self.sync.grok_model("gpt-5.4"), "grok-4.5")
        self.assertEqual(self.sync.grok_model("gpt-5.4-mini"), "grok-composer-2.5-fast")
        self.assertEqual(self.sync.grok_model("gpt-5.3-codex-spark"), "grok-composer-2.5-fast")
        self.assertEqual(self.sync.agy_model("gpt-5.4"), "Claude Opus 4.6 (Thinking)")
        self.assertEqual(self.sync.agy_model("gpt-5.4-mini"), "Gemini 3.5 Flash (Medium)")
        self.assertEqual(self.sync.agy_model("gpt-5.3-codex-spark"), "Gemini 3.5 Flash (Low)")

    def test_check_surfaces_clean_on_repo(self) -> None:
        # Requires generated trees to already match; run sync in the suite setup path if needed.
        code = self.sync.check_surfaces()
        self.assertEqual(code, 0)

    def test_frontmatter_parse(self) -> None:
        meta, body = self.sync.frontmatter("---\nname: x\nmodel: gpt-5.4\n---\nHello\n")
        self.assertEqual(meta["name"], "x")
        self.assertEqual(meta["model"], "gpt-5.4")
        self.assertTrue(body.startswith("Hello"))


class ExamplePlanTests(unittest.TestCase):
    def test_example_plan_is_valid_json(self) -> None:
        path = ROOT / ".codex" / "skills" / "grok-agy-delegate" / "references" / "example-plan.json"
        plan = json.loads(path.read_text())
        self.assertIn("goal", plan)
        self.assertIsInstance(plan["tasks"], list)
        self.assertTrue(plan["tasks"])


if __name__ == "__main__":
    unittest.main()
