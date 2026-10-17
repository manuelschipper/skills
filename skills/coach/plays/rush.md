# Rush

One builder, then your own verification. No review.

1. `coach.py start ID --approved "..."`, then `coach.py spawn ID builder`.
2. A build round.
3. `coach.py finish ID`. On exit 2 or 3, run a build round and finish again.
4. `coach.py retire ID builder`.

Done when the record is `done`.
