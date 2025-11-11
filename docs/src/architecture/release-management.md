# Release Management Guide

Versioning strategy, environment promotion, and deployment processes
for the CO₂ Calculator project. This guide covers operational
procedures for releases, hotfixes, and rollbacks.

**Related documentation:**

- [CI/CD Pipeline](06-cicd-pipeline.md) - Pipeline architecture
- [CI/CD Workflows](cicd-workflows.md) - GitHub Actions details
- [Workflow Guide](workflow-guide.md) - Developer daily workflow

## Versioning Strategy

We follow Semantic Versioning (SemVer) with two release phases:

### Internal Pre-Production (v0.x.x)

Active during development sprints 1-9:

- Format: `v0.MINOR.PATCH` (e.g., `v0.3.1`)
- Released at end of each sprint
- Deployed to pre-production environment
- Internal testing and validation only
- Not public-facing

Version increments:

- `MINOR`: Sprint completion with new features
- `PATCH`: Hotfixes between sprints

### Public Production (v1.0.0+)

Activated after sprint 10:

- Format: `v1.0.0` for first public release
- Full semantic versioning thereafter
- Production-ready with complete docs
- Public-facing release

Version increments:

- `MAJOR`: Breaking changes
- `MINOR`: New features (backward compatible)
- `PATCH`: Bug fixes

## Environment Promotion

Code flows through environments with validation at each stage:

```
feature/* → dev → stage → main (pre-prod/prod)
```

### Environment Overview

| Branch  | Environment   | Purpose                       |
| ------- | ------------- | ----------------------------- |
| `dev`   | Development   | Daily development and testing |
| `stage` | Staging       | Pre-production validation     |
| `main`  | Pre-prod/Prod | Internal/public releases      |

