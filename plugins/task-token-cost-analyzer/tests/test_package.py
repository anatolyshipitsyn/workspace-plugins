from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import subprocess
import types
import unittest


ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = ROOT / "plugins" / "task-token-cost-analyzer"
PORTABLE_MANIFEST = PLUGIN_ROOT / "plugin.json"
CLAUDE_MANIFEST = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
FIXTURES = PLUGIN_ROOT / "tests" / "fixtures"
VALIDATOR_SCRIPT = ROOT / "plugins" / "agent-plugin-creator" / "scripts" / "validate_plugin.py"
REGISTRY_PATH = ROOT / "plugins" / "agent-plugin-creator" / "specs" / "registry.json"
ANALYZER_SCRIPT = PLUGIN_ROOT / "scripts" / "analyze_task_cost.py"
REQUIRED_REFERENCE_DOCS = (
    PLUGIN_ROOT / "skills" / "analyze-task-token-cost" / "references" / "acceptance-matrix.md",
    PLUGIN_ROOT / "skills" / "analyze-task-token-cost" / "references" / "cost-model.md",
    PLUGIN_ROOT / "skills" / "analyze-task-token-cost" / "references" / "client-guidance.md",
)
REQUIRED_TASK3_ARTIFACTS = (
    PLUGIN_ROOT / "skills" / "analyze-task-token-cost" / "SKILL.md",
    PLUGIN_ROOT / "templates" / "cost-report.md",
    PLUGIN_ROOT / "templates" / "plugin-update-prompt.md",
    PLUGIN_ROOT / "README.md",
    PLUGIN_ROOT / "CHANGELOG.md",
)
REQUIRED_MINIMAL_TASK_FIXTURES = (
    FIXTURES / "minimal-task" / "plan.md",
    FIXTURES / "minimal-task" / "progress.md",
    FIXTURES / "minimal-task" / "task-report.md",
)
EVENT_FIXTURES = (
    FIXTURES / "events" / "claude-response.json",
    FIXTURES / "events" / "codex-usage.json",
)
NORMALIZED_EVENT_FIELDS = {
    "client",
    "session_id_hash",
    "event",
    "timestamp",
    "model",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "duration_ms",
}
FORBIDDEN_RAW_FIELDS = {"prompt", "transcript", "raw_body"}
NETWORK_IMPORT_ROOTS = {
    "aiohttp",
    "ftplib",
    "http",
    "httpx",
    "paramiko",
    "requests",
    "socket",
    "telnetlib",
    "urllib",
    "websocket",
}
EDIT_COMMANDS = {
    ("git", "apply"),
    ("patch",),
    ("sed", "-i"),
    ("perl", "-i"),
    ("rm",),
    ("mv",),
    ("cp",),
    ("tee",),
    ("dd",),
    ("truncate",),
}


