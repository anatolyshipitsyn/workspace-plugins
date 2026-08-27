# Task H report

## Changed files

- `plugins/agent-plugin-creator/scripts/validate_plugin.py`
- `plugins/agent-plugin-creator/tests/test_validate_plugin.py`
- `tests/test_end_to_end.py`
- `.superpowers/sdd/2026-08-26-agent-plugin-creator/task-h-report.md`

## Implementation summary

- Claude MCP configurations now normalize `${CLAUDE_PLUGIN_ROOT}` and
  `${CLAUDE_PLUGIN_DATA}` before shared stdio placeholder validation, so
  generated Claude adapters validate consistently with portable manifests.
- Discovered skill bodies now reject the exact unfinished scaffolder sentence,
  while ordinary prose discussing placeholders remains valid.
- Non-Python secret checks now recognize literal shell `export` and JavaScript
  `const`/`let`/`var` declarations for secret-like names, without reporting
  secret values or flagging benign names such as `tokenizer` and `secretary`.
- Claude adapter manifests now have an explicit, intentionally limited schema
  of string `name`, `version`, and `description` fields; unsupported fields are
  rejected.

## Verification

Commands and results:

- `python3 -m unittest plugins/agent-plugin-creator/tests/test_validate_plugin.py -v`: 30 tests passed.
- `python3 -S -m unittest plugins/agent-plugin-creator/tests/test_validate_plugin.py -v`: 30 tests passed.
- `python3 -m unittest plugins/agent-plugin-creator/tests/test_scaffold_plugin.py -v`: 14 tests passed.
- `python3 -S -m unittest plugins/agent-plugin-creator/tests/test_scaffold_plugin.py -v`: 14 tests passed.
- `python3 -m unittest discover -v`: 53 tests passed.
- `python3 -S -m unittest discover -v`: 53 tests passed.
- Real package validation under both Python modes: exit code 0 with no diagnostics.
- `git diff --check`: exit code 0 with no output.

## Self-review

- Shared MCP validation receives normalized portable placeholders only; command
  placeholder rejection remains unchanged.
- Skill placeholder matching is line-oriented and exact enough to avoid
  rejecting prose that merely discusses placeholders.
- Declaration secret matching uses exact secret-name semantics and the existing
  safe-placeholder/value redaction behavior.
- Claude adapter fields are allowlisted rather than inheriting the broader
  portable manifest schema.
- The end-to-end scaffold test now replaces the intentionally unfinished skill
  marker before validation, matching the documented scaffold lifecycle.
