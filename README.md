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
├── .claude-plugin/marketplace.json
├── .agents/plugins/marketplace.json
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
- The two repository-root marketplace manifests expose this workspace as a
  local plugin marketplace. They list plugins by relative path; they never
  duplicate package content.

## Connecting this workspace

This repository is a plugin marketplace named `workspace-plugins`. Both
supported clients can register it from GitHub
(`anatolyshipitsyn/workspace-plugins`) or from a local checkout, so there is no
packaging or publishing step beyond pushing a commit.

Each client reads its own manifest at the repository root:

| Client | Marketplace manifest | Plugin entrypoint it resolves |
| --- | --- | --- |
| Claude Code | `.claude-plugin/marketplace.json` | `plugins/<name>/.claude-plugin/plugin.json` |
| Codex | `.agents/plugins/marketplace.json` | `plugins/<name>/plugin.json` |

Both clients need the marketplace manifests to be present at the source they
read, so a GitHub source only sees plugins that are committed and pushed.
In the local-checkout variants below, replace `/path/to/workspace-plugins`
with your checkout path.

### Claude Code

Register the workspace as a marketplace, then install a plugin from it:

```bash
claude plugin marketplace add anatolyshipitsyn/workspace-plugins
claude plugin install agent-plugin-creator@workspace-plugins
```

To work against a local checkout instead, pass its path:

```bash
claude plugin marketplace add /path/to/workspace-plugins
```

A path source must be absolute or `./`-prefixed; a bare `.` is rejected.

Verify and refresh:

```bash
claude plugin marketplace list
claude plugin list
claude plugin marketplace update workspace-plugins
```

Claude Code copies each installed package into a versioned snapshot under
`~/.claude/plugins/cache/workspace-plugins/<plugin-name>/<version>/`, for a
GitHub source and a local path source alike. Nothing is read live.

`claude plugin marketplace update workspace-plugins` refreshes only the
marketplace manifest, and `claude plugin update <plugin>@workspace-plugins` is
a no-op while the version is unchanged. To pick up edits at the same version,
reinstall:

```bash
claude plugin uninstall agent-plugin-creator@workspace-plugins
claude plugin install agent-plugin-creator@workspace-plugins
```

For a tight edit loop, prefer the `--plugin-dir` form below, which does read the
checkout directly.

Equivalent declarative configuration in `~/.claude/settings.json` (or a
project's `.claude/settings.json`) if you prefer not to use the CLI:

```json
{
  "extraKnownMarketplaces": {
    "workspace-plugins": {
      "source": {
        "source": "github",
        "repo": "anatolyshipitsyn/workspace-plugins"
      }
    }
  },
  "enabledPlugins": {
    "agent-plugin-creator@workspace-plugins": true
  }
}
```

To try a single package for one session without registering anything:

```bash
claude --plugin-dir /path/to/workspace-plugins/plugins/agent-plugin-creator
```

Remove the workspace with:

```bash
claude plugin uninstall agent-plugin-creator@workspace-plugins
claude plugin marketplace remove workspace-plugins
```

### Codex

Register the workspace from GitHub, then install a plugin from it:

```bash
codex plugin marketplace add anatolyshipitsyn/workspace-plugins --ref main
codex plugin add agent-plugin-creator@workspace-plugins
```

`codex plugin marketplace add` also accepts an HTTPS or SSH Git URL, so these
are equivalent:

```bash
codex plugin marketplace add https://github.com/anatolyshipitsyn/workspace-plugins --ref main
codex plugin marketplace add git@github.com:anatolyshipitsyn/workspace-plugins.git --ref main
```

Verify:

```bash
codex plugin marketplace list
codex plugin list
```

Refresh the marketplace snapshot after new commits land on the ref, then
reinstall the plugins you use:

```bash
codex plugin marketplace upgrade
codex plugin add agent-plugin-creator@workspace-plugins
```

Codex clones the marketplace and copies each installed package into a
versioned snapshot under
`~/.codex/plugins/cache/workspace-plugins/<plugin-name>/<version>/`. Nothing is
read live, so a change is only visible after the snapshot is refreshed.

To develop against an unpushed checkout instead of GitHub, register the local
path and re-run `codex plugin add` after each edit:

```bash
codex plugin marketplace add /path/to/workspace-plugins
codex plugin add agent-plugin-creator@workspace-plugins
```

Either form writes a `[marketplaces.workspace-plugins]` entry plus a
per-plugin enable flag to `~/.codex/config.toml`. For a local path that entry
is:

```toml
[marketplaces.workspace-plugins]
source_type = "local"
source = "/path/to/workspace-plugins"

[plugins."agent-plugin-creator@workspace-plugins"]
enabled = true
```

Remove the workspace with:

```bash
codex plugin remove agent-plugin-creator@workspace-plugins
codex plugin marketplace remove workspace-plugins
```

### Adding a plugin to the workspace

A new package under `plugins/<plugin-name>/` is not visible to either client
until it is listed in both marketplace manifests:

```jsonc
// .claude-plugin/marketplace.json — one entry in "plugins": [ ... ]
{
  "name": "<plugin-name>",
  "source": "./plugins/<plugin-name>",
  "description": "<one line>"
}
```

```jsonc
// .agents/plugins/marketplace.json — one entry in "plugins": [ ... ]
{
  "name": "<plugin-name>",
  "source": { "source": "local", "path": "./plugins/<plugin-name>" },
  "policy": { "installation": "AVAILABLE" },
  "category": "Productivity"
}
```

`claude plugin validate` only reads `.claude-plugin/marketplace.json`; it
cannot tell you that the Codex manifest is missing an entry. Run both checks:

```bash
claude plugin validate /path/to/workspace-plugins
python3 -m unittest tests.test_marketplace_manifests
```

`tests/test_marketplace_manifests.py` fails when a directory under `plugins/`
is absent from either manifest, or when a manifest entry points at a path that
does not exist.

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

These checks are about a single plugin package, not about connecting the
workspace. Run them against an installed package root rather than a repository
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
