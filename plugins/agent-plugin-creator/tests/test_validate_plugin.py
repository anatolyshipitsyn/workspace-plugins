from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = ROOT / "plugins" / "agent-plugin-creator"
SCAFFOLD_SCRIPT = PLUGIN_ROOT / "scripts" / "scaffold_plugin.py"
VALIDATE_SCRIPT = PLUGIN_ROOT / "scripts" / "validate_plugin.py"
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
) -> subprocess.CompletedProcess[str]:
    command = [
        "python3",
        str(SCAFFOLD_SCRIPT),
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

    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )


def run_validate(plugin_path: Path, *, isolated: bool = False) -> subprocess.CompletedProcess[str]:
    python = ["python3", "-S"] if isolated else ["python3"]
    return subprocess.run(
        [*python, str(VALIDATE_SCRIPT), str(plugin_path)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class ValidatePluginTest(unittest.TestCase):
    maxDiff = None

    def scaffold_plugin(
        self,
        temp_dir: str,
        *,
        clients: list[str] | None = None,
        skills: list[str] | None = None,
        mcp_servers: list[dict[str, object]] | None = None,
    ) -> Path:
        destination = Path(temp_dir)
        result = run_scaffold(
            destination,
            "Demo Plugin",
            clients=clients or ["codex"],
            skills=skills or ["review-skill"],
            mcp_servers=mcp_servers,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return destination / "demo-plugin"

    def test_accepts_generated_portable_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_root = self.scaffold_plugin(temp_dir)

            result = run_validate(plugin_root)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stderr, "")

    def test_accepts_stdio_command_forms_and_treats_args_as_opaque(self) -> None:
        for command in ("python3", "./bin/server"):
            with self.subTest(command=command):
                with tempfile.TemporaryDirectory() as temp_dir:
                    plugin_root = self.scaffold_plugin(
                        temp_dir,
                        mcp_servers=[
                            {
                                "name": "demo",
                                "config": {
                                    "type": "stdio",
                                    "command": command,
                                    "args": [
                                        "../outside/script.py",
                                        "/tmp/outside-script.py",
                                        "${PLUGIN_ROOT}/config.json",
                                        "--path=../outside.cfg",
                                        "https://example.com/api",
                                    ],
                                    "cwd": "${PLUGIN_ROOT}",
                                },
                            }
                        ],
                    )

                    result = run_validate(plugin_root)

                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_accepts_generated_claude_http_adapter_from_streamable_http(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_root = self.scaffold_plugin(
                temp_dir,
                clients=["codex", "claude"],
                mcp_servers=[
                    {
                        "name": "demo",
                        "config": {
                            "type": "streamable-http",
                            "url": "https://example.com/mcp",
                            "headers": {
                                "X-Tenant": "public",
                            },
                        },
                    }
                ],
            )

            result = run_validate(plugin_root)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_invalid_claude_http_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_root = self.scaffold_plugin(
                temp_dir,
                clients=["codex", "claude"],
                mcp_servers=[
                    {
                        "name": "demo",
                        "config": {
                            "type": "streamable-http",
                            "url": "https://example.com/mcp",
                        },
                    }
                ],
            )

            claude_mcp_path = plugin_root / ".mcp.json"
            cases = [
                ("fragment", "https://example.com/mcp#fragment"),
                ("credentials", "https://user:password@example.com/mcp"),
                ("non-loopback-http", "http://example.com/mcp"),
            ]
            for label, url in cases:
                with self.subTest(label=label):
                    claude_mcp = read_json(claude_mcp_path)
                    mcp_servers = claude_mcp["mcpServers"]
                    assert isinstance(mcp_servers, dict)
                    demo = mcp_servers["demo"]
                    assert isinstance(demo, dict)
                    demo["url"] = url
                    write_json(claude_mcp_path, claude_mcp)

                    result = run_validate(plugin_root)

                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("demo", result.stdout)

    def test_accepts_creator_package_without_suppressing_real_secret_checks(self) -> None:
        result = run_validate(PLUGIN_ROOT)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_manifest_with_unknown_top_level_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_root = self.scaffold_plugin(temp_dir)
            manifest_path = plugin_root / "plugin.json"
            manifest = read_json(manifest_path)
            manifest["unexpected"] = True
            write_json(manifest_path, manifest)

            result = run_validate(plugin_root)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("plugin.json", result.stdout)
            self.assertIn("additional properties", result.stdout.lower())
            self.assertIn("correction", result.stdout.lower())

    def test_rejects_mismatched_or_unsupported_schema_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_root = self.scaffold_plugin(
                temp_dir,
                mcp_servers=[
                    {
                        "name": "demo",
                        "config": {
                            "type": "stdio",
                            "command": "python3",
                            "args": ["server.py"],
                            "cwd": "${PLUGIN_ROOT}",
                        },
                    }
                ],
            )

            cases = [
                (
                    "unsupported-plugin-schema",
                    plugin_root / "plugin.json",
                    {
                        "$schema": "https://agent-plugins.org/schemas/9.9.9/plugin.schema.json",
                        "name": "demo-plugin",
                    },
                    "supported",
                ),
                (
                    "mismatched-mcp-schema",
                    plugin_root / "mcp.json",
                    {
                        "$schema": PLUGIN_SCHEMA_ID,
                        "mcpServers": {
                            "demo": {
                                "type": "stdio",
                                "command": "python3",
                                "args": ["server.py"],
                                "cwd": "${PLUGIN_ROOT}",
                            }
                        },
                    },
                    "schema",
                ),
            ]

            for label, path, payload, needle in cases:
                with self.subTest(label=label):
                    original = path.read_text(encoding="utf-8")
                    try:
                        write_json(path, payload)
                        result = run_validate(plugin_root)
                    finally:
                        path.write_text(original, encoding="utf-8")

                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(path.name, result.stdout)
                    self.assertIn(needle, result.stdout.lower())

    def test_rejects_mcp_path_escape_and_reserved_environment_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_root = self.scaffold_plugin(
                temp_dir,
                mcp_servers=[
                    {
                        "name": "demo",
                        "config": {
                            "type": "stdio",
                            "command": "python3",
                            "args": ["server.py"],
                            "cwd": "${PLUGIN_ROOT}",
                        },
                    }
                ],
            )
            mcp_path = plugin_root / "mcp.json"
            write_json(
                mcp_path,
                {
                    "$schema": MCP_SCHEMA_ID,
                    "mcpServers": {
                        "demo": {
                            "type": "stdio",
                            "command": "python3",
                            "args": ["server.py"],
                            "cwd": "../outside",
                            "env": {
                                "PLUGIN_ROOT": "bad",
                            },
                        }
                    },
                },
            )

            result = run_validate(plugin_root)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("mcp.json", result.stdout)
            self.assertIn("reserved", result.stdout.lower())
            self.assertIn("cwd", result.stdout.lower())

    def test_rejects_plugin_root_placeholder_in_stdio_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_root = self.scaffold_plugin(
                temp_dir,
                mcp_servers=[
                    {
                        "name": "demo",
                        "config": {
                            "type": "stdio",
                            "command": "python3",
                            "args": ["--verbose", "server.py"],
                            "cwd": "${PLUGIN_ROOT}",
                        },
                    }
                ],
            )
            write_json(
                plugin_root / "mcp.json",
                {
                    "$schema": MCP_SCHEMA_ID,
                    "mcpServers": {
                        "demo": {
                            "type": "stdio",
                            "command": "${PLUGIN_ROOT}/bin/server",
                            "args": ["../outside/script.py", "/tmp/outside-script.py"],
                            "cwd": "${PLUGIN_ROOT}",
                        }
                    },
                },
            )

            result = run_validate(plugin_root)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("command", result.stdout.lower())
            self.assertNotIn("args[0]", result.stdout)

    def test_accepts_loopback_http_urls_and_rejects_fragments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_root = self.scaffold_plugin(
                temp_dir,
                mcp_servers=[
                    {
                        "name": "demo",
                        "config": {
                            "type": "streamable-http",
                            "url": "https://example.com/mcp",
                        },
                    }
                ],
            )

            mcp_path = plugin_root / "mcp.json"
            cases = [
                (
                    "loopback-http",
                    {
                        "$schema": MCP_SCHEMA_ID,
                        "mcpServers": {
                            "demo": {
                                "type": "streamable-http",
                                "url": "http://127.0.0.1:8787/mcp",
                            }
                        },
                    },
                    0,
                    None,
                ),
                (
                    "fragment-rejected",
                    {
                        "$schema": MCP_SCHEMA_ID,
                        "mcpServers": {
                            "demo": {
                                "type": "streamable-http",
                                "url": "https://example.com/mcp#fragment",
                            }
                        },
                    },
                    1,
                    "fragment",
                ),
            ]

            for label, payload, expected_code, needle in cases:
                with self.subTest(label=label):
                    write_json(mcp_path, payload)
                    result = run_validate(plugin_root)
                    self.assertEqual(
                        result.returncode,
                        expected_code,
                        result.stdout + result.stderr,
                    )
                    if needle is not None:
                        self.assertIn(needle, result.stdout.lower())

    def test_rejects_quoted_json_secret_values_without_echoing_them(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_root = self.scaffold_plugin(temp_dir)
            secret = "super-secret-value"
            write_json(
                plugin_root / "mcp.json",
                {
                    "$schema": MCP_SCHEMA_ID,
                    "mcpServers": {
                        "demo": {
                            "type": "streamable-http",
                            "url": "https://example.com/mcp",
                            "headers": {"OPENAI_API_KEY": secret},
                        }
                    },
                },
            )

            result = run_validate(plugin_root)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("secret", result.stdout.lower())
            self.assertNotIn(secret, result.stdout)

    def test_accepts_flow_frontmatter_without_yaml_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_root = self.scaffold_plugin(temp_dir)
            skill_md = plugin_root / "skills" / "review-skill" / "SKILL.md"
            skill_md.write_text(
                "---\n"
                "name: review-skill\n"
                "description: Review files\n"
                "allowed-tools: [Read, Write]\n"
                "metadata: {author: team, enabled: true}\n"
                "---\n\nInstructions.\n",
                encoding="utf-8",
            )

            result = run_validate(plugin_root, isolated=True)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_root = self.scaffold_plugin(temp_dir)
            outside_root = Path(temp_dir) / "outside"
            outside_root.mkdir()
            secret_path = outside_root / "secret.txt"
            secret_path.write_text("outside\n", encoding="utf-8")
            (plugin_root / "stolen.txt").symlink_to(secret_path)

            result = run_validate(plugin_root)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("stolen.txt", result.stdout)
            self.assertIn("containment", result.stdout.lower())

    def test_rejects_invalid_skill_frontmatter_or_duplicate_skill_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_root = self.scaffold_plugin(temp_dir)
            skills_root = plugin_root / "skills"

            invalid_skill = skills_root / "broken-skill"
            invalid_skill.mkdir()
            (invalid_skill / "SKILL.md").write_text(
                "name: broken-skill\n",
                encoding="utf-8",
            )

            result = run_validate(plugin_root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("broken-skill/SKILL.md", result.stdout)
            self.assertIn("frontmatter", result.stdout.lower())

            (invalid_skill / "SKILL.md").write_text(
                '---\nname: "review-skill"\ndescription: "Duplicate"\n---\n',
                encoding="utf-8",
            )

            result = run_validate(plugin_root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate", result.stdout.lower())

    def test_rejects_obvious_secret_material_and_dotenv_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_root = self.scaffold_plugin(temp_dir)
            (plugin_root / ".env").write_text("OPENAI_API_KEY=super-secret-value\n", encoding="utf-8")
            (plugin_root / "config.txt").write_text("db_password=super-secret-value\n", encoding="utf-8")
            (plugin_root / "settings.py").write_text(
                'OPENAI_API_KEY = "super-secret-value"\n', encoding="utf-8"
            )

            result = run_validate(plugin_root)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(".env", result.stdout)
            self.assertIn("secret", result.stdout.lower())
            self.assertNotIn("super-secret-value", result.stdout)

    def test_rejects_secret_in_syntax_invalid_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_root = self.scaffold_plugin(temp_dir)
            (plugin_root / "broken_settings.py").write_text(
                'OPENAI_API_KEY = "super-secret-value"\n'
                "def broken(:\n",
                encoding="utf-8",
            )

            result = run_validate(plugin_root)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("broken_settings.py", result.stdout)
            self.assertIn("secret", result.stdout.lower())
            self.assertNotIn("super-secret-value", result.stdout)

    def test_accepts_valid_optional_claude_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_root = self.scaffold_plugin(temp_dir, clients=["codex", "claude"])

            result = run_validate(plugin_root)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
