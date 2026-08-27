from __future__ import annotations

import importlib.util
import json
from pathlib import Path
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


class PackageContractTest(unittest.TestCase):
    maxDiff = None

    def test_package_has_portable_and_minimal_claude_manifests(self) -> None:
        self.assertEqual(validate_manifest(PORTABLE_MANIFEST), [])
        self.assertEqual(validate_manifest(CLAUDE_MANIFEST), [])
        self.assertFalse((PLUGIN_ROOT / ".claude-plugin" / "skills").exists())
        self.assertFalse((PLUGIN_ROOT / ".claude-plugin" / "scripts").exists())
        self.assertEqual(ANALYZER_SCRIPT.relative_to(PLUGIN_ROOT).as_posix(), "scripts/analyze_task_cost.py")

    def test_event_fixture_contains_only_normalized_aggregate_fields(self) -> None:
        event_path = FIXTURES / "events" / "claude-response.json"
        self.assertTrue(event_path.is_file(), "expected normalized event fixture")
        event = json.loads(event_path.read_text(encoding="utf-8"))

        self.assertEqual(
            set(event),
            {
                "client",
                "session_id_hash",
                "event",
                "timestamp",
                "model",
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "duration_ms",
            },
        )
        self.assertIn(event["event"], {"api_response", "compaction", "stop"})
        self.assertIsInstance(event["input_tokens"], int)
        self.assertIsInstance(event["output_tokens"], int)
        self.assertIsInstance(event["total_tokens"], int)
        self.assertIsInstance(event["duration_ms"], int)
        self.assertEqual(event["input_tokens"] + event["output_tokens"], event["total_tokens"])
        self.assertNotIn("prompt", event)
        self.assertNotIn("transcript", event)
        self.assertNotIn("raw_body", event)


if __name__ == "__main__":
    unittest.main()
