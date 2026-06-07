from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any

import httpx

from linear_orchestrator.models import Issue


class OrchestratorClientError(RuntimeError):
    pass


class LinearClient:
    API_URL = "https://api.linear.app/graphql"

    def __init__(self, api_key: str | None = None, timeout: float = 30.0):
        self.api_key = api_key or os.getenv("LINEAR_API_KEY")
        self.timeout = timeout
        if not self.api_key:
            raise OrchestratorClientError("LINEAR_API_KEY is required for live Linear operations.")

    def graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {"query": query, "variables": variables or {}}
        response = httpx.post(self.API_URL, headers=headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        if data.get("errors"):
            raise OrchestratorClientError(json.dumps(data["errors"], ensure_ascii=False))
        return data["data"]

    def list_team_issues(self, team_key: str, first: int = 100) -> list[Issue]:
        query = """
        query TeamIssues($teamKey: String!, $first: Int!, $after: String) {
          issues(first: $first, after: $after, filter: { team: { key: { eq: $teamKey } } }) {
            nodes {
              id
              identifier
              title
              description
              priority
              priorityLabel
              url
              createdAt
              updatedAt
              state { id name type }
              labels { nodes { id name } }
              assignee { id name email }
              project { id name }
            }
            pageInfo { hasNextPage endCursor }
          }
        }
        """
        issues: list[Issue] = []
        after: str | None = None
        while True:
            data = self.graphql(query, {"teamKey": team_key, "first": first, "after": after})
            page = data["issues"]
            issues.extend(Issue.from_linear_node(node) for node in page["nodes"])
            page_info = page["pageInfo"]
            if not page_info["hasNextPage"]:
                return issues
            after = page_info["endCursor"]

    def team_state_ids(self, team_key: str) -> dict[str, str]:
        query = """
        query TeamStates($teamKey: String!) {
          teams(filter: { key: { eq: $teamKey } }) {
            nodes {
              states { nodes { id name } }
            }
          }
        }
        """
        data = self.graphql(query, {"teamKey": team_key})
        teams = data["teams"]["nodes"]
        if not teams:
            raise OrchestratorClientError(f"Linear team {team_key!r} was not found.")
        return {state["name"]: state["id"] for state in teams[0]["states"]["nodes"]}

    def team_label_ids(self, team_key: str) -> dict[str, str]:
        query = """
        query TeamLabels($teamKey: String!) {
          teams(filter: { key: { eq: $teamKey } }) {
            nodes {
              labels { nodes { id name } }
            }
          }
        }
        """
        data = self.graphql(query, {"teamKey": team_key})
        teams = data["teams"]["nodes"]
        if not teams:
            raise OrchestratorClientError(f"Linear team {team_key!r} was not found.")
        return {label["name"]: label["id"] for label in teams[0]["labels"]["nodes"]}

    def create_comment(self, issue_id: str, body: str) -> None:
        mutation = """
        mutation CommentCreate($issueId: String!, $body: String!) {
          commentCreate(input: { issueId: $issueId, body: $body }) {
            success
          }
        }
        """
        self.graphql(mutation, {"issueId": issue_id, "body": body})

    def update_issue(self, issue_id: str, state_id: str | None = None, label_ids: list[str] | None = None) -> None:
        input_value: dict[str, Any] = {}
        if state_id:
            input_value["stateId"] = state_id
        if label_ids is not None:
            input_value["labelIds"] = label_ids
        if not input_value:
            return
        mutation = """
        mutation IssueUpdate($issueId: String!, $input: IssueUpdateInput!) {
          issueUpdate(id: $issueId, input: $input) {
            success
          }
        }
        """
        self.graphql(mutation, {"issueId": issue_id, "input": input_value})


@dataclass(frozen=True)
class PullRequestSummary:
    number: int
    title: str
    url: str
    state: str
    is_draft: bool
    merge_state_status: str | None = None


class GitHubClient:
    def __init__(self, gh_bin: str = "gh"):
        self.gh_bin = gh_bin

    def _gh_json(self, args: list[str]) -> Any:
        env = os.environ.copy()
        if "GH_TOKEN" not in env and "GITHUB_TOKEN" in env:
            env["GH_TOKEN"] = env["GITHUB_TOKEN"]
        completed = subprocess.run(
            [self.gh_bin, *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        if not completed.stdout.strip():
            return None
        return json.loads(completed.stdout)

    def find_prs_for_issue(self, repo: str, issue_key: str) -> list[PullRequestSummary]:
        data = self._gh_json(
            [
                "pr",
                "list",
                "--repo",
                repo,
                "--state",
                "all",
                "--search",
                issue_key,
                "--json",
                "number,title,url,state,isDraft,mergeStateStatus",
            ]
        )
        return [
            PullRequestSummary(
                number=item["number"],
                title=item["title"],
                url=item["url"],
                state=item["state"],
                is_draft=bool(item.get("isDraft")),
                merge_state_status=item.get("mergeStateStatus"),
            )
            for item in data or []
        ]

    def pr_checks(self, repo: str, pr_number: int) -> list[dict[str, Any]]:
        try:
            data = self._gh_json(
                [
                    "pr",
                    "checks",
                    str(pr_number),
                    "--repo",
                    repo,
                    "--json",
                    "name,state,link,startedAt,completedAt",
                ]
            )
        except subprocess.CalledProcessError as exc:
            return [
                {
                    "name": "gh pr checks",
                    "state": "UNKNOWN",
                    "link": "",
                    "error": (exc.stderr or exc.stdout or "").strip(),
                }
            ]
        return list(data or [])
