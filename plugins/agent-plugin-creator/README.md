# agent-plugin-creator

`agent-plugin-creator` is a portable Agent Plugin package that helps an agent
design, scaffold, and validate new plugin packages for Codex and Claude Code.
It keeps one shared skill tree, uses bundled published schemas, and relies on
local Python scripts for deterministic offline scaffolding and validation.

## What it includes

- portable root manifest: `plugin.json`
- minimal Claude Code adapter: `.claude-plugin/plugin.json`
- shared skill: `skills/create-agent-plugin/`
- local scripts: `scripts/scaffold_plugin.py` and `scripts/validate_plugin.py`
- bundled release metadata and schemas: `specs/`

## Release policy

The package follows the local registry at
`${PLUGIN_ROOT}/specs/registry.json`, where `PLUGIN_ROOT` is the installed
package directory.

- published release used for scaffolding: `1.0.0`
- portable schema id:
  `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`
- MCP schema id:
  `https://agent-plugins.org/schemas/1.0.0/mcp.schema.json`
- tracked draft only: `1.1.0`

The scaffolder uses the registry's latest published release and does not expose
`--spec-version`.

## Offline usage

The package ships with a local registry and bundled schemas so generation and
validation do not need network access during normal use. Upstream links are
kept for traceability, but the scripts read the local files under
`${PLUGIN_ROOT}/specs/`.

## Installation examples

### Codex

Set `PLUGIN_ROOT` to the installed package directory. For example:

```text
${PLUGIN_ROOT}/
├── plugin.json
├── skills/
└── scripts/
```

Load the package through the Codex client's local plugin workflow so the root
`plugin.json` and shared `skills/` directory stay canonical.

### Claude Code

Set `PLUGIN_ROOT` to the installed package directory. For example:

```text
${PLUGIN_ROOT}/
├── plugin.json
├── .claude-plugin/plugin.json
├── skills/
└── scripts/
```

Load the same package through Claude Code's local plugin workflow. The shared
skills stay at the package root; `.claude-plugin/plugin.json` is only the
adapter entrypoint.

## Usage flow

1. Ask the shared `create-agent-plugin` skill to create a new plugin or update
   an existing one.
2. Provide the plugin name, purpose, description, license, target clients,
   shared skills, and optional MCP server definitions.
3. Review the proposed tree and confirm immediately before any files are
   written.
4. Run structural validation after generation or edits.

Optional portable metadata flags:

- `--license LICENSE` writes `plugin.json["license"]` only when supplied.
- `--author-name NAME` sets `plugin.json["author"]["name"]`.
- `--author-email EMAIL` sets `plugin.json["author"]["email"]`.
- `--author-url URL` sets `plugin.json["author"]["url"]`.

When license or author details are not supplied, the scaffolder omits those
manifest fields intentionally. It does not guess defaults.

Example scaffold invocation:

```bash
python3 "${PLUGIN_ROOT}/scripts/scaffold_plugin.py" \
  --destination /tmp/plugins \
  --name demo-plugin \
  --description "Demo portable plugin" \
  --clients codex,claude \
  --license MIT \
  --author-name "Ada Lovelace" \
  --author-email "ada@example.com" \
  --author-url "https://example.com/ada" \
  --with-skill review-skill
```

Example validation invocation:

```bash
python3 "${PLUGIN_ROOT}/scripts/validate_plugin.py" \
  /tmp/plugins/demo-plugin
```

Static validation checks manifests, paths, skills, and secret hygiene. It does
not prove MCP runtime behavior; if a generated package includes an MCP server,
run a separate runtime smoke test.

## No-secret policy

- Do not commit credentials, tokens, passwords, `.env` files, or generated
  secret material.
- Do not embed secrets in `plugin.json`, `mcp.json`, `.mcp.json`, HTTP
  headers, examples, or docs.
- Use placeholders or out-of-band configuration for sensitive values.

## Upstream references

- Agent Plugins repository:
  `https://github.com/agentplugins/agent-plugins-spec`
- Agent Plugins 1.0.0 spec:
  `https://raw.githubusercontent.com/agentplugins/agent-plugins-spec/main/spec/1.0.0.md`
- Agent Plugins 1.1.0 draft:
  `https://raw.githubusercontent.com/agentplugins/agent-plugins-spec/main/spec/1.1.0.md`

## Attribution

- Bundled Agent Plugins schemas under `${PLUGIN_ROOT}/specs/1.0.0/` retain Apache-2.0
  attribution. See `${PLUGIN_ROOT}/specs/1.0.0/NOTICE.md`.
- Any copied specification prose or copied examples must retain CC-BY-4.0
  attribution.
