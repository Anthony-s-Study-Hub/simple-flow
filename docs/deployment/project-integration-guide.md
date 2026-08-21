# Project Integration Guide

Each project supplies only project-specific configuration.

Required inputs:

- Test command.
- Test paths or directories.
- Scope rules for allowed changed files.
- Documentation mapping.
- Project Baseline.
- Roadmap Target source.

The installed core skills, CI workflows, validators, and templates should not be
edited per project. If a project needs different core workflow logic, treat that
as a portability defect in the deployment package.

Installed skills must keep their bundled `scripts/` directories. Those scripts
are the agent-facing deterministic entrypoints and call the shared
`simple_flow_agent` helper package installed at the project root.

