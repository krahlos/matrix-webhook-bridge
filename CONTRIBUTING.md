# Contributing

Contributions are welcome — no approval needed to get started.

## Picking up work

- **Existing issues**: If an issue has no assignee and you want to work on it
  just comment `.take` and the bot will assign it to you. [^1]
- **New features**: Create an issue describing what you want to add, then start
  implementing. No need to wait for a response before opening a draft PR.

[^1]: GitHub does not allow non-maintainers to assign issues, so the bot has to
      do it for you. See `.github/workflows/self_assign.yml` for details.

## Testing your PR's Docker image

If you'd like to test the built image without building it locally, ask a
maintainer to add the `pr/publish-image` label to your PR. This publishes
`ghcr.io/krahlos/matrix-webhook-bridge:pr-<number>` and comments the pull
command on the PR once it's up. The image is rebuilt on every push while the
label is set, and removed from the registry once the PR is closed.

This isn't automatic: building a PR's code with the maintainer's registry
credentials needs a maintainer to apply the label and then approve the
publish run, so expect it only on request rather than by default.

## Guidelines

- Keep PRs focused — one feature or fix per PR
- Update tests and docs where relevant
- Follow the existing code style
- Use [`prek`][prek], since the hooks are anyway enforced on CI

[prek]: https://github.com/j178/prek
