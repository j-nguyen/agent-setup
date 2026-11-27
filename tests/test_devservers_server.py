"""Tests for mcp/servers/devservers.py. Standard library only.

Everything runs in a temp dir with DEVSERVERS_DIR and a throwaway git repo. Every process a test starts is
killed in tearDown, whatever the test did.
"""
import importlib.util
import json
import os
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

SERVER = Path(__file__).resolve().parent.parent / "mcp" / "servers" / "devservers.py"
spec = importlib.util.spec_from_file_location("devservers_server", SERVER)
dev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dev)

GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(cwd, *args):
    subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args], cwd=cwd, check=True,
                   capture_output=True, timeout=30, stdin=subprocess.DEVNULL, env={**os.environ, **GIT_ENV})


def py(code: str) -> str:
    return f"{shlex.quote(sys.executable)} -u -c {shlex.quote(code)}"


SLEEP = py("import time; time.sleep(120)")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until(fn, timeout=10.0, step=0.05):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = fn()
        if v:
            return v
        time.sleep(step)
    return fn()


class DevCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.state = self.tmp / "state"
        patcher = mock.patch.dict(os.environ, {"DEVSERVERS_DIR": str(self.state),
                                               "HOME": str(self.tmp / "home"), "XDG_STATE_HOME": str(self.tmp / "xs")})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.pgids: list[int] = []
        real_spawn = dev.spawn

        def tracking_spawn(*a, **kw):
            rec = real_spawn(*a, **kw)
            self.pgids.append(rec["pgid"])
            return rec
        dev.spawn = tracking_spawn
        self.addCleanup(setattr, dev, "spawn", real_spawn)
        self.addCleanup(self._kill_all)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "README").write_text("x\n")
        git(self.repo, "add", "README")
        git(self.repo, "commit", "-q", "-m", "init")

    def _kill_all(self):
        for pgid in self.pgids:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except OSError:
                pass
        for pid, proc in list(dev._CHILDREN.items()):
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
        dev._CHILDREN.clear()
        self._tmp.cleanup()

    # -- helpers ---------------------------------------------------------- #
    def add_worktree(self, name: str) -> Path:
        path = self.tmp / name
        git(self.repo, "worktree", "add", "-q", "-b", name, str(path))
        return path

    def write_config(self, cfg: dict, where: Path | None = None, local: bool = False, commit=False) -> Path:
        base = (where or self.repo) / ".agents"
        base.mkdir(exist_ok=True)
        f = base / (dev.LOCAL_FILE if local else dev.TEAM_FILE)
        f.write_text(json.dumps(cfg, indent=2))
        if commit:
            git(self.repo, "add", ".agents")
            git(self.repo, "commit", "-q", "-m", "config")
        return f

    def trust(self, path: Path | None = None) -> str:
        ctx = dev.resolve(str(path or self.repo))
        return dev.trust_record(ctx, dev.load_config(ctx))

    def call(self, tool: str, path: Path | None = None, **args):
        args.setdefault("project_path", str(path or self.repo))
        return dev.TOOL_FUNCS[tool](args)

    def jcall(self, tool: str, path: Path | None = None, **args) -> dict:
        return json.loads(self.call(tool, path, **args))

    def err(self, tool: str, path: Path | None = None, **args) -> str:
        with self.assertRaises(dev.ToolError) as cm:
            self.call(tool, path, **args)
        return str(cm.exception)

    def server_cfg(self, run=SLEEP, **extra) -> dict:
        return {"servers": {"dev": {"run": run, "default": True, **extra}}}

    def setup_trusted(self, cfg: dict, **kw) -> None:
        self.write_config(cfg, **kw)
        self.trust(kw.get("where"))

    def alive(self, pid: int) -> bool:
        child = dev._CHILDREN.get(pid)
        if child is not None:
            return child.poll() is None
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        try:  # a zombie still answers kill(0); read its state
            return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
        except OSError:
            return True


class ProtocolTests(DevCase):
    def test_tools_list_has_nine_tools_with_annotations(self):
        resp = dev.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = {t["name"]: t for t in resp["result"]["tools"]}
        self.assertEqual(set(tools), {"status", "start", "setup", "stop", "restart", "trust", "logs",
                                      "wait_ready", "configure"})
        for n in ("status", "logs", "wait_ready"):
            self.assertTrue(tools[n]["annotations"]["readOnlyHint"])
        for n in ("stop", "restart"):
            self.assertTrue(tools[n]["annotations"]["destructiveHint"])
        for n in ("start", "setup", "trust", "configure"):
            self.assertNotIn("readOnlyHint", tools[n].get("annotations", {}))

    def test_initialize_and_unknown_tool(self):
        resp = dev.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                   "params": {"protocolVersion": "2025-06-18"}})
        self.assertEqual(resp["result"]["serverInfo"]["name"], "devservers")
        self.assertIn("instructions", resp["result"])
        bad = dev.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "nope"}})
        self.assertEqual(bad["error"]["code"], -32602)

    def test_tool_error_becomes_is_error(self):
        resp = dev.handle_message({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                   "params": {"name": "stop", "arguments": {"project_path": str(self.repo),
                                                                              "name": "dev"}}})
        self.assertTrue(resp["result"]["isError"])

    def test_no_os_branches_and_no_imports_of_siblings(self):
        text = SERVER.read_text()
        self.assertNotIn("sys.platform", text)
        self.assertNotIn("platform.system", text)
        self.assertNotIn("import memory", text)
        self.assertNotIn("agent-setup import", text)


