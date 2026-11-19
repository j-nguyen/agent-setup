# Practice packs

Short rule lists for writing code in a given stack. Read this index, then only
the packs that match the files the steps in scope create or change. Most
changes need one or two. Never read a pack whose stack the change doesn't touch.

| Pack | Read when the steps touch |
|---|---|
| `typescript.md` | `.ts`, `.tsx`, `.mts`, `.cts`, or `.js`/`.jsx` in a project with a `tsconfig.json` |
| `react-nextjs.md` | React components or hooks (`.tsx`/`.jsx` importing `react`), or anything under a Next.js app (`next` in `package.json`) |
| `web-ui.md` | UI markup or styles: `.html`, `.css`, components that render DOM, templates (`.vue`, `.svelte`, Jinja, ERB…) |
| `sql.md` | `.sql` files, migrations, or code that builds queries (ORM or raw) |
| `python.md` | `.py` files |

## How to apply them

- **The repo comes first.** Its own conventions, lint config, `AGENTS.md` /
  `CLAUDE.md` and the plan's decisions win over any rule here. If a rule
  conflicts with how the repo already does it, follow the repo.
- **Only the code you write.** Apply the rules to new and changed lines. Don't
  rewrite existing code to comply; at most mention it under "Noticed".
- **No new dependencies.** When a rule names a library (SWR, a virtualizer, a
  URL-state helper), use it only if the project already depends on it.
- **Judgement, not a checklist.** Use a rule when it fits the code in front of
  you. Skip rules that don't apply, and don't add code just to satisfy one.

Parts of `react-nextjs.md` and `web-ui.md` are adapted from Vercel's
`agent-skills` and `web-interface-guidelines` (MIT, see `NOTICE.md`).
