#!/usr/bin/env python3
"""Mechanical grep-audit pipeline: scope, intro, inventory, shard-prompt, verify, trial, measure, render, card."""

import argparse

from grep_audit.card import cmd_card, cmd_intro, cmd_scope
from grep_audit.common import (
    DEFAULT_SHARD_LINES,
    DIMENSIONS,
    GREP_WORDMARK,
    rubric_headings,
)
from grep_audit.inventory import cmd_inventory, plan_shards
from grep_audit.measure import cmd_measure, cmd_trial, grep_hits, proof_error
from grep_audit.render import audit_score, cmd_render
from grep_audit.shard_prompt import cmd_shard_prompt
from grep_audit.verify import cmd_verify

__all__ = [
    "DIMENSIONS", "GREP_WORDMARK", "audit_score", "grep_hits", "plan_shards", "proof_error", "rubric_headings",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subcommands = parser.add_subparsers(dest="command", required=True)

    parser_scope = subcommands.add_parser("scope", help="ask whether to audit the repository or a Git diff")
    parser_scope.add_argument("--repo", required=True, help="repository name or path; only its basename is shown")
    parser_scope.set_defaults(func=cmd_scope)

    parser_intro = subcommands.add_parser("intro", help="print the branded introduction with one delivery ending")
    parser_intro.add_argument("--repo", required=True, help="repository name or path; only its basename is shown")
    parser_intro.add_argument("--base", help="announce a change-range audit of merge-base(BASE, HEAD)..HEAD")
    ending = parser_intro.add_mutually_exclusive_group()
    ending.add_argument("--destination", help="known detailed-report destination")
    ending.add_argument("--chat-only", action="store_true", help="state that nothing will be stored")
    ending.add_argument("--question", action="store_true", help="ask where to store the report (default)")
    parser_intro.set_defaults(func=cmd_intro)

    parser_inventory = subcommands.add_parser(
        "inventory", help="enumerate, classify, and shard every file in the repository"
    )
    parser_inventory.add_argument("--repo", default=".")
    parser_inventory.add_argument("--work", required=True, help="artifact directory outside the repository")
    parser_inventory.add_argument(
        "--scope", action="append", default=[],
        help="restrict a whole-repository audit to a repository-relative path (repeatable; not with --base)",
    )
    parser_inventory.add_argument(
        "--base", help="audit only merge-base(BASE, HEAD)..HEAD; unchanged files become searchable context"
    )
    parser_inventory.add_argument("--shard-lines", type=int, default=DEFAULT_SHARD_LINES)
    parser_inventory.add_argument(
        "--override", action="append", default=[], metavar="PREFIX=CLASS",
        help="force a class for everything under PREFIX (repeatable)",
    )
    parser_inventory.add_argument("--rubric", help="path to the greppable SKILL.md (default: sibling skill)")
    parser_inventory.set_defaults(func=cmd_inventory)

    parser_prompt = subcommands.add_parser("shard-prompt", help="print the complete prompt for one shard")
    parser_prompt.add_argument("--work", required=True)
    parser_prompt.add_argument("--shard", required=True)
    parser_prompt.set_defaults(func=cmd_shard_prompt)

    parser_verify = subcommands.add_parser(
        "verify", help="reconcile shard artifacts against assignments and check evidence"
    )
    parser_verify.add_argument("--work", required=True)
    parser_verify.set_defaults(func=cmd_verify)

    parser_trial = subcommands.add_parser("trial", help="draft vocabulary search proofs for model confirmation")
    parser_trial.add_argument("--work", required=True)
    parser_trial.set_defaults(func=cmd_trial)

    parser_measure = subcommands.add_parser("measure", help="measure blast radii, search trials, and packets")
    parser_measure.add_argument("--work", required=True)
    parser_measure.set_defaults(func=cmd_measure)

    parser_render = subcommands.add_parser("render", help="write the detailed Markdown report")
    parser_render.add_argument("--work", required=True)
    parser_render.add_argument("--out", required=True, help="audit.md path")
    parser_render.set_defaults(func=cmd_render)

    parser_card = subcommands.add_parser("card", help="print the human briefing for a stored detailed report")
    parser_card.add_argument("--work", required=True)
    parser_card.add_argument("--report", required=True, help="absolute path to the stored audit.md")
    parser_card.set_defaults(func=cmd_card)

    args = parser.parse_args()
    raise SystemExit(args.func(args) or 0)


if __name__ == "__main__":
    main()
