# workspace-plugins

This repository stores portable Agent Plugins under `plugins/<plugin-name>/`.
Each plugin is meant to stay self-contained, independently distributable, and
compatible across supported clients without copying shared assets between
client-specific adapters.

## Repository layout

```text
workspace-plugins/
├── AGENTS.md
├── DECISIONS.md
├── plugins/
│   └── <plugin-name>/
│       ├── plugin.json
│       ├── skills/
│       ├── mcp.json
│       ├── .claude-plugin/plugin.json
│       ├── .mcp.json
│       ├── scripts/
│       └── specs/
└── tests/
```

- `plugin.json`, `skills/`, and optional `mcp.json` are the portable package.
- `.claude-plugin/plugin.json` and optional `.mcp.json` are Claude Code
  adapters only.
- Shared skills, scripts, and other package assets must exist once at the
  plugin root and must not be duplicated under client adapter directories.

## Release policy

Repository plugins follow the latest published release from the local registry
bundled with the plugin package being used. For
`plugins/agent-plugin-creator`, that registry currently selects published
Agent Plugins `1.0.0` and tracks `1.1.0` only as a draft.

The creator intentionally does not expose `--spec-version`. Release selection
comes from the plugin's local published-release registry so scaffolding and
validation stay deterministic, offline-capable, and aligned with repository
policy.

## Using `agent-plugin-creator`

`plugins/agent-plugin-creator` provides one shared skill plus local scaffold
and validation scripts.

Typical flow:

1. Load the installed `agent-plugin-creator` package in Codex or Claude Code.
2. Ask the shared `create-agent-plugin` skill to propose a plugin tree.
3. Confirm immediately before any files are written.
4. Run the generated package through the local validator.

The creator package README documents the package-level details, including the
bundled registry, offline usage, and the exact scaffold and validator commands.

## Loading checks

Use these checks against an installed package root rather than a repository
checkout path.

### Codex

Confirm the installed package contains:

```text
${PLUGIN_ROOT}/plugin.json
${PLUGIN_ROOT}/skills/
```

If the plugin includes MCP configuration, confirm `${PLUGIN_ROOT}/mcp.json`
exists only when the package needs a portable MCP definition.

### Claude Code

Confirm the same portable files still exist at the package root, plus the
minimal adapter entrypoints:

```text
${PLUGIN_ROOT}/.claude-plugin/plugin.json
${PLUGIN_ROOT}/.mcp.json
```

Only the adapter metadata lives in the Claude-specific files. The shared skill
tree remains under `${PLUGIN_ROOT}/skills/` and must not be copied into
`.claude-plugin/`.

## Repository checks

Before treating a plugin package as complete, verify:

- the package validates against its bundled published schemas;
- every discovered `SKILL.md` is valid;
- no secrets, `.env` files, symlinks that escape the package root, or generated
  artifacts are present;
- documentation describes the current release-selection policy and client
  loading rules;
- focused tests and the repository checks in `AGENTS.md` pass.
