from linear_orchestrator.clients import GitHubClient
from linear_orchestrator.cli import _codex_credentials_present, _repo_write_credentials_ready
from linear_orchestrator.config import load_config
from linear_orchestrator.models import Issue
from linear_orchestrator.policy import decide_issue, decide_issues, title_similarity
from linear_orchestrator.runner import (
    apply_run_update,
    build_auto_merge_plans,
    build_monitor_updates,
    load_fixture,
    select_run_plan,
    summarize_check_state,
)


def _config():
    return load_config("linear-orchestrator.config.json")


def test_one_26_is_marked_duplicate_of_one_23():
    config = _config()
    one_23 = Issue(
        identifier="ONE-23",
        title="增加作者写入口并优化交互界面",
        state="Triage",
        labels=("type:mvp", "needs-human-review", "area:web"),
        priority="Medium",
        assignee="钱浩",
    )
    one_26 = Issue(
        identifier="ONE-26",
        title="为博客增加作者编辑入口",
        state="待 Agent 处理",
        labels=(),
    )

    decision = decide_issue(one_26, [one_23, one_26], config)

    assert title_similarity(one_26.title, one_23.title) >= config.intake["duplicate_threshold"]
    assert decision.action == "mark_duplicate"
    assert decision.duplicate_of == "ONE-23"
    assert decision.next_state == "Duplicate"


def test_product_intake_routes_to_human_when_acceptance_is_missing():
    config = _config()
    issue = Issue(
        identifier="ONE-23",
        title="增加作者写入口并优化交互界面",
        state="Triage",
        labels=("area:web",),
        description="作者入口",
    )

    decision = decide_issue(issue, [issue], config)

    assert decision.action == "human_needed"
    assert decision.next_state == "人工评审"
    assert "needs-human-review" in decision.labels_to_add
    assert "入口放在哪里" in decision.human_question


def test_low_risk_complete_intake_promotes_to_agent_queue():
    config = _config()
    issue = Issue(
        identifier="ONE-30",
        title="personal-agent docs: add orchestrator runbook",
        state="Backlog",
        labels=("area:docs",),
        description=(
            "Acceptance: add a docs page describing scan, triage, run, and monitor. "
            "Verification: run the orchestrator policy tests and link the command output."
        ),
    )

    decision = decide_issue(issue, [issue], config)

    assert decision.action == "promote_to_agent_queue"
    assert decision.next_state == "待 Agent 处理"
    assert decision.target_repo == "qianhaoq/personal-agent"
    assert "ai-agent-ready" in decision.labels_to_add


def test_high_risk_ready_issue_is_not_selected_for_automatic_run():
    config = _config()
    issue = Issue(
        identifier="ONE-8",
        title="ai-quant-lab live trading controls",
        state="待 Agent 处理",
        labels=("ai-agent-ready", "risk:trading"),
        description="Acceptance: add guarded controls and tests. Verification: run api tests.",
    )
    decisions = decide_issues([issue], config)

    assert decisions[0].action == "guarded_wait"
    assert decisions[0].next_state == "人工评审"
    assert select_run_plan([issue], decisions, config) is None
    assert select_run_plan([issue], decisions, config, allow_high_risk=True).guarded is True


def test_ready_low_risk_issue_builds_run_plan_with_repo_adapter_commands():
    config = _config()
    issue = Issue(
        identifier="ONE-31",
        title="personal-agent add Linear orchestrator docs",
        state="待 Agent 处理",
        labels=("ai-agent-ready", "area:docs"),
        description="Acceptance: update docs and run targeted tests.",
    )
    decisions = decide_issues([issue], config)

    plan = select_run_plan([issue], decisions, config)

    assert plan is not None
    assert plan.issue_key == "ONE-31"
    assert plan.issue_title == "personal-agent add Linear orchestrator docs"
    assert plan.repo == "qianhaoq/personal-agent"
    assert plan.branch.startswith("one-31-")
    assert plan.worktree_path.endswith(plan.branch)
    assert "scripts/run_tests.sh tests/test_linear_orchestrator_policy.py" in plan.test_commands
    assert "--ask-for-approval" in plan.codex_command
    assert "never" in plan.codex_command


def test_repo_routing_ignores_process_labels_for_github_io_workflow_issue():
    config = _config()
    issue = Issue(
        identifier="ONE-24",
        title="拆分处理 Claude review reopened / ready_for_review 触发",
        state="待 Agent 处理",
        labels=("ai-agent-ready", "area:infra", "type:spike"),
        project="AI-native qianhaoq.github.io 研发工作流",
        description=(
            "Acceptance: update `.github/workflows/claude-review.yml` behavior for "
            "reopened and ready_for_review, then document the limitation in "
            "`docs/ai-native-workflow.md`."
        ),
    )
    decisions = decide_issues([issue], config)

    plan = select_run_plan([issue], decisions, config)

    assert plan is not None
    assert plan.issue_key == "ONE-24"
    assert plan.repo == "qianhaoq/qianhaoq.github.io"
    assert "pnpm quality:pr" in plan.test_commands
    assert "pnpm test:bdd" in plan.bdd_commands


