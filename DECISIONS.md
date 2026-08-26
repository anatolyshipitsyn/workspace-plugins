# Repository Decisions

## 2026-08-26: Portable format and release-selection policy

### Decision

- Agent Plugins are the portable format for this repository.
- Codex and Claude Code are the supported clients.
- Shared skills are not duplicated across client adapters.
- Superpowers is external methodology.
- Subagent-Driven Development is required for substantial plugin work.
- The latest published release is selected from a local registry.
- No `--spec-version` option is exposed.

### Context

This repository stores portable plugins meant to work across clients while
remaining self-contained and independently distributable. The
`agent-plugin-creator` package needs a local published-release registry and
bundled schemas that later generation and validation tasks can consume
offline.

### Reason

Using Agent Plugins as the portable contract keeps manifests, skills, and MCP
configuration aligned across clients. Thin client adapters avoid duplicated
shared assets. A local registry allows deliberate release upgrades without
hard-coding a specification version into repository policy or generator flags.

### Consequences

Repository plugins target the registry-selected published release by default.
Shared skills stay in one place, client differences remain minimal, and
schema-version changes flow through explicit registry updates.

### Cost If Wrong

If these decisions are wrong, generated plugins could drift from the upstream
published contract, duplicate files across clients, or force breaking changes
in later generator and validator tasks.
