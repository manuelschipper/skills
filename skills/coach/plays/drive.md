# Drive

The builder and a read-only reviewer go back and forth until a review passes with no open
blockers. The same builder session works every round; each review gets a fresh reviewer, who
reads every earlier review.

1. `coach.py start ID --approved "..."`, `coach.py spawn ID builder`, then a build round.
2. A review round for `review`.
   - A nonempty `valve`: go stuck, quoting the valve and the open blockers.
   - Verdict `pass`: go to step 3.
   - Verdict `findings`: `coach.py state ID build`, a build round (a `valve` from its
     `accept` also goes stuck), then repeat step 2.
3. `coach.py finish ID`. On exit 2 or 3, `coach.py state ID build`, run a build round, and
   return to step 2: the repair gets reviewed.
4. `coach.py retire ID builder`.

Done when the record is `done`.

The valve stops a drive that is not converging: a repair round with no commit, a finding that
reopens one marked resolved, or findings still open at round 6. It hands the call to the user
rather than ending the drive.
