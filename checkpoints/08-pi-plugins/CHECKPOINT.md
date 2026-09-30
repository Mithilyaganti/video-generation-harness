# checkpoint/08-pi-plugins

The checkpoint 06 loop now runs as a bare Pi extension. Not Oh My Pi. Not a fork of pi-mono. Plain Pi gets the same schema text and no extension. Thinking is `--thinking low`. There is no import denylist.

Strict is the headline. Flash plus the extension: 12/12, all on the first reply, so the settle loop did not run. Plain flash: 8/12. Bunny plus the extension: 9/12, from 8/12 on the first reply. Checkpoint 06's own harness was 12/12 on bunny. This port is lower.

| Scene | Flash+ext | Plain flash | Bunny first | Bunny kept | Bunny notes |
| --- | --- | --- | --- | --- | --- |
| orchard-basket | 18/18 | 17/18 | 18/18 | 18/18 | 0 |
| pantry-jar | 18/18 | 18/18 | 10/18 | 18/18 | 1 |
| quay-cleat | 18/18 | 17/18 | 18/18 | 18/18 | 0 |
| ridge-flag | 18/18 | 18/18 | 18/18 | 18/18 | 0 |
| study-globe | 18/18 | 18/18 | 18/18 | 18/18 | 0 |
| terrace-jug | 18/18 | 18/18 | 18/18 | 18/18 | 0 |
| trail-flask | 18/18 | 18/18 | 17/18 | 17/18 | 2 |
| ward-chart | 18/18 | 18/18 | 18/18 | 18/18 | 0 |
| yard-hose | 18/18 | 17/18 | 18/18 | 18/18 | 0 |
| annex-badge | 18/18 | 18/18 | 17/18 | 17/18 | 2 |
| booth-token | 18/18 | 17/18 | 18/18 | 18/18 | 0 |
| chapel-candle | 18/18 | 18/18 | 17/18 | 17/18 | 2 |

Crash rounds were 0 on every scene. Valid clips and the picture were 12/12 on every arm. The plain misses, and the three bunny misses that stayed, are `plant_not_deleted` at 17/18. Pantry is the one note round that moved a score, from 10/18 to 18/18. Every kept clip passed the shortcut tests.

Flash 12/12 versus plain 8/12 is two samples. The extension never sent a note on flash.

Booth's first bunny call wrote `log.json` as a list. The scorer threw, and that call is not in the table. After a list log is treated as no frames, the scene was run again. That reply passed 18/18.

Clips are under `media/<scene>/<arm>/pi-1/`.

`python3 -m harness.pi_clip --selftest`, `python3 -m harness --selftest`, `python3 -m harness.fair_run --selfcheck`, and `python3 check.py selftest` all exited 0 before this branch was pushed.
