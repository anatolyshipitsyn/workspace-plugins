# Agent Plugin Creator Design

## Status

Proposed design for review.

## Goal

Create a portable Agent Plugin named `agent-plugin-creator` that helps an
agent design, scaffold, and validate new Agent Plugins for Codex and Claude
Code without duplicating shared skills or relying on symlinks.

## Decisions

1. Use a skill for the interactive design workflow and deterministic Python
   scripts for file creation and structural validation.
2. Do not expose `--spec-version`. Select `latestRelease` from a local
   registry and never silently select a working draft.
3. Bundle published schemas locally so generation and validation work offline.
4. Keep shared skills and scripts in one package; generate only small client
   adapters where Codex and Claude Code require different metadata or MCP
   configuration.
5. Treat Agent Plugins as the portable contract, Claude Code as a client
   adapter, and Superpowers as an external development methodology.
6. Refuse to overwrite existing files unless explicitly approved.

## Package Layout

```text
plugins/agent-plugin-creator/
├── plugin.json
├── .claude-plugin/plugin.json
├── skills/create-agent-plugin/
│   ├── SKILL.md
│   ├── references/
│   └── assets/templates/
├── specs/<release>/
│   ├── plugin.schema.json
│   └── mcp.schema.json
├── specs/registry.json
├── scripts/scaffold_plugin.py
├── scripts/validate_plugin.py
├── README.md
├── CHANGELOG.md
└── LICENSE
```

The creator does not need an MCP server. Its behavior is implemented by the
skill and local scripts.

## Registry and Release Selection

`specs/registry.json` contains supported release identifiers, the latest
published release, draft identifiers, and upstream source URLs. The generator
loads only `latestRelease` for ordinary generation and rejects a registry that
points to a draft or lacks the corresponding local schemas.

Generated `plugin.json` and `mcp.json` contain the exact canonical schema
identifiers for the selected release. Updating the registry changes defaults
for newly generated plugins only; existing plugins are not rewritten.

The generator does not fetch or execute remote content during normal
generation. Registry updates are deliberate repository changes.

## Skill Workflow

`create-agent-plugin` must:

1. Determine whether the request is for a new or existing plugin.
2. Collect name, purpose, description, author, license, target clients,
   skills, and optional MCP servers.
3. Explain the portable/client boundary and identify Claude adapter files.
4. Show the proposed tree and plan before mutating the target.
5. Require explicit confirmation immediately before creating files.
6. Invoke `scaffold_plugin.py` with validated structured input.
7. Invoke `validate_plugin.py` on the result.
8. Report files, selected published release, validation results, and client
   limitations.

The skill must not claim runtime compatibility merely because JSON validates.
MCP runtime smoke tests remain separate.

## Generator Contract

`scaffold_plugin.py` accepts a destination and structured metadata. It must:

- normalize and validate the plugin name;
- create only requested component directories;
- generate portable `plugin.json`;
- generate `.claude-plugin/plugin.json` when Claude support is requested;
- generate `mcp.json` and `.mcp.json` only when requested;
- use client-specific path placeholders in each MCP file;
- refuse writes outside the destination;
- refuse overwrites by default;
- produce deterministic UTF-8 output.

Portable manifests may contain only fields allowed by the selected schema.
Client-specific data belongs under `extensions` or client adapter files.

## Validator Contract

The validator must cover both schema rules and semantic requirements that JSON
Schema cannot fully express:

- root manifest and matching MCP schema versions;
- immediate-child skill discovery and Agent Skills frontmatter/layout;
- package-root containment and non-escaping symlinks;
- single-token stdio commands and permitted `cwd` forms;
- transport and HTTPS rules for remote MCP;
- reserved `PLUGIN_ROOT` and `PLUGIN_DATA` names;
- absence of credentials, secret material, and unfinished placeholders;
- valid Claude adapter files when present.

Failures identify the file, rule, and corrective action. Independent invalid
components are reported independently where the specification permits it.

## Codex and Claude Code

The portable package is canonical. Codex-compatible clients use root
`plugin.json`, `skills/`, and `mcp.json`. Claude Code compatibility uses
`.claude-plugin/plugin.json`, root-level `skills/`, and `.mcp.json` when needed.
Shared skills are written once. Claude-specific behavior is not presented as
part of the portable Agent Plugins contract.

## Security and Licensing

Do not place credentials in manifests, MCP environment maps, headers, or
templates. Resolve user paths before writing, require confirmation for
overwrites, do not execute generated code, and keep bundled schemas inside the
creator root.

Bundled schemas retain upstream Apache-2.0 attribution. Copied specification
prose or documentation examples retain CC-BY-4.0 attribution. Prefer concise
derived references and upstream links over copying the full specification.

## Verification

Completion requires creator manifest and skill validation, generator tests for
normal/optional generation, latest-release selection, invalid names,
overwrite refusal, and containment, validator tests for malformed manifests,
mismatched schemas, invalid transports, escaping paths, reserved names, and
secrets, generated examples that validate, available-client loading checks,
and `git diff --check`.
