# Contributing

Contributions are welcome — no approval needed to get started.

## Picking up work

- **Existing issues**: If an issue has no assignee and you want to work on it
  just comment `.take` and the bot will assign it to you. [^1]
- **New features**: Create an issue describing what you want to add, then start
  implementing. No need to wait for a response before opening a draft PR.

[^1]: GitHub does not allow non-maintainers to assign issues, so the bot has to
      do it for you. See `.github/workflows/self_assign.yml` for details.

## Guidelines

- Keep PRs focused — one feature or fix per PR
- Update tests and docs where relevant
- Follow the existing code style
- Use `pre-commit` since they are anyway enforced on CI
