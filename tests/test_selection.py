"""Selection tests: which skills, subagents and MCP servers get installed.

Everything runs with HOME, CODEX_HOME and XDG_* in a temp dir. The real home is never touched.
"""
import json
import shutil
import stat
import sys
import unittest
from pathlib import Path
from unittest import mock

import test_instructions_block as base

FAKE_CLAUDE = """#!{python}
import json, os, sys
path = os.path.join(os.environ["CLAUDE_CONFIG_DIR"], ".claude.json")
try:
    data = json.load(open(path))
except FileNotFoundError:
    data = {{}}
servers = data.setdefault("mcpServers", {{}})
args = sys.argv[1:]
if args[:2] == ["mcp", "add-json"]:
    servers[args[4]] = json.loads(args[5])
elif args[:2] == ["mcp", "remove"]:
    servers.pop(args[4], None)
elif args[:2] == ["mcp", "get"]:
    print("Status: connected")
json.dump(data, open(path, "w"))
"""

TARGETS = ("--targets", "codex,opencode")


class SelectionCase(base.TempHomeCase):
    def agents_dir(self):
        return Path(self.env["CODEX_HOME"]) / "agents"

    def skills_dir(self):
        return Path(self.env["HOME"]) / ".agents" / "skills"

    def config_file(self):
        return Path(self.env["XDG_CONFIG_HOME"]) / "agent-setup" / "config.json"

    def config(self):
        return json.loads(self.config_file().read_text())

    def codex_config(self):
        return (Path(self.env["CODEX_HOME"]) / "config.toml").read_text()

    def instructions(self):
        return (Path(self.env["CODEX_HOME"]) / "AGENTS.md").read_text()

    def ok(self, *args):
        r = self.run_cli(*args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def installed_skills(self):
        return sorted(p.name for p in self.skills_dir().iterdir()) if self.skills_dir().exists() else []

    def installed_agents(self):
        return sorted(p.stem for p in self.agents_dir().iterdir()) if self.agents_dir().exists() else []


class CoreTests(SelectionCase):
    def load(self):
        skills, agents, servers = self.m.load_skills(), self.m.load_agents(), self.m.load_mcp()
        return skills, agents, servers, self.m.catalog(skills, agents, servers)

    def test_requires_file_lists_the_skill_links(self):
        requires = self.m.load_requires()
        self.assertEqual(len(requires), 5)
        self.assertEqual(requires["skills/review-changes"], ["agents/code-reviewer", "agents/finding-verifier"])
        self.m.validate_requires(requires, self.load()[3])

    def test_catalog_leaves_out_optional_servers(self):
        self.config_file().parent.mkdir(parents=True)
        self.config_file().write_text(json.dumps({"trackers": ["linear"]}))
        _, _, servers, cat = self.load()
        self.assertIn("linear", [s["name"] for s in servers])
        self.assertNotIn("linear", cat["mcp"])

    def test_no_selection_means_everything_and_nothing_new(self):
        cat = self.load()[3]
        eff, notes = self.m.effective_selection({}, cat)
        self.assertEqual(eff, {k: set(v) for k, v in cat.items()})
        self.assertEqual(notes, [])
        self.assertEqual(self.m.new_items({}, cat), {"skills": [], "agents": [], "mcp": []})

    def test_closure_adds_required_agents_with_notes(self):
        cat = self.load()[3]
        cfg = {"selection": self.m.selection_maps(cat, {"skills/review-changes"})}
        eff, notes = self.m.effective_selection(cfg, cat)
        self.assertEqual(eff["skills"], {"review-changes"})
        self.assertEqual(eff["agents"], {"code-reviewer", "finding-verifier"})
        self.assertEqual(eff["mcp"], set())
        self.assertIn("also installs agents/code-reviewer (needed by skills/review-changes)", notes)
        self.assertTrue(cfg["selection"]["agents"]["code-reviewer"] is False)

    def test_unknown_names_in_the_config_are_ignored(self):
        cat = self.load()[3]
        cfg = {"selection": {"skills": {"gone": True}, "agents": {}, "mcp": {}}}
        eff, _ = self.m.effective_selection(cfg, cat)
        self.assertEqual(eff, {"skills": set(), "agents": set(), "mcp": set()})

    def test_new_items_are_those_the_choice_does_not_mention(self):
        cat = self.load()[3]
        maps = self.m.selection_maps(cat, set())
        del maps["skills"]["debug-ticket"]
        new = self.m.new_items({"selection": maps}, cat)
        self.assertEqual(new, {"skills": ["debug-ticket"], "agents": [], "mcp": []})

    def test_filter_keeps_optional_servers(self):
        self.config_file().parent.mkdir(parents=True)
        self.config_file().write_text(json.dumps({"trackers": ["linear"]}))
        skills, agents, servers, cat = self.load()
        eff = {"skills": set(), "agents": set(), "mcp": set()}
        _, _, kept = self.m.filter_sources(skills, agents, servers, eff)
        self.assertEqual([s["name"] for s in kept], ["linear"])

    def test_ambiguous_bare_name_errors(self):
        cat = {"skills": ["both", "only-skill"], "agents": ["both"], "mcp": []}
        with self.assertRaisesRegex(ValueError, "ambiguous name 'both'"):
            self.m.resolve_items(["both"], cat)
        self.assertEqual(self.m.resolve_items(["agents/both", "only-skill"], cat),
                         [("agents", "both"), ("skills", "only-skill")])
        with self.assertRaisesRegex(ValueError, "unknown item"):
            self.m.resolve_items(["nope"], cat)

    def test_validate_rejects_unknown_requires_names(self):
        bad = self.tmp / "requires.json"
        for content in ({"skills/review-changes": ["agents/nope"]}, {"skills/nope": ["agents/architect"]},
                        {"review-changes": ["agents/architect"]}):
            bad.write_text(json.dumps(content))
            self.m.REQUIRES_FILE = bad
            with self.assertRaisesRegex(ValueError, "requires.json: unknown item"):
                self.m.cmd_validate(None)

    def test_validate_cli_passes_on_the_repo(self):
        self.assertIn("ok:", self.ok("validate").stdout)


class SyncTests(SelectionCase):
    def test_no_selection_installs_everything_and_never_prompts(self):
        r = self.ok("sync", *TARGETS)
        self.assertNotIn("New items", r.stdout)
        self.assertNotIn("also installs", r.stdout)
        self.assertEqual(self.installed_skills(), sorted(n for n, _ in self.m.load_skills()))
        self.assertEqual(self.installed_agents(), sorted(a["name"] for a in self.m.load_agents()))
        self.assertIn("memory block", self.ok("sync", "--dry-run", *TARGETS).stdout)
        self.assertIn("agent-setup memory", self.instructions())
        self.assertIn("agent-setup devservers", self.instructions())
        self.assertFalse(self.config_file().exists())

    def test_only_installs_the_skill_and_its_agents(self):
        self.ok("select", "--only", "review-changes")
        r = self.ok("sync", *TARGETS)
        self.assertIn("also installs agents/code-reviewer (needed by skills/review-changes)", r.stdout)
        self.assertEqual(self.installed_skills(), ["review-changes"])
        self.assertEqual(self.installed_agents(), ["code-reviewer", "finding-verifier"])
        self.assertNotIn("memory", self.codex_config() if (Path(self.env["CODEX_HOME"]) / "config.toml").exists()
                         else "")
        self.assertFalse((Path(self.env["CODEX_HOME"]) / "AGENTS.md").exists())
        self.assertFalse(self.config()["selection"]["agents"]["code-reviewer"])

    def test_deselecting_removes_only_what_was_installed_for_it(self):
        self.ok("sync", *TARGETS)
        foreign = self.skills_dir() / "someone-elses-skill"
        foreign.mkdir()
        self.ok("select", "--skip", "record-feature,browser-recorder,codegraph")
        r = self.ok("sync", *TARGETS)
        self.assertIn("remove", r.stdout)
        self.assertNotIn("record-feature", self.installed_skills())
        self.assertNotIn("browser-recorder", self.installed_agents())
        self.assertIn("review-changes", self.installed_skills())
        self.assertIn("someone-elses-skill", self.installed_skills())
        self.assertNotIn("codegraph", self.codex_config())
        self.assertIn("memory", self.codex_config())
        opencode = json.loads((Path(self.env["XDG_CONFIG_HOME"]) / "opencode" / "opencode.json").read_text())
        self.assertNotIn("codegraph", opencode["mcp"]["servers"])
        self.assertIn("memory", opencode["mcp"]["servers"])

    def test_deselecting_memory_removes_only_the_memory_block(self):
        self.ok("sync", *TARGETS)
        before = self.instructions()
        self.assertIn("agent-setup memory", before)
        self.ok("select", "--skip", "memory")
        r = self.ok("sync", *TARGETS)
        after = self.instructions()
        self.assertIn("remove", r.stdout)
        self.assertNotIn("agent-setup memory", after)
        self.assertIn("agent-setup devservers", after)
        self.assertEqual(after, self.m.without_block(before, Path("x"), "memory"))

    def test_deselecting_every_server_removes_both_blocks(self):
        self.ok("sync", *TARGETS)
        self.ok("select", "--skip", "memory,devservers")
        self.ok("sync", *TARGETS)
        self.assertNotIn("agent-setup", self.instructions())

    def test_new_items_are_skipped_with_yes_and_without_a_tty(self):
        self.ok("select", "--only", "review-changes")
        cfg = self.config()
        del cfg["selection"]["skills"]["debug-ticket"]
        self.config_file().write_text(json.dumps(cfg))
        for extra in (("--yes",), ()):  # run_cli has no TTY, so both skip
            r = self.ok("sync", *extra, *TARGETS)
            self.assertIn("skipped   skills/debug-ticket", r.stdout)
            self.assertIn("select --add skills/debug-ticket", r.stdout)
            self.assertEqual(self.config(), cfg)
            self.assertNotIn("debug-ticket", self.installed_skills())

    def test_dry_run_lists_new_items_and_never_asks(self):
        self.ok("select", "--only", "review-changes")
        cfg = self.config()
        del cfg["selection"]["skills"]["debug-ticket"]
        self.config_file().write_text(json.dumps(cfg))
        r = self.ok("sync", "--dry-run", *TARGETS)
        self.assertIn("new (not selected)  skills/debug-ticket", r.stdout)
        self.assertEqual(self.config(), cfg)
        new = {"skills": ["debug-ticket"], "agents": [], "mcp": []}
        with mock.patch.object(self.m, "is_interactive", return_value=True), \
                mock.patch("builtins.input", side_effect=AssertionError("must not ask")):
            self.assertEqual(self.m.resolve_new_items(cfg, new, {}, dry=True, yes=False), cfg)

    def test_interactive_answers_are_recorded(self):
        cat = {"skills": ["a", "b"], "agents": [], "mcp": []}
        new = {"skills": ["a", "b"], "agents": [], "mcp": []}
        for answer, expect in (("y", (True, True)), ("", (False, False)), ("n", (False, False)),
                               ("2", (False, True)), ("skills/a", (True, False))):
            cfg = {"selection": {"skills": {}, "agents": {}, "mcp": {}}}
            with mock.patch.object(self.m, "is_interactive", return_value=True), \
                    mock.patch("builtins.input", return_value=answer):
                out = self.m.resolve_new_items(cfg, new, cat, dry=False, yes=False)
            self.assertEqual((out["selection"]["skills"]["a"], out["selection"]["skills"]["b"]), expect, answer)
            self.assertEqual(self.config()["selection"]["skills"], out["selection"]["skills"])

    def test_interactive_eof_records_nothing(self):
        cfg = {"selection": {"skills": {}, "agents": {}, "mcp": {}}}
        new = {"skills": ["a"], "agents": [], "mcp": []}
        with mock.patch.object(self.m, "is_interactive", return_value=True), \
                mock.patch("builtins.input", side_effect=EOFError):
            self.assertEqual(self.m.resolve_new_items(cfg, new, {}, dry=False, yes=False), cfg)
        self.assertFalse(self.config_file().exists())


class SelectCommandTests(SelectionCase):
    def maps(self):
        return self.config()["selection"]

    def test_only_and_skip_and_all(self):
        self.ok("select", "--only", "memory,architect")
        maps = self.maps()
        self.assertEqual([n for n, v in maps["mcp"].items() if v], ["memory"])
        self.assertEqual([n for n, v in maps["agents"].items() if v], ["architect"])
        self.assertFalse(any(maps["skills"].values()))
        self.ok("select", "--skip", "skills/debug-ticket")
        maps = self.maps()
        self.assertFalse(maps["skills"]["debug-ticket"])
        self.assertTrue(maps["skills"]["review-changes"])
        self.ok("select", "--all")
        self.assertTrue(all(all(v.values()) for v in self.maps().values()))

    def test_add_and_remove_change_the_saved_choice(self):
        self.ok("select", "--only", "memory")
        self.ok("select", "--add", "review-changes,devservers")
        maps = self.maps()
        self.assertTrue(maps["skills"]["review-changes"])
        self.assertTrue(maps["mcp"]["devservers"])
        self.ok("select", "--remove", "memory")
        self.assertFalse(self.maps()["mcp"]["memory"])
        self.assertTrue(self.maps()["mcp"]["devservers"])

    def test_remove_without_a_saved_choice_starts_from_everything(self):
        self.ok("select", "--remove", "record-feature")
        maps = self.maps()
        self.assertFalse(maps["skills"]["record-feature"])
        self.assertTrue(maps["skills"]["review-changes"])

    def test_bad_names_and_exclusive_flags_fail(self):
        r = self.run_cli("select", "--only", "nope")
        self.assertEqual(r.returncode, 1)
        self.assertIn("unknown item: nope", r.stderr)
        self.assertFalse(self.config_file().exists())
        self.assertEqual(self.run_cli("select", "--only", "memory", "--all").returncode, 2)

    def test_trackers_set_keeps_the_selection_and_select_keeps_trackers(self):
        self.ok("trackers", "--set", "github")
        self.ok("select", "--only", "memory")
        self.assertEqual(self.config()["trackers"], ["github"])
        self.ok("trackers", "--set", "linear")
        cfg = self.config()
        self.assertEqual(cfg["trackers"], ["linear"])
        self.assertTrue(cfg["selection"]["mcp"]["memory"])

    def test_show_current_choice(self):
        self.assertIn("No saved choice", self.ok("select").stdout)
        self.ok("select", "--only", "review-changes")
        out = self.ok("select").stdout
        self.assertIn("[x] skills/review-changes", out)
        self.assertIn("[+] agents/code-reviewer", out)
        self.assertIn("[ ] skills/debug-ticket", out)

    def test_ask_checklist_toggles_and_saves(self):
        cat = self.m.catalog(self.m.load_skills(), self.m.load_agents(), self.m.load_mcp())
        desc = {}
        answers = iter(["none", "skills/review-changes, memory", "bogus", ""])
        with mock.patch("builtins.input", side_effect=lambda _p: next(answers)):
            chosen = self.m.ask_selection({}, cat, desc, self.m.load_requires())
        self.assertEqual(chosen, {"skills/review-changes", "mcp/memory"})

    def test_ask_checklist_eof_keeps_the_saved_choice(self):
        cat = self.m.catalog(self.m.load_skills(), self.m.load_agents(), self.m.load_mcp())
        with mock.patch("builtins.input", side_effect=EOFError):
            self.assertIsNone(self.m.ask_selection({}, cat, {}, {}))
        r = self.run_cli("select", "--ask")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.config_file().exists())

    def test_checklist_numbers_follow_the_printed_order(self):
        cat = {"skills": ["s"], "agents": ["a"], "mcp": ["m"]}
        answers = iter(["none", "2", ""])
        with mock.patch("builtins.input", side_effect=lambda _p: next(answers)):
            chosen = self.m.ask_selection({}, cat, {}, {})
        self.assertEqual(chosen, {"agents/a"})


