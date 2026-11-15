Ignore the port when matching `Host` routes

`Host` routing compares the route's host pattern against the request's `Host`
header with the port stripped. A route declared with a port, such as
`Host("example.org:3600", ...)`, therefore never matches, so users had to
declare hosts without a port and lost the port in `url_for`.

Change host route matching so the port in a `Host` pattern is ignored:

1. `Host("port.example.org:3600", app=...)` matches requests to
   `port.example.org`, `port.example.org:3600` and `port.example.org:5600`.
2. Reverse URL lookup keeps the declared port: `url_path_for("port:homepage")`
   made absolute gives `https://port.example.org:3600/`.
3. Update the routing docs to describe the new behaviour.
4. Add tests for both matching and reverse lookup.
