---
description: Branch Completion Workflow (Automated) - Backup, squash, analyze changes, and create a clean conventional commit.
---

# Branch Completion Workflow (Automated)

**Workspace-scoped automated workflow** - Prepares your branch for PR by creating a clean, squashed commit following conventional commit standards.

## When to Use

Use this prompt when you've completed work on a feature branch and need to:

1. Backup current state
2. Reset to parent branch (squash workflow)
3. Analyze changes
4. Create a clean conventional commit
5. Push final commit

**Note**: This workflow prepares your branch but does NOT create the PR. Use `branch-pr-creation.prompt.md` for PR creation.

## Important: Context Management

**Before running this workflow**:

- **Clean your conversation context** - Close other files and clear unrelated context to avoid confusion
- **Start fresh conversation** if previous context is polluted with unrelated tasks
- This workflow requires focused attention on git operations only

## Automated Execution Flow

### Step 1: Detect Branch Information

**Execute**: `git branch --show-current`

**Extract from branch name** (e.g., `feat/243-backoffice-data-management`):

- **Type**: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `style`, `deps`
- **Scope**: Extract key area (e.g., `backoffice`, `data-management`, `data-ingestion`)
- **Issue number**: If present in branch name (e.g., `243`)

**Validate**: Branch should follow pattern: `<type>/<issue>-<scope>-<description>`

### Step 2: Create Backup Commit

**Check current status first**:

```bash
git status
```

**If there are unstaged/uncommitted changes**:

```bash
git add .
git commit -m "wip: backup before squash"
git push -u origin HEAD
```

**If changes are already committed** (common scenario):

- Skip to Step 3 - your backup already exists on remote

**Wait for**: Push to complete successfully. This is your safety net.

**Important**: Verify all files are committed before proceeding. Uncommitted files will be lost during reset.

### Step 3: Create Local Backup Branch and Reset

**Create local backup branch** (in case something goes wrong):

```bash
git branch backup-<branch-name>
```

**Example**: `git branch backup-feat-243-backoffice-data-management`

**Fetch latest dev and rebase**:

```bash
git fetch origin dev:dev
git reset --hard origin/dev
```

**Expected result**: Your working directory now matches `origin/dev`, and your changes are safely stored in the backup branch.

**Verify backup branch exists**:

```bash
git branch -a | grep backup
```

### Step 4: Analyze Changes from Backup Branch

**Checkout changes from backup branch**:

```bash
git diff backup-<branch-name> --stat
git diff backup-<branch-name>
```

**Find corresponding implementation plan** (if exists):

```bash
# Search for implementation plan with matching issue number
find docs/implementation-plans -name "<issue-number>-*.md" -type f
```

**Example**: For branch `feat/243-backoffice-data-management`, search for `docs/implementation-plans/243-*.md`

**Read the implementation plan** to extract:

- Original problem statement
- Planned approach
- Expected outcomes
- Any documented breaking changes

**Analyze the diff alongside implementation plan**:

- Which files changed (backend/, frontend/, docs/, tests/)?
- Does the implementation match the plan?
- What are the 2-3 key changes?
- Any breaking changes or migration needed?
- Related issues (from branch name, code comments, or implementation plan)

**Use implementation plan content** to enrich commit message context and rationale.

### Step 5: Generate Conventional Commit Message

**Auto-generate based on analysis**:

**Format**:

```
<type>(<scope>): <description>

<context paragraph - why this change is necessary>

Key changes:
- Change 1 with rationale
- Change 2 with rationale

Side effects:
- Any performance impacts
- Migration steps if needed

Relates-to #<issue-number>
```

**Critical Rules**:

- Title max 50 chars, imperative mood, lowercase after type, no period
- Body wrapped at 72 chars
- Explain **what** and **why**, not just **how**
- Use active voice
- Add `BREAKING CHANGE:` footer if applicable
- **Use `Relates-to #` NOT `Closes #`** unless the issue is truly being closed
- Match the footer format to GitHub's linking syntax: `Relates-to`, `See also`, `Follows-up`

### Step 6: Create Final Commit

**Stage ALL changes** (verify nothing is missed):

```bash
git add .
git status  # Verify all expected files are staged
```

**Create commit**:

```bash
git commit -m "<generated-message>"
```

**Verify commit succeeded**:

```bash
git log -1 --stat
```

### Step 7: Push Final Commit

**Execute**:

```bash
git push -u origin HEAD --force-with-lease
```

**Note**: `--force-with-lease` is safe since we rewrote history.

**Next Step**: Your branch is now ready for PR creation. Use `branch-pr-creation.prompt.md` to create the PR.

## Execution Guidelines

### Terminal Tool Usage

- Use `run_in_terminal` tool for each command
- Set `isBackground=false` for commands that complete quickly
- Set `timeout=30000` for git operations, `timeout=60000` for push operations
- Capture and display output to user
- Wait for each command to complete before proceeding

### Error Handling

- If any step fails, stop and show error message
- Provide recovery instructions (e.g., `git reflog` for reset issues)
- Don't proceed to next step if previous step failed

### User Interaction Points

1. **After Step 1**: Confirm detected branch info (type, scope, issue)
2. **After Step 4**: Show commit message draft for approval
3. **After Step 7**: Confirm branch is ready for PR creation

## Checklist

Before running this workflow:

- [ ] All tests pass locally (`make test`)
- [ ] Linter passes (`make lint`, `make format`)
- [ ] No debug statements or console.log
- [ ] Documentation updated if needed
- [ ] Changes are atomic and logical
- [ ] Ready to rewrite history

## Troubleshooting

**Reset went wrong?**

```bash
git reflog  # Find backup commit
git reset --hard HEAD@{1}  # Go back to backup
```

**Need to edit last commit?**

```bash
git commit --amend
git push --force-with-lease
```

**gh CLI not authenticated?**

```bash
gh auth login
```

## Related Resources

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Development Workflow](../docs/src/architecture/workflow-guide.md)

## Lessons Learned & Common Pitfalls

### What We Learned from Real Usage

1. **Always check git status before reset**
   - Uncommitted files will be lost during `git reset`
   - Verify all changes are staged or committed before Step 3

2. **Create backup branch before reset**
   - Local backup branch provides safety net
   - Easier to recover than reflog
   - Delete only after PR verification

3. **Clean conversation context**
   - Close unrelated files before running workflow
   - Start fresh conversation if context is polluted
   - Focus only on git operations

### Common Issues and Solutions

**Issue**: Lost uncommitted changes after reset
**Solution**: Always run `git status` before Step 3, commit everything first

**Issue**: Wrong issue linker in commit footer
**Solution**: Use `Relates-to #` by default, only `Closes #` when certain

**Issue**: Context pollution causes confusion
**Solution**: Clean workspace, close files, start fresh conversation

## Troubleshooting

**Reset went wrong?**

```bash
git reflog  # Find the backup commit
git reset --hard HEAD@{1}  # Go back
```

**Need to edit last commit?**

```bash
git commit --amend
git push --force-with-lease
```

**Lost uncommitted changes?**

```bash
# Recover from backup branch
git checkout backup-<branch-name> -- <file-path>
```
