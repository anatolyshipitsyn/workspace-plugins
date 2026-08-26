from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import tempfile
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_TESTS = (
    ("agent_plugin_creator_tests.test_scaffold_plugin", ROOT / "plugins" / "agent-plugin-creator" / "tests" / "test_scaffold_plugin.py"),
    ("agent_plugin_creator_tests.test_validate_plugin", ROOT / "plugins" / "agent-plugin-creator" / "tests" / "test_validate_plugin.py"),
    ("agent_plugin_creator_tests.test_package", ROOT / "plugins" / "agent-plugin-creator" / "tests" / "test_package.py"),
)
REGISTRY_PATH = ROOT / "plugins" / "agent-plugin-creator" / "specs" / "registry.json"
ORIGINAL_REGISTRY = REGISTRY_PATH.read_bytes()
ORIGINAL_DONT_WRITE_BYTECODE = sys.dont_write_bytecode
_ISOLATED_WORKSPACES: list[tempfile.TemporaryDirectory[str]] = []


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


def _load_isolated_plugin_tests() -> list[types.ModuleType]:
    previous_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        workspace = tempfile.TemporaryDirectory(prefix="agent-plugin-creator-tests-")
        _ISOLATED_WORKSPACES.append(workspace)

        isolated_root = Path(workspace.name)
        isolated_plugin = isolated_root / "plugins" / "agent-plugin-creator"
        source_plugin = ROOT / "plugins" / "agent-plugin-creator"

        shutil.copytree(
            source_plugin,
            isolated_plugin,
            ignore=shutil.ignore_patterns("__pycache__"),
        )

        modules = []
        for module_name, path in PLUGIN_TESTS:
            module = _load_module(module_name, path)
            for name, value in vars(module).items():
                if isinstance(value, Path):
                    try:
                        relative_path = value.relative_to(ROOT)
                    except ValueError:
                        continue
                    setattr(module, name, isolated_root / relative_path)
            modules.append(module)
        return modules
    finally:
        sys.dont_write_bytecode = previous_dont_write_bytecode


def load_tests(
    loader: unittest.TestLoader,
    standard_tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    del pattern

    suite = unittest.TestSuite()
    suite.addTests(standard_tests)

    for module in _load_isolated_plugin_tests():
        suite.addTests(loader.loadTestsFromModule(module))

    class DiscoveryIsolationTest(unittest.TestCase):
        def test_bridged_tests_leave_repository_registry_unchanged(self) -> None:
            self.assertEqual(REGISTRY_PATH.read_bytes(), ORIGINAL_REGISTRY)

        def test_bridge_restores_bytecode_setting(self) -> None:
            self.assertEqual(sys.dont_write_bytecode, ORIGINAL_DONT_WRITE_BYTECODE)

    suite.addTests(loader.loadTestsFromTestCase(DiscoveryIsolationTest))

    return suite
