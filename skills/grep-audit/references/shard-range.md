## Change-range assignment

Your files are the changed maintained files of this range. The other {{CONTEXT_COUNT}} in the
repository are unchanged context: search them freely for owners, callers, contracts, and tests,
but read in full only your assignment. Give every finding two extra fields; a finding that omits
either is dropped, and neither is inferred from the path, because an untouched pre-existing line
of a modified file needs your causality judgment:

- `scope`: `change` when the fix is directly necessary because of this change, including a fix
  on an unchanged file the change now requires; `follow-up` for pre-existing debt the change
  merely sits beside, such as untouched lines of a modified file. A follow-up is reported and
  never scored.
- `traces_to`: the changed, renamed (old or new path), or deleted path that makes the finding
  relevant; for a finding caused by the change on a changed file, that file's own path.

A `cross_shard_leads` entry about a changed generated or vendored file lists that file together
with the maintained source or generator path you verified it against; a lead naming only the
generated file is not a verification.

Renamed in this range:

{{RENAMED}}

Deleted in this range (a surviving reference to one of these is a finding on the referrer):

{{DELETED}}
