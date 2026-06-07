from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from linear_orchestrator.clients import GitHubClient, LinearClient
from linear_orchestrator.config import OrchestratorConfig
from linear_orchestrator.models import Decision, Issue, RepoAdapter
from linear_orchestrator.policy import decide_issues, is_high_risk


@dataclass(frozen=True)
class RunPlan:
    issue_key: str
    issue_title: str
    repo: str
    branch: str
    local_path: str | None
    worktree_path: str | None
    setup_commands: tuple[str, ...]
    test_commands: tuple[str, ...]
    bdd_commands: tuple[str, ...]
    preview_commands: tuple[str, ...]
    codex_command: tuple[str, ...]
    guarded: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "issue": self.issue_key,
            "issue_title": self.issue_title,
            "repo": self.repo,
            "branch": self.branch,
            "local_path": self.local_path,
            "worktree_path": self.worktree_path,
            "setup_commands": list(self.setup_commands),
            "test_commands": list(self.test_commands),
            "bdd_commands": list(self.bdd_commands),
            "preview_commands": list(self.preview_commands),
            "codex_command": list(self.codex_command),
            "guarded": self.guarded,
        }


@dataclass(frozen=True)
class MonitorUpdate:
    issue_key: str
    next_state: str | None
    comment: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "issue": self.issue_key,
            "next_state": self.next_state,
            "comment": self.comment,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class AutoMergePlan:
    issue_key: str
    repo: str
    pr_number: int
    url: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "issue": self.issue_key,
            "repo": self.repo,
            "pr_number": self.pr_number,
            "url": self.url,
            "reason": self.reason,
        }


def load_fixture(path: str | Path) -> list[Issue]:
    fixture_path = Path(path)
    with fixture_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    nodes = data.get("issues", data) if isinstance(data, dict) else data
    issues: list[Issue] = []
    for node in nodes:
        if "identifier" in node and "state" in node and isinstance(node.get("state"), dict):
            issues.append(Issue.from_linear_node(node))
        else:
            normalized = dict(node)
            if isinstance(normalized.get("labels"), list):
                normalized["labels"] = tuple(normalized["labels"])
            issues.append(Issue(**normalized))
    return issues


def filter_nonterminal(issues: Iterable[Issue], config: OrchestratorConfig) -> list[Issue]:
    return [issue for issue in issues if issue.state not in config.terminal_states]


def decisions_for_issues(issues: Iterable[Issue], config: OrchestratorConfig) -> list[Decision]:
    return decide_issues(filter_nonterminal(issues, config), config)


def decision_table(decisions: Iterable[Decision]) -> str:
    rows = ["issue | action | state -> next | repo | reason", "--- | --- | --- | --- | ---"]
    for decision in decisions:
        transition = decision.current_state
        if decision.next_state:
            transition = f"{transition} -> {decision.next_state}"
        rows.append(
            " | ".join(
                [
                    decision.issue_key,
                    decision.action,
                    transition,
                    decision.target_repo or "-",
                    decision.reason.replace("\n", " "),
                ]
            )
        )
    return "\n".join(rows)


def apply_triage(decisions: Iterable[Decision], issues: Iterable[Issue], config: OrchestratorConfig, client: LinearClient) -> list[str]:
    state_ids = client.team_state_ids(config.team_key)
    label_ids = client.team_label_ids(config.team_key)
    issue_by_key = {issue.identifier: issue for issue in issues}
    applied: list[str] = []
    for decision in decisions:
        if decision.action in {"skip_terminal", "no_op", "ready_to_run", "monitor_pr"}:
            continue
        issue = issue_by_key.get(decision.issue_key)
        if not issue:
            continue
        linear_id = issue.raw.get("id")
        if not linear_id:
            continue
        if decision.comment:
            client.create_comment(linear_id, decision.comment)
        next_state_id = state_ids.get(decision.next_state) if decision.next_state else None
        merged_label_names = set(issue.labels) | set(decision.labels_to_add)
        label_id_values = [label_ids[name] for name in sorted(merged_label_names) if name in label_ids]
        if next_state_id or decision.labels_to_add:
            client.update_issue(linear_id, state_id=next_state_id, label_ids=label_id_values if label_id_values else None)
        applied.append(decision.issue_key)
    return applied


