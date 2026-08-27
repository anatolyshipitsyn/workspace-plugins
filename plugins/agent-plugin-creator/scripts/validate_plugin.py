from __future__ import annotations

import argparse
import ast
import datetime
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterable
from urllib.parse import urlparse


SCRIPT_PATH = Path(__file__).resolve()
CREATOR_PLUGIN_ROOT = SCRIPT_PATH.parents[1]
SPECS_ROOT = CREATOR_PLUGIN_ROOT / "specs"
REGISTRY_PATH = SPECS_ROOT / "registry.json"
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SKILL_NAME_MAX_LENGTH = 64
SKILL_DESCRIPTION_MAX_LENGTH = 1024
SKILL_COMPATIBILITY_MAX_LENGTH = 500
CLAUDE_PLUGIN_ROOT = "${CLAUDE_PLUGIN_ROOT}"
CLAUDE_PLUGIN_DATA = "${CLAUDE_PLUGIN_DATA}"
PORTABLE_PLUGIN_ROOT = "${PLUGIN_ROOT}"
PORTABLE_PLUGIN_DATA = "${PLUGIN_DATA}"
CLAUDE_MANIFEST_FIELD_TYPES = {
    "name": str,
    "version": str,
    "description": str,
}
SKILL_FRONTMATTER_KEYS = {
    "name",
    "description",
    "license",
    "compatibility",
    "allowed-tools",
    "metadata",
}
SECRET_PATTERNS = [
    re.compile(
        r"(?im)^[ \t]*(?:[a-z0-9_.-]+[_.-])?(?:api[_-]?key|secret|token|password|passwd|private[_-]?key|authorization)[ \t]*[:=][ \t]*['\"]?[^\s'\"]{6,}"
    ),
    re.compile(r"(?i)\bauthorization\b\s*[:=]\s*['\"]?(?:bearer|basic)\s+[^\s'\"]+"),
]
SECRET_NAME_PATTERN = re.compile(
    r"(?i)(?:^|[_.-])(?:api[_-]?key|secret|token|password|passwd|private[_-]?key|authorization)$"
)
HTTP_HEADER_NAME_PATTERN = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
ENVIRONMENT_PLACEHOLDER_PATTERN = re.compile(r"\$\{[^}]+\}")
YAML_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
YAML_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt ]\d{1,2}:\d{2}:\d{2}"
    r"(?:\.\d*)?(?:[ \t]*(?:Z|[-+]\d{1,2}(?::?\d{2})?))?$"
)
YAML_SEXAGESIMAL_PATTERN = re.compile(r"^[-+]?[0-9][0-9_]*(?::[0-9][0-9_]*)+$")
UNFINISHED_SKILL_PLACEHOLDER_PATTERN = re.compile(
    r"(?im)^\s*Replace this placeholder with real instructions for `[^`\r\n]+`\.\s*$"
)
NON_PYTHON_SECRET_DECLARATION_PATTERN = re.compile(
    r"(?im)^[ \t]*(?:export[ \t]+)?(?:(?:const|let|var)[ \t]+)?"
    r"([a-z_][a-z0-9_]*)[ \t]*=[ \t]*"
    r"(?:\"([^\"\n]*)\"|'([^'\n]*)'|([^\s;#]+))"
)


class ValidationFailure(Exception):
    pass


class Diagnostic:
    def __init__(self, path: str, rule: str, correction: str) -> None:
        self.path = path
        self.rule = rule
        self.correction = correction

    def render(self) -> str:
        return f"path={self.path} | rule={self.rule} | correction={self.correction}"


