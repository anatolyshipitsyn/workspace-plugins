from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = ROOT / "plugins" / "github-pr-agent"
VALIDATE_SCRIPT = ROOT / "plugins" / "agent-plugin-creator" / "scripts" / "validate_plugin.py"
REGISTRY_PATH = ROOT / "plugins" / "agent-plugin-creator" / "specs" / "registry.json"
SKILL_NAMES = ("create-pr", "update-pr", "babysit-pr")


class PackageMetadataTest(unittest.TestCase):
    maxDiff = None

    def test_portable_manifest_targets_the_registry_release(self) -> None:
        manifest = json.loads((PLUGIN_ROOT / "plugin.json").read_text(encoding="utf-8"))
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        latest = registry["latestRelease"]

        self.assertEqual(
            manifest["$schema"], registry["sources"]["releases"][latest]["pluginSchemaId"]
        )
        self.assertEqual(manifest["name"], "github-pr-agent")
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertEqual(manifest["license"], "Apache-2.0")
        self.assertNotIn("extensions", manifest)

    def test_claude_adapter_holds_metadata_only(self) -> None:
        adapter = json.loads(
            (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(adapter), {"name", "version", "description"})
        self.assertEqual(adapter["name"], "github-pr-agent")
        self.assertFalse((PLUGIN_ROOT / ".claude-plugin" / "skills").exists())
        self.assertFalse((PLUGIN_ROOT / ".claude-plugin" / "scripts").exists())

    def test_shared_skills_exist_once_at_the_package_root(self) -> None:
        for name in SKILL_NAMES:
            with self.subTest(skill=name):
                skill = PLUGIN_ROOT / "skills" / name / "SKILL.md"
                self.assertTrue(skill.is_file())
                self.assertIn(f"name: {name}", skill.read_text(encoding="utf-8"))

        self.assertEqual(
            sorted(path.name for path in (PLUGIN_ROOT / "skills").iterdir() if path.is_dir()),
            sorted(SKILL_NAMES),
        )

    def test_babysit_skill_documents_the_token_frugal_defaults(self) -> None:
        skill_text = (PLUGIN_ROOT / "skills" / "babysit-pr" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("scripts/gh_pr_watch.py", skill_text)
        for flag in ("--all-checks", "--max-body", "--print-unchanged", "--retry-failed-now"):
            self.assertIn(flag, skill_text)
        self.assertIn("only when the state an agent would act on has changed", skill_text)
        self.assertIn("at most three retry cycles per SHA", skill_text)

    def test_package_validates_against_the_bundled_schemas(self) -> None:
        result = subprocess.run(
            ["python3", str(VALIDATE_SCRIPT), str(PLUGIN_ROOT)],
            capture_output=True,
            text=True,
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
