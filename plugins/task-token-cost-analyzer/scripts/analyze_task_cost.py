#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys


NORMALIZED_EVENT_FIELDS = (
    "client",
    "session_id_hash",
    "event",
    "timestamp",
    "model",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "duration_ms",
)
FORBIDDEN_EVENT_FIELDS = {
    "prompt",
    "transcript",
    "raw_body",
    "raw-body",
    "request_body",
    "response_body",
    "headers",
    "authorization",
    "api_key",
    "secret",
    "token",
    "password",
}
IGNORED_EXPORT_FIELDS = {
    "prompt",
    "transcript",
    "raw_body",
    "raw-body",
    "request_body",
    "response_body",
    "headers",
}
ALLOWED_CLIENTS = {"claude", "codex"}
EVENT_CLASSES = {"api_response", "compaction", "stop"}
TEXT_SUFFIXES = {".json", ".jsonl", ".md", ".txt", ".yaml", ".yml"}
SECRET_PATTERNS = (
    re.compile(r"(?i)\b(authorization\s*:\s*bearer\s+)([^\s]+)"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password|passwd)\b(\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"\b(sk|ghp|gho|ghu|xoxb|xoxp)-[A-Za-z0-9._-]+\b"),
)
SECRET_KEY_PATTERN = re.compile(r"(?i)(^token$|access[_-]?token|auth[_-]?token|api[_-]?key|secret|password|passwd|authorization)")
SCRIPT_PATH = Path(__file__).resolve()
PLUGIN_ROOT = SCRIPT_PATH.parents[1]
REPORT_TEMPLATE_PATH = PLUGIN_ROOT / "templates" / "cost-report.md"
PROMPT_TEMPLATE_PATH = PLUGIN_ROOT / "templates" / "plugin-update-prompt.md"


@dataclass(frozen=True)
class EvidenceFile:
    relative_path: str
    byte_count: int
    line_count: int
    evidence_class: str

    def to_dict(self) -> dict[str, object]:
        return {
            "relative_path": self.relative_path,
            "byte_count": self.byte_count,
            "line_count": self.line_count,
            "evidence_class": self.evidence_class,
        }


@dataclass(frozen=True)
class EvidenceInventory:
    root: str
    files: list[EvidenceFile]

    @property
    def total_bytes(self) -> int:
        return sum(item.byte_count for item in self.files)

    @property
    def total_lines(self) -> int:
        return sum(item.line_count for item in self.files)

    def to_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "files": [item.to_dict() for item in self.files],
            "total_bytes": self.total_bytes,
            "total_lines": self.total_lines,
        }


@dataclass(frozen=True)
class AnalysisResult:
    root: str
    evidence: dict[str, str]
    measured: dict[str, object]
    derived: dict[str, object]
    estimated: dict[str, object]
    missing: dict[str, object]
    inventory: EvidenceInventory

    def to_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "evidence": dict(self.evidence),
            "measured": dict(self.measured),
            "derived": dict(self.derived),
            "estimated": dict(self.estimated),
            "missing": dict(self.missing),
            "inventory": self.inventory.to_dict(),
        }


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def resolve_root(root: Path) -> Path:
    resolved = root.expanduser().resolve()
    if not resolved.exists():
        raise ValueError(f"Root path does not exist: {root}")
    if not resolved.is_dir():
        raise ValueError(f"Root path is not a directory: {root}")
    return resolved


def resolve_within(root: Path, path: Path) -> Path:
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.expanduser().resolve()
    if not is_relative_to(resolved, root):
        raise ValueError(f"Path is outside the requested root: {path}")
    return resolved


def classify_evidence(path: Path) -> str:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if "event" in path.parts or suffix in {".json", ".jsonl"} and "usage" in name:
        return "telemetry"
    if "review" in name:
        return "review"
    if "plan" in name:
        return "plan"
    if "progress" in name:
        return "progress"
    if "report" in name:
        return "report"
    if suffix in {".json", ".jsonl"}:
        return "telemetry"
    return "artifact"


