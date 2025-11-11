# Development Workflow Guide

This guide covers the complete development workflow from issue creation
through production deployment. Follow these processes to ensure smooth
collaboration and code quality.

## Branch Strategy

We use a three-tier promotion model with automatic deployments:

```
main (pre-prod) ← stage (staging) ← dev (development) ← feature branches
```

Each branch maps to an environment:

| Branch  | Environment    | URL                                  | Deploy Trigger    |
| ------- | -------------- | ------------------------------------ | ----------------- |
| `dev`   | Development    | https://co2-calculator-dev.epfl.ch   | Auto on merge     |
| `stage` | Staging        | https://co2-calculator-stage.epfl.ch | Manual sprint end |
| `main`  | Pre-Production | https://co2-calculator.epfl.ch       | Manual with tag   |

Feature branches are created from `dev` and merged back to `dev`.

## Development Process

Follow this step-by-step workflow for all changes:

1. **Create issue** - Describe feature or bug with acceptance criteria
2. **Branch from dev** - `git checkout dev && git checkout -b issue-123-feature-name`
3. **Develop locally** - Code, test, document
4. **Run CI checks** - `make ci` must pass before pushing
5. **Push and PR** - Create pull request targeting `dev`
6. **Code review** - Address feedback within 1-2 days
7. **Merge to dev** - Auto-deploys to development environment
8. **Validate** - Test in dev environment
9. **Promote to stage** - Manual PR at sprint end
10. **Production release** - Tag and deploy to pre-prod

## Pull Request Lifecycle

### Creating Pull Requests

**For feature/fix → dev:**

- PR created by developer
- Review by another IT4R developer
- Final approval by product owner
- Automatic deployment on merge

**For dev → stage:**

- PR created by lead developer
- Review and merge by product owner
- Manual deployment at sprint end

### Review Timeline

| Activity           | Expected Time     |
| ------------------ | ----------------- |
| Code Review        | 1-2 business days |
| Staging Release    | End of sprint     |
| Production Release | As needed (TBD)   |

### Review Criteria

Reviewers verify these aspects before approval:

- **Code Quality** - Follows standards, linter passes
- **Documentation** - Clear comments and updated docs
- **Testing** - 60% coverage, tests pass
- **Security** - No secrets, follows security policy
- **Performance** - No obvious bottlenecks
- **Accessibility** - WCAG AA for UI changes
- **Responsiveness** - Works on mobile/tablet/desktop

For UI changes, include screenshots and test on multiple devices.

## Definition of Done

A feature is complete when:

- ✅ Code implemented with all planned functionality
- 📘 Documentation updated (code comments, README, guides)
- 🧪 Code reviewed and tests passing
- 🧩 Acceptance criteria met (validated by PM)
- 🧼 No critical bugs in staging environment
- 🚀 Deployed to production

## Definition of Ready

Issues are ready for development when:

### Functional Specs (by PM/Stakeholder)

- 🎯 Feature purpose and business value clear
- 🧩 Solution approach validated
- 🎨 Design mockups approved (if UI work)
- 💾 Sample data available
- ✅ Acceptance criteria defined with test strategy

### Technical Specs (by Developer)

- ⚙️ Implementation approach documented
- 🔗 Dependencies identified and managed
- ⏱️ Time estimate provided
- 🤝 Scheduled at sprint planning

## Issue Management

### Issue Labels

Use these labels to categorize and prioritize work:

**Type:**

- `bug` - Something broken
- `feature` - New functionality
- `docs` - Documentation work
- `refactor` - Code improvement
- `security` - Security issue

**Priority:**

- `priority: critical` - Production blocker
- `priority: high` - Important, schedule soon
- `priority: medium` - Normal (default)
- `priority: low` - Nice to have

**Status:**

- `in-review` - Under review
- `in-code-review` - PR submitted
- `pending-spec` - Needs clarification
- `wish` - Future consideration

### Issue Lifecycle

Issues progress through these states:

1. **Open** - Created with template
2. **Triaged** - Labeled and prioritized
3. **Ready** - Meets Definition of Ready
4. **In Progress** - Developer actively working
5. **Review** - PR created, awaiting review
6. **Merged** - PR merged to `dev`
7. **Validated** - Tested in dev environment
8. **Closed** - Resolved and deployed

### Issue Templates

Use appropriate templates when creating issues:

- [Bug Report](https://github.com/EPFL-ENAC/co2-calculator/issues/new?template=bug_report.md)
- [Feature Request](https://github.com/EPFL-ENAC/co2-calculator/issues/new?template=feature_request.md)
- [Documentation](https://github.com/EPFL-ENAC/co2-calculator/issues/new?template=documentation.md)
- [Security Vulnerability](https://github.com/EPFL-ENAC/co2-calculator/security/advisories/new)

## Project Management

All development work flows through GitHub:

- **Planning** - GitHub Projects for sprint boards
- **Tracking** - Issues for all tasks
- **Documentation** - Each delivery includes guides for autonomy
- **Communication** - GitHub Discussions for questions

Sprint cycle:

- Sprint length: 2 weeks
- Planning: Start of sprint
- Review: End of sprint
- Retrospective: End of sprint

## Common Scenarios

### Adding a New Feature

1. Create feature request issue with acceptance criteria
2. Wait for triage and Definition of Ready
3. Branch from `dev`: `git checkout -b issue-456-new-feature`
4. Implement with tests and docs
5. Run `make ci` locally
6. Push and create PR to `dev`
7. Address review feedback
8. Merge and validate in dev environment

### Fixing a Bug

1. Create bug report with reproduction steps
2. Branch from `dev`: `git checkout -b issue-789-fix-bug`
3. Add test that reproduces bug
4. Fix issue and verify test passes
5. Run `make ci` locally
6. Push and create PR to `dev`
7. Reference issue in PR description

### Updating Documentation

1. Create docs issue describing update needed
2. Branch from `dev`: `git checkout -b issue-101-update-docs`
3. Update documentation files
4. Preview changes locally
5. Push and create PR to `dev`
6. Merge after review

For urgent documentation fixes, smaller PRs are acceptable.
