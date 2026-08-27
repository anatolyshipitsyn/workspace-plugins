# Client Guidance

This plugin is optional and offline-safe.

## Codex

- Run the analyzer only on an explicitly selected completed task path.
- Import usage or event exports only after mapping them to the normalized aggregate event shape.
- Use a root-relative `--events` path only for telemetry stored inside the selected task root; use an absolute path for a separate local export outside the root.
- Keep generated reports separate from source evidence and review them before acting on any update prompt.

## Claude Code

- Use the shared package files from the portable plugin root.
- Keep `.claude-plugin/plugin.json` as metadata only.
- Do not duplicate skills, scripts, or MCP configuration under the Claude adapter.

## Privacy

- Exclude prompts, transcripts, raw request bodies, headers, and credentials.
- Prefer relative paths, file counts, line counts, and numeric token totals.
- Reject malformed or secret-bearing telemetry instead of echoing it into output.
