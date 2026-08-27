from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "plugins" / "agent-plugin-creator" / "specs" / "registry.json"
ORIGINAL_REGISTRY = REGISTRY_PATH.read_bytes()
ORIGINAL_DONT_WRITE_BYTECODE = sys.dont_write_bytecode
_ISOLATED_WORKSPACES: list[tempfile.TemporaryDirectory[str]] = []


def discover_plugin_tests() -> list[tuple[str, Path]]:
    plugin_tests: list[tuple[str, Path]] = []
    for plugin_root in sorted((ROOT / "plugins").glob("*")):
        tests_root = plugin_root / "tests"
        if not tests_root.is_dir():
            continue
        module_prefix = f"{plugin_root.name.replace('-', '_')}_tests"
        for path in sorted(tests_root.glob("test_*.py")):
            plugin_tests.append((f"{module_prefix}.{path.stem}", path))
    return plugin_tests


def _load_module(module_name: str, path: Path) -> types.ModuleType:
    sys.modules.pop(module_name, None)

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to create an import spec for {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _rewrite_isolated_value(value: object, isolated_root: Path) -> object:
    if isinstance(value, Path):
        try:
            relative_path = value.relative_to(ROOT)
        except ValueError:
            return value
        return isolated_root / relative_path
    if isinstance(value, tuple):
        return tuple(_rewrite_isolated_value(item, isolated_root) for item in value)
    if isinstance(value, list):
        return [_rewrite_isolated_value(item, isolated_root) for item in value]
    if isinstance(value, set):
        return {_rewrite_isolated_value(item, isolated_root) for item in value}
    if isinstance(value, dict):
        return {
            key: _rewrite_isolated_value(item, isolated_root) for key, item in value.items()
        }
    return value


class PluginDiscoveryBridgeTests(unittest.TestCase):
    def test_repeated_load_tests_uses_fresh_modules_for_the_second_workspace(self) -> None:
        loader = unittest.TestLoader()

        first_suite = load_tests(loader, unittest.TestSuite(), None)
        first_module = sys.modules["task_token_cost_analyzer_tests.test_package"]
        first_plugin_root = first_module.PLUGIN_ROOT

        second_suite = load_tests(loader, unittest.TestSuite(), None)
        second_module = sys.modules["task_token_cost_analyzer_tests.test_package"]
        second_plugin_root = second_module.PLUGIN_ROOT

        self.assertGreater(first_suite.countTestCases(), 0)
        self.assertGreater(second_suite.countTestCases(), 0)
        self.assertIsNot(first_module, second_module)
        self.assertNotEqual(first_plugin_root, second_plugin_root)
        self.assertTrue(second_plugin_root.is_dir())
        self.assertNotEqual(second_plugin_root.parents[1], ROOT)


def _load_isolated_plugin_tests() -> list[types.ModuleType]:
    previous_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        workspace = tempfile.TemporaryDirectory(prefix="repository-plugin-tests-")
        _ISOLATED_WORKSPACES.append(workspace)
        isolated_root = Path(workspace.name)
        shutil.copytree(
            ROOT / "plugins",
            isolated_root / "plugins",
            ignore=shutil.ignore_patterns("__pycache__"),
        )

        modules = []
        for module_name, path in discover_plugin_tests():
            module = _load_module(module_name, path)
            for name, value in vars(module).items():
                rewritten = _rewrite_isolated_value(value, isolated_root)
                if rewritten is not value:
                    setattr(module, name, rewritten)
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
        def test_import_tests_preserves_flag_and_cleans_test_bytecode(self) -> None:
            result = subprocess.run(
                [
                    sys.executable,
                    "-S",
                    "-c",
                    (
                        "from pathlib import Path; "
                        "import sys; "
                        "root = Path.cwd(); "
                        "root_cache = root / 'tests' / '__pycache__'; "
                        "plugin_cache = root / 'plugins' / 'agent-plugin-creator' / 'tests' / '__pycache__'; "
                        "root_cache.mkdir(parents=True, exist_ok=True); "
                        "plugin_cache.mkdir(parents=True, exist_ok=True); "
                        "(root_cache / 'task-c-sentinel.pyc').write_bytes(b''); "
                        "(plugin_cache / 'task-c-sentinel.pyc').write_bytes(b''); "
                        "sys.dont_write_bytecode = False; "
                        "import tests; "
                        "assert sys.dont_write_bytecode is False"
                    ),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((ROOT / "tests" / "__pycache__" / "task-c-sentinel.pyc").exists())
            self.assertFalse(
                (
                    ROOT
                    / "plugins"
                    / "agent-plugin-creator"
                    / "tests"
                    / "__pycache__"
                    / "task-c-sentinel.pyc"
                ).exists()
            )

        def test_bridged_tests_leave_repository_registry_unchanged(self) -> None:
            self.assertEqual(REGISTRY_PATH.read_bytes(), ORIGINAL_REGISTRY)

        def test_bridge_restores_bytecode_setting(self) -> None:
            self.assertEqual(sys.dont_write_bytecode, ORIGINAL_DONT_WRITE_BYTECODE)

    suite.addTests(loader.loadTestsFromTestCase(DiscoveryIsolationTest))

    return suite
