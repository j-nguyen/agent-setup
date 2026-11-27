"""Tests for mcp/servers/postgres.py. Standard library only.

Unit tests put a stub `psql` first on PATH: it records its argv and the PG* variables it got, and prints canned
output. Integration tests need a real PostgreSQL and a superuser URL in POSTGRES_MCP_TEST_ADMIN_URL; without it
they are skipped.
"""
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit, urlunsplit

SERVER = Path(__file__).resolve().parent.parent / "mcp" / "servers" / "postgres.py"
spec = importlib.util.spec_from_file_location("postgres_server", SERVER)
pg = importlib.util.module_from_spec(spec)
sys.modules["postgres_server"] = pg  # dataclasses looks the module up by name
spec.loader.exec_module(pg)

GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

STUB = """#!{python}
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
cfg = json.load(open(os.path.join(here, "stub.json")))
cmds = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "-c"]
with open(os.path.join(here, "calls.jsonl"), "a") as f:
    f.write(json.dumps({{"argv": sys.argv[1:], "cmds": cmds,
                        "env": {{k: v for k, v in os.environ.items() if k.startswith("PG")}}}}) + "\\n")
joined = "\\n".join(cmds)
for needle, out in cfg.get("outputs", []):
    if needle in joined:
        sys.stdout.write(out)
        break
if cfg.get("stderr"):
    sys.stderr.write(cfg["stderr"])
sys.exit(cfg.get("exit", 0))
"""

CHECK_OK = "localhost 5432\nkind,detail\ninfo,appdb agent_ro\n"


def git(cwd, *args):
    subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, check=True, capture_output=True,
                   timeout=30, stdin=subprocess.DEVNULL, env={**os.environ, **GIT_ENV})


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))
        self.proj = self.root / "proj"
        (self.proj / ".agents").mkdir(parents=True)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        stub = self.bin / "psql"
        stub.write_text(STUB.format(python=sys.executable), encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        self.set_stub()
        self.svcfile = self.root / "pg_service.conf"
        self.svcfile.write_text("[svc]\nhost=localhost\n", encoding="utf-8")  # the default local service
        self.sysdir = self.root / "sysconf"  # no pg_service.conf in it unless a test writes one
        self.sysdir.mkdir()
        env = mock.patch.dict(os.environ, {"PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
                                           "PGSERVICEFILE": str(self.svcfile),
                                           "PGSYSCONFDIR": str(self.sysdir)})
        env.start()
        self.addCleanup(env.stop)
        pg._CHECK_CACHE.clear()
        self.addCleanup(pg._CHECK_CACHE.clear)
        self.session_setup = pg.session_setup(pg.parse_config({"service": "x"}, Path("x")))

    def set_stub(self, outputs=None, **kw):
        data = {"outputs": (outputs or []) + [["\\echo", CHECK_OK]], **kw}  # first match wins
        (self.bin / "stub.json").write_text(json.dumps(data), encoding="utf-8")

    def raw_calls(self):
        f = self.bin / "calls.jsonl"
        return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []

    def calls(self):
        """Calls with the fixed session SET prefix removed from "cmds" (it is asserted on its own)."""
        out = []
        for c in self.raw_calls():
            n = len(self.session_setup)
            self.assertEqual(c["cmds"][:n], self.session_setup)
            out.append({**c, "cmds": c["cmds"][n:]})
        return out

    def config(self, **cfg):
        (self.proj / ".agents" / pg.CONFIG_FILE).write_text(json.dumps(cfg), encoding="utf-8")

    def call(self, name, **args):
        args.setdefault("project_path", str(self.proj))
        resp = pg.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                  "params": {"name": name, "arguments": args}})
        res = resp["result"]
        return res["content"][0]["text"], res["isError"]


class ConfigTests(Base):
    def test_missing_config_is_not_configured_with_steps(self):
        text, err = self.call("query", sql="select 1")
        self.assertTrue(err)
        self.assertTrue(text.startswith("NOT CONFIGURED:"))
        self.assertIn("postgres.local.json", text)
        self.assertIn("GRANT pg_read_all_data", text)

    def test_unknown_key_refused(self):
        self.config(service="x", sslmode="disable")
        text, err = self.call("query", sql="select 1")
        self.assertTrue(err)
        self.assertIn("unknown key", text)

    def test_exactly_one_of_service_and_url_env(self):
        for cfg in ({}, {"service": "a", "url_env": "B"}):
            self.config(**cfg)
            text, err = self.call("query", sql="select 1")
            self.assertTrue(err)
            self.assertIn("exactly one", text)

    def test_limits_and_types(self):
        for cfg in ({"max_rows": 1001}, {"timeout_ms": 60001}, {"max_rows": True}, {"allow_remote": "yes"},
                    {"env_file": "../x"}, {"env_file": "/etc/x"}):
            self.config(service="a", **cfg)
            _, err = self.call("query", sql="select 1")
            self.assertTrue(err, cfg)

    def test_options_url_param_refused(self):
        with self.assertRaises(pg.ToolError):
            pg.conn_from_url("postgres://u:p@localhost/db?options=-c%20default_transaction_read_only%3Doff")

    def test_main_checkout_fallback_for_worktree(self):
        main = self.root / "main"
        main.mkdir()
        git(main, "init", "-q")
        wt = self.root / "wt"
        git(main, "worktree", "add", "-q", "--orphan", "-b", "feature", str(wt))  # no commit needed
        (main / ".agents").mkdir()
        (main / ".agents" / pg.CONFIG_FILE).write_text('{"service": "mainsvc"}', encoding="utf-8")
        project = pg.resolve_project(str(wt))
        self.assertEqual(project.root, os.path.realpath(main))
        self.assertEqual(pg.load_config(project).service, "mainsvc")
        (wt / ".agents").mkdir()
        (wt / ".agents" / pg.CONFIG_FILE).write_text('{"service": "wtsvc"}', encoding="utf-8")
        self.assertEqual(pg.load_config(project).service, "wtsvc")

    def test_url_env_lookup_order(self):
        main = self.root / "main"
        main.mkdir()
        git(main, "init", "-q")
        wt = self.root / "wt"
        git(main, "worktree", "add", "-q", "--orphan", "-b", "feature", str(wt))
        project = pg.resolve_project(str(wt))
        cfg = pg.parse_config({"url_env": "DBURL"}, Path("x"))
        with mock.patch.dict(os.environ, {"DBURL": "postgres://env@h/db"}):
            self.assertEqual(pg.lookup_url(project, cfg), "postgres://env@h/db")
            (main / ".env").write_text("DBURL=postgres://main@h/db\n", encoding="utf-8")
            self.assertEqual(pg.lookup_url(project, cfg), "postgres://main@h/db")
            (wt / ".env").write_text("export DBURL='postgres://wt@h/db'\n", encoding="utf-8")
            self.assertEqual(pg.lookup_url(project, cfg), "postgres://wt@h/db")
        with mock.patch.dict(os.environ, clear=False):
            os.environ.pop("DBURL", None)
            (wt / ".env").unlink()
            (main / ".env").unlink()
            with self.assertRaises(pg.ToolError):
                pg.lookup_url(project, cfg)


