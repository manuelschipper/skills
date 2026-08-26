"""Branded audit introduction and compact human-facing result card."""

import textwrap
from collections import Counter
from pathlib import Path

from .common import CARD_WIDTH, GREP_WORDMARK, REACH_SURFACES, plural, require_artifact
from .render import reach_totals


def cmd_scope(args):
    """Print the deterministic scope question used only when the request is ambiguous."""
    repository = Path(args.repo).resolve().name
    lines = [
        "  GREP · CHOOSE THE AUDIT",
        f"  {repository}",
        "",
        "  1  WHOLE REPOSITORY",
        "     Read every maintained project file and assess the codebase as a whole.",
        "",
        "  2  GIT DIFF",
        "     Audit every committed change from an explicit base to the checked-out",
        "     HEAD. Pull requests are one kind of Git diff.",
        "",
        "  Which should I audit?",
        "  For a Git diff, include the base ref—for example: origin/main.",
    ]
    print("\n".join(lines))


def cmd_intro(args):
    """Print the deterministic audit introduction with one delivery ending."""
    repository = Path(args.repo).resolve().name
    target = f"the change {args.base}..HEAD in {repository}" if args.base else repository
    lines = [
        GREP_WORDMARK,
        "",
        open_paragraph(f"A read-only audit of how easily coding agents can work in {target}."),
        "",
        "  I will seed the repository's vocabulary from its README, documentation,",
        "  commands, filenames, and public code. As the readers inspect the code, they",
        "  will add internal concepts and alternate spellings those surfaces do not",
        "  reveal. Then I will check whether every term leads clearly to its",
        "  implementation, usage, rules, and tests.",
        "",
        "──────────────────────────────────────────────────────────────────────────────",
        "  HOW THE AUDIT WORKS",
        "",
        *(
            [open_paragraph(
                "I will read every changed source, test, configuration, script, schema, and documentation "
                "file in full and search the unchanged repository as context for what the change reaches. "
                "Generated and third-party material is identified separately."
            )]
            if args.base else [
                "  I will inspect the source, tests, configuration, scripts, schemas, and",
                "  documentation maintained by the project. Generated and third-party material",
                "  is identified separately.",
            ]
        ),
        "",
        "  If this environment supports them, subagents will divide the reading.",
        "  Nothing in the repository will be modified. A deep audit may take a while.",
        "",
        "──────────────────────────────────────────────────────────────────────────────",
        "  WHAT YOU WILL GET",
        "",
        "  A visual health score, the most important improvements in plain language,",
        "  and a detailed Markdown report with the evidence and work packets a coding",
        "  agent needs to implement them.",
        "",
        "──────────────────────────────────────────────────────────────────────────────",
    ]
    if args.destination:
        lines.extend(["  REPORT DESTINATION", "", f"  {args.destination}"])
    elif args.chat_only:
        lines.extend(["  DELIVERY", "", "  Chat only · nothing will be stored"])
    else:
        lines.extend(["  ONE QUESTION BEFORE I START", "", "  Where should I store the detailed Markdown audit?"])
    print("\n".join(lines))


def open_field(label, value, label_width=15):
    prefix = "  " + f"{label:{label_width}} "
    return textwrap.fill(
        " ".join(str(value).split()), width=CARD_WIDTH, initial_indent=prefix,
        subsequent_indent=" " * len(prefix), break_long_words=False, break_on_hyphens=False,
    )


def open_paragraph(value, indent=2):
    prefix = " " * indent
    return textwrap.fill(
        " ".join(str(value).split()), width=CARD_WIDTH, initial_indent=prefix,
        subsequent_indent=prefix, break_long_words=False, break_on_hyphens=False,
    )


def property_bar(score):
    return "●" * score["clean"] + "○" * score["affected"]


def score_bar(value, width=10):
    if value is None:
        return "○" * width
    filled = int(width * value / 100 + 0.5)
    return "●" * filled + "○" * (width - filled)


def cmd_card(args):
    """Print a compact result card whose final line is the absolute report path."""
    work = Path(args.work)
    report_path = Path(args.report)
    if not report_path.is_absolute():
        raise SystemExit("--report must be an absolute path")
    audit = require_artifact(work, "audit.json", "render (step 5)")
    repository = audit["repository"]
    audited = audit.get("range")
    findings = audit["findings"]
    scored = [finding for finding in findings if finding.get("scope") != "follow-up"]
    narrative = audit["narrative"]
    score = audit["score"]
    dirty = f"dirty ({len(repository['dirty'])} entries)" if repository["dirty"] else "clean"
    severity = Counter(finding["severity"] for finding in scored)
    separator = "─" * CARD_WIDTH
    if audited:
        lines = [
            "  GREPPABILITY AUDIT · CHANGE SCOPE",
            open_field(
                Path(repository["repo"]).name,
                f"{audited['merge_base'][:12]}..{audited['head'][:12]} on {repository['branch']}; "
                f"base {audited['base_input']} = {audited['base'][:12]}",
                label_width=len(Path(repository["repo"]).name),
            ),
            "",
        ]
        score_label = "CHANGE SCORE"
    else:
        lines = [
            "  GREPPABILITY AUDIT",
            f"  {Path(repository['repo']).name}  {repository['head'][:12]}  {repository['branch']}  {dirty}",
            "",
        ]
        score_label = "SCORE"
    if score["value"] is None:
        lines.extend([f"  {score_label}  WITHHELD", open_field("reason", "; ".join(score["blockers"]))])
    else:
        lines.extend([
            f"  {score_label}  {score['value']}",
            f"  PROPERTIES CLEAN  {score['clean']}/{score['applicable']}   {property_bar(score)}",
        ])
    high_status = "No high-risk findings" if severity["HIGH"] == 0 else plural(severity["HIGH"], "high-risk finding")
    finding_status = "no findings" if not scored else plural(len(scored), "finding")
    if len(findings) > len(scored):
        finding_status += f" · {plural(len(findings) - len(scored), 'follow-up')} not scored"
    lines.extend([
        f"              {high_status} · {finding_status}",
        "",
        separator,
        "  VERDICT",
        open_paragraph(narrative["verdict"]),
        "",
        separator,
        "  DIMENSION SCORES",
        "",
    ])
    for dimension in score["dimensions"]:
        value = "--" if dimension["value"] is None else str(dimension["value"])
        lines.append(f"  {dimension['name']:27} {value:>3}   {score_bar(dimension['value'])}")
    lines.append("")
    themes = narrative.get("themes", [])
    lines.extend([separator, "  TOP IMPROVEMENTS", ""])
    if themes:
        for index, theme in enumerate(themes, 1):
            lines.extend([f"  {index}  {theme['title']}", "", open_paragraph(theme["explanation"], indent=5), "", ""])
    else:
        lines.extend(["  None recommended.", ""])
    totals = reach_totals(audit.get("trials", []))
    readable = [file for file in audit["files"] if file["treatment"] == "read"]
    read = sum(file["status"] == "read-in-full" for file in readable)
    uncovered = sum(file["status"] == "uncovered" for file in readable)
    pending = sum(file["status"] == "pending" for file in readable)
    context = sum(file["treatment"] == "context" for file in audit["files"])
    checked = sum(state["state"] != "unverified" for state in score["states"])
    gaps = uncovered + pending
    coverage_text = (
        (
            f"{read}/{len(readable)} changed maintained files read · "
            f"{sum(change['status'] == 'D' for change in audited['changed'])} deleted · "
            f"{context} unchanged files searched as context, not read or scored · "
            if audited else f"{read}/{len(readable)} maintained project files read · "
        )
        + (f"all {len(score['states'])} properties checked" if checked == len(score["states"])
           else f"{checked}/{len(score['states'])} properties checked")
        + (" · no coverage gaps" if gaps == 0 else f" · {plural(gaps, 'coverage gap')}")
    )
    misses = [(key, concept) for key in REACH_SURFACES for concept in totals[key]["missing"]]
    if not audit.get("trials"):
        search_text = "No vocabulary search trials recorded."
    elif not misses:
        search_text = "Search reached every applicable owner, wiring path, contract, test, and expected absence."
    else:
        search_text = "Search misses: " + "; ".join(f"{key} for {concept}" for key, concept in misses) + "."
    lines.extend([
        separator,
        "  AUDIT RECEIPT",
        "",
        open_paragraph(coverage_text),
        open_paragraph(search_text),
        "",
    ])
    reconciliation = len(audit["dropped"]) + len(audit["problems"])
    if reconciliation:
        lines.extend([
            open_paragraph(
                f"Reconciliation: {len(audit['dropped'])} dropped · {plural(len(audit['problems']), 'problem')}."
            ),
            "",
        ])
    lines.append(f"Detailed audit   {report_path}")
    print("\n".join(lines))
