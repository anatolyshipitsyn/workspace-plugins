# Agent Plugins

Agent Plugins are the portable contract for this repository. The canonical
package shape is:

- root `plugin.json`
- root `skills/`
- optional root `mcp.json`

The local bundled registry at `${PLUGIN_ROOT}/specs/registry.json`, where
`PLUGIN_ROOT` is the installed plugin directory, selects the only supported
published release:

- latest published release: `1.0.0`
- latest published plugin schema id:
  `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`
- latest published MCP schema id:
  `https://agent-plugins.org/schemas/1.0.0/mcp.schema.json`
- known draft release tracked but not scaffolded: `1.1.0`

Current policy:

- Use the local registry's `latestRelease` for ordinary generation.
- Do not expose or depend on `--spec-version`.
- Reject registry states that point `latestRelease` at a draft or unsupported
  release.
- Use only portable fields in the root manifest. Client-specific metadata
  belongs in adapter files or extension namespaces, not in ad hoc root fields.

The bundled schemas and registry are intentionally local so scaffolding and
validation work offline without fetching upstream content.

Upstream references:

- Repository:
  `https://github.com/agentplugins/agent-plugins-spec`
- Published 1.0.0 spec:
  `https://raw.githubusercontent.com/agentplugins/agent-plugins-spec/main/spec/1.0.0.md`
- Published plugin schema:
  `https://raw.githubusercontent.com/agentplugins/agent-plugins-spec/main/schemas/1.0.0/plugin.schema.json`
- Published MCP schema:
  `https://raw.githubusercontent.com/agentplugins/agent-plugins-spec/main/schemas/1.0.0/mcp.schema.json`
- Draft 1.1.0 spec:
  `https://raw.githubusercontent.com/agentplugins/agent-plugins-spec/main/spec/1.1.0.md`

Do not claim `1.1.0` conformance unless the local registry and bundled schemas
are deliberately updated to a published release.
