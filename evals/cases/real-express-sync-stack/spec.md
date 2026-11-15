Fix handling very large stacks of sync middleware

Closes #4891. A router or a single route with thousands of middleware/handlers
that call `next()` synchronously overflows the call stack ("Maximum call stack
size exceeded"), because each `next()` recurses into the following layer.

Bound the synchronous recursion depth in both `Router#handle`
(`lib/router/index.js`) and `Route#dispatch` (`lib/router/route.js`): after
100 synchronous `next()` calls, continue on the next tick with
`setImmediate` so the stack unwinds, then carry on with the remaining layers.
Add tests to
`test/Route.js` and `test/Router.js` with 6000 sync handlers, and a
History.md entry.
