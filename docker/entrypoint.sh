#!/bin/sh
set -eu

if command -v gh >/dev/null 2>&1; then
  git config --global credential.https://github.com.helper '!gh auth git-credential'
fi

git config --global --add safe.directory '*'

exec "$@"
