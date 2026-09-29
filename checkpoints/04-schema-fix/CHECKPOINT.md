# checkpoint/04-schema-fix

The record schema was unclear, and that was a real miss. The wording now lists every frame index, and it puts the full true sentence in the first answer. Both sides got the same words. The repair loop did not get a private copy.

Strict passes went from 0/4 to 2/4 for one-shot and for repair. The two passes are first replies. The wording helps both sides equally.

| Scene | One-shot strict | One-shot picture | Repair strict | Repair picture |
| --- | --- | --- | --- | --- |
| shed-wrench | 1, 18/18 | yes | 1, 18/18 | yes |
| cafe-spoon | 0, 3/18 | no | 0, 10/18 | yes |
| loft-violin | 1, 18/18 | yes | 1, 18/18 | yes |
| pier-bucket | 0, 3/18 | no | 0, 10/18 | yes |

Checkpoint 03 is not this result. That branch compared a plain script that was never asked for a record with a compiler that did not ask the model to draw.

`python3 -m harness --selftest` and `python3 check.py selftest` both exited 0 before this branch was pushed.
