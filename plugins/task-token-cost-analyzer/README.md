# task-token-cost-analyzer

Analyze the token and process cost of a completed task from local aggregate evidence without network access.

## Usage

```bash
python3 plugins/task-token-cost-analyzer/scripts/analyze_task_cost.py \
  --root plugins/task-token-cost-analyzer \
  --report-out /tmp/task-token-cost-report.md \
  --prompt-out /tmp/task-token-cost-update-prompt.md
```

Add `--events PATH` only when you have a local normalized aggregate export to measure real token totals. Use a root-relative path when the export is stored inside the selected task root, or an absolute path when the normalized export lives elsewhere on disk; relative escapes outside the root are rejected.

## Outputs

- `cost-report.md` renders a stable Markdown report with evidence quality, acceptance coverage, cost breakdown, avoidable costs, recommendations, and limitations.
- `plugin-update-prompt.md` renders a reviewable update prompt for a bounded follow-up change, plus the changelog and task report entry, and does not apply changes automatically.

## Optional Adapters

Do not install hooks as part of this plugin. This plugin does not require hooks. Optional Claude local adapters may collect `SessionStart`, `UserPromptSubmit`, `PostToolUse`, `SubagentStop`, and `Stop` events, but raw API bodies are sensitive and should not be stored in plugin outputs.

Codex normalized export and Compliance API inputs are optional and client/account dependent. Treat them as local imports when available; do not claim a portable Codex hook contract from them.

MCP measurements are limited to tool counts and durations, not automatic LLM token counts.

## Safety

- Keep analysis scoped to an explicitly selected completed task root.
- Exclude prompts, transcripts, raw request bodies, headers, and credentials.
- Keep subagent or reviewer handoff to task-only context instead of full conversation history.
- Review the generated update prompt before acting on it.
