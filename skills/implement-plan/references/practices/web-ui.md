# Web UI (HTML, CSS, accessibility)

Adapted from Vercel's Web Interface Guidelines (MIT, see `NOTICE.md`). Apply
to the UI you build. Follow the repo's design system and copy style where it has them.

**Semantics and accessibility**
- `<button>` for actions, `<a href>` / `<Link>` for navigation. Never a
  clickable `<div>` or `<span>`.
- Semantic HTML before ARIA. Headings in order (`h1`→`h6`), landmarks
  (`main`, `nav`), `<table>` for tabular data.
- Every form control has a `<label>` (or `aria-label`). Icon-only buttons have
  `aria-label`. Decorative icons have `aria-hidden="true"`.
- Images have `alt` (`alt=""` if decorative).
- Async messages (toasts, validation results) are announced with `aria-live="polite"`.
- Custom interactive widgets work with the keyboard (Enter/Space, Escape,
  arrows where expected). Drag and gesture actions have a click/keyboard alternative.

**Focus**
- Every interactive element has a visible focus style. Use `:focus-visible`.
- Never `outline: none` without a replacement focus style.
- Sticky headers and overlays must not hide the focused element. Modals trap
  focus and return it on close.

**Forms**
- Correct `type` and `inputmode` (`email`, `tel`, `url`, `number`), a
  meaningful `name`, and `autocomplete` values.
- Never block paste. Labels are clickable (`for`/`htmlFor` or wrapping).
- Errors appear inline next to the field and say how to fix it. On submit,
  focus the first invalid field.
- The submit button stays enabled until the request starts, then shows progress.
- Warn before leaving a form with unsaved changes.

**Content and layout**
- Handle empty, short and very long content: empty states, `text-overflow` /
  line clamping / `overflow-wrap`, `min-width: 0` on flex children that truncate.
- `<img>` has explicit `width` and `height` (no layout shift). Below-the-fold
  images `loading="lazy"`; the main above-the-fold image gets priority.
- Lay out with flex/grid, not JavaScript measurement. No layout reads
  (`getBoundingClientRect`, `offsetHeight`) during render.
- Full-bleed layouts respect `env(safe-area-inset-*)`. Don't disable zoom
  (`user-scalable=no`, `maximum-scale=1`).

**Motion**
- Honor `prefers-reduced-motion`. Animate `transform` and `opacity` only.
- Never `transition: all`; list the properties.

**State and navigation**
- Filters, tabs, pagination and other shareable view state live in the URL.
- Destructive actions need a confirmation or an undo window.

**Locale and copy**
- Format dates, times, numbers and currency with `Intl.*`, not hand-built strings.
- `…` for loading text and truncation ("Saving…"). Tabular numbers
  (`font-variant-numeric: tabular-nums`) in columns.
- Specific button labels ("Save API key", not "Continue"). Error messages say
  what to do next.

**Theming**
- Dark themes set `color-scheme: dark`. Colors come from the repo's tokens or
  CSS variables, not new hard-coded values. Hover, active and focus states are
  visibly distinct from rest.
