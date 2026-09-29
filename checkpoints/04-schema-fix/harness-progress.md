# Harness progress

Plain language. No key. The two brief files are on this store. This pass did not need them.

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

## The easy 8/8 does not show a harness win

Those eight clips are one kind of plant: a short flash of a still object, plus one kind of false question: a thing that is not in the scene, or a wrong color. The prompts also gave the exact frames. A plain script copied them. That is good plumbing (a thinking cap, letting the script use `os` and `pathlib`, and enough time to save the frames). It does not leave room to show that a harness beats the plain model.

The desk water-bottle question is false, and the words alone do not give the answer. One frame still answers it, because the bottle is missing in every frame. Playing the frames backward, or shuffling them, leaves the same answer. A false question is not a hard question. I am not counting that trap as solved.

## Harder pictures, still plain

Same model, `space-bunny-free`, still one script and no scene record. The prompt states the timing in seconds and does not give frame numbers. A trap counts only when three extra checks pass: the question text does not give the answer, one frame is not enough, and reversing or shuffling the frames changes the answer.

| Scene | What had to happen | Plain picture | Trap checks |
| --- | --- | --- | --- |
| delay-cart | orange marigold about 0.8s after a blue cart leaves | yes, cart frames 0–5, marigold 16–21, 10 frames between them | yes |
| cover-marble | red marble slides left to right and is not drawn while it crosses a board | yes, left 0–20, hidden for 12 frames, right 33–47 | yes |
| count-blocks | two red blocks, then about 0.8s later four red blocks | yes, two on frames 0–2, four on 13–15, 10 frames between them | yes |
| needle-thread | a thin thread for about a quarter second, about 2s after a bell, in a 96-frame clip | yes, bell frames 3–8, thread 33–35, 24 frames between them | yes |

Plain on these four: 4/4. The easy scenes stay 8/8, and I did not add another easy still plant.

The first delay score said the log missed the cart. The picture was already right. The script had named it `cart_1`. The score now treats that suffix as the same object. That correction did not change what the model drew.

The full pass is still no, only because plain mode does not write a scene record before the script. That was not what these pictures needed. I am not adding a scene record, and I am not running the skipped ideas. Plain is still at 100% on these harder tasks, so there is no before-and-after where a harness beats the plain model. Clips are under `media/<scene>/plain/plain-hard/clip.mp4`.

## Harder again, and plain still matches the rule

The next prompts still give the timing in seconds and do not give frame numbers. The easy-to-drop event is not called a plant, and it is left out of the object list. A trap still counts only when the words, one frame, and a reversed or shuffled clip cannot answer it.

| Scene | What had to happen | Plain picture | Trap checks |
| --- | --- | --- | --- |
| order-band | horn first, then bell, then drum, about 0.8s apart, even though the drum is named first | yes, horn 4–6, bell 17–19, drum 30–32 | yes |
| reappear-balls | one red ball hides behind a board and three come out the other side | yes, one ball, hidden for 7 frames, then three | yes |
| pan-moth | the camera pans and a moth crosses from the left of the post to the right of the post | yes, left through frame 17, right from frame 21 | yes |
| buried-mote | a purple mote, not in the object list, about 0.8s after a lamp blink | yes, lamp 2–5, mote 16–20 | yes |

The three-ball exit stays up longer than a brief moment. The score did not limit that length. The hide and the change from one to three did happen.

The mote script failed on the first run only because it never created the frames folder. The same script, with that folder created and no edit to the picture, passes. That is the same kind of plumbing as letting a script save a file. It is not a harness that draws a better picture.

## What plain saturates

Plain `space-bunny-free` already follows a rule it can turn into arithmetic and rectangles. That includes a delay stated in seconds, three events in a required order, a hide followed by a different count, a left-to-right cross while the camera pans, and a short flash that is not labeled as a plant. The false question on those clips is an order question, so one frame is not enough and reversing the frames changes the answer. There is no held-out scene in this pass where a harness beat that plain script.

