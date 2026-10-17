#!/usr/bin/env python3
"""Run the exact steps of a coach play.

Covers Molds record writes, worktrees, Herdr agents, report validation, verification, climb
scoring, and delivery. The coach agent decides what happens next; this script makes each
step happen the same way every time. Every record change goes through here, so agents never
write to Molds.
"""

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import sys
import tomllib
import uuid
from datetime import datetime, timezone
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
PLAYS = ("rush", "screen", "drive", "climb")
STATES = ("brief", "build", "review", "stuck", "done", "dropped")
TRANSITIONS = (
    ("brief", "build"), ("build", "review"), ("review", "build"),
    ("build", "done"), ("review", "done"),
    ("build", "stuck"), ("review", "stuck"),
    ("stuck", "brief"), ("stuck", "build"), ("stuck", "review"),
    ("stuck", "dropped"),
)
TASKS = {"build": "builder", "review": "reviewer", "fix-review": "reviewer", "judge": "reviewer"}
# Paths every task worktree ignores locally: the run directory holding prompts, reports, and
# probe scratch, and the settings file Claude Code writes when a permission is remembered.
EXCLUDES = (".coach/", ".claude/settings.local.json")
# A drive that still has findings at this round stops for the user instead of looping on.
VALVE_ROUND = 6


class Fail(Exception):
    pass


