# TypeScript

**Types**
- No `any`. Use `unknown` at untrusted boundaries (JSON, `catch`, third-party
  callbacks) and narrow it with a type guard or the repo's schema validator.
- No non-null `!` or `as` casts to silence the compiler. Narrow instead. A
  cast is fine only right after a check the compiler can't see, with a comment.
- Model states as discriminated unions (`{ status: "ok"; data } | { status:
  "error"; error }`), not several optional fields that can't all be set together.
- Exhaustive `switch` over a union: end with a `never` check so a new variant
  fails to compile.
- Let inference work for locals; annotate exported functions' parameters and
  return types. Prefer `satisfies` over `as` for checking object literals.
- `readonly` / `ReadonlyArray` for inputs you don't mutate. Don't mutate arguments.
- Literal unions or `as const` objects over `enum`, unless the repo uses enums.
- Reuse existing types (`Pick`, `Omit`, the generated API/DB types) instead of
  redeclaring a shape that can drift.

**Errors and async**
- Validate external input once, at the edge (request body, env, file, API
  response), then pass typed values inward.
- Throw `Error` subclasses (or the repo's error type), never strings. Keep the
  cause: `new AppError("…", { cause: err })`.
- Every promise is awaited, returned, or deliberately voided (`void p` with a
  reason). No floating promises.
- Independent awaits run together with `Promise.all` (or `allSettled` when one
  failure must not cancel the rest). Don't `await` inside a loop when the
  iterations don't depend on each other.
- Pass `AbortSignal` / timeouts through to `fetch` and long operations when the
  caller has one.

**Code shape**
- Early returns over nested `if`s. Small functions with one job.
- `const` by default; `let` only when reassigned. Never `var`.
- `===` / `!==`. `??` for defaults (not `||`, which swallows `0` and `""`).
  `?.` only where `undefined` is a real, expected value.
- Use `Map`/`Set` for lookups by key inside loops, not `array.find`/`includes`
  (O(n²) otherwise).
- Import from the module that defines the thing, not a barrel `index.ts`, when
  the repo's bundler or tests are slowed by barrels.
- Named exports, unless the framework requires a default (Next.js pages, etc.).
- No commented-out code, no `console.log` left behind (use the repo's logger).

**Tests**
- Test behavior through the public function or route, not private helpers.
- Cover the failure path and one edge case (empty, boundary, invalid input)
  for each new branch. Type-check tests too (`tsc --noEmit` if the repo has it).