class ConfigTests(DevCase):
    def check(self, cfg):
        return dev.check_schema(cfg, "t")

    def test_valid_full_config(self):
        self.check({"setup": {"copy": [".env"], "install": "npm ci", "after_install": "x"},
                    "preflight": [{"run": "true", "in": "main", "hint": "h"}], "ports": {"PORT": 3000, "B": 3100},
                    "ports_from": {"env_file": ".env.yarn"}, "env": {"A": "b"}, "env_strip": ["X"],
                    "max_running": 3, "idle_timeout_minutes": 0,
                    "servers": {"dev": {"run": "x", "default": True, "stop_signal": "INT", "stop_timeout": 5,
                                        "ready": {"log": "Ready (?P<P>\\d+)", "port": "PORT", "timeout_sec": 5}}}})

    def test_strict_schema_rejects(self):
        bad = [{"nope": 1}, {"servers": {"Bad_Name": {"run": "x"}}}, {"servers": {"setup": {"run": "x"}}},
               {"servers": {"a": {}}}, {"servers": {"a": {"run": "x", "zz": 1}}},
               {"servers": {"a": {"run": "x", "stop_signal": "USR1"}}},
               {"servers": {"a": {"run": "x", "ready": {"log": "("}}}},
               {"ports": {"A": 3000, "B": 3010}}, {"ports": {"1A": 3000}}, {"ports": {"A": True}},
               {"setup": {"copy": "x"}}, {"setup": 5}, {"max_running": 0}, {"idle_timeout_minutes": -1},
               {"env": {"A": 1}}, {"preflight": [{"in": "main"}]}, {"preflight": [{"run": "x", "in": "elsewhere"}]},
               {"ports_from": {"env_file": "../x"}}, [], "x"]
        for cfg in bad:
            with self.subTest(cfg=cfg), self.assertRaises(dev.ToolError):
                self.check(cfg)

    def test_local_overrides_top_level_and_servers_merge_by_name(self):
        team = {"max_running": 3, "ports": {"PORT": 3000},
                "servers": {"a": {"run": "team-a", "default": True}, "b": {"run": "team-b"}}}
        local = {"max_running": 1, "servers": {"b": {"run": "local-b"}, "c": {"run": "local-c"}}}
        m = dev.merge_config(team, local)
        self.assertEqual(m["max_running"], 1)
        self.assertEqual(m["ports"], {"PORT": 3000})
        self.assertEqual({n: s["run"] for n, s in m["servers"].items()},
                         {"a": "team-a", "b": "local-b", "c": "local-c"})
        self.assertIsNone(dev.merge_config(None, None))

    def test_merged_needs_a_server_and_one_default(self):
        with self.assertRaises(dev.ToolError):
            dev.check_merged({"setup": {}})
        with self.assertRaises(dev.ToolError):
            dev.check_merged({"servers": {"a": {"run": "x", "default": True}, "b": {"run": "y", "default": True}}})

    def test_hash_changes_with_every_edit_and_ignores_key_order(self):
        base = {"servers": {"dev": {"run": "a"}}, "max_running": 1}
        h = dev.config_hash(base)
        self.assertEqual(h, dev.config_hash({"max_running": 1, "servers": {"dev": {"run": "a"}}}))
        for changed in ({"servers": {"dev": {"run": "b"}}, "max_running": 1},
                        {"servers": {"dev": {"run": "a"}}, "max_running": 2},
                        {"servers": {"dev": {"run": "a"}}, "max_running": 1, "env": {}}):
            self.assertNotEqual(h, dev.config_hash(changed))

    def test_invalid_json_file_is_a_tool_error(self):
        (self.repo / ".agents").mkdir()
        (self.repo / ".agents" / dev.TEAM_FILE).write_text("{not json")
        self.assertIn("cannot read", self.err("start"))


class TrustTests(DevCase):
    def test_untrusted_config_never_spawns(self):
        marker = self.tmp / "ran"
        self.write_config(self.server_cfg(run=f"touch {marker}; sleep 5"))
        msg = self.err("start")
        self.assertIn("not trusted", msg)
        self.assertIn(f"touch {marker}", msg)  # the commands are shown
        self.assertIn(dev.config_hash(dev.load_config(dev.resolve(str(self.repo)))), msg)
        time.sleep(0.2)
        self.assertFalse(marker.exists())
        self.assertEqual(self.pgids, [])
        self.assertIn("not trusted", self.err("setup"))
        self.assertIn("not trusted", self.err("restart"))

    def test_trust_with_current_hash_then_start_works_and_edit_untrusts(self):
        f = self.write_config(self.server_cfg())
        h = dev.config_hash(dev.load_config(dev.resolve(str(self.repo))))
        self.assertIn("Trusted", self.call("trust", hash=h))
        self.assertEqual(self.jcall("start")["result"], "started")
        self.jcall("stop")
        f.write_text(json.dumps(self.server_cfg(run=py("import time; time.sleep(121)"))))
        msg = self.err("start")
        self.assertIn("Changes since the trusted config", msg)
        self.assertIn("time.sleep(121)", msg)

    def test_stale_hash_is_rejected(self):
        f = self.write_config(self.server_cfg())
        old = dev.config_hash(dev.load_config(dev.resolve(str(self.repo))))
        f.write_text(json.dumps(self.server_cfg(run="echo changed")))
        self.assertIn("stale hash", self.err("trust", hash=old))
        self.assertIn("not trusted", self.err("start"))

    def test_trust_without_config_and_without_hash(self):
        self.assertIn("no devservers config", self.err("trust", hash="abc"))
        self.assertIn("hash is required", self.err("trust"))

    def test_cli_trust_refuses_without_terminal(self):
        self.write_config(self.server_cfg())
        r = subprocess.run([sys.executable, str(SERVER), "trust", str(self.repo)], capture_output=True, text=True,
                           timeout=30, stdin=subprocess.DEVNULL, env=os.environ.copy())
        self.assertEqual(r.returncode, 1)
        self.assertIn("without a terminal", r.stderr)
        self.assertIn("would run", r.stdout)
        self.assertFalse(dev.is_trusted(dev.resolve(str(self.repo)),
                                        dev.load_config(dev.resolve(str(self.repo)))))

    def test_cli_trust_with_yes_answer(self):
        self.write_config(self.server_cfg())
        ctx = dev.resolve(str(self.repo))
        with mock.patch.object(sys.stdin, "isatty", return_value=True), \
                mock.patch.object(sys.stdout, "isatty", return_value=True), \
                mock.patch("builtins.input", return_value="y"), mock.patch("builtins.print"):
            self.assertEqual(dev.cli_trust(str(self.repo)), 0)
        self.assertTrue(dev.is_trusted(ctx, dev.load_config(ctx)))

    def test_trust_is_shared_by_worktrees_of_the_project(self):
        self.write_config(self.server_cfg(), commit=True)
        wt = self.add_worktree("wt1")
        self.trust()
        self.assertEqual(self.jcall("start", wt)["result"], "started")


class ProposalTests(DevCase):
    def test_proposal_holds_literal_commands_and_executes_nothing(self):
        marker = self.tmp / "ran"
        (self.repo / "package.json").write_text(json.dumps(
            {"scripts": {"dev": f"touch {marker}", "dev:all": "x", "build": "y"}}))
        (self.repo / "package-lock.json").write_text("{}")
        (self.repo / ".env").write_text("A=1\n")
        msg = self.err("start")
        self.assertIn("no devservers config", msg)
        self.assertIn("npm run dev", msg)
        self.assertIn("npm run dev:all", msg)
        self.assertIn("npm ci", msg)
        self.assertNotIn("npm run build", msg)
        self.assertIn(".env", msg)
        time.sleep(0.2)
        self.assertFalse(marker.exists())
        self.assertEqual(self.pgids, [])
        self.assertFalse((self.repo / ".agents").exists())

    def test_nothing_detected_says_so(self):
        self.assertIn("Nothing to propose", self.err("start"))

    def test_proposal_is_valid_config(self):
        (self.repo / "manage.py").write_text("")
        (self.repo / "uv.lock").write_text("")
        cfg, _ = dev.build_proposal(dev.resolve(str(self.repo)))
        dev.check_merged(dev.check_schema(cfg, "p"))
        self.assertEqual(cfg["ports"], {"PORT": 8000})
        self.assertIn("runserver", cfg["servers"]["dev"]["run"])
        self.assertEqual(cfg["setup"]["install"], "uv sync")


