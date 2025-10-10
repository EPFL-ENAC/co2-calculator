# Contributing Guide – CO₂ Calculator @ EPFL

Thanks for your interest in contributing to the CO₂ Calculator project! 🎉

This guide ensures quality, security, maintainability, and longevity of our codebase, following EPFL project specifications.

---

## Table of Contents

### 📖 Getting Started

- [Quick Start](#quick-start)
- [Need Help?](#need-help)
- [Development Setup](#development-setup)
- [Local Development](#local-development)
- [Debugging & Troubleshooting](#debugging--troubleshooting)

### 🔧 Development Standards

- [Code Standards](#code-standards)
- [Security](#security)
- [Performance](#performance)
- [Testing](#testing)
- [CI/CD](#cicd-pipeline)
- [Commit Messages](#commit-messages)
- [Dependencies Management](#dependencies-management)

### 🔄 Processes

- [Project Management](#project-management)
- [Development Workflow](#development-workflow)
- [Issue Management](#issue-management)
- [Release Process](#release-process)
- [Environment Release Process](#environment-release-process)
- [Emergency Hotfix Process](#emergency-hotfix-process)
- [RFC Process](#rfc-process-request-for-comments)

---

## Getting Started

## Quick Start

**New contributors:**

1. Fork the repository
2. Create an issue describing your fix/feature
3. Follow our [Git Workflow](#git-workflow) process

**TL;DR:** `Issue → Branch from dev → Code → Test → PR to dev → Review (1-2 days) → Merge → Auto-deploy`

## Need Help?

- 💬 [Start a discussion](https://github.com/EPFL-ENAC/epfl-calculator-co2/discussions) for questions
- 📋 [Create an issue](https://github.com/EPFL-ENAC/epfl-calculator-co2/issues/new/choose) to report bugs or request features
- 📖 Read our [Code of Conduct](https://github.com/EPFL-ENAC/epfl-calculator-co2/blob/main/CODE_OF_CONDUCT.md)
- 📧 Email **enacit4research@epfl.ch** for technical support

---

## Development Setup

Every possible script/code running entry should pass via the Makefile

```bash
make install  # Install dependencies
```

**Requirements:** Node.js LTS, npm, GNU Make

### Editor Setup (Recommended)

- ESLint plugin
- Prettier plugin
- TypeScript support
- Stylelint plugin

---

## Local Development

### Running the Project Locally

All development commands run through the Makefile and Docker Compose:

```bash
make run          # Start all services locally
make stop         # Stop all services
make logs         # View service logs
make shell        # Access container shell
```

### Technology Stack

- **Backend**: Python with `uv` for dependency management
- **Frontend**: Node.js with `npm`
- **Database**: PostgreSQL with Alembic migrations
- **Container**: Docker Compose for orchestration

### Environment Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Update `.env` with your local settings (see `.env.example` for documentation)
3. **Never commit** `.env` files or secrets to the repository

### Database Migrations

We use **Alembic** for database schema management:

```bash
make migrate         # Run pending migrations
make migration-new   # Create new migration
make migration-down  # Rollback last migration
```

---

## Debugging & Troubleshooting

### Common Issues

**Database connection errors:**

- Verify `.env` database credentials
- Ensure database container is running: `docker-compose ps`
- Check logs: `make logs`

**Dependencies out of sync:**

```bash
make clean install  # Clean and reinstall all dependencies
```

### Debugging

**Backend (Python):**

- Add breakpoints using `import pdb; pdb.set_trace()`
- View logs: `make logs backend`

**Frontend:**

- Use browser DevTools (browser extension for vuejs and pinia)
- Add breakpoints
- View logs: `make logs frontend`
- Run dev mode: `make dev-frontend`

### Logs Location

- **Container logs**: `docker-compose logs -f [service-name]`
- **Application logs**: Check `logs/` directory (if configured)
- **CI/CD logs**: GitHub Actions tab in repository

---

## Development Standards

## Code Standards

### Documentation

- Code must be documented with clear, concise comments that explain business logic and technical choices
- Each module should include technical documentation (README, installation guide, API docs)
- Use English for all documentation and comments

### General Principles

- Use consistent naming conventions
  - camelCase: JAVASCRIPT + TYPESCRIPT
  - snake_case: PYTHON
  - KEBAB-case: file name
  - (DTO) + database column name: snake_case
  - For data: don't mix or translate naming convention accross env (if database columns backend is python and snake_case is database + api choice, then frontend will use snake_case always (no exception))
- Keep a clear, coherent file structure that matches the project architecture

### JavaScript/TypeScript

- Follow team standards with ESLint + Prettier
- Document complex business logic
- Use TypeScript types appropriately

### HTML

- **WCAG Level AA compliant**
- Use semantic tags (not just divs/spans)
- Keyboard accessible with visible focus states
- Responsive design (mobile to desktop)

### CSS

- Use design tokens, no hardcoded values
- Prefer rem/em over px
- No component library overrides

### Python

- Follow **PEP8** and [Python Guide](https://docs.python-guide.org/writing/style/)
- Use type hints where appropriate
- Document functions and classes with docstrings
- unit test + integration test using pytest

---

## Security

- [MANDATORY] Never commit secrets, API keys, or sensitive data

---

## Performance

- [OPTIONAL] Code should be optimized to avoid bottlenecks
- [OPTIONAL] Load and performance tests must be integrated into the CI/CD pipeline for the backend only
  - Exception is made for the frontend
- [OPTIONAL] Profile code when working on performance-critical sections

---

## Testing

### Requirements

- **Unit tests**: Every feature must have unit tests (if it makes sense, sometime only integration make sense)
- **Integration tests**: Test feature interactions
- **E2E tests**: Critical user flows must be covered
- **Coverage**: 60%
- **Non-regression**: Run full test suite after every update (release)

### Running Tests

```bash
make test  # Run full test suite
```

---

## CI/CD Pipeline

### DevSecOps Approach

We follow automated CI/CD with security scanning and testing.

### Automated Checks

All pull requests trigger GitHub Actions workflows that run:

- **Linting**: ESLint (JS/TS), Stylelint (CSS), Ruff/Black (Python)
- **Testing**: Full test suite must pass with 60% coverage minimum
- **Security**: Dependency vulnerability scans via Dependabot and `uv pip audit` (Python), `npm audit` (Node.js)
- **Build**: Docker image build validation

### Merge Requirements

- All status checks must pass (green) before merge is allowed
- Dependabot security alerts must be resolved or explicitly acknowledged
- Code review approval required (see [PR Review Criteria](#pr-review-criteria))

### Deployment Pipeline

- **dev branch**: Auto-deploys to development environment on merge
- **stage branch**: Auto-deploys to staging environment on merge
- **main branch**: Auto-deploys to pre-production environment on git tag/ github release

See [Development Workflow](#development-workflow) for the complete promotion process.

## Commit Messages

We use **conventional commits** for consistency:

- `feat: add new feature`
- `fix: resolve bug`
- `docs: update documentation`
- `test: add or update tests`
- `refactor: code refactoring`
- `style: formatting changes`
- `chore: maintenance tasks`

---

## Dependencies Management

### Adding New Dependencies

**Backend (Python with uv):**

```bash
uv add package-name==X.Y.Z
make install  # Update lock file
```

**Frontend (npm):**

```bash
npm install package-name@X.Y.Z --save-exact
```

### Version Pinning Policy

- **HARD versioning required** - Always pin exact versions
- Use `==X.Y.Z` for Python, `"X.Y.Z"` for npm
- No version ranges `~`, `^`) allowed
- Document why each dependency is needed

### Upgrade Strategy

- **Security updates only** unless approved by project manager
- Monitor security advisories (Dependabot, npm audit)
- Test thoroughly in dev environment before promoting
- Document breaking changes in PR description

### Breaking Changes

- Major version upgrades require RFC (see [RFC Process](#rfc-process-request-for-comments))
- Document migration path in `MIGRATION.md`
- Provide both upgrade and downgrade scripts
- Communicate changes in release notes

---

## Processes

## Project Management

- All development planning _MUST_ go through github projects and issues.
- Each delivery must include documentation and guides needed to enable the internal team to operate autonomously

## Development Workflow

### Branch Strategy

We use a three-tier branching model:

```
main (pre-production) ← stage (staging) ← dev (development) ← feature/fix branches
```

**Branch Descriptions:**

- \*`main`\*\*: Pre-production code, deployed to https://{NAME}.epfl.ch
- \*`stage`\*\*: Staging environment, deployed to https://{NAME}-stage.epfl.ch
- \*`dev`\*\*: Active development, auto-deployed to https://{NAME}-dev.epfl.ch
- \*`feature/fix branches`\*\*: Individual feature or bug fix branches created from `dev`

### Environments

| Environment        | Branch  | URL                          | Deployment                            |
| ------------------ | ------- | ---------------------------- | ------------------------------------- |
| **Development**    | `dev`   | https://{NAME}-dev.epfl.ch   | Automatic on merge                    |
| **Staging**        | `stage` | https://{NAME}-stage.epfl.ch | Manual End of sprint: `dev` → `stage` |
| **Pre-Production** | `main`  | https://{NAME}.epfl.ch       | /!\ TBD /!\ : `stage` → `main`        |

### Development Process

**Full Workflow:**

```
Issue → Branch → PR → Code Review → Merge to Dev → Staging → Production
```

**Step-by-step:**

1. **Create an issue** describing the feature or fix
2. **Create a branch** from `dev`: `git checkout -b issue-123-feature-name`
3. **Develop** your changes with proper documentation
4. **Test locally** - `make test` must pass
5. **Push** and create **pull request** to `dev`
6. **Code review** - address all feedback (< 2 days)
7. **Merge to `dev`** → Auto-deploys to development environment
8. **Validate** in dev environment
9. **Promote to `stage`** → Manual deployment end of sprint: TBD
10. **Staging validation** → Final testing before production: TBD
11. **Promote to `main`** → Pre-Production release: use `v0.x.x` versioning TBD

### PR Lifecycle Process

**Pull Request Validation Requirements:**

- **feat → dev**: PR must be created by (1) another dev IT4R, (2) validated by third party, (3) merged by product owner
- **dev → stage**: PR must be created by lead dev and validated (merged) by product owner

### Timeline & SLA

| Activity           | Timeframe         |
| ------------------ | ----------------- |
| Code Review        | 1-2 business days |
| Staging Release    | End of sprint     |
| Production Release | TBD               |

### PR Review Criteria

TBD with code reviewer (should be in pull_REQUEST_TEMPLATE.md)

- [ ] description of changes
- [ ] Code documentation
- [ ] Adherence to standards and best practices
- [ ] Security considerations
- [ ] Performance impact
- [ ] Test coverage
- [ ] Responsiveness (for UI changes)
- For UI Changes:
  - [ ] screenshots/GIFs/videos demonstrating the changes
  - [ ] accessibility (keyboard navigation, screen readers)
  - [ ] Test on different screen sizes
  - [ ] Link related issues

### Definition of Done

- ✅ Code completed — all planned functionalities implemented. (Developer)
- 📘 Documentation updated — relevant documentation, user guides, or release notes are updated. (Developer)
- 🧪 Code reviewed and tested — acceptance tests succeed, PR merged (Code reviewer)
- 🧩 Meets acceptance criteria — fulfills all user story acceptance criteria (PM)
- 🧼 No critical bugs — the feature works as intended with no blocking defects (tested in stage - QA by TBD ?)
- 🚀 Integrated and deployed (to Prod.) (Developer)

---

## Issue Management

### Issue Labels

**Type:**

- `bug` - Something isn't working
- `feature` - New functionality
- `docs` - Documentation improvements
- `refactor` - Code quality improvements
- `security` - Security-related issues

**Priority:**

- `priority: critical` - Blocks production, needs immediate attention
- `priority: high` - Important, schedule soon
- `priority: medium` - Normal priority (default)
- `priority: low` - Nice to have, low urgency

**Status:**

- `in-review` -
- `in-code-review` -
- `pending-spec` -
- `wish` -

### Issue Lifecycle

1. **Open** - Issue created with template
2. **Triaged** - Labeled and prioritized by team
3. **Ready** - In developer's to-do list
4. **In Progress** - Active development
5. **Review** - Code review in progress (PR created)
6. **Merged** - PR merged to `dev`
7. **Validated** - Tested in dev environment
8. **Closed** - Issue resolved and deployed

### Issue Templates

Use our [issue templates](https://github.com/EPFL-ENAC/epfl-calculator-co2/issues/new/choose):

- Bug Report
- Feature Request
- Documentation Update
- Security Vulnerability

---

## Release Process

### Versioning

We follow **Semantic Versioning (SemVer)** with a phased approach:

- `MAJOR.MINOR.PATCH` (e.g., `1.2.3`)
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

### Versioning Strategy

Our versioning strategy distinguishes between internal/non-public releases and public-facing releases:

1. **Internal/Non-Public Releases** (`v0.x.x`):

   - Tagged versions released at the end of each sprint (sprints 1-9)
   - Format: `v0.MINOR.PATCH` (e.g., `v0.1.2`)
   - Intended for internal testing and validation only
   - Not public-facing releases
   - Represent pre-production status

2. **Public-Facing Release** (`v1.0.0`):
   - First official public release
   - Released at the end of the 10-sprint development process
   - Format: `v1.0.0` (following semantic versioning)
   - Production-ready with full functionality and documentation

### Automated Releases

- **Changelog**: Auto-generated via `release-please` GitHub workflow
- **Release Notes**: Automatically created from conventional commits
- **Tagging**: Automatic on merge to `main`: TBD ()
- **Cycle**: End of sprint promotions through dev → stage → main (see [Development Workflow](#development-workflow))

### Migration Guides

For breaking changes, document in `MIGRATION.md`:

- Version-specific upgrade instructions
- Downgrade procedures
- Database migration scripts
- Configuration changes needed

---

## Environment Release Process

### Pre-Production vs Production

Our release process distinguishes between internal/non-public releases and public-facing releases:

1. **Pre-Production Environment** (Internal/Non-Public Releases):

   - Used during active development cycles (sprints 1-9)
   - Runs `v0.x.x` tagged versions released at the end of each sprint
   - Intended for internal testing and validation only
   - Not public-facing

2. **Production Environment** (Public-Facing Release):
   - Activated at the end of the project (after sprint 10)
   - Runs stable `v1.0.0` and subsequent versions
   - First public-facing release is `v1.0.0`
   - Requires full validation and approval
   - Only production-ready code should be promoted here

### PM Testing Process

- PM conducts pre-sprint release testing in the dev environment
- Testing occurs 2-3 days before sprint completion
- Final validation happens in stage environment before pre-production promotion

### Environment Promotion Rules

- All code must pass through dev → stage → main progression
- Each environment has specific validation requirements
- Manual approvals required for stage and production promotions
- Pre-prod releases use `v0.x.x` versioning
- Production releases begin with `v1.0.0`

---

## Emergency Hotfix Process

For **critical production bugs** that can't wait for the regular release cycle:

### Hotfix Workflow

1. **Create hotfix branch** from `main`:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b hotfix/critical-bug-description
   ```
2. **Fix the issue** with minimal changes
3. **Test thoroughly** - hotfixes have higher risk
4. **Fast-track PR** to `main`:
   - Label as `priority: critical`
   - Request immediate review from Lead Developer + Project Manager
   - Skip staging validation (emergency only)
5. **Merge to `main`** and deploy immediately
6. **Backport to `dev` and `stage`**:
   ```bash
   git checkout dev
   git cherry-pick <hotfix-commit>
   git push origin dev
   ```

### Fast-Track Approval

- **Review SLA**: 2-4 hours (during business hours)
- **Approvers**: Minimum Lead Developer OR Project Manager
- **Post-deployment**: Document incident and root cause

---

## RFC Process

_Request for Comments process for major architectural decisions_
TBD

---

_Thank you for helping make the CO₂ Calculator project better! Your contributions make a difference in advancing sustainability research at EPFL._
