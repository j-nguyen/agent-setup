#!/usr/bin/env python3
"""Eval harness for the review-changes skill + code-reviewer subagent.

For every (case, agent, trial):
  1. Build a throwaway git repo: `main` = case/before, `feature` = before + after.
  2. Ask the agent CLI, non-interactively and in natural language, to review the
     branch against the spec. This exercises the *installed* skill and subagent
     (run `bin/agent-setup sync` first).
  3. Record the transcript, the final report, whether the skill was used and
     whether it delegated to the code-reviewer subagent.
  4. Have a judge model grade the report against case/expected.json.

Standard library only. Results go to evals/results/<timestamp>/.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

_ARGS = None  # parsed CLI args, set in main()
HERE = Path(__file__).resolve().parent
CASES = HERE / "cases"
RESULTS = HERE / "results"

PROMPT = """Please review the changes on the `feature` branch of this repo against `main` \
before I merge it. Here's what the change is supposed to do:

{spec}
No database is available for this review."""

PROMPT_EXPLICIT = "Use the review-changes skill.\n\n" + PROMPT

DEBUG_PROMPT = """Can you check whether this Linear ticket actually reproduces in this repo? \
Linear isn't connected here, so I pasted the ticket below.

{ticket}"""

DEBUG_PROMPT_EXPLICIT = "Use the debug-ticket skill.\n\n" + DEBUG_PROMPT

# --tracker mode: only an ID is given; the agent has to fetch the ticket from a mock tracker.
TRACKER_PROMPTS = {
    "jira": "Can you check whether PROJ-101 reproduces in this repo?",
    "gitlab": "Can you check whether https://gitlab.com/acme/billing/-/issues/101 reproduces in this repo?",
}

# --------------------------------------------------------------------------- #
# Agents. Each returns (cmd, env-extras) and knows how to read its transcript.
# --------------------------------------------------------------------------- #
CLAUDE_TOOLS = ("Read Grep Glob Skill Agent Task TodoWrite "
                "Bash(git:*) Bash(gh:*) Bash(ls:*) Bash(cat:*) Bash(find:*) Bash(grep:*) "
                "Bash(rg:*) Bash(wc:*) Bash(head:*) Bash(tail:*) Bash(python3:*) Bash(node:*) "
                "Bash(npm:*) Bash(npx:*) Bash(pytest:*) Bash(mypy:*) Bash(tsc:*) Bash(mktemp:*) Bash(tar:*)")

DELEGATION_RE = re.compile(
    r'\\*"(?:subagent_type|agent_type|agent|role|subagent)\\*"\s*:\s*\\*"code-reviewer\\*"')
STAMP = "Reviewed by the code-reviewer subagent."
DEBUG_STAMP = "Debugged by the debugger subagent."
CACHE_RE = re.compile(r"(^|/)(__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.tsbuildinfo|"
                      r"node_modules/\.cache)(/|$)|\.pyc$")
VERIFIER_STAMP = "Verified by the finding-verifier subagent."
def skill_re(skill: str) -> re.Pattern:
    s = re.escape(skill)
    return re.compile(rf'\\*"(?:skill|id|name)\\*"\s*:\s*\\*"{s}\\*"|{s}/SKILL\.md'
                      rf'|skill_content name=\\*"{s}')


def ran_command_containing(raw: str, needle: str) -> bool:
    """True if any tool call's `command` argument contains `needle` (all three CLIs use that key)."""
    return bool(re.search(r'\\*"command\\*"\s*:\s*\\*"[^"]*' + re.escape(needle), raw))


