# Task 3 report — semantic validator

## Changed files

- `plugins/agent-plugin-creator/scripts/validate_plugin.py`
- `plugins/agent-plugin-creator/tests/test_validate_plugin.py`
- `.superpowers/sdd/2026-08-26-agent-plugin-creator/task-3-report.md`

## Implementation summary

Implemented an offline semantic validator CLI at `python3 validate_plugin.py PLUGIN_PATH`.
It loads the local release registry, validates `plugin.json` against bundled local
schemas, falls back to a deterministic standard-library structural validator when a
local JSON Schema package is unavailable, and adds semantic checks for:

- skill discovery and frontmatter validation under `skills/`;
- symlink and realpath containment inside the plugin root;
- `mcp.json` schema/version matching, stdio path containment, remote HTTPS rules,
  command/args/cwd path containment, and reserved environment names;
- optional Claude adapter manifest acceptance;
- obvious committed secret material (including parsed JSON objects and arrays) and
  `.env` files.
- dependency-independent fallback parsing for supported scalar, flow-array,
  flow-object, and simple block frontmatter values.

Diagnostics are emitted in a stable human-readable format with `path`, `rule`, and
`correction`, and the validator never executes plugin code or uses the network.

## Focused verification

Command:

```bash
python3 -m unittest plugins/agent-plugin-creator/tests/test_validate_plugin.py -v
```

Result:

- `Ran 11 tests in 1.479s`
- `OK`

The focused suite includes regression coverage for quoted JSON secret values,
filesystem escapes in MCP `command` and `args` while preserving flag arguments,
and valid array/object frontmatter with the validator launched as `python3 -S`.

Command:

```bash
python3 -S -m unittest plugins/agent-plugin-creator/tests/test_validate_plugin.py -v
```

Result:

- `Ran 11 tests in 1.496s`
- `OK`

Command:

```bash
git diff --check
```

Result:

- no output
- exit code `0`

## Self-review rulings

- Kept validation offline and deterministic by resolving schemas from the local
  registry only.
- Used the existing scaffolder output as the positive fixture, so placeholder skill
  bodies remain accepted; Task 3 enforces skill frontmatter/layout rather than
  placeholder prose.
- Kept all changes inside the Task 3 write set.

## Limitations

- The structural schema fallback is intentionally scoped to the bundled schema
  features used by this plugin (`type`, `properties`, `required`,
  `additionalProperties`, `items`, `oneOf`, `$ref`, `const`, `enum`, `pattern`,
  `propertyNames`, and `not`).
- The validator performs static package checks only; it does not provide an MCP
  runtime smoke test.
- MCP command/argument path detection is intentionally heuristic: bare executable
  names, in-package relative paths, URL-like arguments, and ordinary flags remain
  valid; absolute paths, traversal, explicit `${PLUGIN_ROOT}` paths, and relative
  paths resolving through an external symlink are rejected.

## Fix round 2 verification

Command:

```bash
python3 -m unittest plugins/agent-plugin-creator/tests/test_validate_plugin.py -v
```

Result: `Ran 12 tests in 1.944s` — `OK`.

Command:

```bash
python3 -S -m unittest plugins/agent-plugin-creator/tests/test_validate_plugin.py -v
```

Result: `Ran 12 tests in 1.948s` — `OK`.

The added regression coverage validates a generated stdio plugin with relative
script and URL-like arguments, and rejects command/argument traversal and
`${PLUGIN_ROOT}` escapes without treating flags as paths. Structured secret
detection and dependency-independent frontmatter fallback remain covered.

`git diff --check` passed with exit code `0`.

## Fix round 3 verification

The validator now uses syntax-aware Python inspection for concrete credential
assignments and structured JSON inspection for configuration values. It does not
exclude scripts or tests: the regression suite confirms the creator package
self-validates, while a real `OPENAI_API_KEY` assignment in a generated Python
file, JSON header, config file, and `.env` file is still rejected.

Commands:

```bash
python3 -m unittest plugins/agent-plugin-creator/tests/test_validate_plugin.py -v
python3 -S -m unittest plugins/agent-plugin-creator/tests/test_validate_plugin.py -v
git diff --check
```

Results:

- Both unittest commands: `Ran 13 tests` — `OK` (`1.851s` and `1.852s`).
- `git diff --check`: exit code `0`, no output.
