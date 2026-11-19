#!/usr/bin/env python3
"""Eval harness for the shared skills and subagents (review, debug, plan/conformance).

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
import textwrap
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

CONFORMANCE_PROMPT = """I implemented the plan in `{plan}` on the `feature` branch of this repo. \
Before I merge it into `main`, can you check whether what I built actually matches the plan?{steps}"""

PLAN_PROMPT = """{request}

I won't be around to answer questions, so make reasonable assumptions instead of asking, and note them."""

ARCH_EXPLICIT = "Use the plan-architecture skill.\n\n"

# Plan cases with a ticket.md give only the ticket ID; the ticket is served from a mock Jira.
TICKET_PLAN_PROMPT = "Can you plan out {ticket} before anyone starts building it?"

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
CONFORMANCE_STAMP = "Reviewed against the plan by the plan-reviewer subagent."
PLAN_STAMP = "Planned by the architect subagent."
SKILL_FOR = {"review": "review-changes", "debug": "debug-ticket",
             "conformance": "plan-architecture", "plan": "plan-architecture"}
ARCH_DELEGATION_RE = re.compile(
    r'\\*"(?:subagent_type|agent_type|agent|role|subagent)\\*"\s*:\s*\\*"architect\\*"')
# `path/to/file.ext:12` or `path:12-30`, inside backticks or a table cell
CITE_RE = re.compile(r"`?((?:[\w.-]+/)*[\w.-]+\.[A-Za-z]{1,6}):(\d+)(?:-(\d+))?`?")
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
              debug: bool = False, plan: bool = False, plans_dir: Path | None = None,
              ticket: bool = False) -> list[str]:
    if agent == "claude" and plan:
        # Plan mode saves the plan file (Write); editing existing files stays blocked.
        # Ticket plans go to the temp plans directory outside the repo, and fetching the
        # ticket reads credentials from env vars, which needs plain Bash in -p mode.
        tools = CLAUDE_TOOLS + " Write Bash(mkdir:*)" + (" Bash" if ticket else "")
        cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
               "--no-session-persistence", "--allowedTools", tools,
               "--disallowedTools", "Edit NotebookEdit"]
        cmd += ["--add-dir", str(plans_dir)] if plans_dir else []
        return cmd + (["--model", model] if model else [])
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
        net = (["-c", "sandbox_workspace_write.network_access=true"]
               if ticket or (debug and getattr(_ARGS, "tracker", None)) else [])
        # No --ephemeral: Codex can't spawn subagents without the parent session's rollout
        # ("collab spawn failed: ... no rollout found for thread id"), so ephemeral runs
        # silently fall back to reviewing inline.
        cmd = ["codex", "exec", "--json", *net, "--sandbox", "workspace-write" if (debug or plan) else "read-only",
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


def subagent_outputs(agent: str, raw: str, since: float) -> list[str]:
    """Final messages of the subagents a run started, oldest first. Coordinators relay a
    compact version, so the evals grade the subagent's own full report when they can find it."""
    events = []
    for line in raw.splitlines():
        try:
            events.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            pass
    out: list[str] = []
    if agent == "claude":  # tool_result blocks answering the main thread's Agent/Task calls
        ids = [c["id"] for e in events if e.get("type") == "assistant" and not e.get("parent_tool_use_id")
               for c in e["message"]["content"] if c.get("type") == "tool_use" and c["name"] in ("Agent", "Task")]
        results = {}
        for e in events:
            if e.get("type") != "user":
                continue
            for c in (e.get("message") or {}).get("content") or []:
                if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("tool_use_id") in ids:
                    body = c.get("content")
                    if isinstance(body, list):
                        body = "\n".join(b.get("text", "") for b in body if isinstance(b, dict))
                    results[c["tool_use_id"]] = body or ""
        out = [results[i] for i in ids if i in results]
    elif agent == "codex":  # child sessions are saved as rollouts that name their parent thread
        tid = next((e.get("thread_id") for e in events if e.get("type") == "thread.started"), None)
        root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "sessions"
        found = []
        for f in root.rglob("rollout-*.jsonl") if tid and root.exists() else []:
            if f.stat().st_mtime < since:
                continue
            try:
                lines = f.read_text(errors="replace").splitlines()
                meta = json.loads(lines[0]).get("payload", {})
            except (OSError, IndexError, json.JSONDecodeError):
                continue
            if meta.get("parent_thread_id") != tid:
                continue
            msg = ""
            for line in lines:
                try:
                    pl = json.loads(line).get("payload", {})
                except json.JSONDecodeError:
                    continue
                if pl.get("type") == "task_complete" and pl.get("last_agent_message"):
                    msg = pl["last_agent_message"]
            found.append((lines and json.loads(lines[0]).get("timestamp", ""), msg))
        out = [m for _, m in sorted(found) if m]
    return [_clean_subagent_text(o) for o in out]


def _clean_subagent_text(text: str) -> str:
    """Drop harness wrappers around a subagent's report: Claude Code adds a hand-back frame and
    tool list before it, indents every line, and appends agentId/usage lines after it."""
    m = re.search(r"^[ ]{0,4}#{1,2} ", text, re.M)
    if not m:
        return text
    body = re.split(r"\n(?=agentId: |<usage>)", text[m.start():])[0]
    return textwrap.dedent(body).strip() + "\n"


def usage_summary(agent: str, raw: str) -> dict:
    out: dict = {}
    for line in raw.splitlines():
        try:
            e = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if agent == "claude" and e.get("type") == "result":
            mu = (e.get("modelUsage") or {}).values()
            out = {"cost_usd": e.get("total_cost_usd"), "turns": e.get("num_turns"),
                   "is_error": e.get("is_error"),
                   "input_tokens": sum((m.get("inputTokens") or 0) + (m.get("cacheReadInputTokens") or 0)
                                       + (m.get("cacheCreationInputTokens") or 0) for m in mu),
                   "output_tokens": sum(m.get("outputTokens") or 0 for m in mu)}
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
    if not (case / "after").exists():  # plan cases: just the starting codebase
        return
    git(dest, "checkout", "-q", "-b", "feature")
    shutil.copytree(case / "after", dest, dirs_exist_ok=True)
    git(dest, "add", "-A")
    title_src = case / "spec.md"
    title = title_src.read_text().splitlines()[0][:72] if title_src.exists() else "Implement the plan"
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


CONFORMANCE_JUDGE_PROMPT = """You are grading an architecture-conformance report written by an AI reviewer.
The reviewer checked an implementation against a written plan. Grade it against the answer key.
Be strict and literal. Grade only what the report says; do not review the code yourself.

ANSWER KEY (JSON):
{expected}

THE REPORT:
<<<REPORT
{report}
REPORT>>>

Instructions:
- must_find / nice_to_find: found=true only if the report identifies the same mismatch between plan and
  code (as a deviation, a Partial/Missing/Deviated checklist row, an unplanned change or a plan gap) at the
  same location or clearly the same code. A vague mention does not count. For each found item, set
  recommend_reported to the report's recommendation for it: "Fix code", "Update plan", "Discuss", or
  "none" if it gives none.
- must_not_flag: flagged=true if the report presents that item as a problem: a deviation, a Missing or
  Partial or Deviated row, scope creep, or a recommendation to change code or plan because of it.
  Listing it as a supporting change, Conforms, Not yet or N/A is not flagging.
- checklist: for every checklist id in the answer key's "checklist", give the status the report's
  checklist table assigns (one of Conforms, Partial, Missing, Deviated, Not yet, N/A), or "missing"
  if the report has no row for it. If the report numbers items differently, match by content.
- other_findings: every deviation, unplanned change or plan gap in the report that matches no
  answer-key item. valid=true if, from the report's description, it is a plausible, real mismatch
  between plan and code; false if noise, speculative, or a pure code-quality nit unrelated to the plan.
- verdict_reported: the text of the report's **Verdict:** line, or "missing".
- format_ok: true if the report has a verdict, a checklist table with a status and evidence per item,
  and every deviation has a location and a recommendation.

Reply with ONLY a JSON object, no prose, in this shape:
{{"must_find":[{{"id":"...","found":true,"recommend_reported":"Fix code","note":"..."}}],
  "nice_to_find":[{{"id":"...","found":false,"note":"..."}}],
  "must_not_flag":[{{"id":"...","flagged":false,"note":"..."}}],
  "checklist":{{"C1":"Conforms"}},
  "other_findings":[{{"ref":"A5","valid":true,"note":"..."}}],
  "verdict_reported":"...","format_ok":true}}"""


PLAN_JUDGE_PROMPT = """You are grading a software design plan written by an AI architect for an existing
codebase. Grade it against the answer key and the rubric. Be strict and literal. Grade only what the plan
says; you may not see the code, so rely on the answer key for facts about the codebase.

ANSWER KEY (JSON):
{expected}

THE PLAN (plus the agent's final message, if any):
<<<PLAN
{report}
PLAN>>>

Instructions:
- must_find: found=true only if the plan clearly and specifically addresses that point (in its
  decisions, design, steps, tests or checklist). A passing mention without a concrete decision does
  not count.
- nice_to_find: same, for extra-credit points.
- must_not_flag: flagged=true if the plan does or recommends the described anti-pattern.
- other_findings: return [].
- rubric: score each 1-5 (5 = excellent), with a one-line note:
  grounding: cites real files and existing patterns of this codebase rather than generic advice;
  proportionality: depth and machinery match the size of the request (no needless layers, services
    or options for a small change; enough depth for a large one);
  decisions: clear decisions with reasons and rejected alternatives;
  checklist: conformance items are specific, verifiable in code, traced to decisions and tagged with steps;
  actionability: steps are ordered, small, name files and have checkable "done when"s.
- verdict_reported: "n/a".
- format_ok: true if the plan has a Status line, Decisions with D-ids, Implementation steps, and a
  Conformance checklist with C-ids.

Reply with ONLY a JSON object, no prose, in this shape:
{{"must_find":[{{"id":"...","found":true,"note":"..."}}],
  "nice_to_find":[{{"id":"...","found":false,"note":"..."}}],
  "must_not_flag":[{{"id":"...","flagged":false,"note":"..."}}],
  "other_findings":[],
  "rubric":{{"grounding":{{"score":4,"note":"..."}},"proportionality":{{"score":4,"note":"..."}},
    "decisions":{{"score":4,"note":"..."}},"checklist":{{"score":4,"note":"..."}},
    "actionability":{{"score":4,"note":"..."}}}},
  "verdict_reported":"n/a","format_ok":true}}"""

JUDGE_TEMPLATES = {"debug": DEBUG_JUDGE_PROMPT, "conformance": CONFORMANCE_JUDGE_PROMPT,
                   "plan": PLAN_JUDGE_PROMPT}


def run_judge(judge: str, expected: dict, report: str, workdir: Path, model: str | None) -> dict:
    template = JUDGE_TEMPLATES.get(expected.get("kind", ""), JUDGE_PROMPT)
    prompt = template.format(expected=json.dumps(expected, indent=1), report=report)
    if judge == "claude":
        cmd = ["claude", "-p", prompt, "--output-format", "json", "--no-session-persistence",
               "--tools", ""] + (["--model", model] if model else [])
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=workdir,
                           stdin=subprocess.DEVNULL)
        out = json.loads(r.stdout)
        # Newer Claude Code versions print a list of events. The answer is in the "result" event.
        if isinstance(out, list):
            out = next((e for e in reversed(out) if e.get("type") == "result"), {})
        text = out.get("result", "")
    elif judge == "codex":
        out = workdir / "judge.txt"
        cmd = ["codex", "exec", "--sandbox", "read-only", "--ephemeral", "--skip-git-repo-check",
               "-C", str(workdir), "-o", str(out)] + (["-m", model] if model else []) + [prompt]
        subprocess.run(cmd, capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL)
        text = out.read_text() if out.exists() else ""
    else:
        raise ValueError(judge)
    return parse_json_obj(text)


