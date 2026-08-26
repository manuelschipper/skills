"""Shard reconciliation, evidence validation, coverage recovery, and stable finding identity."""

import json
from pathlib import Path

from .common import (
    FINDING_SCOPES,
    INITIAL_STATUS,
    SEVERITIES,
    dump,
    fmt,
    git,
    load,
    require_artifact,
)


def check_accept(checks):
    """Validate an acceptance contract without interpreting or executing its argv."""
    if not isinstance(checks, list) or not checks:
        return "accept must be a non-empty list"
    for check in checks:
        argv = check.get("argv") if isinstance(check, dict) else None
        if not isinstance(argv, list) or not argv or not all(isinstance(argument, str) for argument in argv):
            return "accept entries need an argv list of strings"
        if not isinstance(check.get("expect"), str) or not check["expect"]:
            return "accept entries need an expect string"
    return None


def collect_records(target, records, shard, label, problems):
    """Attach shard provenance to free-form leads and vocabulary additions."""
    if not isinstance(records, list):
        problems.append(f"{shard}: {label} must be a list")
        return
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict):
            problems.append(f"{shard}: {label} entry {index} must be an object")
            continue
        target.append({**record, "shard": shard})


def check_finding(finding, index, inventory, repo, properties):
    """Validate a finding and verify its whitespace-normalized quote near the claimed line."""
    if not isinstance(finding, dict):
        return f"finding {index}: must be an object"
    required = ("property", "severity", "path", "line", "evidence", "observation")
    missing = [key for key in required if key not in finding]
    if missing:
        return f"finding {index}: missing {', '.join(missing)}"
    if not isinstance(finding["property"], str) or not finding["property"].strip():
        return f"finding {index}: property must be a non-empty string"
    if not isinstance(finding["observation"], str) or not finding["observation"].strip():
        return f"finding {index}: observation must be a non-empty string"
    if finding["property"].strip() not in properties:
        return f"finding {index}: property is not a rubric heading: {finding['property']!r}"
    if finding["severity"] not in SEVERITIES:
        return f"finding {index}: severity must be one of {SEVERITIES}"
    recipe = finding.get("recipe")
    if bool(recipe) == bool(finding.get("decision")):
        return f"finding {index}: needs exactly one of recipe (list of steps) or decision (question and options)"
    if recipe and (not isinstance(recipe, list) or not all(isinstance(step, str) and step.strip() for step in recipe)):
        return f"finding {index}: recipe must be a list of non-empty steps"
    if finding.get("decision"):
        decision = finding["decision"]
        if not isinstance(decision, dict) or not isinstance(decision.get("question"), str) or not decision["question"].strip():
            return f"finding {index}: decision needs a question"
        options = decision.get("options")
        if not isinstance(options, list) or len(options) < 2 or not all(
            isinstance(option, str) and option.strip() for option in options
        ):
            return f"finding {index}: decision needs at least two non-empty options"
        if not isinstance(decision.get("recommendation"), str) or not decision["recommendation"].strip():
            return f"finding {index}: decision needs a recommendation"
    if not finding.get("accept") and not finding.get("symbol"):
        return f"finding {index}: needs accept checks or a symbol to derive them from"
    if finding.get("accept") and (error := check_accept(finding["accept"])):
        return f"finding {index}: {error}"
    if not isinstance(finding["path"], str) or not finding["path"].strip():
        return f"finding {index}: path must be a non-empty string"
    if finding["path"] not in inventory:
        return f"finding {index}: {finding['path']} is not in the inventory"
    file = repo / finding["path"]
    if not file.is_file():
        return f"finding {index}: {finding['path']} does not exist"
    lines = file.read_text(errors="replace").splitlines()
    line = finding["line"]
    if not isinstance(line, int) or line < 1 or line > len(lines):
        return f"finding {index}: {finding['path']}:{line} is out of range (1..{len(lines)})"
    if not isinstance(finding["evidence"], str) or not finding["evidence"].strip():
        return f"finding {index}: evidence must be a non-empty string"
    if len(finding["evidence"].strip().splitlines()) > 3:
        return f"finding {index}: evidence must be at most 3 lines"
    quote = " ".join(finding["evidence"].split())
    window = " ".join(" ".join(lines[max(0, line - 3):min(len(lines), line + 2)]).split())
    if quote not in window:
        return f"finding {index}: evidence not found at {finding['path']}:{line} (+/-2 lines)"
    return None


