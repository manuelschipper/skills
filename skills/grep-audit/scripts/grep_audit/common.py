"""Shared artifact, formatting, and rubric contracts for every audit stage."""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

READ_CLASSES = ("source", "test", "config", "script", "schema", "docs")
BOUNDARY_CLASSES = ("generated", "vendored")
LISTED_CLASSES = ("data", "binary")
CLASS_ORDER = READ_CLASSES + BOUNDARY_CLASSES + LISTED_CLASSES
# A change-range audit gives unchanged files the `context` treatment: searchable, never read or scored.
INITIAL_STATUS = {"read": "pending", "boundary": "boundary-only", "listed": "listed", "context": "context"}
FINDING_SCOPES = ("change", "follow-up")
SEVERITIES = ("HIGH", "MED", "LOW")
REACH_SURFACES = ("owner", "wiring", "contract", "tests", "absence")
SEVERITY_DEFINITIONS = {
    "HIGH": "A domain search cannot reach the concept's owner or contract.",
    "MED": "Search reaches the owner or contract only after extra reads or context reconstruction.",
    "LOW": "Search succeeds, but inconsistent names or structure still add friction.",
}
DIMENSIONS = (
    ("Names & vocabulary", (
        "Use distinctive domain names",
        "Use one spelling per concept",
        "Keep names true as behavior changes",
        "Keep operational strings whole",
    )),
    ("Ownership & layout", (
        "Give each definition one home",
        "Make paths and exports say where code lives",
        "Put the searchable explanation at the definition",
        "Make imports readable as contracts",
        "Give each cohesive concept one boundary",
        "Treat line count as a diagnostic, not a design rule",
    )),
    ("Contracts & boundaries", (
        "Use precise identity and state types",
        "Encode authority and validate boundaries",
        "State ownership and dependency direction",
    )),
    ("Execution flow", (
        "Show cross-cutting composition",
        "Keep orchestration visible and side effects owned",
    )),
    ("Tests & repository memory", (
        "Make tests and fixtures answer to feature terms",
        "Record expected absence",
        "Remove obsolete paths and mark retained dead ends",
        "Record repository-wide search conventions",
    )),
)
DEFAULT_SHARD_LINES = 10000
MAX_SHARD_FILES = 400
REPORT_WIDTH = 100
CARD_WIDTH = 78
SEVERITY_CREDIT = {"HIGH": 0.0, "MED": 0.5, "LOW": 0.75}
GREP_WORDMARK = """                        ██████  ██████  ███████ ██████
                       ██       ██   ██ ██      ██   ██
                       ██  ███  ██████  █████   ██████
                       ██   ██  ██   ██ ██      ██
                        ██████  ██   ██ ███████ ██

                              GREPPABILITY AUDIT"""


def git(repo, *args, check=True):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    if check and result.returncode not in (0, 1):
        sys.exit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def load(path, default=None):
    path = Path(path)
    if not path.exists():
        if default is not None:
            return default
        sys.exit(f"missing {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as error:
        sys.exit(f"invalid JSON in {path.name} at line {error.lineno}, column {error.colno}")


def require_artifact(work, name, step):
    """Load a stage input or name the workflow step that creates it."""
    path = Path(work) / name
    if not path.exists():
        sys.exit(f"missing {name} (run {step})")
    return load(path)


def dump(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=1, sort_keys=True) + "\n")


def rubric_headings(rubric_path):
    text = Path(rubric_path).read_text()
    headings = [line[4:].strip() for line in text.splitlines() if line.startswith("### ")]
    if not headings:
        sys.exit(f"no '### ' properties found in {rubric_path}")
    return headings


def rubric_body(rubric_path):
    """Return the rubric without skill frontmatter for shard assessment."""
    text = Path(rubric_path).read_text()
    if text.startswith("---"):
        text = text.split("\n---\n", 1)[1]
    return text.strip()


def default_rubric():
    return Path(__file__).resolve().parents[3] / "greppable" / "SKILL.md"


def ascii_safe(text):
    return str(text).encode("ascii", "backslashreplace").decode("ascii")


def bar(value, unit, width=40):
    """Render one mark for every unit, with one mark for any nonzero remainder."""
    if value <= 0 or unit <= 0:
        return ""
    return "#" * min(width, max(1, round(value / unit)))


def fmt(number):
    return f"{number:,}"


def wrap(text, width=REPORT_WIDTH, indent=""):
    return textwrap.fill(
        " ".join(text.split()), width=width, subsequent_indent=indent,
        break_long_words=False, break_on_hyphens=False,
    )


def field(label, text, gutter=2, label_width=9):
    """Render one report field with wrapped continuation indentation."""
    first = " " * gutter + f"{label:{label_width}} "
    return textwrap.fill(
        " ".join(str(text).split()), width=REPORT_WIDTH, initial_indent=first,
        subsequent_indent=" " * len(first), break_long_words=False, break_on_hyphens=False,
    )


def plural(count, singular):
    return f"{count} {singular}" + ("" if count == 1 else "s")