def _adapter_by_repo(config: OrchestratorConfig, repo: str) -> RepoAdapter:
    for adapter in config.repo_adapters:
        if adapter.repo == repo:
            return adapter
    raise ValueError(f"No repo adapter configured for {repo}")


def build_run_plan(issue: Issue, decision: Decision, config: OrchestratorConfig) -> RunPlan:
    if not decision.target_repo:
        raise ValueError(f"{issue.identifier} has no target repo.")
    adapter = _adapter_by_repo(config, decision.target_repo)
    branch = f"{issue.identifier.lower()}-{_slug(issue.title)}"
    prompt = (
        f"Implement Linear issue {issue.identifier}: {issue.title}\n\n"
        f"Linear description:\n{issue.description or '(no description)'}\n\n"
        "Create a draft PR with verification evidence. Do not merge."
    )
    worktree_path = None
    if adapter.local_path:
        local_path = Path(adapter.local_path)
        worktree_path = str(local_path.parent / f"{local_path.name}-{branch}")
    codex_command = ("codex", "exec", "--json", "--sandbox", "workspace-write", prompt)
    return RunPlan(
        issue_key=issue.identifier,
        issue_title=issue.title,
        repo=adapter.repo,
        branch=branch,
        local_path=adapter.local_path,
        worktree_path=worktree_path,
        setup_commands=adapter.setup_commands,
        test_commands=adapter.test_commands,
        bdd_commands=adapter.bdd_commands,
        preview_commands=adapter.preview_commands,
        codex_command=codex_command,
        guarded=is_high_risk(issue, config) or not adapter.allow_auto_run,
    )


def select_run_plan(issues: Iterable[Issue], decisions: Iterable[Decision], config: OrchestratorConfig, issue_key: str | None = None, allow_high_risk: bool = False) -> RunPlan | None:
    issue_by_key = {issue.identifier: issue for issue in issues}
    for decision in decisions:
        if issue_key and decision.issue_key != issue_key:
            continue
        if decision.action not in {"ready_to_run", "guarded_wait"}:
            continue
        issue = issue_by_key[decision.issue_key]
        if decision.action == "guarded_wait" and not allow_high_risk:
            continue
        plan = build_run_plan(issue, decision, config)
        if plan.guarded and not allow_high_risk:
            continue
        return plan
    return None


def execute_run_plan(plan: RunPlan) -> None:
    if not plan.local_path:
        raise ValueError(f"{plan.repo} has no local_path configured.")
    repo_path = Path(plan.local_path)
    if not repo_path.exists():
        raise ValueError(f"local_path does not exist: {repo_path}")
    worktree_path = Path(plan.worktree_path or repo_path.parent / f"{repo_path.name}-{plan.branch}")
    if worktree_path.exists():
        raise ValueError(f"worktree path already exists: {worktree_path}")
    subprocess.run(["git", "worktree", "add", "-b", plan.branch, str(worktree_path)], cwd=repo_path, check=True)
    commands: list[str | tuple[str, ...]] = [
        *plan.setup_commands,
        plan.codex_command,
        *plan.test_commands,
        *plan.bdd_commands,
        *plan.preview_commands,
    ]
    for command in commands:
        if isinstance(command, str):
            subprocess.run(command, cwd=worktree_path, shell=True, check=True)
        else:
            subprocess.run(list(command), cwd=worktree_path, check=True)
    if _git_has_changes(worktree_path):
        subprocess.run(["git", "add", "-A"], cwd=worktree_path, check=True)
        subprocess.run(["git", "commit", "-m", f"{plan.issue_key} AI agent implementation"], cwd=worktree_path, check=True)
    if _git_has_branch_diff(worktree_path):
        subprocess.run(["git", "push", "-u", "origin", plan.branch], cwd=worktree_path, check=True)
        subprocess.run(
            [
                "gh",
                "pr",
                "create",
                "--repo",
                plan.repo,
                "--draft",
                "--title",
                f"{plan.issue_key}: {plan.issue_title}",
                "--body",
                _pr_body(plan),
            ],
            cwd=worktree_path,
            check=True,
        )


