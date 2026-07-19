#!/bin/bash -eux

uv run ruff check
uv run ruff format --diff
uv run pyright