def agent_cmd(agent: str, prompt: str, repo: Path, out_dir: Path, model: str | None,
              debug: bool = False) -> list[str]:
    if agent == "claude":
        # The debugger may add files (Write); nobody may edit existing ones (Edit).
        tools = CLAUDE_TOOLS + (" Write Bash(mkdir:*) Bash(python:*) Bash(curl:*) Bash(env:*) Bash(command:*)"
                                if debug else "")
        # Tracker fetches read credentials from env vars ($JIRA_API_TOKEN), which Claude Code asks
        # a human to approve; with nobody to ask in -p mode, allow plain Bash for these runs.
        if debug and getattr(_ARGS, "tracker", None):
            tools += " Bash"
        blocked = "Edit NotebookEdit" if debug else "Edit Write NotebookEdit"
        cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
               "--no-session-persistence", "--allowedTools", tools, "--disallowedTools", blocked]
        return cmd + (["--model", model] if model else [])
    if agent == "codex":
        # Codex's sandbox blocks network by default; --tracker runs need it to reach the mock API.
        net = ["-c", "sandbox_workspace_write.network_access=true"] if debug and getattr(_ARGS, "tracker", None) else []
        cmd = ["codex", "exec", "--json", *net, "--sandbox", "workspace-write" if debug else "read-only",
               "--ephemeral",
               "--skip-git-repo-check", "-C", str(repo),
               "-o", str(out_dir / "report.md"), prompt]
        return cmd[:2] + (["-m", model] if model else []) + cmd[2:]
    if agent == "opencode":
        cmd = ["opencode", "run", "--standalone", "--format", "json", "--auto", "--archived",
               "--title", f"eval-{out_dir.name}", prompt]
        return cmd[:2] + (["-m", model] if model else []) + cmd[2:]
    raise ValueError(agent)


def extract_report(agent: str, raw: str, out_dir: Path) -> str:
    events = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    if agent == "claude":
        for e in reversed(events):
            if e.get("type") == "result":
                return e.get("result") or ""
    if agent == "codex":
        p = out_dir / "report.md"
        if p.exists():
            return p.read_text()
    # opencode (and fallback): longest text part from the last assistant turn(s)
    texts = []
    for e in events:
        part = e.get("part") or e.get("properties", {}).get("part") or {}
        if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
            texts.append(part["text"])
    if texts:
        tail = texts[-3:]
        return max(tail, key=len)
    return raw[-20000:]


def usage_summary(agent: str, raw: str) -> dict:
    out: dict = {}
    for line in raw.splitlines():
        try:
            e = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if agent == "claude" and e.get("type") == "result":
            out = {"cost_usd": e.get("total_cost_usd"), "turns": e.get("num_turns"),
                   "is_error": e.get("is_error")}
        if agent == "codex" and e.get("type") == "turn.completed":
            u = e.get("usage") or {}
            out["input_tokens"] = out.get("input_tokens", 0) + (u.get("input_tokens") or 0)
            out["output_tokens"] = out.get("output_tokens", 0) + (u.get("output_tokens") or 0)
    return out


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args], cwd=repo, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "Eval", "GIT_AUTHOR_EMAIL": "eval@example.com",
                        "GIT_COMMITTER_NAME": "Eval", "GIT_COMMITTER_EMAIL": "eval@example.com"})


def build_repo(case: Path, dest: Path) -> None:
    dest.mkdir(parents=True)
    git(dest, "init", "-q", "-b", "main")
    if (case / "commits.json").exists():  # debug cases: a linear history, optionally tagged
        for c in json.loads((case / "commits.json").read_text()):
            shutil.copytree(case / "commits" / c["dir"], dest, dirs_exist_ok=True)
            git(dest, "add", "-A")
            git(dest, "commit", "-q", "-m", c["message"])
            if c.get("tag"):
                git(dest, "tag", c["tag"])
        return
    shutil.copytree(case / "before", dest, dirs_exist_ok=True)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "Initial commit")
    git(dest, "checkout", "-q", "-b", "feature")
    shutil.copytree(case / "after", dest, dirs_exist_ok=True)
    git(dest, "add", "-A")
    title = (case / "spec.md").read_text().splitlines()[0][:72]
    git(dest, "commit", "-q", "-m", title)


