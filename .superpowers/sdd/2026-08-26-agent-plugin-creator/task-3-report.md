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
  names and ordinary non-path arguments remain valid, while slash-prefixed,
  placeholder, traversal, and common script/config path values are checked.
