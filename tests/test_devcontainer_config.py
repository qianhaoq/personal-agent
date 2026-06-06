"""Regression tests for the repository Dev Container contract."""

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEVCONTAINER_PATH = REPO_ROOT / ".devcontainer" / "devcontainer.json"


def _load_devcontainer():
    with DEVCONTAINER_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def test_devcontainer_uses_ci_aligned_python_and_node():
    config = _load_devcontainer()
    features = config["features"]

    assert config["image"] == "mcr.microsoft.com/devcontainers/python:3.11-bookworm"
    assert features["ghcr.io/devcontainers/features/node:1"]["version"] == "22"
    assert "uv venv .venv --python 3.11" in config["updateContentCommand"]
    assert 'uv pip install -e ".[all,dev]"' in config["updateContentCommand"]


def test_devcontainer_keeps_heavy_setup_prebuild_friendly():
    config = _load_devcontainer()

    update_content_command = config["updateContentCommand"]
    post_create_command = config["postCreateCommand"]

    assert "uv pip install" in update_content_command
    assert "npm install" in update_content_command
    assert "python --version" in post_create_command
    assert "node --version" in post_create_command
    assert "uv --version" in post_create_command
    assert "uv pip install" not in post_create_command
    assert "npm install" not in post_create_command


def test_devcontainer_supports_github_cli_codespace_ssh():
    config = _load_devcontainer()
    features = config["features"]

    sshd_feature = features["ghcr.io/devcontainers/features/sshd:1"]
    assert sshd_feature["version"] == "latest"


def test_devcontainer_does_not_embed_secrets_or_tokens():
    config = _load_devcontainer()
    serialized_config = json.dumps(config, sort_keys=True).lower()

    forbidden_terms = ("api_key", "password", "secret", "token", "github_token")
    for term in forbidden_terms:
        assert term not in serialized_config
