#!/bin/bash

# 1. Identify current branch and find associated PR
CURRENT_BRANCH=$(git branch --show-current)
PR_JSON=$(gh pr view "$CURRENT_BRANCH" --json number,title,baseRefName 2>/dev/null)

if [ $? -ne 0 ]; then
  echo "Error: No PR found for branch '$CURRENT_BRANCH'. Make sure you've pushed and created a PR."
  exit 1
fi

PR_NUMBER=$(echo "$PR_JSON" | jq -r '.number')
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

# 2. Extract Issue ID from branch name (assumes digits at start or after a slash)
# Regex matches the first sequence of numbers found in the branch name.
# Falls back to the PR number when the branch name has no digits, so this
# still works for PRs that aren't tied to a numbered issue.
ISSUE_ID=$(echo "$CURRENT_BRANCH" | grep -oE '[0-9]+' | head -1)

if [ -z "$ISSUE_ID" ]; then
  ISSUE_ID="$PR_NUMBER"
fi

# 3. Write to the code-review directory (transient review artifacts, not plans).
REPO_ROOT=$(git rev-parse --show-toplevel)
REVIEW_DIR="$REPO_ROOT/docs/code-review"
mkdir -p "$REVIEW_DIR"

# Create a kebab-case description from the PR title
DESC=$(echo "$PR_JSON" | jq -r '.title' | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')
OUTPUT_FILE="$REVIEW_DIR/$ISSUE_ID-copilot-feedback-$DESC.md"

echo "Targeting PR #$PR_NUMBER for Issue #$ISSUE_ID"
echo "Saving to: $OUTPUT_FILE"

# 4. Fetch and format the comments
{
  echo "# Bot Review TODOs: PR #$PR_NUMBER"
  echo "Source Branch: \`$CURRENT_BRANCH\`"
  echo "---"

  echo "## Raw Feedback"

  # Fetch Review Summaries
  gh pr view "$PR_NUMBER" --json reviews \
    --jq '.reviews[] | select(.author.login | test("copilot|github-actions|advanced-security"; "i")) | "### Summary Feedback (\(.author.login))\n\(.body)\n---"'

  # Fetch Inline Comments
  gh api "repos/$REPO/pulls/$PR_NUMBER/comments" \
    --jq '.[] | select(.user.login | test("copilot|github-actions|advanced-security"; "i")) | "### File: `\(.path)` (Line \(.line)) — \(.user.login)\n\n\(.body)\n---"'
} > "$OUTPUT_FILE"

# Emit a machine-readable marker on the final line so callers can capture the path.
echo "OUTPUT_FILE=$OUTPUT_FILE"
