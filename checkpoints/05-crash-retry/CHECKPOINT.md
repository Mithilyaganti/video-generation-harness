# checkpoint/05-crash-retry

A working clip is part of the harness. On twelve new scenes, one-shot is the first reply and gets no second chance. The other side starts from that same reply. If the reply does not leave a clip, it may try twice more, and the only added text is the script error.

A valid clip means the script exited 0 and `clip.mp4` exists. First replies: 9/12 valid, 5/12 strict, 9/12 picture. After the retry: 12/12 valid, 6/12 strict, 12/12 picture. The nine clips that already existed were kept. The three new clips are barn-halter, diner-bottle, and pond-net.

| Scene | First valid | First strict | First picture | Kept valid | Kept strict | Kept picture |
| --- | --- | --- | --- | --- | --- | --- |
| barn-halter | no | 0/18 | no | yes | 9/18 | yes |
| bath-soap | yes | 10/18 | yes | yes | 10/18 | yes |
| cabin-axe | yes | 18/18 | yes | yes | 18/18 | yes |
| diner-bottle | no | 3/18 | no | yes | 10/18 | yes |
| field-sickle | yes | 18/18 | yes | yes | 18/18 | yes |
| gym-towel | yes | 18/18 | yes | yes | 18/18 | yes |
| hall-umbrella | yes | 10/18 | yes | yes | 10/18 | yes |
| kiln-glaze | yes | 18/18 | yes | yes | 18/18 | yes |
| mill-sack | yes | 10/18 | yes | yes | 10/18 | yes |
| pond-net | no | 16/18 | no | yes | 18/18 | yes |
| roof-nail | yes | 10/18 | yes | yes | 10/18 | yes |
| vault-seal | yes | 18/18 | yes | yes | 18/18 | yes |

Diner is the traceback. `os.makedirs` hit a folder the sandbox had already created, and the next reply then failed with `NameError` on `sys`. The second traceback produced the clip. Barn's first reply had no Python, so the retry had no traceback. Pond's script had already exited 0; copying the frames raised `Errno 5`, and the rerun passed strict.

Cafe and pier reached 18/18 once the notes said the expected id and the id that was found. Those are the same clips that had stalled at 10/18. They are not this held-out result.

Checkpoint 03 is not this result. Checkpoint 04 is the shared schema wording, which helped both sides equally.

`python3 -m harness --selftest`, `python3 -m harness.fair_run --selfcheck`, and `python3 check.py selftest` all exited 0 before this branch was pushed.