class ConnectionTests(Base):
    def test_url_maps_to_env_not_argv(self):
        (self.proj / ".env").write_text("DBURL=postgres://reader:s%40cret@localhost:5433/appdb?sslmode=require\n",
                                        encoding="utf-8")
        self.config(url_env="DBURL")
        self.set_stub([["FETCH", "a\n1\n"]])
        text, err = self.call("query", sql="select 1 as a")
        self.assertFalse(err, text)
        for c in self.calls():
            self.assertNotIn("s@cret", " ".join(c["argv"]))
            self.assertNotIn("s%40cret", " ".join(c["argv"]))
            self.assertNotIn("reader", " ".join(c["argv"]))
            self.assertEqual(c["env"]["PGPASSWORD"], "s@cret")
            self.assertEqual(c["env"]["PGUSER"], "reader")
            self.assertEqual(c["env"]["PGPORT"], "5433")
            self.assertEqual(c["env"]["PGDATABASE"], "appdb")
            self.assertEqual(c["env"]["PGSSLMODE"], "require")
            self.assertIn("default_transaction_read_only=on", c["env"]["PGOPTIONS"])
            self.assertIn("statement_timeout=10000", c["env"]["PGOPTIONS"])
            self.assertEqual(c["env"]["PGAPPNAME"], "agent-postgres-mcp")
            for flag in ("-X", "-q", "-w", "--csv", "ON_ERROR_STOP=1", "pager=off"):
                self.assertIn(flag, c["argv"])

    def test_password_never_in_output_or_errors(self):
        (self.proj / ".env").write_text("DBURL=postgres://reader:hunter2@localhost/appdb\n", encoding="utf-8")
        self.config(url_env="DBURL")
        self.set_stub(exit=3, stderr='psql: error: connection to "hunter2" failed: ERROR: hunter2 is wrong\n')
        text, err = self.call("query", sql="select 1")
        self.assertTrue(err)
        self.assertNotIn("hunter2", text)
        self.assertIn("***", text)

    def test_stderr_capped(self):
        self.config(service="svc")
        self.set_stub([["FETCH", ""]], exit=3, stderr="x" * 10000)
        # the check run (first psql call) fails with exit 3 and a long stderr
        text, err = self.call("query", sql="select 1")
        self.assertTrue(err)
        self.assertLess(len(text), 2200)

    def test_service_uses_pgservice(self):
        self.config(service="svc")
        self.set_stub([["FETCH", "a\n1\n"]])
        self.call("query", sql="select 1")
        self.assertEqual(self.calls()[0]["env"]["PGSERVICE"], "svc")

    def test_connection_exit_code_2(self):
        self.config(service="svc")
        self.set_stub(exit=2, stderr="could not connect")
        text, err = self.call("query", sql="select 1")
        self.assertTrue(err)
        self.assertTrue(text.startswith("CONNECTION:"))

    def test_psql_missing(self):
        self.config(service="svc")
        with mock.patch.dict(os.environ, {"PATH": str(self.root / "empty")}):
            text, err = self.call("query", sql="select 1")
        self.assertTrue(err)
        self.assertTrue(text.startswith("PSQL MISSING:"))


class RoleCheckTests(Base):
    def test_not_read_only_refused_and_no_user_sql_runs(self):
        self.config(service="svc")
        self.set_stub([["\\echo", "localhost 5432\nkind,detail\ninfo,appdb owner\nproblem,role is superuser\n"
                                  "problem,role owns 1 relation(s)\n"]])
        text, err = self.call("query", sql="select 1")
        self.assertTrue(err)
        self.assertTrue(text.startswith("NOT READ-ONLY:"))
        self.assertIn("role is superuser", text)
        self.assertIn("GRANT pg_read_all_data", text)
        self.assertEqual(len(self.calls()), 1)
        self.assertNotIn("BEGIN TRANSACTION READ ONLY", self.calls()[0]["cmds"])

    def test_check_runs_first_and_is_cached(self):
        self.config(service="svc")
        self.set_stub([["FETCH", "a\n1\n"]])
        self.call("query", sql="select 1")
        self.call("query", sql="select 2")
        calls = self.calls()
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0]["cmds"][0], "\\echo :HOST :PORT")
        self.assertEqual(sum(1 for c in calls if "\\echo :HOST :PORT" in c["cmds"]), 1)
        key = next(iter(pg._CHECK_CACHE))
        exp, target = pg._CHECK_CACHE[key]
        pg._CHECK_CACHE[key] = (0.0, target)  # expired: next call checks again
        self.call("query", sql="select 3")
        self.assertEqual(sum(1 for c in self.calls() if "\\echo :HOST :PORT" in c["cmds"]), 2)
        self.assertLessEqual(pg.CHECK_TTL, 300)

    def test_role_sql_covers_every_d4_rule(self):
        sql = pg.ROLE_CHECK_SQL
        for needle in ("rolsuper", "rolcreaterole", "rolcreatedb", "rolreplication", "pg_has_role", "datdba",
                       "nspowner", "relowner", "proowner", "typowner", "has_database_privilege",
                       "has_schema_privilege", "'INSERT'", "'UPDATE'", "'DELETE'", "'TRUNCATE'",
                       "has_sequence_privilege", "has_any_column_privilege(session_user, c.oid, 'INSERT')",
                       "has_any_column_privilege(session_user, c.oid, 'UPDATE')"):
            self.assertIn(needle, sql)
        for r in pg.ALLOWED_ROLES:
            self.assertIn(r, sql)

    def test_remote_url_refused_without_connecting(self):
        (self.proj / ".env").write_text("DBURL=postgres://u:p@db.example.com/x\n", encoding="utf-8")
        self.config(url_env="DBURL")
        text, err = self.call("query", sql="select 1")
        self.assertTrue(err)
        self.assertTrue(text.startswith("REMOTE:"))
        self.assertEqual(self.calls(), [])

    def test_remote_service_refused_after_check_and_allowed_with_flag(self):
        self.config(service="svc")
        self.set_stub([["\\echo", "db.example.com 5432\nkind,detail\ninfo,appdb agent_ro\n"],
                       ["FETCH", "a\n1\n"]])
        text, err = self.call("query", sql="select 1")
        self.assertTrue(err)
        self.assertTrue(text.startswith("REMOTE:"))
        pg._CHECK_CACHE.clear()
        self.config(service="svc", allow_remote=True)
        text, err = self.call("query", sql="select 1")
        self.assertFalse(err, text)

    def test_local_hosts(self):
        for h in ("localhost", "127.0.0.1", "127.9.9.9", "::1", "/var/run/postgresql", "/tmp,127.0.0.1",
                  "localhost,::1", "localhost, [::1] ", "/tmp,,localhost"):
            self.assertTrue(pg.is_local_host(h), h)
        for h in ("10.0.0.1", "db.example.com", "0.0.0.0", "/nonexistent,attacker.example", "127.0.0.1,10.9.9.9",
                  "", ",", " , "):
            self.assertFalse(pg.is_local_host(h), h)

    def test_url_host_list_with_remote_entry_refused_before_psql(self):
        for host in ("/nonexistent,attacker.example", "127.0.0.1,10.9.9.9", ","):
            (self.proj / ".env").write_text(f"DBURL=postgres://u:p@/db?host={host}\n", encoding="utf-8")
            self.config(url_env="DBURL")
            text, err = self.call("query", sql="select 1")
            self.assertTrue(err, host)
            self.assertTrue(text.startswith("REMOTE:"), (host, text))
        self.assertEqual(self.raw_calls(), [])

    def test_url_host_list_all_local_ok(self):
        self.config(url_env="DBURL")
        self.set_stub([["FETCH", "a\n1\n"]])
        for host in ("/tmp,127.0.0.1", "localhost,::1"):
            (self.proj / ".env").write_text(f"DBURL=postgres://u:p@/db?host={host}\n", encoding="utf-8")
            pg._CHECK_CACHE.clear()
            text, err = self.call("query", sql="select 1")
            self.assertFalse(err, (host, text))

    def test_netloc_host_list_with_remote_entry_refused(self):
        (self.proj / ".env").write_text("DBURL=postgres://u:p@127.0.0.1,10.9.9.9/db\n", encoding="utf-8")
        self.config(url_env="DBURL")
        text, err = self.call("query", sql="select 1")
        self.assertTrue(err)
        self.assertTrue(text.startswith(("REMOTE:", "NOT CONFIGURED:")), text)
        self.assertEqual(self.raw_calls(), [])

    def test_remote_target_wins_over_not_read_only(self):
        self.config(service="svc")
        self.set_stub([["\\echo", "db.example.com 5432\nkind,detail\ninfo,appdb owner\nproblem,role is superuser\n"]])
        text, err = self.call("query", sql="select 1")
        self.assertTrue(err)
        self.assertTrue(text.startswith("REMOTE:"), text)
        self.assertNotIn("superuser", text)