def missing_ids(expected: dict, grade: dict) -> list[str]:
    """Answer-key items the judge left out of its grade (it sometimes drops one)."""
    out = []
    for key in ("must_find", "nice_to_find", "must_not_flag"):
        got = {g.get("id") for g in grade.get(key, [])}
        out += [i["id"] for i in expected.get(key, []) if i["id"] not in got]
    return out


def judge_complete(judge: str, expected: dict, report: str, workdir: Path, model: str | None) -> dict:
    """Grade, and re-ask once if the judge skipped answer-key items, so a skipped item
    isn't scored as a miss. Items still missing after that are recorded in `missing_ids`."""
    grade = run_judge(judge, expected, report, workdir, model)
    if missing_ids(expected, grade):
        retry = run_judge(judge, expected, report, workdir, model)
        if len(missing_ids(expected, retry)) < len(missing_ids(expected, grade)):
            grade = retry
    grade["missing_ids"] = missing_ids(expected, grade)
    return grade


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


def conformance_verdict(text: str) -> str:
    v = " ".join(text.lower().replace("*", "").split())
    if "does not conform" in v or "doesn't conform" in v:
        return "Does not conform"
    if "with deviations" in v:
        return "Conforms with deviations"
    if "conform" in v:
        return "Conforms"
    return "missing"


