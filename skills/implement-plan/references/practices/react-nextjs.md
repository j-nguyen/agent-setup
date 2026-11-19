# React and Next.js

Adapted from Vercel's `react-best-practices` and `composition-patterns` (MIT,
see `NOTICE.md`), ordered by impact. Check the React and Next.js versions in
`package.json` first: some rules apply only to the App Router or React 19.

**1. No waterfalls (critical)**
- Start independent requests together: `Promise.all`, not sequential `await`s.
- In route handlers and server components, start promises early and await them
  where the value is needed. Move an `await` into the branch that uses it.
- Check cheap synchronous conditions before awaiting a remote value.
- Restructure server components so sibling fetches run in parallel instead of
  parent-then-child. Wrap slow parts in `<Suspense>` to stream the rest.

**2. Bundle size (critical)**
- Import from the specific module, not a barrel file (`lodash/debounce`, an icon's
  own path), unless the project already sets `optimizePackageImports`.
- Load heavy, rarely used components with `next/dynamic` / `React.lazy`.
- Load analytics, logging and chat widgets after hydration.
- Keep import paths statically analyzable (no `require(variable)`).

**3. Server side (high)**
- Authenticate and authorize every server action like an API route. It is a
  public endpoint.
- Pass client components only the fields they render. Everything passed is
  serialized into the page.
- No module-level mutable state that holds per-request data in RSC/SSR code.
- `React.cache()` to dedupe the same fetch within one request.
- Non-blocking work after the response (logging, analytics) goes in `after()`
  when the Next.js version has it.

**4. Client data and effects (medium-high)**
- Use the repo's data-fetching library (SWR, React Query) for client fetches;
  don't hand-roll `useEffect` + `fetch` when one exists.
- Derive values during render. Don't copy props or state into other state with
  `useEffect`.
- Put interaction logic in event handlers, not in effects that watch state.
- Effect dependencies are primitives or stable references. Clean up every
  subscription, listener and timer. Scroll and touch listeners are `{ passive: true }`.

**5. Re-renders (medium)**
- Never define a component inside another component.
- Functional `setState(prev => …)` when the next state depends on the previous.
- Lazy init for expensive initial state: `useState(() => compute())`.
- Hoist constant default props (`[]`, `{}`) and static JSX out of the component.
- `useMemo`/`memo` only for genuinely expensive work, not simple expressions.
- `useTransition` / `useDeferredValue` for non-urgent updates that make input lag.
- `useRef` for values that change often but don't affect what's rendered.

**6. Rendering (medium)**
- Conditional rendering with a ternary or a boolean, not `count && <X/>`
  (renders `0`).
- Stable, unique `key`s from the data, never the array index for lists that reorder.
- Long lists: virtualize (if the project has a virtualizer) or use
  `content-visibility: auto`.
- Avoid hydration mismatches: no `Date.now()`, `Math.random()` or `window`
  reads during server render. `suppressHydrationWarning` only where unavoidable.

**7. Component design**
- Don't keep adding boolean props to change behavior (`isCompact`, `withIcon`,
  `hideFooter`). Make explicit variant components, or compound components that
  share state through context.
- Prefer `children` to `renderX` props for composition.
- One provider owns how a piece of state is managed. Consumers use its
  interface (state, actions), not its internals.
- React 19: pass `ref` as a prop instead of `forwardRef`; `use()` can read context.

**Tests**: test what the user sees (Testing Library queries by role and label),
not implementation details or internal state.