One repair was tried on the kitchen glint, where the first picture drew the orange spark at the right time but only about 36 pixels of its color, under the 80-pixel bar, and left the kettle color up for the whole clip. The retry was told what the frames showed and was asked for a solid patch. The kettle color still covered most of the clip, and the glint color still did not count. That retry was dropped.

A dock speck script had the right schedule, a short lantern flare and a white speck about one second later, then crashed in Pillow before it saved a frame. I did not patch that script and did not count the crash as a harness win.

## What would be needed for a gap

A gap needs a miss the model cannot fix by writing the sentence into a loop. The tries above are still that kind of sentence. The next bar would have to be something the script cannot see in the prompt: a second pass that only looks at the pixels and can reject a clip the text already described, or a rule whose timing is not stated and has to be discovered. Another retry that only repeats the measured miss did not move the glint over the visibility bar, so more of those retries is not the next step. No checkpoint was cut for this, because plain was not beaten on held-out scenes.

## The pitch number is the strict pass

The picture score above is still the easy one. Plain keeps drawing the plant when the prompt states the timing. That score can stay 8/8 on the first eight scenes. The strict checker asks for a different item: the plant verified from a scene record, the trap verified against that record, and the timing logged. A clip with no `record.json` fails that item even when the picture is right.

The eight easy plain clips, scored with that checker, are 0/8. Each one misses the record step, the plant window in the record, the one-frame-per-second survival check, the encoded plant color, and the keyed order trap (options, index, and canary). Workshop is the least bad of them, at 5 of 18 gates. The others are 2 to 4 of 18. None pass.

The harness that clears those gates writes the record first, then a renderer that draws that record as solid rectangles, then the log, the mp4, and an order trap whose answer is computed from the log. The trace records the record step before the code step. The plant stays up for two seconds, so every 1 fps sample phase hits it twice. The false question is an order question, so one frame does not answer it and reversing the frames changes the answer.

That harness does not ask the model to draw. Plain still does, on `space-bunny-free`. The comparison is on eight new scenes, none of them in the earlier picture runs.

| Scene | Plain strict | Harness strict |
| --- | --- | --- |
| stable-bridle | 0, 3/18 | 1, 18/18 |
| clinic-glove | 0, 3/18 | 1, 18/18 |
| studio-chalk | 0, 3/18 | 1, 18/18 |
| garage-funnel | 0, 0/18 | 1, 18/18 |
| garden-trowel | 0, 3/18 | 1, 18/18 |
| lab-beaker | 0, 3/18 | 1, 18/18 |
| stage-ribbon | 0, 2/18 | 1, 18/18 |
| market-scale | 0, 2/18 | 1, 18/18 |

Plain strict on these held-out scenes: 0/8. Harness strict: 8/8. Garden-trowel is the one plain clip whose pixels matched the older plant window, and it still fails the strict item. Clips are under `media/<scene>/plain/plain-strict/` and `media/<scene>/strict/strict-1/`.

Four smaller tries were weighed and left out, because they do not move this strict score:

- Several plants in one clip. The checker scores one `record.plant`. Extra objects do not add a gate.
- A plant that lasts only a few frames in a clip of 20 seconds. The self-test builds that clip from a record and the checker rejects it on `plant_survives_1fps`. Plain fails it too. It does not separate the two.
- A count question. The checker can key an order claim or an absence claim. A count has no key, so it cannot pass.
- A longer, messier brief. Plain already fails the strict item with no record. More prose would not raise the harness score.

That run is saved as `checkpoint/03-strict-record`. It is not a harness win. Plain was never asked for a record, and the harness never asked the model to draw. A reviewer would call the 0/8 versus 8/8 a format difference. The branch stays. The comparison below replaces it.

## Fair strict comparison

Same brief, same record schema, `space-bunny-free` on both sides, four new scenes. One-shot means one reply that contains the record and the drawing script. Staged means the model writes the record, then a second reply writes the script from that record. The checker then scores the clip. The picture number is separate: after decoding `clip.mp4`, the plant color is on every frame the brief gives the plant. No compiler drew these clips.

