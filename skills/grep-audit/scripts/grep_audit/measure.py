"""Vocabulary trials, proof validation, blast radii, packets, and narrative checks."""

import re
import sys
from collections import Counter
from pathlib import Path

from .common import REACH_SURFACES, READ_CLASSES, dump, plural, require_artifact
from .verify import check_accept


def grep_hits(repo, term, by_path, whole_word=True):
    """Return deterministic repository-relative hits for one literal spelling."""
    pattern = (
        re.compile(rf"(?<![0-9A-Za-z_]){re.escape(term)}(?![0-9A-Za-z_])", re.IGNORECASE)
        if whole_word else None
    )
    needle = term.casefold()
    hits = []
    for path in by_path:
        content = (repo / path).read_bytes()
        if b"\0" in content:
            continue
        for line_number, line in enumerate(content.decode("utf-8", "replace").splitlines(), 1):
            matched = pattern.search(line) if whole_word else needle in line.casefold()
            if matched:
                hits.append(f"{path}:{line_number}")
    return hits


def spelling_error(spelling):
    """Reject spellings whose search results cannot carry useful identity."""
    if not any(character.isalnum() for character in spelling):
        return "is only punctuation"
    if len(spelling) == 1:
        return "is a single character"
    return None


def whole_word_spelling(spelling):
    """Protect short and all-capital identities from substring false positives."""
    return len(spelling) < 4 or spelling.isupper()


def spelling_match(text, spelling):
    if whole_word_spelling(spelling):
        pattern = re.compile(
            rf"(?<![0-9A-Za-z_]){re.escape(spelling)}(?![0-9A-Za-z_])", re.IGNORECASE
        )
        return bool(pattern.search(text))
    return spelling.casefold() in text.casefold()


def proof_location(value):
    path, separator, suffix = value.rpartition(":")
    return (path, int(suffix)) if separator and suffix.isdigit() else (value, None)


def proof_match(repo, value, spellings, by_path):
    """Validate a proof and return the exact matched path or source line."""
    if not isinstance(value, str) or not value.strip():
        return "proof must be a non-empty path or path:line", None
    path, line = proof_location(value)
    if path not in by_path:
        return f"path not in inventory: {value}", None
    lines = (repo / path).read_text(errors="replace").splitlines()
    if line is not None and not 1 <= line <= len(lines):
        return f"line out of range: {value}", None
    if any(spelling_match(path, spelling) for spelling in spellings):
        return None, f"path: {path}"
    start, end = (max(0, line - 3), min(len(lines), line + 2)) if line is not None else (0, len(lines))
    for index in range(start, end):
        if any(spelling_match(lines[index], spelling) for spelling in spellings):
            return None, f"{path}:{index + 1}: {' '.join(lines[index].split())}"
    return f"proof contains none of its spellings: {value}", None


def proof_error(repo, value, spellings, by_path):
    return proof_match(repo, value, spellings, by_path)[0]


