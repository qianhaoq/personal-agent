## Goal

<!-- Describe the change clearly. What problem does it solve? Why is this approach the right one? -->

## Related Issue

<!-- Link the issue this PR addresses. Prefer a Linear issue for AI-native work. -->

Linear issue:
GitHub issue: Fixes #

## Agent Plan

<!-- For agent-created or agent-assisted PRs, summarize the plan that was reviewed before implementation. Mention important files, constraints, and rejected broad changes. -->

## Type of Change

<!-- Check the one that applies. -->

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Security fix
- [ ] Documentation update
- [ ] Tests (adding or improving test coverage)
- [ ] Refactor (no behavior change)
- [ ] New skill (bundled or hub)
- [ ] Development workflow / infrastructure

## Changes Made

<!-- List the specific changes. Include file paths for code changes. -->

-

## Verification Evidence

<!-- Paste commands and outcomes. For docs-only changes, explain the static check performed. -->

- [ ] Relevant targeted tests or static checks were run.
- [ ] CI is expected to cover the remaining surface.
- [ ] Any skipped checks are explained below.

Commands and results:

```text

```

## Environment

<!-- State whether this used a Dev Container, sandbox, worktree, local checkout, or remote agent environment. -->

## Risks

<!-- Call out security, credentials, data migration, compatibility, release, or rollback risks. Write "None identified" only after checking. -->

## Human Review Focus

<!-- Name the decisions the human owner must review. AI review is advisory; the human owner is accountable for merge and release. -->

## Follow-up Memory

<!-- If this PR revealed a reusable rule, say whether AGENTS.md, docs, tests, skills, or a runbook were updated. -->

## Checklist

<!-- Complete these before requesting review. -->

### Code

- [ ] I've read the [Contributing Guide](https://github.com/NousResearch/hermes-agent/blob/main/CONTRIBUTING.md)
- [ ] My commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (`fix(scope):`, `feat(scope):`, etc.) or another repository-specific protocol documented in `AGENTS.md`
- [ ] I searched for [existing PRs](https://github.com/NousResearch/hermes-agent/pulls) to make sure this isn't a duplicate
- [ ] My PR contains only changes related to this fix/feature (no unrelated commits)
- [ ] I've run `scripts/run_tests.sh` or documented why a narrower/static check is sufficient
- [ ] I've added tests for my changes (required for bug fixes, strongly encouraged for features)
- [ ] I've tested on my platform: <!-- e.g. Ubuntu 24.04, macOS 15.2, Windows 11, Dev Container -->

### Documentation & Housekeeping

<!-- Check all that apply. It's OK to check "N/A" if a category doesn't apply to your change. -->

- [ ] I've updated relevant documentation (README, `docs/`, docstrings) or N/A
- [ ] I've updated `cli-config.yaml.example` if I added/changed config keys or N/A
- [ ] I've updated `CONTRIBUTING.md` or `AGENTS.md` if I changed architecture or workflows or N/A
- [ ] I've considered cross-platform impact (Windows, macOS) per the compatibility guide or N/A
- [ ] I've updated tool descriptions/schemas if I changed tool behavior or N/A

## For New Skills

<!-- Only fill this out if you're adding a skill. Delete this section otherwise. -->

- [ ] This skill is broadly useful to most users (if bundled) per the Contributing Guide
- [ ] SKILL.md follows the standard format (frontmatter, trigger conditions, steps, pitfalls)
- [ ] No external dependencies that aren't already available (prefer stdlib, curl, existing Hermes tools)
- [ ] I've tested the skill end-to-end: `hermes --toolsets skills -q "Use the X skill to do Y"`

## Screenshots / Logs

<!-- If applicable, add screenshots or log output showing the fix/feature in action. -->