STATUS_ALIASES = {"conforms": "Conforms", "met": "Conforms", "partial": "Partial", "missing": "Missing",
                  "deviated": "Deviated", "not yet": "Not yet", "n/a": "N/A", "na": "N/A"}


def norm_status(s: str) -> str:
    s = (s or "").strip().lower().strip("*` ")
    return STATUS_ALIASES.get(s, s)


def score(expected: dict, grade: dict, verdict_expected: str) -> dict:
    must = grade.get("must_find", [])
    nice = grade.get("nice_to_find", [])
    decoys = grade.get("must_not_flag", [])
    other = grade.get("other_findings", [])
    found = sum(1 for m in must if m.get("found"))
    v = (grade.get("verdict_reported") or "").lower()
    kind = expected.get("kind")
    extra: dict = {}
    if kind == "conformance":
        verdict_ok = conformance_verdict(v) in expected["verdict_any"]
        key = expected.get("checklist", {})
        got = grade.get("checklist") or {}
        ok = sum(1 for cid, allowed in key.items()
                 if norm_status(got.get(cid, "")) in {norm_status(a) for a in allowed})
        extra["checklist_ok"] = f"{ok}/{len(key)}"
        rec_items = [(m, e) for m in must for e in expected["must_find"]
                     if m.get("id") == e["id"] and m.get("found") and e.get("recommend_any")]
        rec_ok = sum(1 for m, e in rec_items
                     if any(a.lower() in (m.get("recommend_reported") or "").lower() for a in e["recommend_any"]))
        extra["recommend_ok"] = f"{rec_ok}/{len(rec_items)}"
    elif kind == "plan":
        verdict_ok = None
        rub = grade.get("rubric") or {}
        extra["rubric"] = {k: (rub.get(k) or {}).get("score") for k in
                           ("grounding", "proportionality", "decisions", "checklist", "actionability")}
    elif expected.get("verdict_any"):  # debug cases, and reviews where several verdicts are fine
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
        "judge_missing": grade.get("missing_ids", []),
        **extra,
    }


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run_one(case: Path, agent: str, trial: int, run_dir: Path, args) -> dict:
    label = f"{case.name}/{agent}/t{trial}"
    out_dir = run_dir / case.name / agent / f"t{trial}"
    out_dir.mkdir(parents=True, exist_ok=True)
    expected = json.loads((case / "expected.json").read_text())
    kind = expected.get("kind", "review")
    debug = kind == "debug"
    arch = kind in ("conformance", "plan")
    plan_text, cites = "", {}
    with tempfile.TemporaryDirectory(prefix=f"agent-eval-{case.name}-") as tmp:
        repo = Path(tmp) / "repo"
        build_repo(case, repo)
        mock, extra_env = None, {}
        plans_dir = Path(tmp) / "agent-plans"  # the temp plans directory for ticket plans
        ticket_plan = kind == "plan" and (case / "ticket.md").exists()
        if kind == "plan":
            plans_dir.mkdir()
            extra_env["AGENT_PLANS_DIR"] = str(plans_dir)
        if ticket_plan:
            from mock_tracker import MockTracker
            mock = MockTracker((case / "ticket.md").read_text(), expected["ticket"], "acme/billing", 101).start()
            extra_env |= {"JIRA_BASE_URL": mock.url, "JIRA_EMAIL": "eval@example.com", "JIRA_API_TOKEN": "eval-token"}
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
        elif kind == "conformance":
            steps = expected.get("steps_note")
            prompt = (ARCH_EXPLICIT if args.explicit else "") + CONFORMANCE_PROMPT.format(
                plan=expected["plan"], steps=f" {steps}" if steps else "")
        elif kind == "plan":
            request = (TICKET_PLAN_PROMPT.format(ticket=expected["ticket"]) if ticket_plan
                       else (case / "request.md").read_text().strip())
            prompt = (ARCH_EXPLICIT if args.explicit else "") + PLAN_PROMPT.format(request=request)
        else:
            spec = (case / "spec.md").read_text()
            prompt = (PROMPT_EXPLICIT if args.explicit else PROMPT).format(spec=spec)
        cmd = agent_cmd(agent, prompt, repo, out_dir, args.models.get(agent), debug, kind == "plan",
                        plans_dir if kind == "plan" else None, ticket_plan)
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
        fetched = mock.fetched("jira" if ticket_plan else args.tracker) if mock else None
        if mock:
            (out_dir / "tracker-requests.txt").write_text("\n".join(mock.requests) + "\n")
            mock.stop()
        # Reviewers must leave the repo untouched; the debugger may only *add* files.
        # -uall lists files inside new directories; rstrip keeps the leading " M" column intact.
        status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=repo,
                                capture_output=True, text=True).stdout.rstrip()
        head_branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo,
                                     capture_output=True, text=True).stdout.strip()
        if kind == "plan":
            plan_text, plan_files = read_new_plans(repo, expected, plans_dir)
        if arch:
            graded_text = plan_text or extract_report(agent, raw, out_dir)
            cites = check_citations(graded_text, repo)
    # Tool caches from running checks (e.g. __pycache__) aren't changes to the project.
    status = "\n".join(l for l in status.splitlines() if not CACHE_RE.search(l))
    tracked_changes = [l for l in status.splitlines() if not l.startswith("??")]
    if debug:
        unsafe = bool(tracked_changes) or head_branch != "main" or any(
            ran_command_containing(raw, n) for n in expected.get("forbidden_command_substrings", []))
    elif kind == "plan":  # may only add or rewrite plan docs
        allowed = re.compile(expected.get("allowed_writes", r"^docs/.*\.md$"))
        unsafe = any(not allowed.match(l[3:].strip().strip('"')) for l in status.splitlines()) or any(
            ran_command_containing(raw, n) for n in expected.get("forbidden_command_substrings", []))
    elif kind == "conformance":
        unsafe = bool(status) or any(
            ran_command_containing(raw, n) for n in expected.get("forbidden_command_substrings", []))
    else:
        unsafe = bool(status)
    (out_dir / "transcript.jsonl").write_text(raw)
    (out_dir / "stderr.txt").write_text(err)
    report = extract_report(agent, raw, out_dir)
    final_message = report
    (out_dir / "relay.md").write_text(final_message)
    # Grade the subagents' own reports (reviewer + verifier, debugger, plan reviewer) when found,
    # since the coordinator relays only a compact version of them.
    stamps = (STAMP, VERIFIER_STAMP, DEBUG_STAMP, CONFORMANCE_STAMP)
    full = [o for o in subagent_outputs(agent, raw, t0) if any(st in o for st in stamps)]
    if kind != "plan" and full:
        report = "\n\n".join(full)
    if kind == "plan":  # grade the saved plan; fall back to the chat output if nothing was saved
        report = (plan_text + "\n\n---\nFINAL MESSAGE TO THE USER:\n" + final_message) if plan_text else final_message
    (out_dir / "report.md").write_text(report)
    result = {
        "report_chars": len(report),
        "relay_chars": len(final_message),
        "graded_subagent_report": bool(full) and kind != "plan",
        "case": case.name, "agent": agent, "trial": trial, "exit": code,
        "seconds": round(elapsed),
        "kind": kind,
        "used_skill": bool(skill_re(SKILL_FOR[kind]).search(raw)),
        # Each subagent stamps its report; that works the same in every tool. Plan mode strips the
        # stamp when saving, so look for it (or the spawn call) in the whole transcript.
        "delegated": (CONFORMANCE_STAMP in report if kind == "conformance"
                      else (PLAN_STAMP in raw or bool(ARCH_DELEGATION_RE.search(raw))) if kind == "plan"
                      else (DEBUG_STAMP if debug else STAMP) in report),
        "citations": cites,
        "plan_saved": bool(plan_text) if kind == "plan" else None,
        # where the plan landed: "temp" (the temp plans directory) or "repo"; ticket plans belong in temp
        "plan_location": (("temp" if any(f.startswith("temp:") for f in plan_files) else "repo")
                          if kind == "plan" and plan_text else None),
        "plan_location_ok": (None if kind != "plan" or "plan_location" not in expected or not plan_text
                             else any(f.startswith("temp:") for f in plan_files) == (expected["plan_location"] == "temp")),
        "ticket_fetched": fetched if ticket_plan else None,
        "plan_lines": len(plan_text.splitlines()) if kind == "plan" else None,
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
            grade = judge_complete(args.judge, expected, report, out_dir, args.judge_model)
            (out_dir / "grade.json").write_text(json.dumps(grade, indent=2))
            result["score"] = score(expected, grade, expected.get("verdict", ""))
        except Exception as e:  # keep the run even if grading fails
            result["error"] = f"judge failed: {e}"
    if kind == "plan" and not plan_text:
        result["note"] = "no plan file saved; graded the final message"
    s = result.get("score", {})
    print(f"  done  {label}  {elapsed:.0f}s  must={s.get('must_found', '?')} "
          f"decoys={s.get('decoys_flagged', '?')} delegated={result['delegated']}", flush=True)
    return result


def read_new_plans(repo: Path, expected: dict, plans_dir: Path | None = None) -> tuple[str, list[str]]:
    """Contents of plan docs the run added or changed (untracked or modified .md under docs/), plus
    any plan saved in the temp plans directory (listed as `temp:<path>`)."""
    out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=repo,
                         capture_output=True, text=True).stdout
    files = sorted(l[3:].strip().strip('"') for l in out.splitlines()
                   if l[3:].strip().endswith(".md") and l[3:].strip().startswith("docs/"))
    texts = [f"<!-- file: {f} -->\n" + (repo / f).read_text(errors="replace") for f in files if (repo / f).is_file()]
    if plans_dir and plans_dir.is_dir():
        for f in sorted(plans_dir.rglob("*.md")):
            rel = f.relative_to(plans_dir).as_posix()
            files.append(f"temp:{rel}")
            texts.append(f"<!-- file: $AGENT_PLANS_DIR/{rel} -->\n" + f.read_text(errors="replace"))
    return "\n\n".join(texts), files


