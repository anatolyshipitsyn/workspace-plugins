# Task Token Cost Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable Agent Plugin that analyzes completed-task token cost from local evidence, optionally imports normalized hook telemetry, and emits a safe report plus a prompt for improving the analyzer.

**Architecture:** The portable package contains one shared skill, a dependency-free Python analyzer, references, templates, and tests. Client-specific telemetry adapters are optional inputs: Claude hooks can write normalized local events, while Codex events/API exports can be imported when available; neither adapter is required for package use. The analyzer is read-only by default and never changes repository policy or its own source.

**Tech Stack:** Markdown Agent Skill, Python 3 standard library, JSON, deterministic Markdown rendering, `unittest`, Agent Plugins 1.0.0 package conventions from the repository registry.

**Spec:** `docs/superpowers/specs/2026-08-27-task-token-cost-analyzer-design.md`

## Global Constraints

- The plugin MUST remain optional and reusable; it MUST NOT modify `AGENTS.md` or require repository-wide hooks.
- The portable package MUST contain shared skills, scripts, references, and templates once; Claude-specific adapters MUST remain minimal.
- The analyzer MUST distinguish `measured`, `derived`, `estimated`, and `missing` evidence and MUST NOT fabricate exact token counts.
- The analyzer MUST be offline-capable and MUST NOT send telemetry, prompts, transcripts, credentials, or headers to a remote service.
- Hooks and event imports MUST store aggregate metadata by default; raw prompts, transcripts, API bodies, and secret values MUST be redacted or excluded.
- Codex hooks MUST NOT be assumed to exist as a portable contract; Codex data is accepted only through an explicit normalized event/export input.
- Claude hook integration MUST be optional and client-specific; the portable core MUST work without `.claude` settings or hook installation.
- The acceptance matrix MUST cover Codex, Claude, MCP, YAML, and security with a status, evidence, and confidence for each area.
- The first audit MUST be adversarial and MUST run before the first independent review; validator-like fixes MUST be batched into one review round where practical.
- Tests MUST run without `-v`; detailed output is captured only when a test command fails.
- All generated report paths MUST remain inside an explicitly selected output directory; no destructive operation is permitted.
- Package metadata MUST follow the latest published release selected by the local registry and MUST NOT expose `--spec-version`.

---

## File map

The implementation uses these focused units:

- `plugins/task-token-cost-analyzer/plugin.json` — portable Agent Plugin manifest.
- `plugins/task-token-cost-analyzer/.claude-plugin/plugin.json` — minimal Claude adapter manifest.
- `plugins/task-token-cost-analyzer/skills/analyze-task-token-cost/SKILL.md` — user-facing orchestration and approval boundary.
- `plugins/task-token-cost-analyzer/skills/analyze-task-token-cost/references/acceptance-matrix.md` — five-area acceptance checks and evidence states.
- `plugins/task-token-cost-analyzer/skills/analyze-task-token-cost/references/cost-model.md` — measured/derived/estimated cost model and categorization rules.
- `plugins/task-token-cost-analyzer/skills/analyze-task-token-cost/references/client-guidance.md` — Codex import, Claude hook, MCP, and privacy guidance.
- `plugins/task-token-cost-analyzer/scripts/analyze_task_cost.py` — deterministic evidence reader, event normalizer, aggregation, redaction, and CLI.
- `plugins/task-token-cost-analyzer/templates/cost-report.md` — stable report headings and tables.
- `plugins/task-token-cost-analyzer/templates/plugin-update-prompt.md` — bounded self-improvement prompt contract.
- `plugins/task-token-cost-analyzer/tests/test_analyze_task_cost.py` — analyzer and telemetry tests.
- `plugins/task-token-cost-analyzer/tests/test_package.py` — manifest, adapter, path, and no-duplication tests.
- `plugins/task-token-cost-analyzer/tests/test_end_to_end.py` — artifact fixture to report/prompt integration test.
- `plugins/task-token-cost-analyzer/README.md` and `CHANGELOG.md` — installation, usage, privacy, and release notes.