def cmd_trial(args):
    """Populate draft search proofs by repository class for the model to confirm."""
    work = Path(args.work)
    inventory = require_artifact(work, "inventory.json", "inventory (step 1)")
    vocabulary = require_artifact(work, "vocabulary.json", "seed vocabulary (step 2)")
    repo = Path(inventory["repo"])
    by_path = {file["path"]: file for file in inventory["files"]}
    surface_classes = {
        "owner": ("source", "schema", "script"),
        "wiring": ("source", "script", "config"),
        "contract": ("schema", "config", "source", "docs"),
        "tests": ("test",),
        "absence": ("docs", "config"),
    }
    drafted = 0
    concepts = vocabulary.get("concepts")
    if not isinstance(concepts, list):
        raise SystemExit("vocabulary.json: concepts must be a list")
    for index, concept in enumerate(concepts, 1):
        if not isinstance(concept, dict):
            raise SystemExit(f"vocabulary.json: concept {index} must be an object")
        spellings = concept.get("spellings", [])
        if not isinstance(spellings, list) or not all(isinstance(spelling, str) for spelling in spellings):
            raise SystemExit(f"vocabulary.json: concept {index} spellings must be a list of strings")
        hits = {
            spelling: grep_hits(repo, spelling, by_path, whole_word=whole_word_spelling(spelling))
            for spelling in spellings
        }
        ordered_hits = list(dict.fromkeys(hit for spelling in spellings for hit in hits[spelling]))
        if "documented" not in concept:
            concept["documented"] = next(
                (hit for hit in ordered_hits if by_path[hit.rsplit(":", 1)[0]]["class"] == "docs"), None
            )
            drafted += 1
        reach = concept.setdefault("reach", {})
        for surface, classes in surface_classes.items():
            if surface in reach:
                continue
            reach[surface] = next(
                (hit for hit in ordered_hits if by_path[hit.rsplit(":", 1)[0]]["class"] in classes), None
            )
            drafted += 1
        concept.setdefault("findings", [])
    dump(work / "vocabulary.json", vocabulary)
    print(
        f"trialed: {plural(len(concepts), 'concept')}; "
        f"filled {plural(drafted, 'draft proof')}; confirm every proof and attach finding IDs to misses"
    )


