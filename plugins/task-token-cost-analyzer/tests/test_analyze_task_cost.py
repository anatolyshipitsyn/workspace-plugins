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


def write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def write_jsonl(path: Path, records: list[object]) -> Path:
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    return path


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

    def test_load_events_maps_claude_hook_and_codex_export_from_json_array(self) -> None:
        analyzer = load_analyzer(self)

        with tempfile.TemporaryDirectory() as temp_dir:
            events_path = write_json(
                Path(temp_dir) / "events.json",
                [
                    {
                        "hook_event_name": "Stop",
                        "session_id": "claude-hook-session-001",
                        "timestamp": "2026-08-27T09:00:00Z",
                        "model": "claude-sonnet-4",
                        "usage": {"input_tokens": 700, "output_tokens": 300},
                        "duration_ms": 1110,
                        "prompt": "secret-prompt",
                        "raw_body": {"api_key": "secret-value"},
                    },
                    {
                        "exported_from": "codex",
                        "event_type": "response.completed",
                        "session_id": "codex-export-session-001",
                        "created_at": "2026-08-27T09:01:00Z",
                        "model_slug": "gpt-5-codex",
                        "usage": {"prompt_tokens": 1000, "completion_tokens": 400, "total_tokens": 1400},
                        "duration_ms": 900,
                        "transcript": "secret-transcript",
                    },
                ],
            )

            events = analyzer.load_events(events_path)

        self.assertEqual(
            events,
            [
                {
                    "client": "claude",
                    "session_id_hash": "claude-hook-session-001",
                    "event": "stop",
                    "timestamp": "2026-08-27T09:00:00Z",
                    "model": "claude-sonnet-4",
                    "input_tokens": 700,
                    "output_tokens": 300,
                    "total_tokens": 1000,
                    "duration_ms": 1110,
                },
                {
                    "client": "codex",
                    "session_id_hash": "codex-export-session-001",
                    "event": "api_response",
                    "timestamp": "2026-08-27T09:01:00Z",
                    "model": "gpt-5-codex",
                    "input_tokens": 1000,
                    "output_tokens": 400,
                    "total_tokens": 1400,
                    "duration_ms": 900,
                },
            ],
        )

    def test_load_events_maps_claude_otel_jsonl_and_discards_raw_fields(self) -> None:
        analyzer = load_analyzer(self)

        with tempfile.TemporaryDirectory() as temp_dir:
            events_path = write_jsonl(
                Path(temp_dir) / "events.jsonl",
                [
                    {
                        "otel_scope": "claude",
                        "attributes": {
                            "event.name": "PostToolUse",
                            "session.id": "claude-otel-session-001",
                            "gen_ai.response.model": "claude-sonnet-4",
                            "gen_ai.usage.input_tokens": 400,
                            "gen_ai.usage.output_tokens": 100,
                            "gen_ai.latency.ms": 320,
                        },
                        "timestamp": "2026-08-27T09:02:00Z",
                        "prompt": "secret-prompt",
                        "transcript": "secret-transcript",
                    },
                    {
                        "otel_scope": "claude",
                        "attributes": {
                            "event.name": "Stop",
                            "session.id": "claude-otel-session-002",
                            "gen_ai.response.model": "claude-sonnet-4",
                            "gen_ai.usage.input_tokens": 200,
                            "gen_ai.usage.output_tokens": 50,
                            "gen_ai.latency.ms": 180,
                        },
                        "timestamp": "2026-08-27T09:03:00Z",
                        "raw_body": {"authorization": "Bearer secret-value"},
                    },
                ],
            )

            events = analyzer.load_events(events_path)

        self.assertEqual([event["event"] for event in events], ["api_response", "stop"])
        self.assertEqual([event["total_tokens"] for event in events], [500, 250])
        self.assertTrue(all(set(event) == set(analyzer.NORMALIZED_EVENT_FIELDS) for event in events))
        serialized = json.dumps(events, sort_keys=True)
        self.assertNotIn("secret-prompt", serialized)
        self.assertNotIn("secret-transcript", serialized)
        self.assertNotIn("secret-value", serialized)

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

    def test_cli_resolves_root_relative_events_path(self) -> None:
        self.assertTrue(SCRIPT_PATH.is_file(), f"missing analyzer script: {SCRIPT_PATH}")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "plan.md").write_text("# Plan\n", encoding="utf-8")
            events_path = write_jsonl(
                root / "events.jsonl",
                [
                    {
                        "exported_from": "codex",
                        "event_type": "stop",
                        "session_id": "codex-export-session-002",
                        "created_at": "2026-08-27T09:05:00Z",
                        "model_slug": "gpt-5-codex",
                        "usage": {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140},
                        "duration_ms": 120,
                    }
                ],
            )

            completed = run_cli(root, "--events", events_path.name)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["measured"]["total_tokens"], 140)
        self.assertEqual(payload["evidence"]["token_counts"], "measured")

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
