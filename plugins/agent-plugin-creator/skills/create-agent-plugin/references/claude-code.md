# Claude Code

Claude Code support is an adapter layered on top of the same portable package.

Use:

- `.claude-plugin/plugin.json` for minimal Claude-facing metadata;
- root `skills/` for the shared skill tree;
- optional `.mcp.json` only when Claude-specific MCP placeholders are needed.

Adapter rules:

- Keep `.claude-plugin/plugin.json` minimal.
- Match the Claude adapter `name` to the root `plugin.json` name.
- Do not copy shared skills into `.claude-plugin/`.
- Translate portable MCP placeholders only where Claude-specific placeholders
  are required.

Local loading example:

1. Place the package at a stable path such as
   `~/.claude/plugins/agent-plugin-creator`.
2. Keep the shared skills at the package root.
3. Point Claude Code at the package through its local plugin loading workflow,
   which should read `.claude-plugin/plugin.json` as the adapter entrypoint.

Treat Claude Code behavior as client-specific compatibility, not as part of
the portable Agent Plugins contract.