def measure_vocabulary(work, ledger, repo, by_path, finding_ids, problems):
    """Validate concept-level closure and every documented/reach proof."""
    vocabulary = require_artifact(work, "vocabulary.json", "search trials (step 4)")
    concepts = vocabulary.get("concepts")
    if not isinstance(concepts, list):
        problems.append("vocabulary: concepts must be a list")
        concepts = []
    rejected = vocabulary.get("rejected")
    if not isinstance(rejected, list):
        problems.append("vocabulary: rejected must be a list")
        rejected = []
    valid_concepts = []
    for index, concept in enumerate(concepts, 1):
        label = f"concept {index}"
        if not isinstance(concept, dict):
            problems.append(f"vocabulary: {label} must be an object")
            continue
        name = concept.get("concept")
        spellings = concept.get("spellings")
        if not isinstance(name, str) or not name.strip():
            problems.append(f"vocabulary: {label} needs a non-empty concept")
            continue
        label = name
        if not isinstance(spellings, list) or not spellings or not all(
            isinstance(spelling, str) and spelling.strip() for spelling in spellings
        ):
            problems.append(f"vocabulary: {label} needs non-empty spellings")
            continue
        for spelling in spellings:
            if error := spelling_error(spelling):
                problems.append(f"vocabulary: {label} spelling {spelling!r} {error}")
        documented = concept.get("documented")
        documented_match = None
        if "documented" not in concept:
            problems.append(f"vocabulary: {label} has no documented provenance")
            documented_mark, documented_path = "!", None
        elif documented is None:
            documented_mark, documented_path = " ", None
        elif (proof := proof_match(repo, documented, spellings, by_path))[0]:
            problems.append(f"vocabulary: {label} documented {proof[0]}")
            documented_mark, documented_path = "?", documented if isinstance(documented, str) else None
        else:
            documented_mark, documented_path, documented_match = "x", documented, proof[1]
        valid_concepts.append((concept, documented_mark, documented_path, documented_match))
    valid_rejected = []
    for index, rejection in enumerate(rejected, 1):
        label = f"rejected entry {index}"
        if not isinstance(rejection, dict):
            problems.append(f"vocabulary: {label} must be an object")
            continue
        name, spellings, reason = rejection.get("concept"), rejection.get("spellings"), rejection.get("reason")
        if not isinstance(name, str) or not name.strip():
            problems.append(f"vocabulary: {label} needs a non-empty concept")
            continue
        if not isinstance(spellings, list) or not spellings or not all(
            isinstance(spelling, str) and spelling.strip() for spelling in spellings
        ):
            problems.append(f"vocabulary: rejected {name} needs non-empty spellings")
            continue
        if not isinstance(reason, str) or not reason.strip():
            problems.append(f"vocabulary: rejected {name} needs a reason")
            continue
        valid_rejected.append(rejection)
    targets = []
    for concept in concepts:
        if isinstance(concept, dict) and isinstance(concept.get("concept"), str) and isinstance(concept.get("spellings"), list):
            targets.append((
                "merged", concept["concept"],
                {term.casefold() for term in [concept["concept"], *concept["spellings"]] if isinstance(term, str)},
                None,
            ))
    for rejection in valid_rejected:
        targets.append((
            "rejected", rejection["concept"],
            {term.casefold() for term in [rejection["concept"], *rejection["spellings"]]},
            rejection["reason"],
        ))
    resolutions = []
    for index, addition in enumerate(ledger.get("vocabulary_additions", []), 1):
        label = f"addition {index}"
        if not isinstance(addition, dict):
            problems.append(f"vocabulary: {label} must be an object")
            continue
        name, spellings, paths = addition.get("concept"), addition.get("spellings"), addition.get("paths")
        if not isinstance(name, str) or not name.strip():
            problems.append(f"vocabulary: {label} needs a non-empty concept")
            continue
        if not isinstance(spellings, list) or not spellings or not all(
            isinstance(spelling, str) and spelling.strip() for spelling in spellings
        ):
            problems.append(f"vocabulary: addition {name} needs non-empty spellings")
            continue
        if not isinstance(paths, list) or not paths or not all(isinstance(path, str) and path.strip() for path in paths):
            problems.append(f"vocabulary: addition {name} needs defining paths")
        else:
            for value in paths:
                path, _ = proof_location(value)
                if path not in by_path:
                    problems.append(f"vocabulary: addition {name} path not in inventory: {value}")
        terms = list(dict.fromkeys([name, *spellings]))
        folded = {term.casefold() for term in terms}
        matched = next(
            ((disposition, target, adopted, reason) for disposition, target, adopted, reason in targets if adopted & folded),
            None,
        )
        if matched is None:
            problems.append(f"vocabulary: unresolved addition {name}")
            resolutions.append({"concept": name, "disposition": "unresolved", "target": None, "unadopted": terms})
        else:
            disposition, target, adopted, reason = matched
            resolutions.append({
                "concept": name, "disposition": disposition, "target": target,
                "unadopted": [term for term in terms if term.casefold() not in adopted],
                "reason": reason,
            })
    trials = []
    for concept, documented_mark, documented_path, documented_match in valid_concepts:
        name, spellings = concept["concept"], concept["spellings"]
        per_spelling = {
            spelling: grep_hits(repo, spelling, by_path, whole_word=whole_word_spelling(spelling))
            for spelling in spellings
        }
        raw_reach = concept.get("reach")
        if not isinstance(raw_reach, dict):
            problems.append(f"vocabulary: {name} not trialed: reach must contain all five surfaces")
            raw_reach = {}
        missing_keys = [key for key in REACH_SURFACES if key not in raw_reach]
        if missing_keys:
            problems.append(f"vocabulary: {name} not trialed: missing reach {', '.join(missing_keys)}")
        reach, misses = {}, []
        for key in REACH_SURFACES:
            if key not in raw_reach:
                reach[key] = {"mark": "!", "path": None}
                continue
            value = raw_reach[key]
            if value is None:
                reach[key] = {"mark": " ", "path": None}
                misses.append(key)
            elif value == "n/a":
                reach[key] = {"mark": "-", "path": None}
            elif (proof := proof_match(repo, value, spellings, by_path))[0]:
                reach[key] = {"mark": "?", "path": value if isinstance(value, str) else None}
                problems.append(f"vocabulary: {name} {key} {proof[0]}")
            else:
                reach[key] = {"mark": "x", "path": value, "match": proof[1]}
        links = concept.get("findings", [])
        if not isinstance(links, list) or not all(isinstance(finding_id, str) for finding_id in links):
            problems.append(f"vocabulary: {name} findings must be a list of IDs")
            links = []
        unknown = [finding_id for finding_id in links if finding_id not in finding_ids]
        if unknown:
            problems.append(f"vocabulary: {name} references unknown findings: {', '.join(unknown)}")
        if misses and not links:
            problems.append(f"vocabulary: {name} misses {', '.join(misses)} without an accepted finding")
        named = sorted({
            path for path in by_path for spelling in spellings if spelling.casefold() in path.casefold()
        })
        trials.append({
            "concept": name,
            "spellings": spellings,
            "documented": {"mark": documented_mark, "path": documented_path, "match": documented_match},
            "reach": reach,
            "findings": links,
            "hits": sum(len(hits) for hits in per_spelling.values()),
            "hits_by_spelling": {spelling: len(hits) for spelling, hits in per_spelling.items()},
            "hits_by_class": dict(Counter(
                by_path[hit.rsplit(":", 1)[0]]["class"] for hits in per_spelling.values() for hit in hits
            )),
            "named_files": named,
        })
    ledger["vocabulary_rejected"] = valid_rejected
    ledger["vocabulary_resolutions"] = resolutions
    return trials


