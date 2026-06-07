# Global Linear Orchestrator

`linear_orchestrator` is the non-daemon v1 control loop for the OneRepublic Linear team. It lets this repository act as the global automation host without deploying `personal-agent` as a long-running service.

The v1 posture is conservative:

- Scheduled GitHub Actions run `scan`, `triage`, and `monitor` in dry-run mode.
- Linear writes require manual `workflow_dispatch` with `apply=true`.
- Coding-agent execution requires manual `run` dispatch with `execute_agent=true`.
- Security, trading, secrets, and production-release work stays guarded and cannot be merged or released automatically.

## Commands

```bash
pnpm orchestrator:scan
pnpm orchestrator:triage
pnpm orchestrator:run
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

Each adapter declares repository matchers, setup commands, test commands, optional BDD commands, preview checks, and whether automatic low-risk execution is allowed.

## GitHub Actions

`.github/workflows/linear-orchestrator.yml` runs every 30 minutes in dry-run mode:

```text
scan -> triage -> monitor
```

Manual dispatch can run one mode at a time:

- `scan`: read-only queue report.
- `triage`: use `apply=true` to write Linear comments, labels, and status changes.
- `monitor`: currently read-only until PR/check transition rules are hardened.
- `run`: use `execute_agent=true` to invoke the coding agent for an eligible issue.

Required secrets for live runs:

- `LINEAR_API_KEY`
- `ORCHESTRATOR_GH_TOKEN` for cross-repository PR reads, or the default repository `GITHUB_TOKEN` for same-repo checks.
- `CODEX_API_KEY` or the configured coding-agent credentials when `run --execute-agent` is enabled.

If `LINEAR_API_KEY` is not configured, scheduled runs skip safely and write a GitHub step summary instead of failing with a stack trace.

## Human Gate

The orchestrator does not auto-merge, auto-release, alter production secrets, or enable live trading. Human owners remain responsible for product decisions, high-risk approval, final merge, release timing, and rollback decisions.
