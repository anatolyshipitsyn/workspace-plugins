# Agent Plugin Creator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `plugins/agent-plugin-creator`, a portable Agent Plugin that interactively designs new plugins and uses deterministic local scripts to scaffold and validate them for Codex and Claude Code.

**Architecture:** The plugin has one shared `create-agent-plugin` skill, local release schemas, a registry that identifies the latest published release, and Python scripts for deterministic scaffolding and validation. The root `plugin.json` and `mcp.json` are portable Agent Plugins files; `.claude-plugin/plugin.json` and `.mcp.json` are optional Claude Code adapters. No MCP server is required.

**Tech Stack:** Markdown Agent Skill, Python 3 standard library, JSON Schema Draft 2020-12 validation through an available local validator or a small structural fallback, JSON, shell-based verification.

**Spec:** `docs/superpowers/specs/2026-08-26-agent-plugin-creator-design.md`; upstream Agent Plugins Specification repository and its published schemas.

**Status:** Complete on branch `codex/agent-plugin-creator`. Implementation,
scoped reviews, final whole-branch review, and verification are recorded in
the SDD ledger at `.superpowers/sdd/2026-08-26-agent-plugin-creator/progress.md`.

## Global Constraints

- The generator MUST select `latestRelease` from a local registry and MUST NOT expose `--spec-version`.
- The generator MUST reject a registry whose latest release is listed as a draft or lacks local `plugin.schema.json` and `mcp.schema.json` files.
- The generated portable manifest MUST contain only fields permitted by the selected Agent Plugins schema.
- Portable component locations MUST be root `plugin.json`, root `skills/`, and root `mcp.json`.
- Claude-specific files MUST remain adapters: `.claude-plugin/plugin.json` and `.mcp.json` when requested.
- Shared skills and scripts MUST be created once and MUST NOT rely on symlinks.
- The generator MUST refuse overwrite by default and MUST keep writes inside the requested destination.
- The validator MUST check schema rules plus path containment, symlink containment, MCP semantic rules, reserved environment names, and obvious secret material.
- Bundled schemas MUST retain Apache-2.0 attribution; copied specification prose or examples MUST retain CC-BY-4.0 attribution.
- Do not commit credentials, tokens, passwords, `.env` files, or generated secret material.

---

### Task 1: Align repository policy and add the release registry

**Files:**
- Modify: `AGENTS.md`
- Create: `DECISIONS.md`
- Create: `plugins/agent-plugin-creator/specs/registry.json`
- Create: `plugins/agent-plugin-creator/specs/1.0.0/plugin.schema.json`
- Create: `plugins/agent-plugin-creator/specs/1.0.0/mcp.schema.json`
- Create: `plugins/agent-plugin-creator/specs/1.0.0/NOTICE.md`
- Test: `tests/test_registry.py`

**Interfaces:**
- Produces a registry with `latestRelease`, `supportedReleases`, `draftReleases`, and source metadata.
- Produces schemas addressable as `specs/<release>/plugin.schema.json` and `mcp.schema.json`.

- [ ] **Step 1: Write the failing registry tests**

```python
def test_latest_release_is_published_and_has_both_schemas():
    registry = load_registry()
    assert registry["latestRelease"] in registry["supportedReleases"]
    assert registry["latestRelease"] not in registry["draftReleases"]
    release_dir = ROOT / "plugins/agent-plugin-creator/specs" / registry["latestRelease"]
    assert (release_dir / "plugin.schema.json").is_file()
    assert (release_dir / "mcp.schema.json").is_file()
```

- [ ] **Step 2: Run the test and verify it fails because the registry is absent**

Run: `python3 -m unittest tests/test_registry.py -v`
Expected: FAIL because the registry and bundled release directory do not exist.

- [ ] **Step 3: Add registry metadata and the current published schemas**

Use the current upstream published release `1.0.0` as `latestRelease`; record `1.1.0` as a draft only. Copy the exact upstream 1.0.0 schemas and retain Apache-2.0 attribution in `NOTICE.md`. Add the previously accepted decisions to `DECISIONS.md`.

- [ ] **Step 4: Run the registry test**

Run: `python3 -m unittest tests/test_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md DECISIONS.md plugins/agent-plugin-creator/specs tests/test_registry.py
git commit -m "feat: add agent plugin release registry"
```

### Task 2: Implement deterministic scaffolding

**Files:**
- Create: `plugins/agent-plugin-creator/scripts/scaffold_plugin.py`
- Create: `plugins/agent-plugin-creator/tests/test_scaffold_plugin.py`

