"""Installer tests: managed instruction blocks, the {repo} setting and the doctor auto-memory check.

Everything runs with HOME, CODEX_HOME and XDG_* in a temp dir; the real home is never touched.
"""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BIN = REPO / "bin" / "agent-setup"


def load_installer():
    loader = importlib.machinery.SourceFileLoader("agent_setup_under_test", str(BIN))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class TempHomeCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.env = {
            "HOME": str(self.tmp / "home"),
            "CODEX_HOME": str(self.tmp / "home" / ".codex"),
            "XDG_CONFIG_HOME": str(self.tmp / "xdg-config"),
            "XDG_STATE_HOME": str(self.tmp / "xdg-state"),
            "XDG_DATA_HOME": str(self.tmp / "xdg-data"),
            "CLAUDE_CONFIG_DIR": str(self.tmp / "home"),
        }
        (self.tmp / "home").mkdir()
        self._saved = {k: os.environ.get(k) for k in [*self.env, "CLAUDE_CODE_DISABLE_AUTO_MEMORY",
                                                       "AGENT_MEMORY_DIR"]}
        os.environ.update(self.env)
        os.environ.pop("CLAUDE_CODE_DISABLE_AUTO_MEMORY", None)
        os.environ.pop("AGENT_MEMORY_DIR", None)
        self.m = load_installer()

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._tmp.cleanup()

    def run_cli(self, *args, extra_env=None, path=None):
        env = {**os.environ, **(extra_env or {})}
        if path is not None:
            env["PATH"] = path
        return subprocess.run([sys.executable, str(BIN), *args], capture_output=True, text=True, timeout=120,
                              env=env, stdin=subprocess.DEVNULL)


class BlockFunctionTests(TempHomeCase):
    def setUp(self):
        super().setUp()
        self.block = self.m.load_instruction_block()
        self.p = Path("x.md")

    def test_block_has_markers_and_source_text(self):
        self.assertTrue(self.block.startswith(self.m.INSTR_BEGIN))
        self.assertTrue(self.block.endswith(self.m.INSTR_END))
        self.assertIn("`search`", self.block)

    def test_insert_keeps_surrounding_text_exactly(self):
        text = "# Mine\r\nline  with trailing spaces  \n\n<!-- OTHER_START -->\nx\n<!-- OTHER_END -->\n"
        out = self.m.with_block(text, self.block, self.p)
        self.assertTrue(out.startswith(text))
        self.assertEqual(self.m.without_block(out, self.p), text)

    def test_replace_in_place_changes_only_the_block(self):
        text = "before\n\n" + self.block + "\n\nafter\n"
        out = self.m.with_block(text, "NEW".join([self.m.INSTR_BEGIN + "\n", "\n" + self.m.INSTR_END]), self.p)
        self.assertTrue(out.startswith("before\n\n"))
        self.assertTrue(out.endswith("\n\nafter\n"))
        self.assertIn("NEW", out)
        self.assertNotIn("`search`", out)

    def test_idempotent(self):
        once = self.m.with_block("a\n", self.block, self.p)
        self.assertEqual(self.m.with_block(once, self.block, self.p), once)

    def test_empty_file(self):
        out = self.m.with_block("", self.block, self.p)
        self.assertEqual(out, self.block + "\n")
        self.assertEqual(self.m.without_block(out, self.p), "")

    def test_unbalanced_markers_rejected(self):
        for bad in (self.m.INSTR_BEGIN + "\nx", self.m.INSTR_END + "\n" + self.m.INSTR_BEGIN):
            with self.assertRaises(ValueError):
                self.m.with_block(bad, self.block, self.p)