def test_monitor_updates_move_green_active_pr_to_preview():
    config = _config()
    issue = Issue(
        identifier="ONE-32",
        title="personal-agent docs update",
        state="AI 评审",
        labels=("ai-agent-ready",),
        description="Acceptance: update docs and tests.",
    )
    decision = decide_issues([issue], config)[0]
    summaries = [
        {
            "issue": "ONE-32",
            "repo": "qianhaoq/personal-agent",
            "prs": [
                {
                    "number": 10,
                    "state": "OPEN",
                    "is_draft": False,
                    "url": "https://github.com/qianhaoq/personal-agent/pull/10",
                    "check_state": "success",
                }
            ],
        }
    ]

    updates = build_monitor_updates(summaries, [decision], config)

    assert updates[0].next_state == "预览验证"
    assert "检查已通过" in updates[0].comment


def test_monitor_arms_auto_merge_for_low_risk_green_pr():
    config = _config()
    issue = Issue(
        identifier="ONE-24",
        title="qianhaoq.github.io Claude review trigger update",
        state="AI 评审",
        labels=("ai-agent-ready", "area:infra"),
        project="AI-native qianhaoq.github.io 研发工作流",
        description="Acceptance: update workflow docs and tests.",
    )
    decision = decide_issues([issue], config)[0]
    summaries = [
        {
            "issue": "ONE-24",
            "repo": "qianhaoq/qianhaoq.github.io",
            "prs": [
                {
                    "number": 19,
                    "state": "OPEN",
                    "is_draft": False,
                    "url": "https://github.com/qianhaoq/qianhaoq.github.io/pull/19",
                    "check_state": "success",
                    "auto_merge_enabled": False,
                }
            ],
        }
    ]

    plans = build_auto_merge_plans(summaries, [issue], [decision], config)

    assert len(plans) == 1
    assert plans[0].repo == "qianhaoq/qianhaoq.github.io"
    assert plans[0].pr_number == 19


def test_monitor_does_not_auto_merge_human_or_high_risk_prs():
    config = _config()
    human_issue = Issue(
        identifier="ONE-23",
        title="为博客增加作者编辑入口",
        state="AI 评审",
        labels=("ai-agent-ready", "needs-human-review", "area:web"),
        description="Acceptance: add author editing UI.",
    )
    high_risk_issue = Issue(
        identifier="ONE-8",
        title="ai-quant-lab live trading controls",
        state="AI 评审",
        labels=("ai-agent-ready", "risk:trading"),
        description="Acceptance: add guarded controls and tests.",
    )
    decisions = decide_issues([human_issue, high_risk_issue], config)
    summaries = [
        {
            "issue": "ONE-23",
            "repo": "qianhaoq/qianhaoq.github.io",
            "prs": [
                {
                    "number": 23,
                    "state": "OPEN",
                    "is_draft": False,
                    "url": "https://github.com/qianhaoq/qianhaoq.github.io/pull/23",
                    "check_state": "success",
                    "auto_merge_enabled": False,
                }
            ],
        },
        {
            "issue": "ONE-8",
            "repo": "qianhaoq/ai-quant-lab",
            "prs": [
                {
                    "number": 8,
                    "state": "OPEN",
                    "is_draft": False,
                    "url": "https://github.com/qianhaoq/ai-quant-lab/pull/8",
                    "check_state": "success",
                    "auto_merge_enabled": False,
                }
            ],
        },
    ]

    plans = build_auto_merge_plans(summaries, [human_issue, high_risk_issue], decisions, config)

    assert plans == []


def test_check_summary_distinguishes_failed_and_pending():
    assert summarize_check_state([{"state": "SUCCESS"}, {"state": "SKIPPED"}]) == "success"
    assert summarize_check_state([{"state": "SUCCESS"}, {"state": "FAILURE"}]) == "failed"
    assert summarize_check_state([{"state": "SUCCESS"}, {"state": "PENDING"}]) == "pending"


class _FakeGitHubClient(GitHubClient):
    def __init__(self, payload):
        self.payload = payload

    def _gh_json(self, args):  # noqa: ARG002
        return self.payload


