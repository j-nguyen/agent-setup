Make getFilePath support Windows-style paths

`getFilePath` (`src/utils/filepath.ts`, mirrored in `deno_dist/`) turns a
request path into the file path the serve-static adapters (Bun, Deno,
Cloudflare Workers) read. It only understands `/` as a separator, so paths
using Windows-style `\` separators are not handled.

1. Treat `\` like `/` when rejecting directory traversal: a `..` segment
   delimited by either separator (e.g. `\..\foo`, `.\..\foo`) returns
   `undefined`.
2. Strip a leading `\` or `.\` the same way a leading `/` or `./` is stripped.
3. Convert `\` separators to `/` so the returned path always uses `/`
   (e.g. `foo\bar.txt` becomes `foo/bar.txt`).
4. Keep existing behaviour for `/` paths, and add tests that run the existing
   cases with `\` separators.