Repository-level discovery remains unchanged; this plugin does not add a
mandatory hook to `AGENTS.md`.

## Task 1: Define the package contract and evidence fixtures

**Files:**

- Create: `plugins/task-token-cost-analyzer/plugin.json`
- Create: `plugins/task-token-cost-analyzer/.claude-plugin/plugin.json`
- Create: `plugins/task-token-cost-analyzer/skills/analyze-task-token-cost/references/acceptance-matrix.md`
- Create: `plugins/task-token-cost-analyzer/skills/analyze-task-token-cost/references/cost-model.md`
- Create: `plugins/task-token-cost-analyzer/skills/analyze-task-token-cost/references/client-guidance.md`
- Create: `plugins/task-token-cost-analyzer/tests/test_package.py`
- Create: `plugins/task-token-cost-analyzer/tests/fixtures/minimal-task/plan.md`
- Create: `plugins/task-token-cost-analyzer/tests/fixtures/minimal-task/progress.md`
- Create: `plugins/task-token-cost-analyzer/tests/fixtures/minimal-task/task-report.md`
- Create: `plugins/task-token-cost-analyzer/tests/fixtures/events/claude-response.json`
- Create: `plugins/task-token-cost-analyzer/tests/fixtures/events/codex-usage.json`

**Interfaces:**

- The portable manifest declares the plugin name, SemVer version, description, and Agent Plugins schema URL selected by the existing local registry.
- The Claude manifest contains only supported Claude metadata and does not contain copied skills or scripts.
- The event fixture shape is normalized JSON with fields `client`, `session_id_hash`, `event`, `timestamp`, `model`, `input_tokens`, `output_tokens`, `total_tokens`, and `duration_ms`; optional fields are omitted rather than set to secret-bearing raw payloads.
- `test_package.py` imports the future analyzer contract only through documented CLI paths and validates no adapter duplication.

- [ ] **Step 1: Write failing package and fixture tests**

```python
def test_package_has_portable_and_minimal_claude_manifests(self):
    self.assertEqual(validate_manifest(PORTABLE_MANIFEST), [])
    self.assertEqual(validate_manifest(CLAUDE_MANIFEST), [])
    self.assertFalse((PLUGIN_ROOT / ".claude-plugin" / "skills").exists())

def test_event_fixture_contains_only_normalized_aggregate_fields(self):
    event = json.loads((FIXTURES / "events/claude-response.json").read_text())
    self.assertIn(event["event"], {"api_response", "compaction", "stop"})
    self.assertNotIn("prompt", event)
    self.assertNotIn("transcript", event)
```

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest plugins/task-token-cost-analyzer/tests/test_package.py`

Expected: FAIL because the package and fixtures do not exist.

- [ ] **Step 2: Add manifests and normalized evidence fixtures**

Use the current repository registry conventions. Keep all values deterministic,
use HTTPS schema identifiers, and make the Claude manifest a metadata adapter
only. The event fixtures must contain numeric aggregate counts and no raw
request/response bodies.

- [ ] **Step 3: Run package tests in both interpreter modes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest plugins/task-token-cost-analyzer/tests/test_package.py`

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -S -m unittest plugins/task-token-cost-analyzer/tests/test_package.py`

Expected: PASS.

- [ ] **Step 4: Commit the package contract**

```bash
git add plugins/task-token-cost-analyzer/plugin.json \
  plugins/task-token-cost-analyzer/.claude-plugin/plugin.json \
  plugins/task-token-cost-analyzer/skills/analyze-task-token-cost/references \
  plugins/task-token-cost-analyzer/tests