class ConfigureTests(DevCase):
    def test_team_scope_writes_file_and_trusts(self):
        before = set(p.name for p in self.repo.iterdir())
        out = self.call("configure", config=self.server_cfg(), scope="team")
        self.assertIn("trusted", out)
        self.assertEqual(json.loads((self.repo / ".agents" / dev.TEAM_FILE).read_text()), self.server_cfg())
        self.assertEqual(set(p.name for p in self.repo.iterdir()) - before, {".agents"})
        self.assertEqual(sorted(p.name for p in (self.repo / ".agents").iterdir()), [dev.TEAM_FILE])
        self.assertEqual(self.jcall("start")["result"], "started")

    def test_local_scope_is_excluded_and_overrides(self):
        self.write_config({"servers": {"dev": {"run": "echo team", "default": True}}})
        self.call("configure", config={"servers": {"dev": {"run": SLEEP, "default": True}}}, scope="local")
        exclude = (self.repo / ".git" / "info" / "exclude").read_text().splitlines()
        self.assertIn(f".agents/{dev.LOCAL_FILE}", exclude)
        self.call("configure", config={"servers": {"dev": {"run": SLEEP, "default": True}}}, scope="local")
        self.assertEqual((self.repo / ".git" / "info" / "exclude").read_text().count(dev.LOCAL_FILE), 1)
        st = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo, capture_output=True, text=True).stdout
        self.assertNotIn(dev.LOCAL_FILE, st)
        self.assertEqual(self.jcall("start")["command"], SLEEP)  # the local file won

    def test_invalid_config_and_scope_write_nothing(self):
        self.assertIn("invalid config", self.err("configure", config={"bogus": 1}, scope="team"))
        self.assertIn("scope", self.err("configure", config=self.server_cfg(), scope="other"))
        self.assertFalse((self.repo / ".agents").exists())