class PairTrackingDict(dict[str, Any]):
    def __init__(self, pairs: list[tuple[str, Any]]) -> None:
        super().__init__(pairs)
        self.pairs = list(pairs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("plugin_path")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_json_with_pairs(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=PairTrackingDict)


def path_label(package_root: Path, target: Path) -> str:
    try:
        return target.relative_to(package_root).as_posix()
    except ValueError:
        return str(target)


def add_diagnostic(
    diagnostics: list[Diagnostic],
    package_root: Path,
    target: Path,
    rule: str,
    correction: str,
) -> None:
    diagnostics.append(Diagnostic(path_label(package_root, target), rule, correction))


def load_registry_metadata() -> tuple[dict[str, Any], dict[str, dict[str, Any]], str]:
    registry = read_json(REGISTRY_PATH)
    latest_release = registry.get("latestRelease")
    supported_releases = registry.get("supportedReleases")
    draft_releases = registry.get("draftReleases")
    release_sources = registry.get("sources", {}).get("releases")

    if not isinstance(latest_release, str):
        raise ValidationFailure("Local registry is missing latestRelease.")
    if not isinstance(supported_releases, list):
        raise ValidationFailure("Local registry is missing supportedReleases.")
    if not isinstance(draft_releases, list):
        raise ValidationFailure("Local registry is missing draftReleases.")
    if not isinstance(release_sources, dict):
        raise ValidationFailure("Local registry is missing release source metadata.")

    if latest_release not in supported_releases:
        raise ValidationFailure("Local registry latestRelease is not supported.")
    if latest_release in draft_releases:
        raise ValidationFailure("Local registry latestRelease is a draft.")

    for release in supported_releases:
        release_dir = SPECS_ROOT / release
        if not (release_dir / "plugin.schema.json").is_file():
            raise ValidationFailure(f"Supported release {release!r} is missing plugin.schema.json.")
        if not (release_dir / "mcp.schema.json").is_file():
            raise ValidationFailure(f"Supported release {release!r} is missing mcp.schema.json.")

    normalized_sources: dict[str, dict[str, Any]] = {}
    for release in supported_releases:
        source = release_sources.get(release)
        if not isinstance(source, dict):
            raise ValidationFailure(f"Supported release {release!r} is missing source metadata.")
        plugin_schema_id = source.get("pluginSchemaId")
        mcp_schema_id = source.get("mcpSchemaId")
        if not isinstance(plugin_schema_id, str) or not isinstance(mcp_schema_id, str):
            raise ValidationFailure(f"Supported release {release!r} is missing canonical schema ids.")
        normalized_sources[release] = {
            "pluginSchemaId": plugin_schema_id,
            "mcpSchemaId": mcp_schema_id,
        }

    return registry, normalized_sources, latest_release


class StructuralSchemaValidator:
    def __init__(self, schema: dict[str, Any]) -> None:
        self.schema = schema

    def validate(self, instance: Any) -> list[str]:
        errors: list[str] = []
        self._validate(instance, self.schema, "$", errors)
        return errors

    def _resolve_ref(self, ref: str) -> dict[str, Any]:
        if not ref.startswith("#/"):
            raise ValidationFailure(f"Unsupported schema reference {ref!r}.")
        node: Any = self.schema
        for segment in ref[2:].split("/"):
            node = node[segment]
        if not isinstance(node, dict):
            raise ValidationFailure(f"Schema reference {ref!r} did not resolve to an object.")
        return node

    def _validate(self, instance: Any, schema: dict[str, Any], location: str, errors: list[str]) -> None:
        if "$ref" in schema:
            self._validate(instance, self._resolve_ref(schema["$ref"]), location, errors)
            return

        if "oneOf" in schema:
            matches = 0
            nested_failures: list[list[str]] = []
            for option in schema["oneOf"]:
                option_errors: list[str] = []
                self._validate(instance, option, location, option_errors)
                if option_errors:
                    nested_failures.append(option_errors)
                else:
                    matches += 1
            if matches != 1:
                errors.append(f"{location}: expected exactly one matching schema option")
            return

        if "const" in schema and instance != schema["const"]:
            errors.append(f"{location}: expected constant value {schema['const']!r}")

        if "enum" in schema and instance not in schema["enum"]:
            errors.append(f"{location}: expected one of {schema['enum']!r}")

        expected_type = schema.get("type")
        if expected_type is not None and not self._matches_type(instance, expected_type):
            errors.append(
                f"{location}: expected type {expected_type}, got {type(instance).__name__}"
            )
            return

        if "not" in schema:
            inner_errors: list[str] = []
            self._validate(instance, schema["not"], location, inner_errors)
            if not inner_errors:
                errors.append(f"{location}: value matched a forbidden schema")

        if isinstance(instance, str):
            min_length = schema.get("minLength")
            if isinstance(min_length, int) and len(instance) < min_length:
                errors.append(f"{location}: must be at least {min_length} characters long")
            max_length = schema.get("maxLength")
            if isinstance(max_length, int) and len(instance) > max_length:
                errors.append(f"{location}: must be at most {max_length} characters long")
            pattern = schema.get("pattern")
            if isinstance(pattern, str) and re.match(pattern, instance) is None:
                errors.append(f"{location}: must match pattern {pattern!r}")

        if isinstance(instance, list):
            items_schema = schema.get("items")
            if isinstance(items_schema, dict):
                for index, item in enumerate(instance):
                    self._validate(item, items_schema, f"{location}[{index}]", errors)

        if isinstance(instance, dict):
            property_names_schema = schema.get("propertyNames")
            if isinstance(property_names_schema, dict):
                for key in instance:
                    self._validate(key, property_names_schema, f"{location}.<key>", errors)

            properties = schema.get("properties", {})
            if isinstance(properties, dict):
                for required_key in schema.get("required", []):
                    if required_key not in instance:
                        errors.append(f"{location}: missing required property {required_key!r}")

                for key, value in instance.items():
                    if key in properties:
                        property_schema = properties[key]
                        if isinstance(property_schema, dict):
                            self._validate(value, property_schema, f"{location}.{key}", errors)
                        continue

                    additional = schema.get("additionalProperties", True)
                    if additional is False:
                        errors.append(f"{location}: unknown property {key!r}")
                    elif isinstance(additional, dict):
                        self._validate(value, additional, f"{location}.{key}", errors)

    @staticmethod
    def _matches_type(instance: Any, expected_type: str) -> bool:
        if expected_type == "object":
            return isinstance(instance, dict)
        if expected_type == "array":
            return isinstance(instance, list)
        if expected_type == "string":
            return isinstance(instance, str)
        if expected_type == "boolean":
            return isinstance(instance, bool)
        if expected_type == "number":
            return isinstance(instance, (int, float)) and not isinstance(instance, bool)
        if expected_type == "integer":
            return isinstance(instance, int) and not isinstance(instance, bool)
        if expected_type == "null":
            return instance is None
        return True


class SchemaValidator:
    def __init__(self, schema: dict[str, Any]) -> None:
        self.schema = schema
        self._validator = None
        try:
            from jsonschema import Draft202012Validator  # type: ignore
        except ImportError:
            self._fallback = StructuralSchemaValidator(schema)
        else:
            self._validator = Draft202012Validator(schema)
            self._fallback = None

    def validate(self, instance: Any) -> list[str]:
        if self._validator is not None:
            errors = []
            for error in self._validator.iter_errors(instance):
                location = "$"
                if error.path:
                    location += "." + ".".join(str(part) for part in error.path)
                errors.append(f"{location}: {error.message}")
            return errors
        if self._fallback is None:
            return []
        return self._fallback.validate(instance)


def extract_frontmatter_document(skill_path: Path) -> tuple[dict[str, Any], str] | None:
    content = skill_path.read_text(encoding="utf-8")
    if not content.startswith("---\n"):
        return None
    end_marker = content.find("\n---\n", 4)
    if end_marker == -1:
        return None
    frontmatter_text = content[4:end_marker]
    body = content[end_marker + 5 :]

    try:
        import yaml  # type: ignore
    except ImportError:
        frontmatter = parse_simple_frontmatter(frontmatter_text)
    else:
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as exc:
            raise ValidationFailure(f"YAML parser error: {exc}") from exc

    if not isinstance(frontmatter, dict):
        raise ValidationFailure("Skill frontmatter must decode to a mapping.")

    return frontmatter, body


def parse_simple_frontmatter(frontmatter_text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    lines = frontmatter_text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        index += 1
        if not stripped:
            continue
        if ":" not in stripped:
            raise ValidationFailure("Skill frontmatter contains a malformed line.")
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValidationFailure("Skill frontmatter contains an empty key.")
        if value in {"|", ">"}:
            nested, index = consume_indented_block(lines, index)
            parsed_value: Any = parse_simple_block_scalar(nested, value)
        elif value.startswith(("[", "{")):
            if value.startswith("[") and not value.endswith("]"):
                raise ValidationFailure("Skill frontmatter contains an unterminated flow sequence.")
            if value.startswith("{") and not value.endswith("}"):
                raise ValidationFailure("Skill frontmatter contains an unterminated flow mapping.")
            parsed_value = parse_simple_flow_value(value)
        elif not value:
            nested, index = consume_indented_block(lines, index)
            parsed_value = parse_simple_block_value(nested)
        else:
            parsed_value = parse_simple_scalar(value)
        result[key] = parsed_value
    return result


def consume_indented_block(lines: list[str], start_index: int) -> tuple[list[str], int]:
    nested: list[str] = []
    index = start_index
    while index < len(lines):
        line = lines[index]
        if line.startswith((" ", "\t")) or not line.strip():
            nested.append(line)
            index += 1
            continue
        break
    return nested, index


def split_simple_flow_items(value: str) -> list[str]:
    items: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    for index, character in enumerate(value):
        if quote:
            if character == quote and (index == 0 or value[index - 1] != "\\"):
                quote = None
        elif character in {"'", '"'}:
            quote = character
        elif character in "[{":
            depth += 1
        elif character in "]}":
            depth -= 1
        elif character == "," and depth == 0:
            items.append(value[start:index].strip())
            start = index + 1
    items.append(value[start:].strip())
    return [item for item in items if item]


def parse_simple_scalar(value: str) -> Any:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    lowered = value.lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    if lowered in {"null", "~"}:
        return None
    if re.fullmatch(r"[-+]?0b[0-1_]+", value, re.IGNORECASE):
        return int(value.replace("_", ""), 2)
    if re.fullmatch(r"[-+]?0x[0-9a-f_]+", value, re.IGNORECASE):
        return int(value.replace("_", ""), 16)
    if re.fullmatch(r"[-+]?0[0-7_]+", value):
        sign = -1 if value.startswith("-") else 1
        digits = value.lstrip("+-").replace("_", "")
        return sign * int(digits, 8)
    if re.fullmatch(r"[-+]?(?:0|[1-9][0-9_]+|[1-9][0-9]*)", value):
        return int(value.replace("_", ""))
    if YAML_DATE_PATTERN.fullmatch(value):
        return datetime.date.fromisoformat(value)
    if YAML_TIMESTAMP_PATTERN.fullmatch(value):
        timestamp = value.replace(" ", "T", 1).replace("Z", "+00:00")
        try:
            return datetime.datetime.fromisoformat(timestamp)
        except ValueError:
            pass
    if YAML_SEXAGESIMAL_PATTERN.fullmatch(value):
        sign = -1 if value.startswith("-") else 1
        components = value.lstrip("+-").split(":")
        total = 0
        for component in components:
            total = (total * 60) + int(component.replace("_", ""))
        return sign * total
    if lowered in {".inf", "+.inf", "-.inf", ".nan"}:
        return float(lowered.replace(".inf", "inf").replace(".nan", "nan"))
    if re.fullmatch(r"[-+]?(?:[0-9][0-9_]*)?\.[0-9_]*(?:[eE][-+]?[0-9]+)?", value) or re.fullmatch(
        r"[-+]?[0-9][0-9_]*\.[0-9_]*(?:[eE][-+]?[0-9]+)", value
    ):
        return float(value.replace("_", ""))
    return value


def parse_simple_flow_value(value: str) -> Any:
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [parse_simple_flow_value(item) if item[:1] in "[{" else parse_simple_scalar(item) for item in split_simple_flow_items(inner)]
    if value.startswith("{") and value.endswith("}"):
        inner = value[1:-1].strip()
        result: dict[Any, Any] = {}
        if not inner:
            return result
        for item in split_simple_flow_items(inner):
            if ":" not in item:
                raise ValidationFailure("Skill frontmatter contains a malformed flow mapping.")
            key, raw_item = item.split(":", 1)
            key = parse_simple_scalar(key)
            result[key] = parse_simple_flow_value(raw_item.strip()) if raw_item.strip()[:1] in "[{" else parse_simple_scalar(raw_item)
        return result
    return parse_simple_scalar(value)


def parse_simple_block_value(lines: list[str]) -> Any:
    meaningful = [line.strip() for line in lines if line.strip()]
    if not meaningful:
        return None
    if all(line.startswith("-") for line in meaningful):
        return [parse_simple_scalar(line[1:].strip()) for line in meaningful]
    if all(":" in line for line in meaningful):
        result: dict[Any, Any] = {}
        for line in meaningful:
            key, value = line.split(":", 1)
            result[parse_simple_scalar(key)] = parse_simple_scalar(value)
        return result
    raise ValidationFailure("Skill frontmatter contains an unsupported indented value.")


def parse_simple_block_scalar(lines: list[str], style: str) -> str:
    meaningful = [line for line in lines if line.strip()]
    if not meaningful:
        raise ValidationFailure("Skill frontmatter block scalar must contain an indented value.")

    indentation = min(
        len(line) - len(line.lstrip(" \t"))
        for line in meaningful
    )
    if indentation == 0:
        raise ValidationFailure("Skill frontmatter block scalar must contain an indented value.")

    normalized_lines: list[str] = []
    for line in lines:
        if line.strip():
            current_indentation = len(line) - len(line.lstrip(" \t"))
            if current_indentation < indentation:
                raise ValidationFailure("Skill frontmatter block scalar indentation is malformed.")
            normalized_lines.append(line[indentation:])
        else:
            normalized_lines.append("")

    if style == "|":
        return "\n".join(normalized_lines).strip("\n")
    return fold_simple_block_scalar(normalized_lines)


def fold_simple_block_scalar(lines: list[str]) -> str:
    folded: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            folded.append(" ".join(paragraph))
            paragraph.clear()

    for line in lines:
        if line == "":
            flush_paragraph()
            if folded and folded[-1] != "":
                folded.append("")
            continue
        paragraph.append(line)
    flush_paragraph()
    return "\n".join(folded).strip("\n")


def validate_skill_frontmatter(
    diagnostics: list[Diagnostic],
    package_root: Path,
    skill_dir: Path,
    seen_skill_names: dict[str, Path],
) -> None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        add_diagnostic(
            diagnostics,
            package_root,
            skill_dir,
            "Immediate skill directories must contain SKILL.md.",
            "Add a valid SKILL.md file to this skill directory or remove the directory.",
        )
        return

    try:
        document = extract_frontmatter_document(skill_md)
    except (ValidationFailure, UnicodeDecodeError) as exc:
        add_diagnostic(
            diagnostics,
            package_root,
            skill_md,
            f"Invalid skill frontmatter: {exc}",
            "Fix the YAML frontmatter so it is a valid mapping with required fields.",
        )
        return

    if document is None:
        add_diagnostic(
            diagnostics,
            package_root,
            skill_md,
            "Agent Skills files must start with YAML frontmatter.",
            "Add leading --- frontmatter with at least name and description.",
        )
        return

    frontmatter, body = document
    if UNFINISHED_SKILL_PLACEHOLDER_PATTERN.search(body):
        add_diagnostic(
            diagnostics,
            package_root,
            skill_md,
            "Skill body still contains unfinished scaffolder placeholder text.",
            "Replace the scaffold placeholder with the skill's real instructions.",
        )
    unexpected_keys = sorted(set(frontmatter) - SKILL_FRONTMATTER_KEYS)
    if unexpected_keys:
        add_diagnostic(
            diagnostics,
            package_root,
            skill_md,
            f"Unexpected skill frontmatter field(s): {', '.join(unexpected_keys)}.",
            "Remove unsupported frontmatter keys.",
        )

    name = frontmatter.get("name")
    description = frontmatter.get("description")

    if not isinstance(name, str) or not name.strip():
        add_diagnostic(
            diagnostics,
            package_root,
            skill_md,
            "Skill frontmatter must define a non-empty string name.",
            "Set name to the discovered skill directory name.",
        )
        return

    normalized_name = name.strip()
    if (
        len(normalized_name) > SKILL_NAME_MAX_LENGTH
        or SKILL_NAME_PATTERN.fullmatch(normalized_name) is None
    ):
        add_diagnostic(
            diagnostics,
            package_root,
            skill_md,
            "Skill names must be 1-64 characters of lowercase letters, digits, and single internal hyphens only.",
            "Rename the skill and frontmatter name to a valid hyphen-case identifier.",
        )

    if normalized_name != skill_dir.name:
        add_diagnostic(
            diagnostics,
            package_root,
            skill_md,
            "Immediate skill discovery uses directory names that must match frontmatter name.",
            "Rename the directory or the frontmatter name so they match exactly.",
        )

    if normalized_name in seen_skill_names:
        first_path = path_label(package_root, seen_skill_names[normalized_name] / "SKILL.md")
        add_diagnostic(
            diagnostics,
            package_root,
            skill_md,
            f"Duplicate discovered skill name {normalized_name!r}; first seen at {first_path}.",
            "Keep only one immediate skill directory for each discovered skill name.",
        )
    else:
        seen_skill_names[normalized_name] = skill_dir

    if not isinstance(description, str) or not description.strip():
        add_diagnostic(
            diagnostics,
            package_root,
            skill_md,
            "Skill frontmatter must define a non-empty string description.",
            "Add a concise description explaining when the skill applies.",
        )
    elif len(description) > SKILL_DESCRIPTION_MAX_LENGTH:
        add_diagnostic(
            diagnostics,
            package_root,
            skill_md,
            "Skill description must be between 1 and 1024 characters.",
            "Shorten the description so it stays within the current Agent Skills limit.",
        )

    compatibility = frontmatter.get("compatibility")
    if compatibility is not None:
        if not isinstance(compatibility, str) or not compatibility.strip():
            add_diagnostic(
                diagnostics,
                package_root,
                skill_md,
                "Skill compatibility must be a non-empty string when present.",
                "Set compatibility to a concise string or remove the field.",
            )
        elif len(compatibility) > SKILL_COMPATIBILITY_MAX_LENGTH:
            add_diagnostic(
                diagnostics,
                package_root,
                skill_md,
                "Skill compatibility must be between 1 and 500 characters when present.",
                "Shorten the compatibility note or remove the field.",
            )

    allowed_tools = frontmatter.get("allowed-tools")
    if allowed_tools is not None and (
        not isinstance(allowed_tools, str) or not allowed_tools.strip()
    ):
        add_diagnostic(
            diagnostics,
            package_root,
            skill_md,
            "Skill allowed-tools must be a non-empty space-separated string when present.",
            "Encode allowed-tools as a single string or remove the field.",
        )

    metadata = frontmatter.get("metadata")
    if metadata is not None and (
        not isinstance(metadata, dict)
        or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in metadata.items()
        )
    ):
        add_diagnostic(
            diagnostics,
            package_root,
            skill_md,
            "Skill metadata must be an optional map with string keys and values when present.",
            "Use a mapping whose keys and values are strings or remove the metadata field.",
        )


def validate_skills(diagnostics: list[Diagnostic], package_root: Path) -> None:
    skills_root = package_root / "skills"
    if not skills_root.exists():
        return
    if not skills_root.is_dir():
        add_diagnostic(
            diagnostics,
            package_root,
            skills_root,
            "skills must be a directory when present.",
            "Replace the file with a skills directory or remove it.",
        )
        return

    seen_skill_names: dict[str, Path] = {}
    for child in sorted(skills_root.iterdir(), key=lambda path: path.name):
        if child.name.startswith("."):
            continue
        if not child.is_dir():
            add_diagnostic(
                diagnostics,
                package_root,
                child,
                "Immediate children of skills/ must be skill directories.",
                "Move extra files out of skills/ or wrap them in a named skill directory.",
            )
            continue
        validate_skill_frontmatter(diagnostics, package_root, child, seen_skill_names)


def ensure_within_root(root_resolved: Path, target: Path) -> bool:
    try:
        target.relative_to(root_resolved)
    except ValueError:
        return False
    return True


def validate_package_containment(diagnostics: list[Diagnostic], package_root: Path) -> None:
    root_resolved = package_root.resolve()
    for current_root, dir_names, file_names in os.walk(package_root, topdown=True, followlinks=False):
        current_path = Path(current_root)
        for name in sorted(dir_names + file_names):
            candidate = current_path / name
            if candidate.is_symlink():
                resolved = candidate.resolve(strict=False)
                if not ensure_within_root(root_resolved, resolved):
                    add_diagnostic(
                        diagnostics,
                        package_root,
                        candidate,
                        "Package containment forbids symlinks that resolve outside the plugin root.",
                        "Replace the symlink with a real file or directory inside the plugin package.",
                    )


def normalize_mcp_placeholders(value: Any, placeholder_root: str, placeholder_data: str) -> Any:
    if isinstance(value, str):
        return value.replace(placeholder_root, PORTABLE_PLUGIN_ROOT).replace(
            placeholder_data, PORTABLE_PLUGIN_DATA
        )
    if isinstance(value, list):
        return [normalize_mcp_placeholders(item, placeholder_root, placeholder_data) for item in value]
    if isinstance(value, dict):
        return {
            key: normalize_mcp_placeholders(item, placeholder_root, placeholder_data)
            for key, item in value.items()
        }
    return value


def normalize_claude_http_aliases(value: Any) -> Any:
    if isinstance(value, list):
        return [normalize_claude_http_aliases(item) for item in value]
    if isinstance(value, dict):
        normalized = {
            key: normalize_claude_http_aliases(item) for key, item in value.items()
        }
        if normalized.get("type") == "http" and "url" in normalized:
            normalized["type"] = "streamable-http"
        return normalized
    return value


def validate_json_schema(
    diagnostics: list[Diagnostic],
    package_root: Path,
    target_path: Path,
    instance: Any,
    schema_path: Path,
) -> None:
    schema = read_json(schema_path)
    validator = SchemaValidator(schema)
    for error in validator.validate(instance):
        add_diagnostic(
            diagnostics,
            package_root,
            target_path,
            f"Schema validation failed: {error}",
            "Update the file so it matches the bundled local schema exactly.",
        )


def resolve_release_for_plugin_schema(
    plugin_schema_id: Any,
    normalized_sources: dict[str, dict[str, Any]],
    registry: dict[str, Any],
) -> tuple[str | None, str | None]:
    if not isinstance(plugin_schema_id, str):
        return None, "plugin.json must define a string $schema."
    for release, metadata in normalized_sources.items():
        if metadata["pluginSchemaId"] == plugin_schema_id:
            if release not in registry.get("supportedReleases", []):
                return None, f"Selected release {release!r} is not supported by the local registry."
            if release in registry.get("draftReleases", []):
                return None, f"Selected release {release!r} is a draft and must not be used."
            release_dir = SPECS_ROOT / release
            if not (release_dir / "plugin.schema.json").is_file() or not (
                release_dir / "mcp.schema.json"
            ).is_file():
                return None, f"Selected release {release!r} is missing bundled local schemas."
            return release, None
    return None, "plugin.json selects an unsupported schema id."


def validate_manifest_release(
    diagnostics: list[Diagnostic],
    package_root: Path,
    plugin_manifest: dict[str, Any],
    registry: dict[str, Any],
    normalized_sources: dict[str, dict[str, Any]],
) -> str | None:
    release, error = resolve_release_for_plugin_schema(
        plugin_manifest.get("$schema"), normalized_sources, registry
    )
    if error is not None:
        add_diagnostic(
            diagnostics,
            package_root,
            package_root / "plugin.json",
            error,
            "Set plugin.json $schema to the canonical schema id for a supported published release.",
        )
        return None
    return release


def resolve_plugin_relative_path(package_root: Path, raw_path: str) -> Path | None:
    if raw_path == PORTABLE_PLUGIN_ROOT:
        return package_root.resolve()
    if raw_path.startswith(f"{PORTABLE_PLUGIN_ROOT}/"):
        return (package_root / raw_path[len(PORTABLE_PLUGIN_ROOT) + 1 :]).resolve(strict=False)
    if raw_path.startswith("./"):
        return (package_root / raw_path[2:]).resolve(strict=False)
    if raw_path.startswith("${") or Path(raw_path).is_absolute():
        return None
    return (package_root / raw_path).resolve(strict=False)


def contains_dotdot_suffix(raw_path: str, prefix: str) -> bool:
    suffix = raw_path[len(prefix) :].lstrip("/")
    return ".." in Path(suffix).parts


def validate_stdio_command(
    diagnostics: list[Diagnostic],
    package_root: Path,
    target_path: Path,
    server_name: str,
    command: str,
    *,
    placeholder_root: str,
    placeholder_data: str,
) -> None:
    if command.startswith((placeholder_root, placeholder_data, CLAUDE_PLUGIN_ROOT, CLAUDE_PLUGIN_DATA)):
        add_diagnostic(
            diagnostics,
            package_root,
            target_path,
            f"mcp server {server_name!r} command must be bare or ./-relative and must not use placeholders.",
            "Use a bare executable name or a ./-relative path in command.",
        )
        return

    if Path(command).is_absolute():
        add_diagnostic(
            diagnostics,
            package_root,
            target_path,
            f"mcp server {server_name!r} command must not be an absolute path.",
            "Use a bare executable name or a ./-relative path in command.",
        )
        return

    if command.startswith("./"):
        resolved = resolve_plugin_relative_path(package_root, command)
        if resolved is None or not ensure_within_root(package_root.resolve(), resolved):
            add_diagnostic(
                diagnostics,
                package_root,
                target_path,
                f"mcp server {server_name!r} command escapes plugin-root containment.",
                "Keep the ./-relative command path inside the plugin package.",
            )
        return

    if "/" in command or "\\" in command:
        add_diagnostic(
            diagnostics,
            package_root,
            target_path,
            f"mcp server {server_name!r} command must be a bare executable or start with ./.",
            "Rewrite command as a bare executable name or a ./-relative path.",
        )


def is_loopback_hostname(hostname: str | None) -> bool:
    if hostname is None:
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def validate_stdio_server(
    diagnostics: list[Diagnostic],
    package_root: Path,
    target_path: Path,
    server_name: str,
    server_config: dict[str, Any],
    *,
    placeholder_root: str,
    placeholder_data: str,
) -> None:
    command = server_config.get("command")
    label_path = target_path
    if isinstance(command, str) and any(character.isspace() for character in command):
        add_diagnostic(
            diagnostics,
            package_root,
            label_path,
            f"mcp server {server_name!r} uses a multi-token stdio command.",
            "Put the executable in command and pass extra tokens through args.",
        )
    if isinstance(command, str):
        validate_stdio_command(
            diagnostics, package_root, target_path, server_name, command,
            placeholder_root=placeholder_root, placeholder_data=placeholder_data,
        )

    env = server_config.get("env")
    if isinstance(env, dict):
        for key in env:
            if key in {"PLUGIN_ROOT", "PLUGIN_DATA"}:
                add_diagnostic(
                    diagnostics,
                    package_root,
                    label_path,
                    f"mcp server {server_name!r} redefines reserved environment name {key}.",
                    "Remove reserved environment entries and use other variable names.",
                )

    cwd = server_config.get("cwd")
    if not isinstance(cwd, str):
        return

    accepted_prefixes = (f"{placeholder_root}/", placeholder_root, f"{placeholder_data}/", placeholder_data, "./")
    if not cwd.startswith(accepted_prefixes):
        add_diagnostic(
            diagnostics,
            package_root,
            label_path,
            f"mcp server {server_name!r} cwd must be plugin-relative or use the allowed placeholders.",
            "Use ./..., ${PLUGIN_ROOT}..., or ${PLUGIN_DATA}... according to the selected adapter.",
        )
        return

    if cwd.startswith(placeholder_data) and contains_dotdot_suffix(cwd, placeholder_data):
        add_diagnostic(
            diagnostics,
            package_root,
            label_path,
            f"mcp server {server_name!r} cwd must not traverse upward from the data directory placeholder.",
            "Remove .. segments from the cwd path.",
        )
        return

    resolved = resolve_plugin_relative_path(
        package_root,
        cwd.replace(placeholder_root, PORTABLE_PLUGIN_ROOT).replace(
            placeholder_data, PORTABLE_PLUGIN_DATA
        ),
    )
    if resolved is None:
        return
    if not ensure_within_root(package_root.resolve(), resolved):
        add_diagnostic(
            diagnostics,
            package_root,
            label_path,
            f"mcp server {server_name!r} cwd escapes plugin-root containment.",
            "Point cwd to a location inside the plugin package.",
        )


def validate_remote_server(
    diagnostics: list[Diagnostic],
    package_root: Path,
    target_path: Path,
    server_name: str,
    server_config: dict[str, Any],
) -> None:
    url = server_config.get("url")
    if not isinstance(url, str):
        return
    if "${" in url:
        add_diagnostic(
            diagnostics,
            package_root,
            target_path,
            f"mcp server {server_name!r} remote URLs must not contain path placeholders.",
            "Replace placeholders with a real HTTPS endpoint or switch to stdio transport.",
        )
        return

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        add_diagnostic(
            diagnostics,
            package_root,
            target_path,
            f"mcp server {server_name!r} remote transport must use a valid absolute HTTP or HTTPS URL.",
            "Set url to an absolute HTTP or HTTPS endpoint with a host name.",
        )
        return

    if parsed.fragment:
        add_diagnostic(
            diagnostics,
            package_root,
            target_path,
            f"mcp server {server_name!r} remote URL must not contain a fragment.",
            "Remove the fragment from the MCP endpoint URL.",
        )

    if parsed.scheme == "http" and not is_loopback_hostname(parsed.hostname):
        add_diagnostic(
            diagnostics,
            package_root,
            target_path,
            f"mcp server {server_name!r} remote HTTP URLs are limited to loopback hosts.",
            "Use HTTPS for non-loopback hosts or point HTTP at localhost or a loopback IP.",
        )
    if parsed.username or parsed.password:
        add_diagnostic(
            diagnostics,
            package_root,
            target_path,
            f"mcp server {server_name!r} remote URL must not embed credentials.",
            "Remove credentials from the URL and use a secure runtime auth mechanism instead.",
        )


def looks_like_secret_name(name: str) -> bool:
    return SECRET_NAME_PATTERN.search(name.strip().lower()) is not None


def is_valid_http_header_name(name: str) -> bool:
    return HTTP_HEADER_NAME_PATTERN.fullmatch(name) is not None


def is_valid_http_header_value(value: str) -> bool:
    return all(character == "\t" or (31 < ord(character) < 127) for character in value)


def contains_environment_placeholder(value: str) -> bool:
    return ENVIRONMENT_PLACEHOLDER_PATTERN.search(value) is not None


def validate_remote_headers(
    diagnostics: list[Diagnostic],
    package_root: Path,
    target_path: Path,
    server_name: str,
    raw_server_config: dict[str, Any] | None,
    normalized_server_config: dict[str, Any],
) -> None:
    headers = raw_server_config.get("headers") if isinstance(raw_server_config, dict) else None
    if not isinstance(headers, dict):
        headers = normalized_server_config.get("headers")
    if not isinstance(headers, dict):
        return

    pairs = headers.pairs if isinstance(headers, PairTrackingDict) else list(headers.items())
    seen_names: dict[str, str] = {}
    duplicate_reported = False
    for header_name, header_value in pairs:
        if not isinstance(header_name, str):
            continue
        normalized_name = header_name.lower()
        if normalized_name in seen_names and not duplicate_reported:
            add_diagnostic(
                diagnostics,
                package_root,
                target_path,
                f"mcp server {server_name!r} headers must not contain case-insensitive duplicate names.",
                "Remove duplicate header names so each header appears at most once.",
            )
            duplicate_reported = True
        else:
            seen_names[normalized_name] = header_name

        if not is_valid_http_header_name(header_name):
            add_diagnostic(
                diagnostics,
                package_root,
                target_path,
                f"mcp server {server_name!r} header names must be valid HTTP field names.",
                "Use visible token characters only in header names.",
            )

        if isinstance(header_value, str) and not is_valid_http_header_value(header_value):
            add_diagnostic(
                diagnostics,
                package_root,
                target_path,
                f"mcp server {server_name!r} header values must not contain HTTP control characters.",
                "Remove newlines or other control characters from header values.",
            )
        elif isinstance(header_value, str) and contains_environment_placeholder(header_value):
            add_diagnostic(
                diagnostics,
                package_root,
                target_path,
                f"mcp server {server_name!r} header values must not contain placeholder or environment expansion syntax.",
                "Move runtime header injection outside the committed manifest and keep header values literal.",
            )


def validate_mcp_file(
    diagnostics: list[Diagnostic],
    package_root: Path,
    release: str,
    normalized_sources: dict[str, dict[str, Any]],
    target_path: Path,
    *,
    placeholder_root: str,
    placeholder_data: str,
) -> None:
    try:
        raw_data = read_json_with_pairs(target_path)
    except (json.JSONDecodeError, OSError) as exc:
        add_diagnostic(
            diagnostics,
            package_root,
            target_path,
            f"Invalid JSON: {exc}",
            "Fix the JSON syntax.",
        )
        return

    if not isinstance(raw_data, dict):
        add_diagnostic(
            diagnostics,
            package_root,
            target_path,
            "mcp configuration must be a JSON object.",
            "Replace the file contents with a JSON object.",
        )
        return

    normalized_data = normalize_mcp_placeholders(raw_data, placeholder_root, placeholder_data)
    if placeholder_root == CLAUDE_PLUGIN_ROOT:
        normalized_data = normalize_claude_http_aliases(normalized_data)
    schema_path = SPECS_ROOT / release / "mcp.schema.json"
    validate_json_schema(diagnostics, package_root, target_path, normalized_data, schema_path)

    expected_schema = normalized_sources[release]["mcpSchemaId"]
    if raw_data.get("$schema") != expected_schema:
        add_diagnostic(
            diagnostics,
            package_root,
            target_path,
            "mcp schema selection must match the root plugin manifest release.",
            "Set mcp $schema to the canonical schema id for the selected release.",
        )

    mcp_servers = normalized_data.get("mcpServers")
    raw_mcp_servers = raw_data.get("mcpServers")
    if not isinstance(mcp_servers, dict):
        return

    for server_name, server_config in sorted(mcp_servers.items()):
        if not isinstance(server_name, str) or not isinstance(server_config, dict):
            continue
        raw_server_config = raw_mcp_servers.get(server_name) if isinstance(raw_mcp_servers, dict) else None
        transport = server_config.get("type")
        if transport == "stdio":
            validate_stdio_server(
                diagnostics,
                package_root,
                target_path,
                server_name,
                server_config,
                placeholder_root=PORTABLE_PLUGIN_ROOT,
                placeholder_data=PORTABLE_PLUGIN_DATA,
            )
        elif transport in {"streamable-http", "sse"}:
            validate_remote_server(diagnostics, package_root, target_path, server_name, server_config)
            validate_remote_headers(
                diagnostics,
                package_root,
                target_path,
                server_name,
                raw_server_config if isinstance(raw_server_config, dict) else None,
                server_config,
            )


def validate_claude_manifest(diagnostics: list[Diagnostic], package_root: Path, portable_manifest: dict[str, Any]) -> None:
    adapter_path = package_root / ".claude-plugin" / "plugin.json"
    if not adapter_path.exists():
        return

    try:
        adapter_manifest = read_json(adapter_path)
    except (json.JSONDecodeError, OSError) as exc:
        add_diagnostic(
            diagnostics,
            package_root,
            adapter_path,
            f"Invalid Claude adapter JSON: {exc}",
            "Fix the JSON syntax in the Claude adapter manifest.",
        )
        return

    if not isinstance(adapter_manifest, dict):
        add_diagnostic(
            diagnostics,
            package_root,
            adapter_path,
            "Claude adapter manifest must be a JSON object.",
            "Replace the file contents with a JSON object.",
        )
        return

    unsupported_fields = sorted(set(adapter_manifest) - set(CLAUDE_MANIFEST_FIELD_TYPES))
    if unsupported_fields:
        add_diagnostic(
            diagnostics,
            package_root,
            adapter_path,
            f"Claude adapter field(s) are unsupported: {', '.join(unsupported_fields)}.",
            "Keep the Claude adapter manifest limited to name, version, and description.",
        )

    for field, expected_type in CLAUDE_MANIFEST_FIELD_TYPES.items():
        if field in adapter_manifest and not isinstance(adapter_manifest[field], expected_type):
            add_diagnostic(
                diagnostics,
                package_root,
                adapter_path,
                f"Claude adapter field {field!r} must be a string when present.",
                f"Set {field} to a string value or remove it from the Claude adapter manifest.",
            )

    adapter_name = adapter_manifest.get("name")
    if not isinstance(adapter_name, str) or adapter_name != portable_manifest.get("name"):
        add_diagnostic(
            diagnostics,
            package_root,
            adapter_path,
            "Claude adapter name must match the portable plugin manifest name.",
            "Set .claude-plugin/plugin.json name to the same plugin name as plugin.json.",
        )

def iter_text_files(package_root: Path) -> Iterable[Path]:
    for current_root, dir_names, file_names in os.walk(package_root, topdown=True, followlinks=False):
        current_path = Path(current_root)
        dir_names[:] = sorted(dir_names)
        for file_name in sorted(file_names):
            yield current_path / file_name


def contains_structured_secret(value: Any, key_name: str | None = None) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and looks_like_secret_name(key) and isinstance(child, str):
                if is_obvious_secret_value(child):
                    return True
            if contains_structured_secret(child, key if isinstance(key, str) else None):
                return True
    elif isinstance(value, list):
        return any(contains_structured_secret(child, key_name) for child in value)
    return False


def contains_python_secret_material(content: str) -> bool:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return contains_python_text_secret_material(content)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and looks_like_secret_name(target.id):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        if is_obvious_secret_value(node.value.value):
                            return True
            if node.value is not None and contains_python_secret_dict_literal(node.value):
                return True
    return False


def contains_python_text_secret_material(content: str) -> bool:
    assignment_pattern = re.compile(
        r"(?im)^[ \t]*([a-z_][a-z0-9_]*)[ \t]*(?::[^\n=]+)?=[ \t]*"
        r"(?:\"([^\"\n]*)\"|'([^'\n]*)'|([^\s#]+))"
    )
    for match in assignment_pattern.finditer(content):
        if not looks_like_secret_name(match.group(1)):
            continue
        value = next(group for group in match.groups()[1:] if group is not None)
        if is_obvious_secret_value(value):
            return True
    return False


def contains_non_python_secret_material(content: str) -> bool:
    for match in NON_PYTHON_SECRET_DECLARATION_PATTERN.finditer(content):
        if not looks_like_secret_name(match.group(1)):
            continue
        value = next(group for group in match.groups()[1:] if group is not None)
        if is_obvious_secret_value(value):
            return True
    return False


def contains_python_secret_dict_literal(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Dict):
            continue
        for key, value in zip(child.keys, child.values):
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and looks_like_secret_name(key.value)
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
                and is_obvious_secret_value(value.value)
            ):
                return True
    return False


