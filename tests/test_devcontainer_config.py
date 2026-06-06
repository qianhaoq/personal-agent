"""Regression tests for the repository Dev Container contract."""

import json
import shlex
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEVCONTAINER_PATH = REPO_ROOT / ".devcontainer" / "devcontainer.json"


def _load_devcontainer():
    with DEVCONTAINER_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _command_tokens(config, key):
    tokens = shlex.split(config[key])
    expanded = list(tokens)
    for token in tokens:
        if " " in token or "&&" in token or ";" in token:
            expanded.extend(shlex.split(token))
    return expanded


def test_devcontainer_uses_ci_aligned_python_and_node():
    config = _load_devcontainer()
    features = config["features"]
    update_tokens = _command_tokens(config, "updateContentCommand")

    assert config["image"].startswith("mcr.microsoft.com/devcontainers/python:3.11")
    assert features["ghcr.io/devcontainers/features/node:1"]["version"] == "22"
    assert {"uv", "venv", ".venv", "--python", "3.11"}.issubset(update_tokens)
    assert {"uv", "pip", "install", "-e", ".[all,dev]"}.issubset(update_tokens)


def test_devcontainer_installs_required_bootstrap_tools():
    config = _load_devcontainer()
    on_create_tokens = set(_command_tokens(config, "onCreateCommand"))

    expected_packages = {
        "git-lfs",
        "ripgrep",
        "ffmpeg",
        "gcc",
        "python3-dev",
        "libffi-dev",
        "libolm-dev",
        "procps",
    }
    assert {"apt-get", "install"}.issubset(on_create_tokens)
    assert expected_packages.issubset(on_create_tokens)
    assert "https://astral.sh/uv/0.11.6/install.sh" in on_create_tokens
    assert "UV_INSTALL_DIR=/usr/local/bin" in on_create_tokens


def test_devcontainer_keeps_heavy_setup_prebuild_friendly():
    config = _load_devcontainer()

    update_tokens = set(_command_tokens(config, "updateContentCommand"))
    post_create_tokens = set(_command_tokens(config, "postCreateCommand"))

    assert {"uv", "pip", "install"}.issubset(update_tokens)
    assert {"npm", "install"}.issubset(update_tokens)
    assert {"python", "node", "uv", "--version"}.issubset(post_create_tokens)
    assert "install" not in post_create_tokens


def test_devcontainer_supports_github_cli_codespace_ssh():
    config = _load_devcontainer()
    features = config["features"]

    sshd_feature = features["ghcr.io/devcontainers/features/sshd:1"]
    assert sshd_feature["version"] == "latest"


def test_devcontainer_does_not_use_sensitive_field_names():
    config = _load_devcontainer()
    serialized_keys = json.dumps(list(_walk_keys(config))).lower()

    forbidden_terms = ("api_key", "password", "secret", "token", "github_token")
    for term in forbidden_terms:
        assert term not in serialized_keys


def _walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)
