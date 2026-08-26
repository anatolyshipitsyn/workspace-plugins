# Task A Report

## Scope

Implemented Task A only within the allowed write set:

- `plugins/agent-plugin-creator/scripts/scaffold_plugin.py`
- `plugins/agent-plugin-creator/scripts/validate_plugin.py`
- `plugins/agent-plugin-creator/tests/test_scaffold_plugin.py`
- `plugins/agent-plugin-creator/tests/test_validate_plugin.py`
- `.superpowers/sdd/2026-08-26-agent-plugin-creator/task-a-report.md`

## Changes

- Updated Claude adapter generation so portable `streamable-http` entries stay
  unchanged in `mcp.json` and become Claude `http` entries in `.mcp.json`.
- Tightened stdio validation to match Agent Plugins 1.0.0 semantics:
  `command` must be bare or `./`-relative, placeholders are rejected in
  `command`, and `args` are treated as opaque strings instead of filesystem
  paths.
- Updated remote transport validation to allow loopback HTTP, reject URL
  fragments, and keep rejecting placeholders, embedded credentials, and
  invalid non-absolute URLs.
- Added focused regression coverage for the new scaffold and validator rules.

## Verification

Passed:

- `python3 -m unittest plugins/agent-plugin-creator/tests/test_scaffold_plugin.py -v`
- `python3 -m unittest plugins/agent-plugin-creator/tests/test_validate_plugin.py -v`
- `python3 -S -m unittest plugins/agent-plugin-creator/tests/test_scaffold_plugin.py -v`
- `python3 -S -m unittest plugins/agent-plugin-creator/tests/test_validate_plugin.py -v`
- `git diff --check`

## Self-review

- Confirmed the portable MCP file is still rendered directly from the portable
  config and only the Claude adapter applies transport-name conversion.
- Confirmed validator normalization is scoped to `.mcp.json`, so portable
  `mcp.json` still enforces the bundled 1.0.0 schema unchanged.
- Kept existing symlink containment, reserved-variable checks, and secret
  detection intact.

## Limitations

- The bundled Agent Plugins 1.0.0 schema does not define Claude's `http`
  transport alias, so validation accepts Claude adapter entries by normalizing
  that alias back to portable `streamable-http` before schema validation.
- This task covers structural and semantic validation only; it does not add an
  MCP runtime smoke test.
