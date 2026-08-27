# Agent Skills

Agent Skills are shared instructions discovered from immediate child
directories under `skills/`. Each discovered skill directory must contain a
matching `SKILL.md`.

Minimum requirements for this repository:

- `SKILL.md` starts with YAML frontmatter.
- Frontmatter includes `name` and `description`.
- Supported extra keys are limited to the validator's accepted set, including
  `license` when needed.
- The frontmatter `name` must exactly match the skill directory name.
- Use concise routing in `SKILL.md` and move topic-specific detail to
  `references/`.

Packaging guidance:

- Keep one shared skill tree at the plugin root.
- Do not duplicate shared skills into `.claude-plugin/`.
- References and scripts should be addressed through paths that stay inside the
  plugin package.

Use the skill body to explain decisions that change the agent's behavior:

- whether the task is for a new plugin or an existing package;
- what metadata must be collected before writing files;
- when to show a proposed tree and pause for confirmation;
- which deterministic scripts to invoke;
- what validation proves and what it does not prove.
