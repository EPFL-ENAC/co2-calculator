---
description: Branch Completion & PR Creation Workflow (Automated) - Complete your branch and create a PR using a two-step workflow.
---

# Branch Completion & PR Creation Workflow (Automated)

**Workspace-scoped automated workflow** - Orchestrates the complete process of finishing a feature branch and creating a GitHub Pull Request.

## Overview

This is the **parent workflow** that combines two specialized workflows:

1. **Flow A**: [`branch-completion.prompt.md`](./branch-completion.prompt.md) - Backup, squash, analyze, and commit
2. **Flow B**: [`branch-pr-creation.prompt.md`](./branch-pr-creation.prompt.md) - Create PR with template and metadata

## When to Use

Use this workflow when you've completed work on a feature branch and need to:

1. ✅ Backup current state
2. ✅ Reset to parent branch (squash workflow)
3. ✅ Analyze changes and craft conventional commit
4. ✅ Push final commit
5. ✅ Create PR with proper template, reviewers, and labels

## Important: Context Management

**Before running this workflow**:

- **Clean your conversation context** - Close other files and clear unrelated context to avoid confusion
- **Start fresh conversation** if previous context is polluted with unrelated tasks
- This workflow requires focused attention on git operations only

## Execution Strategy

### Option 1: Full Automation (Recommended)

Run both flows in sequence within the same conversation:

1. Execute Flow A (branch completion)
2. Verify commit is correct
3. Execute Flow B (PR creation)
4. Clean up backup branch

### Option 2: Step-by-Step

Run each flow separately for more control:

1. Run Flow A, review the commit
2. Start fresh conversation if needed
3. Run Flow B to create PR

## Automated Execution Flow

### Phase 1: Branch Completion

**Execute**: Flow A from [`branch-completion.prompt.md`](./branch-completion.prompt.md)

**Steps**:

1. Detect branch information
2. Create backup commit and push
3. Create local backup branch and reset to dev
4. Analyze changes from backup branch
5. Generate conventional commit message
6. Create final commit
7. Push final commit

**Expected outcome**: Your branch has a clean, squashed commit ready for PR.

**Verification**:

```bash
git status  # Should be clean
git log -1  # Should show conventional commit
```

### Phase 2: PR Creation

**Execute**: Flow B from [`branch-pr-creation.prompt.md`](./branch-pr-creation.prompt.md)

**Steps**:

1. Verify clean state
2. Extract PR metadata from commit
3. Generate PR body from template
4. Ask for reviewers
5. Create PR using gh CLI
6. Output PR information

**Expected outcome**: PR created on GitHub with proper metadata.

### Phase 3: Cleanup (Optional)

**After PR verification**:

```bash
git branch -d backup-<branch-name>
```

**Example**: `git branch -d backup-feat-243-backoffice-data-management`

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
- Don't proceed to next phase if previous phase failed

### User Interaction Points

1. **After Phase 1, Step 1**: Confirm detected branch info (type, scope, issue)
2. **After Phase 1, Step 4**: Show commit message draft for approval
3. **Before Phase 2, Step 4**: Ask for reviewer username
4. **After Phase 2**: Ask if backup branch should be deleted

## Checklist

Before running this workflow:

- [ ] All tests pass locally (`make test`)
- [ ] Linter passes (`make lint`, `make format`)
- [ ] No debug statements or console.log
- [ ] Documentation updated if needed
- [ ] Changes are atomic and logical
- [ ] Ready to rewrite history
- [ ] gh CLI is authenticated (`gh auth status`)

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

**Lost uncommitted changes?**

```bash
# Recover from backup branch
git checkout backup-<branch-name> -- <file-path>
```

## Related Resources

- [Branch Completion Workflow](./branch-completion.prompt.md) - Flow A details
- [PR Creation Workflow](./branch-pr-creation.prompt.md) - Flow B details
- [Conventional Commits](https://www.conventionalcommits.org/)
- [gh CLI Documentation](https://cli.github.com/)
- [Development Workflow](../docs/src/architecture/workflow-guide.md)
- [PR Template](../.github/PULL_REQUEST_TEMPLATE.md)

## Lessons Learned & Common Pitfalls

### What We Learned from Real Usage

1. **Always check git status before reset**
   - Uncommitted files will be lost during `git reset`
   - Verify all changes are staged or committed before Phase 1, Step 3

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
**Solution**: Always run `git status` before Phase 1, Step 3, commit everything first

**Issue**: Wrong issue linker in commit footer
**Solution**: Use `Relates-to #` by default, only `Closes #` when certain

**Issue**: Context pollution causes confusion
**Solution**: Clean workspace, close files, start fresh conversation

## Workflow Architecture

```
┌─────────────────────────────────────────────────────┐
│  Branch Completion & PR Creation (Parent Workflow) │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────┐
        │  Phase 1: Branch Completion     │
        │  (branch-completion.prompt.md)  │
        │                                 │
        │  1. Detect branch info          │
        │  2. Backup commit & push        │
        │  3. Create backup branch        │
        │  4. Reset to dev                │
        │  5. Analyze changes             │
        │  6. Generate commit message     │
        │  7. Create & push commit        │
        └─────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────┐
        │  Phase 2: PR Creation           │
        │  (branch-pr-creation.prompt.md) │
        │                                 │
        │  1. Verify clean state          │
        │  2. Extract PR metadata         │
        │  3. Generate PR body            │
        │  4. Get reviewers               │
        │  5. Create PR                   │
        │  6. Output PR info              │
        └─────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────┐
        │  Phase 3: Cleanup (Optional)    │
        │                                 │
        │  Delete backup branch           │
        └─────────────────────────────────┘
```
