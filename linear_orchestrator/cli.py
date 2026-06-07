from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from linear_orchestrator.clients import GitHubClient, LinearClient, OrchestratorClientError
from linear_orchestrator.config import load_config
from linear_orchestrator.runner import (
    apply_auto_merge_plans,
    apply_monitor_updates,
    apply_triage,
    build_auto_merge_plans,
    build_monitor_updates,
    decision_table,
    decisions_for_issues,
    execute_run_plan,
    load_fixture,
    monitor_issue_prs,
    select_run_plan,
)


def _load_issues(args: argparse.Namespace, config):
    if args.fixture:
        return load_fixture(args.fixture)
    return LinearClient().list_team_issues(config.team_key)


def _print(value, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(value)


def _cmd_scan(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    issues = _load_issues(args, config)
    decisions = decisions_for_issues(issues, config)
    if args.json:
        _print([decision.to_dict() for decision in decisions], True)
    else:
        _print(decision_table(decisions), False)
    return 0


def _cmd_triage(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    issues = _load_issues(args, config)
    decisions = decisions_for_issues(issues, config)
    actionable = [
        decision for decision in decisions
        if decision.action in {"cancel_onboarding_noise", "mark_duplicate", "human_needed", "promote_to_agent_queue", "guarded_wait"}
    ]
    if not args.apply:
        _print([decision.to_dict() for decision in actionable] if args.json else decision_table(actionable), args.json)
        return 0
    if args.fixture:
        raise SystemExit("--apply cannot be used with --fixture.")
    applied = apply_triage(actionable, issues, config, LinearClient())
    _print({"applied": applied}, True)
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    issues = _load_issues(args, config)
    decisions = decisions_for_issues(issues, config)
    plan = select_run_plan(
        issues,
        decisions,
        config,
        issue_key=args.issue,
        allow_high_risk=args.allow_high_risk_run,
    )
    if not plan:
        _print({"run_plan": None, "reason": "No eligible issue found."}, True)
        return 0
    if not args.execute_agent:
        _print({"run_plan": plan.to_dict(), "executed": False}, True)
        return 0
    if plan.guarded and not args.allow_high_risk_run:
        raise SystemExit("Refusing guarded run without --allow-high-risk-run.")
    execute_run_plan(plan)
    _print({"run_plan": plan.to_dict(), "executed": True}, True)
    return 0


def _cmd_monitor(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    issues = _load_issues(args, config)
    decisions = decisions_for_issues(issues, config)
    github = GitHubClient()
    summary = monitor_issue_prs(decisions, github, include_checks=True)
    updates = build_monitor_updates(summary, decisions, config)
    auto_merge_plans = build_auto_merge_plans(summary, issues, decisions, config)
    auto_merge_applied: list[str] = []
    if args.auto_merge:
        if args.fixture:
            raise SystemExit("--auto-merge cannot be used with --fixture.")
        auto_merge_applied = apply_auto_merge_plans(auto_merge_plans, github)
    if not args.apply:
        _print(
            {
                "prs": summary,
                "planned_updates": [update.to_dict() for update in updates],
                "auto_merge_plans": [plan.to_dict() for plan in auto_merge_plans],
                "auto_merge_applied": auto_merge_applied,
            },
            True,
        )
        return 0
    if args.fixture:
        raise SystemExit("--apply cannot be used with --fixture.")
    applied = apply_monitor_updates(updates, issues, config, LinearClient())
    _print(
        {
            "prs": summary,
            "applied": applied,
            "auto_merge_plans": [plan.to_dict() for plan in auto_merge_plans],
            "auto_merge_applied": auto_merge_applied,
        },
        True,
    )
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    linear_present = bool(os.getenv("LINEAR_API_KEY"))
    github_env_present = bool(os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN"))
    gh_auth = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    repo_results = []
    for adapter in config.repo_adapters:
        result = subprocess.run(
            ["gh", "repo", "view", adapter.repo, "--json", "nameWithOwner,viewerPermission"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        repo_results.append(
            {
                "repo": adapter.repo,
                "ok": result.returncode == 0,
                "detail": result.stdout.strip() if result.returncode == 0 else result.stderr.strip(),
            }
        )
    payload = {
        "linear_api_key": "present" if linear_present else "missing",
        "github_env_token": "present" if github_env_present else "missing",
        "gh_auth": "ok" if gh_auth.returncode == 0 else "failed",
        "repos": repo_results,
    }
    _print(payload, True)
    if args.require_linear and not linear_present:
        return 2
    if args.require_github and gh_auth.returncode != 0 and not github_env_present:
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Global Linear AI Orchestrator")
    parser.add_argument("--config", default=None, help="Path to linear-orchestrator.config.json")
    parser.add_argument("--fixture", default=None, help="Read issues from a JSON fixture instead of Linear")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Read-only queue scan")
    scan.set_defaults(func=_cmd_scan)

    triage = subparsers.add_parser("triage", help="Plan or apply Linear triage updates")
    triage.add_argument("--apply", action="store_true", help="Write Linear comments/status/labels")
    triage.set_defaults(func=_cmd_triage)

    run = subparsers.add_parser("run", help="Build or execute one AI run plan")
    run.add_argument("--issue", default=None, help="Specific issue key to run")
    run.add_argument("--execute-agent", action="store_true", help="Actually invoke the coding agent")
    run.add_argument("--allow-high-risk-run", action="store_true", help="Allow guarded high-risk draft-PR work")
    run.set_defaults(func=_cmd_run)

    monitor = subparsers.add_parser("monitor", help="Read GitHub PR/check state for active issues")
    monitor.add_argument("--apply", action="store_true", help="Write Linear updates when transition rules allow it")
    monitor.add_argument("--auto-merge", action="store_true", help="Arm GitHub auto-merge for eligible low-risk PRs")
    monitor.set_defaults(func=_cmd_monitor)

    doctor = subparsers.add_parser("doctor", help="Check credentials and repository access")
    doctor.add_argument("--require-linear", action="store_true", help="Fail when LINEAR_API_KEY is missing")
    doctor.add_argument("--require-github", action="store_true", help="Fail when gh/GitHub token is unavailable")
    doctor.set_defaults(func=_cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except OrchestratorClientError as exc:
        print(f"orchestrator error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
