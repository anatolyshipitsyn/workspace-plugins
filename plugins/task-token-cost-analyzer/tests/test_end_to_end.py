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

    def test_skill_routes_to_cli_and_documents_pressure_guardrails(self) -> None:
        for path in (SKILL_PATH, README_PATH, CHANGELOG_PATH):
            self.assertTrue(path.is_file(), f"missing Task 3 artifact: {path.relative_to(PLUGIN_ROOT)}")

        skill = SKILL_PATH.read_text(encoding="utf-8")
        readme = README_PATH.read_text(encoding="utf-8")
        changelog = CHANGELOG_PATH.read_text(encoding="utf-8")

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

        for hook_event in ("SessionStart", "UserPromptSubmit", "PostToolUse", "SubagentStop", "Stop"):
            self.assertIn(hook_event, readme)
        self.assertIn("optional", readme.lower())
        self.assertIn("Compliance API", readme)
        self.assertIn("client/account dependent", readme)
        self.assertIn("tool counts", readme.lower())
        self.assertIn("durations", readme.lower())
        self.assertIn("not automatic llm token counts", readme.lower())
        self.assertIn("do not install hooks", readme.lower())

        self.assertIn("0.1.0", changelog)
        self.assertIn("update prompt", changelog.lower())


if __name__ == "__main__":
    unittest.main()
