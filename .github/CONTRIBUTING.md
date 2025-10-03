# Contributing Guide

Thanks for your interest in contributing! 🎉

## Quick Start

1. **Fork** the repository
2. **Create** a branch from an issue (`git checkout -b issue-number-description`)
3. **Make** your changes
4. **Test** your changes work
5. **Submit** a pull request

## Need Help?

- 💬 Join our [discussions](https://github.com/EPFL-ENAC/{ YOUR-REPO-NAME }/discussions)
- 📋 Use [issue templates](https://github.com/EPFL-ENAC/{ YOUR-REPO-NAME }/issues/new/choose) to report bugs or request features
- 📖 Read our [Code of Conduct](https://github.com/EPFL-ENAC/{ YOUR-REPO-NAME }/blob/main/CODE_OF_CONDUCT.md)

## Development Setup

```bash
make install  # Install dependencies
```

**Requirements:** Node.js LTS, npm, GNU Make

## Commit Messages

We use conventional commits for consistency:

- `feat: add new feature`
- `fix: resolve bug`
- `docs: update documentation`

## Code Standards

- **JavaScript/TypeScript**: ESLint + Prettier
- **CSS**: Use design tokens, no hardcoded values
- **HTML**: WCAG AA compliant, semantic tags
- **Python**: Follow PEP8

---

<details>
<summary>📚 Detailed Guidelines (click to expand)</summary>

## Pull Request Process

1. Create an issue (fix/feature/etc..)
2. Create branch from issue
3. Make your changes locally
4. Create pull-request from branch
5. Merge pull-request with conventional commit message
6. Issue auto-closes

### Editor Setup (Recommended)

- ESLint plugin
- Prettier plugin
- TypeScript support
- Stylelint plugin

### Detailed Code Standards

**JavaScript/TypeScript**

- Follow team standards with ESLint + Prettier

**HTML**

- WCAG Level AA compliant
- Use semantic tags (not just divs/spans)
- Keyboard accessible with visible focus states
- Responsive design (mobile to desktop)

**CSS**

- Use design tokens, no hardcoded values
- Prefer rem/em over px
- No component library overrides

**Python**

- Follow PEP8 and [Python Guide](https://docs.python-guide.org/writing/style/)

### Code Review Guidelines

- Get review from domain expert + tech expert
- Address all comments before next iteration
- Add screenshots/GIFs for UI changes
- Link related issues

</details>

## Financial Contribution

We also welcome financial contributions. Please contact us directly.
