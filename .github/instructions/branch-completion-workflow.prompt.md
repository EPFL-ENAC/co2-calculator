# Branch Completion & PR Creation Workflow (Automated)

**Workspace-scoped automated workflow** - Executes all commands via terminal tools to complete your branch and create a PR.

## When to Use

Use this prompt when you've completed work on a feature branch and need to automate:

1. Backup commit and push
2. Reset to parent branch (squash workflow)
3. Analyze changes and craft conventional commit
4. Push final commit
5. Create PR with proper template, reviewers, and labels

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

### Step 8: Create PR with Full Automation

**Verify clean state before PR creation**:

```bash
git status  # Should show clean working directory
git log -1  # Verify commit is correct
```

**Auto-detect PR metadata**:

- **Base branch**: `dev` (default)
- **Title**: Use commit message title (first line)
- **Reviewers**: Prompt user or use default from branch scope
- **Labels**: Map from commit type:
  - `feat` → `type: feature`
  - `fix` → `type: bugfix`
  - `refactor` → `type: refactor`
  - `docs` → `type: documentation`
  - `test` → `type: test`
  - `chore` → `type: chore`
  - `deps` → `dependencies`

**Generate PR body** from template:

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

**Execute** (use `--web` flag for manual body editing - more reliable):

```bash
gh pr create \
  --title "<commit-title>" \
  --base dev \
  --label "<label>" \
  --web  # Opens browser for body editing
```

**Alternative** (if `--web` not available, use body file):

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

**Output**: Show PR URL and confirmation message.

**Note**: `--web` flag is preferred over `--body` or `--body-file` to avoid shell escaping issues with multi-line content.

### Step 9: Cleanup Backup Branch (Optional)

**After PR is successfully created and verified**:

```bash
# Ask user for confirmation
"PR created successfully! Delete backup branch?"

# If user confirms:
git branch -d backup-<branch-name>
```

**Example**: `git branch -d backup-feat-243-backoffice-data-management`

**Purpose**: Clean up temporary backup branch once workflow is complete and verified.

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
3. **Before Step 8**: Ask for reviewer username if not auto-detected

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

**Wrong base branch?**

```bash
gh pr edit <pr-number> --base main  # Change PR base
```

**gh CLI not authenticated?**

```bash
gh auth login
```

## Related Resources

- [Conventional Commits](https://www.conventionalcommits.org/)
- [gh CLI Documentation](https://cli.github.com/)
- [Development Workflow](../docs/src/architecture/workflow-guide.md)
- [PR Template](../.github/PULL_REQUEST_TEMPLATE.md)

## Lessons Learned & Common Pitfalls

### What We Learned from Real Usage

1. **Always check git status before reset**
   - Uncommitted files will be lost during `git reset`
   - Verify all changes are staged or committed before Step 3

2. **Use `--web` flag for PR creation**
   - Multi-line `--body` arguments cause shell escaping issues
   - `--body-file` can fail with heredoc syntax in terminals
   - `--web` opens browser for reliable manual editing

3. **Use `Relates-to` not `Closes`**
   - Only use `Closes #` when issue is truly complete
   - `Relates-to #` is safer for ongoing work
   - Match GitHub's linking syntax exactly

4. **Create backup branch before reset**
   - Local backup branch provides safety net
   - Easier to recover than reflog
   - Delete only after PR verification

5. **Clean conversation context**
   - Close unrelated files before running workflow
   - Start fresh conversation if context is polluted
   - Focus only on git operations

### Common Issues and Solutions

**Issue**: PR creation fails with heredoc errors
**Solution**: Use `--web` flag instead of `--body` or `--body-file`

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

**Wrong base branch?**

```bash
gh pr edit --base main  # Change PR base
```

**PR creation fails?**

```bash
# Use web interface instead
gh pr create --web
```

**Lost uncommitted changes?**

```bash
# Recover from backup branch
git checkout backup-<branch-name> -- <file-path>
```
