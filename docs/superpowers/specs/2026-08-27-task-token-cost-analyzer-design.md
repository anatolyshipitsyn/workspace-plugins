# Task Token Cost Analyzer — Design

## Goal

Create a reusable, client-neutral Agent Plugin that analyzes the token cost of
a completed engineering task and proposes a concrete prompt for improving the
plugin itself. The plugin is optional: it is not added to `AGENTS.md`, does not
run automatically for every task, and does not require Codex or Claude to
expose private token telemetry.

## Design choice

Use a hybrid implementation:

- one shared Agent Skill orchestrates collection, interpretation, and report
  generation;
- a dependency-free Python script computes deterministic metrics from supplied
  artifacts when available;
- Markdown references define the cost model, acceptance matrix, client
  guidance, and report/prompt contracts;
- optional event or usage JSON may provide measured token counts, but missing
  telemetry produces estimates rather than invented precision.

The plugin will not modify repository policy, plans, task ledgers, client
configuration, or its own source automatically. Applying the generated update
prompt remains a deliberate user action.

## Package layout

```text
plugins/task-token-cost-analyzer/
├── plugin.json
├── .claude-plugin/plugin.json
├── skills/analyze-task-token-cost/SKILL.md
├── skills/analyze-task-token-cost/references/
│   ├── acceptance-matrix.md
│   ├── cost-model.md
│   └── client-guidance.md
├── scripts/analyze_task_cost.py
├── templates/cost-report.md
├── templates/plugin-update-prompt.md
├── tests/
├── README.md
└── CHANGELOG.md
```

The portable package contains the shared skill and script once. The Claude
manifest is a minimal adapter; no skills or scripts are copied below
`.claude-plugin/`.

## Inputs and evidence levels

The skill accepts a repository/task path and optionally an event JSON file.
It searches only explicitly scoped locations for:

- implementation plan and design;
- SDD ledger and task reports;
- review reports and fix-round records;
- git diff/statistics;
- test commands and captured logs;
- client-provided usage events containing numeric token counts.

Evidence is labeled as `measured`, `derived`, `estimated`, or `missing`. A
missing client counter is never replaced with a fabricated exact count.
Sensitive contents are not echoed into reports; paths and aggregate metadata
are preferred over raw prompts, credentials, headers, or transcripts.

## Analysis workflow

1. Confirm the scope and identify available evidence.
2. Run the local adversarial audit before proposing efficiency changes.
3. Evaluate the acceptance matrix for Codex, Claude, MCP, YAML, and security.
4. Calculate measured/derived metrics and estimate only clearly marked gaps.
5. Classify work as product value, required process, rework, or avoidable
   overhead.
6. Produce a report with findings, confidence, and prioritized actions.
7. Produce a separate ready-to-paste prompt for updating this plugin.
8. Ask the user to review the prompt; never apply it implicitly.

The report must analyze every completed task, not only the final implementation
task. It must identify repeated context, redundant test output, review loops,
avoidable waiting/polling, and late-discovered acceptance gaps when evidence
supports those conclusions.

## Acceptance matrix

The matrix is a reusable checklist, not a claim that every task uses every
technology. Each row records `applicable`, `pass`, `fail`, `not observed`, or
`not applicable`, with evidence and confidence.

| Area | Required checks |
|---|---|
| Codex | skill discovery, concise task context, worktree/SDD boundaries, non-verbose verification, no unsupported telemetry assumptions |
| Claude | adapter discovery, shared skill paths, Claude variable conventions, equivalent workflow and output |
| MCP | transport semantics, URL/header safety, placeholder policy, runtime-smoke-test status, no secret embedding |
| YAML | frontmatter validity, scalar typing, malformed/nested flow parity, quoted and block scalar behavior |
| Security | secret/redaction checks, path/symlink containment, no credential echo, safe report inputs, no destructive writes |

The first local adversarial audit must exercise negative cases before the first
independent review. It should include malformed inputs, missing evidence,
false-positive names, duplicate context, and a report containing a secret-like
value to confirm redaction.

## Metrics and cost model

The script reports counts and ratios where evidence permits:

- number of tasks, implementer turns, review/fix rounds, and repeated runs;
- bytes/lines of plans, reports, diffs, and test logs;
- measured input/output tokens from optional usage events;
- estimated context volume from artifact sizes, explicitly marked as a proxy;
- repeated-context and verbose-output indicators;
- time spent waiting, if timestamps exist.

It must distinguish token cost from wall-clock cost. Waiting without new model
output is reported as time overhead, not silently converted to tokens.

## Output contracts

The Markdown report contains:

1. scope and evidence inventory;
2. measured versus estimated data;
3. acceptance-matrix table;
4. cost breakdown by task and category;
5. top avoidable-cost causes;
6. prioritized recommendations with expected trade-offs;
7. confidence and limitations.

The update prompt contains only bounded proposed changes: target file(s), the
behavior to change, acceptance tests, and a request to update the changelog
and report. It explicitly instructs the next run to preserve portability,
client neutrality, redaction, and the optional nature of this plugin.

## Error handling and safety

- Missing or unreadable evidence produces a partial report with `missing`
  labels and a non-fatal diagnostic.
- Malformed event JSON is reported without echoing its contents.
- Invalid numeric counts are rejected rather than coerced silently.
- The script is read-only by default and writes only to an explicitly selected
  output path.
- No network, plugin installation, branch mutation, credential access, or
  automatic self-modification is part of the MVP.

## Testing strategy

- unit tests for event parsing, evidence classification, aggregation,
  redaction, missing/malformed inputs, and deterministic output;
- fixture tests for the full acceptance matrix and adversarial audit;
- end-to-end test from scoped artifacts to report and update prompt;
- package test for portable manifest, Claude adapter minimality, and no
  duplicated shared files;
- run tests without `-v`; capture detailed output only when a test fails;
- run the final suite and self-validation in both normal Python and
  dependency-minimal mode where supported.

## Non-goals

- exact billing or provider pricing calculations;
- automatic interception of Codex or Claude conversations;
- mandatory repository-wide hooks;
- replacing SDD, code review, or client-native telemetry;
- automatic edits to the plugin based on its own recommendations.

## Success criteria

The plugin can be installed independently in Codex or Claude, analyze a
completed task from local artifacts without network access, clearly separate
measured facts from estimates, check the five required acceptance areas, and
emit a safe actionable update prompt without modifying the repository.
