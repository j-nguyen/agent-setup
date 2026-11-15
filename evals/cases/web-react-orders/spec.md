Orders table on the ops dashboard (React 18).

1. Load the open orders once when the dashboard opens. Usually 5k–20k rows.
2. Show them in a table that can be sorted by newest or largest and filtered by customer. Typing in the filter and scrolling must stay smooth with 20k rows (`@tanstack/react-virtual` is already a dependency).
3. Clicking a row expands its details. The expanded row must stay expanded when the table is re-sorted or filtered.
4. A header clock ticks every second. The ticking must not slow down the table.
5. A "Compact rows" setting, shared through context.
