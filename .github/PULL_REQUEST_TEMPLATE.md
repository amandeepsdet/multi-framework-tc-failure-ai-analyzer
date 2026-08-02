# Pull Request

## Summary
Briefly describe what this PR changes and why.

## Type of change
- [ ] Bug fix
- [ ] New feature / adapter
- [ ] Documentation
- [ ] Refactor / internal
- [ ] CI / build

## Checklist
- [ ] Tests added/updated and passing (`pytest tests/aiqa tests/ai -m "sdk or ai" -o addopts=""`)
- [ ] `ruff` and `black` pass
- [ ] Core stays framework-agnostic (no framework imports in `aiqa/core`, `aiqa/analysis`, `aiqa/reporting`)
- [ ] New framework support added as an **adapter** under `aiqa/adapters`
- [ ] Docs/CHANGELOG updated if user-facing
- [ ] Public `import aiqa` API unchanged (or the change is intentional and documented)

## Related issues
Closes #