| Scene | One-shot strict | One-shot picture | Staged strict | Staged picture |
| --- | --- | --- | --- | --- |
| attic-compass | 0, 16/18 | yes | 0, 17/18 | yes |
| creek-paddle | 0, 16/18 | yes | 0, 17/18 | yes |
| office-stamp | 0, 17/18 | yes | 0, 16/18 | yes |
| nursery-rattle | 0, 17/18 | yes | 0, 17/18 | yes |

Strict pass: one-shot 0/4, staged 0/4. Picture: one-shot 4/4, staged 4/4. The full-pass gap closed. Staging picked up one gate on two scenes and lost one gate on office-stamp.

The misses that remain are small and shared. `plant_in_frames` fails when the record lists two frame numbers, the start and the end, while the log lists the whole two-second span. The decoded picture still has the plant color on all 24 of those frames. `options_unbiased` fails when the other answer is an empty string, so the abstain sentence is 34 characters longer. Office-stamp's one-shot did copy the long true sentence and passed that gate. Attic's staged record listed all 24 frames and passed the window gate. Neither side did both on the same clip.

The order traps need the video. On all eight clips the checker reports the same shortcut result: the question text does not give the answer, one frame is not enough, and shuffling the frames changes the keyed answer.

No checkpoint/04. The gap did not survive once both sides were asked for the record and both pictures came from the model. Clips are under `media/<scene>/one-shot/fair-1/` and `media/<scene>/staged/fair-1/`.

## The two misses were schema wording

Both sides had been stopping at 16 or 17 of 18 on the same two gates. Those gates were reading the prompt the way it was written.

`plant_in_frames` wants the record's frame list to be the same set of indexes as the log. The prompt said "frames 14 through 37". The model wrote `[14, 37]`, the two endpoints, and the log listed all 24 frames. Overlap 0.08. The checker was exact. The phrase "through" was not.

`options_unbiased` rejects a keyed sentence that is 12 or more characters longer than the other answer. The schema example was `"answers": ["", "<abstain>"]`. The model copied the empty string. The abstain sentence is 35 characters, so the gap was 34.

The schema now lists every frame index, says `[14, 37]` is only two frames, and puts the full true sentence in `answers[0]`. Both sides got that wording. The repair loop did not get a private copy.

That wording is saved as `checkpoint/04-schema-fix`. It helps both sides equally. One-shot and repair each moved from 0/4 strict passes on the previous four scenes to 2/4 here, and those passes are first replies.

## Repair loop, same schema

One-shot is still one reply and no checker feedback. Repair uses that same first reply, then at most two rounds that contain only the failing gate lines. The kept clip is the best attempt.

| Scene | One-shot strict | One-shot picture | Repair strict | Repair picture | Rounds kept |
| --- | --- | --- | --- | --- | --- |
| shed-wrench | 1, 18/18 | yes | 1, 18/18 | yes | first reply, no repair |
| cafe-spoon | 0, 3/18 | no | 0, 10/18 | yes | first reply, two rounds did not beat it |
| loft-violin | 1, 18/18 | yes | 1, 18/18 | yes | first reply, no repair |
| pier-bucket | 0, 3/18 | no | 0, 10/18 | yes | first reply, two rounds did not beat it |

Strict pass: one-shot 2/4, repair 2/4. Picture: one-shot 2/4, repair 4/4. The two full passes list all 24 plant frames and both answer sentences. They happened on the first reply, on both sides, so the loop did not produce them.

Cafe and pier one-shots crashed in the script before a clip was saved. The repair side's first reply on those scenes did draw, and the plant color is in the decoded mp4, but the log has no order claim the checker can key. The feedback said "the log cannot decide the claim" and "no key could be computed". Two rounds left the score at 10/18. The kept clip is still the first reply.

The loop did not win, so it is not part of checkpoint 04. Clips are under `media/<scene>/one-shot/schema-1/` and `media/<scene>/repair/schema-1/`.
