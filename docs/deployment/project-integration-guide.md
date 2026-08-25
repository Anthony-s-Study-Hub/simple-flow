# Project Integration Guide

Each project supplies only project-specific configuration.

Install Simple Flow only through its versioned public GitHub repository
package. The installer does not accept vendored, local-checkout, ignored
`build/`, or alternate-repository sources.

Required inputs:

- Test command.
- Test paths or directories.
- Scope rules for allowed changed files.
- Documentation mapping.
- Project Baseline.
- High-Level Project Baseline and Component Baseline documents that follow the
  fixed Phase 5 baseline schemas.
- Roadmap Target source.

The installed core skills, CI workflows, validators, and templates should not be
edited per project. If a project needs different core workflow logic, treat that
as a portability defect in the deployment package.

Installed skills must keep their bundled `scripts/` directories. Those scripts
are the agent-facing deterministic entrypoints and use the matching public
Simple Flow package version.

Documentation-Curation also installs `.simple-flow/baselines/` templates and
the `simple_flow_documentation_curation` helper package. Projects may fill in
project-specific baseline content, but should not change the fixed section
names, decision fields, or Component Index columns.

