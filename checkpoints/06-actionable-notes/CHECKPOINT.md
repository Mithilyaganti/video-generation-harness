# checkpoint/06-actionable-notes

The cafe and pier notes were not edited. The same expected-versus-found lines were tried on twelve new scenes. One-shot is the first reply: no retry and no notes. The harness is that same reply, then a crash retry if there is no clip, then at most two rounds of those notes. The kept clip is the best attempt.

Strict is the headline. First reply 6/12. After the notes, 12/12. Valid clips were already 12/12, and the picture was already 12/12. No scene used the crash retry.

| Scene | First strict | Kept strict | Note rounds |
| --- | --- | --- | --- |
| orchard-basket | 18/18 | 18/18 | 0 |
| pantry-jar | 10/18 | 18/18 | 1 |
| quay-cleat | 17/18 | 18/18 | 1 |
| ridge-flag | 18/18 | 18/18 | 0 |
| study-globe | 9/18 | 18/18 | 2 |
| terrace-jug | 10/18 | 18/18 | 1 |
| trail-flask | 18/18 | 18/18 | 0 |
| ward-chart | 18/18 | 18/18 | 0 |
| yard-hose | 18/18 | 18/18 | 0 |
| annex-badge | 10/18 | 18/18 | 1 |
| booth-token | 17/18 | 18/18 | 2 |
| chapel-candle | 18/18 | 18/18 | 0 |

The six that moved had a log id the claim could not key, or a later snapshot that dropped the plant. The notes named the expected id and the id that was found.

Every kept clip passed the shortcut tests: no-video, single-frame, and shuffled frames. Four first replies failed those three because the log had no key yet. After the notes, those four passed them too.

Checkpoint 05 is the crash retry, which raised valid clips from 9/12 to 12/12. This result is the strict score on new scenes.

`python3 -m harness --selftest`, `python3 -m harness.fair_run --selfcheck`, and `python3 check.py selftest` all exited 0 before this branch was pushed.
