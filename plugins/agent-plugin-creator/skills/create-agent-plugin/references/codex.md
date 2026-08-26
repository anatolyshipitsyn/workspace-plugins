# Codex

For Codex-compatible clients, the portable package is the source of truth.

Use:

- root `plugin.json` as the portable manifest;
- root `skills/` for shared skills;
- root `mcp.json` only when MCP servers are part of the package.

Codex-facing guidance for this plugin:

- Keep the root manifest limited to portable Agent Plugins fields.
- Prefer local scripts and bundled schemas so the package can be used offline.
- When the request includes MCP servers, validate the generated `mcp.json`
  statically and report that a separate runtime smoke test is still needed.

Local loading example:

1. Place the package at a stable path such as
   `~/.codex/plugins/agent-plugin-creator`.
2. Ensure the root manifest and shared `skills/` directory remain at that
   package root.
3. Load the plugin through the Codex client's local plugin workflow for a
   filesystem package.

Do not move shared skills into client-specific folders for Codex.
