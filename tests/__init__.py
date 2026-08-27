"""Repository-level test package."""

import atexit
from pathlib import Path
import sys


_TEST_ROOT = Path(__file__).parent
_BYTECODE_ROOTS = (
    _TEST_ROOT,
    _TEST_ROOT.parent / "plugins" / "agent-plugin-creator" / "tests",
)
_PRIOR_DONT_WRITE_BYTECODE = sys.dont_write_bytecode

# Discovery imports this package before importing any repository test modules.
# Prevent those imports from creating repository-local bytecode artifacts.
sys.dont_write_bytecode = True


def _remove_test_bytecode() -> None:
    for bytecode_root in _BYTECODE_ROOTS:
        for bytecode_path in bytecode_root.rglob("*.pyc"):
            bytecode_path.unlink(missing_ok=True)
        for cache_dir in sorted(bytecode_root.rglob("__pycache__"), reverse=True):
            try:
                cache_dir.rmdir()
            except OSError:
                continue


atexit.register(_remove_test_bytecode)

# Ordinary callers must observe the same process-wide setting they provided.
sys.dont_write_bytecode = _PRIOR_DONT_WRITE_BYTECODE
