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
SKILL_PATH = PLUGIN_ROOT / "skills" / "analyze-task-token-cost" / "SKILL.md"
REPORT_TEMPLATE = PLUGIN_ROOT / "templates" / "cost-report.md"
PROMPT_TEMPLATE = PLUGIN_ROOT / "templates" / "plugin-update-prompt.md"
README_PATH = PLUGIN_ROOT / "README.md"
CHANGELOG_PATH = PLUGIN_ROOT / "CHANGELOG.md"
CLIENT_GUIDANCE_PATH = (
    PLUGIN_ROOT / "skills" / "analyze-task-token-cost" / "references" / "client-guidance.md"
)
FIXTURES = PLUGIN_ROOT / "tests" / "fixtures"
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


def run_analyzer(
    root: Path,
    events: Path,
    report_out: Path,
    prompt_out: Path,
) -> subprocess.CompletedProcess[str]:
    command = [
        "python3",
        str(SCRIPT_PATH),
        "--root",
        str(root),
        "--events",
        str(events),
        "--report-out",
        str(report_out),
        "--prompt-out",
        str(prompt_out),
    ]
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
    )


class EndToEndContractTests(unittest.TestCase):
    maxDiff = None

    def test_fixture_produces_report_and_update_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report_out = output_dir / "task-token-cost-report.md"
            prompt_out = output_dir / "task-token-cost-update-prompt.md"

            result = run_analyzer(FIXTURES, EVENTS / "codex-usage.json", report_out, prompt_out)
            report = report_out.read_text(encoding="utf-8") if report_out.exists() else ""
            prompt = prompt_out.read_text(encoding="utf-8") if prompt_out.exists() else ""

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["measured"]["total_tokens"], 3000)
        for section in (
            "## Scope",
            "## Evidence",
            "## Acceptance Matrix",
            "## Cost Breakdown",
            "## Avoidable Costs",
            "## Recommendations",
            "## Limitations",
        ):
            self.assertIn(section, report)
        for section in (
            "## Target Files",
            "## Problem",
            "## Proposed Change",
            "## Acceptance Tests",
            "## Safety Constraints",
        ):
            self.assertIn(section, prompt)
        self.assertIn("do not apply automatically", prompt.lower())
        self.assertIn("task-only context", prompt.lower())
        self.assertIn("| Security | not observed |", report)
        self.assertIn("no secret scrubbing evidence was observed", report.lower())
        self.assertNotIn("| Security | pass |", report)

    def test_render_helpers_return_markdown_without_writing_files(self) -> None:
        analyzer = load_analyzer(self)
        self.assertTrue(REPORT_TEMPLATE.is_file(), f"missing report template: {REPORT_TEMPLATE}")
        self.assertTrue(PROMPT_TEMPLATE.is_file(), f"missing prompt template: {PROMPT_TEMPLATE}")

        result = analyzer.analyze_task(FIXTURES, EVENTS / "codex-usage.json")

        report = analyzer.render_report(result, REPORT_TEMPLATE)
        prompt = analyzer.render_update_prompt(result, PROMPT_TEMPLATE)

        self.assertIsInstance(report, str)
        self.assertIsInstance(prompt, str)
        self.assertIn("Acceptance Matrix", report)
        self.assertIn("Avoidable Costs", report)
        self.assertIn("Target Files", prompt)
        self.assertIn("Safety Constraints", prompt)

    def test_report_marks_security_pass_only_when_secret_scrubbing_evidence_exists(self) -> None:
        analyzer = load_analyzer(self)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "plan.md").write_text("Plan keeps scope bounded.\n", encoding="utf-8")
            (root / "task-report.md").write_text(
                "Authorization: Bearer example-secret\napi_key=example-secret\n",
                encoding="utf-8",
            )

            result = analyzer.analyze_task(root)

        report = analyzer.render_report(result, REPORT_TEMPLATE)

        self.assertEqual(result.evidence["secret_scrubbing"], "derived")
        self.assertIn("| Security | pass |", report)
        self.assertIn("redacted secret-like values", report)
        self.assertNotIn("| Security | not observed |", report)

    def test_adversarial_fixture_stays_deterministic_and_aggregate_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            root = temp_root / "task-root"
            root.mkdir()
            (root / "plan.md").write_text("Primary plan.\n", encoding="utf-8")
            (root / "task-report.md").write_text(
                "Authorization: Bearer example-secret\nRule 7 kept 42.\n",
                encoding="utf-8",
            )
            (root / "nested").mkdir()
            (root / "nested" / "plan-copy.md").write_text("Repeated plan context.\n", encoding="utf-8")
            (root / "nested" / "review.md").write_text("Second review.\n", encoding="utf-8")
            (root / "focused-tests.log").write_text(
                "\n".join(f"line {index}" for index in range(220)) + "\n",
                encoding="utf-8",
            )
            events = root / "events.json"
            events.write_text(
                json.dumps(
                    [
                        {
                            "exported_from": "codex",
                            "event_type": "stop",
                            "session_id": "codex-export-session-005",
                            "created_at": "2026-08-27T10:12:00Z",
                            "model_slug": "gpt-5-codex",
                            "usage": {"prompt_tokens": 60, "completion_tokens": 20, "total_tokens": 80},
                            "duration_ms": 45,
                            "metadata": {
                                "secretary": "Ada Lovelace",
                                "tokenizer_name": "bpe",
                                "relative_review_path": "../outside",
                            },
                        }
                    ]
                ),
                encoding="utf-8",
            )

            first_output_dir = temp_root / "run-one"
            second_output_dir = temp_root / "run-two"
            first_output_dir.mkdir()
            second_output_dir.mkdir()

            first_report_out = first_output_dir / "report.md"
            first_prompt_out = first_output_dir / "prompt.md"
            second_report_out = second_output_dir / "report.md"
            second_prompt_out = second_output_dir / "prompt.md"

            first = run_analyzer(root, events, first_report_out, first_prompt_out)
            second = run_analyzer(root, events, second_report_out, second_prompt_out)

            first_report = first_report_out.read_text(encoding="utf-8")
            first_prompt = first_prompt_out.read_text(encoding="utf-8")
            second_report = second_report_out.read_text(encoding="utf-8")
            second_prompt = second_prompt_out.read_text(encoding="utf-8")

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(first.stdout), json.loads(second.stdout))
        self.assertEqual(first_report, second_report)
        self.assertEqual(first_prompt, second_prompt)
        self.assertIn("Repeated context files: 1", first_report)
        self.assertIn("Verbose log files: 1", first_report)
        self.assertNotIn("example-secret", first_report)
        self.assertNotIn("example-secret", first_prompt)
        self.assertNotIn("../outside", first_report)
        self.assertNotIn("../outside", first_prompt)

    def test_skill_routes_to_cli_and_documents_pressure_guardrails(self) -> None:
        for path in (SKILL_PATH, README_PATH, CHANGELOG_PATH, CLIENT_GUIDANCE_PATH):
            self.assertTrue(path.is_file(), f"missing Task 3 artifact: {path.relative_to(PLUGIN_ROOT)}")

        skill = SKILL_PATH.read_text(encoding="utf-8")
        readme = README_PATH.read_text(encoding="utf-8")
        changelog = CHANGELOG_PATH.read_text(encoding="utf-8")
        client_guidance = CLIENT_GUIDANCE_PATH.read_text(encoding="utf-8")

        self.assertIn("analyze_task_cost.py", skill)
        self.assertIn("current task brief", skill.lower())
        self.assertIn("complete conversation history", skill.lower())
        self.assertIn("task-only context", skill.lower())
        self.assertIn("focused tests", skill.lower())
        self.assertIn("independent review", skill.lower())
        self.assertIn("local adversarial audit", skill.lower())
        self.assertIn("validator", skill.lower())
        self.assertIn("batched", skill.lower())
        self.assertIn("update prompt", skill.lower())
        self.assertIn("do not apply automatically", skill.lower())
        self.assertIn("Claude", skill)
        self.assertIn("Codex", skill)
        self.assertIn("MCP", skill)
        self.assertIn("YAML", skill)
        self.assertIn("security", skill.lower())
        self.assertIn("absolute path", skill.lower())
        self.assertIn("root-relative", skill.lower())

        for hook_event in ("SessionStart", "UserPromptSubmit", "PostToolUse", "SubagentStop", "Stop"):
            self.assertIn(hook_event, readme)
        self.assertIn("optional", readme.lower())
        self.assertIn("Compliance API", readme)
        self.assertIn("client/account dependent", readme)
        self.assertIn("tool counts", readme.lower())
        self.assertIn("durations", readme.lower())
        self.assertIn("not automatic llm token counts", readme.lower())
        self.assertIn("do not install hooks", readme.lower())
        self.assertIn("absolute path", readme.lower())
        self.assertIn("root-relative", readme.lower())

        self.assertIn("0.1.0", changelog)
        self.assertIn("update prompt", changelog.lower())

        self.assertIn("absolute path", client_guidance.lower())
        self.assertIn("root-relative", client_guidance.lower())


if __name__ == "__main__":
    unittest.main()
