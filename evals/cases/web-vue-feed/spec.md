Activity feed in the audit console (Vue 3.5).

1. Load the last 24 hours of events when the feed opens: 20k–50k events, which are never edited client-side.
2. Show them newest first, filterable by actor or resource, with a "Hide logins" toggle. Typing and scrolling must stay smooth at 50k events (`vue-virtual-scroller` is already a dependency).
3. Show the count of matching events and the number of deletes.
4. Clicking a row selects it.
5. The feed is shown and hidden many times as users switch tabs in the console, so it must not leak memory or listeners.
