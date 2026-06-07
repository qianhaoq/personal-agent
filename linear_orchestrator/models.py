from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Issue:
    identifier: str
    title: str
    state: str
    description: str = ""
    labels: tuple[str, ...] = ()
    priority: str | int | None = None
    assignee: str | None = None
    project: str | None = None
    url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def key_number(self) -> int:
        try:
            return int(self.identifier.rsplit("-", 1)[1])
        except (IndexError, ValueError):
            return 0

    @property
    def text(self) -> str:
        parts = [self.identifier, self.title, self.description or "", self.project or ""]
        parts.extend(self.labels)
        return "\n".join(part for part in parts if part)

    @classmethod
    def from_linear_node(cls, node: dict[str, Any]) -> "Issue":
        labels = node.get("labels", {}).get("nodes", [])
        assignee = node.get("assignee")
        project = node.get("project")
        state = node.get("state") or {}
        return cls(
            identifier=node.get("identifier", ""),
            title=node.get("title", ""),
            state=state.get("name", ""),
            description=node.get("description") or "",
            labels=tuple(label.get("name", "") for label in labels if label.get("name")),
            priority=node.get("priorityLabel") or node.get("priority"),
            assignee=assignee.get("name") if assignee else None,
            project=project.get("name") if project else None,
            url=node.get("url"),
            created_at=node.get("createdAt"),
            updated_at=node.get("updatedAt"),
            raw=node,
        )


@dataclass(frozen=True)
class RepoAdapter:
    name: str
    repo: str
    local_path: str | None = None
    matchers: tuple[str, ...] = ()
    setup_commands: tuple[str, ...] = ()
    test_commands: tuple[str, ...] = ()
    bdd_commands: tuple[str, ...] = ()
    preview_commands: tuple[str, ...] = ()
    allow_auto_run: bool = True
    allow_auto_merge: bool = False


@dataclass(frozen=True)
class Decision:
    issue_key: str
    action: str
    reason: str
    confidence: float
    current_state: str
    next_state: str | None = None
    labels_to_add: tuple[str, ...] = ()
    labels_to_remove: tuple[str, ...] = ()
    target_repo: str | None = None
    duplicate_of: str | None = None
    human_question: str | None = None
    comment: str | None = None
    blocked: bool = False

    @property
    def requires_human(self) -> bool:
        return self.action in {"human_needed", "guarded_wait"} or bool(self.human_question)

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue": self.issue_key,
            "action": self.action,
            "reason": self.reason,
            "confidence": self.confidence,
            "current_state": self.current_state,
            "next_state": self.next_state,
            "labels_to_add": list(self.labels_to_add),
            "labels_to_remove": list(self.labels_to_remove),
            "target_repo": self.target_repo,
            "duplicate_of": self.duplicate_of,
            "human_question": self.human_question,
            "comment": self.comment,
            "blocked": self.blocked,
        }