class SyncInstructionTests(TempHomeCase):
    def files(self):
        return self.m.instruction_files()

    def test_sync_creates_inserts_and_second_run_is_ok(self):
        codex, opencode = self.files()["codex"], self.files()["opencode"]
        codex.parent.mkdir(parents=True)
        codex.write_text("my codex notes\n")
        r = self.run_cli("sync", "--targets", "codex,opencode")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(codex.read_text().startswith("my codex notes\n"))
        self.assertIn(self.m.INSTR_BEGIN, codex.read_text())
        self.assertEqual(opencode.read_text().count(self.m.INSTR_BEGIN), 1)  # created
        self.assertFalse(self.files()["claude"].exists())  # --targets respected
        manifest = json.loads(self.m.state_file().read_text())
        self.assertEqual(sorted(manifest["instructions"]), sorted([str(codex), str(opencode)]))
        again = self.run_cli("sync", "--targets", "codex,opencode")
        self.assertIn(f"ok        {codex}", again.stdout)
        self.assertIn(f"ok        {opencode}", again.stdout)
        self.assertNotIn("update", again.stdout.split("Instruction blocks")[1])

    def test_dry_run_writes_nothing(self):
        r = self.run_cli("sync", "--dry-run", "--targets", "codex,opencode")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("create", r.stdout)
        self.assertFalse(self.files()["codex"].exists())
        self.assertFalse(self.files()["opencode"].exists())
        self.assertFalse(self.m.state_file().exists())

    def test_changed_source_replaces_block(self):
        codex = self.files()["codex"]
        codex.parent.mkdir(parents=True)
        codex.write_text("top\n\n" + self.m.INSTR_BEGIN + "\nstale text\n" + self.m.INSTR_END + "\n\nbottom\n")
        r = self.run_cli("sync", "--targets", "codex")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        text = codex.read_text()
        self.assertNotIn("stale text", text)
        self.assertTrue(text.startswith("top\n\n" + self.m.INSTR_BEGIN))
        # the devservers block is appended after the user's text; the memory block's neighbours are untouched
        self.assertIn(self.m.INSTR_END + "\n\nbottom\n", text)

    def test_uninstall_removes_only_the_block(self):
        codex = self.files()["codex"]
        codex.parent.mkdir(parents=True)
        codex.write_text("keep me\n")
        self.run_cli("sync", "--targets", "codex")
        self.assertIn(self.m.INSTR_BEGIN, codex.read_text())
        r = self.run_cli("uninstall")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(codex.read_text(), "keep me\n")
        self.assertEqual(json.loads(self.m.state_file().read_text())["instructions"], [])

    def test_uninstall_dry_run_keeps_block(self):
        self.run_cli("sync", "--targets", "codex")
        codex = self.files()["codex"]
        self.run_cli("uninstall", "--dry-run")
        self.assertIn(self.m.INSTR_BEGIN, codex.read_text())

    def test_targets_not_in_run_keep_manifest_entries(self):
        self.run_cli("sync", "--targets", "codex,opencode")
        self.run_cli("sync", "--targets", "codex")
        manifest = json.loads(self.m.state_file().read_text())
        self.assertIn(str(self.files()["opencode"]), manifest["instructions"])
        self.assertIn(self.m.INSTR_BEGIN, self.files()["opencode"].read_text())

    def test_unbalanced_markers_stop_sync_before_writing(self):
        codex = self.files()["codex"]
        codex.parent.mkdir(parents=True)
        codex.write_text(self.m.INSTR_BEGIN + "\nno end\n")
        r = self.run_cli("sync", "--targets", "codex,opencode")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.files()["opencode"].exists())


