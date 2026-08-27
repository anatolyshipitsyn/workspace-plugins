from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_registry() -> dict[str, object]:
    registry_path = ROOT / "plugins" / "agent-plugin-creator" / "specs" / "registry.json"
    with registry_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class RegistryTest(unittest.TestCase):
    def test_latest_release_is_published_and_has_both_schemas(self) -> None:
        registry = load_registry()
        latest_release = registry["latestRelease"]
        self.assertIn(latest_release, registry["supportedReleases"])
        self.assertNotIn(latest_release, registry["draftReleases"])

        release_dir = ROOT / "plugins" / "agent-plugin-creator" / "specs" / str(latest_release)
        self.assertTrue((release_dir / "plugin.schema.json").is_file())
        self.assertTrue((release_dir / "mcp.schema.json").is_file())


if __name__ == "__main__":
    unittest.main()
