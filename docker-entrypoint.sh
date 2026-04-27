#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${GITHUB_TOKEN:-}" && -z "${GH_TOKEN:-}" ]]; then
  export GH_TOKEN="$GITHUB_TOKEN"
fi

if ! git config --global user.name >/dev/null; then
  git config --global user.name "${GIT_AUTHOR_NAME:-The Foundry}"
fi

if ! git config --global user.email >/dev/null; then
  git config --global user.email "${GIT_AUTHOR_EMAIL:-foundry@example.invalid}"
fi

if gh auth status --hostname github.com >/dev/null 2>&1; then
  gh auth setup-git --hostname github.com >/dev/null 2>&1 || true
fi

exec foundry "$@"
