from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable

from linear_orchestrator.config import OrchestratorConfig
from linear_orchestrator.models import Decision, Issue, RepoAdapter


_PRODUCT_DECISION_TERMS = ("入口", "交互", "作者", "编辑", "页面", "UI", "UX", "产品")


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value.casefold())


def _label_set(issue: Issue) -> frozenset[str]:
    return frozenset(label.casefold() for label in issue.labels)


def _contains_any(value: str, terms: Iterable[str]) -> bool:
    normalized = value.casefold()
    return any(term.casefold() in normalized for term in terms)


def is_terminal(issue: Issue, config: OrchestratorConfig) -> bool:
    return issue.state in config.terminal_states


def is_high_risk(issue: Issue, config: OrchestratorConfig) -> bool:
    labels = _label_set(issue)
    risk_labels = {label.casefold() for label in config.risk.get("high_risk_labels", [])}
    if labels & risk_labels:
        return True
    return _contains_any(issue.text, config.risk.get("high_risk_terms", []))


def has_acceptance_criteria(issue: Issue, config: OrchestratorConfig) -> bool:
    description = issue.description or ""
    if _contains_any(description, config.intake.get("acceptance_markers", [])):
        return True
    return len(description.strip()) >= int(config.intake.get("minimum_description_chars", 120))


def select_repo(issue: Issue, config: OrchestratorConfig) -> RepoAdapter | None:
    text = issue.text.casefold()
    for adapter in config.repo_adapters:
        candidates = [adapter.name, adapter.repo, *adapter.matchers]
        if any(candidate.casefold() in text for candidate in candidates if candidate):
            return adapter
    return None


def _shared_signal_bonus(left: str, right: str) -> float:
    signals = ("博客", "作者", "入口", "编辑", "写", "交互", "linear", "runner", "trading")
    shared = [signal for signal in signals if signal in left and signal in right]
    return min(0.18, len(shared) * 0.06)


def title_similarity(left: str, right: str) -> float:
    norm_left = _normalize_text(left)
    norm_right = _normalize_text(right)
    if not norm_left or not norm_right:
        return 0.0
    base = SequenceMatcher(None, norm_left, norm_right).ratio()
    return min(1.0, base + _shared_signal_bonus(norm_left, norm_right))


def find_duplicate(issue: Issue, issues: Iterable[Issue], config: OrchestratorConfig) -> tuple[Issue, float] | None:
    threshold = float(config.intake.get("duplicate_threshold", 0.58))
    candidates: list[tuple[Issue, float]] = []
    for other in issues:
        if other.identifier == issue.identifier or is_terminal(other, config):
            continue
        score = title_similarity(issue.title, other.title)
        if score >= threshold:
            candidates.append((other, score))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[1], item[0].key_number))
    return candidates[0]


def _canonical_duplicate_key(issue: Issue, duplicate: Issue) -> str:
    if duplicate.key_number and issue.key_number:
        return duplicate.identifier if duplicate.key_number < issue.key_number else issue.identifier
    return duplicate.identifier


def _human_question(issue: Issue, target_repo: RepoAdapter | None, has_acceptance: bool) -> str | None:
    if target_repo is None:
        return "请确认这个 issue 应该落到哪个 GitHub 仓库。"
    if not has_acceptance and _contains_any(issue.title, _PRODUCT_DECISION_TERMS):
        return "请确认产品形态和验收标准：入口放在哪里、谁能编辑、保存后用户看到什么结果？"
    if not has_acceptance:
        return "请补充可验证的验收标准，至少说明完成后如何检查通过。"
    return None


def _comment_for_human(issue: Issue, question: str, target_repo: RepoAdapter | None) -> str:
    repo_line = f"\n\nAI 推断目标仓库：`{target_repo.repo}`。" if target_repo else ""
    return (
        "AI triage 需要人工补充一个判断后才能继续自动执行。"
        f"{repo_line}\n\n问题：{question}"
    )


def _guarded_comment(issue: Issue, target_repo: RepoAdapter | None) -> str:
    repo_line = f"目标仓库：`{target_repo.repo}`。" if target_repo else "目标仓库尚未确认。"
    return (
        "该 issue 命中 security/trading/production 风险策略，AI 可以继续准备 draft PR 和验证证据，"
        "但不能自动 merge、发布、启用真实交易或变更生产 secret。\n\n"
        f"{repo_line}"
    )


