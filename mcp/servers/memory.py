#!/usr/bin/env python3
"""Shared local memory MCP server: Markdown files, one per fact, over stdio.

Store layout (root = $AGENT_MEMORY_DIR, else $XDG_DATA_HOME/agent-memory,
else ~/.local/share/agent-memory):

  global/<name>.md             facts that apply everywhere
  projects/<key>/<name>.md     facts for one project; <key> is the project root
                               path with every non-alphanumeric char as "-"

Tools: search, save, update, forget. `python3 memory.py import-claude
[--dry-run]` copies existing Claude Code auto-memory files into the store.

Standard library only. Does not import anything from bin/agent-setup.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME = 64
MAX_BODY_BYTES = 16 * 1024
MAX_RESULTS = 10
TYPES = ("user", "feedback", "project", "reference")
SCOPES = ("global", "project")
PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")  # newest first
SERVER_INFO = {"name": "memory", "version": "1.0.0"}

INSTRUCTIONS = (
    "Shared persistent memory. At the start of a task call `search` with no query and your "
    "project_path to see what is known. `save` durable facts (preferences, corrections, project "
    "decisions, references); `update` instead of duplicating; `forget` stale facts. Never save "
    "secrets. Use only this server for memory, never built-in memory files."
)

PROJECT_PATH_PROP = {"type": "string",
                     "description": "Absolute path of your working directory; picks the project scope."}
TOOLS = [
    {"name": "search",
     "description": "Without a query, list every memory (name, scope, type, description) from global and "
                    "this project. With a query, return up to 10 best matches with their bodies.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "Words to look for; omit to list the index."},
         "project_path": PROJECT_PATH_PROP}}},
    {"name": "save",
     "description": "Create a new memory. Fails if the name already exists in that scope (use update).",
     "inputSchema": {"type": "object", "required": ["name", "description", "type", "body"], "properties": {
         "name": {"type": "string", "description": "lowercase-hyphenated, max 64 chars; becomes the filename"},
         "description": {"type": "string", "description": "One line saying what this memory is."},
         "type": {"type": "string", "enum": list(TYPES)},
         "body": {"type": "string", "description": "The memory itself, max 16 KB."},
         "scope": {"type": "string", "enum": list(SCOPES),
                   "description": "Defaults to global for type user, else project."},
         "project_path": PROJECT_PATH_PROP}}},
    {"name": "update",
     "description": "Change fields of an existing memory. Omitted fields keep their value.",
     "inputSchema": {"type": "object", "required": ["name", "scope"], "properties": {
         "name": {"type": "string"},
         "scope": {"type": "string", "enum": list(SCOPES)},
         "description": {"type": "string"},
         "type": {"type": "string", "enum": list(TYPES)},
         "body": {"type": "string"},
         "project_path": PROJECT_PATH_PROP}}},
    {"name": "forget",
     "description": "Delete a memory.",
     "inputSchema": {"type": "object", "required": ["name", "scope"], "properties": {
         "name": {"type": "string"},
         "scope": {"type": "string", "enum": list(SCOPES)},
         "project_path": PROJECT_PATH_PROP}}},
]


class ToolError(Exception):
    """A user-facing tool failure; the message becomes the isError text."""


def warn(msg: str) -> None:
    print(f"memory: {msg}", file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- #
# Store location and project key
# --------------------------------------------------------------------------- #
def store_root() -> Path:
    explicit = os.environ.get("AGENT_MEMORY_DIR")
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return base / "agent-memory"


def slugify_path(path: str) -> str:
    """Claude Code's project slug: every non-alphanumeric char becomes '-'."""
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def project_root(project_path: str | None) -> str:
    """Git root shared by all worktrees (parent of the common git dir); else the path itself."""
    raw = os.path.abspath(os.path.expanduser(project_path)) if project_path else os.getcwd()
    try:
        r = subprocess.run(["git", "-C", raw, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                           capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return raw
    out = r.stdout.strip()
    if r.returncode != 0 or not out:
        return raw
    return str(Path(out).parent)


def project_key(project_path: str | None) -> str:
    return slugify_path(project_root(project_path))


def scope_dir(scope: str, project_path: str | None) -> Path:
    if scope == "global":
        return store_root() / "global"
    return store_root() / "projects" / project_key(project_path)


def ensure_dir(d: Path) -> None:
    """Create d and any missing parents, each with mode 0700."""
    missing = []
    cur = d
    while not cur.exists():
        missing.append(cur)
        cur = cur.parent
    for p in reversed(missing):
        try:
            p.mkdir(mode=0o700)
        except FileExistsError:
            pass


# --------------------------------------------------------------------------- #
# Memory files
# --------------------------------------------------------------------------- #
@dataclass
class Memory:
    name: str
    description: str
    type: str
    body: str
    created: str
    updated: str
    scope: str = ""


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _value(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        try:
            return str(json.loads(raw))
        except json.JSONDecodeError:
            return raw[1:-1]
    if len(raw) >= 2 and raw[0] == "'" and raw[-1] == "'":
        return raw[1:-1].replace("''", "'")
    return raw


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (fields, body). Top-level `key: value` lines; one nested level under a bare `key:`."""
    if not text.startswith("---\n"):
        raise ValueError("missing '---' frontmatter")
    end = text.find("\n---", 3)
    if end == -1:
        raise ValueError("unterminated frontmatter")
    meta: dict = {}
    nested: dict | None = None
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^(\s*)([A-Za-z0-9_.-]+):(.*)$", line)
        if not m:
            raise ValueError(f"cannot parse frontmatter line: {line!r}")
        indent, key, rest = m.groups()
        if indent and nested is not None:
            nested[key] = _value(rest)
        elif rest.strip() == "":
            nested = meta.setdefault(key, {})
        else:
            nested = None
            meta[key] = _value(rest)
    return meta, text[end + 4:].strip("\n")


def render_memory(m: Memory) -> str:
    def q(s: str) -> str:
        return json.dumps(s, ensure_ascii=False)
    return ("---\n"
            f"name: {q(m.name)}\n"
            f"description: {q(m.description)}\n"
            f"type: {q(m.type)}\n"
            f"created: {q(m.created)}\n"
            f"updated: {q(m.updated)}\n"
            "---\n\n"
            f"{m.body.rstrip(chr(10))}\n")


def read_memory(path: Path, scope: str) -> Memory:
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    name, desc, typ = meta.get("name"), meta.get("description"), meta.get("type")
    if not isinstance(name, str) or not isinstance(desc, str) or typ not in TYPES:
        raise ValueError("frontmatter needs name, description and a valid type")
    return Memory(name=name, description=desc, type=typ, body=body,
                  created=str(meta.get("created", "")), updated=str(meta.get("updated", "")), scope=scope)


def write_atomic(path: Path, content: str) -> None:
    """Write via a temp file in the same dir, then os.replace, so readers never see a half file."""
    ensure_dir(path.parent)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".part", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def list_scope(scope: str, project_path: str | None) -> list[Memory]:
    d = scope_dir(scope, project_path)
    out: list[Memory] = []
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*.md")):
        try:
            out.append(read_memory(f, scope))
        except (ValueError, OSError, UnicodeDecodeError) as e:
            warn(f"skipping malformed memory file {f}: {e}")
    return out


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
def _check_name(name) -> str:
    if not isinstance(name, str) or len(name) > MAX_NAME or not NAME_RE.match(name):
        raise ToolError("name must be lowercase letters, digits and single hyphens, at most 64 chars")
    return name


def _check_type(typ) -> str:
    if typ not in TYPES:
        raise ToolError(f"type must be one of {', '.join(TYPES)}")
    return typ


def _check_scope(scope) -> str:
    if scope not in SCOPES:
        raise ToolError(f"scope must be one of {', '.join(SCOPES)}")
    return scope


def _check_text(value, field: str) -> str:
    if not isinstance(value, str):
        raise ToolError(f"{field} must be a string")
    return value


def _check_body(body) -> str:
    _check_text(body, "body")
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        raise ToolError(f"body is over the {MAX_BODY_BYTES // 1024} KB limit")
    return body


def _check_description(desc) -> str:
    _check_text(desc, "description")
    desc = " ".join(desc.split())
    if not desc:
        raise ToolError("description must not be empty")
    return desc


def _path_for(name: str, scope: str, project_path: str | None) -> Path:
    return scope_dir(scope, project_path) / f"{name}.md"


def _score(m: Memory, terms: list[str]) -> int:
    name, desc, body = m.name.lower(), m.description.lower(), m.body.lower()
    return sum((3 if t in name else 0) + (2 if t in desc else 0) + (1 if t in body else 0) for t in terms)


def tool_search(args: dict) -> str:
    project_path = args.get("project_path")
    query = args.get("query")
    if query is not None and not isinstance(query, str):
        raise ToolError("query must be a string")
    items = list_scope("global", project_path) + list_scope("project", project_path)
    terms = (query or "").lower().split()
    if not terms:
        if not items:
            return "No memories yet."
        return "\n".join(f"- {m.name} [{m.scope}, {m.type}]: {m.description}" for m in items)
    scored = sorted(((_score(m, terms), m) for m in items), key=lambda p: -p[0])
    hits = [m for s, m in scored if s > 0][:MAX_RESULTS]
    if not hits:
        return "No matching memories."
    return "\n\n".join(f"## {m.name} [{m.scope}, {m.type}]\n{m.description}\n\n{m.body}" for m in hits)


def tool_save(args: dict) -> str:
    name = _check_name(args.get("name"))
    desc = _check_description(args.get("description"))
    typ = _check_type(args.get("type"))
    body = _check_body(args.get("body"))
    scope = args.get("scope") or ("global" if typ == "user" else "project")
    _check_scope(scope)
    path = _path_for(name, scope, args.get("project_path"))
    if path.exists():
        raise ToolError(f"{name} already exists in {scope} scope; use update")
    ts = now_iso()
    write_atomic(path, render_memory(Memory(name, desc, typ, body, ts, ts)))
    return f"Saved {name} ({scope})."


def tool_update(args: dict) -> str:
    name = _check_name(args.get("name"))
    scope = _check_scope(args.get("scope"))
    path = _path_for(name, scope, args.get("project_path"))
    if not path.is_file():
        raise ToolError(f"{name} not found in {scope} scope")
    try:
        m = read_memory(path, scope)
    except (ValueError, OSError, UnicodeDecodeError) as e:
        raise ToolError(f"{name} is malformed: {e}") from e
    if args.get("description") is not None:
        m.description = _check_description(args["description"])
    if args.get("type") is not None:
        m.type = _check_type(args["type"])
    if args.get("body") is not None:
        m.body = _check_body(args["body"])
    m.updated = now_iso()
    write_atomic(path, render_memory(m))
    return f"Updated {name} ({scope})."


def tool_forget(args: dict) -> str:
    name = _check_name(args.get("name"))
    scope = _check_scope(args.get("scope"))
    path = _path_for(name, scope, args.get("project_path"))
    if not path.is_file():
        raise ToolError(f"{name} not found in {scope} scope")
    path.unlink()
    return f"Forgot {name} ({scope})."


TOOL_FUNCS = {"search": tool_search, "save": tool_save, "update": tool_update, "forget": tool_forget}


# --------------------------------------------------------------------------- #
# JSON-RPC 2.0 over newline-delimited stdio
# --------------------------------------------------------------------------- #
def _error(rid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def _result(rid, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def handle_message(msg) -> dict | None:
    """Return the response for one decoded message, or None when no reply is due."""
    if not isinstance(msg, dict) or not isinstance(msg.get("method"), str):
        return _error(msg.get("id") if isinstance(msg, dict) else None, -32600, "invalid request")
    method, rid = msg["method"], msg.get("id")
    if "id" not in msg:  # notification: never answered
        return None
    params = msg.get("params")
    params = params if isinstance(params, dict) else {}
    if method == "initialize":
        asked = params.get("protocolVersion")
        version = asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
        return _result(rid, {"protocolVersion": version, "capabilities": {"tools": {}},
                             "serverInfo": SERVER_INFO, "instructions": INSTRUCTIONS})
    if method == "ping":
        return _result(rid, {})
    if method == "tools/list":
        return _result(rid, {"tools": TOOLS})
    if method == "tools/call":
        func = TOOL_FUNCS.get(params.get("name"))
        if func is None:
            return _error(rid, -32602, f"unknown tool: {params.get('name')!r}")
        arguments = params.get("arguments")
        try:
            if arguments is not None and not isinstance(arguments, dict):
                raise ToolError("arguments must be an object")
            text, is_error = func(arguments or {}), False
        except ToolError as e:
            text, is_error = str(e), True
        except OSError as e:
            text, is_error = f"storage error: {e}", True
        return _result(rid, {"content": [{"type": "text", "text": text}], "isError": is_error})
    return _error(rid, -32601, f"method not found: {method}")


def serve(stdin=None, stdout=None) -> int:
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            resp = _error(None, -32700, "parse error")
        else:
            try:
                resp = handle_message(msg)
            except Exception as e:  # keep the loop alive; report on stderr
                warn(f"internal error: {e!r}")
                resp = _error(msg.get("id") if isinstance(msg, dict) else None, -32603, "internal error")
        if resp is not None:
            stdout.write(json.dumps(resp) + "\n")
            stdout.flush()
    return 0


# --------------------------------------------------------------------------- #
# import-claude
# --------------------------------------------------------------------------- #
def import_claude(dry_run: bool, claude_dir: Path | None = None) -> tuple[int, int]:
    """Copy Claude auto-memory files into the store. Returns (imported, skipped). Never touches sources."""
    projects = (claude_dir or Path.home() / ".claude") / "projects"
    imported = skipped = 0
    if not projects.is_dir():
        print(f"nothing to import: {projects} not found")
        return 0, 0
    for mem_dir in sorted(projects.glob("*/memory")):
        slug = mem_dir.parent.name
        for f in sorted(mem_dir.glob("*.md")):
            if f.name == "MEMORY.md":
                continue
            try:
                meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
                nested = meta.get("metadata") if isinstance(meta.get("metadata"), dict) else {}
                typ = meta.get("type") if isinstance(meta.get("type"), str) else nested.get("type")
                name = meta.get("name") if isinstance(meta.get("name"), str) else f.stem
                desc = _check_description(meta.get("description"))
                _check_name(name)
                _check_type(typ)
                _check_body(body)
            except (ValueError, OSError, UnicodeDecodeError, ToolError) as e:
                print(f"  skip      {f}: {e}")
                skipped += 1
                continue
            dest = (store_root() / "global" if typ == "user" else store_root() / "projects" / slug) / f"{name}.md"
            if dest.exists():
                print(f"  exists    {dest}")
                skipped += 1
                continue
            print(f"  {'would import' if dry_run else 'import':<9} {f} -> {dest}")
            if not dry_run:
                ts = now_iso()
                write_atomic(dest, render_memory(Memory(name, desc, typ, body, ts, ts)))
            imported += 1
    print(f"{'would import' if dry_run else 'imported'} {imported}, skipped {skipped}")
    return imported, skipped


def main(argv: list[str]) -> int:
    if argv and argv[0] == "import-claude":
        rest = argv[1:]
        if any(a != "--dry-run" for a in rest):
            print("usage: memory.py import-claude [--dry-run]", file=sys.stderr)
            return 2
        import_claude("--dry-run" in rest)
        return 0
    if argv:
        print("usage: memory.py [import-claude [--dry-run]]", file=sys.stderr)
        return 2
    return serve()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
