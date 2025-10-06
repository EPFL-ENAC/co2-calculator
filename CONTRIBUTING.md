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
- [Commit Messages](#commit-messages)
- [Dependencies Management](#dependencies-management)

### 🔄 Processes
- [Project Management](#project-management)
- [Git Workflow](#git-workflow)
- [RFC Process](#rfc-process-request-for-comments)
- [Release Process](#release-process)
- [Emergency Hotfix Process](#emergency-hotfix-process)
- [Issue Management](#issue-management)

---

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

**Port already in use:**
```bash
make stop  # Stop all services
lsof -ti:PORT | xargs kill -9  # Kill process on port
```

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
- Access shell: `make shell backend`

**Frontend:**
- Use browser DevTools
- View logs: `make logs frontend`
- Run dev mode: `make dev-frontend`

### Logs Location

- **Container logs**: `docker-compose logs -f [service-name]`
- **Application logs**: Check `logs/` directory (if configured)
- **CI/CD logs**: GitHub Actions tab in repository

---

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
   - (DTO) +database column name: snake_case
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

- Follow **OWASP best practices** (input validation, secure session management, etc.)
- Identified vulnerabilities must be fixed immediately
- EPFL reserves the right to perform external security audits
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
- **Coverage**: Must meet EPFL-defined threshold (measured automatically) *WArNING* TODEFINE
- **Non-regression**: Run full test suite after every update (release)

### Running Tests

```bash
make test  # Run full test suite
```

**CI/CD**: Tests run automatically on PR. All must pass before merge.

---

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
- No version ranges (`~`, `^`) allowed
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


## Project Management 

- All development planning _MUST_ go through github projects and issues.
- Each delivery must include documentation and guides needed to enable the internal team to operate autonomously


## Git Workflow

### Branch Strategy

We use a three-tier branching model:

```
main (production) ← stage (staging) ← dev (development) ← feature/fix branches
```

**Branch Descriptions:**

- **`main`**: Production-ready code, deployed to https://{NAME}.epfl.ch
- **`stage`**: Pre-production staging, deployed to https://{NAME}-stage.epfl.ch
- **`dev`**: Active development, auto-deployed to https://{NAME}-dev.epfl.ch
- **`feature/fix branches`**: Individual feature or bug fix branches created from `dev`

### Environments

| Environment | Branch | URL | Deployment |
|-------------|--------|-----|------------|
| **Development** | `dev` | https://{NAME}-dev.epfl.ch | Automatic on merge |
| **Staging** | `stage` | https://{NAME}-stage.epfl.ch | Manual End of sprint: `dev` → `stage` |
| **Production** | `main` | https://{NAME}.epfl.ch | /!\ TBD /!\ : `stage` → `main` |

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
11. **Promote to `main`** → Production release: TBD

### Timeline & SLA

| Activity | Timeframe |
|----------|----------|
| Code Review | 1-2 business days |
| Staging Release | End of sprint |
| Production Release | TBD |

### PR Review Criteria
TBD (should be in pull_REQUEST_TEMPlate.md)
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

---

## Release Process

### Versioning

We follow **Semantic Versioning (SemVer)**:
- `MAJOR.MINOR.PATCH` (e.g., `2.1.3`)
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

### Automated Releases

- **Changelog**: Auto-generated via `release-please` GitHub workflow
- **Release Notes**: Automatically created from conventional commits
- **Tagging**: Automatic on merge to `main`: TBD ()
- **Cycle**: End of sprint promotions through dev → stage → main (see [Git Workflow](#git-workflow))

### Migration Guides

For breaking changes, document in `MIGRATION.md`:
- Version-specific upgrade instructions
- Downgrade procedures
- Database migration scripts
- Configuration changes needed

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
3. **Assigned** - Developer starts work (create branch)
4. **In Progress** - Active development (PR created)
5. **Review** - Code review in progress
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


_Thank you for helping make the CO₂ Calculator project better! Your contributions make a difference in advancing sustainability research at EPFL._
