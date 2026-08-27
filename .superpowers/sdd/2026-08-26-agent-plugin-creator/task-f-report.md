# Task F report

## Changed files

- `plugins/agent-plugin-creator/scripts/scaffold_plugin.py`
- `plugins/agent-plugin-creator/tests/test_scaffold_plugin.py`
- `plugins/agent-plugin-creator/skills/create-agent-plugin/SKILL.md`
- `plugins/agent-plugin-creator/README.md`
- `.superpowers/sdd/2026-08-26-agent-plugin-creator/task-f-report.md`

## Implementation summary

Closed the remaining metadata scaffolding gap in the allowed write set only.

- The scaffold CLI now accepts optional `--license`, `--author-name`,
  `--author-email`, and `--author-url` inputs and writes only schema-valid
  portable manifest metadata when the requester explicitly supplies it.
- License and author values are trimmed, empty values are rejected before any
  plugin directory is created, author emails must look like real email
  addresses, and author URLs must be absolute `http` or `https` URLs.
- The portable manifest continues to omit `license` and `author`
  intentionally when those flags are absent, and the Claude adapter remains
  minimal without duplicated metadata.
- The focused scaffold tests now cover successful metadata preservation,
  intentional omission behavior, and invalid metadata rejection without
  partial writes.
- The shared skill and package README now document the new CLI options and
  call out that omission is deliberate when metadata is not supplied.

## Verification

Command:

```bash
python3 -m unittest plugins/agent-plugin-creator/tests/test_scaffold_plugin.py -v
```

Result:

- `Ran 14 tests in 1.040s`
- `OK`

Command:

```bash
python3 -m unittest plugins/agent-plugin-creator/tests/test_package.py -v
```

Result:

- `Ran 4 tests in 0.123s`
- `OK`

Command:

```bash
python3 -S -m unittest plugins/agent-plugin-creator/tests/test_scaffold_plugin.py -v
```

Result:

- `Ran 14 tests in 1.042s`
- `OK`

Command:

```bash
python3 -S -m unittest plugins/agent-plugin-creator/tests/test_package.py -v
```

Result:

- `Ran 4 tests in 0.123s`
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
python3 /Users/anatoly.shipitz/.codex/skills/.system/skill-creator/scripts/quick_validate.py plugins/agent-plugin-creator/skills/create-agent-plugin
```

Result:

- `Skill is valid!`

Command:

```bash
git diff --check
```

Result:

- exit code `0`
- no output

## Self-review

- Kept the new metadata strictly portable by writing it only to root
  `plugin.json`, which preserves the existing minimal Claude adapter boundary.
- Validated metadata before `plugin_root.mkdir(...)` so rejection still leaves
  no partially generated package behind.
- Accepted partial author objects because the local schema allows any subset
  of `name`, `email`, and `url`, but still rejected blank and malformed
  values so the scaffolder does not preserve low-quality metadata.
- `quick_validate.py` passed under `python3`; an extra `python3 -S` probe
  failed because that helper imports PyYAML and is not designed as a
  standard-library-only check.