**Interfaces:**
- CLI: `python3 scaffold_plugin.py --destination PATH --name NAME --description TEXT --clients codex,claude [--with-skill NAME] [--with-mcp-server JSON] [--force]`
- Produces a plugin directory named after the normalized plugin name.
- `--force` is the only explicit overwrite authorization.

- [ ] **Step 1: Write tests for basic portable output, optional Claude files, and refusal behavior**

```python
def test_creates_portable_plugin_and_shared_skill(tmp_path):
    result = run_scaffold(tmp_path, "Demo Plugin", clients=["codex"], skills=["review"])
    assert result.returncode == 0
    root = tmp_path / "demo-plugin"
    assert (root / "plugin.json").is_file()
    assert (root / "skills/review/SKILL.md").is_file()
    assert not (root / ".claude-plugin/plugin.json").exists()

def test_creates_claude_adapter_without_copying_skills(tmp_path):
    run_scaffold(tmp_path, "demo-plugin", clients=["codex", "claude"], skills=["review"])
    root = tmp_path / "demo-plugin"
    assert (root / ".claude-plugin/plugin.json").is_file()
    assert (root / "skills/review/SKILL.md").is_file()
    assert not (root / ".claude-plugin/skills/review/SKILL.md").exists()

def test_refuses_existing_output_without_force(tmp_path):
    run_scaffold(tmp_path, "demo-plugin", clients=["codex"])
    result = run_scaffold(tmp_path, "demo-plugin", clients=["codex"])
    assert result.returncode != 0
    assert "overwrite" in result.stderr.lower()
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `python3 -m unittest plugins/agent-plugin-creator/tests/test_scaffold_plugin.py -v`
Expected: FAIL because the scaffold script does not exist.

- [ ] **Step 3: Implement the minimal generator**

Load the registry, reject draft latest releases, normalize only safe plugin names, create requested directories, render deterministic JSON, and use atomic exclusive file creation. Keep all destination resolution and containment checks in the script. Generate Claude metadata separately from portable metadata.

- [ ] **Step 4: Run the focused tests**

Run: `python3 -m unittest plugins/agent-plugin-creator/tests/test_scaffold_plugin.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/agent-plugin-creator/scripts/scaffold_plugin.py plugins/agent-plugin-creator/tests/test_scaffold_plugin.py
git commit -m "feat: scaffold portable agent plugins"
```

### Task 3: Implement semantic validation

**Files:**
- Create: `plugins/agent-plugin-creator/scripts/validate_plugin.py`
- Create: `plugins/agent-plugin-creator/tests/test_validate_plugin.py`

**Interfaces:**
- CLI: `python3 validate_plugin.py PLUGIN_PATH`
- Exit code `0` means all checks pass; non-zero means at least one diagnostic exists.
- Diagnostics include `path`, `rule`, and `correction` in human-readable output.

- [ ] **Step 1: Write failing validator tests**

```python
def test_accepts_generated_portable_plugin(plugin_fixture):
    assert validate(plugin_fixture).returncode == 0

def test_rejects_manifest_with_unknown_top_level_field(plugin_fixture):
    write_manifest_field(plugin_fixture, "skills", [])
    result = validate(plugin_fixture)
    assert result.returncode != 0
    assert "unknown" in result.stdout.lower()

def test_rejects_mismatched_mcp_schema(plugin_fixture):
    write_mcp_schema(plugin_fixture, "1.1.0")
    result = validate(plugin_fixture)
    assert result.returncode != 0
    assert "schema" in result.stdout.lower()

