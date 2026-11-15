"""Local fake Jira / GitLab REST APIs for evals (standard library only).

Serves one ticket (from a debug case's ticket.md) in each tracker's real response
format, and records every request, so an eval can check that an agent actually
fetched the ticket from the tracker instead of guessing.

    srv = MockTracker(ticket_md, key="PROJ-101", gitlab_project="acme/billing", gitlab_iid=101)
    srv.start(); ...; srv.requests; srv.stop()
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse


def parse_ticket(md: str) -> tuple[str, list[str], list[str]]:
    """ticket.md -> (title, description paragraphs, comments). Lines after
    'Comment from ...:' paragraphs become comments."""
    first, _, rest = md.strip().partition("\n")
    title = first.split(":", 1)[1].strip() if ":" in first else first
    paras = [p.strip("\n") for p in rest.strip().split("\n\n") if p.strip()]
    desc = [p for p in paras if not p.lower().startswith("comment from")]
    comments = [p for p in paras if p.lower().startswith("comment from")]
    return title, desc, comments


def adf(paragraphs: list[str]) -> dict:
    """Atlassian Document Format, the way Jira Cloud's v3 API returns rich text."""
    content = []
    for p in paragraphs:
        if all(l.startswith("    ") for l in p.splitlines()):
            content.append({"type": "codeBlock", "content": [
                {"type": "text", "text": "\n".join(l[4:] for l in p.splitlines())}]})
        else:
            content.append({"type": "paragraph", "content": [{"type": "text", "text": p}]})
    return {"type": "doc", "version": 1, "content": content}


class MockTracker:
    def __init__(self, ticket_md: str, key: str, gitlab_project: str, gitlab_iid: int):
        self.title, self.desc, self.comments = parse_ticket(ticket_md)
        self.key, self.project, self.iid = key, gitlab_project, gitlab_iid
        self.requests: list[str] = []
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # keep eval output clean
                pass

            def _send(self, code: int, body: object) -> None:
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):  # noqa: N802
                path = unquote(urlparse(self.path).path)
                mock.requests.append(f"GET {path} auth={'yes' if self.headers.get('Authorization') or self.headers.get('PRIVATE-TOKEN') else 'no'}")
                # Jira Cloud REST v3
                if path.rstrip("/") == f"/rest/api/3/issue/{mock.key}":
                    return self._send(200, {"key": mock.key, "fields": {
                        "summary": mock.title, "description": adf(mock.desc),
                        "status": {"name": "To Do"}, "priority": {"name": "High"},
                        "labels": ["bug"], "versions": [], "fixVersions": [], "attachment": [],
                        "comment": {"comments": [
                            {"author": {"displayName": c.split(":", 1)[0].removeprefix("Comment from ").strip()},
                             "created": "2026-11-10T10:00:00.000+0000", "body": adf([c.split(":", 1)[1].strip()])}
                            for c in mock.comments]}}})
                if path.startswith(f"/rest/api/3/issue/{mock.key}/comment"):
                    return self._send(200, {"comments": []})
                # GitLab REST v4 (project may be URL-encoded or numeric-free path)
                proj = f"/api/v4/projects/{mock.project}/issues/{mock.iid}"
                if path.rstrip("/") == proj:
                    user = {"id": 7, "username": "support-maria", "name": "Maria", "state": "active",
                            "web_url": "https://gitlab.com/support-maria"}
                    return self._send(200, {
                        "id": 9001, "iid": mock.iid, "project_id": 42, "title": mock.title,
                        "description": "\n\n".join(mock.desc), "state": "opened", "type": "ISSUE",
                        "issue_type": "issue", "labels": ["bug"], "author": user, "assignees": [],
                        "assignee": None, "milestone": None, "closed_by": None, "closed_at": None,
                        "created_at": "2026-11-10T09:00:00Z", "updated_at": "2026-11-10T10:00:00Z",
                        "user_notes_count": len(mock.comments), "upvotes": 0, "downvotes": 0,
                        "confidential": False, "discussion_locked": False, "weight": None,
                        "references": {"short": f"#{mock.iid}", "full": f"{mock.project}#{mock.iid}"},
                        "web_url": f"https://gitlab.com/{mock.project}/-/issues/{mock.iid}",
                        "time_stats": {"time_estimate": 0, "total_time_spent": 0},
                        "task_completion_status": {"count": 0, "completed_count": 0}})
                if path.rstrip("/") == proj + "/notes":
                    return self._send(200, [{"id": 500 + i, "type": None, "noteable_type": "Issue",
                                             "author": {"id": 8, "username": "dev",
                                                        "name": c.split(":", 1)[0].removeprefix("Comment from ").strip()},
                                             "body": c.split(":", 1)[1].strip(), "system": False,
                                             "created_at": "2026-11-10T10:00:00Z",
                                             "updated_at": "2026-11-10T10:00:00Z"}
                                            for i, c in enumerate(mock.comments)])
                return self._send(404, {"errorMessages": ["Issue does not exist"], "message": "404 Not found"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"

    def start(self) -> "MockTracker":
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def stop(self) -> None:
        self.server.shutdown()

    def fetched(self, tracker: str) -> bool:
        needle = f"/rest/api/3/issue/{self.key}" if tracker == "jira" else f"/issues/{self.iid}"
        return any(needle in r for r in self.requests)
