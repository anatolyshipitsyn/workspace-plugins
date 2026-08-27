# Acceptance Matrix

Use this matrix to classify task evidence without inventing coverage.

## Status values

- `applicable`
- `pass`
- `fail`
- `not observed`
- `not applicable`

## Required areas

| Area | Checks |
| --- | --- |
| Codex | Skill discovery, bounded context, worktree and SDD boundaries, concise verification, no unsupported telemetry assumptions |
| Claude | Adapter discovery, shared skill paths, Claude-specific variable conventions, equivalent offline workflow |
| MCP | Transport semantics, header and URL safety, placeholder policy, runtime smoke-test status, no secret embedding |
| YAML | Valid frontmatter, scalar typing, quoted and block scalar behavior, malformed input handling |
| Security | Redaction, path containment, no credential echo, aggregate-only reports, no destructive writes |

## Evidence rules

- Prefer measured evidence over inferred evidence.
- Mark missing telemetry as `missing` or `not observed`.
- Keep raw prompts, transcripts, request bodies, and secrets out of the matrix.