def decide_issue(issue: Issue, all_issues: Iterable[Issue], config: OrchestratorConfig) -> Decision:
    if is_terminal(issue, config):
        return Decision(
            issue_key=issue.identifier,
            action="skip_terminal",
            reason="Issue is already in a terminal state.",
            confidence=1.0,
            current_state=issue.state,
        )

    if issue.identifier in set(config.intake.get("onboarding_issue_keys", [])):
        return Decision(
            issue_key=issue.identifier,
            action="cancel_onboarding_noise",
            reason="Linear onboarding issue; do not feed it to coding agents.",
            confidence=0.92,
            current_state=issue.state,
            next_state=config.states["canceled"],
            comment="AI triage 建议取消这个 Linear onboarding 示例任务，避免污染真实研发队列。",
        )

    duplicate = find_duplicate(issue, all_issues, config)
    if duplicate:
        canonical_key = _canonical_duplicate_key(issue, duplicate[0])
        if canonical_key != issue.identifier:
            return Decision(
                issue_key=issue.identifier,
                action="mark_duplicate",
                reason=f"Likely duplicate of {canonical_key}.",
                confidence=duplicate[1],
                current_state=issue.state,
                next_state=config.states["duplicate"],
                duplicate_of=canonical_key,
                labels_to_add=(config.labels["human_review"],),
                comment=(
                    f"AI triage 判断该 issue 与 `{canonical_key}` 高度重合。"
                    f"建议把新增信息合并到 `{canonical_key}`，本 issue 标记为 Duplicate。"
                ),
            )

    target_repo = select_repo(issue, config)
    high_risk = is_high_risk(issue, config)
    acceptance_ready = has_acceptance_criteria(issue, config)

    if issue.state in config.intake_states:
        question = _human_question(issue, target_repo, acceptance_ready)
        if question:
            return Decision(
                issue_key=issue.identifier,
                action="human_needed",
                reason="Issue is missing a non-inferable routing or acceptance decision.",
                confidence=0.88,
                current_state=issue.state,
                next_state=config.states["human_review"],
                labels_to_add=(config.labels["human_review"],),
                target_repo=target_repo.repo if target_repo else None,
                human_question=question,
                comment=_comment_for_human(issue, question, target_repo),
                blocked=True,
            )

        labels = {config.labels["agent_ready"]}
        if high_risk:
            labels.add(config.labels["human_review"])
        return Decision(
            issue_key=issue.identifier,
            action="promote_to_agent_queue",
            reason="Issue has enough context for an AI agent to plan and execute.",
            confidence=0.84 if not high_risk else 0.74,
            current_state=issue.state,
            next_state=config.states["ready"],
            labels_to_add=tuple(sorted(labels)),
            target_repo=target_repo.repo if target_repo else None,
            comment=(
                "AI triage 已补齐执行路由，建议进入 `待 Agent 处理`。"
                + ("\n\n" + _guarded_comment(issue, target_repo) if high_risk else "")
            ),
        )

    if issue.state == config.states["ready"]:
        if target_repo is None:
            question = "请确认这个 agent-ready issue 的目标 GitHub 仓库。"
            return Decision(
                issue_key=issue.identifier,
                action="human_needed",
                reason="Ready issue has no target repository.",
                confidence=0.86,
                current_state=issue.state,
                next_state=config.states["human_review"],
                labels_to_add=(config.labels["human_review"],),
                human_question=question,
                comment=_comment_for_human(issue, question, None),
                blocked=True,
            )
        if high_risk:
            return Decision(
                issue_key=issue.identifier,
                action="guarded_wait",
                reason="High-risk issue requires explicit manual dispatch before AI execution.",
                confidence=0.95,
                current_state=issue.state,
                next_state=config.states["human_review"],
                labels_to_add=(config.labels["human_review"],),
                target_repo=target_repo.repo,
                comment=_guarded_comment(issue, target_repo),
                blocked=True,
            )
        return Decision(
            issue_key=issue.identifier,
            action="ready_to_run",
            reason="Issue is ready for AI implementation.",
            confidence=0.9,
            current_state=issue.state,
            next_state=config.states["running"],
            target_repo=target_repo.repo,
            labels_to_add=(config.labels["agent_ready"],),
        )

    if issue.state in {config.states["running"], config.states["in_progress"], config.states["ai_review"], config.states["review"]}:
        return Decision(
            issue_key=issue.identifier,
            action="monitor_pr",
            reason="Issue is already active; monitor GitHub PR, checks, review, and preview state.",
            confidence=0.82,
            current_state=issue.state,
            target_repo=target_repo.repo if target_repo else None,
        )

    if issue.state == config.states["preview"]:
        return Decision(
            issue_key=issue.identifier,
            action="preview_human_validation",
            reason="Preview verification requires product validation before merge.",
            confidence=0.92,
            current_state=issue.state,
            next_state=config.states["merge_ready"],
            labels_to_add=(config.labels["human_review"],),
            target_repo=target_repo.repo if target_repo else None,
            human_question="请验证 preview 产品结果是否满足验收标准；通过后进入待合并。",
        )

    if issue.state == config.states["merge_ready"]:
        return Decision(
            issue_key=issue.identifier,
            action="await_human_merge",
            reason="Merge remains a human-owned gate.",
            confidence=1.0,
            current_state=issue.state,
            target_repo=target_repo.repo if target_repo else None,
            human_question="请做最终 merge/release 判断。",
        )

    return Decision(
        issue_key=issue.identifier,
        action="no_op",
        reason="No safe automated transition matched.",
        confidence=0.5,
        current_state=issue.state,
        target_repo=target_repo.repo if target_repo else None,
    )


def decide_issues(issues: Iterable[Issue], config: OrchestratorConfig) -> list[Decision]:
    issue_list = list(issues)
    return [decide_issue(issue, issue_list, config) for issue in issue_list]