def run(argv, cwd=None, check=True, stdin=None):
    p = subprocess.run(argv, cwd=cwd, input=stdin, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise Fail(f"{' '.join(argv)} exited {p.returncode}: {(p.stderr or p.stdout).strip()}")
    return p


def git(*args, cwd=None):
    return run(["git", *args], cwd=cwd).stdout.strip()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


# --- Repository layout -------------------------------------------------------------------
# The Molds project is named after the repository; a task's branch, worktree, and run
# directory are all derived from its record ID. main() runs from the main checkout, so
# removing a task worktree never removes the working directory.


def common_dir():
    return Path(git("rev-parse", "--path-format=absolute", "--git-common-dir"))


def project():
    """The repository name reduced to what Molds accepts: ^[a-z][a-z0-9]{0,15}$."""
    repo = common_dir().parent.name
    name = re.sub(r"[^a-z0-9]", "", repo.lower())[:16]
    if not re.fullmatch(r"[a-z][a-z0-9]*", name):
        raise Fail(f"repository name {repo!r} gives no valid Molds project name")
    return name


def branch(rid):
    return f"coach/{rid}"


def worktree(rid):
    return Path.home() / "worktrees" / common_dir().parent.name / rid


def run_dir(rid):
    return worktree(rid) / ".coach"


def head(rid):
    wt = worktree(rid)
    if not wt.is_dir():
        raise Fail(f"{wt} does not exist; run start first")
    return git("rev-parse", "HEAD", cwd=wt)


def require_clean(rid):
    wt = worktree(rid)
    head(rid)
    if git("status", "--porcelain", cwd=wt):
        raise Fail(f"{wt} has uncommitted changes")
    if git("rev-parse", "--abbrev-ref", "HEAD", cwd=wt) != branch(rid):
        raise Fail(f"{wt} is not on {branch(rid)}")


def is_ancestor(old, new, cwd=None):
    return run(["git", "merge-base", "--is-ancestor", old, new], cwd=cwd, check=False).returncode == 0


# --- Molds -------------------------------------------------------------------------------


def molds(*args, stdin=None):
    p = run(["molds", "--project", project(), *args, "--json"], check=False, stdin=stdin)
    if p.returncode != 0:
        raise Fail(f"molds {' '.join(args)}: {p.stderr.strip()}")
    return json.loads(p.stdout)["result"]


def batch(ops):
    return molds("batch", "--stdin", "--idempotency-key", f"coach-{uuid.uuid4()}",
                 stdin=json.dumps(ops))


def show(rid):
    return molds("show", rid)["document"]


def section(doc, name):
    return next((s["content"] for s in doc["sections"] if s["name"] == name), "")


# Logs are sections holding one single-line JSON object per paragraph.
def entries(doc, name):
    return [json.loads(p) for p in section(doc, name).split("\n\n") if p.strip()]


def append_op(rid, name, entry):
    return {"op": "section_append", "id": rid, "section": name,
            "content": json.dumps(entry, sort_keys=True)}


def log_op(rid, event, **fields):
    return append_op(rid, "Run Log", {"event": event, "at": now(), **fields})


def log(rid, event, **fields):
    batch([log_op(rid, event, **fields)])


def events(doc, event, **match):
    return [e for e in entries(doc, "Run Log")
            if e["event"] == event and all(e.get(k) == v for k, v in match.items())]


def last_index(log_entries, pred):
    return max((i for i, e in enumerate(log_entries) if pred(e)), default=-1)


def set_state(rid, state, question=None, decision=None):
    doc = show(rid)
    rev = doc["revision"]
    ops = []
    if state != doc["state"]:
        ops.append({"op": "state", "id": rid, "state": state, "base_revision": rev})
    if state == "stuck":
        ops.append({"op": "section_set", "id": rid, "section": "Stuck", "content": question,
                    "base_revision": rev})
    elif doc["state"] == "stuck":
        ops.append({"op": "section_remove", "id": rid, "section": "Stuck", "base_revision": rev})
    ops.append(log_op(rid, "state", **{"from": doc["state"], "to": state},
                      **({"decision": decision} if decision else {})))
    batch(ops)


def reviews(doc, tasks=("review", "fix-review")):
    return [e for e in entries(doc, "Code Review")
            if e["task"] in tasks and e["outcome"] == "complete"]


# Blockers are blocking findings left unfixed, minus those a later review disposed of.
def open_blockers(doc):
    out = {}
    for e in reviews(doc):
        for d in e["dispositions"]:
            out.pop(d["finding_id"], None)
        for f in e["findings"]:
            if f["severity"] == "blocking" and not f.get("fix"):
                out[f["id"]] = {**f, "round": e["round"], "tip": e["tip"]}
    return list(out.values())


# --- Brief -------------------------------------------------------------------------------


def brief_sections(text):
    """Map each lowercased Brief heading to its text, ignoring `#` lines inside fences."""
    out, name, fence = {}, None, False
    for line in text.splitlines():
        if line.startswith("```"):
            fence = not fence
        elif not fence and re.match(r"#+\s", line):
            name = re.sub(r"^#+\s*", "", line).strip().lower()
            out[name] = []
            continue
        if name is not None:
            out[name].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def code_block(text):
    m = re.search(r"^```[^\n]*\n(.*?)^```", text or "", re.M | re.S)
    return m.group(1) if m else None


def done_when(brief):
    block = code_block(brief_sections(brief).get("done when"))
    if not block or not block.strip():
        raise Fail("the Brief needs a `## Done when` section with a ```sh block")
    return block


def measure_config(brief):
    text = brief_sections(brief).get("measure")
    if text is None:
        return None
    cmd = code_block(text)
    better = re.search(r"\b(lower|higher) is better\b", text, re.I)
    runs = re.search(r"\bruns:\s*(\d+)", text, re.I)
    target = re.search(r"\btarget:\s*(\S+)", text, re.I)
    if not (cmd and better and runs) or int(runs.group(1)) < 1:
        raise Fail("`## Measure` needs a ```sh block, `lower is better` or `higher is better`,"
                   " and `Runs: N` with N at least 1")
    return {"cmd": cmd, "lower": better.group(1).lower() == "lower",
            "runs": int(runs.group(1)),
            "target": number(target.group(1).rstrip(".")) if target else None}


def number(text):
    try:
        value = float(text)
    except ValueError:
        raise Fail(f"{text!r} is not a number")
    if not math.isfinite(value):
        raise Fail(f"{text!r} is not a finite number")
    return value


def check_brief(brief, play):
    if "goal" not in brief_sections(brief):
        raise Fail("the Brief needs a `## Goal` section")
    done_when(brief)
    if play == "climb":
        measure_config(brief)


# --- Herdr -------------------------------------------------------------------------------


def herdr(*args):
    p = run(["herdr", *args], check=False)
    if p.returncode != 0:
        raise Fail(f"herdr {' '.join(args[:2])}: {(p.stderr or p.stdout).strip()}")
    return json.loads(p.stdout)["result"]


def require_herdr():
    if os.environ.get("HERDR_ENV") != "1":
        raise Fail("this process is outside Herdr")


def runtime(role):
    path = Path.home() / ".coach.toml"
    if not path.exists():
        raise Fail(f"{path} is missing; it names the runtime for each role")
    role_cfg = tomllib.loads(path.read_text()).get("roles", {}).get(role)
    if not role_cfg or "kind" not in role_cfg or "argv" not in role_cfg:
        raise Fail(f"{path} needs [roles.{role}] with `kind` and `argv`")
    return role_cfg["kind"], role_cfg["argv"]


def agent_name(rid, role):
    me = herdr("agent", "get", os.environ["HERDR_PANE_ID"])["agent"].get("name")
    if not me:
        raise Fail('name this agent first: herdr agent rename "$HERDR_PANE_ID" <name>')
    purpose = f"{role}-{rid.rsplit('-', 1)[1]}"
    return f"{me[:32 - len(purpose) - 5]}-sub-{purpose}"


def last_spawn(doc, role):
    spawns = events(doc, "spawn", role=role)
    if not spawns:
        raise Fail(f"no {role} spawned for this task: run spawn first")
    return spawns[-1]


# --- Evidence ----------------------------------------------------------------------------
# What finish requires before a tip can be delivered or marked done.


# Evidence counts only under the Brief it was produced for: every verification, dispatch,
# and accepted report records the digest of the whole Brief.
def brief_id(doc):
    return digest(section(doc, "Brief"))


def verified(doc, tip):
    """True when the latest verification of `tip` passed under the current Brief."""
    runs = events(doc, "verify", tip=tip)
    return bool(runs) and runs[-1]["passed"] and runs[-1]["brief"] == brief_id(doc)


def reviewed(doc, tip):
    """True when the play's required build and review evidence covers exactly `tip`."""
    play, current = doc["fields"]["coach.play"], brief_id(doc)
    builds = [e for e in entries(doc, "Build Log")
              if e["outcome"] == "complete" and e["brief"] == current]
    if not any(is_ancestor(b["tip"], tip) for b in builds):
        return False
    if play == "rush":
        return True
    done = reviews(doc)
    if (not done or done[-1]["verdict"] != "pass" or done[-1]["tip"] != tip
            or done[-1]["brief"] != current or open_blockers(doc)):
        return False
    if play == "climb" and measure_config(section(doc, "Brief")):
        finals = [e for e in entries(doc, "Climb Log") if e.get("final") and e["tip"] == tip]
        return bool(finals) and not finals[-1]["gain_lost"]
    return True


def deliverable(doc, tip):
    """A tip is deliverable when it is verified and reviewed, or when it is a verified
    target integration, possibly repeated, of a reviewed tip."""
    if not verified(doc, tip):
        return False
    frontier, seen = [tip], set()
    while frontier:
        candidate = frontier.pop()
        if candidate in seen:
            continue
        seen.add(candidate)
        if reviewed(doc, candidate):
            return True
        frontier += [e["from"] for e in events(doc, "integrated", to=candidate)]
    return False


# --- Prompts -----------------------------------------------------------------------------


def repair_sections(doc, tip):
    """Prompt sections naming what the next build must repair: a failed verification, a
    target conflict, or a lost climb gain, each recorded since the last accepted build."""
    play, run_log, parts = doc["fields"]["coach.play"], entries(doc, "Run Log"), []
    last_accept = last_index(run_log, lambda e: e["event"] == "accept" and e["task"] == "build")
    verify_at = last_index(run_log, lambda e: e["event"] == "verify")
    if verify_at > last_accept and not run_log[verify_at]["passed"]:
        failed = run_log[verify_at]
        # A climb reverts a failed attempt; only a failure still on the branch needs repair.
        if play != "climb" or is_ancestor(failed["tip"], tip):
            parts += ["## Failed verification", fenced(failed)]
    conflict_at = last_index(run_log, lambda e: e["event"] == "merge-conflict")
    if conflict_at > last_accept:
        c = run_log[conflict_at]
        parts += ["## Target integration",
                  f"Merge `{c['target']}` (at `{c['target_tip']}`) into your branch."
                  f" It conflicted on: {', '.join(c['paths'])}."]
    lost_at = last_index(run_log, lambda e: e["event"] == "gain-lost")
    if lost_at > last_accept:
        parts += ["## Lost gain", "The final measurement of this branch gave back the climb's"
                  " gain. Restore it without undoing the fixes since:", fenced(run_log[lost_at])]
    return parts



def fenced(value):
    return f"```json\n{json.dumps(value, indent=2)}\n```"


def render(doc, rid, task, rnd, tip, report, scratch, dispatch, repair):
    play = doc["fields"]["coach.play"]
    start = events(doc, "start")[-1]
    parts = [(SKILL / "prompts" / f"{task}.md").read_text(), "# Task context", "\n".join([
        f"- Record: {rid}, {doc['title']} (play `{play}`, round {rnd})",
        f"- Worktree: {worktree(rid)}",
        f"- Branch: {branch(rid)}",
        f"- Base: {start['base']}",
        f"- Current tip: {tip}",
        f"- Report path: {report}",
        f"- Scratch directory: {scratch}",
        *([f"- New finding prefix: {dispatch}-"] if task in ("review", "fix-review") else []),
    ]), "## Brief", section(doc, "Brief")]
    if task != "judge":
        parts += ["## Open blockers", fenced(open_blockers(doc))]
    if task == "build":
        done = reviews(doc)
        if done:
            parts += ["## Latest review", fenced(done[-1])]
        parts += repair_sections(doc, tip)
    if task in ("review", "fix-review"):
        parts += ["## Build Log", fenced(entries(doc, "Build Log"))]
        earlier = entries(doc, "Code Review")
        if earlier:
            parts += ["## Earlier reviews", fenced(earlier)]
    if play == "climb":
        climb = entries(doc, "Climb Log")
        if repair:
            parts += ["## Climb history", "This round repairs the branch; it is not an attempt."
                      " Keep every kept gain. Attempts so far:", fenced(climb)]
        else:
            parts += ["## Climb", "Every attempt so far, kept or reverted:", fenced(climb)]
        if task == "judge":
            kept = [e for e in climb if e["kept"]][-1]
            parts.append(f"Compare the kept commit `{kept['tip']}` with the attempt `{tip}`.")
    return "\n\n".join(parts) + "\n"


# --- Report validation -------------------------------------------------------------------
# Reports have a closed shape: unknown keys are rejected, and the runner's own facts (round,
# tips, agent, commits) are added after validation so a report can never overwrite them.

FIELDS = {
    "build": {"outcome", "summary", "decisions", "deviations", "surprises", "repairs",
              "residual_risk", "hypothesis"},
    "review": {"outcome", "verdict", "findings", "dispositions", "probes", "follow_ups",
               "residual_risk"},
    "judge": {"outcome", "verdict", "goal_met", "evidence", "remaining", "residual_risk"},
}
FIELDS["fix-review"] = FIELDS["review"]
FINDING_FIELDS = {"id", "severity", "evidence", "location"}


def need_text(obj, key, problems, where=""):
    if not isinstance(obj.get(key), str) or not obj[key].strip():
        problems.append(f"{where}`{key}` must be a nonempty string")


def need_list(obj, key, problems, item=str):
    value = obj.get(key)
    if not isinstance(value, list) or not all(isinstance(x, item) for x in value):
        problems.append(f"`{key}` must be an array of {'strings' if item is str else 'objects'}")
        return []
    return value


def closed(obj, allowed, problems, where=""):
    extra = sorted(set(obj) - allowed)
    if extra:
        problems.append(f"{where}unexpected keys: {', '.join(extra)}")


def resolve(sha, cwd):
    if not isinstance(sha, str):
        return None
    return run(["git", "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}"],
               cwd=cwd, check=False).stdout.strip() or None


def check_report(task, r, doc, disp, made, tip, wt):
    """Return the problems with report `r`; empty when it can be recorded."""
    p = []
    allowed = ("complete", "blocked") if task == "judge" else ("complete", "spec-gap", "blocked")
    if r.get("outcome") not in allowed:
        return [f"`outcome` must be one of: {', '.join(allowed)}"]
    if r["outcome"] != "complete":
        closed(r, {"outcome", "reason"}, p)
        need_text(r, "reason", p)
        return p
    play = doc["fields"]["coach.play"]
    attempt = play == "climb" and not disp["repair"]
    closed(r, FIELDS[task] - ({"hypothesis"} if task == "build" and play != "climb" else set()), p)
    if task == "build":
        for key in ("summary", "residual_risk") + (("hypothesis",) if attempt else ()):
            need_text(r, key, p)
        if "hypothesis" in r and not attempt:
            need_text(r, "hypothesis", p)
        for key in ("decisions", "deviations", "surprises", "repairs"):
            need_list(r, key, p)
    elif task == "judge":
        if r.get("verdict") not in ("better", "same", "worse"):
            p.append("`verdict` must be better, same, or worse")
        if not isinstance(r.get("goal_met"), bool):
            p.append("`goal_met` must be true or false")
        for key in ("evidence", "remaining", "residual_risk"):
            need_text(r, key, p)
    else:
        p += check_review(task, r, doc, disp["dispatch"], made, tip, wt)
    return p


def check_review(task, r, doc, prefix, made, tip, wt):
    p = []
    fixing = task == "fix-review"
    if r.get("verdict") not in ("pass", "findings"):
        p.append("`verdict` must be pass or findings")
    resolved = {d["finding_id"] for e in reviews(doc) for d in e["dispositions"]
                if d["status"] == "resolved"}
    seen = set()
    findings = need_list(r, "findings", p, dict)
    for f in findings:
        fid = f.get("id")
        where = f"finding {fid}: "
        closed(f, FINDING_FIELDS | ({"fix"} if fixing else {"reopens"}), p, where)
        if not isinstance(fid, str) or not re.fullmatch(rf"{prefix}-\d+", fid) or fid in seen:
            p.append(f"{where}IDs must be unique and numbered {prefix}-1, {prefix}-2, ...")
        else:
            seen.add(fid)
        if f.get("severity") not in ("blocking", "non-blocking"):
            p.append(f"{where}`severity` must be blocking or non-blocking")
        need_text(f, "evidence", p, where)
        if "location" in f:
            need_text(f, "location", p, where)
        if "reopens" in f and (not isinstance(f["reopens"], str) or f["reopens"] not in resolved):
            p.append(f"{where}`reopens` must name an earlier finding marked resolved")
        if "fix" in f:
            full = resolve(f["fix"], wt)
            if full not in made:
                p.append(f"{where}`fix` must be a commit this review made")
            else:
                f["fix"] = full
    blockers = {b["id"]: b for b in open_blockers(doc)}
    disposed = set()
    for d in need_list(r, "dispositions", p, dict):
        fid = d.get("finding_id")
        where = f"disposition {fid}: "
        closed(d, {"finding_id", "status", "evidence"}, p, where)
        if not isinstance(fid, str) or fid not in blockers:
            p.append(f"{where}not an open blocker")
            continue
        disposed.add(fid)
        if d.get("status") not in ("resolved", "not-reproduced"):
            p.append(f"{where}`status` must be resolved or not-reproduced")
        elif d["status"] == "resolved" and blockers[fid]["tip"] == tip:
            p.append(f"{where}the tip is unchanged since it was raised; use not-reproduced"
                     " with counterevidence")
        need_text(d, "evidence", p, where)
    probes = need_list(r, "probes", p, dict)
    if not probes:
        p.append("`probes` must record at least one probe")
    for probe in probes:
        closed(probe, {"description", "result"}, p, "probe: ")
        need_text(probe, "description", p, "probe: ")
        need_text(probe, "result", p, "probe: ")
    for follow in need_list(r, "follow_ups", p, dict):
        closed(follow, {"title", "evidence"}, p, "follow-up: ")
        need_text(follow, "title", p, "follow-up: ")
        need_text(follow, "evidence", p, "follow-up: ")
    need_text(r, "residual_risk", p)
    if r.get("verdict") == "pass":
        if any(f.get("severity") == "blocking" and not f.get("fix") for f in findings):
            p.append("a pass cannot leave a blocking finding unfixed")
        if set(blockers) - disposed:
            p.append(f"a pass must dispose of every open blocker: {sorted(set(blockers) - disposed)}")
    if r.get("verdict") == "findings" and not findings:
        p.append("verdict `findings` needs at least one finding")
    return p


# --- Verification and measurement --------------------------------------------------------


def verify(rid, doc):
    """Run Done-when as one bash script on the tip and record the result."""
    wt, tip = worktree(rid), head(rid)
    block = done_when(section(doc, "Brief"))
    p = run(["bash", "-e", "-o", "pipefail", "-c", block], cwd=wt, check=False)
    passed, tail = p.returncode == 0, "\n".join((p.stdout + p.stderr).splitlines()[-40:])
    dirty = git("status", "--porcelain", cwd=wt)
    if passed and (dirty or head(rid) != tip):
        passed = False
        tail = f"verification changed the worktree:\n{dirty or 'HEAD moved'}"
    result = {"tip": tip, "passed": passed, "exit": p.returncode, "brief": brief_id(doc)}
    if not passed:
        result["output_tail"] = tail
    log(rid, "verify", **result)
    return result


def measure(rid, cfg):
    """Run Measure once untimed to warm caches, then `runs` times, and summarize the values."""
    tip, values = head(rid), []
    for i in range(cfg["runs"] + 1):
        out = run(["bash", "-e", "-o", "pipefail", "-c", cfg["cmd"]], cwd=worktree(rid)).stdout.strip()
        dirty = git("status", "--porcelain", cwd=worktree(rid))
        if dirty or head(rid) != tip:
            # 5: put the measured tip back exactly as it was before refusing.
            git("reset", "--hard", tip, cwd=worktree(rid))
            git("clean", "-fd", cwd=worktree(rid))
            raise Fail(f"the Measure command changed the worktree (discarded):\n{dirty or 'HEAD moved'}")
        if i:
            values.append(number(out.splitlines()[-1].strip() if out else ""))
    return {"median": statistics.median(values), "spread": max(values) - min(values),
            "values": values}


def reached(cfg, value):
    return value <= cfg["target"] if cfg["lower"] else value >= cfg["target"]


# --- Commands ----------------------------------------------------------------------------


def cmd_init(a):
    name = project()
    listing = run(["molds", "projects", "list", "--json"]).stdout
    if name in json.loads(listing)["result"]:
        raise Fail(f"Molds project {name} already exists")
    run(["molds", "projects", "create", name, "--json"])
    for state in STATES:
        molds("states", "add", state)
    molds("states", "default", "brief")
    for state in molds("states", "list")["states"]:
        if state["name"] not in STATES:
            molds("states", "remove", state["name"])
    for src, dst in TRANSITIONS:
        molds("states", "allow", src, dst)
    print(name)


def cmd_new(a):
    states = molds("states", "list")
    names = {s["name"] for s in states["states"]}
    default = next((s["name"] for s in states["states"] if s["is_default"]), None)
    if not set(STATES) <= names or default != "brief":
        raise Fail(f"Molds project {project()} is not set up for coach; it needs the states"
                   f" {', '.join(STATES)} with brief as default")
    ops = [{"op": "create", "title": a.title, "as": "task"},
           {"op": "field_set", "id": "$task", "key": "coach.play", "value": a.play},
           {"op": "field_set", "id": "$task", "key": "coach.round", "value": 0},
           {"op": "section_set", "id": "$task", "section": "Brief",
            "content": Path(a.brief).read_text()}]
    if a.target:
        git("rev-parse", "--verify", f"refs/heads/{a.target}")
        ops.append({"op": "field_set", "id": "$task", "key": "coach.target", "value": a.target})
    if a.source:
        ops.append({"op": "edge_add", "from": "$task", "edge_type": "discovered-from",
                    "to": a.source})
    print(batch(ops)["aliases"]["task"])


def cmd_brief(a):
    doc = show(a.id)
    if doc["state"] not in ("brief", "stuck"):
        raise Fail(f"{a.id} is in {doc['state']}; change the Brief from brief or stuck")
    if entries(doc, "Climb Log"):
        raise Fail("the climb has a baseline under this Brief; a different Goal or Measure is a"
                   " new task")
    brief = Path(a.file).read_text()
    check_brief(brief, doc["fields"]["coach.play"])
    batch([{"op": "section_set", "id": a.id, "section": "Brief", "content": brief,
            "base_revision": doc["revision"]},
           log_op(a.id, "brief", brief=digest(brief))])


def cmd_start(a):
    doc = show(a.id)
    if doc["state"] != "brief":
        raise Fail(f"{a.id} is in {doc['state']}, not brief")
    check_brief(section(doc, "Brief"), doc["fields"]["coach.play"])
    base = git("rev-parse", doc["fields"].get("coach.target") or "HEAD", cwd=a.caller)
    wt = worktree(a.id)
    wt.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-b", branch(a.id), str(wt), base)
    exclude = common_dir() / "info" / "exclude"
    exclude.parent.mkdir(exist_ok=True)
    present = exclude.read_text().splitlines() if exclude.exists() else []
    missing = [line for line in EXCLUDES if line not in present]
    if missing:
        with exclude.open("a") as f:
            f.write("".join(f"{line}\n" for line in missing))
    run_dir(a.id).mkdir()
    log(a.id, "start", base=base, branch=branch(a.id), worktree=str(wt), approved=a.approved)
    set_state(a.id, "build")
    print(json.dumps({"worktree": str(wt), "branch": branch(a.id), "base": base}))


def cmd_spawn(a):
    require_herdr()
    if a.argv and not a.kind:
        raise Fail("agent arguments need --kind")
    show(a.id)
    kind, argv = (a.kind, a.argv) if a.kind else runtime(a.role)
    name = agent_name(a.id, a.role)
    if run(["herdr", "agent", "get", name], check=False).returncode == 0:
        raise Fail(f"{name} is still live; retire the previous {a.role} first")
    tab = herdr("tab", "create", "--workspace", os.environ["HERDR_WORKSPACE_ID"],
                "--cwd", str(worktree(a.id)), "--label", f"{a.id}-{a.role}", "--no-focus")
    tab_id, ready = tab["tab"]["tab_id"], True
    try:
        herdr("agent", "start", name, "--kind", kind, "--pane", tab["root_pane"]["pane_id"],
              "--timeout", "60000", "--", *argv)
    except Fail as e:
        if "agent_not_ready" not in str(e):
            run(["herdr", "tab", "close", tab_id], check=False)
            raise
        ready = False
    log(a.id, "spawn", role=a.role, agent=name, kind=kind, argv=argv, tab=tab_id)
    print(json.dumps({"agent": name, "ready": ready}))
    if not ready:
        print(f"inspect it with: herdr agent read {name} --source visible", file=sys.stderr)


def cmd_retire(a):
    spawn = last_spawn(show(a.id), a.role)
    herdr("tab", "close", spawn["tab"])
    log(a.id, "retire", role=a.role, agent=spawn["agent"])


def outstanding(doc, task):
    """The latest dispatch of `task` that was neither accepted nor abandoned, if any."""
    sent = events(doc, "dispatch", task=task)
    if not sent:
        return None
    d = sent[-1]["dispatch"]
    if events(doc, "accept", dispatch=d) or events(doc, "abandon", dispatch=d):
        return None
    return sent[-1]


def cmd_send(a):
    doc = show(a.id)
    tip = head(a.id)
    if a.task != "build" and not verified(doc, tip):
        raise Fail(f"verify the tip before sending {a.task}")
    if a.task == "judge" and not entries(doc, "Climb Log"):
        raise Fail("score the baseline before judging")
    pending = outstanding(doc, a.task)
    if pending and not a.abandon:
        raise Fail(f"{pending['dispatch']} ({a.task}) has no accepted report yet; accept it, or"
                   " send with --abandon to replace it")
    rnd = doc["fields"]["coach.round"] + (a.task == "build")
    agent = last_spawn(doc, TASKS[a.task])["agent"]
    # Record the dispatch before submitting it, so every dispatch ID is used once; a prompt
    # that never reached the agent is marked abandoned and a retry gets a fresh ID.
    dispatch = f"d{len(events(doc, 'dispatch')) + 1}"
    out = run_dir(a.id)
    prompt, report = out / f"{dispatch}-{a.task}.md", out / f"{dispatch}-{a.task}.json"
    scratch = out / f"{dispatch}-{a.task}-scratch"
    ops = [log_op(a.id, "abandon", dispatch=pending["dispatch"])] if pending else []
    if a.task == "build":
        ops.append({"op": "field_set", "id": a.id, "key": "coach.round", "value": rnd,
                    "base_revision": doc["revision"]})
    repair = a.task == "build" and bool(repair_sections(doc, tip))
    ops.append(log_op(a.id, "dispatch", dispatch=dispatch, task=a.task, round=rnd, agent=agent,
                      tip=tip, report=str(report), brief=brief_id(doc), repair=repair))
    batch(ops)
    try:
        scratch.mkdir(parents=True, exist_ok=True)
        prompt.write_text(render(doc, a.id, a.task, rnd, tip, report, scratch, dispatch, repair))
        herdr("agent", "prompt", agent,
              f"Read {prompt} and follow it exactly. Write your report to {report}, then stop.")
    except (Fail, OSError) as e:
        log(a.id, "abandon", dispatch=dispatch, reason=f"prompt not delivered: {e}")
        raise Fail(f"{dispatch} was not delivered and is abandoned; send again once the agent is"
                   f" ready: {e}")
    print(json.dumps({"agent": agent, "round": rnd, "dispatch": dispatch, "report": str(report)}))


def cmd_accept(a):
    doc = show(a.id)
    disp = outstanding(doc, a.task)
    if not disp:
        raise Fail(f"{a.id} has no {a.task} awaiting acceptance; send one first")
    rnd, report = disp["round"], Path(disp["report"])
    if not report.exists():
        raise Fail(f"no report at {report}; read the agent's pane")
    try:
        r = json.loads(report.read_text())
    except json.JSONDecodeError as e:
        raise Fail(f"report rejected; send this back to the agent:\n- not valid JSON: {e}")
    if not isinstance(r, dict):
        raise Fail("report rejected; send this back to the agent:\n- must be one JSON object")
    wt, mutating = worktree(a.id), a.task in ("build", "fix-review")
    tip = head(a.id)
    if not mutating and tip != disp["tip"]:
        raise Fail(f"a read-only {a.task} moved the tip; restore it with "
                   f"`git -C {wt} reset --hard {disp['tip']}` and send a new {a.task}")
    if r.get("outcome") == "complete" or not mutating:
        require_clean(a.id)
    if mutating and not is_ancestor(disp["tip"], tip, wt):
        raise Fail(f"history was rewritten: {disp['tip']} is no longer in {branch(a.id)}; restore"
                   f" it with `git -C {wt} reset --hard {disp['tip']}` and send a new {a.task}")
    made = git("rev-list", "--reverse", f"{disp['tip']}..{tip}", cwd=wt).split()
    problems = check_report(a.task, r, doc, disp, made, tip, wt)
    if problems:
        raise Fail("report rejected; send these back to the agent:\n- " + "\n- ".join(problems))
    entry = {**r, "round": rnd, "task": a.task, "agent": disp["agent"],
             "dispatch": disp["dispatch"], "brief": disp["brief"], "from_tip": disp["tip"],
             "tip": tip}
    if mutating:
        entry["commits"] = made
    batch([append_op(a.id, "Build Log" if a.task == "build" else "Code Review", entry),
           log_op(a.id, "accept", dispatch=disp["dispatch"], task=a.task, round=rnd,
                  outcome=r["outcome"], tip=tip)])
    valve = []
    if doc["fields"]["coach.play"] == "drive":
        earlier = [e for e in entries(doc, "Build Log") if e["outcome"] == "complete"]
        # The first round under a changed Brief may rightly need no new commit.
        same_brief = bool(earlier) and earlier[-1]["brief"] == disp["brief"]
        if a.task == "build" and same_brief and r["outcome"] == "complete" and not made:
            valve.append("this build round made no commit")
        if any("reopens" in f for f in r.get("findings", [])):
            valve.append("a finding reopens one marked resolved")
        if a.task == "review" and r.get("verdict") == "findings" and rnd >= VALVE_ROUND:
            valve.append(f"round {rnd} still has findings")
    print(json.dumps({
        "outcome": r["outcome"], "verdict": r.get("verdict"), "new_commits": len(made),
        "open_blockers": [b["id"] for b in open_blockers(show(a.id))],
        "follow_ups": r.get("follow_ups", []), "valve": valve,
    }, indent=2))


def cmd_verify(a):
    result = verify(a.id, show(a.id))
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        sys.exit(1)


def cmd_score(a):
    doc = show(a.id)
    if doc["fields"]["coach.play"] != "climb":
        raise Fail("score is for climb tasks")
    require_clean(a.id)
    tip, cfg = head(a.id), measure_config(section(doc, "Brief"))
    climb = entries(doc, "Climb Log")
    if a.final:
        score_final(a.id, doc, tip, cfg, climb)
        return
    if not climb:
        if tip != events(doc, "start")[-1]["base"]:
            raise Fail("the baseline must be scored at the start base, before any attempt")
        entry = {"iteration": 0, "tip": tip, "kept": True}
        if cfg:
            entry.update(measure(a.id, cfg))
            if cfg["target"] is not None:
                entry["goal_met"] = reached(cfg, entry["median"])
        batch([append_op(a.id, "Climb Log", entry)])
        print(json.dumps(entry, indent=2))
        return
    kept = [e for e in climb if e["kept"]][-1]
    if tip == kept["tip"]:
        raise Fail("nothing to score: the tip is still the kept commit")
    rnd = doc["fields"]["coach.round"]
    builds = [e for e in entries(doc, "Build Log")
              if e["round"] == rnd and e["outcome"] == "complete"]
    entry = {"iteration": rnd, "tip": tip,
             "hypothesis": builds[-1].get("hypothesis", "") if builds else ""}
    if not verified(doc, tip) and not verify(a.id, doc)["passed"]:
        entry.update(kept=False, reason="verification failed")
    elif cfg:
        try:
            m = measure(a.id, cfg)
        except Fail as e:
            entry.update(kept=False, reason=f"measure failed: {e}")
        else:
            gain = kept["median"] - m["median"] if cfg["lower"] else m["median"] - kept["median"]
            noise = max(kept["spread"], m["spread"])
            entry.update(m, kept=gain > noise)
            if not entry["kept"]:
                entry["reason"] = f"gain {gain:g} does not beat noise {noise:g}"
            if cfg["target"] is not None:
                entry["goal_met"] = entry["kept"] and reached(cfg, m["median"])
    else:
        judged = [e for e in reviews(doc, ("judge",)) if e["tip"] == tip]
        if not judged:
            raise Fail("judge this attempt first: send then accept a judge task")
        j = judged[-1]
        entry.update(kept=j["verdict"] == "better", verdict=j["verdict"],
                     goal_met=j["verdict"] == "better" and j["goal_met"])
        if not entry["kept"]:
            entry["reason"] = f"judged {j['verdict']}"
    if not entry["kept"]:
        wt = worktree(a.id)
        git("update-ref", f"refs/coach/{a.id}/try-{rnd}", tip, cwd=wt)
        git("reset", "--hard", kept["tip"], cwd=wt)
        git("clean", "-fd", cwd=wt)
    batch([append_op(a.id, "Climb Log", entry)])
    streak = 0
    for e in reversed(climb + [entry]):
        if e["kept"]:
            break
        streak += 1
    print(json.dumps({**entry, "no_gain_streak": streak}, indent=2))


def score_final(rid, doc, tip, cfg, climb):
    """Measure the final tip after the closing review, and say whether the gain survived."""
    if not cfg:
        raise Fail("a judged climb ends with its fix-review; only measured climbs score --final")
    if len([e for e in climb if e["kept"]]) < 2:
        raise Fail("nothing was kept, so there is no final result to measure")
    if not verified(doc, tip):
        raise Fail("verify the final tip first")
    print(json.dumps(final_score(rid, doc, tip, cfg), indent=2))


def final_score(rid, doc, tip, cfg):
    """Measure `tip` against the last kept attempt and record it as a final Climb Log entry."""
    best = [e for e in entries(doc, "Climb Log") if e["kept"]][-1]
    m = measure(rid, cfg)
    loss = m["median"] - best["median"] if cfg["lower"] else best["median"] - m["median"]
    entry = {"final": True, "tip": tip, **m, "kept": False,
             "gain_lost": loss > max(best["spread"], m["spread"])}
    if cfg["target"] is not None:
        entry["goal_met"] = reached(cfg, m["median"])
    ops = [append_op(rid, "Climb Log", entry)]
    if entry["gain_lost"]:
        ops.append(log_op(rid, "gain-lost", tip=tip, median=m["median"], kept_median=best["median"]))
    batch(ops)
    return entry


def target_checkout(target):
    """Return the worktree path where `target` is checked out, if any."""
    path = None
    for line in git("worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            path = line.split(" ", 1)[1]
        elif line == f"branch refs/heads/{target}":
            return path
    return None


def cleanup(rid, tip):
    """Remove a delivered task's worktree, branch, and saved attempts; safe to repeat."""
    wt = worktree(rid)
    if wt.is_dir():
        if git("status", "--porcelain", cwd=wt) or head(rid) != tip:
            raise Fail(f"{wt} changed after delivering {tip}; save or discard that work, then"
                       " run finish again")
        git("worktree", "remove", str(wt))
    if run(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch(rid)}"],
           check=False).returncode == 0:
        git("update-ref", "-d", f"refs/heads/{branch(rid)}", tip)
    for ref in git("for-each-ref", "--format=%(refname)", f"refs/coach/{rid}/").split():
        git("update-ref", "-d", ref)


def cmd_finish(a):
    doc = show(a.id)
    if doc["state"] not in ("build", "review"):
        raise Fail(f"{a.id} is in {doc['state']}; finish from build or review")
    target = doc["fields"].get("coach.target")
    delivered = events(doc, "delivered")
    if delivered:
        cleanup(a.id, delivered[-1]["commit"])
        set_state(a.id, "done")
        print(json.dumps({"delivered": True, "target": target, "commit": delivered[-1]["commit"]}))
        return
    require_clean(a.id)
    tip = head(a.id)
    if not deliverable(doc, tip):
        raise Fail(f"{tip} lacks the evidence {doc['fields']['coach.play']} requires under the"
                   " current Brief: an accepted build it contains, a passing verify of it, and"
                   " for screen, drive, and climb a passing review of it with no open blockers"
                   " (plus, for a measured climb, a final score that kept the gain)")
    if not target:
        set_state(a.id, "done")
        print(json.dumps({"done": True, "branch": branch(a.id), "worktree": str(worktree(a.id))}))
        return
    wt = worktree(a.id)
    merged = run(["git", "merge", "--no-edit", target], cwd=wt, check=False)
    if merged.returncode != 0:
        paths = git("diff", "--name-only", "--diff-filter=U", cwd=wt).split()
        run(["git", "merge", "--abort"], cwd=wt, check=False)
        if not paths:
            raise Fail(f"git merge {target} failed: {(merged.stderr or merged.stdout).strip()}")
        log(a.id, "merge-conflict", target=target, target_tip=git("rev-parse", target), paths=paths)
        print(json.dumps({"delivered": False, "conflicts": paths}, indent=2))
        sys.exit(2)
    integrated = head(a.id)
    if integrated != tip:
        doc = show(a.id)
        result = verify(a.id, doc)
        if not result["passed"]:
            print(json.dumps({"delivered": False, "verification": result}, indent=2))
            sys.exit(3)
        cfg = measure_config(section(doc, "Brief"))
        if doc["fields"]["coach.play"] == "climb" and cfg:
            final = final_score(a.id, doc, integrated, cfg)
            if final["gain_lost"]:
                print(json.dumps({"delivered": False, "measurement": final}, indent=2))
                sys.exit(3)
        log(a.id, "integrated", **{"from": tip, "to": integrated})
    checkout = target_checkout(target)
    if checkout:
        if git("status", "--porcelain", "--untracked-files=no", cwd=checkout):
            raise Fail(f"{checkout} has uncommitted changes; {target} cannot advance")
        git("merge", "--ff-only", branch(a.id), cwd=checkout)
    else:
        old = git("rev-parse", target)
        if not is_ancestor(old, integrated):
            raise Fail(f"{target} moved; run finish again")
        git("update-ref", f"refs/heads/{target}", integrated, old)
    log(a.id, "delivered", target=target, commit=integrated)
    cleanup(a.id, integrated)
    set_state(a.id, "done")
    print(json.dumps({"delivered": True, "target": target, "commit": integrated}, indent=2))


def cmd_state(a):
    doc = show(a.id)
    if a.state == "stuck" and not a.question:
        raise Fail("stuck needs --question FILE")
    if doc["state"] == "stuck" and not a.decision:
        raise Fail("leaving stuck needs --decision TEXT")
    if a.state == "done":
        raise Fail("use finish to reach done")
    if a.state == "dropped" and doc["state"] != "stuck":
        raise Fail("only the user drops a record: go stuck and ask first")
    question = Path(a.question).read_text() if a.question else None
    set_state(a.id, a.state, question=question, decision=a.decision)


def cmd_blockers(a):
    print(json.dumps(open_blockers(show(a.id)), indent=2))


def main():
    ap = argparse.ArgumentParser(prog="coach.py", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create this repository's Molds project and its states")
    p = sub.add_parser("new", help="create a task record in brief; prints its ID")
    p.add_argument("title")
    p.add_argument("--play", choices=PLAYS, required=True)
    p.add_argument("--brief", required=True, help="Markdown file holding the Brief")
    p.add_argument("--target", help="branch to merge into when the task is done")
    p.add_argument("--from", dest="source", help="record this follow-up was discovered from")
    p = sub.add_parser("brief", help="replace the Brief of a record in brief or stuck")
    p.add_argument("id")
    p.add_argument("file")
    p = sub.add_parser("start", help="brief -> build: create the worktree and branch")
    p.add_argument("id")
    p.add_argument("--approved", required=True, help="the operator's approval of the Brief, in their words")
    p = sub.add_parser("spawn", help="open a tab and start a role's agent")
    p.add_argument("id")
    p.add_argument("role", choices=("builder", "reviewer"))
    p.add_argument("--kind", help="override the transport for this task")
    p.add_argument("argv", nargs="*", help="with --kind, after --: the agent's arguments")
    p = sub.add_parser("send", help="render a task prompt and send it to the role's agent")
    p.add_argument("id")
    p.add_argument("task", choices=TASKS)
    p.add_argument("--abandon", action="store_true",
                   help="replace a dispatch of this task that has no accepted report")
    p = sub.add_parser("accept", help="validate the task's report and record it")
    p.add_argument("id")
    p.add_argument("task", choices=TASKS)
    p = sub.add_parser("verify", help="run the Brief's Done-when script on the tip")
    p.add_argument("id")
    p = sub.add_parser("score", help="climb: keep or revert the attempt at the tip")
    p.add_argument("id")
    p.add_argument("--final", action="store_true", help="measure the final tip instead")
    p = sub.add_parser("finish", help="-> done, merging into the target when one is set")
    p.add_argument("id")
    p = sub.add_parser("state", help="move the record, entering or leaving stuck")
    p.add_argument("id")
    p.add_argument("state", choices=STATES)
    p.add_argument("--question", help="stuck: Markdown file with the question for the user")
    p.add_argument("--decision", help="leaving stuck: the user's decision")
    p = sub.add_parser("retire", help="close a role's tab")
    p.add_argument("id")
    p.add_argument("role", choices=("builder", "reviewer"))
    p = sub.add_parser("blockers", help="list open blockers")
    p.add_argument("id")
    a = ap.parse_args()
    # Resolve what the caller's directory means before moving to the main checkout.
    for key in ("brief", "file", "question"):
        if getattr(a, key, None):
            setattr(a, key, str(Path(getattr(a, key)).resolve()))
    a.caller = os.getcwd()
    try:
        os.chdir(common_dir().parent)
        globals()[f"cmd_{a.cmd}"](a)
    except Fail as e:
        print(f"coach: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