git commit -m "feat: define task token analyzer package contract"
```

## Task 2: Implement deterministic analyzer and telemetry normalization

**Files:**

- Create: `plugins/task-token-cost-analyzer/scripts/analyze_task_cost.py`
- Modify: `plugins/task-token-cost-analyzer/tests/test_analyze_task_cost.py`
- Modify: `plugins/task-token-cost-analyzer/tests/fixtures/events/claude-response.json`
- Modify: `plugins/task-token-cost-analyzer/tests/fixtures/events/codex-usage.json`

**Interfaces:**

- `load_events(path: Path) -> list[dict[str, object]]` reads a JSON array or JSON Lines file and rejects malformed JSON, negative counts, non-numeric counts, and unknown secret-bearing raw-body fields.
- `collect_evidence(root: Path) -> EvidenceInventory` records explicitly scoped files by relative path, byte count, line count, and evidence class without reading files outside `root`.
- `analyze_task(root: Path, events: Path | None = None) -> AnalysisResult` returns deterministic aggregate data with `measured`, `derived`, `estimated`, and `missing` sections.
- `redact_text(value: str) -> str` removes credential-like values while preserving rule names and aggregate numbers.
- `render_report(result: AnalysisResult, template: Path) -> str` and `render_update_prompt(result: AnalysisResult, template: Path) -> str` return stable Markdown and never write files.
- CLI: `python3 analyze_task_cost.py --root PATH --report-out PATH --prompt-out PATH [--events PATH]`; exit `0` for complete/partial analysis and exit `2` for invalid arguments or malformed event data.

- [ ] **Step 1: Write failing analyzer tests**

```python
def test_aggregates_measured_event_tokens(self):
    result = analyze_task(FIXTURE_ROOT, EVENTS / "codex-usage.json")
    self.assertEqual(result.measured["total_tokens"], 3000)
    self.assertEqual(result.evidence["token_counts"], "measured")

def test_marks_missing_tokens_as_estimated_or_missing(self):
    result = analyze_task(FIXTURE_ROOT)
    self.assertIn(result.evidence["token_counts"], {"estimated", "missing"})
    self.assertNotIn("exact_total_tokens", result.measured)

def test_rejects_malformed_and_negative_event_data_without_echoing_payload(self):
    completed = run_cli("--events", MALFORMED_EVENTS)
    self.assertEqual(completed.returncode, 2)
    self.assertNotIn("secret-value", completed.stderr)

def test_redacts_secret_like_report_content(self):
    result = analyze_task(SECRET_FIXTURE_ROOT)
    report = render_report(result, REPORT_TEMPLATE)
    self.assertNotIn("secret-value", report)
    self.assertIn("redacted", report.lower())
```

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest plugins/task-token-cost-analyzer/tests/test_analyze_task_cost.py`

Expected: FAIL because the analyzer module and functions do not exist.

- [ ] **Step 2: Implement evidence collection and normalized event loading**

Use only `pathlib`, `json`, `re`, `dataclasses`, `datetime`, and related
standard-library modules. Resolve every input path and reject paths outside
the requested root. Accept Claude hook/OTel exports and Codex exports only
after mapping them to the normalized event fields; discard raw bodies rather
than copying them into the result.

- [ ] **Step 3: Implement aggregation, redaction, and confidence labels**

Compute token totals only from validated numeric events. Compute artifact
bytes/lines, task/review counts, repeated-context indicators, verbose-log
indicators, and available durations as derived metrics. Report absent client
telemetry as `missing`; report artifact-size proxies as `estimated`. Keep
wall-clock waiting separate from token cost.

- [ ] **Step 4: Run focused analyzer tests in both modes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest plugins/task-token-cost-analyzer/tests/test_analyze_task_cost.py`

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -S -m unittest plugins/task-token-cost-analyzer/tests/test_analyze_task_cost.py`

Expected: PASS with identical semantic results.

- [ ] **Step 5: Commit analyzer implementation**