def check_citations(text: str, repo: Path) -> dict:
    """Deterministic grounding check: every `path:line` cited must exist in the repo as checked out
    (the feature branch for conformance, main + the saved plan for plan mode)."""
    # Some agents cite absolute paths into the throwaway checkout (/tmp/agent-eval-x/repo/src/a.py).
    text = re.sub(r"(?<![\w.-])/(?:[\w.-]+/)*?repo/", "", text)
    seen, ok, bad = set(), 0, []
    files = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True).stdout.split()
    for m in CITE_RE.finditer(text):
        path, line = m.group(1), int(m.group(2))
        if (path, line) in seen or path.startswith(("http", "www.")):
            continue
        seen.add((path, line))
        cands = [f for f in files if f == path or f.endswith("/" + path)]
        if any(line <= len((repo / f).read_text(errors="replace").splitlines()) + 1 for f in cands):
            ok += 1
        else:
            bad.append(f"{path}:{line}")
    return {"ok": ok, "total": len(seen), "bad": bad[:20]}


def _tok(r: dict) -> str:
    u = r.get("usage") or {}
    k = lambda n: f"{(n or 0) / 1000:.0f}k"  # noqa: E731
    return f"{k(u.get('input_tokens'))}/{k(u.get('output_tokens'))}" + (
        f" ${u['cost_usd']:.2f}" if u.get("cost_usd") else "")


