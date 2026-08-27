# Repository Decisions

## 2026-08-27: Repository is a local plugin marketplace for both clients

### Decision

- The repository root carries two marketplace manifests:
  `.claude-plugin/marketplace.json` for Claude Code and
  `.agents/plugins/marketplace.json` for Codex.
- Both manifests reference packages by relative path under `plugins/` and
  never duplicate package content.
- Adding a plugin to `plugins/` requires adding it to both manifests.

### Context

Plugin packages were self-contained but there was no supported way to connect
the workspace itself to a client. Claude Code resolves a local marketplace from
`.claude-plugin/marketplace.json`; Codex resolves one from
`.agents/plugins/marketplace.json`. Without them, each package had to be loaded
ad hoc.

### Reason

Two small root-level manifests make the checkout installable in both clients
with one command each, while keeping the portable package layout and the
no-duplication rule unchanged. Codex resolves the portable root `plugin.json`
directly, so no Codex-specific package adapter is needed.

### Consequences

The workspace is installable as marketplace `workspace-plugins` in both
clients, from GitHub or from a local checkout. A GitHub source only exposes
committed and pushed manifests. Both clients copy an installed package into a
versioned cache rather than reading the checkout, so local edits need an
explicit refresh: in Codex re-running `codex plugin add` re-copies the
snapshot, while Claude Code has no refresh that works at an unchanged version
and needs `claude plugin uninstall` followed by `claude plugin install`. New
plugins must be registered in both manifests to become visible, which
`tests/test_marketplace_manifests.py` enforces.

### Cost If Wrong

If a client changes its marketplace manifest location or schema, the affected
manifest must be updated; packages under `plugins/` are unaffected because the
manifests hold no package content. If a plugin is added to only one manifest,
it silently stays invisible in the other client.

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

## 2026-08-27: Task analyzer repository integration boundary

### Decision

- `task-token-cost-analyzer` is an optional repository package, not a mandatory
  repository hook or client dependency.
- The analyzer reports aggregate-only local evidence by default and marks
  missing telemetry as estimated or missing instead of pretending precision.
- Generated update prompts remain review artifacts with a "do not apply automatically" rule.

### Context

Task 4 integrates the analyzer into repository discovery, documentation, and
final package gates. The repository already supports multiple portable plugins,
so the analyzer must fit the same offline, self-contained workflow without
widening repository policy.

### Reason

Keeping the analyzer optional preserves portability across clients and local
setups. Aggregate-only defaults avoid overclaiming token accuracy when no
normalized telemetry exists. Non-applying update prompts keep the package in a
read-only advisory role instead of silently self-modifying the repository.

### Consequences

Repository docs must describe the optional adapter boundary, instruct users not
to install hooks, and keep adversarial/package checks local. Root discovery and
validation must include the analyzer package without duplicating shared code or
requiring network access.

### Cost If Wrong

If these decisions are wrong, the repository could imply mandatory hooks,
pretend estimated telemetry is exact, or let generated prompts cross the line
from recommendation into automatic repository edits.

## 2026-08-27: Task analyzer external-event contract and evidence-bounded acceptance matrix

### Decision

- Root-relative `--events` paths remain confined to the selected task root.
- Separate local telemetry files outside the task root are accepted only through
  an explicit absolute path.
- The acceptance matrix reports `pass` only when the selected evidence shows the
  required area-specific checks; partial signals stay `applicable` with a
  confidence label instead of being promoted from weak heuristics.

### Context

The final review found two contract mismatches in `task-token-cost-analyzer`:
the analyzer treated any measured Codex/Claude client or any YAML file as a
passing acceptance result, and it rejected realistic local telemetry imports
stored next to, rather than inside, the selected task root.

### Reason

Allowing only absolute external event paths preserves the convenient root-local
workflow while keeping accidental relative path escapes blocked. Requiring
observed check coverage for acceptance `pass` keeps the matrix honest about
what the selected local evidence actually demonstrates.

### Consequences

Docs and skill guidance must explain the split: root-relative for in-root
telemetry, absolute for separate local exports. Regression tests must cover the
allowed absolute import, the rejected relative escape, and the conservative
matrix statuses for partial Codex/Claude/YAML evidence.

### Cost If Wrong

If this decision is wrong, users may still need to copy local telemetry into
task roots, or the matrix may continue overstating client and YAML coverage
from evidence that does not prove the advertised workflow.
