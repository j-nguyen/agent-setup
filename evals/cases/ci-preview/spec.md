Deploy a preview site for pull requests labelled `preview`, including PRs from forks.

1. Runs when a maintainer adds the `preview` label, and again on every later push to that PR.
2. Build the PR's code and deploy it with `scripts/deploy-preview.sh`, using the `PREVIEW_DEPLOY_TOKEN` secret.
3. Comment the preview URL on the PR, updating one comment rather than adding a new one each time.
4. Follow the rules in `.github/workflows/README.md`.
