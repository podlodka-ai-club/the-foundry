#!/usr/bin/env bash
set -euo pipefail

# Edit these two lines to change what the next run creates.
TITLE="Prepare minimal fastapi project"
BODY="as small as you can, but working"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f .env ]]; then
  echo "error: .env not found in $REPO_ROOT" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

: "${SOURCE_REPO:?SOURCE_REPO must be set in .env}"
LABEL="${ISSUE_LABEL:-agent-task}"

echo "==> creating issue in $SOURCE_REPO (label=$LABEL)"
ISSUE_URL="$(gh issue create --repo "$SOURCE_REPO" --title "$TITLE" --body "$BODY" --label "$LABEL")"
echo "    $ISSUE_URL"
ISSUE_NUMBER="${ISSUE_URL##*/}"

# GitHub issue-list is eventually consistent — wait until our new issue shows up
# in the labeled listing before calling foundry, otherwise fetch may return 0.
echo "==> waiting for issue #$ISSUE_NUMBER to appear in labeled listing"
for i in 1 2 3 4 5 6 7 8 9 10; do
  if gh issue list --repo "$SOURCE_REPO" --label "$LABEL" --state open --json number \
       --jq ".[] | select(.number == $ISSUE_NUMBER) | .number" | grep -q "$ISSUE_NUMBER"; then
    echo "    visible after ${i}s"
    break
  fi
  sleep 1
done

echo "==> running foundry"
uv run foundry run
