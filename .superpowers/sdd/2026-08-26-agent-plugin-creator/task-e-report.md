# Task E report

## Changed files

- `plugins/agent-plugin-creator/scripts/validate_plugin.py`
- `plugins/agent-plugin-creator/tests/test_validate_plugin.py`
- `.superpowers/sdd/2026-08-26-agent-plugin-creator/task-e-report.md`

## Implementation summary

Closed the remaining bounded validator gaps in the allowed write set only.

- Python secret detection now walks nested and function-local assignments,
  keeps scanning after safe placeholder values, and matches only exact or
  separator-suffixed credential names so benign identifiers like `tokenizer`
  and `secretary` stay valid.
- Remote MCP header validation now enforces HTTP field-name and field-value
  rules, and it catches case-insensitive duplicate header names from raw JSON
  before the normal object loader can collapse them. The same check covers
  normalized Claude `http` adapters.
- The standard-library Agent Skills frontmatter fallback now routes plain
  scalars through the same null/boolean/numeric/quoted typing path as flow
  values, so `python3 -S` rejects invalid required metadata the same way as
  the PyYAML path.
- The regression tests now cover nested placeholder-then-secret Python
  scanning, benign secret-substring identifiers, remote header semantics,
  Claude duplicate-header normalization, placeholder-safe headers, and
  YAML-typing parity across normal and isolated interpreter modes.

## Verification

Command:

```bash
python3 -m unittest plugins/agent-plugin-creator/tests/test_validate_plugin.py -v
```

Result:

- `Ran 25 tests in 5.291s`
- `OK`

Command:

```bash
python3 -S -m unittest plugins/agent-plugin-creator/tests/test_validate_plugin.py -v
```

Result:

- `Ran 25 tests in 5.291s`
- `OK`

Command:

```bash
python3 plugins/agent-plugin-creator/scripts/validate_plugin.py plugins/agent-plugin-creator
```

Result:

- exit code `0`
- no output

Command:

```bash
python3 -S plugins/agent-plugin-creator/scripts/validate_plugin.py plugins/agent-plugin-creator
```

Result:

- exit code `0`
- no output

Command:

```bash
git diff --check
```

Result:

- exit code `0`
- no output

## Self-review

- Kept the secret-name matcher narrow to exact and separator-suffixed
  credential identifiers so the new nested scan closes the real hole without
  reviving the old false positives.
- Used raw JSON pair tracking only where duplicate HTTP header names matter,
  which preserves the existing manifest-loading behavior everywhere else.
- Tightened the `python3 -S` scalar fallback at the top-level parse boundary
  instead of broadening later validation, so the isolated and PyYAML paths now
  agree for the required frontmatter typing cases covered by the brief.

## Task E fix round 1

- Added regressions proving `description: TRUE` and `description: 0x10` are
  rejected consistently with and without PyYAML (`python3` and `python3 -S`).
- Extended the stdlib scalar fallback to match YAML typing relevant to Agent
  Skills frontmatter: case-insensitive booleans/nulls, binary/hex/octal and
  underscored integers, and common float forms.
- Preserved quoted strings, block scalars, metadata type enforcement,
  secret/header checks, and creator self-validation.

Fix-round verification:

- `python3 -m unittest plugins/agent-plugin-creator/tests/test_validate_plugin.py -v` — 25 tests passed.
- `python3 -S -m unittest plugins/agent-plugin-creator/tests/test_validate_plugin.py -v` — 25 tests passed.
- Both regular and isolated real-package validator commands passed.
- `git diff --check` passed.
