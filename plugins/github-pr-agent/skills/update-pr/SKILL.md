---
name: update-pr
description: Update the title and body of one or more GitHub pull requests to describe the current net change without losing important existing context.
---

# Update Pull Request

Resolve the target from an explicit number/URL or the current branch. For ordinary Git, use `gh pr view <branch> --json number`; inspect the PR's current title and body before editing.

Preserve existing images, links, issue references, and other information that remains relevant. Rewrite only the net change between the PR base and head: explain why first, then what changed, verification, and documentation follow-up when applicable. Do not mention abandoned approaches, absolute local paths, secrets, or internal confidential URLs.

After reviewing the proposed text, update with:

```bash
gh pr edit <number> --title "<title>" --body-file <generated-body>
```

Do not post review replies, change reviewers, labels, draft state, or merge state unless explicitly requested.
