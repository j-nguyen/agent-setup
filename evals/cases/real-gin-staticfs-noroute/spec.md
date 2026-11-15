Route StaticFS() not found to the router's NoRoute() handlers

Closes #1220. When a file requested under a `Static`/`StaticFS` route doesn't
exist (or can't be opened), gin currently lets `http.FileServer` write its own
plain "404 page not found" response, ignoring any handlers the user set with
`router.NoRoute(...)`.

Change the static handler created by `createStaticHandler` so that:

1. It checks whether the requested file can be opened from the `http.FileSystem`.
2. If it can't, it sets status 404 and hands the request to the router's
   NoRoute handlers, exactly as a request to an unregistered path would be
   handled, instead of serving the FileServer 404 page.
3. Existing files are still served by `http.FileServer` as before.

Add a test that a NoRoute handler's body is returned for missing files under
`StaticFS`, for both GET and HEAD.
