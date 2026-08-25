# GitHub Setup Guide

Simple Flow does not configure GitHub for a target project. Keep the project's
existing branch protections, CI requirements, Issue templates, and merge policy
in place.

For the Issue → PR → merge route, contributors need a configured `origin`, an
authenticated GitHub CLI, and permission to create Issues and pull requests.
Start-Implement discovers the repository and default branch locally, then opens
the PR against that branch. PR-Finalize checks the normal GitHub protections and
merges only after explicit user approval.
