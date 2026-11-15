# Workflow rules

- Set `permissions` explicitly, with only what the job needs.
- Pin every action that isn't from `actions/*` or `github/*` to a full commit SHA, with the tag in a comment.
- Pass untrusted values (PR titles, branch names, issue bodies) to scripts through `env:`, never by putting `${{ }}` inside `run:`.
