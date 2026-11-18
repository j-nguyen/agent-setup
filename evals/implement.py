#!/usr/bin/env python3
"""Implement-plan evals: does the implement-plan skill build an accepted plan, on the cheaper
`implementer` subagent, without over-engineering it? Standard library only.

For every (case, agent, trial) with `"kind": "implement"` in its expected.json:
  1. Build a throwaway git repo from case/before (which holds the accepted plan).
  2. Ask the agent CLI, in natural language, to implement the plan.
  3. Grade with deterministic checks, no judge:
     - tests: the project's tests plus case/hidden/* (added after the run) pass;
     - scope: every changed file matches `allowed_paths`; the plan file is untouched;
     - size: added lines <= `max_added_lines`;
     - over-engineering: no added line matches a `forbidden_added` pattern;
     - no commits; the skill was used; it delegated to `implementer`; which models ran.

    python3 evals/implement.py                       # claude + codex, 1 trial
    python3 evals/implement.py --agents claude --trials 3
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("eval_run", HERE / "run.py")
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

STAMP = "Implemented by the implementer subagent."
DELEGATION_RE = re.compile(
    r'\\*"(?:subagent_type|agent_type|agent|role|subagent)\\*"\s*:\s*\\*"implementer\\*"')
PROMPT = """{request}

I won't be around to answer questions, so make reasonable assumptions instead of asking, and note them."""
CLAUDE_TOOLS = base.CLAUDE_TOOLS + " Edit Write Bash"


def agent_cmd(agent: str, prompt: str, repo: Path, out_dir: Path, model: str | None) -> list[str]:
    if agent == "claude":
        cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
               "--no-session-persistence", "--allowedTools", CLAUDE_TOOLS]
        return cmd + (["--model", model] if model else [])
    if agent == "codex":  # not --ephemeral: Codex can't spawn subagents in an ephemeral session
        cmd = ["codex", "exec", "--json", "--sandbox", "workspace-write", "--skip-git-repo-check",
               "-C", str(repo), "-o", str(out_dir / "report.md"), prompt]
        return cmd[:2] + (["-m", model] if model else []) + cmd[2:]
    if agent == "opencode":
        cmd = ["opencode", "run", "--standalone", "--format", "json", "--auto", "--archived",
               "--title", f"eval-{out_dir.name}", prompt]
        return cmd[:2] + (["-m", model] if model else []) + cmd[2:]
    raise ValueError(agent)


def models_used(agent: str, raw: str, since: float) -> dict:
    """Which models answered, split into the main thread and subagents (best effort)."""
    main, sub = set(), set()
    if agent == "claude":
        for line in raw.splitlines():
            try:
                e = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            m = (e.get("message") or {}).get("model") if e.get("type") == "assistant" else None
            if m:
                (sub if e.get("parent_tool_use_id") else main).add(m)
    elif agent == "codex":
        tid = next((json.loads(l).get("thread_id") for l in raw.splitlines()
                    if '"thread.started"' in l), None)
        root = Path.home() / ".codex" / "sessions"
        for f in root.rglob("rollout-*.jsonl") if tid and root.exists() else []:
            if f.stat().st_mtime < since:
                continue
            lines = f.read_text(errors="replace").splitlines()
            try:
                meta = json.loads(lines[0]).get("payload", {})
            except (IndexError, json.JSONDecodeError):
                continue
            is_child, is_main = meta.get("parent_thread_id") == tid, meta.get("id") == tid
            if not (is_child or is_main):
                continue
            # Each turn_context names the model for the turn that follows. A child session
            # starts with a copy of the parent's context (the parent's model), then switches
            # to its own role's model, so for a child the last one is the model that worked.
            turns = []
            for line in lines:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("type") == "turn_context" and (e.get("payload") or {}).get("model"):
                    turns.append(e["payload"]["model"])
            if turns:
                (sub.add(turns[-1]) if is_child else main.update(turns))
    return {"main": sorted(main), "subagent": sorted(sub)}


