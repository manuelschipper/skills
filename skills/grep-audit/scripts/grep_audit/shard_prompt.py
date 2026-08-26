"""Complete, resumable prompt construction for one audit shard."""

import sys
from pathlib import Path

from .common import plural, require_artifact, rubric_body


def cmd_shard_prompt(args):
    """Print the exact prompt a shard reader must receive."""
    work = Path(args.work)
    inventory = require_artifact(work, "inventory.json", "inventory (step 1)")
    shards = require_artifact(work, "shards.json", "inventory (step 1)")["shards"]
    shard = next((value for value in shards if value["id"] == args.shard), None)
    if shard is None:
        sys.exit(f"unknown shard {args.shard}")
    template = (Path(__file__).resolve().parents[2] / "references" / "shard-prompt.md").read_text()
    by_path = {file["path"]: file for file in inventory["files"]}
    files = "\n".join(
        f"- {path} ({by_path[path]['class']}, {plural(by_path[path]['lines'], 'line')}"
        + (f"; renamed from {by_path[path]['old_path']}" if by_path[path].get("old_path") else "")
        + ")"
        for path in shard["files"]
    )
    audited = inventory.get("range")
    if audited:
        deleted = [change["path"] for change in audited["changed"] if change["status"] == "D"]
        renamed = [change for change in audited["changed"] if change.get("old_path")]
        context = sum(file["treatment"] == "context" for file in inventory["files"])
        audit_kind = (
            f"a change-range greppability audit of `{inventory['repo']}` covering "
            f"`{audited['merge_base'][:12]}..{audited['head'][:12]}` (base `{audited['base_input']}`)"
        )
        range_block = (Path(__file__).resolve().parents[2] / "references" / "shard-range.md").read_text().strip()
        range_block = (
            range_block.replace("{{CONTEXT_COUNT}}", plural(context, "unchanged file"))
            .replace("{{DELETED}}", "\n".join(f"- {path}" for path in deleted) or "- (none)")
            .replace(
                "{{RENAMED}}",
                "\n".join(f"- {change['old_path']} -> {change['path']}" for change in renamed) or "- (none)",
            )
        )
    else:
        audit_kind = f"a whole-repository greppability audit of `{inventory['repo']}`"
        range_block = ""
    vocabulary = require_artifact(work, "vocabulary.json", "seed vocabulary (step 2)")["concepts"]
    vocab = "\n".join(
        f"- {concept['concept']}: {', '.join(concept['spellings'])}" for concept in vocabulary
    ) or "- (none recorded yet)"
    filled = (
        template.replace("{{SHARD_ID}}", shard["id"])
        .replace("{{SHARD_COUNT}}", str(len(shards)))
        .replace("{{AUDIT_KIND}}", audit_kind)
        .replace("{{RANGE}}\n\n", f"{range_block}\n\n" if range_block else "")
        .replace("{{ARTIFACT}}", str(work / "shards" / f"{shard['id']}.json"))
        .replace("{{PROPERTIES}}", "\n".join(f"- {heading}" for heading in inventory["properties"]))
        .replace("{{VOCABULARY}}", vocab)
        .replace("{{FILES}}", files)
        .replace("{{RUBRIC}}", rubric_body(inventory["rubric"]))
    )
    print(filled)