def test_github_pr_lookup_requires_exact_linear_issue_key():
    github = _FakeGitHubClient(
        [
            {
                "number": 4,
                "title": "ONE-27: Global Linear Orchestrator v1",
                "body": "Linear issue: ONE-27",
                "headRefName": "qianhao/one-27-global-linear-orchestrator-v1",
                "url": "https://github.com/qianhaoq/personal-agent/pull/4",
                "state": "MERGED",
                "isDraft": False,
                "mergeStateStatus": "UNKNOWN",
            },
            {
                "number": 8,
                "title": "Fix monitor handoff",
                "body": "Linear issue: ONE-7",
                "headRefName": "qianhao/monitor-handoff",
                "url": "https://github.com/qianhaoq/personal-agent/pull/8",
                "state": "OPEN",
                "isDraft": False,
                "mergeStateStatus": "CLEAN",
            },
            {
                "number": 9,
                "title": "Background runner polish",
                "body": "No issue key in body",
                "headRefName": "qianhao/one-7-background-runner-polish",
                "url": "https://github.com/qianhaoq/personal-agent/pull/9",
                "state": "OPEN",
                "isDraft": True,
                "mergeStateStatus": "UNKNOWN",
            },
            {
                "number": 10,
                "title": "ONE-7: Background runner polish",
                "body": "No canonical issue line.",
                "headRefName": "qianhao/background-runner-polish",
                "url": "https://github.com/qianhaoq/personal-agent/pull/10",
                "state": "OPEN",
                "isDraft": False,
                "mergeStateStatus": "CLEAN",
            },
            {
                "number": 11,
                "title": "ONE-28: Require exact Linear key matches",
                "body": "Linear issue: ONE-28\n\nRegression note: ONE-7 must not match ONE-27.",
                "headRefName": "qianhao/one-28-monitor-exact-linear-key",
                "url": "https://github.com/qianhaoq/personal-agent/pull/11",
                "state": "OPEN",
                "isDraft": False,
                "mergeStateStatus": "CLEAN",
            },
        ]
    )

    prs = github.find_prs_for_issue("qianhaoq/personal-agent", "ONE-7")

    assert [pr.number for pr in prs] == [8, 10]


def test_fixture_loader_accepts_top_level_issue_arrays(tmp_path):
    fixture = tmp_path / "issues.json"
    fixture.write_text(
        """
        [
          {
            "identifier": "ONE-31",
            "title": "personal-agent docs",
            "state": "待 Agent 处理",
            "description": "Acceptance: update docs.",
            "labels": ["ai-agent-ready", "area:docs"]
          }
        ]
        """,
        encoding="utf-8",
    )

    issues = load_fixture(fixture)

    assert issues[0].identifier == "ONE-31"
    assert issues[0].labels == ("ai-agent-ready", "area:docs")


def test_github_actions_requires_unattended_codex_credentials(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_OAUTH_ACCESS_TOKEN", raising=False)

    assert _codex_credentials_present() is False

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    assert _codex_credentials_present() is True


def test_local_codex_login_allows_subscription_execution(monkeypatch):
    import linear_orchestrator.cli as cli

    class _Completed:
        returncode = 0

    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_OAUTH_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(cli.subprocess, "run", lambda *args, **kwargs: _Completed())

    assert _codex_credentials_present() is True


def test_cross_repo_auto_run_requires_orchestrator_token(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "qianhaoq/personal-agent")
    monkeypatch.delenv("ORCHESTRATOR_GH_TOKEN", raising=False)

    assert _repo_write_credentials_ready("qianhaoq/personal-agent") == (True, None)
    ready, reason = _repo_write_credentials_ready("qianhaoq/qianhaoq.github.io")

    assert ready is False
    assert "ORCHESTRATOR_GH_TOKEN" in reason

    monkeypatch.setenv("ORCHESTRATOR_GH_TOKEN", "test-token")

    assert _repo_write_credentials_ready("qianhaoq/qianhaoq.github.io") == (True, None)


def test_apply_run_update_writes_state_comment_and_labels():
    config = _config()
    issue = Issue(
        identifier="ONE-31",
        title="personal-agent add Linear orchestrator docs",
        state="待 Agent 处理",
        labels=("ai-agent-ready",),
        raw={"id": "linear-id"},
    )

    class _FakeLinear:
        comments = []
        updates = []

        def team_state_ids(self, team_key):
            assert team_key == "ONE"
            return {"AI 评审": "state-ai-review"}

        def team_label_ids(self, team_key):
            assert team_key == "ONE"
            return {"ai-agent-ready": "label-agent-ready"}

        def create_comment(self, issue_id, body):
            self.comments.append((issue_id, body))

        def update_issue(self, issue_id, state_id=None, label_ids=None):
            self.updates.append((issue_id, state_id, label_ids))

    client = _FakeLinear()

    applied = apply_run_update(
        "ONE-31",
        [issue],
        config,
        client,
        next_state="AI 评审",
        labels_to_add=("ai-agent-ready",),
        comment="done",
    )

    assert applied is True
    assert client.comments == [("linear-id", "done")]
    assert client.updates == [("linear-id", "state-ai-review", ["label-agent-ready"])]
