# Global Linear Orchestrator

`linear_orchestrator` is the non-daemon v1 control loop for the OneRepublic Linear team. It lets this repository act as the global automation host without deploying `personal-agent` as a long-running service.

The v1 posture is AI-first with explicit risk boundaries:

- Scheduled GitHub Actions run the safe `auto` loop: apply triage updates, monitor PR/check state, write allowed Linear state updates, and arm GitHub auto-merge for eligible low-risk PRs.
- Low-risk coding-agent execution is automatic only when unattended Codex credentials are available in the runner. Without `OPENAI_API_KEY`, `CODEX_API_KEY`, or `CODEX_OAUTH_ACCESS_TOKEN`, GitHub-hosted scheduled runs skip code execution and continue triage/monitor automation.
- Local runs can use an existing Codex subscription login. If `codex login status` succeeds on your machine, `auto --execute-agent` can run without API-key secrets.
- Security, trading, secrets, production-release work, and anything labeled `needs-human-review` stays guarded and cannot be merged or released automatically.

## Commands

```bash
pnpm orchestrator:scan
pnpm orchestrator:triage
pnpm orchestrator:run
pnpm orchestrator:auto
pnpm orchestrator:monitor
pnpm orchestrator:doctor
```

The same commands are available through Python:

```bash
python -m linear_orchestrator.cli --json scan
python -m linear_orchestrator.cli --json triage
python -m linear_orchestrator.cli --json triage --apply
python -m linear_orchestrator.cli --json run --issue ONE-31
python -m linear_orchestrator.cli --json run --issue ONE-31 --execute-agent
python -m linear_orchestrator.cli --json auto --apply --execute-agent --auto-merge
python -m linear_orchestrator.cli --json monitor
python -m linear_orchestrator.cli --json doctor
```

Use `--fixture path/to/issues.json` for local policy tests without calling Linear.

## State Flow

The default OneRepublic flow is:

```text
Triage / Backlog / 待办
  -> 待 Agent 处理
  -> Agent 执行中
  -> AI 评审 / 评审中
  -> 人工评审 / 预览验证
  -> 待合并
  -> Done
```

Terminal states are `Done`, `Canceled`, and `Duplicate`.

## AI Decisions

`scan` and `triage` evaluate every non-terminal issue:

- Duplicate intake is linked to the canonical issue. Example: `ONE-26` should be folded into `ONE-23`.
- Linear onboarding issues such as `ONE-1` to `ONE-4` are kept out of the coding queue.
- Missing product decisions are routed to `人工评审` with one concrete question.
- Complete low-risk work is labeled `ai-agent-ready` and promoted to `待 Agent 处理`.
- `risk:security` and `risk:trading` can produce draft PR work only after explicit manual dispatch.

## Repo Adapters

Adapters live in `linear-orchestrator.config.json`.

Current repos:

- `qianhaoq/personal-agent`
- `qianhaoq/qianhaoq.github.io`
- `qianhaoq/ai-quant-lab`

Each adapter declares repository matchers, setup commands, test commands, optional BDD commands, preview checks, whether automatic low-risk execution is allowed, and whether low-risk PRs can be armed for GitHub auto-merge.

## GitHub Actions

`.github/workflows/linear-orchestrator.yml` runs every 30 minutes:

```text
auto --apply --execute-agent --auto-merge --max-runs 1
```

Manual dispatch can run one mode at a time:

- `scan`: read-only queue report.
- `triage`: use `apply=true` to write Linear comments, labels, and status changes.
- `monitor`: reads PR/check state and can arm auto-merge when `auto_merge=true`.
- `run`: use `execute_agent=true` to invoke the coding agent for an eligible issue.
- `auto`: runs the scheduled safe loop on demand. It writes safe Linear updates when `apply=true`, executes at most one eligible low-risk issue when `execute_agent=true`, and then monitors PR state.

`monitor` only arms auto-merge when all of these are true:

- The repo adapter has `allow_auto_merge=true`.
- The issue is not high-risk and does not have `needs-human-review`.
- The PR is open, not draft, and not already auto-merge enabled.
- GitHub checks are green.

Auto-merge still relies on GitHub branch protection. It does not bypass required checks, required reviews, merge queues, or repository rules.

Required secrets for live runs:

- `LINEAR_API_KEY`
- `ORCHESTRATOR_GH_TOKEN` for cross-repository PR reads, or the default repository `GITHUB_TOKEN` for same-repo checks.
- `OPENAI_API_KEY`, `CODEX_API_KEY`, or `CODEX_OAUTH_ACCESS_TOKEN` when GitHub-hosted `auto --execute-agent` should actually invoke Codex.

If you use Codex through a ChatGPT subscription and do not have API keys, run `auto --execute-agent` from a machine where `codex login status` succeeds, or use a self-hosted runner that has that non-interactive Codex login available. GitHub-hosted runners cannot see your local Codex App or Claude Code subscription session.

If `LINEAR_API_KEY` is not configured, scheduled runs skip safely and write a GitHub step summary instead of failing with a stack trace.

## Human Gate

The orchestrator may arm auto-merge for low-risk PRs after checks are green. Human owners remain responsible for product decisions, high-risk approval, release timing, rollback decisions, production secrets, and live trading controls.
