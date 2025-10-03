# Contributing Guide – CO₂ Calculator @ EPFL

Thanks for your interest in contributing to the CO₂ Calculator project! 🎉

This guide ensures quality, security, maintainability, and longevity of our codebase, following EPFL project specifications.

---

## Quick Start

**New contributors:**
1. Fork the repository
2. Create an issue describing your fix/feature
3. Follow our [Git Workflow](#git-workflow) process

**TL;DR:** `Issue → Branch from dev → Code → Test → PR to dev → Review (1-2 days) → Merge → Auto-deploy`

## Need Help?

- 💬 Join our [discussions](https://github.com/EPFL-ENAC/epfl-calculator-co2/discussions)
- 📋 Use [issue templates](https://github.com/EPFL-ENAC/epfl-calculator-co2/issues/new/choose) to report bugs or request features
- 📖 Read our [Code of Conduct](https://github.com/EPFL-ENAC/epfl-calculator-co2/blob/main/CODE_OF_CONDUCT.md)

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

## Project Management & Governance

### EPFL Requirements

- Development planned and documented per phase: design → implementation → validation → deployment
- **All work must be approved** by EPFL project manager before implementation
- Evolution and changes require EPFL validation
- Track all tasks using the project ticketing tool

### Intellectual Property
*WARNING* : is this what we want ?
- All code becomes **property of EPFL** (internal license)
- By contributing, you agree to this transfer of ownership

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

## Code Standards

### Documentation

- Code must be documented with clear, concise comments that explain business logic and technical choices
- Each module should include technical documentation (README, installation guide, API docs)
- Use English for all documentation and comments

### General Principles

** not sure about SOLID: explain what we take from SOLID **
- Follow **SOLID principles** and general programming best practices
- Use consistent naming conventions (camelCase or snake_case according to the language)
    - Don't mix or translate naming convention accross env (if backend is python and snake_case is database + api choice, then frontend will use snake_case always (no exception))
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
| **Staging** | `stage` | https://{NAME}-stage.epfl.ch | Manual: `dev` → `stage` |
| **Production** | `main` | https://{NAME}.epfl.ch | Bi-weekly: `stage` → `main` |

### Team Roles

- **Lead Developer**: Implementation and technical decisions
- **Code Reviewer**: Quality assurance and code review
- **Project Manager**: Coordination, approvals, and release management

### Development Process

**Full Workflow:**

```
Issue → Branch → PR → Code Review → Merge to Dev → Staging → Production
```

**Step-by-step:**

1. **Create an issue** describing the feature or fix
2. **Create a branch** from `dev`: `git checkout -b issue-123-feature-name`
3. **Develop** your changes with proper documentation
4. **Test locally** - run full test suite (`make test`)
5. **Push** and create **pull request** to `dev`
6. **Code review** (1-2 business days) - address all feedback
7. **Merge to `dev`** → Auto-deploys to development environment
8. **Validate** in dev environment
9. **Promote to `stage`** → Manual deployment (bi-weekly cycle)
10. **Staging validation** → Final testing before production
11. **Promote to `main`** → Production release (bi-weekly)

### Timeline & SLA

| Activity | Timeframe |
|----------|----------|
| Code Review | 1-2 business days |
| Staging Release | Bi-weekly cycle |
| Production Release | Bi-weekly cycle |

### PR Review Criteria

- [ ] Code documentation
- [ ] Adherence to standards and best practices
- [ ] Security considerations
- [ ] Performance impact
- [ ] Test coverage
- [ ] Responsiveness (for UI changes)

### For UI Changes

- Add screenshots/GIFs/videos demonstrating the changes
- Verify accessibility (keyboard navigation, screen readers)
- Test on different screen sizes
- Link related issues

---

## Technical Standards

### Containerization & APIs

- **Container**: Must remain containerized (Docker/OCI) and deployable via public registry
- **APIs**: REST/JSON compliant with OpenAPI specifications
- **CI/CD**: Automated pipeline handles testing and deployment

### Maintenance

- Keep dependencies up-to-date
- Address security vulnerabilities promptly
- Monitor and fix issues reported in ticketing tool

---

## Knowledge Transfer

- Each delivery must include documentation and guides needed to enable the internal team to operate autonomously
- Training sessions should be organized to ensure the EPFL teams can take over the system
- Maintain up-to-date technical documentation
- Document architectural decisions and rationale

---

_Thank you for helping make the CO₂ Calculator project better! Your contributions make a difference in advancing sustainability research at EPFL._
