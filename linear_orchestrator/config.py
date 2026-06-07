from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from linear_orchestrator.models import RepoAdapter


DEFAULT_CONFIG: dict[str, Any] = {
    "team_key": "ONE",
    "states": {
        "triage": "Triage",
        "backlog": "Backlog",
        "todo": "待办",
        "ready": "待 Agent 处理",
        "running": "Agent 执行中",
        "in_progress": "处理中",
        "ai_review": "AI 评审",
        "review": "评审中",
        "human_review": "人工评审",
        "preview": "预览验证",
        "merge_ready": "待合并",
        "done": "Done",
        "canceled": "Canceled",
        "duplicate": "Duplicate",
    },
    "terminal_states": ["Done", "Canceled", "Duplicate"],
    "labels": {
        "agent_ready": "ai-agent-ready",
        "human_review": "needs-human-review",
        "risk_security": "risk:security",
        "risk_trading": "risk:trading",
    },
    "repo_adapters": [
        {
            "name": "personal-agent",
            "repo": "qianhaoq/personal-agent",
            "local_path": "/Users/qianhao02/codex/personal-agent",
            "matchers": ["personal-agent", "hermes", "个人助理", "agent", "gateway", "mcp"],
            "setup_commands": ["uv pip install -e '.[dev]'"],
            "test_commands": ["scripts/run_tests.sh tests/test_linear_orchestrator_policy.py"],
            "bdd_commands": [],
            "preview_commands": [],
            "allow_auto_run": True,
        },
        {
            "name": "qianhaoq.github.io",
            "repo": "qianhaoq/qianhaoq.github.io",
            "local_path": "/Users/qianhao02/codex/qianhaoq.github.io",
            "matchers": ["qianhaoq.github.io", "blog", "博客", "作者", "站点", "pages"],
            "setup_commands": ["pnpm install --frozen-lockfile"],
            "test_commands": ["pnpm quality:pr"],
            "bdd_commands": ["pnpm test:bdd"],
            "preview_commands": ["pnpm browser:smoke"],
            "allow_auto_run": True,
        },
        {
            "name": "ai-quant-lab",
            "repo": "qianhaoq/ai-quant-lab",
            "local_path": "/Users/qianhao02/codex/ai-quant-lab",
            "matchers": ["ai-quant-lab", "AI Quant", "量化", "trading", "alpaca", "broker"],
            "setup_commands": ["pnpm install --frozen-lockfile", "pnpm api:install"],
            "test_commands": ["pnpm api:test", "pnpm test", "pnpm typecheck", "pnpm lint", "pnpm build"],
            "bdd_commands": [],
            "preview_commands": [],
            "allow_auto_run": False,
        },
    ],
    "risk": {
        "high_risk_labels": ["risk:security", "risk:trading"],
        "high_risk_terms": ["secret", "credential", "prod", "production", "交易", "实盘", "上线"],
        "manual_run_required_labels": ["risk:security", "risk:trading"],
    },
    "intake": {
        "onboarding_issue_keys": ["ONE-1", "ONE-2", "ONE-3", "ONE-4"],
        "duplicate_threshold": 0.58,
        "acceptance_markers": ["验收", "acceptance", "done when", "完成条件", "验证", "test"],
        "minimum_description_chars": 120,
    },
}


@dataclass(frozen=True)
class OrchestratorConfig:
    team_key: str
    states: dict[str, str]
    terminal_states: frozenset[str]
    labels: dict[str, str]
    repo_adapters: tuple[RepoAdapter, ...]
    risk: dict[str, Any]
    intake: dict[str, Any]

    @property
    def intake_states(self) -> frozenset[str]:
        return frozenset(
            [
                self.states["triage"],
                self.states["backlog"],
                self.states["todo"],
            ]
        )

    @property
    def active_states(self) -> frozenset[str]:
        return frozenset(
            [
                self.states["ready"],
                self.states["running"],
                self.states["in_progress"],
                self.states["ai_review"],
                self.states["review"],
                self.states["human_review"],
                self.states["preview"],
                self.states["merge_ready"],
            ]
        )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _repo_adapter_from_dict(value: dict[str, Any]) -> RepoAdapter:
    return RepoAdapter(
        name=value["name"],
        repo=value["repo"],
        local_path=value.get("local_path"),
        matchers=tuple(value.get("matchers", [])),
        setup_commands=tuple(value.get("setup_commands", [])),
        test_commands=tuple(value.get("test_commands", [])),
        bdd_commands=tuple(value.get("bdd_commands", [])),
        preview_commands=tuple(value.get("preview_commands", [])),
        allow_auto_run=bool(value.get("allow_auto_run", True)),
    )


def config_from_dict(value: dict[str, Any]) -> OrchestratorConfig:
    return OrchestratorConfig(
        team_key=value["team_key"],
        states=dict(value["states"]),
        terminal_states=frozenset(value["terminal_states"]),
        labels=dict(value["labels"]),
        repo_adapters=tuple(_repo_adapter_from_dict(item) for item in value["repo_adapters"]),
        risk=dict(value["risk"]),
        intake=dict(value["intake"]),
    )


def load_config(path: str | Path | None = None) -> OrchestratorConfig:
    config = DEFAULT_CONFIG
    config_path = Path(path) if path else Path.cwd() / "linear-orchestrator.config.json"
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as handle:
            config = _deep_merge(config, json.load(handle))
    return config_from_dict(config)
