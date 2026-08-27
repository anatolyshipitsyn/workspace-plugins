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
ALLOWED_CLIENTS = {"claude", "codex"}
EVENT_CLASSES = {"api_response", "compaction", "stop"}
TEXT_SUFFIXES = {".json", ".jsonl", ".md", ".txt", ".yaml", ".yml"}
SECRET_PATTERNS = (
    re.compile(r"(?i)\b(authorization\s*:\s*bearer\s+)([^\s]+)"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password|passwd)\b(\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"\b(sk|ghp|gho|ghu|xoxb|xoxp)-[A-Za-z0-9._-]+\b"),
)


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
    resolved = path.expanduser().resolve()
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
    events = [normalize_event(item) for item in raw_events]
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--events")
    parser.add_argument("--format", default="json", choices=("json",))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        result = analyze_task(Path(args.root), Path(args.events) if args.events else None)
    except (OSError, ValueError) as exc:
        print(f"error: {redact_text(str(exc))}", file=sys.stderr)
        return 2

    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
