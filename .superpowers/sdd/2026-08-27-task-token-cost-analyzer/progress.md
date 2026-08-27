# SDD ledger — plan: docs/superpowers/plans/2026-08-27-task-token-cost-analyzer.md

## Preflight scan

| Tasks | Shared file or interface | Finding | Ruling |
|---|---|---|---|
| 1 → 2 | normalized event fixtures and package paths | Task 1 produces the JSON fixture shape and package root that Task 2 parses. | Preserve Task 1 before Task 2; `client`, aggregate counts, and secret-free input are the stable contract. |
| 2 → 3 | analyzer result and Markdown rendering | Task 2 originally required template rendering, but Task 3 creates templates. | Move template rendering ownership to Task 3. Task 2 returns deterministic `AnalysisResult` data only. Cost if wrong: Task 3 may need a small adapter method, covered by its end-to-end test. |
| 3 → 4 | package tests and root discovery | Full `unittest discover` must include tests inside the hyphenated plugin directory. The current discovery bridge is specific to `agent-plugin-creator`. | Task 4 generalizes the repository bridge to discover portable plugin-local tests without duplicate imports. Cost if wrong: root discovery can miss the new plugin tests. |
| 1 → 4 | manifests, adapter, references | Task 4 adversarial/package checks consume the package created by Task 1. | Keep Task 4 after package and analyzer tasks; no parallel implementation dispatches. |

| Task | Self-consistency check | Ruling |
|---|---|---|
| 1 | Package and fixtures have tests in the same task. | Proceed. |
| 2 | Renderer references templates not yet created. | Correct plan before dispatch. |
| 3 | End-to-end test requires analyzer from Task 2 and owns templates. | Proceed after Task 2. |
| 4 | Full-suite claim requires generic test discovery. | Correct plan before dispatch. |

## Rulings

- Ruling: Task 2 returns deterministic structured analysis only; Task 3 owns Markdown template rendering — this removes an impossible dependency on files not yet created. Cost if wrong: one small rendering adapter may be needed in Task 3.
- Ruling: Task 4 generalizes test discovery for plugin-local suites — otherwise the stated complete-suite gate does not validate this new package. Cost if wrong: the bridge may need follow-up isolation work, constrained by focused tests.
- Ruling: Task 2 creates its analyzer test file; it cannot modify a file that Task 1 does not own. Cost if wrong: a shared test helper may need an explicit owner, which the Task 2 review will identify.
- Ruling: The adversarial-audit gate begins when behavior to attack first exists: Task 1 receives a manifest/fixture-only review, while Task 2 must run the audit before its first behavioral review and Task 4 repeats it before whole-package review. Cost if wrong: a cross-cutting issue can remain until Task 2, mitigated by Task 1 schema and fixture tests.

## Task results

- Task 1: complete — commits `3c7f6a1`, `92a62c4`; focused package tests passed in normal and `-S` modes; first review found two medium test-coverage gaps; one combined validator fix round passed scoped re-review.
- Task 2: complete — commits `818867c`, `7e74bc3`; focused analyzer and package tests passed in normal and `-S` modes; initial adversarial audit passed; first review found one high and two medium interface/coverage gaps; one combined fix round passed scoped re-review.
- Task 3: complete — commits `c24ab7f`, `5327852`, `1fbe49e`; package/end-to-end tests passed in normal and `-S` modes; first review found an evidence-bounding Security false positive and end-to-end gap; one combined fix round passed scoped re-review.
- Task 4: complete — commit `e7a6c1b`; generalized root discovery to all plugin-local `test_*.py` suites in an isolated copied plugin tree; added deterministic local adversarial coverage for malformed telemetry, missing telemetry, nested duplicate context, review artifacts, verbose logs, secret-like values, false-positive metadata names, and path-like values; recorded the optional aggregate-only/no-hook/no-automatic-edit boundary in root docs. Audit and focused package tests passed before self-review. Complete non-verbose discovery passed in normal and `-S` modes (79 tests each); both package validators, analyzer smoke, and `git diff --check` passed. No independent reviewer was dispatched because the Task 4 request explicitly prohibited dispatch; self-review remains the completion review for this task. Cost if wrong: a future plugin test module with non-collection mutable path-bearing globals may need a narrowly scoped bridge extension.

## Task 4 fix round 1

- RED: repeated `load_tests()` calls reused `task_token_cost_analyzer_tests.test_package` from `sys.modules`, so the second isolated workspace retained the first workspace's `PLUGIN_ROOT`. The new regression failed with identical module objects before the bridge fix.
- GREEN: `_load_module()` now removes the previous dynamic module before executing the source module, so every discovery pass receives a fresh module bound to its newly copied plugin tree. The regression asserts distinct module identity and second-workspace package paths.
- Added a package-wide AST regression over every package Python file: prohibited network import roots and automatic edit invocation paths/commands are rejected. The static policy covers `os.system`/`os.popen` plus edit-capable literal subprocess commands while allowing the test suite's safe local CLI/validator subprocess checks.
- Focused bridge/package tests passed (81); complete non-verbose discovery passed in normal and `-S` modes (81 each); `git diff --check` passed. Commit `74bd2d7`.

## Task 3 skill baseline

- Baseline pressure exercise: an agent facing requests to skip tests/review and include full chat history retained focused non-verbose checks, adversarial audit, independent review, and task-only context. Task 3 must encode these guardrails and explicitly forbid automatic self-updates. Cost if wrong: the skill could be too weak under urgency pressure; its package tests and Task 4 audit mitigate this.
- Task 2: implementation complete in the assigned worktree; focused analyzer tests and retained Task 1 package tests passed in normal and `-S` modes; the initial local adversarial audit passed without requiring a validator fix round.

## Final fix

- Rebased `codex/task-token-cost-analyzer` onto local `main` at `272ffd4`; the
  replay stopped once on `README.md`, and the conflict was resolved by keeping
  the restored workspace marketplace plus `github-pr-agent` docs from `main`
  alongside the analyzer usage section from this branch.
- Final-review finding: acceptance-matrix statuses overclaimed Codex, Claude,
  and YAML from weak heuristics. Ruling: keep `pass` only for observed
  area-specific evidence and report partial coverage as `applicable` with
  confidence. Cost if wrong: the matrix can still overstate portability or test
  coverage from incomplete local evidence.
- Final-review finding: optional local `--events` inputs rejected realistic
  exports stored outside the selected root. Ruling: allow only explicit
  absolute external paths; keep root-relative paths confined to the selected
  root. Cost if wrong: users may still need extra path normalization or the
  boundary may admit confusing relative escapes.
- Final-review finding: the rebased full suite still failed until the new
  analyzer package was added to both repository marketplace manifests. Ruling:
  advertise every packaged plugin in both root manifests so Codex and Claude
  see the same installable workspace surface. Cost if wrong: the analyzer can
  validate locally but remain undiscoverable through the workspace marketplace.
