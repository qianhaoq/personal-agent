# AI-native Development Workflow

This repository uses Linear for task intent, GitHub for code and review, and agent tooling such as Codex for implementation support. The goal is not to remove human ownership. The goal is to make each task executable, verifiable, and reusable by agents while keeping humans accountable for product and release judgment.

## System Flow

1. A task starts as a Linear issue with goal, context, acceptance criteria, constraints, and verification.
2. The issue enters `待 Agent 处理` when it has enough context for an agent.
3. Codex or another coding agent reads the issue, repository instructions, code, docs, and relevant logs before proposing a plan.
4. A human owner reviews the plan when the change is non-trivial or risky.
5. The agent works in an isolated branch, worktree, sandbox, or Dev Container.
6. The agent runs targeted verification and opens a draft GitHub PR.
7. AI review checks obvious defects, missing tests, unsafe assumptions, and PR completeness.
8. Human review decides architecture, product fit, security, merge readiness, release timing, and rollback needs.
9. Reusable lessons are written back to `AGENTS.md`, this guide, tests, PR templates, skills, or runbooks.

## Linear Queue

Default pilot states:

```text
待 Agent 处理 -> Agent 执行中 -> AI 评审 -> 人工评审 -> 预览验证 -> 待合并 -> Done
```

State meanings:

- `待 Agent 处理`: the issue is ready for an agent to plan or execute.
- `Agent 执行中`: an agent is actively exploring, editing, or verifying.
- `AI 评审`: automated or agent review is checking the PR before human review.
- `人工评审`: a human owner is reviewing decisions, risks, and evidence.
- `预览验证`: the change needs preview, browser, deploy, or runtime validation.
- `待合并`: human review is complete and the PR is ready for final merge.
- `Done`: merged or otherwise completed with evidence recorded.

## Human Responsibilities

Humans own intent, priorities, tradeoffs, and production accountability.

- Define the goal, non-goals, acceptance criteria, and risk tolerance.
- Confirm plans for broad, cross-module, security, data, or release-sensitive changes.
- Review architecture, business correctness, safety, and long-term maintenance.
- Decide merge, release timing, rollout, rollback, and follow-up scope.
- Convert repeated failures into repository instructions, tests, or runbooks.

## Agent Responsibilities

Agents own repeatable execution and evidence gathering.

- Read Linear issue context and repository guidance before editing.
- Produce a concise plan for non-trivial work.
- Keep edits scoped to the issue and existing project patterns.
- Run targeted verification and report exact commands and outcomes.
- Open a draft PR with the required template filled in.
- Surface blockers, skipped checks, and review questions instead of hiding them.

## Development Environment

Use the lightest environment that can prove the change:

- Dev Container: preferred for dependency-sensitive or onboarding-sensitive work. It pins Python 3.11, uv, Node 22, and system packages needed by the repo.
- Worktree or branch: preferred for parallel agent tasks and clean diffs.
- Sandbox or remote VM: preferred when credentials, side effects, or local state should be isolated.
- CI: the merge gate. Local or agent verification is useful, but CI is the shared source of truth before merge.

Do not put secrets in the Dev Container, PR body, Linear issue, test fixtures, or committed configuration. Use scoped environment variables or secret managers.

## Pull Requests

Every PR should include:

- Linear issue link.
- Plan summary.
- Changed behavior or workflow.
- Verification evidence.
- Environment used.
- Risks and skipped checks.
- Human review focus.
- Follow-up memory updates.

PRs created by agents should be draft PRs until a human owner decides they are ready for normal review or merge.

## Feedback Loop

When review, CI, preview, or production feedback reveals a reusable rule, update one of the durable surfaces:

- `AGENTS.md` for agent-facing repository rules.
- `.github/PULL_REQUEST_TEMPLATE.md` for PR evidence requirements.
- Tests for behavior that should never regress.
- Docs or runbooks for operational procedures.
- Skills for repeatable multi-step workflows.

A task is not fully learned until the next agent can benefit from the lesson.
