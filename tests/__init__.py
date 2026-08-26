"""Repository-level test package."""

import atexit
from pathlib import Path
import sys


# Discovery imports this package before importing any repository test modules.
# Prevent those imports from creating repository-local bytecode artifacts.
sys.dont_write_bytecode = True


def _remove_package_bytecode() -> None:
    cache_dir = Path(__file__).with_name("__pycache__")
    if not cache_dir.is_dir():
        return

    for bytecode_path in cache_dir.glob("*.pyc"):
        bytecode_path.unlink(missing_ok=True)
    try:
        cache_dir.rmdir()
    except OSError:
        pass


atexit.register(_remove_package_bytecode)