For deployment triggers and technical flow, see
[CI/CD Pipeline](06-cicd-pipeline.md#deployment-flow).

### Development Environment

**Branch:** `dev`  
**URL:** https://co2-calculator-dev.epfl.ch  
**Purpose:** Daily development and testing

**Deployment:** Automatic on merge to `dev`

**Validation:**

- Automated tests must pass
- Developer smoke testing
- PM testing 2-3 days before sprint end

### Staging Environment

**Branch:** `stage`  
**URL:** https://co2-calculator-stage.epfl.ch  
**Purpose:** Pre-production validation

**Deployment:** Manual PR from `dev` to `stage` at sprint end

**Validation:**

- Full regression testing
- PM final validation
- Performance testing
- Security scan review

### Pre-Production/Production

**Branch:** `main`  
**URL:** https://co2-calculator.epfl.ch  
**Purpose:** Internal releases (v0.x.x), then public (v1.0.0+)

**Deployment:** Manual PR from `stage` to `main` with version tag

**Validation:**

- All staging tests passed
- Migration scripts tested
- Rollback plan documented
- Release notes prepared

## Release Process

### Sprint-End Release (v0.x.x)

Follow this checklist for each sprint release:

1. **Pre-Release Testing** (2-3 days before sprint end)
   - PM validates features in dev environment
   - Team fixes critical bugs
   - Documentation updated

2. **Promote to Staging**

   ```bash
   git checkout stage
   git pull origin stage
   git merge dev
   git push origin stage
   ```

   - Create PR for visibility
   - PM performs final validation
   - Run full test suite

3. **Create Release**

   ```bash
   git checkout main
   git pull origin main
   git merge stage
   git tag -a v0.X.0 -m "Sprint X release"
   git push origin main --tags
   ```

   - Version increments MINOR (v0.X.0)
   - Automated changelog generation
   - Deploy to pre-production

4. **Post-Release**
   - Monitor logs for errors
   - Verify deployment health
   - Update sprint board
   - Document known issues

### Public Release (v1.0.0)

First public release after sprint 10:

1. **Final Validation**
   - Complete all documentation
   - Security audit passed
   - Performance benchmarks met
   - Accessibility review complete

2. **Production Activation**
   - Switch environment from pre-prod to prod
   - Update DNS if needed
   - Monitor closely for 24h

3. **Release Announcement**
   - Publish release notes
   - Update project README
   - Notify stakeholders
   - Marketing announcement

### Automated Release Tools

We use `release-please` GitHub Action for automation:

- Reads conventional commits
- Generates CHANGELOG.md
- Creates release PR
- Publishes GitHub release

Configuration in `.github/workflows/release-please.yml`. For workflow
details, see [CI/CD Workflows](cicd-workflows.md#10-release-please).

### Release Notes

Automatically generated from commit messages:

- `feat:` commits → "Features" section
- `fix:` commits → "Bug Fixes" section
- `BREAKING CHANGE:` → "Breaking Changes" section

Manual edits allowed after generation.

## Emergency Hotfix Process

For critical production bugs requiring immediate fix:

### Hotfix Workflow

1. **Create hotfix branch from main**

   ```bash
   git checkout main
   git pull origin main
   git checkout -b hotfix/critical-bug-fix
   ```

2. **Implement minimal fix**
   - Keep changes focused
   - Add regression test
   - Update documentation

3. **Fast-track review** (2-4 hour SLA)
   - Label PR as `priority: critical`
   - Tag Lead Developer + Project Manager
   - Skip staging (emergency only)

4. **Deploy to production**

   ```bash
   git checkout main
   git merge hotfix/critical-bug-fix
   git tag -a v0.X.Y -m "Hotfix: description"
   git push origin main --tags
   ```

5. **Backport to other branches**

   ```bash
   git checkout dev
   git cherry-pick <hotfix-commit-sha>
   git push origin dev

   git checkout stage
   git cherry-pick <hotfix-commit-sha>
   git push origin stage
   ```

6. **Post-incident review**
   - Document root cause
   - Update runbooks
   - Improve monitoring
   - Schedule permanent fix if needed

### Hotfix Approvers

Minimum approval required:

- Lead Developer **OR** Project Manager
- Emergency: Single approver sufficient
- Post-deployment notification to full team

## Migration Management

### Database Migrations

We use Alembic for schema changes:

**Creating migration:**

```bash
cd backend
make migration-new MESSAGE="add user preferences table"
```

**Testing migration:**

```bash
# Test upgrade
make db-migrate

# Test downgrade
make migration-down
```

**Production deployment:**

- Migrations run automatically during deployment
- Downgrade script must be tested
- Document breaking changes in MIGRATION.md

### Breaking Changes

For changes that break backward compatibility:

1. **Document in MIGRATION.md**
   - Version affected
   - What changed
   - Upgrade instructions
   - Downgrade procedure

2. **Provide migration scripts**
   - Database schema updates
   - Data transformation scripts
   - Configuration changes

3. **Communication**
   - Announce in release notes
   - Email stakeholders
   - Update API documentation
   - Add deprecation warnings early

### Rollback Procedures

If deployment issues occur:

**Application rollback:**

```bash
# ArgoCD rollback to previous version
argocd app rollback co2-calculator

# Or revert git tag
git push origin :refs/tags/v0.X.Y
git tag -d v0.X.Y
```

**Database rollback:**

```bash
cd backend
make migration-down  # Rollback one migration
```

Always test rollback procedures in staging first. For detailed
rollback mechanisms, see
[CI/CD Pipeline](06-cicd-pipeline.md#rollback-mechanisms).

## Monitoring Post-Deployment

After each release, monitor:

- **Error rates** - Check logs for exceptions
- **Performance** - Response times within SLA
- **Database** - Query performance and connections
- **User reports** - GitHub issues and support emails

Set up alerts for:

- HTTP 5xx error rate > 1%
- Response time > 2 seconds
- Database connection pool exhaustion
- Failed deployments

## Release Calendar

### Sprint-Based Releases (v0.x.x)

- Sprint length: 2 weeks
- Release frequency: Every sprint (bi-weekly)
- Code freeze: 2 days before sprint end
- Release day: Last day of sprint

### Production Releases (v1.0.0+)

- Major releases: As needed (planned sprints)
- Minor releases: Monthly or quarterly
- Patch releases: As needed (hotfixes)
- Security patches: Immediate

## Version History

Document major releases:

| Version | Date | Highlights          |
| ------- | ---- | ------------------- |
| v0.1.0  | TBD  | Initial dev release |
| v0.2.0  | TBD  | Sprint 2 features   |
| v1.0.0  | TBD  | Public launch       |

Full changelog maintained in CHANGELOG.md.
