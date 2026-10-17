# Climb

Repeated attempts toward the Brief's Goal. Each attempt is kept when it is better than the
last kept commit and reverted otherwise; the Climb Log carries every attempt into the next
one. The climb ends with one fixing review of everything kept.

The Goal is fixed before the first attempt. It is judged one of two ways:

- **Measured**: the Brief has a `## Measure` section. You run the command; nobody else's
  numbers count.

  ````markdown
  ## Measure
  ```sh
  ./bench/p95.sh
  ```
  Lower is better. Runs: 5. Target: 40.
  ````

  The command's last output line must be a bare number. Each measurement runs the command
  once untimed to warm caches, then `Runs` times. An attempt is kept when its median beats the
  kept median by more than the noise (the larger of the two runs' spreads).
  `Target` is optional.
- **Judged**: no Measure. A fresh reviewer judges each attempt against the Goal: better,
  same, or worse, and whether the Goal is met.

The Brief also states the attempt budget and how many attempts in a row without a gain end
the climb. Ask the user when the request leaves either out. The Brief is fixed once the
baseline is scored.

1. `coach.py start ID --approved "..."`, then `coach.py score ID` to record the baseline. A measured baseline
   that already reports `goal_met` goes stuck: there is nothing to climb. Then
   `coach.py spawn ID builder`.
2. Attempt: `coach.py send ID build`, wait, `coach.py accept ID build`. Outcome `spec-gap` or
   `blocked`: go stuck. No new commit: send the builder again.
3. Judged climbs only: `coach.py verify ID`. When it passes, run a review round for `judge`,
   then `coach.py state ID build`. When it fails, go straight to step 4, which reverts the
   attempt.
4. `coach.py score ID`. It verifies the attempt when step 3 did not, measures or reads the
   judgment, and keeps or reverts the commit. A reverted attempt stays under
   `refs/coach/ID/try-N`.
5. Stop when `goal_met` is true, the budget is spent, or `no_gain_streak` reaches the limit.
   Otherwise return to step 2.
6. When no attempt was kept, go stuck and ask the user whether to drop the record. Otherwise run a review round for `fix-review`; this pass hunts for gamed
   measurements and regressions across the whole climb. Then `coach.py verify ID`. Verdict
   `findings` or a failed verification goes stuck.
7. Measured climbs: `coach.py score ID --final`. `gain_lost: true` means the fixes gave back
   the gain: go stuck.
8. `coach.py finish ID`. On exit 2 or 3, `coach.py state ID build`, run a build round, and
   return to step 6. Then retire the builder. Report the baseline, every kept attempt, and
   the final value or judgment.

Done when the record is `done`.