def scope_error(finding, index, audited):
    """Require every change-range finding to state its own causality; whole-repository findings carry no scope."""
    if not audited:
        finding.pop("scope", None)
        finding.pop("traces_to", None)
        return None
    # No defaults, even on a changed file: an untouched pre-existing line of a modified file is a judgment call.
    traceable = {change["path"] for change in audited["changed"]} | {
        change["old_path"] for change in audited["changed"] if change.get("old_path")
    }
    scope = finding.get("scope")
    if scope not in FINDING_SCOPES:
        return f"finding {index}: scope must be one of {FINDING_SCOPES} (got {scope!r})"
    traces_to = finding.get("traces_to")
    if traces_to not in traceable:
        return f"finding {index}: traces_to must name a changed, renamed, or deleted path (got {traces_to!r})"
    return None


def finding_key(finding):
    """Return the persisted identity used for dedupe and stable IDs."""
    evidence = " ".join(str(finding["evidence"]).split())
    return json.dumps(
        [finding["property"], finding["path"], finding["line"], evidence],
        ensure_ascii=True,
        separators=(",", ":"),
    )


def progress_line(ledger):
    """Return the single user-facing reconciliation progress line."""
    readable = [file for file in ledger["files"] if file["treatment"] == "read"]
    read = sum(file["status"] == "read-in-full" for file in readable)
    uncovered = sum(file["status"] == "uncovered" for file in readable)
    pending = sum(file["status"] == "pending" for file in readable)
    done = sum(shard["status"] == "reconciled" for shard in ledger["shards"])
    pct = f"{100 * read // len(readable)}%" if readable else "n/a"
    context = sum(file["treatment"] == "context" for file in ledger["files"])
    return (
        f"coverage: read {read}/{len(readable)} files ({pct}) | shards {done}/{len(ledger['shards'])} reconciled"
        f" | pending files {pending} | uncovered {uncovered} | findings {len(ledger['findings'])}"
        f" (dropped {len(ledger['dropped'])})" + (f" | context {context}" if context else "")
    )


