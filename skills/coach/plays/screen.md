# Screen

One builder, then one fresh reviewer who reviews and fixes in a single pass. Nobody reviews
the reviewer's fixes; your verification is the last check.

1. `coach.py start ID --approved "..."`, `coach.py spawn ID builder`, then a build round.
2. A review round for `fix-review`, then `coach.py verify ID`.
   - Verdict `findings` means a blocking finding is still unfixed: go stuck with it.
   - A failed verification means the reviewer's fixes broke a check: go stuck.
3. `coach.py finish ID`. On exit 2 or 3, `coach.py state ID build`, run a build round, and
   return to step 2.
4. `coach.py retire ID builder`.

Done when the record is `done`.