# --------------------------------------------------------------------------- #
# Judge
# --------------------------------------------------------------------------- #
JUDGE_PROMPT = """You are grading a code review written by an AI reviewer against an answer key.
Be strict and literal. Grade only what the report says; do not review the code yourself.

ANSWER KEY (JSON):
{expected}

THE REVIEW REPORT:
<<<REPORT
{report}
REPORT>>>

Instructions:
- must_find / nice_to_find: mark found=true only if the report identifies the same root problem
  (as a finding, suggestion, or a Missing/Partial/Contradicted spec row) at the same location or
  clearly the same code. A vague mention ("consider security") does not count.
- must_not_flag: flagged=true if the report presents that item as a problem anywhere
  (finding or suggestion). For an "any-high" item, flagged=true if the report has any High finding
  or a "Changes requested" verdict.
- other_findings: every finding/suggestion in the report that does not match an answer-key item.
  valid=true if, from the report's own description, it is plausibly a real, actionable issue with
  this change; false if it is noise, speculative, pre-existing, or an excluded category.
- verdict_reported: the report's verdict text, or "missing".
- format_ok: true if the report has a verdict, a spec-conformance table, and a findings section
  where every finding has a file:line location. A findings section that says there are no
  blocking findings is fine.

Reply with ONLY a JSON object, no prose, in this shape:
{{"must_find":[{{"id":"...","found":true,"note":"..."}}],
  "nice_to_find":[{{"id":"...","found":false,"note":"..."}}],
  "must_not_flag":[{{"id":"...","flagged":false,"note":"..."}}],
  "other_findings":[{{"ref":"F5","valid":true,"note":"..."}}],
  "verdict_reported":"...","format_ok":true}}"""


def parse_json_obj(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


DEBUG_JUDGE_PROMPT = """You are grading a bug-reproduction report written by an AI debugger against an
answer key. Be strict and literal. Grade only what the report says; do not debug the code yourself.

ANSWER KEY (JSON):
{expected}

THE DEBUG REPORT:
<<<REPORT
{report}
REPORT>>>

Instructions:
- must_find: found=true only if the report clearly contains that item, with evidence (commands
  it ran and their output, or file:line). A claim with no evidence does not count.
- must_not_flag: flagged=true if the report does or says the described thing.
- other_findings: return [].
- verdict_reported: the text of the report's **Verdict:** line, or "missing".
- format_ok: true if the report has a Verdict line, an Attempts table, and a "Files I added" section.

Reply with ONLY a JSON object, no prose, in this shape:
{{"must_find":[{{"id":"...","found":true,"note":"..."}}],
  "nice_to_find":[],
  "must_not_flag":[{{"id":"...","flagged":false,"note":"..."}}],
  "other_findings":[],
  "verdict_reported":"...","format_ok":true}}"""


def run_judge(judge: str, expected: dict, report: str, workdir: Path, model: str | None) -> dict:
    template = DEBUG_JUDGE_PROMPT if expected.get("kind") == "debug" else JUDGE_PROMPT
    prompt = template.format(expected=json.dumps(expected, indent=1), report=report)
    if judge == "claude":
        cmd = ["claude", "-p", prompt, "--output-format", "json", "--no-session-persistence",
               "--tools", ""] + (["--model", model] if model else [])
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=workdir,
                           stdin=subprocess.DEVNULL)
        text = json.loads(r.stdout).get("result", "")
    elif judge == "codex":
        out = workdir / "judge.txt"
        cmd = ["codex", "exec", "--sandbox", "read-only", "--ephemeral", "--skip-git-repo-check",
               "-C", str(workdir), "-o", str(out)] + (["-m", model] if model else []) + [prompt]
        subprocess.run(cmd, capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL)
        text = out.read_text() if out.exists() else ""
    else:
        raise ValueError(judge)
    return parse_json_obj(text)


def verdict_matches(reported: str, allowed: list[str]) -> bool:
    v = " ".join(reported.lower().replace("*", "").split())
    for a in allowed:
        a = a.lower()
        if a == "reproduced":  # don't let "not reproduced" count as "reproduced"
            if re.search(r"(?<!not )\breproduced\b", v) and "not reproduced" not in v:
                return True
        elif a in v:
            return True
    return False