```bash
git add plugins/task-token-cost-analyzer/scripts/analyze_task_cost.py \
  plugins/task-token-cost-analyzer/tests/test_analyze_task_cost.py \
  plugins/task-token-cost-analyzer/tests/fixtures/events
git commit -m "feat: analyze task token cost from local evidence"
```

## Task 3: Add skill orchestration, reports, and update prompt

**Files:**

- Create: `plugins/task-token-cost-analyzer/skills/analyze-task-token-cost/SKILL.md`
- Create: `plugins/task-token-cost-analyzer/templates/cost-report.md`
- Create: `plugins/task-token-cost-analyzer/templates/plugin-update-prompt.md`
- Create: `plugins/task-token-cost-analyzer/README.md`
- Create: `plugins/task-token-cost-analyzer/CHANGELOG.md`
- Modify: `plugins/task-token-cost-analyzer/tests/test_package.py`
- Create: `plugins/task-token-cost-analyzer/tests/test_end_to_end.py`

**Interfaces:**

- The skill invokes `scripts/analyze_task_cost.py` with an explicitly scoped task root and optional normalized event file.
- The report has sections `Scope`, `Evidence`, `Acceptance Matrix`, `Cost Breakdown`, `Avoidable Costs`, `Recommendations`, and `Limitations`.
- The update prompt has sections `Target Files`, `Problem`, `Proposed Change`, `Acceptance Tests`, and `Safety Constraints`; it asks for a bounded plugin update and changelog/report entry without applying changes.
- The skill requires a local adversarial audit before the first independent review and recommends one batched validator fix round when multiple findings share the same validation surface.
- The skill instructs subagents to receive only the current task brief, required interfaces, and referenced artifact paths, not the complete conversation history.
- Test command examples use no `-v`; on failure they save verbose output to a temporary log for diagnosis.

- [ ] **Step 1: Write failing end-to-end and contract tests**

```python
def test_fixture_produces_report_and_update_prompt(self):
    result = run_analyzer(FIXTURE_ROOT, EVENTS / "codex-usage.json")
    self.assertEqual(result.returncode, 0)
    report = REPORT_OUT.read_text()
    prompt = PROMPT_OUT.read_text()
    self.assertIn("Acceptance Matrix", report)
    self.assertIn("Target Files", prompt)
    self.assertIn("do not apply automatically", prompt.lower())

def test_skill_routes_to_cli_and_documents_hook_boundaries(self):
    skill = SKILL.read_text()
    self.assertIn("analyze_task_cost.py", skill)
    self.assertIn("Claude", skill)
    self.assertIn("Codex", skill)
    self.assertIn("MCP", skill)
    self.assertIn("YAML", skill)
    self.assertIn("security", skill.lower())
```

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest plugins/task-token-cost-analyzer/tests/test_end_to_end.py`

Expected: FAIL because skill, templates, and CLI rendering are incomplete.

- [ ] **Step 2: Implement deterministic templates and skill workflow**

Keep the skill concise and route details to references. The skill must request
scope confirmation, run the adversarial audit before reporting recommendations,
show evidence quality, and ask the user to review the generated update prompt.
It must not install hooks, edit `AGENTS.md`, read private client databases, or
send events over the network.

- [ ] **Step 3: Document optional Claude hook and Codex import paths**

Document Claude `SessionStart`, `UserPromptSubmit`, `PostToolUse`, `SubagentStop`,
and `Stop` collection as optional local adapters. Document that Claude
observability may provide usage/compaction values but raw API bodies are
sensitive. Document Codex normalized export/Compliance API input as optional
and client/account dependent; do not claim a portable Codex hook contract.
Document MCP measurements as tool counts/durations, not automatic LLM token
counts.

- [ ] **Step 4: Run package and end-to-end tests in both modes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest plugins/task-token-cost-analyzer/tests/test_package.py plugins/task-token-cost-analyzer/tests/test_end_to_end.py`

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -S -m unittest plugins/task-token-cost-analyzer/tests/test_package.py plugins/task-token-cost-analyzer/tests/test_end_to-end.py`

Expected: PASS.

- [ ] **Step 5: Commit skill and output contracts**

```bash
git add plugins/task-token-cost-analyzer/skills \
  plugins/task-token-cost-analyzer/templates \
  plugins/task-token-cost-analyzer/README.md \
  plugins/task-token-cost-analyzer/CHANGELOG.md \
  plugins/task-token-cost-analyzer/tests
