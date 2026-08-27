#!/usr/bin/env python3
"""Dependency-free, token-frugal PR watcher for the github-pr-agent plugin.

Every snapshot is written to stdout as one compact JSON line. The watcher keeps
that line small on purpose: agents read this output, so raw GitHub API objects
and green check listings are collapsed instead of forwarded.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

PROTECTED_HEAD_BRANCHES = {"development", "staging"}
DEFAULT_MAX_BODY = 600
SEEN_LIMIT = 500
PR_FIELDS = (
    "number,url,state,isDraft,mergedAt,closedAt,headRefName,headRefOid,"
    "baseRefName,mergeable,reviewDecision"
)
CHECK_FIELDS = "name,state,bucket,link,workflow"


def gh(*args):
    process = subprocess.run(["gh", *args], text=True, capture_output=True)
    if process.returncode:
        raise RuntimeError(process.stderr.strip() or "gh command failed")
    return json.loads(process.stdout) if process.stdout.strip() else {}


def gh_checks(pr):
    """Read checks tolerantly: `gh pr checks` exits non-zero on failing,
    pending, and check-less pull requests while still printing usable JSON."""
    process = subprocess.run(
        ["gh", "pr", "checks", pr, "--json", CHECK_FIELDS],
        text=True,
        capture_output=True,
    )
    if process.stdout.strip():
        try:
            payload = json.loads(process.stdout)
        except ValueError:
            payload = None
        if isinstance(payload, list):
            return payload
    if process.returncode and "no checks" not in process.stderr.lower():
        raise RuntimeError(process.stderr.strip() or "gh pr checks failed")
    return []


def should_delete_head_branch(branch):
    return bool(branch) and branch not in PROTECTED_HEAD_BRANCHES


def delete_head_branch(repo, branch):
    gh("api", "--method", "DELETE", f"repos/{repo}/git/refs/heads/{branch}")


def repo_of(meta):
    return meta.get("url", "").split("github.com/")[-1].split("/pull/")[0]


def target(value):
    if value != "auto":
        return value
    return str(gh("pr", "view", "--json", "number")["number"])


def truncate(text, max_body):
    text = (text or "").strip()
    if max_body <= 0 or len(text) <= max_body:
        return text
    return f"{text[:max_body]}… (+{len(text) - max_body} chars)"


def compact_review_item(item, max_body=DEFAULT_MAX_BODY):
    """Reduce a GitHub comment/review object to what a reviewer must act on."""
    compact = {
        "id": item.get("id"),
        "kind": item.get("kind"),
        "author": (item.get("user") or {}).get("login"),
        "url": item.get("html_url"),
        "body": truncate(item.get("body"), max_body),
    }
    if item.get("path"):
        compact["path"] = item["path"]
        line = item.get("line") or item.get("original_line")
        if line:
            compact["line"] = line
    if item.get("state"):
        compact["state"] = item["state"]
    return {key: value for key, value in compact.items() if value not in (None, "")}


def compact_checks(checks, all_checks=False):
    """Count every check, list only the ones that still need attention."""
    passed = pending = failed = skipped = 0
    items = []
    for check in checks:
        bucket = check.get("bucket") or "pending"
        if bucket == "pass":
            passed += 1
        elif bucket == "pending":
            pending += 1
        elif bucket == "skipping":
            skipped += 1
        else:
            failed += 1
        if all_checks or bucket not in ("pass", "skipping"):
            item = {"name": check.get("name"), "bucket": bucket}
            for key in ("workflow", "link"):
                if check.get(key):
                    item[key] = check[key]
            items.append(item)
    summary = {"passed": passed, "failed": failed, "pending": pending, "items": items}
    if skipped:
        summary["skipped"] = skipped
    return summary


def snapshot_digest(data):
    """Stable fingerprint of the state an agent would act on."""
    pr = data["pr"]
    checks = data["checks"]
    return json.dumps(
        [
            pr.get("state"),
            pr.get("isDraft"),
            pr.get("headRefOid"),
            pr.get("mergeable"),
            pr.get("reviewDecision"),
            checks["passed"],
            checks["failed"],
            checks["pending"],
            sorted(f"{item.get('name')}:{item.get('bucket')}" for item in checks["items"]),
            data["actions"],
        ],
        sort_keys=True,
    )


def next_interval(current, base, max_interval, changed):
    """Poll at `base` while the PR moves, back off while it is quiet."""
    if changed:
        return base
    return min(max_interval, max(base, current) * 2)


def trim_seen(ids, limit=SEEN_LIMIT):
    return list(ids)[-limit:] if limit > 0 else list(ids)


def state_path(number):
    base = (
        os.environ.get("PLUGIN_DATA")
        or os.environ.get("CLAUDE_PLUGIN_DATA")
        or os.environ.get("TMPDIR")
        or "/tmp"
    )
    directory = os.path.join(base, "github-pr-agent")
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, f"pr-{number}.json")


def load_seen(path):
    try:
        with open(path) as stream:
            return list(json.load(stream).get("comments", []))
    except (OSError, ValueError):
        return []


def save_seen(path, ids):
    with open(path, "w") as stream:
        json.dump({"comments": trim_seen(ids)}, stream)


def as_list(payload):
    return payload if isinstance(payload, list) else []


def collect_review_items(repo, number):
    items = [
        {**item, "kind": "comment"}
        for item in as_list(gh("api", f"repos/{repo}/issues/{number}/comments?per_page=100"))
    ]
    items += [
        {**item, "kind": "inline", "id": f"inline:{item.get('id')}"}
        for item in as_list(gh("api", f"repos/{repo}/pulls/{number}/comments?per_page=100"))
    ]
    # Pending reviews are intentionally excluded until the reviewer submits them.
    items += [
        {**item, "kind": "review", "id": f"review:{item.get('id')}"}
        for item in as_list(gh("api", f"repos/{repo}/pulls/{number}/reviews?per_page=100"))
        if item.get("state") != "PENDING"
    ]
    return items


def snapshot(pr, max_body=DEFAULT_MAX_BODY, all_checks=False):
    """Return (payload, state_file, seen_ids); the caller persists seen ids
    only after the payload has been printed, so nothing is silently dropped."""
    meta = gh("pr", "view", pr, "--json", PR_FIELDS)
    checks = compact_checks(gh_checks(pr), all_checks=all_checks)
    repo = repo_of(meta)
    items = collect_review_items(repo, meta["number"])

    path = state_path(meta["number"])
    seen = load_seen(path)
    known = set(seen)
    fresh = [item for item in items if item.get("id") not in known]
    seen += [item.get("id") for item in fresh]

    actions = []
    if meta.get("mergedAt"):
        actions.append("stop_pr_closed")
        if should_delete_head_branch(meta.get("headRefName", "")):
            actions.append("delete_merged_head_branch")
    elif meta.get("state") == "CLOSED":
        actions.append("stop_pr_closed")
    if fresh:
        actions.append("process_review_comment")
    if checks["failed"]:
        actions.append("diagnose_ci_failure")
    if not checks["failed"] and not checks["pending"] and not fresh and meta.get("state") == "OPEN":
        actions.append("idle")

    payload = {
        "pr": meta,
        "checks": checks,
        "review_items": [compact_review_item(item, max_body) for item in fresh],
        "actions": actions,
    }
    return payload, path, seen


def emit(payload):
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr", default="auto")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--retry-failed-now", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--max-interval", type=int, default=300)
    parser.add_argument("--max-body", type=int, default=DEFAULT_MAX_BODY)
    parser.add_argument("--all-checks", action="store_true")
    parser.add_argument("--print-unchanged", action="store_true")
    return parser.parse_args(argv)


def retry_failed(pr, args):
    payload, path, seen = snapshot(pr, args.max_body, args.all_checks)
    repo = repo_of(payload["pr"])
    runs = gh(
        "api",
        f"repos/{repo}/actions/runs?head_sha={payload['pr']['headRefOid']}&per_page=100",
    ).get("workflow_runs", [])
    retried = []
    for run in runs:
        if run.get("conclusion") == "failure":
            subprocess.run(["gh", "run", "rerun", str(run["id"]), "--failed"], check=True)
            retried.append(run["id"])
    save_seen(path, seen)
    emit({"action": "retry_requested", "run_ids": retried})
    return 0


def main(argv=None):
    args = parse_args(argv)
    try:
        pr = target(args.pr)
    except Exception as exc:
        emit({"error": str(exc)})
        return 2

    if args.retry_failed_now:
        return retry_failed(pr, args)

    interval = max(10, args.interval)
    base_interval = interval
    max_interval = max(interval, args.max_interval)
    previous_digest = None

    while True:
        try:
            payload, path, seen = snapshot(pr, args.max_body, args.all_checks)
        except Exception as exc:
            emit({"error": str(exc)})
            return 2

        if "delete_merged_head_branch" in payload["actions"]:
            branch = payload["pr"]["headRefName"]
            try:
                delete_head_branch(repo_of(payload["pr"]), branch)
                payload["branch_deletion"] = {"status": "deleted", "branch": branch}
            except Exception as exc:
                payload["branch_deletion"] = {"status": "failed", "error": str(exc)}
                save_seen(path, seen)
                emit(payload)
                return 2

        digest = snapshot_digest(payload)
        changed = digest != previous_digest or bool(payload["review_items"])
        stop = args.once or "stop_pr_closed" in payload["actions"]
        if changed or stop or args.print_unchanged:
            save_seen(path, seen)
            emit(payload)
        previous_digest = digest

        if stop:
            return 0
        interval = next_interval(interval, base_interval, max_interval, changed)
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