def changes(repo: Path, init: str) -> tuple[list[str], list[str]]:
    """Changed paths since the initial commit (tracked diffs + untracked files) and the added lines."""
    numstat = subprocess.run(["git", "diff", init, "--name-only"], cwd=repo,
                             capture_output=True, text=True).stdout.split()
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=repo,
                               capture_output=True, text=True).stdout.split()
    paths = [p for p in numstat + untracked if not base.CACHE_RE.search(p)]
    diff = subprocess.run(["git", "diff", init, "-U0"], cwd=repo, capture_output=True, text=True).stdout
    added = [l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
    for p in untracked:
        f = repo / p
        if f.is_file() and not base.CACHE_RE.search(p):
            added += f.read_text(errors="replace").splitlines()
    return sorted(set(paths)), added


def run_one(case: Path, agent: str, trial: int, run_dir: Path, args) -> dict:
    label = f"{case.name}/{agent}/t{trial}"
    out_dir = run_dir / case.name / agent / f"t{trial}"
    out_dir.mkdir(parents=True, exist_ok=True)
    exp = json.loads((case / "expected.json").read_text())
    result: dict = {"case": case.name, "agent": agent, "trial": trial}
    with tempfile.TemporaryDirectory(prefix=f"agent-eval-{case.name}-") as tmp:
        repo = Path(tmp) / "repo"
        base.build_repo(case, repo)
        init = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
        cmd = agent_cmd(agent, PROMPT.format(request=exp["request"]), repo, out_dir, args.models.get(agent))
        t0 = time.time()
        try:
            r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=args.timeout,
                               stdin=subprocess.DEVNULL, env={**base.os.environ, "PWD": str(repo)})
            raw, err, code = r.stdout, r.stderr, r.returncode
        except subprocess.TimeoutExpired as e:
            raw = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            err, code = "TIMEOUT", -1
        result["seconds"] = round(time.time() - t0)
        paths, added = changes(repo, init)
        commits = int(subprocess.run(["git", "rev-list", "--all", "--count"], cwd=repo,
                                     capture_output=True, text=True).stdout.strip() or 0)
        (out_dir / "diff.patch").write_text(subprocess.run(["git", "diff", init], cwd=repo,
                                                           capture_output=True, text=True).stdout)
        # Hidden acceptance tests go in only now, so the agent never saw them.
        for f in (case / "hidden").glob("*") if (case / "hidden").exists() else []:
            shutil.copy(f, repo / "tests" / f.name)
        t = subprocess.run(exp["test_command"], cwd=repo, capture_output=True, text=True, timeout=300)
        (out_dir / "tests.txt").write_text(t.stdout + t.stderr)
    (out_dir / "transcript.jsonl").write_text(raw)
    (out_dir / "stderr.txt").write_text(err)
    relay = base.extract_report(agent, raw, out_dir)
    (out_dir / "relay.md").write_text(relay)
    subs = base.subagent_outputs(agent, raw, t0)
    allowed = re.compile(exp["allowed_paths"])
    forbidden = [p for p in exp.get("forbidden_added", [])
                 if any(re.search(p, l) for l in added)]
    result |= {
        "exit": code,
        "tests_pass": t.returncode == 0,
        "out_of_scope": [p for p in paths if not allowed.match(p)],
        "plan_untouched": exp["plan"] not in paths,
        "added_lines": len(added),
        "size_ok": len(added) <= exp.get("max_added_lines", 10**9),
        "forbidden_hits": forbidden,
        "no_commits": commits == 1,
        "used_skill": bool(base.skill_re("implement-plan").search(raw)),
        "delegated": STAMP in raw or any(STAMP in s for s in subs) or bool(DELEGATION_RE.search(raw)),
        "models": models_used(agent, raw, t0),
        "usage": base.usage_summary(agent, raw),
        "changed": paths,
    }
    if code != 0:
        result["error"] = f"exit {code}; {err[-300:]}"
    ok = lambda b: "ok" if b else "FAIL"  # noqa: E731
    print(f"  done  {label}  {result['seconds']}s  tests={ok(result['tests_pass'])} "
          f"scope={ok(not result['out_of_scope'])} +{len(added)} lines "
          f"forbidden={len(forbidden)} delegated={result['delegated']}", flush=True)
    return result


def summary(results: list[dict], args) -> str:
    yn = lambda b: "✅" if b else "❌"  # noqa: E731
    lines = [f"# implement-plan eval — {datetime.now():%Y-%m-%d %H:%M}", "",
             f"Models: {json.dumps(args.models) if args.models else 'each tool default'}.", "",
             "| case | agent | trial | tests | scope | plan untouched | added lines | over-engineering | "
             "no commits | skill | delegated | subagent model | main model | time | tokens |",
             "|---" * 15 + "|"]
    for r in sorted(results, key=lambda r: (r["case"], r["agent"], r["trial"])):
        if r.get("error"):
            lines.append(f"| {r['case']} | {r['agent']} | {r['trial']} | ERROR: {r['error'][:80]} |")
            continue
        scope = yn(not r["out_of_scope"]) + (f" ({', '.join(r['out_of_scope'])})" if r["out_of_scope"] else "")
        over = yn(not r["forbidden_hits"]) + (f" ({'; '.join(r['forbidden_hits'])})" if r["forbidden_hits"] else "")
        lines.append(
            f"| {r['case']} | {r['agent']} | {r['trial']} | {yn(r['tests_pass'])} | {scope} | "
            f"{yn(r['plan_untouched'])} | {r['added_lines']} {yn(r['size_ok'])} | {over} | "
            f"{yn(r['no_commits'])} | {yn(r['used_skill'])} | {yn(r['delegated'])} | "
            f"{', '.join(r['models']['subagent']) or '–'} | {', '.join(r['models']['main']) or '–'} | "
            f"{r['seconds']}s | {base._tok(r)} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--agents", default="claude,codex")
    ap.add_argument("--cases", help="comma list of case names (default: all implement cases)")
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=1200, help="seconds per run")
    ap.add_argument("--model", action="append", default=[], metavar="AGENT=MODEL",
                    help="main-thread model, e.g. --model claude=opus")
    args = ap.parse_args()
    args.models = dict(m.split("=", 1) for m in args.model)
    for a in args.agents.split(","):
        if not shutil.which(a):
            print(f"{a} CLI not found on PATH", file=sys.stderr)
            return 2
    cases = sorted(p for p in base.CASES.iterdir() if (p / "expected.json").exists()
                   and json.loads((p / "expected.json").read_text()).get("kind") == "implement")
    if args.cases:
        cases = [c for c in cases if c.name in set(args.cases.split(","))]
    run_dir = base.RESULTS / ("implement-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    run_dir.mkdir(parents=True)
    jobs = [(c, a, t) for t in range(1, args.trials + 1) for c in cases for a in args.agents.split(",")]
    print(f"Running {len(jobs)} implement run(s) -> {run_dir}", flush=True)
    with cf.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(lambda j: run_one(*j, run_dir, args), jobs))
    (run_dir / "results.json").write_text(json.dumps(results, indent=2))
    text = summary(results, args)
    (run_dir / "summary.md").write_text(text)
    print("\n" + text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
