# github-pr-agent

Portable Agent Plugin for the GitHub pull request lifecycle. It ships three
shared skills plus one dependency-free watcher script, and it is designed so an
agent can supervise a PR for a long time without spending tokens on output it
has already read.

| Skill | Purpose |
| --- | --- |
| `create-pr` | Prepare and open a PR with `gh pr create`. |
| `update-pr` | Rewrite title/body for the current net change, preserving still-relevant context. |
| `babysit-pr` | Watch CI, mergeability, and published review feedback until the PR is merged or closed. |

Requires the GitHub CLI (`gh`) with a completed `gh auth login`. The watcher
never merges, closes, replies to people, or changes unrequested PR settings; it
deletes a merged PR's head branch only when that branch is not `development` or
`staging`.

## Package layout

```text
plugins/github-pr-agent/
├── plugin.json                  # portable manifest
├── .claude-plugin/plugin.json   # Claude Code adapter metadata only
├── skills/{create-pr,update-pr,babysit-pr}/SKILL.md
├── scripts/gh_pr_watch.py
└── tests/
```

The skill tree lives once at the package root and is never copied into
`.claude-plugin/`.

## Watcher

```bash
python3 "${PLUGIN_ROOT}/scripts/gh_pr_watch.py" --pr auto --once
python3 "${PLUGIN_ROOT}/scripts/gh_pr_watch.py" --pr auto --watch
python3 "${PLUGIN_ROOT}/scripts/gh_pr_watch.py" --pr 42 --retry-failed-now
```

`--pr` accepts `auto` (infer from the current branch), a PR number, or a PR URL.
Each snapshot is a single compact JSON line:

```json
{"pr": {...}, "checks": {"passed": 12, "failed": 1, "pending": 0, "items": [...]},
 "review_items": [...], "actions": ["diagnose_ci_failure"]}
```

`actions` is the field to branch on: `process_review_comment`,
`diagnose_ci_failure`, `delete_merged_head_branch`, `stop_pr_closed`, `idle`.

### Token-frugal defaults

| Behaviour | Default | Override |
| --- | --- | --- |
| Passing and skipped checks are counted, not listed | on | `--all-checks` |
| Review items reduced to `id`, `kind`, `author`, `path`, `line`, `url`, truncated `body` | 600 chars | `--max-body N` (`0` disables truncation) |
| Continuous mode prints only when the actionable state changes | on | `--print-unchanged` |
| Poll interval doubles while the PR is quiet, resets on any change | 60s → 300s | `--interval`, `--max-interval` |

A review item is reported exactly once. Seen ids are stored under
`${PLUGIN_DATA}/github-pr-agent/pr-<number>.json` (falling back to `$TMPDIR`),
capped at the 500 most recent ids, and are recorded only after the snapshot
carrying them has been printed.

`gh pr checks` exits non-zero for failing, pending, and check-less pull
requests; the watcher reads its JSON anyway instead of aborting the session.

## Checks

```bash
python3 plugins/github-pr-agent/tests/test_gh_pr_watch.py
python3 plugins/github-pr-agent/tests/test_package.py
python3 plugins/agent-plugin-creator/scripts/validate_plugin.py plugins/github-pr-agent
```

The watcher tests cover pure helpers only and never call `gh`, so they run
offline. Watching a real pull request is a separate runtime smoke test.