def cmd_verify(args):
    """Rebuild coverage and accepted findings from the artifacts currently on disk."""
    work = Path(args.work)
    inventory = require_artifact(work, "inventory.json", "inventory (step 1)")
    repo = Path(inventory["repo"])
    by_path = {file["path"]: file for file in inventory["files"]}
    properties = set(inventory["properties"])
    shard_file = work / "shards.json"
    shards = require_artifact(work, "shards.json", "inventory (step 1)")["shards"]
    prior_ledger = load(work / "ledger.json", {})
    finding_ids = prior_ledger.get("finding_id_map", {})
    redispatch = {shard["parent"] for shard in shards if shard["parent"]}
    audited = inventory.get("range")
    status = {file["path"]: INITIAL_STATUS[file["treatment"]] for file in inventory["files"]}
    reader = {}
    findings, dropped, leads, additions, problems, undeclared_by_shard = [], [], [], [], [], {}
    new_shards = []
    for shard in shards:
        shard["status"] = "pending"
        artifact = work / "shards" / f"{shard['id']}.json"
        if not artifact.exists():
            continue
        try:
            data = json.loads(artifact.read_text())
        except json.JSONDecodeError as error:
            problems.append(f"{shard['id']}: artifact is not valid JSON ({error})")
            continue
        assigned = set(shard["files"])
        read = {entry["path"] for entry in data.get("files_read", []) if isinstance(entry, dict)}
        undeclared = sorted(properties - {str(heading).strip() for heading in data.get("properties_checked", [])})
        if undeclared:
            undeclared_by_shard[shard["id"]] = (
                f"{shard['id']}: properties not declared checked, files not counted as read: {', '.join(undeclared)}"
            )
            read = set()
        skipped = {
            entry["path"]: entry.get("reason", "") for entry in data.get("files_skipped", []) if isinstance(entry, dict)
        }
        extra = (read | set(skipped)) - assigned
        if extra:
            problems.append(f"{shard['id']}: reported files outside its assignment: {', '.join(sorted(extra))}")
        remainder = sorted((assigned - read) | (set(skipped) & assigned))
        for path in read & assigned:
            status[path], reader[path] = "read-in-full", shard["id"]
        if remainder:
            if shard["id"] in redispatch or shard["parent"]:
                for path in remainder:
                    status[path] = "uncovered"
                    by_path[path]["reason"] = skipped.get(path) or f"not read by {shard['id']} after re-dispatch"
            else:
                child = {
                    "id": f"{shard['id']}r", "files": remainder,
                    "lines": sum(by_path[path]["lines"] for path in remainder),
                    "status": "pending", "parent": shard["id"],
                }
                if not any(value["id"] == child["id"] for value in shards):
                    new_shards.append(child)
        for index, finding in enumerate(data.get("findings", []), 1):
            error = check_finding(finding, index, by_path, repo, properties) or scope_error(finding, index, audited)
            if error:
                dropped.append({
                    "shard": shard["id"], "reason": error,
                    "path": finding.get("path") if isinstance(finding, dict) else None,
                    "line": finding.get("line") if isinstance(finding, dict) else None,
                })
            else:
                findings.append({**finding, "property": finding["property"].strip(), "shard": shard["id"]})
        collect_records(leads, data.get("cross_shard_leads", []), shard["id"], "cross_shard_leads", problems)
        collect_records(additions, data.get("vocabulary_additions", []), shard["id"], "vocabulary_additions", problems)
        shard["status"] = "reconciled" if not remainder else "partial"
    main_artifact = work / "shards" / "main.json"
    if main_artifact.exists():
        try:
            data = json.loads(main_artifact.read_text())
        except json.JSONDecodeError as error:
            problems.append(f"main: artifact is not valid JSON ({error})")
            data = {}
        for index, finding in enumerate(data.get("findings", []), 1):
            error = check_finding(finding, index, by_path, repo, properties) or scope_error(finding, index, audited)
            if error:
                dropped.append({
                    "shard": "main", "reason": error,
                    "path": finding.get("path") if isinstance(finding, dict) else None,
                    "line": finding.get("line") if isinstance(finding, dict) else None,
                })
            else:
                findings.append({**finding, "property": finding["property"].strip(), "shard": "main"})
        collect_records(leads, data.get("cross_shard_leads", []), "main", "cross_shard_leads", problems)
        collect_records(additions, data.get("vocabulary_additions", []), "main", "vocabulary_additions", problems)
    seen, unique = {}, []
    for finding in findings:
        key = finding_key(finding)
        if key in seen:
            dropped.append({
                "shard": finding["shard"], "path": finding["path"], "line": finding["line"],
                "reason": "duplicate key (property, path, line, normalized evidence) "
                          f"already reported by {seen[key]}",
            })
        else:
            seen[key] = finding["shard"]
            unique.append(finding)
    findings = unique
    shards.extend(new_shards)
    for shard in shards:
        if shard["status"] != "pending" and all(status[path] != "pending" for path in shard["files"]):
            shard["status"] = "reconciled"
    recovered = []
    for shard in shards:
        message = undeclared_by_shard.get(shard["id"])
        if message:
            (recovered if all(status[path] == "read-in-full" for path in shard["files"]) else problems).append(message)
    dump(shard_file, {"shards": shards})
    findings.sort(key=lambda finding: (finding["path"], finding["line"], finding["property"]))
    next_id = max((int(value.removeprefix("F-")) for value in finding_ids.values()), default=0) + 1
    for finding in findings:
        key = finding_key(finding)
        if key not in finding_ids:
            finding_ids[key] = f"F-{next_id:03d}"
            next_id += 1
        finding["id"] = finding_ids[key]
    dirty_now = git(repo, "status", "--porcelain").splitlines()
    if audited:
        head_now = git(repo, "rev-parse", "HEAD").strip()
        if head_now != audited["head"]:
            problems.append(f"HEAD moved from {audited['head'][:12]} to {head_now[:12]}; rerun inventory")
        tracked = [line for line in dirty_now if not line.startswith("??")]
        if tracked:
            problems.append(
                f"working tree differs from HEAD in {len(tracked)} tracked entries; evidence no longer agrees with HEAD"
            )
    ledger = {
        "files": [{**file, "status": status[file["path"]], "reader": reader.get(file["path"])} for file in inventory["files"]],
        "findings": findings,
        "dropped": dropped,
        "problems": problems,
        "recovered": recovered,
        "cross_shard_leads": leads,
        "vocabulary_additions": additions,
        "finding_id_map": finding_ids,
        "git_status_delta": sorted(set(dirty_now) ^ set(inventory["dirty"])),
        "shards": shards,
    }
    dump(work / "ledger.json", ledger)
    print(progress_line(ledger))
    print("\nSHARDS")
    for shard in shards:
        print(
            f"  {shard['id']:6} {shard['status']:10} {len(shard['files']):4d} files  {fmt(shard['lines']):>8} lines"
            + (f"  parent {shard['parent']}" if shard["parent"] else "")
        )
    if new_shards:
        print("\nRE-DISPATCH (run shard-prompt for each, then verify again)")
        for shard in new_shards:
            print(f"  {shard['id']}  {len(shard['files'])} files")
    if problems:
        print("\nPROBLEMS")
        for problem in problems:
            print(f"  {problem}")
    if dropped:
        print("\nDROPPED FINDINGS")
        for finding in dropped:
            print(f"  {finding['shard']}: {finding['reason']}")
    if ledger["git_status_delta"]:
        print("\nGIT STATUS CHANGED SINCE INVENTORY")
        for line in ledger["git_status_delta"]:
            print(f"  {line}")
    incomplete = any(
        file["treatment"] == "read" and file["status"] != "read-in-full" for file in ledger["files"]
    )
    return 1 if problems or dropped or incomplete else 0
