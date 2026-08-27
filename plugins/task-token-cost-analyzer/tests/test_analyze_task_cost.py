from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = ROOT / "plugins" / "task-token-cost-analyzer"
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "analyze_task_cost.py"
FIXTURES = PLUGIN_ROOT / "tests" / "fixtures"
MINIMAL_TASK_ROOT = FIXTURES / "minimal-task"
EVENTS = FIXTURES / "events"


def load_analyzer(testcase: unittest.TestCase):
    testcase.assertTrue(SCRIPT_PATH.is_file(), f"missing analyzer script: {SCRIPT_PATH}")
    spec = importlib.util.spec_from_file_location("analyze_task_cost", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to import {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    previous_module = sys.modules.get(spec.name)
    sys.modules[spec.name] = module
    previous_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        if previous_module is None:
            sys.modules.pop(spec.name, None)
        else:
            sys.modules[spec.name] = previous_module
        sys.dont_write_bytecode = previous_dont_write_bytecode
    return module


def run_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    command = [
        "python3",
        str(SCRIPT_PATH),
        "--root",
        str(root),
        "--format",
        "json",
        *args,
    ]
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
    )


class AnalyzerCoreTests(unittest.TestCase):
    maxDiff = None

    def test_aggregates_measured_event_tokens(self) -> None:
        analyzer = load_analyzer(self)

        result = analyzer.analyze_task(FIXTURES, EVENTS / "codex-usage.json")

        self.assertEqual(result.measured["total_tokens"], 3000)
        self.assertEqual(result.measured["input_tokens"], 1800)
        self.assertEqual(result.measured["output_tokens"], 1200)
        self.assertEqual(result.evidence["token_counts"], "measured")
        self.assertEqual(result.evidence["durations"], "measured")

    def test_marks_missing_tokens_as_estimated_or_missing(self) -> None:
        analyzer = load_analyzer(self)

        result = analyzer.analyze_task(MINIMAL_TASK_ROOT)

        self.assertIn(result.evidence["token_counts"], {"estimated", "missing"})
        self.assertNotIn("exact_total_tokens", result.measured)
        self.assertGreater(result.derived["artifact_bytes"], 0)

    def test_collects_relative_evidence_inventory(self) -> None:
        analyzer = load_analyzer(self)

        inventory = analyzer.collect_evidence(MINIMAL_TASK_ROOT)

        self.assertEqual(
            [item.relative_path for item in inventory.files],
            ["plan.md", "progress.md", "task-report.md"],
        )
        self.assertEqual(
            [item.evidence_class for item in inventory.files],
            ["plan", "progress", "report"],
        )
        self.assertTrue(all(not Path(item.relative_path).is_absolute() for item in inventory.files))

    def test_rejects_event_paths_outside_root(self) -> None:
        analyzer = load_analyzer(self)

        with self.assertRaisesRegex(ValueError, "outside"):
            analyzer.analyze_task(MINIMAL_TASK_ROOT, EVENTS / "codex-usage.json")

    def test_rejects_malformed_and_negative_event_data_without_echoing_payload(self) -> None:
        self.assertTrue(SCRIPT_PATH.is_file(), f"missing analyzer script: {SCRIPT_PATH}")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "task-report.md").write_text("# Report\n", encoding="utf-8")
            malformed = root / "bad-events.json"
            malformed.write_text(
                json.dumps(
                    {
                        "client": "codex",
                        "session_id_hash": "session-1",
                        "event": "stop",
                        "timestamp": "2026-08-27T08:17:00Z",
                        "model": "gpt-5-codex",
                        "input_tokens": -1,
                        "output_tokens": 2,
                        "total_tokens": 1,
                        "duration_ms": 100,
                        "raw_body": "secret-value",
                    }
                ),
                encoding="utf-8",
            )

            completed = run_cli(root, "--events", str(malformed))

        self.assertEqual(completed.returncode, 2)
        self.assertNotIn("secret-value", completed.stderr)

    def test_redacts_secret_like_report_content(self) -> None:
        analyzer = load_analyzer(self)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "plan.md").write_text("Rule 7 expects 42 tokens.\n", encoding="utf-8")
            (root / "task-report.md").write_text(
                "Authorization: Bearer secret-value\napi_key=secret-value\nRule 7 kept 42.\n",
                encoding="utf-8",
            )

            result = analyzer.analyze_task(root)

        serialized = json.dumps(result.to_dict(), sort_keys=True)
        self.assertNotIn("secret-value", serialized)
        self.assertIn("redacted", serialized.lower())

    def test_redact_text_preserves_rule_names_and_numbers(self) -> None:
        analyzer = load_analyzer(self)

        redacted = analyzer.redact_text("Rule 7 token=secret-value count=42")

        self.assertIn("Rule 7", redacted)
        self.assertIn("42", redacted)
        self.assertNotIn("secret-value", redacted)


if __name__ == "__main__":
    unittest.main()
