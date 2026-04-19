#!/usr/bin/env bash
# PostToolUse hook — runs ruff (lint+fix) and ruff-format on edited Python files.
# Triggered on Edit|Write events.

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

[[ "$FILE" == *.py ]] || exit 0

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 1

output=$(ruff check --fix "$FILE" 2>&1)
status=$?

if [[ $status -ne 0 ]]; then
  printf '%s\n' "$output" >&2
  exit 2
fi

output=$(ruff format "$FILE" 2>&1)
status=$?

if [[ $status -ne 0 ]]; then
  printf '%s\n' "$output" >&2
  exit 2
fi
