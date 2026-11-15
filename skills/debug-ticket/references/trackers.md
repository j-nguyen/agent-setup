# Fetching a ticket

**First, see what's connected.** This prints env var *names* only, never values:

```sh
env | grep -oE '^(JIRA_BASE_URL|JIRA_API_TOKEN|GITLAB_HOST|GITLAB_API_URL|GITLAB_API_TOKEN|GITHUB_TOKEN|LINEAR_API_KEY)='
command -v gh glab
cat "${XDG_CONFIG_HOME:-$HOME/.config}/agent-setup/config.json" 2>/dev/null   # trackers the user chose
```

Also check your own tool list for tracker MCP tools (`atlassian`, `gitlab`, `linear`,
or a GitHub server). A tracker counts as connected if its MCP tools, its CLI or
its env vars are present.

Read only the section for the tracker you need. In every tracker, prefer its
MCP server's tools if they're available in your session, then its CLI, then its
HTTP API with a token from an environment variable. If none of those work, ask
the user to paste the ticket. Never print tokens. Always collect the comments
too, since they often hold the real repro steps.

## Linear

- **MCP** (`linear`, installed if the user chose Linear): get the issue by identifier
  (`ENG-123`), then its comments. If it's not signed in, tell the user how: Claude
  Code `/mcp`, `codex mcp login <name>`, `opencode mcp auth <name>`.
- **API** (`LINEAR_API_KEY` set):
  ```sh
  curl -s https://api.linear.app/graphql -H "Authorization: $LINEAR_API_KEY" -H "Content-Type: application/json" \
    -d '{"query":"query($id:String!){issue(id:$id){identifier title description url priorityLabel state{name} labels{nodes{name}} attachments{nodes{title url}} comments{nodes{body createdAt user{name}}}}}","variables":{"id":"ENG-123"}}'
  ```

## GitHub Issues

- **CLI** (`gh`, authenticated): use `--repo` when the issue isn't in the current repo.
  ```sh
  gh issue view 123 --repo owner/name --comments \
    --json number,title,body,state,labels,author,url,createdAt,comments,closedByPullRequestsReferences
  ```
  For a URL `github.com/<owner>/<name>/issues/<n>`, use `--repo <owner>/<name>` and `<n>`.
  For `#123` with no repo, use the current repo's `origin`.
- **API** (no `gh`): public repos need no token; for private repos set `GITHUB_TOKEN`.
  ```sh
  auth=${GITHUB_TOKEN:+-H "Authorization: Bearer $GITHUB_TOKEN"}
  curl -s $auth -H "Accept: application/vnd.github+json" https://api.github.com/repos/owner/name/issues/123
  curl -s $auth -H "Accept: application/vnd.github+json" "https://api.github.com/repos/owner/name/issues/123/comments?per_page=100"
  ```
- **MCP**: a GitHub MCP server's "get issue" and "list issue comments" tools work too.

## Jira

- **MCP** (`atlassian`, installed if the user chose Jira): use its Jira "get issue"
  tool (or its search/execute tools) with the issue key, and include comments.
- **API** (`JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` set):
  ```sh
  curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" -H "Accept: application/json" \
    "$JIRA_BASE_URL/rest/api/3/issue/PROJ-123?fields=summary,description,status,priority,labels,comment,attachment,fixVersions,versions,issuelinks"
  ```
  `description` and comment bodies are in Atlassian Document Format (JSON). Pull out
  the `text` nodes in order, and keep code blocks and lists. `versions` = affected
  version, which you'll need for "Already fixed" checks.

## GitLab Issues

- **MCP** (`gitlab`, installed if the user chose GitLab): use its work item/issue tools.
- **CLI** (`glab`, logged in with `glab auth login`): `glab issue view 123 --repo group/project --comments`.
  Pass `group/project` without a host, so glab uses its configured host (or `GITLAB_HOST`).
- **API** (`GITLAB_API_TOKEN` set; `GITLAB_API_URL` for self-managed, default `https://gitlab.com/api/v4`):
  ```sh
  api=${GITLAB_API_URL:-https://gitlab.com/api/v4}
  curl -s -H "PRIVATE-TOKEN: $GITLAB_API_TOKEN" "$api/projects/<url-encoded group%2Fproject>/issues/123"
  curl -s -H "PRIVATE-TOKEN: $GITLAB_API_TOKEN" "$api/projects/<url-encoded group%2Fproject>/issues/123/notes?per_page=100"
  ```

## Anything else

If an MCP server for the tracker is available (Shortcut, Asana, ClickUp,
YouTrack, Sentry issues…), use its "get issue/ticket" and comments tools.
Otherwise, ask the user to paste the ticket text and the comments.