def check_narrative(narrative, findings, packets, problems):
    """Require short themes that partition findings and point to containing packets."""
    themes = narrative.get("themes")
    if not findings and themes in (None, []):
        return
    if not isinstance(themes, list) or not themes:
        problems.append("narrative: themes must cover every accepted finding")
        return
    if len(themes) > 3:
        problems.append("narrative: themes must contain at most 3 entries")
    packet_findings = {packet["id"]: set(packet["findings"]) for packet in packets}
    seen = Counter()
    for index, theme in enumerate(themes, 1):
        if not isinstance(theme, dict):
            problems.append(f"narrative: theme {index} must be an object")
            continue
        for key in ("title", "explanation"):
            if not isinstance(theme.get(key), str) or not theme[key].strip():
                problems.append(f"narrative: theme {index} needs non-empty {key}")
        if isinstance(theme.get("title"), str) and len(theme["title"]) > 60:
            problems.append(f"narrative: theme {index} title exceeds 60 characters")
        theme_findings = theme.get("findings")
        if not isinstance(theme_findings, list) or not theme_findings:
            problems.append(f"narrative: theme {index} needs finding IDs")
            theme_findings = []
        unknown = [finding_id for finding_id in theme_findings if finding_id not in findings]
        if unknown:
            problems.append(f"narrative: theme {index} has unknown findings {', '.join(unknown)}")
        seen.update(finding_id for finding_id in theme_findings if finding_id in findings)
        theme_packets = theme.get("packets")
        if not isinstance(theme_packets, list) or not theme_packets:
            problems.append(f"narrative: theme {index} needs packet IDs")
            theme_packets = []
        unknown_packets = [packet_id for packet_id in theme_packets if packet_id not in packet_findings]
        if unknown_packets:
            problems.append(f"narrative: theme {index} has unknown packets {', '.join(unknown_packets)}")
        assigned = set().union(*(packet_findings.get(packet_id, set()) for packet_id in theme_packets))
        missing = [finding_id for finding_id in theme_findings if finding_id in findings and finding_id not in assigned]
        if missing:
            problems.append(f"narrative: theme {index} packets do not contain findings {', '.join(missing)}")
    missing = [finding_id for finding_id in findings if seen[finding_id] == 0]
    duplicates = [finding_id for finding_id, count in seen.items() if count > 1]
    if missing:
        problems.append(f"narrative: findings absent from themes: {', '.join(missing)}")
    if duplicates:
        problems.append(f"narrative: findings in more than one theme: {', '.join(duplicates)}")