def count_lines(data: bytes) -> int:
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def redact_text(value: str) -> str:
    redacted = value
    redacted = SECRET_PATTERNS[0].sub(r"\1redacted", redacted)
    redacted = SECRET_PATTERNS[1].sub(r"\1\2redacted", redacted)
    redacted = SECRET_PATTERNS[2].sub("redacted", redacted)
    return redacted


def collect_evidence(root: Path) -> EvidenceInventory:
    resolved_root = resolve_root(root)
    files: list[EvidenceFile] = []
    for path in sorted(resolved_root.rglob("*"), key=lambda item: item.relative_to(resolved_root).as_posix()):
        if not path.is_file():
            continue
        resolved = resolve_within(resolved_root, path)
        data = resolved.read_bytes()
        files.append(
            EvidenceFile(
                relative_path=resolved.relative_to(resolved_root).as_posix(),
                byte_count=len(data),
                line_count=count_lines(data),
                evidence_class=classify_evidence(resolved.relative_to(resolved_root)),
            )
        )
    return EvidenceInventory(root=str(resolved_root), files=files)


def load_events(path: Path) -> list[dict[str, object]]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"Event path is not a file: {path}")

    text = resolved.read_text(encoding="utf-8")
    raw_events = parse_event_payload(text)
    events = [normalize_event_record(item) for item in raw_events]
    return events


def parse_event_payload(text: str) -> list[object]:
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            raise ValueError("Event data is empty")
        payload: list[object] = []
        for line in lines:
            try:
                payload.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError("Malformed event data") from exc
        return payload

    if isinstance(decoded, list):
        return decoded
    if isinstance(decoded, dict):
        return [decoded]
    raise ValueError("Event data must be a JSON object, array, or JSON Lines file")


def normalize_event(record: object) -> dict[str, object]:
    if not isinstance(record, dict):
        raise ValueError("Event records must be JSON objects")

    raw_record = dict(record)
    extras = set(raw_record) - set(NORMALIZED_EVENT_FIELDS)
    forbidden = {field for field in extras if field.lower() in FORBIDDEN_EVENT_FIELDS}
    if forbidden:
        raise ValueError(f"Event data contains forbidden raw fields: {', '.join(sorted(forbidden))}")
    if extras:
        raise ValueError(f"Event data contains unsupported fields: {', '.join(sorted(extras))}")

    normalized: dict[str, object] = {}
    for field in NORMALIZED_EVENT_FIELDS:
        if field not in raw_record:
            raise ValueError(f"Event record is missing required field: {field}")
        normalized[field] = raw_record[field]

    client = normalized["client"]
    if not isinstance(client, str) or client not in ALLOWED_CLIENTS:
        raise ValueError("Event record has an unsupported client")

    event = normalized["event"]
    if not isinstance(event, str) or event not in EVENT_CLASSES:
        raise ValueError("Event record has an unsupported event class")

    for field in ("session_id_hash", "timestamp", "model"):
        value = normalized[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Event record has an invalid {field}")

    for field in ("input_tokens", "output_tokens", "total_tokens", "duration_ms"):
        value = normalized[field]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"Event record has a non-numeric {field}")
        if value < 0:
            raise ValueError(f"Event record has a negative {field}")

    if normalized["input_tokens"] + normalized["output_tokens"] != normalized["total_tokens"]:
        raise ValueError("Event record has inconsistent token totals")

    return normalized


def normalize_event_record(record: object) -> dict[str, object]:
    if not isinstance(record, dict):
        raise ValueError("Event records must be JSON objects")

    mapped = map_supported_event(record)
    if mapped is not None:
        return normalize_event(mapped)

    return normalize_event(record)


def map_supported_event(record: dict[str, object]) -> dict[str, object] | None:
    if set(NORMALIZED_EVENT_FIELDS).issubset(record):
        return None

    mapped = map_claude_hook_event(record)
    if mapped is not None:
        return mapped

    mapped = map_claude_otel_event(record)
    if mapped is not None:
        return mapped

    mapped = map_codex_export_event(record)
    if mapped is not None:
        return mapped

    return None


