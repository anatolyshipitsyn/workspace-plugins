---
name: create-agent-plugin
description: Create or update a portable Agent Plugin package for Codex and Claude Code when the request needs shared skills, client adapters, and local schema-aware scaffolding.
license: Apache-2.0
---

Design the package before you write anything.

- First decide whether the request targets a new plugin or an existing plugin update.
- Collect the plugin name, purpose, concise description, optional portable license, optional author metadata, target clients, shared skills, and any MCP servers that must be packaged.
- Explain the boundary: portable assets live at the plugin root, while Claude Code differences stay in `.claude-plugin/` or `.mcp.json`.
- Show the proposed tree, note which files are shared, and pause for explicit confirmation immediately before mutation.

Use deterministic local scripts from the installed plugin root. Set
`PLUGIN_ROOT` to the directory containing this skill's `skills/` and `scripts/`
directories, then run:

- `python3 "${PLUGIN_ROOT}/scripts/scaffold_plugin.py"` for package creation.
- `python3 "${PLUGIN_ROOT}/scripts/validate_plugin.py" <plugin-directory>` for structural validation after generation or edits.

Scaffold options to use when the requester has supplied metadata:

- `--license LICENSE` writes the portable manifest `license` field.
- `--author-name NAME`, `--author-email EMAIL`, and `--author-url URL` build the portable manifest `author` object from the provided fields only.
- If license or author metadata is not provided, omit those manifest fields intentionally rather than inventing defaults.

Follow the local registry policy:

- Use the bundled latest published release only.
- Do not add or rely on a `--spec-version` flag.
- Use the exact canonical schema identifiers recorded in the local registry.
- Never silently target a working draft release.

Keep the package portable:

- Put shared skills under `skills/` once.
- Keep Claude Code adapters minimal and never duplicate the shared skill tree into `.claude-plugin/`.
- Keep all generated paths inside the plugin root and avoid symlink-based sharing.
- Do not place secrets in manifests, MCP env maps, headers, docs, or examples.

Validation guidance:

- Run the validator after changes and report the selected published release, changed files, and any client-specific limits.
- Make it clear that static validation does not prove MCP runtime behavior; runtime smoke testing is separate when an MCP server exists.

Read references only when needed:

- For Agent Plugins release policy, schema ids, portable fields, and MCP placement, read [references/agent-plugins.md](references/agent-plugins.md).
- For skill frontmatter and routing expectations, read [references/agent-skills.md](references/agent-skills.md).
- For Codex-specific loading and package layout expectations, read [references/codex.md](references/codex.md).
- For Claude Code adapter boundaries, read [references/claude-code.md](references/claude-code.md).
- For Apache-2.0 and CC-BY-4.0 attribution duties, read [references/licensing.md](references/licensing.md).
