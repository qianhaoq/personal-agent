#!/usr/bin/env bash
set -euo pipefail

python --version
node --version
uv --version

if [ ! -x .venv/bin/python ]; then
  uv venv .venv --python 3.11
  . .venv/bin/activate
  uv pip install -e ".[all,dev]"
fi

scripts/run_tests.sh tests/test_devcontainer_config.py tests/acp/test_entry.py -- -q
