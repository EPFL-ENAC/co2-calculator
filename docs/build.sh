#!/bin/sh
# The one docs build: the Makefile, the Dockerfile and CI all call it, so
# a check added here runs everywhere. Output: docs/site.
set -eu
cd "$(dirname "$0")"
uv run --frozen python gen_indexes.py
uv run --frozen zensical build --clean --strict
uv run --frozen python check_links.py site
