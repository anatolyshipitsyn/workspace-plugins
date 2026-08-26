from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
PLUGIN_ROOT = SCRIPT_PATH.parents[1]
SPECS_ROOT = PLUGIN_ROOT / "specs"
REGISTRY_PATH = SPECS_ROOT / "registry.json"
CLAUDE_PLUGIN_DATA = "${CLAUDE_PLUGIN_DATA}"
CLAUDE_PLUGIN_ROOT = "${CLAUDE_PLUGIN_ROOT}"


class ScaffoldError(Exception):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--clients", required=True)
    parser.add_argument("--with-skill", action="append", default=[])
    parser.add_argument("--with-mcp-server", action="append", default=[])
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_name(raw_name: str) -> str:
    lowered = raw_name.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    if not normalized:
        raise ScaffoldError("Plugin name is empty after normalization.")
    return normalized


def load_release_metadata() -> tuple[str, str, str]:
    registry = read_json(REGISTRY_PATH)
    latest_release = registry.get("latestRelease")
    supported_releases = registry.get("supportedReleases", [])
    draft_releases = registry.get("draftReleases", [])
    release_sources = registry.get("sources", {}).get("releases", {})

    if not isinstance(latest_release, str):
        raise ScaffoldError("Latest release is missing from the local registry.")
    if latest_release not in supported_releases:
        raise ScaffoldError(
            f"Latest release {latest_release!r} is not supported by the local registry."
        )
    if latest_release in draft_releases:
        raise ScaffoldError(
            f"Latest release {latest_release!r} is a draft and cannot be scaffolded."
        )

    release_dir = SPECS_ROOT / latest_release
    plugin_schema_path = release_dir / "plugin.schema.json"
    mcp_schema_path = release_dir / "mcp.schema.json"
    if not plugin_schema_path.is_file() or not mcp_schema_path.is_file():
        raise ScaffoldError(
            f"Latest release {latest_release!r} is missing local schema files."
        )

    release_source = release_sources.get(latest_release)
    if not isinstance(release_source, dict):
        raise ScaffoldError(
            f"Latest release {latest_release!r} is missing source metadata in the local registry."
        )

    plugin_schema_url = release_source.get("pluginSchemaId")
    mcp_schema_url = release_source.get("mcpSchemaId")
    if not isinstance(plugin_schema_url, str) or not isinstance(mcp_schema_url, str):
        raise ScaffoldError(
            f"Latest release {latest_release!r} is missing canonical schema URLs."
        )

    return latest_release, plugin_schema_url, mcp_schema_url


def load_name_pattern(release: str) -> re.Pattern[str]:
    schema = read_json(SPECS_ROOT / release / "plugin.schema.json")
    pattern = schema.get("properties", {}).get("name", {}).get("pattern")
    if not isinstance(pattern, str):
        raise ScaffoldError(f"Release {release!r} does not define a name pattern.")
    return re.compile(pattern)


def parse_clients(raw_clients: str) -> list[str]:
    clients: list[str] = []
    seen: set[str] = set()
    for part in raw_clients.split(","):
        client = part.strip().lower()
        if not client:
            continue
        if client not in {"codex", "claude"}:
            raise ScaffoldError(f"Unsupported client {client!r}.")
        if client not in seen:
            clients.append(client)
            seen.add(client)
    if not clients:
        raise ScaffoldError("At least one client must be selected.")
    return clients


def parse_skill_names(raw_skills: list[str]) -> list[str]:
    skills: list[str] = []
    seen: set[str] = set()
    for raw_skill in raw_skills:
        skill_name = normalize_name(raw_skill)
        if skill_name not in seen:
            skills.append(skill_name)
            seen.add(skill_name)
    return skills


def parse_mcp_servers(raw_servers: list[str]) -> dict[str, dict[str, Any]]:
    servers: dict[str, dict[str, Any]] = {}
    for raw_server in raw_servers:
        try:
            payload = json.loads(raw_server)
        except json.JSONDecodeError as exc:
            raise ScaffoldError(f"Invalid MCP server JSON: {exc.msg}.") from exc
        if not isinstance(payload, dict):
            raise ScaffoldError("Each MCP server payload must be a JSON object.")

        name = payload.get("name")
        config = payload.get("config")
        if not isinstance(name, str) or not name.strip():
            raise ScaffoldError("Each MCP server payload must include a non-empty name.")
        if not isinstance(config, dict):
            raise ScaffoldError(
                f"MCP server {name!r} must include a JSON object in the config field."
            )
        if "type" not in config:
            raise ScaffoldError(f"MCP server {name!r} must include a type field.")

        servers[name] = dict(config)
    return servers


