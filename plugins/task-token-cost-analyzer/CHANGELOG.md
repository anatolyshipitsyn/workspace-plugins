# Changelog

## 0.1.0 - 2026-08-27

- Added the portable `analyze-task-token-cost` skill workflow for local Codex and Claude task-cost analysis.
- Added stable Markdown report and update prompt templates for read-only output generation.
- Documented optional hook and export adapter boundaries, including MCP measurement limits and the non-applying update prompt flow.
- Added end-to-end coverage for generated report and update prompt artifacts.
- Made acceptance-matrix client and YAML statuses evidence-bounded with confidence labels instead of promoting weak signals to `pass`.
- Allowed explicit absolute local `--events` inputs outside the selected task root while keeping root-relative event paths contained within that root.