def topological(packets):
    """Return packet IDs in dependency order and reject unknowns or cycles."""
    after = {packet["id"]: list(packet.get("after", [])) for packet in packets}
    order, seen = [], set()

    def visit(packet_id, stack):
        if packet_id in seen:
            return
        if packet_id in stack:
            sys.exit(f"packet dependency cycle at {packet_id}")
        for dependency in after.get(packet_id, []):
            if dependency not in after:
                sys.exit(f"packet {packet_id} depends on unknown packet {dependency}")
            visit(dependency, stack | {packet_id})
        seen.add(packet_id)
        order.append(packet_id)

    for packet_id in sorted(after):
        visit(packet_id, frozenset())
    return order


def validate_packets(value, problems):
    """Discard malformed model-authored packet entries after recording precise problems."""
    if not isinstance(value, list):
        problems.append("packets.json: packets must be a list")
        return []
    packets = []
    for index, packet in enumerate(value, 1):
        label = f"packet entry {index}"
        if not isinstance(packet, dict):
            problems.append(f"{label}: must be an object")
            continue
        if not isinstance(packet.get("id"), str) or not packet["id"]:
            problems.append(f"{label}: needs a non-empty id")
            continue
        if not isinstance(packet.get("title"), str) or not packet["title"]:
            problems.append(f"packet {packet['id']}: needs a non-empty title")
            continue
        if not isinstance(packet.get("findings"), list) or not all(
            isinstance(finding_id, str) for finding_id in packet["findings"]
        ):
            problems.append(f"packet {packet['id']}: findings must be a list of IDs")
            continue
        if not isinstance(packet.get("after", []), list) or not all(
            isinstance(packet_id, str) for packet_id in packet.get("after", [])
        ):
            problems.append(f"packet {packet['id']}: after must be a list of packet IDs")
            continue
        packets.append(packet)
    return packets


