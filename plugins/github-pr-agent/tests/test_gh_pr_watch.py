from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
WATCHER_PATH = PLUGIN_ROOT / "scripts" / "gh_pr_watch.py"


def load_watcher():
    spec = importlib.util.spec_from_file_location("gh_pr_watch", WATCHER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to import {WATCHER_PATH}")
    module = importlib.util.module_from_spec(spec)
    previous_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous_dont_write_bytecode
    return module


watcher = load_watcher()


class HeadBranchDeletionPolicyTests(unittest.TestCase):
    def test_deletes_merged_pr_head_branch_unless_it_is_a_protected_branch(self) -> None:
        self.assertTrue(watcher.should_delete_head_branch("feature/my-change"))
        self.assertFalse(watcher.should_delete_head_branch("development"))
        self.assertFalse(watcher.should_delete_head_branch("staging"))
        self.assertFalse(watcher.should_delete_head_branch(""))


class ReviewItemCompactionTests(unittest.TestCase):
    def test_keeps_only_actionable_fields_and_truncates_long_bodies(self) -> None:
        compact = watcher.compact_review_item(
            {
                "id": "inline:7",
                "kind": "inline",
                "body": "x" * 50,
                "path": "src/app.py",
                "line": 12,
                "html_url": "https://github.com/o/r/pull/1#discussion_r7",
                "user": {"login": "reviewer", "id": 4, "avatar_url": "https://example.test/a.png"},
                "reactions": {"total_count": 3},
                "_links": {"self": {"href": "https://api.github.com/x"}},
            },
            max_body=10,
        )

        self.assertEqual(
            compact,
            {
                "id": "inline:7",
                "kind": "inline",
                "author": "reviewer",
                "url": "https://github.com/o/r/pull/1#discussion_r7",
                "body": "xxxxxxxxxx… (+40 chars)",
                "path": "src/app.py",
                "line": 12,
            },
        )

    def test_drops_empty_fields_and_falls_back_to_the_original_line(self) -> None:
        compact = watcher.compact_review_item(
            {"id": 1, "kind": "review", "body": "", "state": "APPROVED", "user": {"login": "bot"}}
        )
        self.assertEqual(compact, {"id": 1, "kind": "review", "author": "bot", "state": "APPROVED"})

        inline = watcher.compact_review_item(
            {"id": 2, "kind": "inline", "body": "fix", "path": "a.py", "original_line": 9}
        )
        self.assertEqual(inline["line"], 9)


class CheckCompactionTests(unittest.TestCase):
    CHECKS = [
        {"name": "unit", "bucket": "pass", "workflow": "ci", "link": "https://example.test/1"},
        {"name": "lint", "bucket": "fail", "workflow": "ci", "link": "https://example.test/2"},
        {"name": "e2e", "bucket": "pending", "workflow": "ci"},
        {"name": "docs", "bucket": "skipping"},
        {"name": "deploy", "bucket": "cancel"},
    ]

    def test_lists_only_checks_that_need_attention(self) -> None:
        summary = watcher.compact_checks(self.CHECKS)

        self.assertEqual(summary["passed"], 1)
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["failed"], 2)
        self.assertEqual(summary["skipped"], 1)
        self.assertEqual(
            [item["name"] for item in summary["items"]], ["lint", "e2e", "deploy"]
        )
        self.assertEqual(
            summary["items"][0],
            {"name": "lint", "bucket": "fail", "workflow": "ci", "link": "https://example.test/2"},
        )

    def test_all_checks_restores_the_full_listing(self) -> None:
        summary = watcher.compact_checks(self.CHECKS, all_checks=True)
        self.assertEqual(len(summary["items"]), len(self.CHECKS))

    def test_missing_bucket_counts_as_pending(self) -> None:
        summary = watcher.compact_checks([{"name": "unknown"}])
        self.assertEqual(summary["pending"], 1)
        self.assertNotIn("skipped", summary)


class SnapshotDigestTests(unittest.TestCase):
    def payload(self, **overrides):
        payload = {
            "pr": {
                "state": "OPEN",
                "isDraft": False,
                "headRefOid": "abc123",
                "mergeable": "MERGEABLE",
                "reviewDecision": "",
            },
            "checks": {
                "passed": 2,
                "failed": 0,
                "pending": 1,
                "items": [{"name": "e2e", "bucket": "pending"}],
            },
            "actions": ["idle"],
        }
        payload.update(overrides)
        return payload

    def test_identical_state_produces_an_identical_digest(self) -> None:
        self.assertEqual(
            watcher.snapshot_digest(self.payload()),
            watcher.snapshot_digest(self.payload()),
        )

    def test_new_head_commit_changes_the_digest(self) -> None:
        moved = self.payload()
        moved["pr"] = {**moved["pr"], "headRefOid": "def456"}
        self.assertNotEqual(
            watcher.snapshot_digest(self.payload()), watcher.snapshot_digest(moved)
        )

    def test_check_bucket_transition_changes_the_digest(self) -> None:
        turned_red = self.payload()
        turned_red["checks"] = {
            "passed": 2,
            "failed": 1,
            "pending": 0,
            "items": [{"name": "e2e", "bucket": "fail"}],
        }
        self.assertNotEqual(
            watcher.snapshot_digest(self.payload()), watcher.snapshot_digest(turned_red)
        )


