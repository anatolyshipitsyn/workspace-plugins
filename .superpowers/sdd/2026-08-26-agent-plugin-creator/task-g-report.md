# Task G report

## Changed files

- `plugins/agent-plugin-creator/scripts/validate_plugin.py`
- `plugins/agent-plugin-creator/tests/test_validate_plugin.py`
- `plugins/agent-plugin-creator/README.md`
- `.superpowers/sdd/2026-08-26-agent-plugin-creator/task-g-report.md`

## Implementation summary

Closed the remaining validator parity gaps in the allowed write set only.

- Remote MCP header validation now rejects committed `${...}` environment or
  placeholder expansion syntax in both portable `mcp.json` files and Claude
  `http` adapters after normalization, while still accepting ordinary literal
  header values and keeping the existing secret scanning behavior intact.
- The standard-library skill frontmatter fallback now mirrors PyYAML for
  unquoted YAML date scalars such as `2026-08-27` and sexagesimal time-like
  scalars such as `12:34`, so fields that must remain strings are rejected
  consistently under both `python3` and `python3 -S`.
- Regression coverage now proves that quoted date/time strings and block
  scalars remain valid, while unquoted date/time scalars are rejected and the
  creator package still validates cleanly.
- The package README now tells plugin authors to keep committed remote header
  values literal and move runtime auth injection outside manifest files.

## Verification

Command:

```bash
python3 -m unittest plugins/agent-plugin-creator/tests/test_validate_plugin.py -v
```

Result:

- `Ran 25 tests in 7.376s`
- `OK`

Command:

```bash
python3 -S -m unittest plugins/agent-plugin-creator/tests/test_validate_plugin.py -v
```

Result:

- `Ran 25 tests in 7.375s`
- `OK`

Command:

```bash
python3 plugins/agent-plugin-creator/scripts/validate_plugin.py plugins/agent-plugin-creator
```

Result:

- exit code `0`
- no validator diagnostics

Command:

```bash
python3 -S plugins/agent-plugin-creator/scripts/validate_plugin.py plugins/agent-plugin-creator
```

Result:

- exit code `0`
- no validator diagnostics

Command:

```bash
git diff --check
```

Result:

- exit code `0`
- no output

## Self-review

- Limited the fallback scalar typing changes to unquoted plain scalars, so
  quoted strings and block scalar content continue down their existing string
  paths without new coercion.
- Added the header placeholder rule after the existing HTTP control-character
  check so invalid control characters still receive the more specific
  transport diagnostic first.
- Kept the new header rejection scoped to `${...}` syntax rather than broad
  placeholder heuristics, which avoids regressing valid literal headers while
  closing the specific manifest-expansion gap from the review.