def is_obvious_secret_value(value: str) -> bool:
    normalized = value.strip().lower()
    return len(value.strip()) >= 6 and not normalized.startswith(
        ("${", "<", "your-", "replace-", "example")
    )


def validate_secret_material(diagnostics: list[Diagnostic], package_root: Path) -> None:
    for file_path in iter_text_files(package_root):
        if file_path.is_symlink():
            continue

        if file_path.name.startswith(".env"):
            add_diagnostic(
                diagnostics,
                package_root,
                file_path,
                "Committed .env files are not allowed in plugin packages.",
                "Remove the .env file and document required environment variables instead.",
            )
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        if file_path.suffix.lower() == ".py":
            has_secret = contains_python_secret_material(content)
        else:
            has_secret = contains_non_python_secret_material(content) or any(
                pattern.search(content) for pattern in SECRET_PATTERNS
            )
        if file_path.suffix.lower() == ".json":
            try:
                has_secret = has_secret or contains_structured_secret(json.loads(content))
            except json.JSONDecodeError:
                pass

        if has_secret:
            add_diagnostic(
                diagnostics,
                package_root,
                file_path,
                "Obvious secret material was detected in a committed file.",
                "Remove credentials, replace them with placeholders, and keep secret values out of the repository.",
            )


def validate_plugin(plugin_path: Path) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    package_root = plugin_path.expanduser()

    if not package_root.exists():
        return [
            Diagnostic(
                str(package_root),
                "The requested plugin path does not exist.",
                "Pass an existing plugin directory path to the validator.",
            )
        ]
    if not package_root.is_dir():
        return [
            Diagnostic(
                str(package_root),
                "The requested plugin path must be a directory.",
                "Pass the plugin root directory instead of a file.",
            )
        ]

    try:
        registry, normalized_sources, _latest_release = load_registry_metadata()
    except ValidationFailure as exc:
        return [
            Diagnostic(
                str(REGISTRY_PATH),
                str(exc),
                "Repair the local release registry before validating plugins.",
            )
        ]

    manifest_path = package_root / "plugin.json"
    if not manifest_path.is_file():
        add_diagnostic(
            diagnostics,
            package_root,
            manifest_path,
            "Portable plugin packages must contain plugin.json at the root.",
            "Add a root plugin.json manifest.",
        )
        return diagnostics

    try:
        plugin_manifest = read_json(manifest_path)
    except (json.JSONDecodeError, OSError) as exc:
        add_diagnostic(
            diagnostics,
            package_root,
            manifest_path,
            f"Invalid JSON: {exc}",
            "Fix the JSON syntax in plugin.json.",
        )
        return diagnostics

    if not isinstance(plugin_manifest, dict):
        add_diagnostic(
            diagnostics,
            package_root,
            manifest_path,
            "plugin.json must be a JSON object.",
            "Replace plugin.json with a JSON object.",
        )
        return diagnostics

    release = validate_manifest_release(diagnostics, package_root, plugin_manifest, registry, normalized_sources)
    if release is not None:
        validate_json_schema(
            diagnostics,
            package_root,
            manifest_path,
            plugin_manifest,
            SPECS_ROOT / release / "plugin.schema.json",
        )

    validate_skills(diagnostics, package_root)
    validate_package_containment(diagnostics, package_root)
    validate_secret_material(diagnostics, package_root)
    validate_claude_manifest(diagnostics, package_root, plugin_manifest)

    mcp_path = package_root / "mcp.json"
    if release is not None and mcp_path.exists():
        validate_mcp_file(
            diagnostics,
            package_root,
            release,
            normalized_sources,
            mcp_path,
            placeholder_root=PORTABLE_PLUGIN_ROOT,
            placeholder_data=PORTABLE_PLUGIN_DATA,
        )

    claude_mcp_path = package_root / ".mcp.json"
    if release is not None and claude_mcp_path.exists():
        validate_mcp_file(
            diagnostics,
            package_root,
            release,
            normalized_sources,
            claude_mcp_path,
            placeholder_root=CLAUDE_PLUGIN_ROOT,
            placeholder_data=CLAUDE_PLUGIN_DATA,
        )

    return diagnostics


def main() -> int:
    args = parse_args()
    diagnostics = validate_plugin(Path(args.plugin_path))
    for diagnostic in diagnostics:
        print(diagnostic.render())
    return 0 if not diagnostics else 1


if __name__ == "__main__":
    sys.exit(main())
