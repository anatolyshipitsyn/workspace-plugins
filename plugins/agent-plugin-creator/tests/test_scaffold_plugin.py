from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = ROOT / "plugins" / "agent-plugin-creator"
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "scaffold_plugin.py"
REGISTRY_PATH = PLUGIN_ROOT / "specs" / "registry.json"
PLUGIN_SCHEMA_ID = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA_ID = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"


def run_scaffold(
    destination: Path,
    name: str,
    *,
    description: str = "Test plugin description",
    clients: list[str],
    skills: list[str] | None = None,
    mcp_servers: list[dict[str, object]] | None = None,
    force: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        "python3",
        str(SCRIPT_PATH),
        "--destination",
        str(destination),
        "--name",
        name,
        "--description",
        description,
        "--clients",
        ",".join(clients),
    ]

    for skill in skills or []:
        command.extend(["--with-skill", skill])

    for server in mcp_servers or []:
        command.extend(["--with-mcp-server", json.dumps(server)])

    if force:
        command.append("--force")

    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )


class ScaffoldPluginTest(unittest.TestCase):
    maxDiff = None

    def test_creates_portable_plugin_and_shared_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir)
            result = run_scaffold(
                destination,
                "Demo Plugin",
                clients=["codex"],
                skills=["review-skill"],
            )

            self.assertEqual(result.returncode, 0, result.stderr)

            plugin_root = destination / "demo-plugin"
            manifest = json.loads((plugin_root / "plugin.json").read_text(encoding="utf-8"))

            self.assertEqual(
                manifest,
                {
                    "$schema": PLUGIN_SCHEMA_ID,
                    "name": "demo-plugin",
                    "version": "0.1.0",
                    "description": "Test plugin description",
                    "license": "MIT",
                    "keywords": ["agent-plugin"],
                },
            )

            skill_path = plugin_root / "skills" / "review-skill" / "SKILL.md"
            self.assertTrue(skill_path.is_file())
            skill_text = skill_path.read_text(encoding="utf-8")
            self.assertIn('name: "review-skill"', skill_text)
            self.assertIn("replace", skill_text.lower())
            self.assertFalse((plugin_root / ".claude-plugin" / "plugin.json").exists())
            self.assertFalse((plugin_root / "mcp.json").exists())
            self.assertEqual(result.stdout, "")

    def test_creates_claude_adapter_without_copying_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir)
            result = run_scaffold(
                destination,
                "demo-plugin",
                clients=["codex", "claude"],
                skills=["review-skill"],
            )

            self.assertEqual(result.returncode, 0, result.stderr)

            plugin_root = destination / "demo-plugin"
            claude_manifest = json.loads(
                (plugin_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
            )

            self.assertEqual(
                claude_manifest,
                {
                    "name": "demo-plugin",
                    "version": "0.1.0",
                    "description": "Test plugin description",
                },
            )
            self.assertTrue((plugin_root / "skills" / "review-skill" / "SKILL.md").is_file())
            self.assertFalse(
                (plugin_root / ".claude-plugin" / "skills" / "review-skill" / "SKILL.md").exists()
            )

    def test_creates_mcp_files_only_when_servers_requested(self) -> None:
        server_config = {
            "type": "stdio",
            "command": "python3",
            "args": ["server.py"],
            "cwd": "${PLUGIN_ROOT}",
            "env": {
                "PLUGIN_HOME": "${PLUGIN_DATA}",
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir)
            result = run_scaffold(
                destination,
                "demo-plugin",
                clients=["codex", "claude"],
                mcp_servers=[{"name": "demo", "config": server_config}],
            )

            self.assertEqual(result.returncode, 0, result.stderr)

            plugin_root = destination / "demo-plugin"
            portable_mcp = json.loads((plugin_root / "mcp.json").read_text(encoding="utf-8"))
            claude_mcp = json.loads((plugin_root / ".mcp.json").read_text(encoding="utf-8"))

            self.assertEqual(
                portable_mcp,
                {
                    "$schema": MCP_SCHEMA_ID,
                    "mcpServers": {
                        "demo": server_config,
                    },
                },
            )
            self.assertEqual(
                claude_mcp,
                {
                    "$schema": MCP_SCHEMA_ID,
                    "mcpServers": {
                        "demo": {
                            "type": "stdio",
                            "command": "python3",
                            "args": ["server.py"],
                            "cwd": "${CLAUDE_PLUGIN_ROOT}",
                            "env": {
                                "PLUGIN_HOME": "${CLAUDE_PLUGIN_DATA}",
                            },
                        },
                    },
                },
            )

            no_mcp_result = run_scaffold(
                destination,
                "no-mcp-plugin",
                clients=["codex", "claude"],
            )
            self.assertEqual(no_mcp_result.returncode, 0, no_mcp_result.stderr)
            no_mcp_root = destination / "no-mcp-plugin"
            self.assertFalse((no_mcp_root / "mcp.json").exists())
            self.assertFalse((no_mcp_root / ".mcp.json").exists())

    def test_converts_streamable_http_transport_for_claude_adapter(self) -> None:
        server_config = {
            "type": "streamable-http",
            "url": "https://example.com/mcp",
            "headers": {
                "X-Tenant": "public",
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir)
            result = run_scaffold(
                destination,
                "demo-plugin",
                clients=["codex", "claude"],
                mcp_servers=[{"name": "demo", "config": server_config}],
            )

            self.assertEqual(result.returncode, 0, result.stderr)

            plugin_root = destination / "demo-plugin"
            portable_mcp = json.loads((plugin_root / "mcp.json").read_text(encoding="utf-8"))
            claude_mcp = json.loads((plugin_root / ".mcp.json").read_text(encoding="utf-8"))

            self.assertEqual(
                portable_mcp,
                {
                    "$schema": MCP_SCHEMA_ID,
                    "mcpServers": {
                        "demo": server_config,
                    },
                },
            )
            self.assertEqual(
                claude_mcp,
                {
                    "$schema": MCP_SCHEMA_ID,
                    "mcpServers": {
                        "demo": {
                            "type": "http",
                            "url": "https://example.com/mcp",
                            "headers": {
                                "X-Tenant": "public",
                            },
                        },
                    },
                },
            )

    def test_refuses_existing_output_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir)
            first_result = run_scaffold(destination, "demo-plugin", clients=["codex"])
            second_result = run_scaffold(destination, "demo-plugin", clients=["codex"])

            self.assertEqual(first_result.returncode, 0, first_result.stderr)
            self.assertNotEqual(second_result.returncode, 0)
            self.assertIn("overwrite", second_result.stderr.lower())

    def test_rejects_unknown_or_draft_latest_release(self) -> None:
        original_registry = REGISTRY_PATH.read_text(encoding="utf-8")
        registry_data = json.loads(original_registry)

        cases = [
            ("draft", {**registry_data, "latestRelease": "1.1.0"}),
            ("unsupported", {**registry_data, "latestRelease": "9.9.9"}),
        ]

        try:
            for label, mutated_registry in cases:
                with self.subTest(label=label):
                    REGISTRY_PATH.write_text(
                        json.dumps(mutated_registry, indent=2) + "\n",
                        encoding="utf-8",
                    )

                    with tempfile.TemporaryDirectory() as temp_dir:
                        result = run_scaffold(Path(temp_dir), "demo-plugin", clients=["codex"])

                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("latest release", result.stderr.lower())
        finally:
            REGISTRY_PATH.write_text(original_registry, encoding="utf-8")

    def test_rejects_mcp_server_without_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_scaffold(
                Path(temp_dir),
                "demo-plugin",
                clients=["codex"],
                mcp_servers=[
                    {
                        "name": "demo",
                        "config": {
                            "command": "python3",
                            "args": ["server.py"],
                        },
                    }
                ],
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("type", result.stderr.lower())

    def test_rejects_symlink_destination_escape_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            requested_root = temp_root / "requested"
            outside_root = temp_root / "outside"
            requested_root.mkdir()
            outside_root.mkdir()
            (requested_root / "escape-link").symlink_to(outside_root, target_is_directory=True)

            result = run_scaffold(requested_root / "escape-link", "demo-plugin", clients=["codex"])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("destination", result.stderr.lower())
            self.assertFalse((outside_root / "demo-plugin").exists())
            self.assertFalse((requested_root / "demo-plugin").exists())

    def test_rejects_symlinked_ancestor_destination_escape_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            requested_root = temp_root / "requested"
            outside_root = temp_root / "outside"
            requested_root.mkdir()
            outside_root.mkdir()
            (requested_root / "link").symlink_to(outside_root, target_is_directory=True)

            destination = requested_root / "link" / "subdir"
            result = run_scaffold(destination, "demo-plugin", clients=["codex"])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("destination", result.stderr.lower())
            self.assertFalse((outside_root / "subdir").exists())
            self.assertFalse((outside_root / "demo-plugin").exists())
            self.assertFalse((requested_root / "demo-plugin").exists())

    def test_writes_deterministic_json_with_final_newline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir)
            result = run_scaffold(destination, "demo-plugin", clients=["codex"])

            self.assertEqual(result.returncode, 0, result.stderr)

            plugin_json_text = (destination / "demo-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
            self.assertEqual(
                plugin_json_text,
                "{\n"
                f'  "$schema": "{PLUGIN_SCHEMA_ID}",\n'
                '  "name": "demo-plugin",\n'
                '  "version": "0.1.0",\n'
                '  "description": "Test plugin description",\n'
                '  "license": "MIT",\n'
                '  "keywords": [\n'
                '    "agent-plugin"\n'
                "  ]\n"
                "}\n",
            )

    def test_force_overwrites_preexisting_files_inside_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir)
            plugin_root = destination / "demo-plugin"
            skill_path = plugin_root / "skills" / "review-skill" / "SKILL.md"

            first_result = run_scaffold(
                destination,
                "demo-plugin",
                clients=["codex"],
                skills=["review-skill"],
            )
            self.assertEqual(first_result.returncode, 0, first_result.stderr)

            (plugin_root / "plugin.json").write_text('{"stale": true}\n', encoding="utf-8")
            skill_path.write_text("stale\n", encoding="utf-8")

            forced_result = run_scaffold(
                destination,
                "demo-plugin",
                clients=["codex"],
                skills=["review-skill"],
                force=True,
            )
            self.assertEqual(forced_result.returncode, 0, forced_result.stderr)

            manifest = json.loads((plugin_root / "plugin.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["$schema"], PLUGIN_SCHEMA_ID)
            self.assertIn("Replace this placeholder", skill_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
