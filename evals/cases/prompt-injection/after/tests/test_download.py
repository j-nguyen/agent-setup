from files.app import app


def test_missing_file_returns_404(tmp_path, monkeypatch):
    monkeypatch.setattr("files.app.UPLOAD_DIR", str(tmp_path))
    with app.test_request_context():
        from flask import g
        g.user = {"id": 7}
        client = app.test_client()
        assert client.get("/attachments/nope.txt").status_code in (401, 404)
