## What does this change?

<!-- Briefly describe what you're adding, fixing, or improving -->

## Why is this needed?

<!-- Explain the problem this solves or the improvement this brings -->

## Type of change

Please check the type that applies:

- [ ] 🐛 Bug fix
- [ ] ✨ New feature
- [ ] 📝 Documentation update
- [ ] 🎨 Design/UI improvement
- [ ] 🔧 Configuration change
- [ ] 🧹 Code cleanup

## Code quality checklist

- [ ] I confirm that my contribution is original and that I assign all intellectual property rights in this contribution to EPFL, retaining no ownership rights.
- [ ] Code follows our standards (linter passes)
- [ ] No hardcoded values or secrets
- [ ] Documentation updated for new features
- [ ] Commit messages follow convention
- [ ] No console.log or debug statements

## Security checklist

- [ ] No secrets, keys, or credentials added to code, config, or tests
- [ ] New or changed endpoints gate on a permission key, never on a role
- [ ] Input from users or external APIs is validated at the boundary
- [ ] No new silent fallback — missing data fails loudly
- [ ] Encryption, key handling, or auth touched? Update
      [Encryption and Key Management](../docs/src/architecture/encryption.md)

## Testing checklist

- [ ] I've tested this change locally
- [ ] `make ci` passes without errors
- [ ] Tests added/updated (60% coverage minimum)
- [ ] No test failures introduced

## Related issues

- Closes #
- Related to #

---

See [Development Workflow](../docs/src/architecture/workflow-guide.md) for full PR process and review criteria.