class TwoBlockTests(TempHomeCase):
    def test_memory_markers_and_block_are_byte_identical_to_before(self):
        self.assertEqual(self.m.INSTR_BEGIN,
                         "<!-- >>> agent-setup memory (managed; edit shared/memory-instructions.md) >>> -->")
        self.assertEqual(self.m.INSTR_END, "<!-- <<< agent-setup memory <<< -->")
        src = (REPO / "shared" / "memory-instructions.md").read_text(encoding="utf-8").strip()
        self.assertEqual(self.m.load_instruction_block(), f"{self.m.INSTR_BEGIN}\n{src}\n{self.m.INSTR_END}")

    def test_devservers_markers_are_derived_from_the_name(self):
        block = self.m.load_instruction_block("devservers")
        self.assertTrue(block.startswith(
            "<!-- >>> agent-setup devservers (managed; edit shared/devservers-instructions.md) >>> -->\n"))
        self.assertTrue(block.endswith("\n<!-- <<< agent-setup devservers <<< -->"))
        self.assertEqual(list(self.m.instruction_blocks()), ["memory", "devservers"])

    def test_sync_adds_both_blocks_then_is_ok_and_uninstall_removes_both(self):
        codex = self.m.instruction_files()["codex"]
        codex.parent.mkdir(parents=True)
        codex.write_text("my notes\n")
        r = self.run_cli("sync", "--targets", "codex")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        text = codex.read_text()
        self.assertTrue(text.startswith("my notes\n"))
        self.assertEqual(text.count(self.m.INSTR_BEGIN), 1)
        self.assertEqual(text.count(self.m.instr_begin("devservers")), 1)
        self.assertLess(text.index(self.m.INSTR_BEGIN), text.index(self.m.instr_begin("devservers")))
        self.assertIn("memory block", r.stdout)
        self.assertIn("devservers block", r.stdout)
        again = self.run_cli("sync", "--targets", "codex")
        self.assertIn(f"ok        {codex}  (devservers block)", again.stdout)
        self.assertEqual(codex.read_text(), text)
        manifest = json.loads(self.m.state_file().read_text())
        self.assertEqual(manifest["instructions"], [str(codex)])
        r = self.run_cli("uninstall")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(codex.read_text(), "my notes\n")

    def test_only_the_stale_block_is_updated(self):
        codex = self.m.instruction_files()["codex"]
        codex.parent.mkdir(parents=True)
        mem, dev = self.m.load_instruction_block("memory"), self.m.load_instruction_block("devservers")
        stale = f"{self.m.instr_begin('devservers')}\nold text\n{self.m.instr_end('devservers')}"
        codex.write_text(f"top\n\n{mem}\n\nmiddle\n\n{stale}\n\nbottom\n")
        r = self.run_cli("sync", "--targets", "codex")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(codex.read_text(), f"top\n\n{mem}\n\nmiddle\n\n{dev}\n\nbottom\n")
        self.assertIn(f"ok        {codex}  (memory block)", r.stdout)
        self.assertIn(f"update    {codex}  (devservers block)", r.stdout)

    def test_old_install_with_only_memory_block_gains_devservers(self):
        codex = self.m.instruction_files()["codex"]
        codex.parent.mkdir(parents=True)
        mem = self.m.load_instruction_block("memory")
        codex.write_text(f"{mem}\n")
        r = self.run_cli("sync", "--targets", "codex")
        self.assertIn(f"add       {codex}  (devservers block)", r.stdout)
        self.assertTrue(codex.read_text().startswith(f"{mem}\n"))

    def test_unbalanced_devservers_markers_stop_sync_before_writing(self):
        codex = self.m.instruction_files()["codex"]
        codex.parent.mkdir(parents=True)
        codex.write_text(self.m.instr_begin("devservers") + "\nno end\n")
        r = self.run_cli("sync", "--targets", "codex,opencode")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("devservers markers are unbalanced", r.stderr + r.stdout)
        self.assertFalse(self.m.instruction_files()["opencode"].exists())

    def test_dry_run_writes_nothing_and_status_lists_both(self):
        r = self.run_cli("sync", "--dry-run", "--targets", "codex")
        self.assertIn("(devservers block)", r.stdout)
        self.assertFalse(self.m.instruction_files()["codex"].exists())
        self.run_cli("sync", "--targets", "codex")
        status = self.run_cli("status").stdout
        self.assertIn("(memory block)", status)
        self.assertIn("(devservers block)", status)

    def test_doctor_flags_a_missing_devservers_block(self):
        codex = self.m.instruction_files()["codex"]
        codex.parent.mkdir(parents=True)
        codex.write_text(f"{self.m.load_instruction_block('memory')}\n")
        r = self.run_cli("doctor", path=str(Path(shutil.which("git")).parent))
        self.assertIn("devservers instructions missing or out of date for codex", r.stdout)
        self.assertNotIn("memory instructions missing or out of date for codex", r.stdout)