def cmd_measure(args):
    """Recompute every derived measure and fail while any contract remains open."""
    work = Path(args.work)
    inventory = require_artifact(work, "inventory.json", "inventory (step 1)")
    ledger = require_artifact(work, "ledger.json", "verify (steps 3-4)")
    repo = Path(inventory["repo"])
    by_path = {file["path"]: file for file in inventory["files"]}
    problems = ledger["measure_problems"] = []
    ids = {finding["id"]: finding for finding in ledger["findings"]}
    for finding in ledger["findings"]:
        symbol = finding.get("symbol")
        if symbol:
            hits = grep_hits(repo, symbol, by_path)
            finding["blast"] = {
                "symbol": symbol,
                "hits": len(hits),
                "files": len({hit.rsplit(":", 1)[0] for hit in hits}),
                "by_class": dict(Counter(by_path[hit.rsplit(":", 1)[0]]["class"] for hit in hits)),
                "paths": hits,
            }
            new = finding.get("new_symbol")
            if new:
                finding["blast"]["new_symbol"] = new
                finding["blast"]["new_symbol_hits"] = len(grep_hits(repo, new, by_path))
            if not finding.get("accept"):
                finding["accept"] = (
                    [{"argv": ["git", "grep", "-nw", "--", new], "expect": "definition and every call site"}]
                    if new else []
                )
                finding["accept"].append({
                    "argv": ["git", "grep", "-nw", "--", symbol],
                    "expect": "0 hits" if new else "only the surviving owner",
                })
        elif not finding.get("accept"):
            finding["accept"] = []
    trials = measure_vocabulary(work, ledger, repo, by_path, ids, problems)
    # Follow-up findings are reported beside the change but stay out of packets, themes, and the score.
    scored = {finding_id: finding for finding_id, finding in ids.items() if finding.get("scope") != "follow-up"}
    if inventory.get("range"):
        # A boundary lead is only a verification when it also names the maintained source or generator
        # it was checked against; context paths qualify without becoming read coverage.
        lead_paths = [
            lead["paths"] for lead in ledger.get("cross_shard_leads", []) if isinstance(lead.get("paths"), list)
        ]
        for file in inventory["files"]:
            if file["treatment"] == "boundary" and not any(
                file["path"] in paths and any(
                    path != file["path"] and path in by_path and by_path[path]["class"] in READ_CLASSES
                    for path in paths
                )
                for paths in lead_paths
            ):
                problems.append(
                    f"changed {file['class']} file has no cross_shard_leads entry naming it together with the "
                    f"maintained source or generator path it was verified against: {file['path']}"
                )
    packet_artifact = require_artifact(work, "packets.json", "packets and narrative (step 5)")
    if not isinstance(packet_artifact, dict):
        raise SystemExit("packets.json: root must be an object")
    packets = validate_packets(packet_artifact.get("packets"), problems)
    assigned = Counter()
    for packet_id, count in sorted(Counter(packet["id"] for packet in packets).items()):
        if count > 1:
            problems.append(f"packet {packet_id}: id used {count} times")
    for packet in packets:
        unknown = [finding_id for finding_id in packet["findings"] if finding_id not in ids]
        if unknown:
            problems.append(f"packet {packet['id']}: unknown findings {', '.join(unknown)}")
        follow_ups = [finding_id for finding_id in packet["findings"] if finding_id in ids and finding_id not in scored]
        if follow_ups:
            problems.append(f"packet {packet['id']}: follow-up findings are not packeted: {', '.join(follow_ups)}")
        if error := check_accept(packet.get("accept")):
            problems.append(f"packet {packet['id']}: {error}")
        assigned.update(packet["findings"])
        creates = packet.get("creates", [])
        if not isinstance(creates, list) or not all(isinstance(path, str) and path for path in creates):
            problems.append(f"packet {packet['id']}: creates must be a list of repository-relative paths")
            creates = []
        valid_creates = []
        for path in creates:
            candidate = Path(path)
            if candidate.is_absolute() or ".." in candidate.parts:
                problems.append(f"packet {packet['id']}: creates path must be repository-relative: {path}")
            elif path in by_path:
                problems.append(f"packet {packet['id']}: creates path already exists in inventory: {path}")
            else:
                valid_creates.append(path)
        packet["creates"] = sorted(set(valid_creates))
        paths = {ids[finding_id]["path"] for finding_id in packet["findings"] if finding_id in ids}
        blast_paths = {
            hit.rsplit(":", 1)[0]
            for finding_id in packet["findings"] if finding_id in ids
            for hit in ids[finding_id].get("blast", {}).get("paths", [])
        }
        packet["files"] = sorted(paths | blast_paths | set(packet["creates"]))
        packet["tests"] = sorted(
            path for path in packet["files"] if path in by_path and by_path[path]["class"] == "test"
        )
    unassigned = [finding_id for finding_id in scored if assigned[finding_id] == 0]
    duplicates = [finding_id for finding_id, count in assigned.items() if count > 1]
    if duplicates:
        problems.append(f"findings in more than one packet: {', '.join(duplicates)}")
    narrative = require_artifact(work, "narrative.json", "packets and narrative (step 5)")
    if not isinstance(narrative, dict):
        raise SystemExit("narrative.json: root must be an object")
    clean = [
        property_name for property_name in inventory["properties"]
        if not any(finding["property"] == property_name for finding in scored.values())
        and property_name not in narrative.get("properties_not_applicable", {})
    ]
    for property_name in clean:
        if not narrative.get("property_checks", {}).get(property_name):
            problems.append(f"narrative: clean property has no property_checks evidence: {property_name!r}")
    check_narrative(narrative, scored, packets, problems)
    order = topological(packets)
    ledger["trials"] = trials
    ledger["packets"] = [next(packet for packet in packets if packet["id"] == packet_id) for packet_id in order]
    ledger["unassigned_findings"] = unassigned
    dump(work / "ledger.json", ledger)
    print(
        f"measured: {sum('blast' in finding for finding in ledger['findings'])} blast radii, "
        f"{len(trials)} search trials, {len(packets)} packets ({len(unassigned)} findings unassigned); "
        f"problems {len(problems)}"
    )
    for problem in problems:
        print(f"  problem: {problem}")
    return 1 if problems else 0
