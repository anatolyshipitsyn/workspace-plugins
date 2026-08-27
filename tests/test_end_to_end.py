from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CREATOR_ROOT = ROOT / "plugins" / "agent-plugin-creator"
SCAFFOLD_SCRIPT = CREATOR_ROOT / "scripts" / "scaffold_plugin.py"
VALIDATE_SCRIPT = CREATOR_ROOT / "scripts" / "validate_plugin.py"
PLUGIN_SCHEMA_ID = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def run_command(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


class EndToEndTest(unittest.TestCase):
    maxDiff = None

    def test_scaffold_and_validate_codex_and_claude_plugin_offline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir)
            scaffold_result = run_command(
                "python3",
                str(SCAFFOLD_SCRIPT),
                "--destination",
                str(destination),
                "--name",
                "End To End Demo",
                "--description",
                "Offline integration test plugin",
                "--clients",
                "codex,claude",
                "--with-skill",
                "review-skill",
            )

            self.assertEqual(scaffold_result.returncode, 0, scaffold_result.stderr)
            self.assertEqual(scaffold_result.stdout, "")

            plugin_root = destination / "end-to-end-demo"
            manifest = json.loads((plugin_root / "plugin.json").read_text(encoding="utf-8"))
            claude_manifest = json.loads(
                (plugin_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
            )

            self.assertEqual(manifest["$schema"], PLUGIN_SCHEMA_ID)
            self.assertEqual(manifest["name"], "end-to-end-demo")
            self.assertTrue((plugin_root / "skills" / "review-skill" / "SKILL.md").is_file())
            self.assertFalse(
                (plugin_root / ".claude-plugin" / "skills" / "review-skill" / "SKILL.md").exists()
            )
            self.assertEqual(
                claude_manifest,
                {
                    "name": "end-to-end-demo",
                    "version": "0.1.0",
                    "description": "Offline integration test plugin",
                },
            )

            skill_path = plugin_root / "skills" / "review-skill" / "SKILL.md"
            skill_path.write_text(
                skill_path.read_text(encoding="utf-8").replace(
                    "Replace this placeholder with real instructions for `review-skill`.",
                    "Offline integration instructions.",
                ),
                encoding="utf-8",
            )

            validate_result = run_command("python3", str(VALIDATE_SCRIPT), str(plugin_root))
            isolated_validate_result = run_command(
                "python3",
                "-S",
                str(VALIDATE_SCRIPT),
                str(plugin_root),
            )

            self.assertEqual(validate_result.returncode, 0, validate_result.stdout + validate_result.stderr)
            self.assertEqual(validate_result.stdout, "")
            self.assertEqual(validate_result.stderr, "")
            self.assertEqual(
                isolated_validate_result.returncode,
                0,
                isolated_validate_result.stdout + isolated_validate_result.stderr,
            )
            self.assertEqual(isolated_validate_result.stdout, "")
            self.assertEqual(isolated_validate_result.stderr, "")


if __name__ == "__main__":
    unittest.main()
