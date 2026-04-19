#!/usr/bin/env bash
# PostToolUse hook — runs actionlint via pre-commit on edited workflow files.
# Triggered on Edit|Write events.

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

[[ "$FILE" == */.github/workflows/*.yml ]] || exit 0

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 1

output=$(pre-commit run actionlint --files "$FILE" 2>&1)
status=$?

if [[ $status -ne 0 ]]; then
  printf '%s\n' "$output" >&2
  exit 2
fi