class LifecycleTests(DevCase):
    def test_start_twice_returns_same_record(self):
        self.setup_trusted(self.server_cfg())
        a = self.jcall("start")
        b = self.jcall("start")
        self.assertEqual(a["result"], "started")
        self.assertEqual(b["result"], "already running")
        self.assertEqual((a["pid"], a["run_id"]), (b["pid"], b["run_id"]))

    def test_spawn_shape_new_session_devnull_stdin_merged_log_exit_marker(self):
        code = ("import os,sys; print('out'); print('err', file=sys.stderr); "
                "print('stdin is devnull', os.path.samestat(os.fstat(0), os.stat(os.devnull))); "
                "print('sid', os.getsid(0)==os.getpid() or os.getpgrp()==os.getppid()); sys.exit(3)")
        self.setup_trusted(self.server_cfg(run=py(code)))
        rec = self.jcall("start")
        self.assertEqual(os.getpgid(rec["pid"]) if self.alive(rec["pid"]) else rec["pid"], rec["pid"])
        st = wait_until(lambda: (lambda s: s if s["instances"][0]["state"] == "exited" else None)(
            self.jcall("status")))
        self.assertEqual(st["instances"][0]["last_exit"]["code"], 3)
        text = Path(rec["log"]).read_text()
        self.assertIn("out", text)
        self.assertIn("err", text)
        self.assertIn("stdin is devnull True", text)
        self.assertIn("[devservers] exited 3", text)

    def test_exit_marker_survives_exec(self):
        self.setup_trusted(self.server_cfg(run="exec true"))
        self.jcall("start")
        st = wait_until(lambda: (lambda s: s if s["instances"][0]["state"] == "exited" else None)(
            self.jcall("status")))
        self.assertEqual(st["instances"][0]["last_exit"]["code"], 0)

    def test_state_paths_and_modes(self):
        self.setup_trusted(self.server_cfg())
        rec = self.jcall("start")
        pdir = self.state / dev.slugify_path(str(self.repo))
        self.assertTrue((pdir / "instances").is_dir())
        self.assertTrue((pdir / "logs").is_dir())
        self.assertTrue((pdir / "trust.json").is_file())
        for d in (self.state, pdir, pdir / "instances", pdir / "logs"):
            self.assertEqual(d.stat().st_mode & 0o777, 0o700, d)
        self.assertEqual(Path(rec["log"]).stat().st_mode & 0o777, 0o600)

    def test_state_dir_resolution(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("DEVSERVERS_DIR")
            os.environ["XDG_STATE_HOME"] = "/x/state"
            self.assertEqual(dev.state_root(), Path("/x/state/devservers"))
            os.environ.pop("XDG_STATE_HOME")
            self.assertEqual(dev.state_root(), Path(os.environ["HOME"]) / ".local" / "state" / "devservers")

    def test_child_survives_server_exit_and_stop_from_another_process(self):
        self.setup_trusted(self.server_cfg())
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "start", "arguments": {"project_path": str(self.repo)}}}
        r = subprocess.run([sys.executable, str(SERVER)], input=json.dumps(msg) + "\n", capture_output=True,
                           text=True, timeout=60, env=os.environ.copy())
        self.assertEqual(r.returncode, 0, r.stderr)
        started = json.loads(json.loads(r.stdout.splitlines()[0])["result"]["content"][0]["text"])
        pid = started["pid"]
        self.pgids.append(pid)
        time.sleep(0.3)
        self.assertTrue(self.alive(pid), "child died with the server")
        st = self.jcall("status")["instances"][0]
        self.assertEqual((st["state"], st["pid"]), ("running", pid))
        self.assertIn("stopped", self.jcall("stop")["result"])
        self.assertTrue(wait_until(lambda: not self.alive(pid)))

    def test_stop_kills_grandchild_group(self):
        pidfile = self.tmp / "gc.pid"
        child = py(f"import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; "
                   f"time.sleep(120)']); open({str(pidfile)!r},'w').write(str(p.pid)); time.sleep(120)")
        self.setup_trusted(self.server_cfg(run=child))
        rec = self.jcall("start")
        gc = int(wait_until(lambda: pidfile.exists() and pidfile.read_text() or None))
        self.assertTrue(self.alive(gc))
        out = self.jcall("stop")
        self.assertEqual(out["state"], "exited")
        self.assertTrue(wait_until(lambda: not self.alive(gc)), "grandchild survived stop")
        self.assertFalse(self.alive(rec["pid"]))

    def test_stop_escalates_to_kill_and_says_so(self):
        stubborn = py("import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('up',flush=True); "
                      "time.sleep(120)")
        self.setup_trusted(self.server_cfg(run=stubborn, stop_timeout=1))
        rec = self.jcall("start")
        wait_until(lambda: "up" in Path(rec["log"]).read_text())
        t = time.monotonic()
        out = self.jcall("stop")
        self.assertGreaterEqual(time.monotonic() - t, 1.0)
        self.assertIn("sent KILL", out["result"])
        self.assertTrue(out["last_exit"]["killed"])
        self.assertFalse(self.alive(rec["pid"]))

    def test_stop_signal_int(self):
        code = ("import signal,sys,time\n"
                "def h(*a):\n print('got-int',flush=True); sys.exit(0)\n"
                "signal.signal(signal.SIGINT,h); print('up',flush=True); time.sleep(120)")
        self.setup_trusted(self.server_cfg(run=py(code), stop_signal="INT"))
        rec = self.jcall("start")
        wait_until(lambda: "up" in Path(rec["log"]).read_text())
        out = self.jcall("stop")
        self.assertIn("stopped with INT", out["result"])
        self.assertIn("got-int", Path(rec["log"]).read_text())

    def test_stop_unknown_and_already_stopped(self):
        self.setup_trusted(self.server_cfg())
        self.assertIn("no instance", self.err("stop"))
        self.jcall("start")
        self.jcall("stop")
        self.assertEqual(self.jcall("stop")["result"], "already stopped")

    def test_dead_process_is_reaped_not_a_zombie(self):
        self.setup_trusted(self.server_cfg(run="exit 0"))
        rec = self.jcall("start")
        st = wait_until(lambda: (lambda s: s if s["instances"][0]["state"] == "exited" else None)(
            self.jcall("status")))
        self.assertEqual(st["instances"][0]["pid"], rec["pid"])
        self.assertNotIn(rec["pid"], dev._CHILDREN)
        self.assertFalse(Path(f"/proc/{rec['pid']}").exists(), "left a zombie")

    def test_restart_changes_run_id_and_keeps_previous_log(self):
        self.setup_trusted(self.server_cfg())
        a = self.jcall("start")
        b = self.jcall("restart")
        self.assertEqual(b["result"], "restarted")
        self.assertNotEqual(a["run_id"], b["run_id"])
        self.assertNotEqual(a["pid"], b["pid"])
        self.assertTrue(Path(a["log"] + ".1").exists())
        self.assertFalse(self.alive(a["pid"]))

    def test_each_worktree_has_its_own_instance_and_log(self):
        self.write_config(self.server_cfg(), commit=True)
        wt = self.add_worktree("wt1")
        self.trust()
        a, b = self.jcall("start"), self.jcall("start", wt)
        self.assertNotEqual(a["pid"], b["pid"])
        self.assertNotEqual(a["log"], b["log"])
        self.assertEqual(len(self.jcall("status")["instances"]), 1)
        self.assertEqual(self.jcall("status", wt)["instances"][0]["worktree"], str(wt))
        everything = self.jcall("status", all_projects=True)
        self.assertEqual(len(everything["projects"]), 1)
        self.assertEqual(len(everything["projects"][0]["instances"]), 2)

    def test_deleted_worktree_record_dropped_and_slot_freed(self):
        self.write_config(self.server_cfg(), commit=True)
        wt = self.add_worktree("wt1")
        self.trust()
        self.jcall("start", wt)
        ctx_wt = dev.resolve(str(wt))
        self.assertEqual(json.loads((ctx_wt.pdir / "slots.json").read_text()), {str(wt): 1})
        git(self.repo, "worktree", "remove", "--force", str(wt))
        self.jcall("status")
        self.assertEqual(list((ctx_wt.pdir / "instances").glob("*.json")), [])
        self.assertEqual(json.loads((ctx_wt.pdir / "slots.json").read_text()), {})

    def test_max_running_counts_servers_across_worktrees(self):
        cfg = {"max_running": 1, "servers": {"a": {"run": SLEEP, "default": True}, "b": {"run": SLEEP}}}
        self.write_config(cfg, commit=True)
        wt = self.add_worktree("wt1")
        self.trust()
        self.jcall("start")
        msg = self.err("start", wt)
        self.assertIn("max_running is 1", msg)
        self.assertIn(str(self.repo), msg)
        self.assertIn("max_running", self.err("start", name="b"))
        self.jcall("stop")
        self.assertEqual(self.jcall("start", wt)["result"], "started")

    def test_idle_timeout_stops_untouched_instance_and_is_off_by_default(self):
        self.setup_trusted(self.server_cfg(), where=None)
        rec = self.jcall("start")
        ctx = dev.resolve(str(self.repo))
        path = dev.instance_path(ctx, "dev")
        data = json.loads(path.read_text())
        self.assertEqual(data["idle_minutes"], 0)
        data["last_touch"] = time.time() - 99999
        path.write_text(json.dumps(data))
        with dev.locked(ctx):
            pass
        self.assertTrue(self.alive(rec["pid"]), "idle must be off by default")
        self.jcall("stop")
        # on: 1 minute
        self.write_config(self.server_cfg(), where=None)
        cfg = self.server_cfg()
        cfg["idle_timeout_minutes"] = 1
        self.write_config(cfg)
        self.trust()
        rec = self.jcall("start")
        data = json.loads(path.read_text())
        data["last_touch"] = time.time() - 600
        path.write_text(json.dumps(data))
        with dev.locked(ctx):  # reap without touching
            pass
        self.assertTrue(wait_until(lambda: not self.alive(rec["pid"])))
        with dev.locked(ctx):
            pass
        self.assertEqual(self.jcall("status")["instances"][0]["state"], "exited")

    def test_status_touch_keeps_instance_from_idling(self):
        cfg = self.server_cfg()
        cfg["idle_timeout_minutes"] = 1
        self.setup_trusted(cfg)
        rec = self.jcall("start")
        ctx = dev.resolve(str(self.repo))
        path = dev.instance_path(ctx, "dev")
        data = json.loads(path.read_text())
        data["last_touch"] = time.time() - 600
        path.write_text(json.dumps(data))
        self.jcall("status")  # a tool call: touches it before it could idle
        with dev.locked(ctx):
            pass
        self.assertTrue(self.alive(rec["pid"]))

    def test_recycled_leader_pid_is_dead(self):
        self.setup_trusted(self.server_cfg())
        self.jcall("start")
        path = dev.instance_path(dev.resolve(str(self.repo)), "dev")
        data = json.loads(path.read_text())
        data["token"] = "Thu Jan  1 00:00:00 1970"
        path.write_text(json.dumps(data))
        if dev.start_token(data["pid"]) is None:
            self.skipTest("ps -o lstart= unavailable")
        self.assertEqual(self.jcall("status")["instances"][0]["state"], "exited")

    def test_unknown_server_name_and_required_name(self):
        cfg = {"servers": {"a": {"run": SLEEP}, "b": {"run": SLEEP}}}
        self.setup_trusted(cfg)
        self.assertIn("name is required", self.err("start"))
        self.assertIn("unknown server", self.err("start", name="zzz"))


