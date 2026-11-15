Add URL slugs for blog posts.

1. `slugify(title)` lowercases, transliterates accents to ASCII (é -> e), replaces runs of non-alphanumerics with a single `-`, and strips leading/trailing `-`.
2. Slugs are at most 60 characters and never end with `-` after truncation.
3. An empty or all-symbol title yields `"post"`.
4. `build_info()` (used on the /about page) now also reports the short git commit the site was built from, or `"unknown"` if git is unavailable.