class HardeningTests(Base):
    def make_repo(self):
        main = self.root / "main"
        main.mkdir()
        git(main, "init", "-q")
        (main / ".agents").mkdir()
        return main

    def test_tracked_config_refused(self):
        main = self.make_repo()
        (main / ".agents" / pg.CONFIG_FILE).write_text('{"service": "s"}', encoding="utf-8")
        git(main, "add", "-f", ".agents/" + pg.CONFIG_FILE)  # index only: ls-files reads the index
        text, err = self.call("query", sql="select 1", project_path=str(main))
        self.assertTrue(err)
        self.assertTrue(text.startswith("NOT CONFIGURED:"))
        self.assertIn("tracked by git", text)
        self.assertEqual(self.raw_calls(), [])
        # the main checkout's tracked copy is refused for a worktree too
        wt = self.root / "wt"
        git(main, "worktree", "add", "-q", "--orphan", "-b", "feature", str(wt))
        # the orphan worktree has no copy: the config falls back to main's tracked one
        text, err = self.call("query", sql="select 1", project_path=str(wt))
        self.assertTrue(err)
        self.assertIn("tracked by git", text)

    def test_untracked_config_in_git_and_non_git_ok(self):
        main = self.make_repo()
        (main / ".agents" / pg.CONFIG_FILE).write_text('{"service": "svc"}', encoding="utf-8")
        self.set_stub([["FETCH", "a\n1\n"]])
        text, err = self.call("query", sql="select 1", project_path=str(main))
        self.assertFalse(err, text)
        self.config(service="svc")  # self.proj is not a git repo
        text, err = self.call("query", sql="select 1")
        self.assertFalse(err, text)

    def case_insensitive_fs(self):
        probe = self.root / "CaseProbe"
        probe.write_text("x", encoding="utf-8")
        return (self.root / "caseprobe").exists()

    def test_symlinked_agents_dir_refused(self):
        main = self.root / "main"
        (main / "cfg").mkdir(parents=True)
        git(main, "init", "-q")
        (main / "cfg" / pg.CONFIG_FILE).write_text('{"service": "svc"}', encoding="utf-8")
        (main / ".agents").symlink_to("cfg")
        git(main, "add", "-f", ".agents", "cfg")  # index only, no commit
        text, err = self.call("query", sql="select 1", project_path=str(main))
        self.assertTrue(err)
        self.assertTrue(text.startswith("NOT CONFIGURED:"))
        self.assertIn("symlink", text)
        self.assertEqual(self.raw_calls(), [])

    def test_symlinked_config_file_refused_even_outside_git(self):
        real = self.root / "real.json"
        real.write_text('{"service": "svc"}', encoding="utf-8")
        (self.proj / ".agents" / pg.CONFIG_FILE).symlink_to(real)
        text, err = self.call("query", sql="select 1")
        self.assertTrue(err)
        self.assertIn("symlink", text)

    def test_case_variant_tracked_config_refused(self):
        if not self.case_insensitive_fs():
            self.skipTest("case-sensitive file system: `.Agents` is a different path")
        main = self.root / "main"
        (main / ".Agents").mkdir(parents=True)
        git(main, "init", "-q")
        (main / ".Agents" / pg.CONFIG_FILE).write_text('{"service": "svc"}', encoding="utf-8")
        git(main, "add", "-f", ".Agents/" + pg.CONFIG_FILE)
        text, err = self.call("query", sql="select 1", project_path=str(main))
        self.assertTrue(err)
        self.assertIn("tracked by git", text)

    def test_git_failure_inside_a_repo_fails_closed(self):
        main = self.make_repo()
        (main / ".agents" / pg.CONFIG_FILE).write_text('{"service": "svc"}', encoding="utf-8")
        real_git = subprocess.run(["which", "git"], capture_output=True, text=True).stdout.strip()
        stub = self.bin / "git"
        stub.write_text(f'#!/bin/sh\nfor a in "$@"; do [ "$a" = ls-files ] && exit 128; done\nexec {real_git} "$@"\n',
                        encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        text, err = self.call("query", sql="select 1", project_path=str(main))
        self.assertTrue(err)
        self.assertTrue(text.startswith("NOT CONFIGURED:"))
        self.assertIn("cannot be proven untracked", text)
        self.assertIn("exit 128", text)
        self.assertEqual(self.raw_calls(), [])
        # a directory that is not a repository stays allowed even with that git
        self.config(service="svc")
        self.set_stub([["FETCH", "a\n1\n"]])
        text, err = self.call("query", sql="select 1")
        self.assertFalse(err, text)

    def test_git_missing_inside_a_repo_fails_closed(self):
        main = self.make_repo()
        (main / ".agents" / pg.CONFIG_FILE).write_text('{"service": "svc"}', encoding="utf-8")
        with mock.patch.object(pg.subprocess, "run", side_effect=FileNotFoundError("git")):
            self.assertIn("git is not available", pg.personal_file_problem(str(main), ".agents/" + pg.CONFIG_FILE))
            self.assertIsNone(pg.personal_file_problem(str(self.proj), ".agents/" + pg.CONFIG_FILE))

    def test_env_file_symlink_or_case_with_allow_remote_refused(self):
        main = self.make_repo()
        (main / "real.env").write_text("DBURL=postgres://u:p@db.example.com/x\n", encoding="utf-8")
        (main / ".env").symlink_to("real.env")
        project = pg.resolve_project(str(main))
        remote = pg.parse_config({"url_env": "DBURL", "allow_remote": True}, Path("x"))
        with self.assertRaises(pg.ToolError) as cm:
            pg.lookup_url(project, remote)
        self.assertIn("symlink", str(cm.exception))
        local = pg.parse_config({"url_env": "DBURL"}, Path("x"))
        self.assertIn("db.example.com", pg.lookup_url(project, local))
        (main / ".env").unlink()
        if self.case_insensitive_fs():
            (main / ".ENV").write_text("DBURL=postgres://u:p@db.example.com/x\n", encoding="utf-8")
            git(main, "add", ".ENV")
            with self.assertRaises(pg.ToolError) as cm:
                pg.lookup_url(project, remote)
            self.assertIn("tracked by git", str(cm.exception))

    def test_gitlink_at_agents_refused(self):
        main = self.make_repo()
        (main / ".agents" / pg.CONFIG_FILE).write_text('{"service": "svc"}', encoding="utf-8")
        git(main, "update-index", "--add", "--cacheinfo", "160000," + "1" * 40 + ",.agents")  # index only
        text, err = self.call("query", sql="select 1", project_path=str(main))
        self.assertTrue(err)
        self.assertTrue(text.startswith("NOT CONFIGURED:"))
        self.assertIn("nested repository or submodule", text)
        self.assertEqual(self.raw_calls(), [])

    def test_nested_repo_at_agents_refused_tracked_or_not(self):
        main = self.make_repo()
        git(main / ".agents", "init", "-q")
        (main / ".agents" / pg.CONFIG_FILE).write_text('{"service": "svc"}', encoding="utf-8")
        for add in (False, True):
            if add:
                git(main / ".agents", "add", "-f", pg.CONFIG_FILE)  # tracked in the nested index only
            text, err = self.call("query", sql="select 1", project_path=str(main))
            self.assertTrue(err, add)
            self.assertIn("nested repository or submodule", text)
        self.assertEqual(self.raw_calls(), [])

    def test_env_file_in_nested_repo_with_allow_remote_refused(self):
        main = self.make_repo()
        (main / "sub").mkdir()
        git(main / "sub", "init", "-q")
        (main / "sub" / ".env").write_text("DBURL=postgres://u:p@db.example.com/x\n", encoding="utf-8")
        project = pg.resolve_project(str(main))
        remote = pg.parse_config({"url_env": "DBURL", "env_file": "sub/.env", "allow_remote": True}, Path("x"))
        with self.assertRaises(pg.ToolError) as cm:
            pg.lookup_url(project, remote)
        self.assertIn("nested repository or submodule", str(cm.exception))
        local = pg.parse_config({"url_env": "DBURL", "env_file": "sub/.env"}, Path("x"))
        self.assertIn("db.example.com", pg.lookup_url(project, local))

    def test_git_messages_not_localized(self):
        self.config(service="svc")
        self.set_stub([["FETCH", "a\n1\n"]])
        with mock.patch.dict(os.environ, {"LANG": "de_DE.UTF-8", "LC_ALL": "de_DE.UTF-8"}):
            text, err = self.call("query", sql="select 1")  # self.proj is not a git repository
        self.assertFalse(err, text)

    def test_plain_untracked_files_in_a_repo_are_fine(self):
        main = self.make_repo()
        (main / ".env").write_text("DBURL=postgres://u:p@db.example.com/x\n", encoding="utf-8")
        project = pg.resolve_project(str(main))
        remote = pg.parse_config({"url_env": "DBURL", "allow_remote": True}, Path("x"))
        self.assertIn("db.example.com", pg.lookup_url(project, remote))

    def test_tracked_env_file_with_allow_remote_refused(self):
        main = self.make_repo()
        (main / ".env").write_text("DBURL=postgres://u:p@db.example.com/x\n", encoding="utf-8")
        git(main, "add", ".env")
        cfg = pg.parse_config({"url_env": "DBURL", "allow_remote": True}, Path("x"))
        project = pg.resolve_project(str(main))
        with self.assertRaises(pg.ToolError) as cm:
            pg.lookup_url(project, cfg)
        self.assertIn("tracked by git", str(cm.exception))
        local = pg.parse_config({"url_env": "DBURL"}, Path("x"))
        self.assertIn("db.example.com", pg.lookup_url(project, local))  # local-only use is still fine

    def test_every_run_starts_with_session_setup(self):
        self.config(service="svc", timeout_ms=7000)
        self.set_stub([["FETCH", "a\n1\n"]])
        self.call("query", sql="select 1")
        calls = self.raw_calls()
        self.assertEqual(len(calls), 2)  # check run and query run
        for c in calls:
            self.assertEqual(c["cmds"][:5], ["SET standard_conforming_strings = on",
                                             "SET statement_timeout = 7000", "SET lock_timeout = 2000",
                                             "SET idle_in_transaction_session_timeout = 7000",
                                             "SET default_transaction_read_only = on"])
            self.assertEqual(c["cmds"][5], "\\echo :HOST :PORT" if c is calls[0] else "BEGIN TRANSACTION READ ONLY")
            self.assertIn("default_transaction_read_only=on", c["env"]["PGOPTIONS"])

    def service(self, text):
        self.svcfile.write_bytes(text.encode("utf-8"))  # byte-exact, no newline translation

    def test_service_hostaddr_remote_refused_before_connecting(self):
        self.config(service="svc")
        self.service("[other]\nhostaddr=10.0.0.1\n\n[svc]\nhost=localhost\nhostaddr = 127.0.0.1, 203.0.113.7\n")
        text, err = self.call("query", sql="select 1")
        self.assertTrue(err)
        self.assertTrue(text.startswith("REMOTE: hostaddr 203.0.113.7"), text)
        self.assertEqual(self.raw_calls(), [])

    def test_service_remote_host_refused(self):
        self.config(service="svc")
        self.service("[svc]\nhost=db.example.com\n")
        text, err = self.call("query", sql="select 1")
        self.assertTrue(text.startswith("REMOTE: host db.example.com"), text)

    def test_service_hostaddr_loopback_ok(self):
        self.config(service="svc")
        self.service("[svc]\nhost=db.example.com\nhostaddr=127.0.0.1\n")  # libpq dials hostaddr only
        self.set_stub([["\\echo", "127.0.0.1 5432\nkind,detail\ninfo,appdb agent_ro\n"], ["FETCH", "a\n1\n"]])
        # host is remote in the file, so it is still refused: we are conservative on `host`
        text, err = self.call("query", sql="select 1")
        self.assertTrue(err)
        self.service("[svc]\nhostaddr=::1\nport=5433\n")
        text, err = self.call("query", sql="select 1")
        self.assertFalse(err, text)

    def test_service_hostaddr_allowed_with_allow_remote(self):
        self.config(service="svc", allow_remote=True)
        self.service("[svc]\nhostaddr=203.0.113.7\n")
        self.set_stub([["\\echo", "db.example.com 5432\nkind,detail\ninfo,appdb agent_ro\n"],
                       ["FETCH", "a\n1\n"]])
        text, err = self.call("query", sql="select 1")
        self.assertFalse(err, text)

    def problem(self, text, name="svc"):
        """service_problem() text for a service file body, or None when the service is proven local."""
        self.service(text)
        err = pg.service_problem(name)
        return None if err is None else str(err)

    def test_service_libpq_rules(self):
        self.assertIsNone(self.problem("[svc]\nhost=localhost\nhostaddr=127.0.0.1\n"))
        # a duplicate key: the first value wins
        self.assertIsNone(self.problem("[svc]\nhost=127.0.0.1\nhost=db.example.com\n"))
        self.assertIn("REMOTE: host db.example.com", self.problem("[svc]\nhost=db.example.com\nhost=127.0.0.1\n"))
        # an indented line is its own key
        self.assertIn("REMOTE: hostaddr 203.0.113.7", self.problem("[svc]\nhost=localhost\n   hostaddr=203.0.113.7\n"))
        # a duplicate section: only the first is used
        self.assertIsNone(self.problem("[svc]\nhost=localhost\n[svc]\nhost=db.example.com\n"))
        self.assertIn("REMOTE", self.problem("[svc]\nhost=db.example.com\n[svc]\nhost=localhost\n"))
        # a line before the first section is ignored (even a remote host), and so are comments
        self.assertIsNone(self.problem("host=db.example.com\n# hostaddr=10.0.0.1\n[svc]\nhost=localhost\n"))
        # a malformed line in another section is ignored; in the matched section it makes the service unknown
        self.assertIsNone(self.problem("[other]\nbroken line\n[svc]\nhost=localhost\n"))
        self.assertIn("NOT CONFIGURED", self.problem("[svc]\nhost=localhost\nbroken line\n"))
        # ldap: unknown
        self.assertIn("ldap", self.problem("[svc]\nldap://ldap.example.com/db\n"))
        self.assertIn("ldap", self.problem("[svc]\nhost=localhost\nldap=x\n"))
        # a comma list: every entry must be local; unix sockets are local
        self.assertIsNone(self.problem("[svc]\nhost=/var/run/postgresql,localhost\n"))
        self.assertIn("REMOTE: host db.example.com", self.problem("[svc]\nhost=localhost,db.example.com\n"))

    def test_service_header_is_a_prefix_match_like_libpq(self):
        self.assertIn("REMOTE: hostaddr 10.0.0.9", self.problem("[svc] # prod\nhostaddr=10.0.0.9\n[svc]\nhost=localhost\n"))
        self.assertIn("REMOTE: host db.example.com", self.problem("[svc]junk\nhost=db.example.com\n"))
        self.assertIn("was not found", self.problem("[svcx]\nhost=localhost\n"))
        self.assertIsNone(self.problem("[svc] # prod\nhost=localhost\n[svc]\nhost=db.example.com\n"))

    def test_service_error_never_quotes_file_content(self):
        text = self.problem("[svc]\nhost=localhost\npassword hunter2-secret\n")
        self.assertIn("NOT CONFIGURED", text)
        self.assertIn("line 3", text)
        self.assertNotIn("hunter2", text)
        text = self.problem("[svc]\nldap://user:hunter2-secret@ldap.example.com/x\n")
        self.assertIn("ldap", text)
        self.assertNotIn("hunter2", text)

    def checks(self):
        return sum(1 for c in self.raw_calls() if "\\echo :HOST :PORT" in c["cmds"])

    def test_service_edit_invalidates_role_check_cache(self):
        for allow_remote in (False, True):
            pg._CHECK_CACHE.clear()
            (self.bin / "calls.jsonl").unlink(missing_ok=True)
            self.config(service="svc", allow_remote=allow_remote)
            self.service("[svc]\nhost=localhost\nuser=agent_ro\n")
            self.set_stub([["FETCH", "a\n1\n"]])
            self.assertFalse(self.call("query", sql="select 1")[1])
            self.assertFalse(self.call("query", sql="select 1")[1])
            self.assertEqual(self.checks(), 1)  # unchanged file: cache hit
            self.service("[svc]\nhost=localhost\nuser=owner\nport=5433\n")  # same service, another role
            self.set_stub([["\\echo", "localhost 5433\nkind,detail\ninfo,appdb owner\nproblem,role is superuser\n"],
                           ["FETCH", "a\n1\n"]])
            text, err = self.call("query", sql="select 1")
            self.assertEqual(self.checks(), 2, allow_remote)
            self.assertTrue(err)
            self.assertTrue(text.startswith("NOT READ-ONLY:"), text)

    def test_other_service_file_forces_new_check(self):
        self.config(service="svc")
        self.set_stub([["FETCH", "a\n1\n"]])
        self.call("query", sql="select 1")
        other = self.root / "other.conf"
        other.write_bytes(b"[svc]\nhost=localhost\n")
        with mock.patch.dict(os.environ, {"PGSERVICEFILE": str(other)}):
            self.call("query", sql="select 1")
        self.assertEqual(self.checks(), 2)

    def test_cache_hit_label_matches_its_own_key(self):
        self.config(service="svc")
        self.service("[svc]\nhost=localhost\nuser=a\n")
        self.set_stub([["\\echo", "localhost 5432\nkind,detail\ninfo,appdb alice\n"], ["FETCH", "a\n1\n"]])
        self.assertIn("role=alice@", self.call("query", sql="select 1")[0])
        self.service("[svc]\nhost=localhost\nuser=b\n")
        self.set_stub([["\\echo", "localhost 5432\nkind,detail\ninfo,appdb bob\n"], ["FETCH", "a\n1\n"]])
        self.assertIn("role=bob@", self.call("query", sql="select 1")[0])

    def test_service_file_split_on_newline_only_like_libpq(self):
        # \x1c is not a line break for libpq: `[z]` is part of the value and the section goes on
        self.assertIn("REMOTE: hostaddr 10.0.0.9",
                      self.problem("[svc]\nhost=localhost\napplication_name=x\x1c[z]\nhostaddr=10.0.0.9\n"))
        # a bare \r is not a line break for libpq either (fgets); the file must not be read with universal newlines
        self.assertIn("REMOTE: hostaddr 10.0.0.9",
                      self.problem("[svc]\nhost=localhost\n# note\r[z]\nhostaddr=10.0.0.9\n"))
        for ch in ("\r", "\x0b", "\x0c", "\x1d", "\x1e", "\x85", " ", " "):
            self.assertIn("REMOTE: hostaddr 10.0.0.9",
                          self.problem(f"[svc]\nhost=localhost\napplication_name=x{ch}y\nhostaddr=10.0.0.9\n"), repr(ch))
        # CRLF files still parse: the trailing \r is stripped, so the header and values match
        self.assertIsNone(self.problem("[svc]\r\nhost=localhost\r\n[other]\r\nhost=db.example.com\r\n"))
        self.assertIn("REMOTE: host db.example.com", self.problem("[svc]\r\nhost=db.example.com\r\n"))
        # a non-C whitespace character is part of the value, not stripped
        self.assertIn("REMOTE", self.problem("[svc]\nhost=localhost \n"))

    def test_service_not_found_or_unreadable_fails_closed(self):
        self.assertIn("was not found", self.problem("[other]\nhost=localhost\n"))
        self.svcfile.unlink()
        self.assertIn("was not found", str(pg.service_problem("svc")))
        self.svcfile.write_bytes(b"[svc]\nhost=\xff\xfe\n")  # not UTF-8
        self.assertIn("cannot read the service file", str(pg.service_problem("svc")))
        self.config(service="svc")
        self.set_stub([["FETCH", "a\n1\n"]])
        text, err = self.call("query", sql="select 1")
        self.assertTrue(err)
        self.assertTrue(text.startswith("NOT CONFIGURED:"))
        self.assertEqual(self.raw_calls(), [])
        self.config(service="svc", allow_remote=True)  # allow_remote overrides the guard
        self.service("[other]\n")
        text, err = self.call("query", sql="select 1")
        self.assertFalse(err, text)

    def test_service_user_file_first_then_system_file_even_with_pgservicefile(self):
        (self.sysdir / "pg_service.conf").write_text("[svc]\nhostaddr=10.9.9.9\n[sysonly]\nhost=localhost\n",
                                                     encoding="utf-8")
        self.assertIsNone(self.problem("[svc]\nhost=localhost\n"))  # PGSERVICEFILE has it: it wins
        self.assertIn("REMOTE: hostaddr 10.9.9.9", self.problem("[x]\n"))  # not there: the system file is used
        self.assertIsNone(self.problem("[x]\n", "sysonly"))
        home = self.root / "home"
        home.mkdir()
        (home / ".pg_service.conf").write_text("[svc]\nhostaddr=127.0.0.1\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"HOME": str(home)}):
            os.environ.pop("PGSERVICEFILE")
            self.assertIsNone(pg.service_problem("svc"))  # ~/.pg_service.conf comes first

    def test_service_system_file_location_from_pg_config_or_unknown(self):
        (self.sysdir / "pg_service.conf").write_text("[svc]\nhost=localhost\n", encoding="utf-8")
        self.svcfile.write_text("[x]\n", encoding="utf-8")
        stub = self.root / "pgc" / "pg_config"
        stub.parent.mkdir()
        stub.write_text(f"#!/bin/sh\necho {self.sysdir}\n", encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        with mock.patch.dict(os.environ, {"PATH": f"{stub.parent}{os.pathsep}{os.environ['PATH']}"}):
            os.environ.pop("PGSYSCONFDIR")
            self.assertEqual(pg.system_service_file(), self.sysdir / "pg_service.conf")
            self.assertIsNone(pg.service_problem("svc"))
        # no PGSYSCONFDIR and no pg_config: the system file is unknown, so a service missing from the user file
        # cannot be proven local
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}), \
                mock.patch.object(pg, "PG_CONFIG_PATHS", ()):
            os.environ.pop("PGSYSCONFDIR")
            self.assertIsNone(pg.system_service_file())
            self.assertIn("location is unknown", str(pg.service_problem("svc")))
            self.svcfile.write_text("[svc]\nhost=localhost\n", encoding="utf-8")
            self.assertIsNone(pg.service_problem("svc"))  # found in the user file: no need for the system file


class LexerTests(unittest.TestCase):
    def ok(self, sql, expect=None, first=None):
        lx = pg.lex(sql)
        if expect is not None:
            self.assertEqual(lx.sql, expect)
        if first is not None:
            self.assertEqual(lx.first, first)

    def bad(self, sql):
        with self.assertRaises(pg.ToolError) as cm:
            pg.lex(sql)
        self.assertTrue(str(cm.exception).startswith("REJECTED:"))

    def test_accepts(self):
        self.ok("SELECT 1", "SELECT 1", "select")
        self.ok("select 1;", "select 1")
        self.ok("select 1;  -- trailing\n /* c */ ", "select 1")
        self.ok("select ';'", "select ';'")
        self.ok("select $$a;b$$", first="select")
        self.ok("select $t$a;$$b$t$", first="select")
        self.ok("select 'it''s;'", first="select")
        self.ok("select \"a;b\"", first="select")
        self.ok("select /* a /* nested ; */ ; */ 1", first="select")
        self.ok("select E'\\';'", first="select")
        self.ok("select 1 -- ; \\ ", first="select")
        self.ok("  (select 1) union (select 2)", first="select")
        self.ok("with a as (select 1) select * from a", first="with")
        self.ok("select $1", first="select")
        self.ok("select a$b$ from t", first="select")

    def test_rejects(self):
        self.bad("select 1; select 2")
        self.bad("select 1; ;")
        self.bad("select 1; commit")
        self.bad("select 1;drop table t")
        self.bad("\\! touch x")
        self.bad("  \\dt")
        self.bad("select 'abc")
        self.bad("select \"abc")
        self.bad("select $$abc")
        self.bad("select /* abc")
        self.bad("select E'\\'; drop table t")
        self.bad("")
        self.bad("   ")
        self.bad(";")
        self.bad("-- only a comment")
        self.bad("select 1\x00")
        self.bad(None)

    def test_select_like(self):
        for sql in ("select 1", "WITH a AS (select 1) select 1", "values (1)", "table t", "(select 1)"):
            pg.require_select_like(pg.lex(sql), "query")
        for sql in ("update t set a = 1", "delete from t", "insert into t values (1)", "drop table t",
                    "explain select 1", "show all"):
            with self.assertRaises(pg.ToolError):
                pg.require_select_like(pg.lex(sql), "query")


class ToolTests(Base):
    def test_query_commands_and_output(self):
        self.config(service="svc")
        self.set_stub([["FETCH", "id,name\n1,a\n2,b\n"]])
        text, err = self.call("query", sql="select id, name from t;")
        self.assertFalse(err, text)
        run = self.calls()[1]["cmds"]
        self.assertEqual(run[0], "BEGIN TRANSACTION READ ONLY")
        self.assertEqual(run[1], "DECLARE agent_q NO SCROLL CURSOR FOR select id, name from t")
        self.assertEqual(run[2], "FETCH FORWARD 101 FROM agent_q")
        self.assertEqual(run[3], "ROLLBACK")
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith("-- db=appdb role=agent_ro@localhost:5432 rows=2 columns=2 "
                                            "truncated=no ms="))
        self.assertEqual(lines[1], pg.DATA_LINE)
        self.assertEqual(lines[2:], ["id,name", "1,a", "2,b"])

    def test_query_row_truncation(self):
        self.config(service="svc", max_rows=2)
        self.set_stub([["FETCH", "a\n1\n2\n3\n"]])
        text, _ = self.call("query", sql="select a from t")
        self.assertIn("FETCH FORWARD 3", " ".join(self.calls()[1]["cmds"]))
        self.assertIn("rows=2", text)
        self.assertIn("truncated=rows(max_rows=2)", text)
        self.assertNotIn("\n3", text)

    def test_max_rows_argument_validated(self):
        self.config(service="svc")
        for bad in (0, 1001, "5", True):
            _, err = self.call("query", sql="select 1", max_rows=bad)
            self.assertTrue(err, bad)

    def test_cell_and_byte_truncation(self):
        self.config(service="svc")
        self.set_stub([["FETCH", "a\n" + "x" * 900 + "\n"]])
        text, _ = self.call("query", sql="select a from t")
        self.assertIn("cells(>500 chars)", text)
        self.assertNotIn("x" * 501, text)
        rows = "".join(f"{'y' * 400}{i}\n" for i in range(200))
        self.set_stub([["FETCH", "a\n" + rows]])
        text, _ = self.call("query", sql="select a from t", max_rows=1000)
        self.assertIn("bytes", text.splitlines()[0])
        self.assertLessEqual(len(text.encode()), pg.TEXT_CAP + 400)
        self.assertIn("output cut at 32 KB", text)

    def test_query_rejects_non_select_and_multiple(self):
        self.config(service="svc")
        for sql in ("update t set a=1", "select 1; select 2", "\\dt", "select 'x"):
            text, err = self.call("query", sql=sql)
            self.assertTrue(err)
            self.assertTrue(text.startswith("REJECTED:"), text)
        self.assertEqual(self.calls(), [])

    def test_sql_error_and_timeout(self):
        self.config(service="svc")
        self.set_stub([["FETCH", ""]], exit=3, stderr="ERROR:  relation \"x\" does not exist\n")
        # check run itself fails here; point of the test is the prefix mapping
        text, err = self.call("query", sql="select * from x")
        self.assertTrue(text.startswith("SQL ERROR:"))
        self.set_stub(exit=3, stderr="ERROR:  canceling statement due to statement timeout\n")
        text, _ = self.call("query", sql="select 1")
        self.assertTrue(text.startswith("TIMEOUT:"))

    def test_explain_plain_and_analyze(self):
        self.config(service="svc")
        self.set_stub([["EXPLAIN", "QUERY PLAN\nSeq Scan on t  (cost=0.00..1.00)\n  Filter: (a = 1)\n"]])
        text, err = self.call("explain", sql="select * from t where a = 1")
        self.assertFalse(err, text)
        self.assertEqual(self.calls()[1]["cmds"][1], "EXPLAIN (FORMAT TEXT) select * from t where a = 1")
        self.assertIn("Seq Scan on t", text)
        self.assertIn("  Filter: (a = 1)", text)
        self.call("explain", sql="select 1", analyze=True)
        self.assertEqual(self.calls()[-1]["cmds"][1], "EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) select 1")
        n = len(self.calls())
        text, err = self.call("explain", sql="update t set a = 1", analyze=True)
        self.assertTrue(err)
        self.assertTrue(text.startswith("REJECTED:"))
        self.assertEqual(len(self.calls()), n)
        _, err = self.call("explain", sql="update t set a = 1")  # plain explain of a write is allowed to try
        self.assertFalse(err)

    def test_schema_list_and_detail(self):
        self.config(service="svc")
        self.set_stub([["AS est_rows", "schema,name,kind,est_rows\npublic,users,table,10\n"]])
        text, err = self.call("schema", schema="public")
        self.assertFalse(err, text)
        self.assertIn("n.nspname = 'public'", " ".join(self.calls()[1]["cmds"]))
        self.assertIn("public,users,table,10", text)
        self.set_stub([["c.relname = 'users'", "nspname,relname,oid,relkind\npublic,users,16384,r\n"],
                       ["a.attrelid", "sec,ord,c1,c2,c3,c4\n1,1,id,integer,NO,\n1,2,email,text,YES,\n"
                                      "2,0,users_pkey,PRIMARY KEY (id),,\n3,0,users_pkey,CREATE UNIQUE INDEX x,,\n"]])
        text, err = self.call("schema", table="public.users")
        self.assertFalse(err, text)
        self.assertIn("== public.users (r)", text)
        self.assertIn("name,type,nullable,default", text)
        self.assertIn("id,integer,NO,", text)
        self.assertIn("constraint users_pkey: PRIMARY KEY (id)", text)
        self.assertIn("index users_pkey: CREATE UNIQUE INDEX x", text)

    def test_schema_rejects_odd_identifiers(self):
        self.config(service="svc")
        for kw in ({"table": "t'; drop table x; --"}, {"schema": "a b"}, {"table": "a.b", "schema": "c"},
                    {"table": 5}):
            _, err = self.call("schema", **kw)
            self.assertTrue(err, kw)
        self.assertEqual(self.calls(), [])

    def test_schema_unknown_table(self):
        self.config(service="svc")
        self.set_stub([["c.relname = 'nope'", "nspname,relname,oid,relkind\n"]])
        text, err = self.call("schema", table="nope")
        self.assertTrue(err)
        self.assertIn("no table or view", text)


