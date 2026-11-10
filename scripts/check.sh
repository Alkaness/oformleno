#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest
