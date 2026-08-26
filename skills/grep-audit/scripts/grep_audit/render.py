"""Detailed Markdown rendering from verified and measured audit artifacts."""

from collections import Counter, defaultdict
from pathlib import Path

from .common import (
    CLASS_ORDER,
    DIMENSIONS,
    GREP_WORDMARK,
    REACH_SURFACES,
    SEVERITIES,
    SEVERITY_CREDIT,
    SEVERITY_DEFINITIONS,
    ascii_safe,
    bar,
    dump,
    field,
    fmt,
    plural,
    require_artifact,
    wrap,
)
from .inventory import coverage_table, exclusion_table, range_table
from .verify import progress_line


def scored_view(ledger):
    """Return the ledger as the score sees it: follow-up findings are reported, never counted."""
    return {**ledger, "findings": [finding for finding in ledger["findings"] if finding.get("scope") != "follow-up"]}


def area_of(path, depth=2):
    parts = Path(path).parts
    if len(parts) > depth:
        return "/".join(parts[:depth]) + "/"
    if len(parts) > 1:
        return "/".join(parts[:-1]) + "/"
    return "./"


def map_section(ledger):
    files = [file for file in ledger["files"] if file["treatment"] != "context"]
    findings = ledger["findings"]
    per_area = defaultdict(lambda: {"files": 0, "lines": 0, "findings": 0, "high": 0, "classes": Counter()})
    for file in files:
        entry = per_area[area_of(file["path"])]
        entry["files"] += 1
        entry["lines"] += file["lines"]
        entry["classes"][file["treatment"]] += 1
    for finding in findings:
        entry = per_area[area_of(finding["path"])]
        entry["findings"] += 1
        entry["high"] += finding["severity"] == "HIGH"
    most = max((entry["findings"] for entry in per_area.values()), default=0)
    unit = max(1, -(-most // 20))
    out = [f"MAP                                                   scale: one # = {unit} findings"]
    out.append(f"  {'area':38} {'files':>6} {'lines':>9}  {'findings':20}  note")
    for area in sorted(per_area):
        entry = per_area[area]
        note = []
        if entry["high"]:
            note.append(f"{entry['high']} HIGH")
        if entry["classes"]["boundary"] == entry["files"]:
            note.append("boundary only")
        elif entry["classes"]["listed"] == entry["files"]:
            note.append("listed only")
        out.append(
            f"  {area:38} {entry['files']:6d} {fmt(entry['lines']):>9}  "
            f"{bar(entry['findings'], unit, 16):16} {entry['findings']:3d}  {', '.join(note)}"
        )
    return "\n".join(out)


def heat_section(ledger, properties):
    findings = ledger["findings"]
    areas = Counter(area_of(finding["path"]) for finding in findings)
    top = [area for area, _ in areas.most_common(7)]
    rest = sorted(set(areas) - set(top))
    columns = top + (["other"] if rest else [])
    cells = defaultdict(Counter)
    for finding in findings:
        area = area_of(finding["path"])
        cells[finding["property"]][area if area in top else "other"] += 1

    def glyph(count):
        return "." if count == 0 else ":" if count <= 2 else "+" if count <= 5 else "#"

    out = ["HEAT GRID  findings per property and area   . = 0   : = 1-2   + = 3-5   # = 6 or more"]
    if not findings:
        return out[0] + "\n  no findings"
    width = 52
    out.append("  " + " " * (width + 4) + " ".join(f"{index + 1:>3}" for index in range(len(columns))))
    for index, property_name in enumerate(properties, 1):
        row = " ".join(f"{glyph(cells[property_name][column]):>3}" for column in columns)
        out.append(f"  {index:2d} {property_name[:width]:{width}} {row}   {sum(cells[property_name].values()):3d}")
    out.append("  columns:")
    for index, column in enumerate(columns, 1):
        label = column if column != "other" else f"other ({len(rest)} areas)"
        out.append(f"    {index:2d} {label}")
    return "\n".join(out)


def property_ledger(ledger, properties, narrative):
    findings = ledger["findings"]
    not_applicable = narrative.get("properties_not_applicable", {})
    checks = narrative.get("property_checks", {})
    out = ["PROPERTY LEDGER                                       scale: one # = 1 finding"]
    out.append(f"  {'#':>2} {'property':52} {'HIGH':>4} {'MED':>4} {'LOW':>4}  status")
    for index, property_name in enumerate(properties, 1):
        group = [finding for finding in findings if finding["property"] == property_name]
        counts = Counter(finding["severity"] for finding in group)
        if property_name in not_applicable:
            status = "n/a, because:"
        elif group:
            status = bar(len(group), 1, 24)
        elif checks.get(property_name):
            status = "clean, checked by:"
        else:
            status = "UNVERIFIED: no property_checks entry"
        out.append(
            f"  {index:2d} {property_name[:52]:52} {counts['HIGH']:4d} {counts['MED']:4d} "
            f"{counts['LOW']:4d}  {status}"
        )
        if status.startswith("clean") or property_name in not_applicable:
            out.append(
                field("", checks.get(property_name) or not_applicable.get(property_name), gutter=8, label_width=0)
                .replace("         ", "        ", 1)
            )
    out.append(
        f"  {'total':55} {sum(finding['severity'] == 'HIGH' for finding in findings):4d}"
        f" {sum(finding['severity'] == 'MED' for finding in findings):4d}"
        f" {sum(finding['severity'] == 'LOW' for finding in findings):4d}"
    )
    return "\n".join(out)


def dimension_ledger(score):
    property_number = {state["property"]: index for index, state in enumerate(score["states"], 1)}
    out = ["DIMENSION SCORES   same property credits as the overall score"]
    out.append(f"  {'dimension':29} {'score':>5}  properties")
    for dimension in score["dimensions"]:
        value = "--" if dimension["value"] is None else str(dimension["value"])
        numbers = ", ".join(
            str(property_number[property_name]) for property_name in dimension["properties"]
            if property_name in property_number
        )
        out.append(f"  {dimension['name']:29} {value:>5}  {numbers}")
    out.append("  property numbers refer to the ledger below; n/a properties are excluded")
    return "\n".join(out)


def reach_totals(trials):
    totals = {key: {"reached": 0, "applicable": 0, "missing": []} for key in REACH_SURFACES}
    for trial in trials:
        for key in REACH_SURFACES:
            mark = trial["reach"][key]["mark"]
            if mark == "-":
                continue
            totals[key]["applicable"] += 1
            if mark == "x":
                totals[key]["reached"] += 1
            else:
                totals[key]["missing"].append(trial["concept"])
    return totals


def reach_section(trials):
    out = [
        "SEARCH REACH",
        "  doc       [x] documented  [ ] undocumented  [!] unrecorded  [?] invalid proof",
        "  surfaces  [x] proved      [ ] missed        [-] n/a         [!] untried  [?] invalid proof",
    ]
    if not trials:
        return "\n".join(out + ["  no vocabulary concepts recorded"])
    out.append(f"  {'concept':28} doc  ownr  wire  cntr  test  absn  {'hits':>6}")
    for trial in trials:
        marks = "  ".join(f"[{trial['reach'][key]['mark']}]" for key in REACH_SURFACES)
        out.append(
            f"  {trial['concept'][:28]:28} [{trial['documented']['mark']}]  {marks}  {fmt(trial['hits']):>6}"
        )
        out.append(field("spellings", ", ".join(trial["spellings"]), gutter=4))
        proofs = []
        if trial["documented"]["path"]:
            proofs.append(
                f"documented={trial['documented']['path']} -> {trial['documented'].get('match') or 'no match'}"
            )
        proofs.extend(
            f"{key}={trial['reach'][key]['path']} -> {trial['reach'][key].get('match') or 'no match'}"
            for key in REACH_SURFACES if trial["reach"][key]["path"]
        )
        if proofs:
            out.append(field("proof", "; ".join(proofs), gutter=4))
    totals = reach_totals(trials)
    out.append("  reached: " + "  ".join(
        f"{key} {totals[key]['reached']}/{totals[key]['applicable']}"
        for key in REACH_SURFACES if totals[key]["applicable"]
    ))
    out.append("  hits = case-insensitive search count; short and all-uppercase spellings use whole-word matching")
    return "\n".join(out)


def blast_rows(blast):
    """Summarize a blast radius by file so repeated local hits do not dominate a finding."""
    grouped = defaultdict(list)
    for hit in blast["paths"]:
        path, line = hit.rsplit(":", 1)
        grouped[path].append(int(line))
    rows = []
    for path, lines in sorted(grouped.items()):
        span = str(lines[0]) if len(lines) == 1 else f"{lines[0]}-{lines[-1]}"
        rows.append(f"{path}:{span} ({plural(len(lines), 'hit')})")
    return rows


def finding_card(finding, packet_of):
    out = []
    if finding["id"] in packet_of:
        out.append(f"  packet    {packet_of[finding['id']]}")
    out.append(f"  where     {finding['path']}:{finding['line']}")
    if finding.get("scope"):
        out.append(f"  scope     {finding['scope']}; traces to {finding['traces_to']}")
    for line in str(finding["evidence"]).splitlines():
        out.append(f"    | {ascii_safe(line.rstrip())}")
    out.append(field("why", finding["observation"]))
    for search in finding.get("searches", []):
        out.append(f"  search    \"{search.get('term', '')}\" -> {search.get('note', '')}")
    blast = finding.get("blast")
    if blast:
        by_class = ", ".join(f"{key} {value}" for key, value in sorted(blast["by_class"].items()))
        out.append(
            f"  blast     `{blast['symbol']}`: {blast['hits']} hits in {blast['files']} files "
            f"({by_class or 'none'})"
        )
        rows = blast_rows(blast)
        for row in rows[:10]:
            out.append(f"              {row}")
        if len(rows) > 10:
            out.append(f"              +{len(rows) - 10} more files")
        if "new_symbol" in blast:
            out.append(
                f"  new name  `{blast['new_symbol']}`: {blast['new_symbol_hits']} existing hits"
                + (" (free)" if blast["new_symbol_hits"] == 0 else " (collision, choose another)")
            )
    if finding.get("recipe"):
        for index, step in enumerate(finding["recipe"], 1):
            out.append(field("recipe" if index == 1 else "", f"{index}. {step}"))
    if finding.get("decision"):
        out.append(field("decision", finding["decision"].get("question", "")))
        out.append(field("recommend", finding["decision"].get("recommendation", "")))
        for option in finding["decision"].get("options", []):
            out.append(field("", f"- {option}"))
    for index, check in enumerate(finding.get("accept", [])):
        out.append(field("accept" if index == 0 else "", f"{' '.join(check['argv'])} -> {check['expect']}"))
    return "\n".join(ascii_safe(line) for line in out)


def packets_section(ledger):
    packets = ledger.get("packets", [])
    out = ["Packets appear in dependency order. A packet is done when every acceptance line holds."]
    if not packets:
        return out[0] + "\n\nNone recorded."
    ids = {finding["id"]: finding for finding in ledger["findings"]}
    for packet in packets:
        severity = Counter(ids[finding_id]["severity"] for finding_id in packet["findings"] if finding_id in ids)
        lines = [
            (
                f"  findings  {' '.join(packet['findings'])}  "
                f"(HIGH {severity['HIGH']}, MED {severity['MED']}, LOW {severity['LOW']})"
            ),
            f"  scope     {len(packet['files'])} files, {len(packet['tests'])} tests",
        ]
        if packet.get("after"):
            lines.append(f"  after     {', '.join(packet['after'])}")
        if packet.get("note"):
            lines.append(field("note", packet["note"]))
        if packet.get("files"):
            lines.append(field("files", ", ".join(packet["files"])))
        if packet.get("creates"):
            lines.append(field("creates", ", ".join(packet["creates"])))
        if packet.get("tests"):
            lines.append(field("tests", ", ".join(packet["tests"])))
        for index, check in enumerate(packet.get("accept", [])):
            lines.append(field("accept" if index == 0 else "", f"{' '.join(check['argv'])} -> {check['expect']}"))
        out.append(f"### {packet['id']} - {ascii_safe(packet['title'])}\n\n{markdown_code(chr(10).join(lines))}")
    if ledger.get("unassigned_findings"):
        out.append(f"Not in any packet: {' '.join(ledger['unassigned_findings'])}")
    return "\n\n".join(out)


def appendix(ledger, audited=None):
    out = ["LEDGER", "  shards"]
    for shard in ledger["shards"]:
        out.append(
            f"    {shard['id']:6} {shard['status']:10} {len(shard['files']):4d} files  "
            f"{fmt(shard['lines']):>8} lines" + (f"  parent {shard['parent']}" if shard["parent"] else "")
        )
    uncovered = [file for file in ledger["files"] if file["status"] in ("uncovered", "pending")]
    out.append(f"  uncovered or pending files: {len(uncovered)}")
    for file in uncovered:
        out.append(f"    {file['path']}  ({file['status']}: {file['reason'] or 'no reason recorded'})")
    out.append(f"  dropped findings: {len(ledger['dropped'])}")
    for finding in ledger["dropped"]:
        out.append(f"    {finding['shard']}: {finding['reason']}")
    resolutions = ledger.get("vocabulary_resolutions", [])
    out.append(f"  vocabulary additions reconciled: {len(resolutions)}")
    for resolution in resolutions:
        target = f" into {resolution['target']}" if resolution.get("target") else ""
        unadopted = (
            f"; unadopted spellings: {', '.join(resolution['unadopted'])}" if resolution.get("unadopted") else ""
        )
        reason = f"; {resolution['reason']}" if resolution.get("reason") else ""
        out.append(
            field("", f"{resolution['concept']}: {resolution['disposition']}{target}{unadopted}{reason}", gutter=4)
        )
    leads = ledger.get("cross_shard_leads", [])
    out.append(f"  cross-shard leads: {len(leads)}")
    for lead in leads:
        paths = lead.get("paths", [])
        path_text = ", ".join(str(value) for value in paths) if isinstance(paths, list) else str(paths)
        out.append(field(lead.get("shard", "reader"), f"{lead.get('lead', '?')}; paths {path_text}", gutter=4))
    all_problems = ledger["problems"] + ledger.get("measure_problems", [])
    out.append(f"  problems: {len(all_problems)}")
    for problem in all_problems:
        out.append(f"    {problem}")
    out.append(f"  recovered by re-dispatch: {len(ledger.get('recovered', []))}")
    for recovery in ledger.get("recovered", []):
        out.append(f"    {recovery}")
    out.append(f"  git status changes during the audit: {len(ledger['git_status_delta'])}")
    for line in ledger["git_status_delta"]:
        out.append(f"    {line}")
    manifest = [file for file in ledger["files"] if file["treatment"] != "context"]
    if audited:
        out.append(f"  searched context files (unchanged, not read): {len(ledger['files']) - len(manifest)}")
        deleted = [change["path"] for change in audited["changed"] if change["status"] == "D"]
        out.append(f"  deleted in range: {len(deleted)}")
        out.extend(f"    {path}" for path in deleted)
    out.extend(["  file manifest", f"    {'status':14} {'class':10} {'lines':>8}  path"])
    for file in manifest:
        change = f" [{file['change']}" + (f" from {file['old_path']}" if file.get("old_path") else "") + "]" if file.get("change") else ""
        out.append(
            f"    {file['status'][:14]:14} {file['class'][:10]:10} {fmt(file['lines']):>8}  {file['path']}{change}"
        )
    return "\n".join(ascii_safe(line) for line in out)


def markdown_code(text):
    fence = "```"
    while fence in text:
        fence += "`"
    return f"{fence}text\n{text}\n{fence}"


def markdown_cell(text):
    return " ".join(ascii_safe(text).split()).replace("|", "\\|")


def audit_score(inventory, ledger, narrative):
    """Score each property once at its worst accepted severity, withholding on incomplete evidence."""
    findings = scored_view(ledger)["findings"]
    not_applicable = narrative.get("properties_not_applicable", {})
    checks = narrative.get("property_checks", {})
    blockers = list(ledger["problems"] + ledger.get("measure_problems", []))
    incomplete = [
        file for file in ledger["files"] if file["treatment"] == "read" and file["status"] != "read-in-full"
    ]
    if incomplete:
        blockers.append(f"{len(incomplete)} maintained project files are not read in full")
    if ledger.get("unassigned_findings"):
        blockers.append(f"{len(ledger['unassigned_findings'])} findings are not assigned to packets")
    states = []
    for property_name in inventory["properties"]:
        if property_name in not_applicable:
            states.append({"property": property_name, "state": "n/a", "credit": None})
            continue
        severities = [finding["severity"] for finding in findings if finding["property"] == property_name]
        if severities:
            worst = min(severities, key=SEVERITIES.index)
            states.append({"property": property_name, "state": worst, "credit": SEVERITY_CREDIT[worst]})
        elif checks.get(property_name):
            states.append({"property": property_name, "state": "clean", "credit": 1.0})
        else:
            states.append({"property": property_name, "state": "unverified", "credit": None})
            blockers.append(f"property is unverified: {property_name}")
    applicable = [state for state in states if state["state"] != "n/a"]
    if not applicable:
        blockers.append("no rubric properties are applicable")
    raw = (
        100 * sum(state["credit"] for state in applicable if state["credit"] is not None) / len(applicable)
        if applicable else 0
    )
    value = None if blockers else int(raw + 0.5)
    by_property = {state["property"]: state for state in states}
    dimensions = []
    for name, properties in DIMENSIONS:
        dimension_states = [by_property[property_name] for property_name in properties if property_name in by_property]
        dimension_applicable = [state for state in dimension_states if state["state"] != "n/a"]
        complete = len(dimension_states) == len(properties) and all(
            state["credit"] is not None for state in dimension_applicable
        )
        dimension_raw = (
            100 * sum(state["credit"] for state in dimension_applicable if state["credit"] is not None)
            / len(dimension_applicable)
            if dimension_applicable else 0
        )
        dimensions.append({
            "name": name,
            "value": int(dimension_raw + 0.5) if not blockers and complete and dimension_applicable else None,
            "properties": list(properties),
        })
    return {
        "value": value,
        "scope": "change" if inventory.get("range") else "repository",
        "applicable": len(applicable),
        "clean": sum(state["state"] == "clean" for state in applicable),
        "affected": sum(state["state"] in SEVERITIES for state in applicable),
        "not_applicable": len(states) - len(applicable),
        "states": states,
        "dimensions": dimensions,
        "blockers": blockers,
    }


def cmd_render(args):
    """Write the branded detailed report and the internal card state."""
    work = Path(args.work)
    inventory = require_artifact(work, "inventory.json", "inventory (step 1)")
    ledger = require_artifact(work, "ledger.json", "measure (step 5)")
    narrative = require_artifact(work, "narrative.json", "packets and narrative (step 5)")
    if "measure_problems" not in ledger or "trials" not in ledger or "packets" not in ledger:
        raise SystemExit("missing measured ledger state (run measure, step 5)")
    properties = inventory["properties"]
    audited = inventory.get("range")
    scored = scored_view(ledger)
    score = audit_score(inventory, ledger, narrative)
    packet_of = {finding_id: packet["id"] for packet in ledger.get("packets", []) for finding_id in packet["findings"]}
    dirty = f"dirty ({len(inventory['dirty'])} entries)" if inventory["dirty"] else "clean"
    uncovered = sum(file["status"] == "uncovered" for file in ledger["files"])
    pending = sum(file["status"] == "pending" for file in ledger["files"])
    complete = uncovered == 0 and pending == 0
    claim = "change-range" if audited else "whole-repository"
    readable = sum(file["treatment"] == "read" for file in ledger["files"])
    context = sum(file["treatment"] == "context" for file in ledger["files"])
    coverage = (
        (
            f"Change scope only: all {plural(readable, 'changed maintained file')} read in full; "
            f"{plural(context, 'unchanged file')} searched as context, never read or scored."
            if audited else "Complete: every maintained project file was read in full."
        ) if complete else
        f"INCOMPLETE: {uncovered} uncovered and {pending} pending files. "
        f"This is not a {claim} audit; see the ledger."
    )
    score_text = "withheld; " + "; ".join(score["blockers"]) if score["value"] is None else (
        f"{score['value']}/100; {score['clean']} clean + {score['affected']} affected / "
        f"{score['applicable']} applicable properties"
    )
    if audited:
        follow_ups = len(ledger["findings"]) - len(scored["findings"])
        score_text = f"change scope: {score_text}; {plural(follow_ups, 'follow-up finding')} not counted"
    head = [
        f"# Greppability audit{' (change scope)' if audited else ''}: {Path(inventory['repo']).name}",
        "",
        f"> **Coverage:** {coverage}",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Repository | `{inventory['origin'] or inventory['repo']}` |",
        f"| Revision | `{inventory['head'][:12]}` on `{inventory['branch']}`; {dirty} |",
    ]
    if audited:
        deleted = sum(change["status"] == "D" for change in audited["changed"])
        listed = sum(file["treatment"] in ("boundary", "listed") for file in ledger["files"])
        head.extend([
            f"| Range | `{audited['merge_base']}..{audited['head']}` (merge-base..HEAD) |",
            f"| Base | `{markdown_cell(audited['base_input'])}` = `{audited['base']}` |",
            (
                f"| Changed files | {readable} maintained read in full; {deleted} deleted; "
                f"{listed} generated, vendored, data, or binary listed |"
            ),
            f"| Searched context | {context} unchanged files |",
        ])
    head.extend([
        f"| Scope | {', '.join(inventory['scope']) if inventory['scope'] else 'change range' if audited else 'whole repository'} |",
        f"| Rubric | greppable, {len(properties)} properties |",
        f"| Score | {markdown_cell(score_text)} |",
        "| Score scale | Worst accepted severity per property: clean 1.00, LOW 0.75, MED 0.50, HIGH 0.00; n/a excluded. |",
        f"| Method | {markdown_cell(narrative['method'])} |",
        "| Provenance | Every count is derived from reconciled work artifacts; the full file manifest is in the ledger. |",
    ])
    findings = ledger["findings"]

    def cards(group):
        return "\n\n".join(
            f"### {finding['id']} - {finding['severity']} - {ascii_safe(finding['property'])}\n\n"
            f"{markdown_code(finding_card(finding, packet_of))}"
            for finding in group
        )

    finding_body = cards(scored["findings"]) or "No findings."
    follow_up = [finding for finding in findings if finding.get("scope") == "follow-up"]
    if follow_up:
        finding_body += (
            f"\n\nFollow-up findings ({len(follow_up)}): pre-existing debt beside the change, each traced to a "
            f"changed path. Reported for later work; not scored and not packeted.\n\n{cards(follow_up)}"
        )
    legend = "\n".join(f"- **{level}:** {SEVERITY_DEFINITIONS[level]}" for level in SEVERITIES)
    finding_body = f"{legend}\n\n{finding_body}"
    handoff = wrap(
        "Fix in packet order. For each packet: apply every recipe, follow the recorded recommendation for every "
        "design finding, run the packet's accept lines, then each finding's accept lines. A packet is done when "
        "all accept lines hold and git status shows only files it lists or creates. This report contains the complete "
        "evidence, blast paths, recommended repair, alternatives, and acceptance checks for every finding."
    )
    coverage_text = coverage_table(inventory, ledger) + "\n\n" + exclusion_table(ledger["files"])
    if audited:
        coverage_text = f"{range_table({**inventory, 'files': ledger['files']})}\n\n{coverage_text}"
    accepted = f"{len(scored['findings'])} accepted" + (
        f", {len(follow_up)} follow-up" if audited else ""
    )
    sections = [
        ("1. Verdict", wrap(narrative["verdict"]), False),
        ("2. Change map" if audited else "2. Repository map", map_section(scored), True),
        ("3. Coverage", coverage_text, True),
        ("4. Heat grid", heat_section(scored, properties), True),
        ("5. Rubric scorecard", dimension_ledger(score) + "\n\n" + property_ledger(scored, properties, narrative), True),
        ("6. Search reach", reach_section(ledger.get("trials", [])), True),
        (f"7. Findings ({accepted}, {len(ledger['dropped'])} dropped)", finding_body, False),
        ("8. Work packets", packets_section(ledger), False),
        ("9. Handoff", handoff, False),
        ("10. Reconciliation ledger and file manifest", appendix(ledger, audited), True),
    ]
    parts = ["\n".join(head)] + [
        f"## {title}\n\n{markdown_code(text) if fenced else text}" for title, text, fenced in sections
    ]
    body = ascii_safe("\n\n".join(parts) + "\n")
    repository_name = ascii_safe(Path(inventory["repo"]).name)
    purpose = (
        f"the change {audited['merge_base'][:12]}..{audited['head'][:12]} in {repository_name}"
        if audited else repository_name
    )
    report = (
        f"```text\n{GREP_WORDMARK}\n```\n\n"
        f"> A read-only audit of how easily coding agents can work in {purpose}.\n\n{body}"
    )
    Path(args.out).write_text(report)
    audit = {
        "repository": {key: inventory[key] for key in ("repo", "origin", "head", "branch", "dirty", "scope")},
        "range": audited,
        "rubric": {"path": inventory["rubric"], "properties": properties},
        "narrative": narrative,
        "score": score,
        "coverage": {cls: Counter(file["status"] for file in ledger["files"] if file["class"] == cls) for cls in CLASS_ORDER},
        "files": ledger["files"],
        "findings": findings,
        "dropped": ledger["dropped"],
        "trials": ledger.get("trials", []),
        "vocabulary_additions": ledger.get("vocabulary_additions", []),
        "vocabulary_rejected": ledger.get("vocabulary_rejected", []),
        "vocabulary_resolutions": ledger.get("vocabulary_resolutions", []),
        "cross_shard_leads": ledger.get("cross_shard_leads", []),
        "packets": ledger.get("packets", []),
        "unassigned_findings": ledger.get("unassigned_findings", []),
        "shards": ledger["shards"],
        "problems": ledger["problems"] + ledger.get("measure_problems", []),
        "recovered": ledger.get("recovered", []),
        "git_status_delta": ledger["git_status_delta"],
    }
    dump(work / "audit.json", audit)
    print(progress_line(ledger))
    if not complete:
        print(f"incomplete: {uncovered} uncovered and {pending} pending files; do not deliver this as a {claim} audit")
    print(f"report: {args.out} ({report.count(chr(10))} lines, Markdown with branded UTF-8 header and ASCII visuals)")