def _git_has_changes(cwd: Path) -> bool:
    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return bool(completed.stdout.strip())


def _git_has_branch_diff(cwd: Path) -> bool:
    for base_ref in ("origin/main", "main"):
        completed = subprocess.run(
            ["git", "diff", "--quiet", f"{base_ref}...HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode == 0:
            return False
        if completed.returncode == 1:
            return True
    return False


def _pr_body(plan: RunPlan) -> str:
    return (
        "## Goal\n\n"
        f"Implement Linear issue `{plan.issue_key}`: {plan.issue_title}\n\n"
        "## Related Issue\n\n"
        f"Linear issue: {plan.issue_key}\n\n"
        "## Agent Plan\n\n"
        "Generated by `linear_orchestrator run --execute-agent` in an isolated worktree.\n\n"
        "## Verification Evidence\n\n"
        "Commands expected for this repo:\n\n"
        "```text\n"
        + "\n".join([*plan.test_commands, *plan.bdd_commands, *plan.preview_commands])
        + "\n```\n\n"
        "## Risks\n\n"
        "Human owner must review before merge or release.\n\n"
        "## Human Review Focus\n\n"
        "Confirm product intent, risk boundaries, and merge timing."
    )


def monitor_issue_prs(decisions: Iterable[Decision], github: GitHubClient, include_checks: bool = False) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for decision in decisions:
        if decision.action not in {"monitor_pr", "preview_human_validation", "await_human_merge"}:
            continue
        if not decision.target_repo:
            summaries.append({"issue": decision.issue_key, "status": "missing_repo"})
            continue
        try:
            prs = github.find_prs_for_issue(decision.target_repo, decision.issue_key)
        except Exception as exc:
            summaries.append(
                {
                    "issue": decision.issue_key,
                    "repo": decision.target_repo,
                    "status": "github_error",
                    "error": str(exc),
                }
            )
            continue
        pr_dicts = [pr.__dict__ for pr in prs]
        if include_checks:
            for pr_dict in pr_dicts:
                checks = github.pr_checks(decision.target_repo, int(pr_dict["number"]))
                pr_dict["checks"] = checks
                pr_dict["check_state"] = summarize_check_state(checks)
        summaries.append(
            {
                "issue": decision.issue_key,
                "repo": decision.target_repo,
                "prs": pr_dicts,
            }
        )
    return summaries


def summarize_check_state(checks: Iterable[dict[str, object]]) -> str:
    check_list = list(checks)
    if not check_list:
        return "unknown"
    states = {str(check.get("state", "")).casefold() for check in check_list}
    if states & {"failure", "failed", "error", "cancelled", "timed_out", "action_required"}:
        return "failed"
    if states <= {"success", "skipped", "neutral"}:
        return "success"
    return "pending"


def build_monitor_updates(summaries: Iterable[dict[str, object]], decisions: Iterable[Decision], config: OrchestratorConfig) -> list[MonitorUpdate]:
    decision_by_key = {decision.issue_key: decision for decision in decisions}
    updates: list[MonitorUpdate] = []
    for summary in summaries:
        issue_key = str(summary.get("issue", ""))
        decision = decision_by_key.get(issue_key)
        prs = list(summary.get("prs", []))
        if not issue_key or not decision or not prs:
            continue
        prs.sort(key=lambda item: int(item.get("number", 0)), reverse=True)
        pr = prs[0]
        state = str(pr.get("state", "")).upper()
        check_state = str(pr.get("check_state", "unknown"))
        url = pr.get("url", "")
        if state == "MERGED" and decision.current_state == config.states["merge_ready"]:
            updates.append(
                MonitorUpdate(
                    issue_key=issue_key,
                    next_state=config.states["done"],
                    reason="PR is merged after human merge gate.",
                    comment=f"GitHub PR 已合并：{url}\n\nAI monitor 建议将 issue 标记为 Done。",
                )
            )
        elif check_state == "failed":
            updates.append(
                MonitorUpdate(
                    issue_key=issue_key,
                    next_state=config.states["ready"],
                    reason="PR checks failed; send back to agent queue.",
                    comment=f"GitHub PR 检查失败：{url}\n\nAI monitor 建议回到 `待 Agent 处理`，由 agent 诊断并修复 CI。",
                )
            )
        elif check_state == "success" and decision.current_state in {
            config.states["running"],
            config.states["in_progress"],
            config.states["ai_review"],
            config.states["review"],
        }:
            updates.append(
                MonitorUpdate(
                    issue_key=issue_key,
                    next_state=config.states["preview"],
                    reason="PR checks passed; preview or product validation is next.",
                    comment=f"GitHub PR 检查已通过：{url}\n\nAI monitor 建议进入 `预览验证`，由人确认产品结果。",
                )
            )
    return updates


def build_auto_merge_plans(
    summaries: Iterable[dict[str, object]],
    issues: Iterable[Issue],
    decisions: Iterable[Decision],
    config: OrchestratorConfig,
) -> list[AutoMergePlan]:
    issue_by_key = {issue.identifier: issue for issue in issues}
    decision_by_key = {decision.issue_key: decision for decision in decisions}
    plans: list[AutoMergePlan] = []
    for summary in summaries:
        issue_key = str(summary.get("issue", ""))
        issue = issue_by_key.get(issue_key)
        decision = decision_by_key.get(issue_key)
        prs = list(summary.get("prs", []))
        if not issue_key or not issue or not decision or not prs or not decision.target_repo:
            continue
        adapter = _adapter_by_repo(config, decision.target_repo)
        if not _issue_allows_auto_merge(issue, adapter, config):
            continue
        if decision.current_state not in {
            config.states["running"],
            config.states["in_progress"],
            config.states["ai_review"],
            config.states["review"],
            config.states["merge_ready"],
        }:
            continue

        prs.sort(key=lambda item: int(item.get("number", 0)), reverse=True)
        pr = prs[0]
        if str(pr.get("state", "")).upper() != "OPEN":
            continue
        if bool(pr.get("is_draft")) or bool(pr.get("auto_merge_enabled")):
            continue
        if str(pr.get("check_state", "unknown")) != "success":
            continue
        plans.append(
            AutoMergePlan(
                issue_key=issue_key,
                repo=decision.target_repo,
                pr_number=int(pr["number"]),
                url=str(pr.get("url", "")),
                reason="Low-risk PR is open, non-draft, and all checks are green.",
            )
        )
    return plans


def apply_auto_merge_plans(plans: Iterable[AutoMergePlan], github: GitHubClient) -> list[str]:
    applied: list[str] = []
    for plan in plans:
        github.enable_pr_auto_merge(plan.repo, plan.pr_number, merge_method="rebase")
        applied.append(f"{plan.repo}#{plan.pr_number}")
    return applied


def _issue_allows_auto_merge(issue: Issue, adapter: RepoAdapter, config: OrchestratorConfig) -> bool:
    if not adapter.allow_auto_merge:
        return False
    labels = {label.casefold() for label in issue.labels}
    if config.labels["human_review"].casefold() in labels:
        return False
    return not is_high_risk(issue, config)


def apply_monitor_updates(updates: Iterable[MonitorUpdate], issues: Iterable[Issue], config: OrchestratorConfig, client: LinearClient) -> list[str]:
    state_ids = client.team_state_ids(config.team_key)
    issue_by_key = {issue.identifier: issue for issue in issues}
    applied: list[str] = []
    for update in updates:
        issue = issue_by_key.get(update.issue_key)
        if not issue:
            continue
        linear_id = issue.raw.get("id")
        if not linear_id:
            continue
        client.create_comment(linear_id, update.comment)
        next_state_id = state_ids.get(update.next_state) if update.next_state else None
        if next_state_id:
            client.update_issue(linear_id, state_id=next_state_id)
        applied.append(update.issue_key)
    return applied


def _slug(value: str) -> str:
    slug = "".join(char.lower() if char.isascii() and char.isalnum() else "-" for char in value)
    slug = "-".join(part for part in slug.split("-") if part)
    return slug[:48] or "linear-task"