def test_rejects_path_escape_and_reserved_environment_names(plugin_fixture):
    write_invalid_mcp(plugin_fixture, cwd="../outside", env={"PLUGIN_ROOT": "bad"})
    result = validate(plugin_fixture)
    assert result.returncode != 0
    assert "containment" in result.stdout.lower() or "reserved" in result.stdout.lower()
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python3 -m unittest plugins/agent-plugin-creator/tests/test_validate_plugin.py -v`
Expected: FAIL because the validator does not exist.

- [ ] **Step 3: Implement schema and semantic checks**

Validate the bundled schema selected by the root manifest. Add explicit checks for Agent Skills frontmatter, immediate-child discovery, realpath containment, symlink escape, MCP transport/URL rules, placeholder rules, reserved variables, and secret patterns. Do not execute plugin code.

- [ ] **Step 4: Run validator tests and a generated fixture**

Run: `python3 -m unittest plugins/agent-plugin-creator/tests/test_validate_plugin.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/agent-plugin-creator/scripts/validate_plugin.py plugins/agent-plugin-creator/tests/test_validate_plugin.py
git commit -m "feat: validate agent plugin packages"
```

### Task 4: Add the cross-client skill, references, and package metadata

**Files:**
- Create: `plugins/agent-plugin-creator/plugin.json`
- Create: `plugins/agent-plugin-creator/.claude-plugin/plugin.json`
- Create: `plugins/agent-plugin-creator/skills/create-agent-plugin/SKILL.md`
- Create: `plugins/agent-plugin-creator/skills/create-agent-plugin/references/agent-plugins.md`
- Create: `plugins/agent-plugin-creator/skills/create-agent-plugin/references/agent-skills.md`
- Create: `plugins/agent-plugin-creator/skills/create-agent-plugin/references/codex.md`
- Create: `plugins/agent-plugin-creator/skills/create-agent-plugin/references/claude-code.md`
- Create: `plugins/agent-plugin-creator/skills/create-agent-plugin/references/licensing.md`
- Create: `plugins/agent-plugin-creator/README.md`
- Create: `plugins/agent-plugin-creator/CHANGELOG.md`
- Create: `plugins/agent-plugin-creator/LICENSE`
- Create: `plugins/agent-plugin-creator/tests/test_package.py`

**Interfaces:**
- Skill reads references only when their topic applies.
- Skill invokes scripts using paths rooted at its own plugin directory.
- Portable manifest uses the latest published schema identifier from the bundled registry.

- [ ] **Step 1: Write package tests**

```python
def test_creator_has_valid_portable_manifest():
    assert validate_package(ROOT / "plugins/agent-plugin-creator") == []

def test_skill_has_required_frontmatter_and_routes_to_scripts():
    skill = read_skill()
    assert skill.frontmatter["name"] == "create-agent-plugin"
    assert "scaffold_plugin.py" in skill.body
    assert "validate_plugin.py" in skill.body
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python3 -m unittest plugins/agent-plugin-creator/tests/test_package.py -v`
Expected: FAIL because package files do not exist.

- [ ] **Step 3: Add the skill and references**

Keep `SKILL.md` concise. Route schema details, client-specific differences, Agent Skills rules, and licensing to references. Require a proposed tree and explicit confirmation immediately before mutation. Document that validation is not an MCP runtime smoke test.

- [ ] **Step 4: Add manifests and documentation**

Use only portable manifest fields in root `plugin.json`. Put Claude metadata in `.claude-plugin/plugin.json`. Include the upstream specification and schema links, current release/draft status, installation examples for Codex and Claude, and the Apache/CC-BY attribution policy.

- [ ] **Step 5: Run package tests and skill validation**

Run: `python3 -m unittest plugins/agent-plugin-creator/tests/test_package.py -v`
Run: `python3 /Users/anatoly.shipitz/.codex/skills/.system/skill-creator/scripts/quick_validate.py plugins/agent-plugin-creator/skills/create-agent-plugin`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins/agent-plugin-creator
git commit -m "feat: add agent plugin creator skill"
```

### Task 5: End-to-end verification and repository integration

**Files:**
- Modify: `README.md`
- Create: `tests/test_end_to_end.py`

**Interfaces:**
- Repository-level command validates every plugin under `plugins/`.
- End-to-end test creates a temporary plugin with Codex and Claude support and validates it without network access.

- [ ] **Step 1: Write the end-to-end test**

```python
def test_scaffold_then_validate_without_network(tmp_path):
    created = scaffold(name="sample-tools", destination=tmp_path, clients=["codex", "claude"], skills=["review"])
    assert validate(created).returncode == 0
```

- [ ] **Step 2: Run the test and verify it fails or exposes integration gaps**

Run: `python3 -m unittest tests/test_end_to_end.py -v`
Expected: FAIL until all package paths and script interfaces are integrated.

- [ ] **Step 3: Add repository usage documentation and integration checks**

Document how to run the creator, how latest published release selection works, and how to perform Codex/Claude loading checks. Keep generated packages independently distributable.

- [ ] **Step 4: Run the complete verification suite**

Run: `python3 -m unittest discover -v`
Run: `python3 /Users/anatoly.shipitz/.codex/skills/.system/skill-creator/scripts/quick_validate.py plugins/agent-plugin-creator/skills/create-agent-plugin`
Run: `git diff --check`
Expected: all tests and checks pass.

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_end_to_end.py
git commit -m "test: verify agent plugin creator end to end"
```