def map_claude_hook_event(record: dict[str, object]) -> dict[str, object] | None:
    if "hook_event_name" not in record or "usage" not in record or "session_id" not in record:
        return None

    ensure_no_secret_fields(record)
    usage = require_mapping(record.get("usage"), "Claude hook usage")

    input_tokens = read_int(usage, "input_tokens")
    output_tokens = read_int(usage, "output_tokens")
    total_tokens = read_total_tokens(usage, input_tokens, output_tokens)

    return {
        "client": "claude",
        "session_id_hash": read_str(record, "session_id"),
        "event": normalize_export_event(record.get("hook_event_name")),
        "timestamp": read_str(record, "timestamp"),
        "model": read_model_name(record.get("model")),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "duration_ms": read_optional_int(record, "duration_ms", default=0),
    }


def map_claude_otel_event(record: dict[str, object]) -> dict[str, object] | None:
    attributes = record.get("attributes")
    if not isinstance(attributes, dict) or "gen_ai.usage.input_tokens" not in attributes:
        return None

    ensure_no_secret_fields(record)

    input_tokens = read_int(attributes, "gen_ai.usage.input_tokens")
    output_tokens = read_int(attributes, "gen_ai.usage.output_tokens")
    total_tokens = read_total_tokens(attributes, input_tokens, output_tokens, "gen_ai.usage.total_tokens")

    return {
        "client": "claude",
        "session_id_hash": read_str(attributes, "session.id"),
        "event": normalize_export_event(
            attributes.get("event.name") if "event.name" in attributes else record.get("name")
        ),
        "timestamp": read_str(record, "timestamp"),
        "model": read_model_name(
            attributes.get("gen_ai.response.model")
            if "gen_ai.response.model" in attributes
            else record.get("model")
        ),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "duration_ms": read_optional_int(
            attributes,
            "gen_ai.latency.ms",
            default=read_optional_int(record, "duration_ms", default=0),
        ),
    }


def map_codex_export_event(record: dict[str, object]) -> dict[str, object] | None:
    if "usage" not in record or "event_type" not in record or "session_id" not in record:
        return None

    ensure_no_secret_fields(record)
    usage = require_mapping(record.get("usage"), "Codex usage")

    input_tokens = read_first_int(usage, ("prompt_tokens", "input_tokens"))
    output_tokens = read_first_int(usage, ("completion_tokens", "output_tokens"))
    total_tokens = read_total_tokens(usage, input_tokens, output_tokens)

    timestamp_source = "created_at" if "created_at" in record else "timestamp"
    model_source = "model_slug" if "model_slug" in record else "model"

    return {
        "client": "codex",
        "session_id_hash": read_str(record, "session_id"),
        "event": normalize_export_event(record.get("event_type")),
        "timestamp": read_str(record, timestamp_source),
        "model": read_model_name(record.get(model_source)),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "duration_ms": read_optional_int(record, "duration_ms", default=0),
    }


