# Task 3 Report

## Scope

Implemented Task 3 only inside the assigned worktree on `codex/task-token-cost-analyzer`.

Created:

- `plugins/task-token-cost-analyzer/skills/analyze-task-token-cost/SKILL.md`
- `plugins/task-token-cost-analyzer/templates/cost-report.md`
- `plugins/task-token-cost-analyzer/templates/plugin-update-prompt.md`
- `plugins/task-token-cost-analyzer/README.md`
- `plugins/task-token-cost-analyzer/CHANGELOG.md`
- `plugins/task-token-cost-analyzer/tests/test_end_to_end.py`

Modified:

- `plugins/task-token-cost-analyzer/scripts/analyze_task_cost.py`
- `plugins/task-token-cost-analyzer/tests/test_package.py`

Did not modify:

- root test discovery
- `DECISIONS.md`
- Task 4 integration files

## TDD Record

Initial RED commands:

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest plugins/task-token-cost-analyzer/tests/test_end_to_end.py`
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest plugins/task-token-cost-analyzer/tests/test_package.py`

Initial RED result:

- `test_end_to_end.py` failed because the CLI did not support `--report-out` or `--prompt-out`, the templates did not exist, and `SKILL.md` / docs were missing.
- `test_package.py` failed because the Task 3 artifact set was absent.

Test-harness correction before GREEN:

- The first end-to-end draft tried to read generated files after `TemporaryDirectory()` cleanup.
- Fixed the test to read any generated output while the temporary directory is still live so the suite measures analyzer behavior instead of fixture lifetime.

GREEN implementation:

- Added deterministic `render_report()` and `render_update_prompt()` helpers that read template files and return stable Markdown without writing by themselves.
- Extended the CLI with `--report-out` and `--prompt-out`, requiring both together and validating each resolved output path against its selected output directory before writing.
- Kept JSON stdout behavior intact so earlier analyzer contracts still work while the Task 3 CLI also writes Markdown artifacts.
- Added the portable `analyze-task-token-cost` skill with explicit guardrails for focused tests, task-only context, local adversarial audit before the first independent review, one batched validator-fix round for same-surface findings, and update-prompt generation without applying changes.
- Added concise README and changelog coverage for optional Claude hook adapters, optional Codex normalized export / Compliance API input, MCP measurement limits, and the non-applying update-prompt workflow.
- Added a focused end-to-end suite that checks CLI artifact generation, renderer contracts, and the pressure-scenario wording required by the skill/docs.

## Verification

Passed:

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest plugins/task-token-cost-analyzer/tests/test_package.py plugins/task-token-cost-analyzer/tests/test_end_to_end.py`
- `PYTHONDONTWRITEBYTECODE=1 python3 -S -m unittest plugins/task-token-cost-analyzer/tests/test_package.py plugins/task-token-cost-analyzer/tests/test_end_to_end.py`
- `git diff --check`

Focused results:

- CLI run against `tests/fixtures` with `events/codex-usage.json` now writes both Markdown artifacts and still returns measured JSON with `total_tokens=3000`.
- Rendered report includes `Scope`, `Evidence`, `Acceptance Matrix`, `Cost Breakdown`, `Avoidable Costs`, `Recommendations`, and `Limitations`.
- Rendered update prompt includes `Target Files`, `Problem`, `Proposed Change`, `Acceptance Tests`, and `Safety Constraints`, and explicitly says to not apply automatically.

## Fix Rounds

Follow-up wording fixes after initial GREEN:

- Added the exact `focused tests` phrase to the skill after the first green verification showed the pressure contract was checking for that wording.
- Changed the validator-fix guidance to include the exact `batched` wording required by the pressure contract.
- Changed the README hook guidance to include the exact `do not install hooks` wording required by the pressure contract.

Verification after wording fixes:

- Re-ran the same focused normal and `-S` unittest commands after each wording adjustment until both suites passed cleanly.

Fix round 1 for review findings:

- Added RED-phase regression assertions in `test_end_to_end.py` proving the fixture report marks `Security` as `not observed` when secret scrubbing evidence is missing, and never as a false-positive `pass`.
- Added a second regression that exercises secret-bearing local evidence and proves the rendered Acceptance Matrix marks `Security` as `pass` only when `secret_scrubbing` evidence is actually present.
- Changed `build_acceptance_matrix()` so the `Security` row status is evidence-bounded: `pass` only when secret scrubbing was observed locally, otherwise `not observed`.
- Tightened the missing-evidence wording so the report explains that outputs stay aggregate-only while secret scrubbing was not exercised by the selected scope.
- Added a matching limitation note when the selected evidence does not exercise redaction behavior.

Fix round 1 RED command:

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest plugins/task-token-cost-analyzer/tests/test_end_to_end.py`

Fix round 1 RED result:

- `FAILED (failures=2)` because the fixture report still rendered `| Security | pass |` with no secret scrubbing evidence, and the positive-path wording did not yet distinguish observed redaction evidence from the unconditional pass wording.

Fix round 1 verification:

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest plugins/task-token-cost-analyzer/tests/test_end_to_end.py`
- `PYTHONDONTWRITEBYTECODE=1 python3 -S -m unittest plugins/task-token-cost-analyzer/tests/test_end_to_end.py`
- `git diff --check`

## Self-review

- Confirmed the Task 3 changes stay inside the assigned worktree and do not touch root discovery, `DECISIONS.md`, or Task 4 files.
- Confirmed the skill remains concise and routes deeper detail to existing references instead of duplicating them inline.
- Confirmed the update prompt remains advisory only: it requests review, changelog/report updates, and safety constraints, but never applies changes.
- Confirmed the docs do not claim a portable Codex hook contract and keep Claude / Codex telemetry imports optional and local.
- Confirmed no hooks were installed or required, no network behavior was added, and no new secret-bearing surfaces were introduced.
- Confirmed the Acceptance Matrix no longer claims `Security` passed without observed scrubbing evidence, and the new regression covers both missing-evidence and present-evidence cases.

## Commit

- `c24ab7f` — `feat: add task cost analysis workflow and update prompt`

## Limitations

- Output-directory validation is bounded to each explicit output path's resolved parent directory because Task 3 does not introduce a separate `--output-dir` selector.
- The acceptance/report rendering is intentionally deterministic and evidence-driven; broader repository discovery and whole-package integration remain with Task 4.
