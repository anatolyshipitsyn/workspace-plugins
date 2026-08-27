from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGINS_DIR = ROOT / "plugins"
CLAUDE_MANIFEST = ROOT / ".claude-plugin" / "marketplace.json"
CODEX_MANIFEST = ROOT / ".agents" / "plugins" / "marketplace.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _packaged_plugin_names() -> set[str]:
    return {
        entry.name
        for entry in PLUGINS_DIR.iterdir()
        if entry.is_dir() and (entry / "plugin.json").is_file()
    }


def _claude_entries() -> list[dict]:
    return _load(CLAUDE_MANIFEST)["plugins"]


def _codex_entries() -> list[dict]:
    return _load(CODEX_MANIFEST)["plugins"]


class MarketplaceManifestTest(unittest.TestCase):
    maxDiff = None

    def test_claude_manifest_lists_every_packaged_plugin(self) -> None:
        listed = {entry["name"] for entry in _claude_entries()}
        self.assertEqual(listed, _packaged_plugin_names())

    def test_codex_manifest_lists_every_packaged_plugin(self) -> None:
        listed = {entry["name"] for entry in _codex_entries()}
        self.assertEqual(listed, _packaged_plugin_names())

    def test_manifest_sources_resolve_inside_the_repository(self) -> None:
        sources = [(entry["name"], entry["source"]) for entry in _claude_entries()]
        sources += [
            (entry["name"], entry["source"]["path"]) for entry in _codex_entries()
        ]

        for name, source in sources:
            with self.subTest(plugin=name, source=source):
                self.assertTrue(source.startswith("./"), "source must be repo-relative")
                resolved = (ROOT / source).resolve()
                self.assertTrue(resolved.is_relative_to(ROOT.resolve()))
                self.assertTrue((resolved / "plugin.json").is_file())

    def test_marketplace_names_match(self) -> None:
        self.assertEqual(_load(CLAUDE_MANIFEST)["name"], _load(CODEX_MANIFEST)["name"])

    def test_entries_do_not_duplicate_the_package_version(self) -> None:
        for entry in _claude_entries() + _codex_entries():
            with self.subTest(plugin=entry["name"]):
                self.assertNotIn("version", entry)


if __name__ == "__main__":
    unittest.main()
