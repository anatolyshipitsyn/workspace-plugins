# Changelog

## 0.1.0 - 2026-08-27

- Imported the `github-pr-agent` package from a local Codex-only plugin as a
  portable Agent Plugin with a minimal Claude Code adapter.
- Added the shared `create-pr`, `update-pr`, and `babysit-pr` skills.
- Reduced watcher output: passing and skipped checks collapse into counts,
  review items keep only actionable fields with a truncated body, and
  continuous mode prints a snapshot only when the actionable state changes.
- Added quiet-period poll backoff up to `--max-interval`.
- Read `gh pr checks` JSON even when the command exits non-zero, so failing,
  pending, and check-less pull requests no longer abort the watcher.
- Moved watcher state to `${PLUGIN_DATA}` with a bounded seen-comment list, and
  record seen ids only after the snapshot carrying them is printed.
- Added package and watcher tests.
