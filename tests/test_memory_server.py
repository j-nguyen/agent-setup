"""Tests for mcp/servers/memory.py (unit, stdio and import-claude). Standard library only."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent / "mcp" / "servers" / "memory.py"
spec = importlib.util.spec_from_file_location("memory_server", SERVER)
mem = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mem)


def git(cwd, *args):
    subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args], cwd=cwd, check=True, capture_output=True,
                   timeout=30, stdin=subprocess.DEVNULL,
                   env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.store = self.tmp / "store"
        self._old = os.environ.get("AGENT_MEMORY_DIR")
        os.environ["AGENT_MEMORY_DIR"] = str(self.store)
        self.proj = self.tmp / "proj"
        self.proj.mkdir()

    def tearDown(self):
        if self._old is None:
            os.environ.pop("AGENT_MEMORY_DIR", None)
        else:
            os.environ["AGENT_MEMORY_DIR"] = self._old
        self._tmp.cleanup()

    def save(self, name="a-fact", typ="feedback", **kw):
        args = {"name": name, "description": "desc " + name, "type": typ, "body": "body of " + name,
                "project_path": str(self.proj)}
        args.update(kw)
        return mem.tool_save(args)


class ToolTests(StoreTestCase):
    def test_round_trip(self):
        self.save("alpha", "feedback", body="Prefer tabs")
        out = mem.tool_search({"query": "tabs", "project_path": str(self.proj)})
        self.assertIn("alpha", out)
        self.assertIn("Prefer tabs", out)
        mem.tool_update({"name": "alpha", "scope": "project", "body": "Prefer spaces",
                         "project_path": str(self.proj)})
        out = mem.tool_search({"query": "spaces", "project_path": str(self.proj)})
        self.assertIn("Prefer spaces", out)
        mem.tool_forget({"name": "alpha", "scope": "project", "project_path": str(self.proj)})
        self.assertEqual(mem.tool_search({"project_path": str(self.proj)}), "No memories yet.")

    def test_update_keeps_created_and_other_fields(self):
        self.save("alpha")
        path = mem.scope_dir("project", str(self.proj)) / "alpha.md"
        before = mem.read_memory(path, "project")
        mem.tool_update({"name": "alpha", "scope": "project", "description": "new",
                         "project_path": str(self.proj)})
        after = mem.read_memory(path, "project")
        self.assertEqual(after.created, before.created)
        self.assertEqual(after.body, before.body)
        self.assertEqual(after.description, "new")

    def test_empty_query_lists_both_scopes(self):
        self.save("who-i-am", "user")
        self.save("repo-rule", "project")
        out = mem.tool_search({"project_path": str(self.proj)})
        self.assertIn("who-i-am [global, user]", out)
        self.assertIn("repo-rule [project, project]", out)

    def test_other_project_not_listed(self):
        self.save("repo-rule", "project")
        other = self.tmp / "other"
        other.mkdir()
        self.assertNotIn("repo-rule", mem.tool_search({"project_path": str(other)}))

    def test_ranking_name_over_description_over_body(self):
        self.save("zzz-one", description="nothing", body="widget")
        self.save("zzz-two", description="widget", body="nothing")
        self.save("widget", description="nothing", body="nothing")
        out = mem.tool_search({"query": "widget", "project_path": str(self.proj)})
        order = [out.index("## widget"), out.index("## zzz-two"), out.index("## zzz-one")]
        self.assertEqual(order, sorted(order))

    def test_query_returns_at_most_ten(self):
        for i in range(12):
            self.save(f"fact-{i}", body="needle")
        out = mem.tool_search({"query": "needle", "project_path": str(self.proj)})
        self.assertEqual(out.count("\n## ") + 1, 10)

    def test_compact_search_and_exact_lookup(self):
        body = "Beginning. " * 100 + "needle here " + "End. " * 100
        self.save("alpha", body=body)
        self.save("alpha", scope="global", body="A global needle")
        args = {"project_path": str(self.proj)}
        hits = mem.tool_search({**args, "query": "needle", "compact": True})
        self.assertIn("alpha [project, feedback]", hits)
        self.assertIn("alpha [global, feedback]", hits)
        self.assertIn("needle here", hits)
        self.assertLess(len(hits), 500)
        note = mem.tool_get({**args, "name": "alpha", "scope": "project"})
        self.assertIn(body.rstrip(), note)
        self.assertNotIn("A global needle", note)

    def test_stale_revision_cannot_update_or_forget_a_note(self):
        self.save("alpha", scope="global")
        args = {"name": "alpha", "scope": "global"}
        note = mem.tool_get(args)
        revision = note.split("Revision: ", 1)[1].splitlines()[0]
        mem.tool_update({**args, "revision": revision, "body": "new body"})
        for write in (mem.tool_update, mem.tool_forget):
            with self.assertRaisesRegex(mem.ToolError, "changed since it was read"):
                write({**args, "revision": revision})
        note = mem.tool_get(args)
        self.assertIn("new body", note)
        current = note.split("Revision: ", 1)[1].splitlines()[0]
        mem.tool_forget({**args, "revision": current})
        with self.assertRaisesRegex(mem.ToolError, "not found"):
            mem.tool_get(args)

    def test_scope_default(self):
        self.save("u", "user")
        self.save("f", "feedback")
        self.assertTrue((self.store / "global" / "u.md").is_file())
        self.assertTrue((mem.scope_dir("project", str(self.proj)) / "f.md").is_file())

    def test_explicit_scope_overrides_default(self):
        self.save("u", "user", scope="project")
        self.assertTrue((mem.scope_dir("project", str(self.proj)) / "u.md").is_file())

    def test_bad_names_rejected(self):
        for bad in ("../x", "A", "a" * 65, "a--b", "", "a/b"):
            with self.assertRaises(mem.ToolError, msg=bad):
                self.save(bad)

    def test_max_length_name_ok(self):
        self.save("a" * 64)

    def test_bad_type_and_scope_rejected(self):
        with self.assertRaises(mem.ToolError):
            self.save("x", "bogus")
        with self.assertRaises(mem.ToolError):
            self.save("x", scope="elsewhere")

    def test_body_cap(self):
        self.save("ok", body="x" * mem.MAX_BODY_BYTES)
        with self.assertRaises(mem.ToolError):
            self.save("big", body="x" * (mem.MAX_BODY_BYTES + 1))

    def test_duplicate_save_fails(self):
        self.save("dup")
        with self.assertRaises(mem.ToolError) as cm:
            self.save("dup")
        self.assertIn("update", str(cm.exception))

    def test_update_and_forget_missing_fail(self):
        with self.assertRaises(mem.ToolError):
            mem.tool_update({"name": "nope", "scope": "global"})
        with self.assertRaises(mem.ToolError):
            mem.tool_forget({"name": "nope", "scope": "global"})

    def test_file_format(self):
        self.save("fmt", "reference", body="line1\nline2")
        text = (mem.scope_dir("project", str(self.proj)) / "fmt.md").read_text()
        self.assertTrue(text.startswith('---\nname: "fmt"\ndescription: "desc fmt"\ntype: "reference"\ncreated: "'))
        self.assertIn('\nupdated: "', text)
        self.assertTrue(text.endswith("---\n\nline1\nline2\n"))

    def test_store_dirs_are_0700(self):
        self.save("perm")
        self.assertEqual(self.store.stat().st_mode & 0o777, 0o700)
        self.assertEqual(mem.scope_dir("project", str(self.proj)).stat().st_mode & 0o777, 0o700)

    def test_no_temp_files_left(self):
        self.save("clean")
        names = [p.name for p in mem.scope_dir("project", str(self.proj)).iterdir()]
        self.assertEqual(names, ["clean.md"])

    def test_malformed_file_skipped(self):
        self.save("good")
        d = mem.scope_dir("project", str(self.proj))
        (d / "bad.md").write_text("no frontmatter here")
        out = mem.tool_search({"project_path": str(self.proj)})
        self.assertIn("good", out)
        self.assertNotIn("bad", out.replace("body", ""))

    def test_hand_edit_visible_immediately(self):
        self.save("hand")
        path = mem.scope_dir("project", str(self.proj)) / "hand.md"
        path.write_text(path.read_text().replace("body of hand", "edited by hand"))
        self.assertIn("edited by hand", mem.tool_search({"query": "edited", "project_path": str(self.proj)}))


class SlugTests(unittest.TestCase):
    def test_slug_samples_from_all_platforms(self):
        cases = {
            "/home/jnguyen/Documents/Projects/agent-setup": "-home-jnguyen-Documents-Projects-agent-setup",
            "/Users/jo/code/my.app": "-Users-jo-code-my-app",
            "/mnt/c/Users/jo/proj_x": "-mnt-c-Users-jo-proj-x",
        }
        for path, slug in cases.items():
            self.assertEqual(mem.slugify_path(path), slug)


class ProjectKeyTests(StoreTestCase):
    def test_worktree_and_main_share_key(self):
        repo = self.tmp / "repo"
        repo.mkdir()
        git(repo, "init", "-q")
        git(repo, "commit", "-q", "--allow-empty", "-m", "init")
        wt = self.tmp / "repo-wt"
        git(repo, "worktree", "add", "-q", str(wt), "-b", "other")
        sub = repo / "sub"
        sub.mkdir()
        keys = {mem.project_key(str(p)) for p in (repo, wt, sub)}
        self.assertEqual(keys, {mem.slugify_path(str(repo))})

    def test_non_git_falls_back_to_path(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        self.assertEqual(mem.project_key(str(plain)), mem.slugify_path(str(plain)))

    def test_missing_path_falls_back(self):
        gone = self.tmp / "does-not-exist"
        self.assertEqual(mem.project_key(str(gone)), mem.slugify_path(str(gone)))

    def test_no_project_path_uses_cwd(self):
        old = os.getcwd()
        plain = self.tmp / "cwdplain"
        plain.mkdir()
        os.chdir(plain)
        try:
            self.assertEqual(mem.project_key(None), mem.slugify_path(str(plain)))
        finally:
            os.chdir(old)


class StoreRootTests(unittest.TestCase):
    def test_precedence(self):
        keep = {k: os.environ.get(k) for k in ("AGENT_MEMORY_DIR", "XDG_DATA_HOME")}
        try:
            os.environ.pop("AGENT_MEMORY_DIR", None)
            os.environ["XDG_DATA_HOME"] = "/x/data"
            self.assertEqual(mem.store_root(), Path("/x/data/agent-memory"))
            os.environ["AGENT_MEMORY_DIR"] = "/x/mem"
            self.assertEqual(mem.store_root(), Path("/x/mem"))
            os.environ.pop("AGENT_MEMORY_DIR")
            os.environ.pop("XDG_DATA_HOME")
            self.assertEqual(mem.store_root(), Path.home() / ".local" / "share" / "agent-memory")
        finally:
            for k, v in keep.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class StdioTests(StoreTestCase):
    def run_server(self, *lines):
        r = subprocess.run([sys.executable, str(SERVER)], input="\n".join(lines) + "\n", capture_output=True,
                           text=True, timeout=30, env={**os.environ, "AGENT_MEMORY_DIR": str(self.store)})
        out = [json.loads(l) for l in r.stdout.splitlines()]  # raises if stdout has non-JSON
        return out, r.stderr

    def test_initialize_and_tools_list(self):
        out, _ = self.run_server(
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05"}}),
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}))
        self.assertEqual(len(out), 2)  # the notification got no reply
        self.assertEqual(out[0]["result"]["protocolVersion"], "2024-11-05")
        self.assertIn("search", out[0]["result"]["instructions"])
        tools = out[1]["result"]["tools"]
        self.assertEqual([t["name"] for t in tools], ["search", "get", "save", "update", "forget"])
        for t in tools:
            self.assertIn("project_path", t["inputSchema"]["properties"])

    def test_unsupported_version_gets_newest(self):
        out, _ = self.run_server(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                             "params": {"protocolVersion": "1999-01-01"}}))
        self.assertEqual(out[0]["result"]["protocolVersion"], mem.PROTOCOL_VERSIONS[0])

    def test_unknown_method_and_parse_error_then_continue(self):
        out, _ = self.run_server(
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "nope/nope"}),
            "{not json",
            json.dumps({"jsonrpc": "2.0", "id": 3, "method": "ping"}))
        self.assertEqual(out[0]["error"]["code"], -32601)
        self.assertEqual(out[1]["error"]["code"], -32700)
        self.assertIsNone(out[1]["id"])
        self.assertEqual(out[2]["result"], {})

    def test_tool_call_success_and_failure(self):
        call = lambda i, name, args: json.dumps({"jsonrpc": "2.0", "id": i, "method": "tools/call",
                                                 "params": {"name": name, "arguments": args}})
        base = {"description": "d", "type": "user", "body": "b", "project_path": str(self.proj)}
        out, _ = self.run_server(call(1, "save", {"name": "me", **base}),
                                 call(2, "save", {"name": "me", **base}),
                                 call(3, "save", {"name": "../x", **base}),
                                 call(4, "nope", {}))
        self.assertFalse(out[0]["result"]["isError"])
        self.assertTrue(out[1]["result"]["isError"])
        self.assertTrue(out[2]["result"]["isError"])
        self.assertEqual(out[3]["error"]["code"], -32602)

    def test_malformed_file_warns_on_stderr_only(self):
        d = self.store / "global"
        d.mkdir(parents=True)
        (d / "bad.md").write_text("junk")
        out, err = self.run_server(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                               "params": {"name": "search", "arguments": {}}}))
        self.assertFalse(out[0]["result"]["isError"])
        self.assertIn("bad.md", err)


class ImportTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        self.claude = self.tmp / "home" / ".claude"
        self.mdir = self.claude / "projects" / "-home-x-proj" / "memory"
        self.mdir.mkdir(parents=True)
        (self.mdir / "MEMORY.md").write_text("- [index](a.md)\n")
        (self.mdir / "no-trailer.md").write_text(
            '---\nname: no-trailer\ndescription: never add trailers\nmetadata:\n  type: feedback\n---\n\nBody one\n')
        (self.mdir / "who.md").write_text(
            "---\nname: who\ndescription: \"I am a dev\"\ntype: user\n---\n\nBody two\n")
        (self.mdir / "broken.md").write_text("---\nname: broken\n---\nno type\n")

    def snapshot(self):
        return {str(p): p.read_bytes() for p in self.claude.rglob("*") if p.is_file()}

    def test_import_maps_scopes_and_is_idempotent(self):
        before = self.snapshot()
        with open(os.devnull, "w") as sink:
            old, sys.stdout = sys.stdout, sink
            try:
                self.assertEqual(mem.import_claude(False, self.claude), (2, 1))
                self.assertEqual(mem.import_claude(False, self.claude), (0, 3))
            finally:
                sys.stdout = old
        self.assertTrue((self.store / "global" / "who.md").is_file())
        self.assertTrue((self.store / "projects" / "-home-x-proj" / "no-trailer.md").is_file())
        self.assertFalse(list(self.store.rglob("MEMORY.md")))
        moved = mem.read_memory(self.store / "projects" / "-home-x-proj" / "no-trailer.md", "project")
        self.assertEqual((moved.type, moved.body), ("feedback", "Body one"))
        self.assertEqual(self.snapshot(), before)

    def test_dry_run_writes_nothing(self):
        before = self.snapshot()
        r = subprocess.run([sys.executable, str(SERVER), "import-claude", "--dry-run"], capture_output=True,
                           text=True, timeout=30,
                           env={**os.environ, "HOME": str(self.tmp / "home"), "AGENT_MEMORY_DIR": str(self.store)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("would import 2", r.stdout)
        self.assertFalse(self.store.exists())
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