class RepoSettingTests(TempHomeCase):
    def test_devservers_declaration_and_codex_approvals(self):
        servers = {s["name"]: s["spec"] for s in self.m.load_mcp()}
        script = str(REPO / "mcp" / "servers" / "devservers.py")
        spec = servers["devservers"]
        self.assertEqual((spec["command"], spec["args"]), ("python3", [script]))
        self.assertEqual(self.m.mcp_claude(spec)["args"], [script])
        self.assertEqual(self.m.mcp_opencode(spec)["command"], ["python3", script])
        codex = self.m.mcp_codex(spec)
        self.assertEqual(codex["args"], [script])
        self.assertEqual(codex["tools"], {t: {"approval_mode": "approve"} for t in ("status", "logs", "wait_ready")})
        self.assertNotIn("default_tools_approval_mode", codex)
        toml = self.m.toml_inline(codex["tools"])
        self.assertIn('"status" = { "approval_mode" = "approve" }', toml)
        self.assertNotIn("start", toml)
        self.assertFalse({"env", "env_from", "headers", "bearer_token_env"}
                         & set(json.loads((REPO / "mcp" / "devservers.json").read_text())))

    def test_memory_declaration_filled_in_all_renderings(self):
        servers = {s["name"]: s["spec"] for s in self.m.load_mcp()}
        script = str(REPO / "mcp" / "servers" / "memory.py")
        self.assertEqual(servers["memory"]["command"], "python3")
        self.assertEqual(servers["memory"]["args"], [script])
        self.assertEqual(self.m.mcp_claude(servers["memory"])["args"], [script])
        self.assertEqual(self.m.mcp_codex(servers["memory"])["args"], [script])
        self.assertEqual(self.m.mcp_opencode(servers["memory"])["command"], ["python3", script])

    def test_no_secrets_keys_in_declaration(self):
        spec = json.loads((REPO / "mcp" / "memory.json").read_text())
        self.assertFalse({"env", "env_from", "headers", "bearer_token_env"} & set(spec))

    def test_repo_with_quote_is_escaped(self):
        fake = self.tmp / 'we"ird'
        (fake / "mcp").mkdir(parents=True)
        shutil.copy(REPO / "mcp" / "memory.json", fake / "mcp" / "memory.json")
        self.m.REPO, self.m.MCP_SRC = fake, fake / "mcp"
        self.m.TRACKERS_FILE = fake / "none.json"
        servers = self.m.load_mcp()
        self.assertEqual(servers[0]["spec"]["args"], [f"{fake}/mcp/servers/memory.py"])

    def test_repo_setting_reaches_optional_servers(self):
        opt = self.tmp / "mcp" / "optional"
        opt.mkdir(parents=True)
        (opt / "thing.json").write_text('{"command": "x", "args": ["{repo}/a", "{host}"]}')
        self.m.MCP_SRC = self.tmp / "mcp"
        got = self.m._read_mcp_file(opt / "thing.json", {"host": "h"})
        self.assertEqual(got["spec"]["args"], [f"{REPO}/a", "h"])


class DoctorTests(TempHomeCase):
    def settings(self, content):
        p = Path(self.env["HOME"]) / ".claude" / "settings.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    def test_auto_memory_check_states(self):
        self.assertFalse(self.m.claude_auto_memory_off()[0])
        self.settings('{"autoMemoryEnabled": true}')
        self.assertFalse(self.m.claude_auto_memory_off()[0])
        self.settings("not json")
        self.assertFalse(self.m.claude_auto_memory_off()[0])
        self.settings('{"autoMemoryEnabled": false}')
        self.assertTrue(self.m.claude_auto_memory_off()[0])
        os.environ["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "0"  # forces it on, outranks the key
        self.assertFalse(self.m.claude_auto_memory_off()[0])
        os.environ["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
        self.settings("{}")
        self.assertTrue(self.m.claude_auto_memory_off()[0])

    def test_doctor_reports_todo_then_ok(self):
        git = shutil.which("git")
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "git").symlink_to(git)  # a PATH without claude/codex/opencode
        (Path(self.env["HOME"]) / ".claude").mkdir(parents=True)
        r = self.run_cli("doctor", path=str(bin_dir))
        self.assertIn("todo Claude auto-memory", r.stdout, r.stdout + r.stderr)
        self.settings('{"autoMemoryEnabled": false}')
        r = self.run_cli("doctor", path=str(bin_dir))
        self.assertIn("ok   Claude auto-memory", r.stdout, r.stdout + r.stderr)

    def test_doctor_reports_devservers_state_dir(self):
        git_dir = str(Path(shutil.which("git")).parent)
        r = self.run_cli("doctor", extra_env={"DEVSERVERS_DIR": "/mnt/c/Users/x/ds"}, path=git_dir)
        self.assertIn("info devservers state: /mnt/c/Users/x/ds", r.stdout)
        self.assertIn("warn the devservers state is on a Windows drive", r.stdout)
        r = self.run_cli("doctor", path=git_dir)
        self.assertIn(f"info devservers state: {self.tmp / 'xdg-state' / 'devservers'}", r.stdout)
        self.assertNotIn("devservers state is on a Windows drive", r.stdout)

    def test_doctor_warns_on_mnt_store(self):
        r = self.run_cli("doctor", extra_env={"AGENT_MEMORY_DIR": "/mnt/c/Users/x/mem"},
                         path=str(Path(shutil.which("git")).parent))
        self.assertIn("warn the memory store is on a Windows drive", r.stdout)

    def test_sync_never_writes_claude_settings(self):
        self.settings('{"theme": "dark"}')
        p = Path(self.env["HOME"]) / ".claude" / "settings.json"
        before = p.read_bytes()
        self.run_cli("sync", "--targets", "codex,opencode")
        self.assertEqual(p.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