class PollingIntervalTests(unittest.TestCase):
    def test_backs_off_while_nothing_changes_and_resets_on_change(self) -> None:
        interval = watcher.next_interval(60, 60, 300, changed=False)
        self.assertEqual(interval, 120)
        interval = watcher.next_interval(interval, 60, 300, changed=False)
        self.assertEqual(interval, 240)
        interval = watcher.next_interval(interval, 60, 300, changed=False)
        self.assertEqual(interval, 300)
        self.assertEqual(watcher.next_interval(300, 60, 300, changed=False), 300)
        self.assertEqual(watcher.next_interval(300, 60, 300, changed=True), 60)


class SeenStateTests(unittest.TestCase):
    def test_keeps_only_the_most_recent_ids(self) -> None:
        self.assertEqual(watcher.trim_seen(list(range(10)), limit=3), [7, 8, 9])
        self.assertEqual(watcher.trim_seen([1, 2], limit=5), [1, 2])


class StubbedSnapshotTests(unittest.TestCase):
    """Exercise snapshot()/main() against a stubbed `gh`, never the network."""

    META = {
        "number": 7,
        "url": "https://github.com/owner/repo/pull/7",
        "state": "OPEN",
        "isDraft": False,
        "mergedAt": None,
        "closedAt": None,
        "headRefName": "feature/x",
        "headRefOid": "abc123",
        "baseRefName": "main",
        "mergeable": "MERGEABLE",
        "reviewDecision": "",
    }
    COMMENT = {
        "id": 11,
        "body": "please rename this",
        "html_url": "https://github.com/owner/repo/pull/7#issuecomment-11",
        "user": {"login": "reviewer", "avatar_url": "https://example.test/a.png"},
        "reactions": {"total_count": 0},
    }

    def setUp(self) -> None:
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        for name in ("PLUGIN_DATA", "CLAUDE_PLUGIN_DATA", "TMPDIR"):
            self.addCleanup(self._restore_env, name, os.environ.get(name))
            os.environ.pop(name, None)
        os.environ["PLUGIN_DATA"] = self.workspace.name

        self.addCleanup(setattr, watcher, "gh", watcher.gh)
        self.addCleanup(setattr, watcher, "gh_checks", watcher.gh_checks)
        watcher.gh = self._fake_gh
        watcher.gh_checks = lambda pr: [
            {"name": "unit", "bucket": "pass"},
            {"name": "lint", "bucket": "fail", "link": "https://example.test/2"},
        ]

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def _fake_gh(self, *args):
        if args[:2] == ("pr", "view"):
            return dict(self.META)
        endpoint = args[-1]
        if "issues/7/comments" in endpoint:
            return [dict(self.COMMENT)]
        if "pulls/7/comments" in endpoint:
            return []
        if "pulls/7/reviews" in endpoint:
            return [{"id": 21, "state": "PENDING", "body": "draft", "user": {"login": "reviewer"}}]
        raise AssertionError(f"unexpected gh call: {args}")

    def run_main(self, argv):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = watcher.main(argv)
        lines = [line for line in stdout.getvalue().splitlines() if line]
        return code, [json.loads(line) for line in lines]

    def test_once_emits_one_compact_snapshot_without_pending_reviews(self) -> None:
        code, payloads = self.run_main(["--pr", "7", "--once"])

        self.assertEqual(code, 0)
        self.assertEqual(len(payloads), 1)
        payload = payloads[0]
        self.assertEqual(payload["checks"]["passed"], 1)
        self.assertEqual([item["name"] for item in payload["checks"]["items"]], ["lint"])
        self.assertEqual(
            payload["review_items"],
            [
                {
                    "id": 11,
                    "kind": "comment",
                    "author": "reviewer",
                    "url": "https://github.com/owner/repo/pull/7#issuecomment-11",
                    "body": "please rename this",
                }
            ],
        )
        self.assertEqual(
            payload["actions"], ["process_review_comment", "diagnose_ci_failure"]
        )

    def test_a_review_item_is_reported_only_once(self) -> None:
        self.run_main(["--pr", "7", "--once"])
        _, payloads = self.run_main(["--pr", "7", "--once"])

        self.assertEqual(payloads[0]["review_items"], [])
        self.assertNotIn("process_review_comment", payloads[0]["actions"])

    def test_merged_pr_stops_and_asks_for_head_branch_deletion(self) -> None:
        self.META = {**self.META, "state": "MERGED", "mergedAt": "2026-08-27T10:00:00Z"}
        deleted: list[tuple[str, str]] = []
        self.addCleanup(setattr, watcher, "delete_head_branch", watcher.delete_head_branch)
        watcher.delete_head_branch = lambda repo, branch: deleted.append((repo, branch))

        code, payloads = self.run_main(["--pr", "7"])

        self.assertEqual(code, 0)
        self.assertIn("stop_pr_closed", payloads[0]["actions"])
        self.assertEqual(deleted, [("owner/repo", "feature/x")])
        self.assertEqual(payloads[0]["branch_deletion"]["status"], "deleted")


class TruncationTests(unittest.TestCase):
    def test_short_bodies_are_returned_unchanged(self) -> None:
        self.assertEqual(watcher.truncate("  hello  ", 600), "hello")

    def test_zero_disables_truncation(self) -> None:
        self.assertEqual(watcher.truncate("x" * 5000, 0), "x" * 5000)


if __name__ == "__main__":
    unittest.main()
