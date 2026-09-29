# Harness progress

Plain language. No key. The two brief files were not on this machine.

## Models

Clips are generated with `space-bunny-free`. `longcat-2.5-preview-free` was not needed. There is no free MiMo id, so MiMo was not called. `muse-spark-1.3-contributor` is the only allowed judge, and the Go price table bills it, so it was not called. No paid judge was swapped in. `deepseek-v4.1-flash` has not been used yet.

## What failed first

Plain means one Python script and no extra harness. The first three scenes never became clips. The model spent the whole token budget thinking (`finish_reason` length, 6000 reasoning tokens) and sent no script.

| Scene | Plant in frames | Trap false | Clip |
| --- | --- | --- | --- |
| desk | no | no | no |
| workshop | no | no | no |
| kitchen | no | no | no |

Plant and trap accuracy before the fix: 0/3.

## What the trace said to change

Cap the thinking. A short check of the desk brief then named the fern and the false water-bottle question. The next full replies did write scripts, and both scripts contained the plant. The harness then refused to run them because they import `os` to make the output folder.

| Scene | Plant in the script | Plant in frames | Trap false |
| --- | --- | --- | --- |
| desk | yes | no | no |
| kitchen (new) | yes | no | no |

Accuracy with the thinking cap alone: still 0/2, because nothing was drawn.

## After the script was allowed to run

Same two scripts, no new model call. `os` is allowed. The trap is judged from the picture and the question text, not from a required reason token. The checker self-test still rejects a plant that never hides, a blank clip, a deleted plant, a late record, and a repeated scene.

| Scene | Plant in frames | Trap false | Record written first | Full pass |
| --- | --- | --- | --- | --- |
| desk | yes | yes | no | no |
| kitchen (new) | yes | yes | no | no |

Plant and trap accuracy: 0/2 before this run, 2/2 after, including the new kitchen scene. The same harness then generated workshop and porch. Porch is another new scene.

| Scene | Plant in frames | Trap false | New scene |
| --- | --- | --- | --- |
| desk | yes | yes | no |
| workshop | yes | yes | no |
| kitchen | yes | yes | yes |
| porch | yes | yes | yes |

Plant and trap accuracy after the fix: 4/4. Before the thinking cap, the same three scenes that had finished were 0/3. The full pass stays no only because plain mode never writes a scene record, and that check was not what was dropping the plant. Clips are under `media/<scene>/plain/plain-low/clip.mp4`.

One `deepseek-v4.1-flash` call was tried on the porch, the scene space bunny already kept. It did not run. The API said this model requires Global regions, and the workspace privacy setting is not Global. That setting is the blocker. No second DeepSeek call was made. Space bunny remains the generator.

## Ideas I am not running

1. Evolution over many harness edits. The failed step was readable. A search would not have drawn the plant.
2. A separate mutable state file. Git already stores the diff.
3. Splitting one clip across six roles. More handoffs give a cheap model more chances to drop the plant.
4. Three to five variants. Both scripts kept the plant. Ranking copies is not the miss.
5. A second stage-reward board. The script already scores the plant, the trap, and a later deletion.
6. Memory of what worked. The working pattern is "let the script run." There is no extra trick to reload.
7. A scene-language compiler. Not while the model's own script is keeping the plant and the trap. It would not raise those two scores.
8. Grey block-in, then a look pass. Same idea as a record, and the pixels already match.
9. Text and vision gates, and a Muse judge. A text quiz does not put the plant in the frames. There is no free vision model. Muse bills.
10. Spreading plants across twelve skills. One plant type is surviving. A wider bench can wait.
11. Hunting new failure modes. The failure we had is fixed. I am not going looking for a new one yet.
13. A tag for harness-dependent misses. The trace already shows the step. A tag does not change the clip.
14. A model critic. The script already checks frames, timing, and the question. The named critic bills.
15. Keeping taste separate. Already how the score is split. Kitchen's pan is the only look miss, and it is not the plant.
16. PNG frames, then ffmpeg. Already how these clips were written.
17. Swapping Pillow for another drawing library. Pillow drew the plant.
18. Cloning a director-flow or greybox film repo. The useful piece would be a record. The scripts do not need it for the plant.

## Four new scenes

Same harness, `space-bunny-free`, no scene record. Objects are not the desk, workshop, kitchen, or porch sets. Library is a reading shelf (lamp, book, cup, a cactus flash, a question that calls the green lamp red). Window sill is a candle, bowl, and napkin, with parsley, and a question about a teapot. Dock is a buoy, rope, and crate, with kelp, and a question about a fishing rod. Bakery is a loaf, mixer, and box, with thyme, and a question about a rolling pin.

Library’s first pass did not draw. The script already had the cactus and the false lamp question. The harness blocked `pathlib`, then the 40 second limit cut the picture off while frames were still being saved. Allowing `pathlib`, the same way `os` was allowed, and giving the script time to finish, used that same script. Bakery had the same timeout. Neither scene had forgotten the plant.

| Scene | Plant in frames | Trap false |
| --- | --- | --- |
| library | yes | yes |
| window | yes | yes |
| dock | yes | yes |
| bakery | yes | yes |

New scenes: 4/4. Earlier scenes: 4/4. The harness is holding for this plant type. I am not adding more scenes of this kind. Clips are under `media/<scene>/plain/holdout-1/clip.mp4`.
