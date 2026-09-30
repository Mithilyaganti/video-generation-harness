# checkpoint/09-record-script

Bunny plus the Pi extension stayed at 9/12 because trail-flask, annex-badge, and chapel-candle each kept 17/18. The failed gate was `plant_not_deleted`. The picture, the record, and the log already had the plant. The code snapshot treated a script that draws `record.json` as a deletion when the plant id was not a literal in `scene.py`.

The snapshot now counts a script that draws `record["plant"]`, or draws every object when the plant is already in that list. A script that never reads the plant still fails. The same three scripts were rendered again and scored again. No new model call.

| Scene | Cause | Before | After |
| --- | --- | --- | --- |
| trail-flask | Pi plugin, record-driven script | 17/18 | 18/18 |
| annex-badge | Pi plugin, plant on the object list | 17/18 | 18/18 |
| chapel-candle | Pi plugin, record-driven script | 17/18 | 18/18 |

Bunny plus the extension on these twelve scenes: 9/12 before, 12/12 after, on the same kept scripts.

`python3 -m harness.pi_clip --selftest`, `python3 -m harness --selftest`, `python3 -m harness.fair_run --selfcheck`, and `python3 check.py selftest` all exited 0 before this branch was pushed.
