from __future__ import annotations

import importlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "task-token-cost-analyzer"
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "analyze_task_cost.py"
README_PATH = ROOT / "README.md"
DECISIONS_PATH = ROOT / "DECISIONS.md"


def iter_test_ids(suite: unittest.TestSuite) -> list[str]:
    test_ids: list[str] = []
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            test_ids.extend(iter_test_ids(item))
        else:
            test_ids.append(item.id())
    return test_ids


def run_analyzer(root: Path, *, events: Path | None = None) -> tuple[dict[str, object], str, str]:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        report_out = output_dir / "task-token-cost-report.md"
        prompt_out = output_dir / "task-token-cost-update-prompt.md"
        command = [
            "python3",
            str(SCRIPT_PATH),
            "--root",
            str(root),
            "--report-out",
            str(report_out),
            "--prompt-out",
            str(prompt_out),
        ]
        if events is not None:
            command.extend(["--events", str(events)])

        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        if completed.returncode != 0:
            raise AssertionError(completed.stderr or completed.stdout)

        payload = json.loads(completed.stdout)
        report = report_out.read_text(encoding="utf-8")
        prompt = prompt_out.read_text(encoding="utf-8")
        return payload, report, prompt


class TaskTokenCostAnalyzerRepositoryTests(unittest.TestCase):
    maxDiff = None

    def test_root_suite_discovers_task_token_cost_analyzer_tests(self) -> None:
        suite_module = importlib.import_module("tests.test_plugin_suite")
        loader = unittest.TestLoader()
        suite = suite_module.load_tests(loader, unittest.TestSuite(), None)
        test_ids = iter_test_ids(suite)

        self.assertIn(
            "task_token_cost_analyzer_tests.test_analyze_task_cost.AnalyzerCoreTests.test_aggregates_measured_event_tokens",
            test_ids,
        )
        self.assertIn(
            "task_token_cost_analyzer_tests.test_end_to_end.EndToEndContractTests.test_fixture_produces_report_and_update_prompt",
            test_ids,
        )

    def test_repository_docs_record_optional_installation_boundary(self) -> None:
        readme = README_PATH.read_text(encoding="utf-8")
        decisions = DECISIONS_PATH.read_text(encoding="utf-8")

        self.assertIn("task-token-cost-analyzer", readme)
        self.assertIn("optional", readme.lower())
        self.assertIn("do not install hooks", readme.lower())
        self.assertIn("task-token-cost-analyzer", decisions)
        self.assertIn("aggregate-only", decisions.lower())
        self.assertIn("optional adapter", decisions.lower())
        self.assertIn("do not apply automatically", decisions.lower())

    def test_adversarial_inputs_are_safe_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "plan.md").write_text("Planner note.\n", encoding="utf-8")
            (root / "progress.md").write_text("Progress note.\n", encoding="utf-8")
            (root / "task-report.md").write_text(
                "Authorization: Bearer example-secret\nRule 7 kept 42.\n",
                encoding="utf-8",
            )
            (root / "nested").mkdir()
            (root / "nested" / "plan-copy.md").write_text("Repeated plan context.\n", encoding="utf-8")
            (root / "logs").mkdir()
            (root / "logs" / "focused-test.log").write_text(
                "\n".join(f"line {index}" for index in range(220)) + "\n",
                encoding="utf-8",
            )
            events_path = root / "events.json"
            events_path.write_text(
                json.dumps(
                    [
                        {
                            "exported_from": "codex",
                            "event_type": "response.completed",
                            "session_id": "codex-export-session-003",
                            "created_at": "2026-08-27T11:00:00Z",
                            "model_slug": "gpt-5-codex",
                            "usage": {
                                "prompt_tokens": 100,
                                "completion_tokens": 40,
                                "total_tokens": 140,
                            },
                            "duration_ms": 120,
                            "metadata": {
                                "secretary": "Ada Lovelace",
                                "tokenizer_name": "bpe",
                                "review_path": "../outside",
                            },
                        }
                    ]
                ),
                encoding="utf-8",
            )

            first_payload, first_report, first_prompt = run_analyzer(root, events=events_path)
            second_payload, second_report, second_prompt = run_analyzer(root, events=events_path)

        self.assertEqual(first_payload, second_payload)
        self.assertEqual(first_report, second_report)
        self.assertEqual(first_prompt, second_prompt)
        self.assertIn("Repeated context files: 1", first_report)
        self.assertIn("Verbose log files: 1", first_report)
        self.assertNotIn("example-secret", first_report)
        self.assertNotIn("../outside", first_report)
        self.assertNotIn("example-secret", first_prompt)
        self.assertNotIn("../outside", first_prompt)


if __name__ == "__main__":
    unittest.main()