def score(expected: dict, grade: dict, verdict_expected: str) -> dict:
    must = grade.get("must_find", [])
    nice = grade.get("nice_to_find", [])
    decoys = grade.get("must_not_flag", [])
    other = grade.get("other_findings", [])
    found = sum(1 for m in must if m.get("found"))
    v = (grade.get("verdict_reported") or "").lower()
    if expected.get("kind") == "debug":
        verdict_ok = verdict_matches(v, expected["verdict_any"])
    elif "changes requested" in verdict_expected.lower():
        verdict_ok = "changes requested" in v
    else:
        verdict_ok = "approve" in v and "changes requested" not in v
    return {
        "recall": found / len(expected["must_find"]) if expected["must_find"] else None,
        "must_found": f"{found}/{len(expected['must_find'])}",
        "nice_found": f"{sum(1 for n in nice if n.get('found'))}/{len(expected.get('nice_to_find', []))}",
        "decoys_flagged": sum(1 for d in decoys if d.get("flagged")),
        "other_valid": sum(1 for o in other if o.get("valid")),
        "other_invalid": sum(1 for o in other if not o.get("valid")),
        "verdict_ok": verdict_ok,
        "format_ok": bool(grade.get("format_ok")),
    }


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run_one(case: Path, agent: str, trial: int, run_dir: Path, args) -> dict:
    label = f"{case.name}/{agent}/t{trial}"
    out_dir = run_dir / case.name / agent / f"t{trial}"
    out_dir.mkdir(parents=True, exist_ok=True)
    expected = json.loads((case / "expected.json").read_text())
    debug = expected.get("kind") == "debug"
    with tempfile.TemporaryDirectory(prefix=f"agent-eval-{case.name}-") as tmp:
        repo = Path(tmp) / "repo"
        build_repo(case, repo)
        mock, extra_env = None, {}
        if debug and args.tracker:
            from mock_tracker import MockTracker  # evals/ is on sys.path when run as a script
            mock = MockTracker((case / "ticket.md").read_text(), "PROJ-101", "acme/billing", 101).start()
            if args.tracker == "jira":
                extra_env = {"JIRA_BASE_URL": mock.url, "JIRA_EMAIL": "eval@example.com", "JIRA_API_TOKEN": "eval-token"}
            else:  # point both glab (via its own config) and the API fallback at the mock
                host = f"127.0.0.1:{mock.port}"
                glab_dir = Path(tmp) / "glab"
                glab_dir.mkdir()
                (glab_dir / "config.yml").write_text(f"telemetry: false\nhosts:\n  {host}:\n    token: eval-token\n"
                                                     f"    api_protocol: http\n    api_host: {host}\n")
                (glab_dir / "config.yml").chmod(0o600)
                extra_env = {"GLAB_CONFIG_DIR": str(glab_dir), "GITLAB_HOST": host, "GLAB_NO_PROMPT": "1",
                             "GLAB_CHECK_UPDATE": "false", "GITLAB_API_URL": mock.url + "/api/v4",
                             "GITLAB_API_TOKEN": "eval-token"}
            prompt = TRACKER_PROMPTS[args.tracker]
        elif debug:
            ticket = (case / "ticket.md").read_text()
            prompt = (DEBUG_PROMPT_EXPLICIT if args.explicit else DEBUG_PROMPT).format(ticket=ticket)
        else:
            spec = (case / "spec.md").read_text()
            prompt = (PROMPT_EXPLICIT if args.explicit else PROMPT).format(spec=spec)
        cmd = agent_cmd(agent, prompt, repo, out_dir, args.models.get(agent), debug)
        t0 = time.time()
        try:
            # Some CLIs (OpenCode) read the project dir from $PWD rather than the real cwd.
            r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=args.timeout,
                               stdin=subprocess.DEVNULL,
                               env={**{k: v for k, v in os.environ.items() if not k.startswith(("GITLAB_", "JIRA_"))},
                                    "PWD": str(repo), **extra_env})
            raw, err, code = r.stdout, r.stderr, r.returncode
        except subprocess.TimeoutExpired as e:
            raw = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            err, code = "TIMEOUT", -1
        elapsed = time.time() - t0
        fetched = mock.fetched(args.tracker) if mock else None
        if mock:
            (out_dir / "tracker-requests.txt").write_text("\n".join(mock.requests) + "\n")
            mock.stop()
        # Reviewers must leave the repo untouched; the debugger may only *add* files.
        status = subprocess.run(["git", "status", "--porcelain"], cwd=repo,
                                capture_output=True, text=True).stdout.strip()
        head_branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo,
                                     capture_output=True, text=True).stdout.strip()
    # Tool caches from running checks (e.g. __pycache__) aren't changes to the project.
    status = "\n".join(l for l in status.splitlines() if not CACHE_RE.search(l))
    tracked_changes = [l for l in status.splitlines() if not l.startswith("??")]
    if debug:
        unsafe = bool(tracked_changes) or head_branch != "main" or any(
            ran_command_containing(raw, n) for n in expected.get("forbidden_command_substrings", []))
    else:
        unsafe = bool(status)
    (out_dir / "transcript.jsonl").write_text(raw)
    (out_dir / "stderr.txt").write_text(err)
    report = extract_report(agent, raw, out_dir)
    (out_dir / "report.md").write_text(report)
    result = {
        "case": case.name, "agent": agent, "trial": trial, "exit": code,
        "seconds": round(elapsed),
        "used_skill": bool(skill_re("debug-ticket" if debug else "review-changes").search(raw)),
        # Each subagent stamps its report; that works the same in every tool.
        "delegated": (DEBUG_STAMP if debug else STAMP) in report,
        # review cases: did the finding-verifier run; --tracker debug runs: was the ticket fetched
        "verified": fetched if debug else VERIFIER_STAMP in report,
        "repo_modified": unsafe,
        "git_status": status,
        "files_added": [l[3:] for l in status.splitlines() if l.startswith("??")] if debug else [],
        "usage": usage_summary(agent, raw),
    }
    if not report.strip() or code != 0:
        result["error"] = f"exit {code}; {err[-500:]}"
        print(f"  FAIL  {label}  ({result['error'][:120]})", flush=True)
        return result
    if not args.no_judge:
        try:
            grade = run_judge(args.judge, expected, report, out_dir, args.judge_model)
            (out_dir / "grade.json").write_text(json.dumps(grade, indent=2))
            result["score"] = score(expected, grade, expected.get("verdict", ""))
        except Exception as e:  # keep the run even if grading fails
            result["error"] = f"judge failed: {e}"
    s = result.get("score", {})
    print(f"  done  {label}  {elapsed:.0f}s  must={s.get('must_found', '?')} "
          f"decoys={s.get('decoys_flagged', '?')} delegated={result['delegated']}", flush=True)
    return result