class LockTests(DevCase):
    def test_dead_owner_is_taken_over(self):
        pdir = self.state / "p"
        (pdir / "lock").mkdir(parents=True)
        (pdir / "lock" / "owner").write_text("999999999 -\n")
        with dev.project_lock(pdir):
            self.assertEqual((pdir / "lock" / "owner").read_text().split()[0], str(os.getpid()))
        self.assertFalse((pdir / "lock").exists())
        self.assertEqual([p.name for p in pdir.iterdir()], [])

    def test_live_owner_blocks_then_times_out(self):
        pdir = self.state / "p"
        (pdir / "lock").mkdir(parents=True)
        (pdir / "lock" / "owner").write_text(f"{os.getpid()} -\n")
        with mock.patch.object(dev, "LOCK_WAIT", 0.3), self.assertRaises(dev.ToolError):
            with dev.project_lock(pdir):
                self.fail("must not get the lock")
        self.assertTrue((pdir / "lock").exists())

    def test_ownerless_fresh_lock_waits_old_one_is_stale(self):
        pdir = self.state / "p"
        (pdir / "lock").mkdir(parents=True)
        with mock.patch.object(dev, "LOCK_WAIT", 0.2), self.assertRaises(dev.ToolError):
            with dev.project_lock(pdir):
                pass
        old = time.time() - 60
        os.utime(pdir / "lock", (old, old))
        with dev.project_lock(pdir):
            pass

    def test_lock_is_not_held_while_a_command_runs(self):
        self.setup_trusted(self.server_cfg())
        self.jcall("start")
        ctx = dev.resolve(str(self.repo))
        self.assertFalse((ctx.pdir / "lock").exists())
        with dev.project_lock(ctx.pdir):  # another call can take it while the server runs
            pass

    def test_lock_released_when_body_raises(self):
        pdir = self.state / "p"
        with self.assertRaises(RuntimeError), dev.project_lock(pdir):
            raise RuntimeError("x")
        self.assertFalse((pdir / "lock").exists())


@unittest.skipIf(sys.platform == "win32", "open-file limits are Unix only")
class OpenFileLimitTests(unittest.TestCase):
    def setUp(self):
        import resource
        self.resource = resource
        self.saved = resource.getrlimit(resource.RLIMIT_NOFILE)
        self.addCleanup(resource.setrlimit, resource.RLIMIT_NOFILE, self.saved)

    def child_soft_limit(self) -> int:
        out = subprocess.run(["/bin/sh", "-c", "ulimit -n"], capture_output=True, text=True, check=True).stdout
        return int(out.strip())

    def test_a_launchd_default_is_raised_for_the_servers_we_start(self):
        r = self.resource
        hard = self.saved[1]
        r.setrlimit(r.RLIMIT_NOFILE, (256, hard))
        dev.raise_open_file_limit(4096)
        expected = 4096 if hard == r.RLIM_INFINITY else min(4096, hard)
        self.assertEqual(r.getrlimit(r.RLIMIT_NOFILE)[0], expected)
        self.assertEqual(self.child_soft_limit(), expected)

    def test_a_higher_limit_is_never_lowered(self):
        r = self.resource
        soft, hard = self.saved
        if soft == r.RLIM_INFINITY or soft < 512:
            self.skipTest("needs a finite soft limit of at least 512")
        dev.raise_open_file_limit(256)
        self.assertEqual(r.getrlimit(r.RLIMIT_NOFILE), (soft, hard))


class EnvTests(DevCase):
    def run_env(self, cfg: dict, path=None) -> dict:
        code = "import os,json; print('ENV=' + json.dumps(dict(os.environ)))"
        cfg["servers"] = {"dev": {"run": py(code), "default": True, **cfg.pop("server_extra", {})}}
        self.write_config(cfg, where=path)
        self.trust(path)
        rec = self.jcall("start", path)
        wait_until(lambda: "ENV=" in Path(rec["log"]).read_text())
        line = next(l for l in Path(rec["log"]).read_text().splitlines() if l.startswith("ENV="))
        return json.loads(line[4:])

    def test_other_worktrees_values_are_absent_and_slot_values_injected(self):
        port = free_port()
        with mock.patch.dict(os.environ, {"PORT": "1111", "VIRTUAL_ENV": "/other/venv", "BUNDLE_GEMFILE": "/o/G",
                                           "INIT_CWD": "/o", "npm_config_x": "y", "DEVSERVERS_STALE": "1",
                                           "COMPOSE_PROJECT_NAME": "other-wt9", "KEEP_ME": "yes",
                                           "FROM_FILE_PORT": "7777", "STRIPPED": "s", "CAPTURED_PORT": "5"}):
            cfg = {"ports": {"PORT": port}, "env": {"EXTRA": "1"}, "env_strip": ["STRIPPED"],
                   "ports_from": {"env_file": ".env.x"},
                   "server_extra": {"ready": {"log": "x (?P<CAPTURED_PORT>\\d+)"}}}
            (self.repo / ".env.x").write_text("FROM_FILE_PORT=7777\n")
            env = self.run_env(cfg)
        self.assertEqual(env["PORT"], str(port))  # base + slot 0
        for gone in ("VIRTUAL_ENV", "BUNDLE_GEMFILE", "INIT_CWD", "npm_config_x", "DEVSERVERS_STALE", "STRIPPED",
                     "FROM_FILE_PORT", "CAPTURED_PORT"):
            self.assertNotIn(gone, env)
        self.assertNotIn("COMPOSE_PROJECT_NAME", env)  # slot 0
        self.assertEqual(env["KEEP_ME"], "yes")
        self.assertEqual(env["EXTRA"], "1")
        self.assertEqual(env["DEVSERVERS_SLOT"], "0")
        self.assertEqual(env["DEVSERVERS_WORKTREE"], str(self.repo))

    def install_node(self, *versions: str) -> Path:
        root = self.tmp / "home" / ".nvm" / "versions" / "node"
        for v in versions:
            (root / v / "bin").mkdir(parents=True)
            (root / v / "bin" / "node").write_text("")
        return root

    def test_pinned_nvm_node_is_first_on_path(self):
        root = self.install_node("v22.1.0", "v24.22.1", "v24.22.2", "v24.23.0")
        (self.repo / ".nvmrc").write_text("24.22\n")
        with mock.patch.dict(os.environ, {"PATH": "/usr/bin:/bin"}):
            env = self.run_env({})
        self.assertEqual(env["PATH"], f"{root / 'v24.22.2' / 'bin'}:/usr/bin:/bin")

    def test_path_is_unchanged_without_a_matching_node(self):
        self.install_node("v22.1.0")
        (self.repo / ".nvmrc").write_text("v24\n")
        with mock.patch.dict(os.environ, {"PATH": "/usr/bin:/bin"}):
            env = self.run_env({})
        self.assertEqual(env["PATH"], "/usr/bin:/bin")

    def test_worktree_gets_slot_port_and_compose_name(self):
        port = free_port()
        self.write_config({"ports": {"PORT": port}, "servers": {"dev": {"run": "true", "default": True}}},
                          commit=True)
        wt = self.add_worktree("wt1")
        with mock.patch.dict(os.environ, {"PORT": "1111", "COMPOSE_PROJECT_NAME": "repo-wt7"}):
            env = self.run_env({"ports": {"PORT": port}}, path=wt)
        self.assertEqual(env["PORT"], str(port + 1))
        self.assertEqual(env["DEVSERVERS_SLOT"], "1")
        self.assertEqual(env["COMPOSE_PROJECT_NAME"], "repo-wt1")

    def test_ports_must_be_free_and_holder_is_named(self):
        port = free_port()
        cfg = self.server_cfg()
        cfg["ports"] = {"PORT": port}
        self.setup_trusted(cfg)
        with socket.socket() as s:
            s.bind(("127.0.0.1", port))
            s.listen()
            msg = self.err("start")
        self.assertIn(str(port), msg)
        self.assertIn("in use", msg)
        self.assertEqual(self.pgids, [])

    def test_busy_port_names_the_registered_instance(self):
        port = free_port()
        cfg = {"ports": {"PORT": port}, "max_running": 5,
               "servers": {"a": {"run": py("import os,socket,time; s=socket.socket(); "
                                           "s.bind(('127.0.0.1',int(os.environ['PORT']))); s.listen(); "
                                           "print('up',flush=True); time.sleep(120)"), "default": True},
                           "b": {"run": SLEEP}}}
        self.setup_trusted(cfg)
        rec = self.jcall("start", name="a")
        wait_until(lambda: "up" in Path(rec["log"]).read_text())
        msg = self.err("start", name="b")
        self.assertIn("a in", msg)
        self.assertIn(str(rec["pid"]), msg)

    def test_preflight_failure_stops_start_with_hint(self):
        cfg = self.server_cfg()
        cfg["preflight"] = [{"run": "echo nope >&2; exit 4", "hint": "start the database"}]
        self.setup_trusted(cfg)
        msg = self.err("start")
        self.assertIn("preflight failed", msg)
        self.assertIn("start the database", msg)
        self.assertIn("nope", msg)
        self.assertEqual(self.pgids, [])

    def test_preflight_in_main_runs_in_main_checkout(self):
        self.write_config({"preflight": [{"run": "pwd > pf.txt", "in": "main"}],
                           "servers": {"dev": {"run": SLEEP, "default": True}}}, commit=True)
        wt = self.add_worktree("wt1")
        self.trust()
        self.jcall("start", wt)
        self.assertEqual((self.repo / "pf.txt").read_text().strip(), str(self.repo))
        self.assertFalse((wt / "pf.txt").exists())


