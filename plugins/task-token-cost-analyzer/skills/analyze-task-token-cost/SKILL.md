---
name: analyze-task-token-cost
description: Use when reviewing the token and process cost of a completed task from local Codex or Claude evidence, especially when the agent must stay offline, keep context bounded, and produce a report plus a non-applying update prompt.
---

# Analyze Task Token Cost

Run `python3 plugins/task-token-cost-analyzer/scripts/analyze_task_cost.py --root PATH --report-out PATH --prompt-out PATH [--events PATH]` on an explicitly selected completed task root. The generated report and update prompt are read-only artifacts; do not apply automatically.

## Workflow

1. Confirm the selected task root and any optional event file stay local, scoped, and relevant to the current task only.
2. Run the focused tests in normal and `-S` modes without `-v`; if one fails, save the verbose rerun to a temporary log for diagnosis.
3. Generate the report and update prompt, then perform a local adversarial audit before the first independent review or recommendation.
4. If multiple findings share the same validator, schema, MCP, YAML, or security surface, use one batched validator-fix round.
5. When using a reviewer or subagent, provide task-only context: the current task brief, required interfaces, and referenced artifact paths, not the complete conversation history.
6. Ask the user to review the generated update prompt. It is for proposing a bounded change and changelog/report entry, not for applying edits.

## Guardrails

- Keep raw prompts, transcripts, request bodies, and secrets out of evidence and outputs.
- Do not install hooks, edit `AGENTS.md`, read private client databases, or send events over the network.
- Treat Codex and Claude telemetry imports as optional local inputs.
- Treat MCP as tool counts and durations unless separate normalized token telemetry is provided.

## References

- `references/acceptance-matrix.md` for Codex, Claude, MCP, YAML, and security acceptance areas
- `references/cost-model.md` for measured, derived, estimated, and missing cost rules
- `references/client-guidance.md` for local adapter and privacy boundaries