def require_mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def read_str(record: dict[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Event record has an invalid {field}")
    return value


def read_model_name(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, dict):
        for field in ("display_name", "name", "id"):
            nested = value.get(field)
            if isinstance(nested, str) and nested.strip():
                return nested
    raise ValueError("Event record has an invalid model")


def read_int(record: dict[str, object], field: str) -> int:
    if field not in record:
        raise ValueError(f"Event record is missing required field: {field}")
    value = record[field]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Event record has a non-numeric {field}")
    if value < 0:
        raise ValueError(f"Event record has a negative {field}")
    return value


def read_optional_int(record: dict[str, object], field: str, default: int) -> int:
    if field not in record:
        return default
    return read_int(record, field)


def read_first_int(record: dict[str, object], fields: tuple[str, ...]) -> int:
    for field in fields:
        if field in record:
            return read_int(record, field)
    raise ValueError(f"Event record is missing required field: {fields[0]}")


def read_total_tokens(
    record: dict[str, object],
    input_tokens: int,
    output_tokens: int,
    field: str = "total_tokens",
) -> int:
    if field not in record:
        return input_tokens + output_tokens

    total_tokens = read_int(record, field)
    if input_tokens + output_tokens != total_tokens:
        raise ValueError("Event record has inconsistent token totals")
    return total_tokens


def normalize_export_event(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Event record has an unsupported event class")

    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    event_map = {
        "api_response": "api_response",
        "apiresponse": "api_response",
        "response_completed": "api_response",
        "posttooluse": "api_response",
        "post_tool_use": "api_response",
        "compaction": "compaction",
        "subagentstop": "compaction",
        "subagent_stop": "compaction",
        "stop": "stop",
        "session_stop": "stop",
    }
    if normalized not in event_map:
        raise ValueError("Event record has an unsupported event class")
    return event_map[normalized]


def ensure_no_secret_fields(record: object, parent_key: str | None = None) -> None:
    if isinstance(record, dict):
        for key, value in record.items():
            key_name = str(key)
            lowered = key_name.lower()
            if lowered in IGNORED_EXPORT_FIELDS:
                continue
            if SECRET_KEY_PATTERN.search(lowered):
                raise ValueError(f"Event data contains forbidden raw fields: {key_name}")
            ensure_no_secret_fields(value, key_name)
        return

    if isinstance(record, list):
        for item in record:
            ensure_no_secret_fields(item, parent_key)


def count_by_class(files: list[EvidenceFile], evidence_class: str) -> int:
    return sum(1 for item in files if item.evidence_class == evidence_class)


def duplicate_class_count(files: list[EvidenceFile], classes: tuple[str, ...]) -> int:
    duplicates = 0
    for evidence_class in classes:
        count = count_by_class(files, evidence_class)
        if count > 1:
            duplicates += count - 1
    return duplicates


def estimate_tokens_from_bytes(byte_count: int) -> int:
    if byte_count <= 0:
        return 0
    return max(1, round(byte_count / 4))


def collect_secret_observations(root: Path) -> list[dict[str, object]]:
    observations: list[dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if not path.is_file():
            continue
        resolved = resolve_within(root, path)
        if resolved.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = resolved.read_text(encoding="utf-8", errors="replace")
        for index, line in enumerate(text.splitlines(), start=1):
            sanitized = redact_text(line)
            if sanitized != line:
                observations.append(
                    {
                        "relative_path": resolved.relative_to(root).as_posix(),
                        "line": index,
                        "status": "redacted",
                    }
                )
    return observations


def analyze_task(root: Path, events: Path | None = None) -> AnalysisResult:
    resolved_root = resolve_root(root)
    inventory = collect_evidence(resolved_root)
    secret_observations = collect_secret_observations(resolved_root)

    measured: dict[str, object] = {}
    derived: dict[str, object] = {
        "artifact_bytes": inventory.total_bytes,
        "artifact_lines": inventory.total_lines,
        "evidence_file_count": len(inventory.files),
        "task_file_count": sum(
            1 for item in inventory.files if item.evidence_class in {"artifact", "plan", "progress", "report"}
        ),
        "review_file_count": count_by_class(inventory.files, "review"),
        "repeated_context_files": duplicate_class_count(
            inventory.files, ("plan", "progress", "report", "review")
        ),
        "verbose_log_files": sum(
            1
            for item in inventory.files
            if item.line_count >= 200 or item.relative_path.endswith((".log", ".jsonl"))
        ),
        "secret_redaction_hits": len(secret_observations),
    }
    estimated: dict[str, object] = {}
    missing: dict[str, object] = {}
    evidence = {
        "token_counts": "missing",
        "artifact_sizes": "derived" if inventory.files else "missing",
        "durations": "missing",
        "secret_scrubbing": "derived" if secret_observations else "missing",
    }

    if events is not None:
        event_path = resolve_within(resolved_root, events)
        normalized_events = load_events(event_path)
        measured = {
            "event_count": len(normalized_events),
            "input_tokens": sum(int(item["input_tokens"]) for item in normalized_events),
            "output_tokens": sum(int(item["output_tokens"]) for item in normalized_events),
            "total_tokens": sum(int(item["total_tokens"]) for item in normalized_events),
            "duration_ms": sum(int(item["duration_ms"]) for item in normalized_events),
            "clients": sorted({str(item["client"]) for item in normalized_events}),
            "models": sorted({str(item["model"]) for item in normalized_events}),
        }
        evidence["token_counts"] = "measured"
        evidence["durations"] = "measured"
        derived["available_duration_ms"] = measured["duration_ms"]
    else:
        estimated_tokens = estimate_tokens_from_bytes(inventory.total_bytes)
        if estimated_tokens:
            estimated = {
                "approx_total_tokens": estimated_tokens,
                "basis": "artifact-size proxy at 4 bytes per token",
                "confidence": "low",
            }
            evidence["token_counts"] = "estimated"
            missing["measured_events"] = "No normalized event file was provided."
        else:
            missing["token_counts"] = "No normalized event file or artifact proxy is available."
        missing["durations"] = "No measured duration telemetry was provided."

    if derived["review_file_count"] == 0:
        missing["review_artifacts"] = "No review evidence observed."
    if secret_observations:
        derived["secret_observations"] = secret_observations

    return AnalysisResult(
        root=str(resolved_root),
        evidence=evidence,
        measured=measured,
        derived=derived,
        estimated=estimated,
        missing=missing,
        inventory=inventory,
    )


def format_inline_list(values: list[object]) -> str:
    normalized = [str(value) for value in values if str(value).strip()]
    return ", ".join(normalized) if normalized else "none observed"


def format_bullets(lines: list[str]) -> str:
    if not lines:
        return "- none"
    return "\n".join(f"- {line}" for line in lines)


def format_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    divider = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(
        ["| " + " | ".join(headers) + " |", divider, *body]
    )


def build_scope_section(result: AnalysisResult) -> str:
    return format_bullets(
        [
            f"Selected root: `{result.root}`",
            f"Evidence files: {len(result.inventory.files)}",
            f"Token evidence quality: `{result.evidence['token_counts']}`",
            f"Duration evidence quality: `{result.evidence['durations']}`",
        ]
    )


def build_evidence_section(result: AnalysisResult) -> str:
    measured = result.measured
    derived = result.derived
    estimated = result.estimated
    missing = result.missing
    lines = [
        f"Measured clients: {format_inline_list(measured.get('clients', []))}",
        f"Measured models: {format_inline_list(measured.get('models', []))}",
        f"Artifact bytes: {derived['artifact_bytes']}",
        f"Artifact lines: {derived['artifact_lines']}",
        f"Repeated context files: {derived['repeated_context_files']}",
        f"Verbose log files: {derived['verbose_log_files']}",
    ]
    if estimated:
        lines.append(
            f"Estimated tokens: {estimated['approx_total_tokens']} ({estimated['confidence']} confidence; {estimated['basis']})"
        )
    if missing:
        lines.append(f"Missing evidence keys: {format_inline_list(sorted(missing))}")
    return format_bullets(lines)


def build_acceptance_matrix(result: AnalysisResult) -> str:
    measured_clients = {str(client) for client in result.measured.get("clients", [])}
    inventory_paths = [item.relative_path.lower() for item in result.inventory.files]
    has_yaml = any(path.endswith((".yaml", ".yml")) for path in inventory_paths)
    rows = [
        (
            "Codex",
            "pass" if "codex" in measured_clients else "not observed",
            "Measured Codex usage export observed." if "codex" in measured_clients else "No Codex telemetry in scope.",
        ),
        (
            "Claude",
            "pass" if "claude" in measured_clients else "not observed",
            "Measured Claude usage export observed." if "claude" in measured_clients else "No Claude telemetry in scope.",
        ),
        (
            "MCP",
            "not observed",
            "Use only tool counts and durations; automatic LLM token counts are not available from MCP alone.",
        ),
        (
            "YAML",
            "pass" if has_yaml else "not observed",
            "YAML evidence is present in scope." if has_yaml else "No YAML artifacts were selected for analysis.",
        ),
        (
            "Security",
            "pass",
            "Outputs keep aggregate-only measurements, redact secret-like values, and exclude raw prompts or transcripts.",
        ),
    ]
    return format_table(("Area", "Status", "Evidence"), rows)


def build_cost_breakdown(result: AnalysisResult) -> str:
    measured_total = str(result.measured.get("total_tokens", "not measured"))
    estimated_total = str(result.estimated.get("approx_total_tokens", "n/a"))
    derived = result.derived
    rows = [
        ("Measured tokens", measured_total, result.evidence["token_counts"]),
        ("Estimated tokens", estimated_total, result.evidence["token_counts"]),
        ("Evidence files", str(derived["evidence_file_count"]), "derived"),
        ("Review artifacts", str(derived["review_file_count"]), "derived"),
        ("Duration ms", str(result.measured.get("duration_ms", "not measured")), result.evidence["durations"]),
    ]
    return format_table(("Category", "Value", "Source"), rows)


def build_avoidable_costs(result: AnalysisResult) -> str:
    derived = result.derived
    items = [
        f"Repeated context artifacts observed: {derived['repeated_context_files']}",
        f"Verbose log artifacts observed: {derived['verbose_log_files']}",
        f"Secret redaction observations: {derived['secret_redaction_hits']}",
    ]
    if result.evidence["token_counts"] != "measured":
        items.append("Measured token telemetry is missing, so recommendations must avoid pretending estimates are exact.")
    return format_bullets(items)


def build_recommendations(result: AnalysisResult) -> str:
    items = [
        "Run a local adversarial audit before the first independent review and before making recommendations.",
        "Give any reviewer or subagent task-only context: the current task brief, required interfaces, and referenced artifact paths, never the complete conversation history.",
        "Batch validator fixes when multiple findings share the same validation surface so one fix round closes the full cluster.",
        "Generate the update prompt for user review and do not apply automatically.",
    ]
    if result.evidence["token_counts"] != "measured":
        items.append("Normalize a local Claude or Codex event export if you need measured token totals.")
    if int(result.derived.get("verbose_log_files", 0)) > 0:
        items.append("Keep focused test commands concise and save verbose reruns to a temporary log only after a failure.")
    return format_bullets(items)


def build_limitations(result: AnalysisResult) -> str:
    items = [
        "The analyzer reports aggregate local evidence only; it does not read remote services or send events over the network.",
        "MCP measurements are limited to tool counts and durations unless separate normalized telemetry is supplied.",
        "Codex and Claude imports remain optional local inputs, and missing telemetry stays marked as estimated or missing.",
    ]
    if result.missing:
        items.append(f"Missing evidence: {format_inline_list(sorted(result.missing))}")
    return format_bullets(items)


def build_target_files(result: AnalysisResult) -> str:
    evidence_paths = [f"`{item.relative_path}`" for item in result.inventory.files[:5]]
    items = [
        f"Primary analysis root: `{result.root}`",
        f"In-scope evidence paths: {', '.join(evidence_paths) if evidence_paths else 'none observed'}",
        "Bounded plugin update files implicated by the evidence plus the matching changelog and task report entry.",
    ]
    return format_bullets(items)


def build_problem_statement(result: AnalysisResult) -> str:
    statements = [
        f"Token evidence is `{result.evidence['token_counts']}` and duration evidence is `{result.evidence['durations']}`.",
        "The update should reduce avoidable process cost without widening scope beyond the current task.",
    ]
    if result.missing:
        statements.append(f"Missing evidence prevents stronger claims for: {format_inline_list(sorted(result.missing))}.")
    return format_bullets(statements)


def build_proposed_change(result: AnalysisResult) -> str:
    statements = [
        "Prepare a bounded plugin update that improves the highest-confidence cost issue supported by the evidence.",
        "Include the exact changelog and task report entry needed to document the adjustment.",
        "Keep any follow-up review request limited to task-only context and referenced artifact paths.",
    ]
    if int(result.derived.get("repeated_context_files", 0)) > 0:
        statements.append("Remove repeated context handoffs before adding new process steps.")
    return format_bullets(statements)


def build_acceptance_tests(result: AnalysisResult) -> str:
    del result
    return format_bullets(
        [
            "`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest plugins/task-token-cost-analyzer/tests/test_package.py plugins/task-token-cost-analyzer/tests/test_end_to_end.py`",
            "`PYTHONDONTWRITEBYTECODE=1 python3 -S -m unittest plugins/task-token-cost-analyzer/tests/test_package.py plugins/task-token-cost-analyzer/tests/test_end_to_end.py`",
            "If a focused test fails, save the verbose rerun to a temporary log for diagnosis instead of adding `-v` to the default command.",
        ]
    )


def build_safety_constraints(result: AnalysisResult) -> str:
    del result
    return format_bullets(
        [
            "Do not apply automatically; generate the update prompt only.",
            "Do not send the complete conversation history. Use task-only context.",
            "Run the local adversarial audit before the first independent review or recommendation.",
            "Do not install hooks, edit AGENTS.md, read private client databases, or send events over the network.",
        ]
    )


def render_template(template: Path, values: dict[str, str]) -> str:
    template_text = template.read_text(encoding="utf-8")
    return template_text.format(**values).rstrip() + "\n"


def render_report(result: AnalysisResult, template: Path) -> str:
    return render_template(
        template,
        {
            "scope": build_scope_section(result),
            "evidence": build_evidence_section(result),
            "acceptance_matrix": build_acceptance_matrix(result),
            "cost_breakdown": build_cost_breakdown(result),
            "avoidable_costs": build_avoidable_costs(result),
            "recommendations": build_recommendations(result),
            "limitations": build_limitations(result),
        },
    )


def render_update_prompt(result: AnalysisResult, template: Path) -> str:
    return render_template(
        template,
        {
            "target_files": build_target_files(result),
            "problem": build_problem_statement(result),
            "proposed_change": build_proposed_change(result),
            "acceptance_tests": build_acceptance_tests(result),
            "safety_constraints": build_safety_constraints(result),
        },
    )


def resolve_output_path(path: Path) -> Path:
    candidate = path.expanduser()
    selected_output_dir = (candidate.parent if candidate.parent != Path("") else Path(".")).resolve()
    if not selected_output_dir.exists():
        raise ValueError(f"Output directory does not exist: {selected_output_dir}")
    if not selected_output_dir.is_dir():
        raise ValueError(f"Output directory is not a directory: {selected_output_dir}")

    resolved_path = candidate.resolve()
    if not is_relative_to(resolved_path, selected_output_dir):
        raise ValueError(f"Output path is outside the selected output directory: {path}")
    return resolved_path


def write_output(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--events")
    parser.add_argument("--report-out")
    parser.add_argument("--prompt-out")
    parser.add_argument("--format", default="json", choices=("json",))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        result = analyze_task(Path(args.root), Path(args.events) if args.events else None)
        if bool(args.report_out) != bool(args.prompt_out):
            raise ValueError("Both --report-out and --prompt-out are required together")
        if args.report_out and args.prompt_out:
            report_out = resolve_output_path(Path(args.report_out))
            prompt_out = resolve_output_path(Path(args.prompt_out))
            write_output(report_out, render_report(result, REPORT_TEMPLATE_PATH))
            write_output(prompt_out, render_update_prompt(result, PROMPT_TEMPLATE_PATH))
    except (OSError, ValueError) as exc:
        print(f"error: {redact_text(str(exc))}", file=sys.stderr)
        return 2

    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
