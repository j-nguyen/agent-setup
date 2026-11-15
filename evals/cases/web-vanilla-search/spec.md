Search-as-you-type product search on the shop home page (vanilla JS, no framework).

1. Results update as the user types. The API is expensive, so don't call it on every keystroke, and the results shown must always match what's currently in the box.
2. Up to 500 results. Typing and scrolling must stay smooth on mid-range phones (no long tasks or jank).
3. Load product images lazily as they scroll into view, without layout shift (the API returns `imageWidth`/`imageHeight`).
4. Product names come from marketplace sellers.
5. Cards in the grid all have the same height.