class DoctorStatusTests(SelectionCase):
    def setUp(self):
        super().setUp()
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        (self.bin / "git").symlink_to(shutil.which("git"))
        fake = self.bin / "claude"
        fake.write_text(FAKE_CLAUDE.format(python=sys.executable))
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)

    def test_doctor_is_clean_after_a_partial_sync(self):
        self.ok("select", "--only", "review-changes,memory")
        r = self.run_cli("sync", extra_env=None, path=str(self.bin))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.run_cli("doctor", path=str(self.bin))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("All good.", r.stdout)
        self.assertIn("info also installs agents/code-reviewer", r.stdout)
        self.assertNotIn("FIX", r.stdout)

    def test_doctor_flags_a_selected_item_that_is_not_installed(self):
        self.ok("select", "--only", "review-changes")
        self.run_cli("sync", path=str(self.bin))
        self.ok("select", "--add", "debug-ticket")
        r = self.run_cli("doctor", path=str(self.bin))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("skill debug-ticket not linked", r.stdout)

    def test_status_lists_unselected_items(self):
        self.ok("select", "--only", "review-changes")
        out = self.ok("status").stdout
        self.assertIn("not selected:", out)
        self.assertIn("skills/debug-ticket", out)
        self.assertIn("also installs agents/code-reviewer", out)
        self.assertIn("skills:    review-changes", out)


if __name__ == "__main__":
    unittest.main()
