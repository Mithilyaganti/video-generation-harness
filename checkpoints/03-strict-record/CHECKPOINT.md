# checkpoint/03-strict-record

The strict checker is the pitch number. The easy picture score stays where it was.

Plain `space-bunny-free` on eight new scenes: **0/8** strict. The staged harness on the same scenes: **8/8** strict, 18/18 gates on each clip.

The harness writes `record.json` before the renderer, draws that record, and logs the timing. The plant stays up for two seconds, so a 1 fps sample still hits it. The trap is a false order question. The answer key matches the log. Plain leaves out the record, so the plant is not verified from one, and the other strict gates fail with it.

`python3 -m harness --selftest` and `python3 check.py selftest` in the eval-checks directory both exited 0 before this branch was pushed.

Numbers are in `harness-progress.md` beside this file, and in the store progress doc.
