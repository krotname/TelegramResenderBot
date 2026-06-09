#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <owner/repo> [branch ...]"
  exit 1
fi

REPO="$1"
shift

if [ $# -eq 0 ]; then
  BRANCHES=("main" "master")
else
  BRANCHES=("$@")
fi

PROTECTION_PAYLOAD=$(cat <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "lint (3.12)",
      "lint (3.13)",
      "types (3.12)",
      "types (3.13)",
      "tests (3.12)",
      "tests (3.13)",
      "security",
      "Analyze (python)"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "require_last_push_approval": true,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": true
}
JSON
)

for BRANCH in "${BRANCHES[@]}"; do
  if ! gh api "repos/${REPO}/branches/${BRANCH}" --silent >/dev/null 2>&1; then
    echo "Skipping ${BRANCH}: branch not found."
    continue
  fi

  echo "Applying protection to ${BRANCH}."
  printf '%s\n' "$PROTECTION_PAYLOAD" | gh api \
    --method PUT \
    --input - \
    -H "Accept: application/vnd.github+json" \
    "repos/${REPO}/branches/${BRANCH}/protection"
done

echo "Done."
