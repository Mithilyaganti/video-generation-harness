# checkpoint/07-dsh-plugins

Same twelve checkpoint 06 scenes. Same brief, same schema text, same checker. Five arms, one key, in parallel. Muse stayed out. `deepseek-ai/deepseek-harness` is not forked.

Space Bunny Free won both harnesses, 12/12 strict. On flash, the plugin harness beat the custom harness by one scene, and plain dsh produced no clip.

| Arm | Harness | Model | Strict | Valid clip | Picture | Shortcuts | Crash rounds | Note rounds | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | Custom, checkpoint 06 | deepseek-v4.1-flash | 10/12 | 11/12 | 11/12 | 11/12 | 8 | 10 | 4604 |
| B | dsh plus plugins | deepseek-v4.1-flash | 11/12 | 11/12 | 11/12 | 11/12 | 2 | 2 | 2886 |
| C | Plain dsh | deepseek-v4.1-flash | 0/12 | 0/12 | 0/12 | 0/12 | 0 | 0 | 1304 |
| D | Custom, checkpoint 06 | space-bunny-free | 12/12 | 12/12 | 12/12 | 12/12 | 0 | 6 | 3600 |
| E | dsh plus plugins | space-bunny-free | 12/12 | 12/12 | 12/12 | 12/12 | 4 | 6 | 3974 |

Mean seconds: A 384, B 241, C 109, D 300, E 331.

| Scene | A | B | C | D | E |
| --- | --- | --- | --- | --- | --- |
| orchard-basket | 17/18 | 18/18 | 0/18 | 18/18 | 18/18 |
| pantry-jar | 18/18 | 18/18 | 0/18 | 18/18 | 18/18 |
| quay-cleat | 18/18 | 18/18 | 2/18 | 18/18 | 18/18 |
| ridge-flag | 18/18 | 18/18 | 0/18 | 18/18 | 18/18 |
| study-globe | 18/18 | 0/18 | 0/18 | 18/18 | 18/18 |
| terrace-jug | 18/18 | 18/18 | 0/18 | 18/18 | 18/18 |
| trail-flask | 18/18 | 18/18 | 0/18 | 18/18 | 18/18 |
| ward-chart | timeout | 18/18 | 0/18 | 18/18 | 18/18 |
| yard-hose | 18/18 | 18/18 | 2/18 | 18/18 | 18/18 |
| annex-badge | 18/18 | 18/18 | 2/18 | 18/18 | 18/18 |
| booth-token | 18/18 | 18/18 | 0/18 | 18/18 | 18/18 |
| chapel-candle | 18/18 | 18/18 | 0/18 | 18/18 | 18/18 |

A orchard-basket is a valid clip and the picture is there. Strict is 17/18 because the script fence came before the record fence. A ward-chart made no clip: the Go read timed out. B study-globe used both crash rounds and both note rounds, and none of the five replies left a valid clip. Plain C kept the schema in the task and was scored from files the agent wrote. The replies contain the fences. Three scenes also wrote a record and a script. None wrote an mp4.

Harness comparison on flash is B, then A, then C. Inside the custom harness, D beat A. Inside dsh, E beat B. Every kept valid clip passed the shortcut tests.

`node dsh/selftest.mjs`, `python3 -m harness.dsh_selftest`, `python3 -m harness --selftest`, `python3 -m harness.fair_run --selfcheck`, and `python3 check.py selftest` all exited 0 before this branch was pushed.