def load_validator_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("task_token_cost_validator", VALIDATOR_SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load validator from {VALIDATOR_SCRIPT}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_manifest(path: Path) -> list[str]:
    if not path.is_file():
        return [f"missing manifest: {path.relative_to(PLUGIN_ROOT).as_posix()}"]

    validator = load_validator_module()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    diagnostics: list[object] = []

    if path == PORTABLE_MANIFEST:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        latest = registry["latestRelease"]
        normalized_sources = {
            release: {
                "pluginSchemaId": release_data["pluginSchemaId"],
                "mcpSchemaId": release_data["mcpSchemaId"],
            }
            for release, release_data in registry["sources"]["releases"].items()
            if (
                isinstance(release_data, dict)
                and "pluginSchemaId" in release_data
                and "mcpSchemaId" in release_data
            )
        }
        validator.validate_manifest_release(
            diagnostics,
            PLUGIN_ROOT,
            manifest,
            registry,
            normalized_sources,
        )
        release = latest
        validator.validate_json_schema(
            diagnostics,
            PLUGIN_ROOT,
            path,
            manifest,
            validator.SPECS_ROOT / release / "plugin.schema.json",
        )
    else:
        validator.validate_claude_manifest(
            diagnostics,
            PLUGIN_ROOT,
            json.loads(PORTABLE_MANIFEST.read_text(encoding="utf-8")),
        )

    return [diagnostic.render() for diagnostic in diagnostics]


def run_validate(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(VALIDATOR_SCRIPT), str(path)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )


def dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else None
    return None


def literal_command(node: ast.AST) -> tuple[str, ...] | None:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    values: list[str] = []
    for element in node.elts:
        if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
            return None
        values.append(element.value)
    return tuple(values)


class PackageContractTest(unittest.TestCase):
    maxDiff = None

    def test_package_has_portable_and_minimal_claude_manifests(self) -> None:
        self.assertEqual(validate_manifest(PORTABLE_MANIFEST), [])
        self.assertEqual(validate_manifest(CLAUDE_MANIFEST), [])
        self.assertFalse((PLUGIN_ROOT / ".claude-plugin" / "skills").exists())
        self.assertFalse((PLUGIN_ROOT / ".claude-plugin" / "scripts").exists())
        self.assertEqual(ANALYZER_SCRIPT.relative_to(PLUGIN_ROOT).as_posix(), "scripts/analyze_task_cost.py")
        self.assertFalse((PLUGIN_ROOT / ".claude-plugin" / "hooks").exists())
        for path in (*REQUIRED_REFERENCE_DOCS, *REQUIRED_MINIMAL_TASK_FIXTURES):
            self.assertTrue(path.is_file(), f"expected prior-task artifact: {path.relative_to(PLUGIN_ROOT)}")
        for path in REQUIRED_TASK3_ARTIFACTS:
            self.assertTrue(path.is_file(), f"expected Task 3 artifact: {path.relative_to(PLUGIN_ROOT)}")

    def test_event_fixture_contains_only_normalized_aggregate_fields(self) -> None:
        for event_path in EVENT_FIXTURES:
            self.assert_normalized_aggregate_event(event_path)

    def test_package_passes_shared_validator_and_omits_optional_mcp_files(self) -> None:
        result = run_validate(PLUGIN_ROOT)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")
        self.assertFalse((PLUGIN_ROOT / "mcp.json").exists())
        self.assertFalse((PLUGIN_ROOT / ".mcp.json").exists())

    def test_package_tree_stays_local_and_read_only(self) -> None:
        script_text = ANALYZER_SCRIPT.read_text(encoding="utf-8")
        help_result = subprocess.run(
            ["python3", str(ANALYZER_SCRIPT), "--help"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            check=False,
        )

        self.assertEqual(help_result.returncode, 0, help_result.stdout + help_result.stderr)
        self.assertIn("--root", help_result.stdout)
        self.assertIn("--events", help_result.stdout)
        self.assertIn("--report-out", help_result.stdout)
        self.assertIn("--prompt-out", help_result.stdout)
        self.assertNotIn("--spec-version", help_result.stdout)
        self.assertNotIn("requests", script_text)
        self.assertNotIn("urllib.request", script_text)
        self.assertNotIn("http.client", script_text)
        self.assertIn("Do not install hooks", script_text)
        self.assertNotIn("git apply", script_text.lower())
        self.assertNotIn("os.system", script_text)
        self.assertFalse(any(path.is_symlink() for path in PLUGIN_ROOT.rglob("*")))
        self.assertFalse(any(path.name == ".env" for path in PLUGIN_ROOT.rglob("*")))

    def test_package_python_has_no_network_imports_or_automatic_edit_invocations(self) -> None:
        network_imports: list[str] = []
        automatic_edits: list[str] = []

        for path in PLUGIN_ROOT.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            relative_path = path.relative_to(PLUGIN_ROOT).as_posix()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".", maxsplit=1)[0] in NETWORK_IMPORT_ROOTS:
                            network_imports.append(f"{relative_path}: import {alias.name}")
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.split(".", maxsplit=1)[0] in NETWORK_IMPORT_ROOTS:
                        network_imports.append(f"{relative_path}: from {node.module}")
                if not isinstance(node, ast.Call):
                    continue
                call_name = dotted_name(node.func)
                if call_name in {"os.system", "os.popen"}:
                    automatic_edits.append(f"{relative_path}: {call_name}")
                    continue
                if call_name not in {
                    "subprocess.run",
                    "subprocess.call",
                    "subprocess.check_call",
                    "subprocess.check_output",
                    "subprocess.Popen",
                } or not node.args:
                    continue
                command = literal_command(node.args[0])
                if command and any(command[: len(prefix)] == prefix for prefix in EDIT_COMMANDS):
                    automatic_edits.append(f"{relative_path}: {' '.join(command)}")

        self.assertEqual(network_imports, [])
        self.assertEqual(automatic_edits, [])

    def assert_normalized_aggregate_event(self, event_path: Path) -> None:
        self.assertTrue(event_path.is_file(), "expected normalized event fixture")
        event = json.loads(event_path.read_text(encoding="utf-8"))

        self.assertEqual(set(event), NORMALIZED_EVENT_FIELDS)
        self.assertIn(event["event"], {"api_response", "compaction", "stop"})
        self.assertIsInstance(event["input_tokens"], int)
        self.assertIsInstance(event["output_tokens"], int)
        self.assertIsInstance(event["total_tokens"], int)
        self.assertIsInstance(event["duration_ms"], int)
        self.assertEqual(event["input_tokens"] + event["output_tokens"], event["total_tokens"])
        for field in FORBIDDEN_RAW_FIELDS:
            self.assertNotIn(field, event)


if __name__ == "__main__":
    unittest.main()