def ensure_destination(destination: Path) -> Path:
    resolved_destination = destination.resolve()
    if resolved_destination.exists():
        if not resolved_destination.is_dir():
            raise ScaffoldError("Destination must be an existing directory or a new directory path.")
    else:
        resolved_destination.mkdir(parents=True, exist_ok=True)
    return resolved_destination


def validate_output_path(destination: Path, plugin_name: str) -> Path:
    output_path = (destination / plugin_name).resolve()
    try:
        output_path.relative_to(destination)
    except ValueError as exc:
        raise ScaffoldError("Resolved output path escapes the destination directory.") from exc
    return output_path


def translate_for_claude(value: Any) -> Any:
    if isinstance(value, str):
        return (
            value.replace("${PLUGIN_ROOT}", CLAUDE_PLUGIN_ROOT)
            .replace("${PLUGIN_DATA}", CLAUDE_PLUGIN_DATA)
        )
    if isinstance(value, list):
        return [translate_for_claude(item) for item in value]
    if isinstance(value, dict):
        return {key: translate_for_claude(item) for key, item in value.items()}
    return value


def render_json(path: Path, data: dict[str, Any], *, force: bool, plugin_root: Path) -> None:
    resolved_path = path.resolve(strict=False)
    try:
        resolved_path.relative_to(plugin_root)
    except ValueError as exc:
        raise ScaffoldError("Refusing to write outside the generated plugin directory.") from exc

    if path.exists() and path.is_dir():
        raise ScaffoldError(f"Refusing to overwrite directory {path}.")

    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if force else "x"
    with path.open(mode, encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def render_text(path: Path, content: str, *, force: bool, plugin_root: Path) -> None:
    resolved_path = path.resolve(strict=False)
    try:
        resolved_path.relative_to(plugin_root)
    except ValueError as exc:
        raise ScaffoldError("Refusing to write outside the generated plugin directory.") from exc

    if path.exists() and path.is_dir():
        raise ScaffoldError(f"Refusing to overwrite directory {path}.")

    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if force else "x"
    with path.open(mode, encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def build_skill_placeholder(skill_name: str) -> str:
    return "\n".join(
        [
            "---",
            f'name: "{skill_name}"',
            f'description: "Instructions for {skill_name}"',
            "---",
            "",
            f"Replace this placeholder with real instructions for `{skill_name}`.",
            "",
        ]
    )


def scaffold_plugin(
    destination: Path,
    name: str,
    description: str,
    clients: list[str],
    skills: list[str],
    mcp_servers: dict[str, dict[str, Any]],
    *,
    force: bool,
) -> Path:
    latest_release, plugin_schema_url, mcp_schema_url = load_release_metadata()
    name_pattern = load_name_pattern(latest_release)
    normalized_name = normalize_name(name)
    if not name_pattern.fullmatch(normalized_name):
        raise ScaffoldError(
            f"Normalized plugin name {normalized_name!r} does not satisfy the latest release constraints."
        )

    destination_root = ensure_destination(destination)
    plugin_root = validate_output_path(destination_root, normalized_name)
    if plugin_root.exists() and not force:
        raise ScaffoldError(f"Refusing to overwrite existing output directory {plugin_root}.")
    plugin_root.mkdir(parents=True, exist_ok=True)

    render_json(
        plugin_root / "plugin.json",
        {
            "$schema": plugin_schema_url,
            "name": normalized_name,
            "version": "0.1.0",
            "description": description,
            "license": "MIT",
            "keywords": ["agent-plugin"],
        },
        force=force,
        plugin_root=plugin_root,
    )

    for skill_name in skills:
        render_text(
            plugin_root / "skills" / skill_name / "SKILL.md",
            build_skill_placeholder(skill_name),
            force=force,
            plugin_root=plugin_root,
        )

    if "claude" in clients:
        render_json(
            plugin_root / ".claude-plugin" / "plugin.json",
            {
                "name": normalized_name,
                "version": "0.1.0",
                "description": description,
            },
            force=force,
            plugin_root=plugin_root,
        )

    if mcp_servers:
        portable_mcp = {
            "$schema": mcp_schema_url,
            "mcpServers": mcp_servers,
        }
        render_json(
            plugin_root / "mcp.json",
            portable_mcp,
            force=force,
            plugin_root=plugin_root,
        )
        if "claude" in clients:
            render_json(
                plugin_root / ".mcp.json",
                translate_for_claude(portable_mcp),
                force=force,
                plugin_root=plugin_root,
            )

    return plugin_root


def main() -> int:
    args = parse_args()
    try:
        clients = parse_clients(args.clients)
        skills = parse_skill_names(args.with_skill)
        mcp_servers = parse_mcp_servers(args.with_mcp_server)
        scaffold_plugin(
            Path(args.destination),
            args.name,
            args.description,
            clients,
            skills,
            mcp_servers,
            force=args.force,
        )
    except (ScaffoldError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
