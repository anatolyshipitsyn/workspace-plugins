from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_TESTS = (
    ("agent_plugin_creator_tests.test_scaffold_plugin", ROOT / "plugins" / "agent-plugin-creator" / "tests" / "test_scaffold_plugin.py"),
    ("agent_plugin_creator_tests.test_validate_plugin", ROOT / "plugins" / "agent-plugin-creator" / "tests" / "test_validate_plugin.py"),
    ("agent_plugin_creator_tests.test_package", ROOT / "plugins" / "agent-plugin-creator" / "tests" / "test_package.py"),
)


def _load_module(module_name: str, path: Path) -> types.ModuleType:
    existing_module = sys.modules.get(module_name)
    if existing_module is not None:
        return existing_module

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to create an import spec for {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_tests(
    loader: unittest.TestLoader,
    standard_tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    del pattern

    suite = unittest.TestSuite()
    suite.addTests(standard_tests)

    for module_name, path in PLUGIN_TESTS:
        suite.addTests(loader.loadTestsFromModule(_load_module(module_name, path)))

    return suite
