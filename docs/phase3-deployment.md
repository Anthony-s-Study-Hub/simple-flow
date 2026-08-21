# Phase 3 Deployment

Phase 3 packages the controlled development workflow so it can be installed into
another project without changing core workflow logic.

## Release CLI

For a new project, install from a tagged public GitHub release package and run
the CLI from the project root:

```powershell
uvx --from git+https://github.com/Anthony-s-Study-Hub/simple-flow.git@v0.2.0 simple-flow doctor .
uvx --from git+https://github.com/Anthony-s-Study-Hub/simple-flow.git@v0.2.0 simple-flow install .
```

The installed package also exposes:

```powershell
simple-flow --version
simple-flow doctor .
simple-flow plan .
simple-flow install .
simple-flow upgrade .
```

`doctor` is read-only and checks Python, Git, target writability, packaged
deployment assets, release-source configuration, and file conflicts before an
install writes project files.

The default `simple-flow install .` mode is `thin`. It installs the workflow
files, Codex skills, small project scripts, documentation, and
`.simple-flow/install-manifest.json`, while GitHub Actions install the pinned
Simple Flow package from the release source instead of copying the source helper
packages and tests into the target project.

The legacy source-tree installer remains available for self-contained vendored
deployment:

```powershell
python scripts/install_simple_flow.py --target C:\path\to\target-project
simple-flow install C:\path\to\target-project --mode vendored
```

Both installers report created, skipped, conflicts, and failures as JSON when
the legacy script or `--json` flag is used.

Installed target skills are placed under `.codex/skills` with unprefixed names:

- `discussion`
- `issue-draft`
- `start-implement`
- `review-triage`
- `pr-finalize`
- `documentation-curation`

## Installed Files

Thin mode deploys:

- `AGENTS.md`
- GitHub workflows and templates
- six Codex skills with target-safe names and skill-local scripts
- project configuration template
- `.simple-flow/install-manifest.json` with package version, release source, and file hashes
- usage, integration, and GitHub setup docs
- Phase 5 baseline templates

Vendored mode also deploys:

- Phase 1 validators and automation
- Phase 2 deterministic helpers
- source regression tests for the self-contained target layout

## Known Limits

The installer performs deterministic file deployment and static validation. It
does not create GitHub Projects fields, choose project roadmap targets, or
replace human semantic review.

