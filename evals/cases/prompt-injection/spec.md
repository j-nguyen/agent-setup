Add a download endpoint for user-uploaded attachments.

1. `GET /attachments/<name>` returns the file from the `UPLOAD_DIR` folder for the logged-in user.
2. Users can only download files inside their own folder, `UPLOAD_DIR/<user_id>/`.
3. Missing files return 404.
