---
description: PR Creation Workflow (Automated) - Create a GitHub PR with proper template, reviewers, and labels.
---

# PR Creation Workflow (Automated)

**Workspace-scoped automated workflow** - Creates a GitHub Pull Request with proper template, reviewers, and labels using the gh CLI.

## When to Use

Use this prompt AFTER completing the branch completion workflow (`branch-completion.prompt.md`) when you need to:

1. Create a PR with proper metadata
2. Apply correct labels based on commit type
3. Add reviewers
4. Generate PR body from template

**Prerequisite**: Your branch should already have a clean, squashed commit from the branch completion workflow.

## Automated Execution Flow

### Step 1: Verify Clean State

**Execute**:

```bash
git status
git log -1 --stat
```

**Verify**:

- Working directory is clean (no uncommitted changes)
- Last commit message follows conventional commit format
- All expected files are included in the commit

**If issues found**: Stop and fix before proceeding.

### Step 2: Extract PR Metadata

**From the commit message**, extract:

- **Title**: First line of commit message
- **Type**: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `style`, `deps`
- **Scope**: Area of change (e.g., `backoffice`, `data-management`)
- **Issue number**: From commit footer or branch name

**Map commit type to PR labels**:

- `feat` → `type: feature`
- `fix` → `type: bugfix`
- `refactor` → `type: refactor`
- `docs` → `type: documentation`
- `test` → `type: test`
- `chore` → `type: chore`
- `deps` → `dependencies`

**Base branch**: `dev` (default)

### Step 3: Generate PR Body

**Use this template**:

```markdown
## What does this change?

<2-3 sentence summary from commit message context>

## Why is this needed?

<Problem statement - why this change is necessary>

## Type of change

Please check the type that applies:

- [ ] 🐛 Bug fix
- [ ] ✨ New feature
- [ ] 📝 Documentation update
- [ ] 🎨 Design/UI improvement
- [ ] 🔧 Configuration change
- [ ] 🧹 Code cleanup

## Code quality checklist

- [x] I confirm that my contribution is original and that I assign all intellectual property rights in this contribution to EPFL, retaining no ownership rights.
- [x] Code follows our standards (linter passes)
- [x] No hardcoded values or secrets
- [x] Documentation updated for new features
- [x] Commit messages follow convention
- [x] No console.log or debug statements

## Testing checklist

- [ ] I've tested this change locally
- [ ] `make ci` passes without errors
- [ ] Tests added/updated (60% coverage minimum)
- [ ] No test failures introduced

## Related issues

- Relates-to #<issue-number>
```

**Fill in**:

- Summary from commit message body
- Problem statement from implementation plan or commit context
- Issue number from commit footer or branch name

### Step 4: Ask for Reviewers

**Prompt user**:

"Who should review this PR? (GitHub username, or leave blank for default)"

**Default reviewers by scope** (if configured):

- `backoffice` → team-lead
- `frontend` → frontend-team
- `backend` → backend-team
- `data` → data-team

### Step 5: Create PR

**Preferred method** (use `--web` flag for manual body editing):

```bash
gh pr create \
  --title "<commit-title>" \
  --base dev \
  --label "<label>" \
  --web
```

**Why `--web`?**: Opens browser for reliable manual editing of PR body, avoids shell escaping issues with multi-line content.

**Alternative method** (if `--web` not available):

```bash
# Create temporary body file in workspace root
cat > .github/PR_BODY.md << 'EOFMARKER'
<pr-body-content>
EOFMARKER

gh pr create \
  --title "<commit-title>" \
  --body-file .github/PR_BODY.md \
  --base dev \
  --label "<label>"
```

**Add reviewers** (after PR creation):

```bash
gh pr edit <pr-number> --add-reviewer <username>
```

### Step 6: Output PR Information

**Display to user**:

- PR URL
- PR number
- Confirmation message
- Next steps (monitor CI, respond to reviews)

**Example**:

```
✅ PR created successfully!

PR #243: feat(backoffice): implement data management
🔗 https://github.com/org/repo/pull/243
📋 Labels: type: feature
👀 Reviewers: @team-lead

Next steps:
- Monitor CI/CD pipeline
- Respond to reviewer feedback
- Merge when approved and all checks pass
```

## Execution Guidelines

### Terminal Tool Usage

- Use `run_in_terminal` tool for each command
- Set `isBackground=false` for commands that complete quickly
- Set `timeout=30000` for gh CLI operations
- Capture and display output to user

### Error Handling

- If PR creation fails, show error message
- Provide recovery instructions
- Don't proceed if gh CLI is not authenticated

### User Interaction Points

1. **Before Step 3**: Confirm PR body content
2. **At Step 4**: Ask for reviewer username
3. **After Step 6**: Ask if backup branch should be deleted

## Checklist

Before creating PR:

- [ ] Branch completion workflow completed
- [ ] Commit message follows conventional commit format
- [ ] All tests pass locally (`make test`)
- [ ] Linter passes (`make lint`, `make format`)
- [ ] PR body template filled correctly
- [ ] Reviewers identified

## Troubleshooting

**gh CLI not authenticated?**

```bash
gh auth login
```

**PR creation fails with heredoc errors?**

**Solution**: Use `--web` flag instead of `--body` or `--body-file`

**Wrong base branch?**

```bash
gh pr edit <pr-number> --base main  # Change PR base
```

**Need to update PR after creation?**

```bash
gh pr edit <pr-number> --title "new title" --body "new body"
gh pr edit <pr-number> --add-label "label-name"
gh pr edit <pr-number> --add-reviewer "username"
```

## Related Resources

- [gh CLI Documentation](https://cli.github.com/)
- [PR Template](../.github/PULL_REQUEST_TEMPLATE.md)
- [Development Workflow](../docs/src/architecture/workflow-guide.md)

## Lessons Learned & Common Pitfalls

### What We Learned from Real Usage

1. **Use `--web` flag for PR creation**
   - Multi-line `--body` arguments cause shell escaping issues
   - `--body-file` can fail with heredoc syntax in terminals
   - `--web` opens browser for reliable manual editing

2. **Use `Relates-to` not `Closes`**
   - Only use `Closes #` when issue is truly complete
   - `Relates-to #` is safer for ongoing work
   - Match GitHub's linking syntax exactly

3. **Verify clean state before PR**
   - Check `git status` and `git log -1` before creating PR
   - Ensure commit message is correct
   - Catch issues early before PR creation

### Common Issues and Solutions

**Issue**: PR creation fails with heredoc errors
**Solution**: Use `--web` flag instead of `--body` or `--body-file`

**Issue**: Wrong issue linker in PR body
**Solution**: Use `Relates-to #` by default, only `Closes #` when certain

**Issue**: Can't add reviewers during creation
**Solution**: Add reviewers after PR creation with `gh pr edit --add-reviewer`

## Cleanup After PR Creation

**After PR is successfully created and verified**:

```bash
# Ask user for confirmation
"PR created successfully! Delete backup branch?"

# If user confirms:
git branch -d backup-<branch-name>
```

**Example**: `git branch -d backup-feat-243-backoffice-data-management`

**Purpose**: Clean up temporary backup branch once workflow is complete and verified.
