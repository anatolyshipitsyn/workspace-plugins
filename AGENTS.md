# Agent Plugin Repository Workflow

## Purpose

This repository stores portable Agent Plugins for use across projects and
clients, including Codex and Claude Code.

Portable plugin components belong under `plugins/<plugin-name>/` and must
follow the latest published Agent Plugins specification supported by the
repository's local registry. The portable manifest is `plugin.json` at the
plugin root. Skills belong under `skills/`, and portable MCP configuration
belongs in `mcp.json`.

Claude Code compatibility is provided by the minimal client-specific files
`.claude-plugin/plugin.json` and, when needed, `.mcp.json`. Shared skills and
scripts must not be duplicated.

## Development Method

Use Subagent-Driven Development from `obra/superpowers` for every substantial
plugin implementation or change.

The required sequence is:

1. Clarify the problem and produce a bounded design.
2. Obtain approval for the design.
3. Write an implementation plan with independent, verifiable tasks.
4. Create or verify an isolated Git worktree.
5. Create a progress ledger for the plan.
6. Dispatch one fresh implementer subagent per independent task.
7. Require the implementer to add or update tests, run them, self-review, and
   report the result.
8. Run a separate task review for specification compliance and code quality.
9. Resolve review findings through the implementer and perform a scoped
   re-review.
10. After all tasks are complete, run a whole-branch review.
11. Verify the final package and tests before declaring the work complete.

Do not skip the task review or the final review. Do not fix reviewed findings
directly in the controller session; route them through the implementer so the
fix is tested and reviewed.

## Decision Recording

Record durable architectural and workflow decisions in `DECISIONS.md`.
Record implementation progress, rulings, review findings, and fix rounds in
the ledger owned by the active implementation plan.

When a decision is made during implementation, record:

- the decision;
- the context;
- the reason;
- the consequences and possible cost if the decision is wrong.

## Plugin Rules

- Keep each plugin self-contained and independently distributable.
- Keep all package paths inside the plugin root.
- Do not use symlinks as the primary sharing mechanism.
- Do not commit credentials, tokens, passwords, `.env` files, or generated
  secret material.
- Do not embed secrets in MCP `env` or HTTP headers.
- Use `${PLUGIN_ROOT}` and `${PLUGIN_DATA}` according to the portable MCP
  specification.
- Use the Claude-specific path and variable conventions only in Claude
  adapter files.
- Use Semantic Versioning for plugin versions.

## Verification Before Completion

Before declaring a plugin complete, verify at minimum:

- `plugin.json` is valid and conforms to the Agent Plugins schema;
- every discovered `SKILL.md` is valid;
- `mcp.json` and `.mcp.json` are valid when present;
- no package path escapes the plugin root;
- secrets are absent;
- focused tests and runtime smoke tests pass;
- documentation and changelog describe the current behavior;
- `git diff --check` passes.

Static validation does not replace a runtime smoke test for an MCP server.

## External Methodology

`obra/superpowers` is an external development methodology and skill set. Do
not copy its implementation into this repository or treat it as one of the
repository's portable Agent Plugins. Install and update it separately for
each supported client.