class ProtocolTests(unittest.TestCase):
    def rpc(self, method, params=None, rid=1):
        return pg.handle_message({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})

    def test_initialize(self):
        r = self.rpc("initialize", {"protocolVersion": "2025-03-26"})["result"]
        self.assertEqual(r["protocolVersion"], "2025-03-26")
        self.assertEqual(r["capabilities"], {"tools": {}})
        self.assertEqual(r["serverInfo"], {"name": "postgres", "version": "1.0.0"})
        self.assertEqual(r["instructions"], pg.INSTRUCTIONS)
        self.assertEqual(self.rpc("initialize", {"protocolVersion": "1999"})["result"]["protocolVersion"],
                         pg.PROTOCOL_VERSIONS[0])

    def test_tools_list(self):
        tools = self.rpc("tools/list")["result"]["tools"]
        self.assertEqual([t["name"] for t in tools], ["schema", "query", "explain"])
        for t in tools:
            self.assertEqual(t["annotations"], {"readOnlyHint": True})
            self.assertIn("project_path", t["inputSchema"]["required"])

    def test_budget(self):
        self.assertLessEqual(len(pg.INSTRUCTIONS), 400)
        for t in pg.TOOLS:
            self.assertLessEqual(len(t["description"]), 200, t["name"])
        self.assertLessEqual(len(json.dumps(pg.TOOLS, separators=(",", ":"))), 2500)

    def test_no_skills_or_resources_methods(self):
        for method in ("skills/list", "skills/get", "resources/list", "resources/read"):
            self.assertEqual(self.rpc(method)["error"]["code"], -32601)
        caps = self.rpc("initialize")["result"]["capabilities"]
        self.assertEqual(set(caps), {"tools"})

    def test_install_doc_holds_the_role_sql(self):
        doc = (SERVER.parent.parent.parent / "INSTALL.md").read_text(encoding="utf-8")
        indented = "\n".join(f"   {line}" if line else "" for line in pg.ROLE_SETUP_SQL.splitlines())
        self.assertIn(indented, doc)

    def test_ping_unknown_tool_notification(self):
        self.assertEqual(self.rpc("ping")["result"], {})
        self.assertEqual(self.rpc("tools/call", {"name": "status"})["error"]["code"], -32602)
        self.assertIsNone(pg.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_missing_project_path(self):
        r = self.rpc("tools/call", {"name": "query", "arguments": {"sql": "select 1"}})["result"]
        self.assertTrue(r["isError"])
        self.assertIn("project_path", r["content"][0]["text"])

    def test_serve_loop(self):
        import io
        out = io.StringIO()
        pg.serve(io.StringIO('{"jsonrpc":"2.0","id":1,"method":"ping"}\nnot json\n'), out)
        lines = [json.loads(x) for x in out.getvalue().splitlines()]
        self.assertEqual(lines[0]["result"], {})
        self.assertEqual(lines[1]["error"]["code"], -32700)


ADMIN_URL = os.environ.get("POSTGRES_MCP_TEST_ADMIN_URL")


def with_user(url: str, user: str, password: str, database: str | None = None) -> str:
    p = urlsplit(url)
    host = p.hostname or "localhost"
    netloc = f"{user}:{password}@{host}" + (f":{p.port}" if p.port else "")
    return urlunsplit((p.scheme, netloc, "/" + database if database else p.path, p.query, ""))


@unittest.skipUnless(ADMIN_URL and subprocess.run(["which", "psql"], capture_output=True).returncode == 0,
                     "set POSTGRES_MCP_TEST_ADMIN_URL (superuser URL) and install psql to run these")
class IntegrationTests(unittest.TestCase):
    """Roles and a scratch database are created per class and dropped afterwards."""

    @classmethod
    def admin(cls, sql, url=None):
        r = subprocess.run(["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-At", url or ADMIN_URL, "-c", sql],
                           capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        if r.returncode:
            raise RuntimeError(r.stderr)
        return r.stdout

    @classmethod
    def setUpClass(cls):
        sfx = uuid.uuid4().hex[:8]
        cls.db, cls.pw = f"mcp_test_{sfx}", "pw-" + sfx
        cls.roles = {n: f"mcp_{n}_{sfx}" for n in ("ro", "super", "owner", "writer", "member", "creator",
                                                   "colwriter", "dbowner")}
        cls.admin(f"CREATE DATABASE {cls.db}")
        cls.db_url = with_user(ADMIN_URL, urlsplit(ADMIN_URL).username, urlsplit(ADMIN_URL).password or "",
                               cls.db)
        cls.admin("REVOKE CREATE ON SCHEMA public FROM PUBLIC", cls.db_url)
        r = cls.roles
        for n, name in r.items():
            attrs = "SUPERUSER" if n == "super" else ""
            cls.admin(f"CREATE ROLE {name} LOGIN {attrs} PASSWORD '{cls.pw}'")
        cls.admin(f"GRANT CONNECT ON DATABASE {cls.db} TO {r['ro']}, {r['owner']}, {r['writer']}, "
                  f"{r['member']}, {r['creator']}, {r['colwriter']}, {r['dbowner']}")
        cls.admin(f"ALTER DATABASE {cls.db} OWNER TO {r['dbowner']}")
        cls.admin(f"CREATE TABLE t(a int, b text); INSERT INTO t VALUES (1,'x'),(2,'y'),(3,'z'); "
                  f"GRANT USAGE ON SCHEMA public TO {r['ro']}, {r['writer']}, {r['member']}, {r['creator']}, "
                  f"{r['colwriter']}; "
                  f"GRANT SELECT ON t TO {r['ro']}, {r['member']}, {r['creator']}, {r['colwriter']}; "
                  f"GRANT UPDATE (b) ON t TO {r['colwriter']}; "
                  f"GRANT SELECT, INSERT ON t TO {r['writer']}; "
                  f"ALTER SCHEMA public OWNER TO {r['super']}; "
                  f"GRANT CREATE ON SCHEMA public TO {r['creator']}; "
                  f"CREATE TABLE owned(a int); ALTER TABLE owned OWNER TO {r['owner']}; "
                  f"GRANT {r['writer']} TO {r['member']}", cls.db_url)
        try:
            cls.admin(f"GRANT pg_read_all_data TO {r['ro']}", cls.db_url)
            cls.has_read_all = True
        except RuntimeError:
            cls.has_read_all = False

    @classmethod
    def tearDownClass(cls):
        cls.admin(f"DROP DATABASE IF EXISTS {cls.db} WITH (FORCE)")
        for name in cls.roles.values():
            cls.admin(f"DROP ROLE IF EXISTS {name}")

    def setUp(self):
        pg._CHECK_CACHE.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.proj = Path(os.path.realpath(self.tmp.name))
        (self.proj / ".agents").mkdir()
        self.addCleanup(pg._CHECK_CACHE.clear)

    def as_role(self, key, **cfg):
        url = with_user(ADMIN_URL, self.roles[key], self.pw, self.db)
        (self.proj / ".env").write_text(f"DBURL={url}\n", encoding="utf-8")
        (self.proj / ".agents" / pg.CONFIG_FILE).write_text(json.dumps({"url_env": "DBURL", **cfg}),
                                                                        encoding="utf-8")  # no allow_remote: the
        # test server must be local, so a wrong REMOTE verdict fails the suite
        pg._CHECK_CACHE.clear()

    def call(self, name, **args):
        resp = pg.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                  "params": {"name": name, "arguments": {"project_path": str(self.proj), **args}}})
        res = resp["result"]
        return res["content"][0]["text"], res["isError"]

    def test_unsafe_roles_refused(self):
        for key, needle in (("super", "superuser"), ("owner", "owns"), ("writer", "can write"),
                            ("member", "member of"), ("creator", "CREATE on schema"),
                            ("colwriter", "can write"), ("dbowner", "owns the database")):
            self.as_role(key)
            text, err = self.call("query", sql="select 1")
            self.assertTrue(err, key)
            self.assertTrue(text.startswith("NOT READ-ONLY:"), (key, text))
            self.assertIn(needle, text, key)

    def test_default_public_create_refused(self):
        """PostgreSQL 14 and older give PUBLIC CREATE on public; setUpClass revoked it, so grant it back."""
        self.admin("GRANT CREATE ON SCHEMA public TO PUBLIC", self.db_url)
        try:
            self.as_role("ro")
            text, err = self.call("query", sql="select 1")
            self.assertTrue(err)
            self.assertTrue(text.startswith("NOT READ-ONLY:"), text)
            self.assertIn("CREATE on schema", text)
        finally:
            self.admin("REVOKE CREATE ON SCHEMA public FROM PUBLIC", self.db_url)

    def test_readonly_role_accepted(self):
        self.as_role("ro")
        text, err = self.call("query", sql="select a, b from t order by a")
        self.assertFalse(err, text)
        self.assertIn("1,x", text)
        text, err = self.call("query", sql="select a from t order by a", max_rows=2)
        self.assertIn("truncated=rows(max_rows=2)", text)
        text, err = self.call("schema")
        self.assertIn("public,t,table", text)
        text, err = self.call("schema", table="t")
        self.assertIn("a,integer,YES", text)
        text, err = self.call("explain", sql="select * from t", analyze=True)
        self.assertFalse(err, text)
        self.assertIn("Seq Scan", text)

    def test_writes_fail_and_change_nothing(self):
        self.as_role("ro")
        attempts = ("with d as (delete from t returning a) select * from d",
                    "select 1; commit; drop table t",
                    "select 1 \\! touch " + str(self.proj / "pwned"))
        for sql in attempts:
            _, err = self.call("query", sql=sql)
            self.assertTrue(err, sql)
        self.assertFalse((self.proj / "pwned").exists())
        text, _ = self.call("query", sql="select count(*) from t")
        self.assertIn("3", text.splitlines()[-1])

    def test_timeout_and_analyze_update_and_plain_explain_update(self):
        self.as_role("ro", timeout_ms=1000)
        text, err = self.call("query", sql="select pg_sleep(5)")
        self.assertTrue(err)
        self.assertTrue(text.startswith(("TIMEOUT:", "SQL ERROR:")), text)
        text, err = self.call("explain", sql="update t set a = 1", analyze=True)
        self.assertTrue(text.startswith("REJECTED:"))
        text, err = self.call("explain", sql="update t set a = 1")
        self.assertTrue(err)  # A4: no UPDATE privilege, so no plan


if __name__ == "__main__":
    unittest.main()