def fmt_summary(results: list[dict], args) -> str:
    lines = [f"# review-changes eval — {datetime.now():%Y-%m-%d %H:%M}", "",
             f"Judge: `{args.judge}`{' (' + args.judge_model + ')' if args.judge_model else ''}. "
             f"Prompt: {'explicit skill' if args.explicit else 'natural language'}. "
             f"Models: {json.dumps(args.models) if args.models else 'each tool default'}.", "",
             "| case | agent | trial | must-find | nice | decoys flagged | other valid/invalid | "
             "verdict | format | skill | delegated | verified/fetched | safe | time |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(results, key=lambda r: (r["case"], r["agent"], r["trial"])):
        s = r.get("score")
        if not s:
            lines.append(f"| {r['case']} | {r['agent']} | {r['trial']} | ERROR: "
                         f"{r.get('error', '')[:80]} |||||||||| ")
            continue
        yn = lambda b: "–" if b is None else ("✅" if b else "❌")  # noqa: E731
        lines.append(
            f"| {r['case']} | {r['agent']} | {r['trial']} | {s['must_found']} | {s['nice_found']} | "
            f"{s['decoys_flagged']} | {s['other_valid']}/{s['other_invalid']} | {yn(s['verdict_ok'])} | "
            f"{yn(s['format_ok'])} | {yn(r['used_skill'])} | {yn(r['delegated'])} | "
            f"{yn(r.get('verified'))} | "
            f"{yn(not r['repo_modified'])} | {r['seconds']}s |")
    lines += ["", "## Totals per agent", "",
              "| agent | runs | must-find recall | decoys flagged | invalid extra findings | "
              "verdict correct | delegated |", "|---|---|---|---|---|---|---|"]
    for agent in sorted({r["agent"] for r in results}):
        rs = [r for r in results if r["agent"] == agent]
        scored = [r for r in rs if r.get("score")]
        tot_must = sum(int(r["score"]["must_found"].split("/")[1]) for r in scored)
        got_must = sum(int(r["score"]["must_found"].split("/")[0]) for r in scored)
        lines.append(
            f"| {agent} | {len(rs)} ({len(rs) - len(scored)} errored) | "
            f"{got_must}/{tot_must} ({(got_must / tot_must * 100 if tot_must else 0):.0f}%) | "
            f"{sum(r['score']['decoys_flagged'] for r in scored)} | "
            f"{sum(r['score']['other_invalid'] for r in scored)} | "
            f"{sum(r['score']['verdict_ok'] for r in scored)}/{len(scored)} | "
            f"{sum(r['delegated'] for r in rs)}/{len(rs)} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--agents", default="claude,codex", help="comma list: claude,codex,opencode")
    ap.add_argument("--cases", help="comma list of case names (default: all)")
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=3, help="parallel runs")
    ap.add_argument("--timeout", type=int, default=1800, help="seconds per review")
    ap.add_argument("--model", action="append", default=[], metavar="AGENT=MODEL",
                    help="e.g. --model claude=opus --model opencode=openai/gpt-5.5")
    ap.add_argument("--judge", default="claude", choices=["claude", "codex"])
    ap.add_argument("--judge-model")
    ap.add_argument("--explicit", action="store_true", help="name the skill in the prompt")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--tracker", choices=["jira", "gitlab"],
                    help="debug cases: give only a ticket ID and serve the ticket from a mock tracker")
    ap.add_argument("--regrade", metavar="RUN_DIR", help="re-run only the judge on an earlier run")
    args = ap.parse_args()
    args.models = dict(m.split("=", 1) for m in args.model)
    global _ARGS
    _ARGS = args

    if args.regrade:
        return regrade(Path(args.regrade), args)

    agents = args.agents.split(",")
    for a in agents:
        if not shutil.which(a):
            print(f"{a} CLI not found on PATH", file=sys.stderr)
            return 2
    cases = sorted(p for p in CASES.iterdir() if (p / "expected.json").exists())
    if args.cases:
        wanted = set(args.cases.split(","))
        cases = [c for c in cases if c.name in wanted]
    run_dir = RESULTS / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True)
    jobs = [(c, a, t) for t in range(1, args.trials + 1) for c in cases for a in agents]
    print(f"Running {len(jobs)} review(s) -> {run_dir}", flush=True)
    with cf.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(lambda j: run_one(*j, run_dir, args), jobs))
    (run_dir / "results.json").write_text(json.dumps(results, indent=2))
    summary = fmt_summary(results, args)
    (run_dir / "summary.md").write_text(summary)
    print("\n" + summary)
    return 0


def regrade(run_dir: Path, args) -> int:
    results = json.loads((run_dir / "results.json").read_text())
    for r in results:
        out_dir = run_dir / r["case"] / r["agent"] / f"t{r['trial']}"
        report = (out_dir / "report.md").read_text() if (out_dir / "report.md").exists() else ""
        if not report.strip():
            continue
        expected = json.loads((CASES / r["case"] / "expected.json").read_text())
        grade = run_judge(args.judge, expected, report, out_dir, args.judge_model)
        (out_dir / f"grade-{args.judge}.json").write_text(json.dumps(grade, indent=2))
        r["score"] = score(expected, grade, expected.get("verdict", ""))
        r.pop("error", None)
    summary = fmt_summary(results, args)
    (run_dir / f"summary-{args.judge}.md").write_text(summary)
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
