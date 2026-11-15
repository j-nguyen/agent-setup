# Attribution

Parts of these review guidelines are adapted from Anthropic's open-source review prompts:

- `00-baseline.md` is adapted from the `code-review` plugin command in
  https://github.com/anthropics/claude-plugins-official (`plugins/code-review/commands/code-review.md`),
  licensed under the Apache License 2.0.
- `02-security.md` is adapted from https://github.com/anthropics/claude-code-security-review
  (`.claude/commands/security-review.md`), Copyright (c) 2025 Anthropic, licensed under the MIT License.

Changes: rewritten as tool-agnostic single-agent passes (no tool- or model-specific steps,
no GitHub comment posting), merged validation into a shared evidence bar, and extended with
supply-chain checks. `01-spec.md`, `03-architecture.md`, `04-performance.md` and
`report-format.md` are original to this repo.