git commit -m "feat: add task cost analysis workflow and update prompt"
```

## Task 4: Run adversarial audit, integrate repository checks, and package

**Files:**

- Create: `tests/test_task_token_cost_analyzer.py`
- Modify: `README.md`
- Modify: `DECISIONS.md`
- Modify: `plugins/task-token-cost-analyzer/tests/test_analyze_task_cost.py`
- Modify: `plugins/task-token-cost-analyzer/tests/test_end_to_end.py`

**Interfaces:**

- Repository discovery includes the new plugin tests without importing a second copy of shared code.
- The adversarial audit exercises malformed event JSON, nested/duplicate evidence, secret-like values, path escape, missing telemetry, false-positive names, and verbose test logs.
- The repository README documents optional installation/use, not mandatory hooks.
- `DECISIONS.md` records the optional-adapter boundary, aggregate-only default, and no automatic self-modification.

- [ ] **Step 1: Add adversarial test cases before the first independent review**

```python
def test_adversarial_inputs_are_safe_and_deterministic(self):
    for fixture in ADVERSARIAL_FIXTURES:
        first = run_analyzer(fixture)
        second = run_analyzer(fixture)
        self.assertEqual(first.report, second.report)
        self.assertNotIn("api-key-secret", first.report)
        self.assertNotIn("../outside", first.report)
```

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_task_token_cost_analyzer.py`

Expected: FAIL until the adversarial fixture bridge and repository documentation are complete.

- [ ] **Step 2: Implement the local adversarial audit and documentation**

Run the audit before dispatching the first independent review. Record its
results in the SDD ledger. Batch same-surface validator findings into one
review round and keep every fix covered by a regression test.

- [ ] **Step 3: Run complete checks without verbose output**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover`

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -S -m unittest discover`

Run: `PYTHONDONTWRITEBYTECODE=1 python3 plugins/agent-plugin-creator/scripts/validate_plugin.py plugins/agent-plugin-creator`

Run: `PYTHONDONTWRITEBYTECODE=1 python3 plugins/task-token-cost-analyzer/scripts/analyze_task_cost.py --root plugins/task-token-cost-analyzer --report-out /tmp/task-token-cost-report.md --prompt-out /tmp/task-token-cost-update-prompt.md`

On failure, rerun only the failing command with `-v` and redirect output to a
temporary log; do not include the log or sensitive input in the report.

- [ ] **Step 4: Run final package checks**

Verify both manifests, all `SKILL.md` files, optional MCP files, path
containment, no symlinks or secret files, deterministic report output, and
`git diff --check`. Confirm the new plugin does not add `--spec-version`,
mandatory hooks, network calls, or automatic self-edits.

- [ ] **Step 5: Commit repository integration**

```bash
git add README.md DECISIONS.md tests/test_task_token_cost_analyzer.py \
  plugins/task-token-cost-analyzer
git commit -m "test: verify task token analyzer integration"
```

## Review and completion gates

After each task, dispatch one fresh implementer/reviewer pair as required by
`AGENTS.md`. Before the first independent review, run the adversarial audit.
When several findings affect the same validator surface, send one combined
fix brief and perform one scoped re-review. After all tasks and fix rounds,
run exactly one final whole-branch review on the complete branch, then run the
complete non-verbose suite and package self-validation before declaring the
plugin complete.

The final result must remain usable without hooks, exact token telemetry, a
network connection, or changes to the host repository's `AGENTS.md`.