class LogsAndReadyTests(DevCase):
    def started(self, **server) -> dict:
        self.setup_trusted(self.server_cfg(**server))
        return self.jcall("start")

    def append(self, rec, text):
        with open(rec["log"], "ab") as f:
            f.write(text.encode())

    def logs(self, **kw):
        return dev.do_logs({"project_path": str(self.repo), **kw})

    def test_cursor_polls_return_only_new_lines(self):
        rec = self.started()
        self.append(rec, "one\ntwo\n")
        lines, cur, more = self.logs()
        self.assertEqual(lines, ["one", "two"])
        self.assertFalse(more)
        self.assertEqual(self.logs(since=cur)[0], [])
        self.append(rec, "three\nfour\n")
        lines2, cur2, _ = self.logs(since=cur)
        self.assertEqual(lines2, ["three", "four"])
        self.assertEqual(self.logs(since=cur2)[0], [])
        self.assertTrue(cur2.startswith(rec["run_id"] + ":"))

    def test_partial_line_waits_for_newline(self):
        rec = self.started()
        _, cur, _ = self.logs()
        self.append(rec, "half")
        self.assertEqual(self.logs(since=cur)[0], [])
        self.append(rec, "-done\n")
        self.assertEqual(self.logs(since=cur)[0], ["half-done"])

    def test_tail_without_since_and_max_lines(self):
        rec = self.started()
        self.append(rec, "".join(f"l{i}\n" for i in range(10)))
        lines, _, _ = self.logs(max_lines=3)
        self.assertEqual(lines, ["l7", "l8", "l9"])

    def test_cursor_with_overflow_continues_where_it_stopped(self):
        rec = self.started()
        _, cur, _ = self.logs()
        self.append(rec, "".join(f"l{i}\n" for i in range(5)))
        lines, cur2, more = self.logs(since=cur, max_lines=2)
        self.assertEqual((lines, more), (["l0", "l1"], True))
        lines, cur3, more = self.logs(since=cur2, max_lines=2)
        self.assertEqual((lines, more), (["l2", "l3"], True))
        self.assertEqual(self.logs(since=cur3, max_lines=2)[:1], (["l4"],))

    def test_max_lines_is_capped(self):
        rec = self.started()
        self.append(rec, "".join(f"l{i}\n" for i in range(dev.MAX_LINES + 50)))
        self.assertEqual(len(self.logs(max_lines=10 ** 6)[0]), dev.MAX_LINES)
        self.assertEqual(len(self.logs()[0]), dev.DEFAULT_LINES)
        with self.assertRaises(dev.ToolError):
            self.logs(max_lines=0)

    def test_grep_filters_and_cursor_still_advances(self):
        rec = self.started()
        _, cur, _ = self.logs()
        self.append(rec, "ok 1\nERROR a\nok 2\nERROR b\n")
        lines, cur2, _ = self.logs(since=cur, grep="ERROR")
        self.assertEqual(lines, ["ERROR a", "ERROR b"])
        self.assertEqual(self.logs(since=cur2)[0], [])
        self.assertEqual(self.logs(grep="ok")[0], ["ok 1", "ok 2"])
        with self.assertRaises(dev.ToolError):
            self.logs(grep="(")

    def test_ansi_is_stripped_in_output_only(self):
        rec = self.started()
        self.append(rec, "\x1b[31mred\x1b[0m text\nprogress 10%\rprogress 100%\n")
        lines, _, _ = self.logs()
        self.assertEqual(lines, ["red text", "progress 100%"])
        self.assertIn("\x1b[31m", Path(rec["log"]).read_text())

    def test_cursor_from_an_old_run_restarts_at_zero(self):
        rec = self.started()
        self.append(rec, "old\n")
        _, cur, _ = self.logs()
        self.jcall("restart")
        new = self.jcall("status")["instances"][0]
        self.append(new, "fresh\n")
        lines, cur2, _ = self.logs(since=cur)
        self.assertEqual(lines, ["fresh"])
        self.assertIn(new["run_id"], cur2)
        self.assertEqual(self.logs(since="garbage")[0], ["fresh"])

    def test_tool_logs_text_has_next_cursor(self):
        rec = self.started()
        self.append(rec, "hello\n")
        out = self.call("logs")
        self.assertIn("hello", out)
        self.assertRegex(out, r"next since=\w+:\d+")

    def test_logs_of_exited_instance_include_exit_marker(self):
        self.setup_trusted(self.server_cfg(run="echo bye; exit 5"))
        self.jcall("start")
        wait_until(lambda: self.jcall("status")["instances"][0]["state"] == "exited")
        lines, _, _ = self.logs()
        self.assertEqual(lines[-2:], ["bye", "[devservers] exited 5"])

    def test_wait_ready_by_log_regex_and_captured_port(self):
        code = "import time; print('Local:   http://localhost:54321/', flush=True); time.sleep(120)"
        self.started(run=py(code), ready={"log": r"Local:.*:(?P<VITE_PORT>\d+)"})
        out = self.jcall("wait_ready", timeout_sec=10)
        self.assertEqual(out["result"], "ready")
        self.assertEqual(out["ports"], {"VITE_PORT": 54321})
        self.assertEqual(self.jcall("status")["instances"][0]["ports"], {"VITE_PORT": 54321})

    def test_wait_ready_by_port(self):
        port = free_port()
        code = ("import os,socket,time; time.sleep(0.5); s=socket.socket(); "
                "s.bind(('127.0.0.1',int(os.environ['PORT']))); s.listen(); time.sleep(120)")
        cfg = {"ports": {"PORT": port}, "servers": {"dev": {"run": py(code), "default": True,
                                                              "ready": {"port": "PORT"}}}}
        self.setup_trusted(cfg)
        self.jcall("start")
        self.assertEqual(self.jcall("wait_ready", timeout_sec=15)["result"], "ready")

    def test_wait_ready_requires_every_loopback_http_probe(self):
        port = free_port()
        code = """
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health" and not Path("api-ready").exists():
            self.send_response(503)
        else:
            self.send_response(302 if self.path == "/" else 200)
            self.send_header("Location", "http://example.invalid/")
        self.end_headers()

HTTPServer(("127.0.0.1", int(os.environ["PORT"])), Handler).serve_forever()
"""
        probes = [{"port": "PORT", "path": "/"}, {"port": "PORT", "path": "/health"}]
        cfg = self.server_cfg(run=py(code), ready={"http": probes})
        cfg["ports"] = {"PORT": port}
        self.setup_trusted(cfg)
        self.jcall("start")
        self.assertEqual(self.jcall("wait_ready", timeout_sec=1)["result"], "waiting")
        (self.repo / "api-ready").touch()
        self.assertEqual(self.jcall("wait_ready", timeout_sec=3)["result"], "ready")

    def test_remote_http_probe_urls_are_rejected(self):
        for path in ("https://example.com/", "//example.com/", "/has space", "/\n"):
            cfg = self.server_cfg(ready={"http": [{"port": 3000, "path": path}]})
            with self.assertRaisesRegex(dev.ToolError, "local HTTP path"):
                dev.check_schema(cfg, "test")

    def test_wait_ready_waiting_then_exited_with_last_lines(self):
        self.started(ready={"log": "never appears"})
        out = self.jcall("wait_ready", timeout_sec=1)
        self.assertEqual(out["result"], "waiting")
        self.assertFalse(self.jcall("status")["instances"][0]["ready"])
        self.jcall("stop")
        self.setup_trusted(self.server_cfg(run="echo crash; exit 2", ready={"log": "x"}))
        self.jcall("start")
        out = self.jcall("wait_ready", timeout_sec=10)
        self.assertEqual(out["result"], "exited")
        self.assertEqual(out["last_exit"]["code"], 2)
        self.assertIn("crash", out["last_lines"])

    def test_wait_ready_without_ready_config_is_ready_when_running(self):
        self.started()
        self.assertEqual(self.jcall("wait_ready", timeout_sec=2)["result"], "ready")

    def test_wait_timeout_is_capped(self):
        self.assertEqual(dev._int_arg({"timeout_sec": 10 ** 6}, "timeout_sec", 60, 1, dev.MAX_WAIT), dev.MAX_WAIT)
        self.assertEqual(dev._int_arg({}, "timeout_sec", 60, 1, dev.MAX_WAIT), 60)

    def test_wait_ready_unknown_instance(self):
        self.setup_trusted(self.server_cfg())
        self.assertIn("no instance", self.err("wait_ready"))


