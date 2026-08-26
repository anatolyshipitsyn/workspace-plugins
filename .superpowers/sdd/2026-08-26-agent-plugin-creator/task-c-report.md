# Task C report

## Scope

Completed Task C inside the allowed write set only:

- `tests/test_plugin_suite.py`
- `.superpowers/sdd/2026-08-26-agent-plugin-creator/task-c-report.md`

No existing tests or production files were modified.

## Implementation notes

- Added a repository-level `unittest` discovery bridge in
  `tests/test_plugin_suite.py`.
- The bridge uses `load_tests` plus `importlib.util.spec_from_file_location`
  to load the creator plugin's local unittest modules by explicit file path,
  which avoids the default discovery import problem caused by the
  `agent-plugin-creator` directory name.
- The bridge reuses the existing plugin-local test modules without copying
  assertions or test logic, keeps module names stable, and adds them in a
  deterministic order: scaffold, validator, package.
- The implementation stays offline and only imports local test files already
  committed in the repository.
- Fix round 1 copies the creator plugin into a temporary workspace before
  loading the bridged modules and rebinds their repository-derived `Path`
  constants to that copy. This keeps subprocesses and fixture writes away
  from tracked plugin files without changing the existing tests.
- Added a final bridge assertion that compares the repository registry with
  its pre-suite bytes after all bridged tests complete.

## Verification

Pre-implementation red check:

```text
python3 -m unittest discover -v
```

Result before the bridge existed:

```text
test_scaffold_and_validate_codex_and_claude_plugin_offline (tests.test_end_to_end.EndToEndTest.test_scaffold_and_validate_codex_and_claude_plugin_offline) ... ok
test_latest_release_is_published_and_has_both_schemas (tests.test_registry.RegistryTest.test_latest_release_is_published_and_has_both_schemas) ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.208s

OK
```

Required Task C checks:

```text
python3 -m unittest discover -v
```

```text
Ran 36 tests in 4.378s
OK
```

```text
python3 -m unittest tests.test_plugin_suite -v
```

```text
Ran 34 tests in 4.190s
OK
```

```text
python3 -S -m unittest tests.test_plugin_suite -v
```

```text
Ran 34 tests in 4.200s
OK
```

```text
git diff --check
```

```text
exit 0 with no output
```

Fix-round verification:

```text
python3 -m unittest discover -v
```

```text
Ran 37 tests in 4.308s
OK
```

```text
python3 -m unittest discover -v
```

```text
Ran 37 tests in 4.255s
OK
```

```text
python3 -S -m unittest tests.test_plugin_suite -v
```

```text
Ran 35 tests in 4.037s
OK
```

The focused bridge suite also passed under `python3` in 4.122s with 35 tests. The
registry-unchanged assertion passed at the end of each bridge execution.

Fix-round 2 verification:

```text
python3 -m unittest tests.test_plugin_suite -v
```

```text
Ran 36 tests in 4.062s
OK
```

```text
python3 -m unittest discover -v
```

```text
Ran 38 tests in 4.302s
OK
```

```text
python3 -m unittest discover -v
```

```text
Ran 38 tests in 4.323s
OK
```

```text
python3 -S -m unittest tests.test_plugin_suite -v
```

```text
Ran 36 tests in 4.127s
OK
```

The bridge now temporarily disables bytecode writes while dynamically loading
the plugin test modules and restores the caller's prior setting in `finally`.
The focused bridge suite's restoration assertion passed, and only generated
`__pycache__` directories were removed after verification.

Fix-round 3 verification:

```text
python3 -m unittest discover -v
```

```text
Ran 38 tests in 5.014s
OK
```

```text
python3 -m unittest discover -v
```

```text
Ran 38 tests in 5.016s
OK
```

```text
python3 -S -m unittest tests.test_plugin_suite -v
```

```text
Ran 36 tests in 4.861s
OK
```

`tests/__init__.py` now enables `sys.dont_write_bytecode` before unittest
imports repository test modules and registers cleanup for its own package
cache. The bridge continues to restore the prior bytecode setting in
`finally`; the registry assertion passed and no repository `__pycache__` or
`.pyc` artifacts remained after the runs.

Fix-round 4 verification:

```text
python3 -m unittest discover -v
```

```text
Ran 39 tests in 5.067s
OK
```

```text
python3 -m unittest discover -v
```

```text
Ran 39 tests in 5.103s
OK
```

```text
python3 -S -m unittest tests.test_plugin_suite -v
```

```text
Ran 37 tests in 4.964s
OK
```

`tests/__init__.py` now captures the caller's bytecode flag, suppresses
bytecode during package initialization, restores that flag before package
import returns, and cleans any test-package caches at process exit. The bridge
still restores its temporary import setting in `finally`, and the subprocess
regression confirms ordinary `import tests` preserves the caller's setting.
No repository `__pycache__`/`.pyc` artifacts or registry mutation remained.

Fix-round 4 final artifact check:

```text
find . -type d -name __pycache__ -print
find . -type f -name '*.pyc' -print
```

No output. The cleanup tracks pre-existing bytecode and removes only caches
created during the current test process.

## Self-review

- Confirmed the bridge is limited to repository-level discovery and does not
  alter any creator package implementation or any existing test module.
- Confirmed the bridge loads only the three required plugin-local unittest
  modules and preserves deterministic suite order.
- Confirmed focused plugin-suite execution works under both `python3` and
  `python3 -S`, so the bridge does not depend on site-packages bootstrapping.
- Confirmed default discovery now includes both root tests and the bridged
  plugin-local tests from the repository root command.
- Confirmed the bridged tests execute against a temporary plugin copy and the
  tracked registry remains byte-for-byte unchanged after repeated discovery.
- Confirmed dynamic imports restore `sys.dont_write_bytecode` and no repository
  bytecode caches remain after cleanup.
- Confirmed the package-level guard runs before discovered test imports and
  default discovery leaves no repository bytecode artifacts or registry
  mutation.
- Confirmed ordinary `import tests` restores the caller's prior bytecode flag
  and default discovery remains artifact-free across repeated runs.
