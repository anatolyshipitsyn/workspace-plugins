---
name: babysit-pr
description: Monitor an open GitHub pull request until it is merged/closed or user help is required, diagnosing CI, surfacing review feedback, and retrying only likely flaky failures.
---

# PR Babysitter

Use `scripts/gh_pr_watch.py` from this plugin. Accept no argument (infer from the current branch), a PR number, or a PR URL. Monitoring requests use continuous mode:

```bash
python3 <plugin-root>/scripts/gh_pr_watch.py --pr auto --watch
```

Each snapshot is one compact JSON line: green checks collapse into counts, only failing and pending checks are listed, review items carry just `id`, `kind`, `author`, `path`, `line`, `url`, and a truncated `body`, and in continuous mode a snapshot is printed only when the state an agent would act on has changed. Keep those defaults. Use `--all-checks`, `--max-body 0`, or `--print-unchanged` only when a specific diagnosis needs the fuller output, and drop back to the defaults afterwards. Never re-print or re-summarize a snapshot that has not changed.

Inspect each snapshot's `actions` before acting. Check newly surfaced published review feedback before CI and mergeability. Fix only failures clearly caused by the branch; diagnose failed job logs first, fetching only the failing job's log rather than a whole run. For transient infrastructure/network/runner failures, use `--retry-failed-now` only when the snapshot recommends it, with at most three retry cycles per SHA.

For actionable review feedback, inspect the PR state, patch locally on the PR head branch, commit with `codex: address PR review feedback (#<n>)`, push, and restart the watcher. Do not post replies to human-authored comments without explicit confirmation of the exact response. Resolve a thread only when the requester or Codex bot is the author and leave `[from Codex]: ...` with the commit reference.

When a PR is merged, delete its head branch unless the head branch is named `development` or `staging`. Do not delete branches for PRs that were only closed. Do not close/reopen, merge, mark draft/ready, or interact with other humans unless explicitly requested. Stop only when the PR is merged/closed or a permissions, dirty-worktree, ambiguous-review, or exhausted-retry blocker requires user help. A green and review-clean snapshot is a milestone; continue watching while the PR remains open.
