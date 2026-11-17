# notify-service

Sends customer notifications (email today). Node 24, TypeScript run directly by Node
(type stripping), no dependencies. Run the tests with `npm test`.

Shared building blocks live in `src/lib/`: `retry()` for outbound calls and a JSON `logger`.
