## Goal

<!-- 中文优先：说明这次改动解决什么问题、为什么采用这个方案。English is fine for external contributor context. -->

## Related Issue

<!-- 中文优先：链接对应 Linear / GitHub issue。AI-native 任务优先填写 Linear issue。 -->

Linear issue:
GitHub issue: Fixes #

## Agent Plan

<!-- 中文优先：agent 创建或辅助的 PR 需要写计划摘要、关键文件、约束和拒绝的大范围改动。 -->

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

<!-- 中文优先：列出具体改动。代码改动请包含关键文件路径。 -->

-

## Verification Evidence

<!-- 中文优先：粘贴命令和结果。文档-only 改动说明做过什么静态检查。 -->

- [ ] Relevant targeted tests or static checks were run.
- [ ] CI is expected to cover the remaining surface.
- [ ] Any skipped checks are explained below.

Commands and results:

```text

```

## Environment

<!-- 中文优先：说明使用了 Dev Container、sandbox、worktree、本地 checkout 还是远程 agent 环境。 -->

## Risks

<!-- 中文优先：说明安全、凭证、数据迁移、兼容性、发布或回滚风险。检查后才能写 "None identified"。 -->

## Human Review Focus

<!-- 中文优先：列出需要人类 owner 判断的点。AI review 只是建议，merge 和 release 责任在人。 -->

## Follow-up Memory

<!-- 中文优先：如果本 PR 暴露出可复用规则，说明是否已更新 AGENTS.md、docs、tests、skills 或 runbook。 -->

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