def _frac(vals: list[str]) -> str:
    a = sum(int(v.split("/")[0]) for v in vals)
    b = sum(int(v.split("/")[1]) for v in vals)
    return f"{a}/{b} ({a / b * 100:.0f}%)" if b else "–"


def _cite(r: dict) -> str:
    c = r.get("citations") or {}
    return f"{c['ok']}/{c['total']}" if c.get("total") else "–"


def fmt_arch(results: list[dict]) -> list[str]:
    yn = lambda b: "–" if b is None else ("✅" if b else "❌")  # noqa: E731
    lines: list[str] = []
    conf = [r for r in results if r.get("kind") == "conformance"]
    plan = [r for r in results if r.get("kind") == "plan"]
    if conf:
        lines += ["## Conformance (review mode)", "",
                  "| case | agent | trial | deviations found | recommend ok | checklist ok | nice | decoys flagged | "
                  "other valid/invalid | verdict | format | skill | delegated | safe | cites ok | time | tokens |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in sorted(conf, key=lambda r: (r["case"], r["agent"], r["trial"])):
            s = r.get("score")
            if not s:
                lines.append(f"| {r['case']} | {r['agent']} | {r['trial']} | ERROR: {r.get('error', '')[:80]} |")
                continue
            lines.append(f"| {r['case']} | {r['agent']} | {r['trial']} | {s['must_found']} | {s['recommend_ok']} | "
                         f"{s['checklist_ok']} | {s['nice_found']} | {s['decoys_flagged']} | "
                         f"{s['other_valid']}/{s['other_invalid']} | {yn(s['verdict_ok'])} | {yn(s['format_ok'])} | "
                         f"{yn(r['used_skill'])} | {yn(r['delegated'])} | {yn(not r['repo_modified'])} | "
                         f"{_cite(r)} | {r['seconds']}s | {_tok(r)} |")
        lines += ["", "| agent | runs | deviation recall | recommendation acc. | checklist acc. | decoys flagged "
                  "| invalid extras | verdict | skill | delegated | safe | citation validity |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for agent in sorted({r["agent"] for r in conf}):
            rs = [r for r in conf if r["agent"] == agent]
            sc = [r for r in rs if r.get("score")]
            ci = [r["citations"] for r in rs if (r.get("citations") or {}).get("total")]
            lines.append(
                f"| {agent} | {len(rs)} ({len(rs) - len(sc)} err) | {_frac([r['score']['must_found'] for r in sc])} | "
                f"{_frac([r['score']['recommend_ok'] for r in sc])} | {_frac([r['score']['checklist_ok'] for r in sc])} | "
                f"{sum(r['score']['decoys_flagged'] for r in sc)} | {sum(r['score']['other_invalid'] for r in sc)} | "
                f"{sum(bool(r['score']['verdict_ok']) for r in sc)}/{len(sc)} | {sum(r['used_skill'] for r in rs)}/{len(rs)} | "
                f"{sum(r['delegated'] for r in rs)}/{len(rs)} | {sum(not r['repo_modified'] for r in rs)}/{len(rs)} | "
                f"{_frac([str(c['ok']) + '/' + str(c['total']) for c in ci])} |")
        lines.append("")
    if plan:
        dims = ("grounding", "proportionality", "decisions", "checklist", "actionability")
        lines += ["## Planning (plan mode)", "",
                  "| case | agent | trial | must-cover | nice | anti-patterns | " + " | ".join(dims) +
                  " | format | saved | ticket | lines | skill | delegated | safe | cites ok | time | tokens |",
                  "|---" * (21) + "|"]
        for r in sorted(plan, key=lambda r: (r["case"], r["agent"], r["trial"])):
            s = r.get("score")
            if not s:
                lines.append(f"| {r['case']} | {r['agent']} | {r['trial']} | ERROR: {r.get('error', '')[:80]} |")
                continue
            rub = s.get("rubric") or {}
            lines.append(f"| {r['case']} | {r['agent']} | {r['trial']} | {s['must_found']} | {s['nice_found']} | "
                         f"{s['decoys_flagged']} | " + " | ".join(str(rub.get(d, '–')) for d in dims) +
                         f" | {yn(s['format_ok'])} | {_saved(r)} | {_ticket(r)} | {r.get('plan_lines')} | "
                         f"{yn(r['used_skill'])} | {yn(r['delegated'])} | {yn(not r['repo_modified'])} | "
                         f"{_cite(r)} | {r['seconds']}s | {_tok(r)} |")
        lines += ["", "| agent | runs | must-cover | anti-patterns | " + " | ".join(dims) +
                  " | saved | skill | delegated | safe | citation validity |", "|---" * 15 + "|"]
        for agent in sorted({r["agent"] for r in plan}):
            rs = [r for r in plan if r["agent"] == agent]
            sc = [r for r in rs if r.get("score")]
            ci = [r["citations"] for r in rs if (r.get("citations") or {}).get("total")]
            avg = lambda d: (lambda xs: f"{sum(xs) / len(xs):.1f}" if xs else "–")(  # noqa: E731
                [r["score"]["rubric"][d] for r in sc if (r["score"].get("rubric") or {}).get(d)])
            lines.append(
                f"| {agent} | {len(rs)} ({len(rs) - len(sc)} err) | {_frac([r['score']['must_found'] for r in sc])} | "
                f"{sum(r['score']['decoys_flagged'] for r in sc)} | " + " | ".join(avg(d) for d in dims) +
                f" | {sum(bool(r.get('plan_saved')) for r in rs)}/{len(rs)} | {sum(r['used_skill'] for r in rs)}/{len(rs)} | "
                f"{sum(r['delegated'] for r in rs)}/{len(rs)} | {sum(not r['repo_modified'] for r in rs)}/{len(rs)} | "
                f"{_frac([str(c['ok']) + '/' + str(c['total']) for c in ci])} |")
        lines.append("")
    return lines


def _yn(b) -> str:
    return "–" if b is None else ("✅" if b else "❌")


def _saved(r: dict) -> str:
    """✅/❌, plus where the plan landed when the case says where it belongs."""
    if not r.get("plan_saved"):
        return _yn(False)
    if r.get("plan_location_ok") is None:
        return _yn(True)
    return f"{_yn(r['plan_location_ok'])} {r.get('plan_location')}"


def _ticket(r: dict) -> str:
    """Ticket plan cases: was the ticket fetched from the mock tracker."""
    return "–" if r.get("ticket_fetched") is None else _yn(r["ticket_fetched"])


def fmt_summary(results: list[dict], args) -> str:
    arch = [r for r in results if r.get("kind") in ("conformance", "plan")]
    results = [r for r in results if r.get("kind") not in ("conformance", "plan")]
    if not results:
        return "\n".join([f"# plan-architecture eval — {datetime.now():%Y-%m-%d %H:%M}", "",
                          f"Judge: `{args.judge}`. Prompt: {'explicit skill' if args.explicit else 'natural language'}. "
                          f"Models: {json.dumps(args.models) if args.models else 'each tool default'}.", ""]
                         + fmt_arch(arch))
    lines = [f"# review-changes eval — {datetime.now():%Y-%m-%d %H:%M}", "",
             f"Judge: `{args.judge}`{' (' + args.judge_model + ')' if args.judge_model else ''}. "
             f"Prompt: {'explicit skill' if args.explicit else 'natural language'}. "
             f"Models: {json.dumps(args.models) if args.models else 'each tool default'}.", "",
             "| case | agent | trial | must-find | nice | decoys flagged | other valid/invalid | "
             "verdict | format | skill | delegated | verified/fetched | safe | time | tokens in/out | report/relay chars |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
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
            f"{yn(not r['repo_modified'])} | {r['seconds']}s | {_tok(r)} | {r.get('report_chars', '')}/{r.get('relay_chars', '–')} |")
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
    if arch:
        lines += [""] + fmt_arch(arch)
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--agents", default="claude,codex", help="comma list: claude,codex,opencode")
    ap.add_argument("--cases", help="comma list of case names (default: all)")
    ap.add_argument("--kind", help="comma list of case kinds: review,debug,conformance,plan (default: all)")
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
    # implement cases have their own runner (evals/implement.py)
    cases = sorted(p for p in CASES.iterdir() if (p / "expected.json").exists()
                   and json.loads((p / "expected.json").read_text()).get("kind", "review") in SKILL_FOR)
    if args.cases:
        wanted = set(args.cases.split(","))
        cases = [c for c in cases if c.name in wanted]
    if args.kind:
        kinds = set(args.kind.split(","))
        cases = [c for c in cases
                 if json.loads((c / "expected.json").read_text()).get("kind", "review") in kinds]
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

    def one(r: dict) -> None:
        out_dir = run_dir / r["case"] / r["agent"] / f"t{r['trial']}"
        report = (out_dir / "report.md").read_text() if (out_dir / "report.md").exists() else ""
        if not report.strip() or r.get("exit") not in (0, None):  # the agent run itself failed
            return
        expected = json.loads((CASES / r["case"] / "expected.json").read_text())
        if expected.get("kind") in ("conformance", "plan"):  # re-check citations on a rebuilt fixture
            with tempfile.TemporaryDirectory() as tmp:
                build_repo(CASES / r["case"], Path(tmp) / "repo")
                r["citations"] = check_citations(report, Path(tmp) / "repo")
        grade = judge_complete(args.judge, expected, report, out_dir, args.judge_model)
        (out_dir / f"grade-{args.judge}.json").write_text(json.dumps(grade, indent=2))
        r["score"] = score(expected, grade, expected.get("verdict", ""))
        r.pop("error", None)

    with cf.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        list(pool.map(one, results))
    (run_dir / f"results-{args.judge}.json").write_text(json.dumps(results, indent=2))
    summary = fmt_summary(results, args)
    (run_dir / f"summary-{args.judge}.md").write_text(summary)
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
