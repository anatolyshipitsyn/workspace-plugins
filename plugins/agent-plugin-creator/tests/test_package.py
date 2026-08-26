from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = ROOT / "plugins" / "agent-plugin-creator"
VALIDATE_SCRIPT = PLUGIN_ROOT / "scripts" / "validate_plugin.py"
REGISTRY_PATH = PLUGIN_ROOT / "specs" / "registry.json"
README_PATH = PLUGIN_ROOT / "README.md"
SKILL_PATH = PLUGIN_ROOT / "skills" / "create-agent-plugin" / "SKILL.md"


def run_validate(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(VALIDATE_SCRIPT), str(path)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )


class PackageMetadataTest(unittest.TestCase):
    maxDiff = None

    def test_creator_has_valid_portable_manifest(self) -> None:
        manifest = json.loads((PLUGIN_ROOT / "plugin.json").read_text(encoding="utf-8"))
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        latest = registry["latestRelease"]
        schema_id = registry["sources"]["releases"][latest]["pluginSchemaId"]

        self.assertEqual(manifest["$schema"], schema_id)
        self.assertEqual(manifest["name"], "agent-plugin-creator")
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertEqual(manifest["license"], "Apache-2.0")
        self.assertNotIn("extensions", manifest)

        result = run_validate(PLUGIN_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")

    def test_skill_routes_to_scripts_and_references(self) -> None:
        skill_text = SKILL_PATH.read_text(encoding="utf-8")

        self.assertIn("name: create-agent-plugin", skill_text)
        self.assertIn("scaffold_plugin.py", skill_text)
        self.assertIn("validate_plugin.py", skill_text)
        self.assertIn("explicit confirmation immediately before mutation", skill_text)
        self.assertIn("latest published release only", skill_text)
        self.assertIn("Do not add or rely on a `--spec-version` flag.", skill_text)
        self.assertIn("static validation does not prove MCP runtime behavior", skill_text)
        for reference in (
            "references/agent-plugins.md",
            "references/agent-skills.md",
            "references/codex.md",
            "references/claude-code.md",
            "references/licensing.md",
        ):
            self.assertIn(reference, skill_text)

    def test_claude_adapter_is_minimal_and_shared_skills_are_not_duplicated(self) -> None:
        adapter = json.loads(
            (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )

        self.assertEqual(
            adapter,
            {
                "name": "agent-plugin-creator",
                "version": "0.1.0",
                "description": "Claude Code adapter for the shared agent-plugin-creator package.",
            },
        )
        self.assertFalse((PLUGIN_ROOT / ".claude-plugin" / "skills").exists())
        self.assertFalse((PLUGIN_ROOT / ".claude-plugin" / "commands").exists())
        self.assertEqual(
            sorted(path.relative_to(PLUGIN_ROOT).as_posix() for path in PLUGIN_ROOT.glob("**/SKILL.md")),
            ["skills/create-agent-plugin/SKILL.md"],
        )

    def test_documentation_links_and_policy_are_present(self) -> None:
        readme = README_PATH.read_text(encoding="utf-8")
        changelog = (PLUGIN_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        license_text = (PLUGIN_ROOT / "LICENSE").read_text(encoding="utf-8")
        agent_plugins_ref = (
            PLUGIN_ROOT / "skills" / "create-agent-plugin" / "references" / "agent-plugins.md"
        ).read_text(encoding="utf-8")
        licensing_ref = (
            PLUGIN_ROOT / "skills" / "create-agent-plugin" / "references" / "licensing.md"
        ).read_text(encoding="utf-8")

        for needle in (
            "https://github.com/agentplugins/agent-plugins-spec",
            "https://raw.githubusercontent.com/agentplugins/agent-plugins-spec/main/spec/1.0.0.md",
            "https://raw.githubusercontent.com/agentplugins/agent-plugins-spec/main/spec/1.1.0.md",
            "Codex",
            "Claude Code",
            "Offline usage",
            "No-secret policy",
        ):
            self.assertIn(needle, readme)

        self.assertIn("latest published release: `1.0.0`", agent_plugins_ref)
        self.assertIn("known draft release tracked but not scaffolded: `1.1.0`", agent_plugins_ref)
        self.assertIn("CC-BY-4.0", licensing_ref)
        self.assertIn("Apache-2.0", licensing_ref)
        self.assertIn("0.1.0 - 2026-08-26", changelog)
        self.assertIn("Apache License", license_text)


if __name__ == "__main__":
    unittest.main()
