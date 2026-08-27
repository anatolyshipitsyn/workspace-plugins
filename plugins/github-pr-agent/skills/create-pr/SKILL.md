---
name: create-pr
description: Create a GitHub pull request from the current branch, with a concise title and a body explaining why, what changed, and how it was verified.
---

# Create Pull Request

Use this skill when the user asks to create, open, or submit a Pull Request.

1. Inspect `git status`, the current branch, the diff from the appropriate base, and recent commits. Stop if unrelated uncommitted changes make the scope unclear.
2. Determine the repository and base branch. Do not push, publish, or create a PR without the user's request.
3. Run the project's relevant checks before opening the PR. Report failures instead of hiding them.
4. Push the current branch when needed, then use `gh pr create` with a title and Markdown body.
5. The body must lead with motivation, then summarize the net change, verification, and any documentation follow-up. Use repository-relative paths and inline backticks; never include secrets or absolute local paths.
6. Return the PR URL and the exact verification status.

Typical command:

```bash
gh pr create --base <base> --head <branch> --title "<title>" --body-file <generated-body>
```

Ask before adding reviewers, labels, assignees, or changing draft/ready state unless the user explicitly requested those mutations.