class SetupTests(DevCase):
    def default_cfg(self, **setup) -> dict:
        return {"setup": setup, "ports": {"PORT": free_port()},
                "servers": {"dev": {"run": SLEEP, "default": True}}}

    def run_setup(self, path=None) -> dict:
        out = self.jcall("setup", path)
        done = self.jcall("wait_ready", path, task="setup", timeout_sec=30)
        return {**out, "done": done}

    def test_start_refuses_until_setup_and_names_next_calls(self):
        self.setup_trusted(self.default_cfg(install="true"))
        msg = self.err("start")
        self.assertIn("setup(", msg)
        self.assertIn("wait_ready(", msg)
        self.assertIn('task="setup"', msg)
        self.assertEqual(self.pgids, [])
        self.assertEqual(self.run_setup()["done"]["result"], "ready")
        self.assertEqual(self.jcall("start")["result"], "started")

    def test_two_worktrees_get_slots_1_and_2_and_env_files(self):
        (self.repo / ".env").write_text("SECRET=1\n")
        cfg = self.default_cfg(copy=[".env"], install="echo installed > installed.txt",
                               after_install="echo after >> installed.txt")
        self.write_config(cfg, commit=True)
        w1, w2 = self.add_worktree("wt1"), self.add_worktree("wt2")
        self.trust()
        for wt in (w1, w2):
            self.assertEqual(self.run_setup(wt)["done"]["result"], "ready")
        slots = json.loads((dev.resolve(str(w1)).pdir / "slots.json").read_text())
        self.assertEqual(slots, {str(w1): 1, str(w2): 2})
        for n, wt in ((1, w1), (2, w2)):
            self.assertEqual((wt / ".env").read_text(), "SECRET=1\n")
            self.assertEqual((wt / "installed.txt").read_text().split(), ["installed", "after"])
            env = (wt / dev.ENV_FILE).read_text().splitlines()
            self.assertIn(f"DEVSERVERS_SLOT={n}", env)
            self.assertIn(f"PORT={cfg['ports']['PORT'] + n}", env)
            self.assertIn(f"COMPOSE_PROJECT_NAME=repo-wt{n}", env)
        exclude = (self.repo / ".git" / "info" / "exclude").read_text()
        self.assertIn(dev.ENV_FILE, exclude)
        self.assertEqual(self.jcall("start", w1)["slot"], 1)
        self.assertEqual(self.jcall("start", w2)["slot"], 2)
        self.assertEqual(self.jcall("status", w2)["slot"], 2)

    def test_copy_never_overwrites_and_never_leaves_the_worktree(self):
        (self.repo / ".env").write_text("main\n")
        (self.repo / "outside.txt").write_text("secret\n")
        cfg = self.default_cfg(copy=[".env", "../x", "/etc/passwd", "missing", "sub/.env"])
        self.write_config(cfg, commit=True)
        wt = self.add_worktree("wt1")
        (wt / ".env").write_text("mine\n")
        self.trust()
        out = self.run_setup(wt)
        self.assertEqual((wt / ".env").read_text(), "mine\n")
        notes = "\n".join(out["notes"])
        self.assertIn("skip .env: already exists", notes)
        self.assertIn("skip ../x", notes)
        self.assertIn("skip /etc/passwd", notes)
        self.assertIn("skip missing", notes)
        self.assertFalse((self.tmp / "x").exists())

    def test_copy_follows_no_symlink_out_of_main(self):
        (self.tmp / "elsewhere").mkdir()
        (self.tmp / "elsewhere" / "k").write_text("k")
        (self.repo / "link").symlink_to(self.tmp / "elsewhere")
        cfg = self.default_cfg(copy=["link"])
        self.write_config(cfg, commit=True)
        wt = self.add_worktree("wt1")
        self.trust()
        out = self.run_setup(wt)
        self.assertIn("skip link: resolves outside", "\n".join(out["notes"]))
        self.assertFalse(os.path.lexists(wt / "link"))

    def test_copy_is_skipped_in_main_and_main_is_slot_zero(self):
        (self.repo / ".env").write_text("main\n")
        self.setup_trusted(self.default_cfg(copy=[".env"]))
        out = self.run_setup()
        self.assertIn("skip .env: this is the main checkout", "\n".join(out["notes"]))
        self.assertIn("DEVSERVERS_SLOT=0", (self.repo / dev.ENV_FILE).read_text())

    def test_empty_setup_object_completes_without_a_task(self):
        self.setup_trusted(self.default_cfg())
        out = self.jcall("setup")
        self.assertIn("nothing to run", out["result"])
        self.assertEqual(self.jcall("start")["result"], "started")

    def test_delegated_setup_string_runs_as_task(self):
        cfg = {"setup": "echo hi > delegated.txt", "servers": {"dev": {"run": SLEEP, "default": True}}}
        self.setup_trusted(cfg)
        out = self.run_setup()
        self.assertEqual(out["done"]["result"], "ready")
        self.assertEqual((self.repo / "delegated.txt").read_text().strip(), "hi")
        self.assertFalse((self.repo / dev.ENV_FILE).exists())  # delegated: the project owns its files
        self.assertEqual(self.jcall("start")["result"], "started")

    def test_failed_setup_leaves_no_marker(self):
        self.setup_trusted(self.default_cfg(install="echo boom; exit 1"))
        out = self.run_setup()
        self.assertEqual(out["done"]["result"], "exited")
        self.assertEqual(out["done"]["last_exit"]["code"], 1)
        self.assertIn("boom", "\n".join(out["done"]["last_lines"]))
        self.assertIn("setup(", self.err("start"))

    def test_setup_logs_are_readable_as_a_task(self):
        self.setup_trusted(self.default_cfg(install="echo installing-now"))
        self.run_setup()
        lines, _, _ = dev.do_logs({"project_path": str(self.repo), "task": "setup"})
        self.assertIn("installing-now", lines)

    def test_changed_lockfile_or_config_makes_setup_stale(self):
        cfg = self.default_cfg(install="true")
        f = self.write_config(cfg)
        self.trust()
        self.run_setup()
        self.jcall("start")
        self.jcall("stop")
        (self.repo / "package-lock.json").write_text("{}")
        self.assertIn("lockfile changed", self.err("start"))
        self.run_setup()
        self.assertEqual(self.jcall("start")["result"], "started")
        self.jcall("stop")
        cfg["setup"]["install"] = "true # changed"
        f.write_text(json.dumps(cfg))
        self.trust()
        self.assertIn("config changed", self.err("start"))

    def test_config_without_setup_starts_directly(self):
        self.setup_trusted(self.server_cfg())
        self.assertIn("no `setup`", self.call("setup"))
        self.assertEqual(self.jcall("start")["result"], "started")

    def test_start_can_run_required_setup_once(self):
        cfg = self.default_cfg(install="echo ran >> setup-count")
        self.write_config(cfg)
        self.assertIn("not trusted", self.err("start", setup_if_needed=True))
        self.assertFalse((self.repo / "setup-count").exists())
        self.trust()
        self.assertIn("has not been set up", self.err("start"))
        self.assertEqual(self.jcall("start", setup_if_needed=True)["result"], "started")
        self.assertEqual(self.jcall("start", setup_if_needed=True)["result"], "already running")
        self.assertEqual((self.repo / "setup-count").read_text(), "ran\n")

    def test_start_stops_after_failed_setup(self):
        self.setup_trusted(self.default_cfg(install="echo setup-failed; exit 3"))
        out = self.jcall("start", setup_if_needed=True)
        self.assertEqual((out["phase"], out["result"], out["last_exit"]["code"]), ("setup", "exited", 3))
        self.assertIn("setup-failed", out["last_lines"])
        self.assertEqual([r["name"] for r in self.jcall("status")["instances"]], ["setup"])

    def test_start_reports_pending_setup_and_can_resume(self):
        self.setup_trusted(self.default_cfg(install="echo ran >> setup-count; sleep 3"))
        out = self.jcall("start", setup_if_needed=True, setup_timeout_sec=1)
        self.assertEqual((out["phase"], out["result"]), ("setup", "waiting"))
        self.assertEqual(self.jcall("start", setup_if_needed=True)["result"], "started")
        self.assertEqual((self.repo / "setup-count").read_text(), "ran\n")

    def test_worktree_inherits_only_opted_in_main_config(self):
        wt = self.add_worktree("feature")
        cfg = self.server_cfg()
        self.write_config(cfg, local=True)
        self.assertIsNone(dev.load_config(dev.resolve(str(wt))))
        cfg["inherit_worktrees"] = True
        self.write_config(cfg, local=True)
        self.assertEqual(dev.load_config(dev.resolve(str(wt))), cfg)
        self.assertIn("not trusted", self.err("start", wt))
        self.trust()
        self.assertEqual(self.jcall("start", wt)["worktree"], str(wt))
        own = self.server_cfg(run="echo separate")
        self.write_config(own, where=wt, local=True)
        self.assertEqual(dev.load_config(dev.resolve(str(wt))), own)

    def test_setup_twice_while_running_returns_the_task(self):
        self.setup_trusted(self.default_cfg(install="sleep 3"))
        a = self.jcall("setup")
        b = self.jcall("setup")
        self.assertEqual(b["result"], "setup already running")
        self.assertEqual(a["pid"], b["pid"])
        self.jcall("wait_ready", task="setup", timeout_sec=20)

    def test_ports_from_env_file_ports_are_checked(self):
        port = free_port()
        (self.repo / ".env.yarn").write_text(f"WEB_PORT={port}\nOTHER=1\n")
        cfg = {"ports_from": {"env_file": ".env.yarn"}, "servers": {"dev": {"run": SLEEP, "default": True}}}
        self.setup_trusted(cfg)
        with socket.socket() as s:
            s.bind(("127.0.0.1", port))
            s.listen()
            self.assertIn(str(port), self.err("start"))
        out = self.jcall("start")
        self.assertEqual(out["ports"], {"WEB_PORT": port})

    def test_named_app_ports_exclude_shared_services_and_need_values_in_worktrees(self):
        port = free_port()
        wt = self.add_worktree("feature")
        cfg = self.server_cfg()
        cfg["ports_from"] = {"env_file": ".env.yarn", "keys": ["PORT"], "main": {"PORT": port}}
        cfg["servers"]["dev"]["port_keys"] = ["PORT"]
        self.write_config(cfg, where=wt)
        self.trust(wt)
        self.assertIn("missing port values for PORT", self.err("start", wt))
        with socket.socket() as db:
            db.bind(("127.0.0.1", 0))
            db.listen()
            (wt / ".env.yarn").write_text(f"PORT={port}\nDB_PORT={db.getsockname()[1]}\n")
            self.assertEqual(self.jcall("start", wt)["ports"], {"PORT": port})
        self.assertEqual(dev.file_ports(dev.resolve(str(self.repo)), cfg), {"PORT": port})


if __name__ == "__main__":
    unittest.main()
