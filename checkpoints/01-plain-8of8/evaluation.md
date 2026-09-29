---
cursor:
  subagentId: "bc-de57fd49-4c29-5b3a-a92c-f18c77f7e69c"
---

# How a clip is scored

A clip passes only when a program can prove every hard check below. Nothing here is a glance, and nothing here is a grade for how pretty the picture is. The render log is the answer key. The frames and the encoded mp4 have to agree with that log.

Taste is a separate block, and it is not scored. `taste.scored` is false on every result. A pretty clip can still fail. A false question can still fail. The bad fixture below is a false question, and it fails.

The checker is `internal/eval-checks/check.py`. It does not call a model.

## What has to be true

For one clip, all of these pass together.

The scene record exists and was written before the renderer code. The trace never drops the plant after it appears. The plant's frames and color in the log are exactly the frames and color in the record. The plant is large enough, and a different color from the background, that a viewer is not being asked to see a speck. At 1 frame per second, every sampling phase still hits the plant at least twice. The raw PNG at each object's center matches the logged color. After the mp4 is decoded, the plant's center still matches. The picture is not a blank frame.

The asked claim is false of the log, unless the clip is marked as the true twin of that question. The writer's key matches the key the program computes. A nearby object from the question is on screen with the plant. One frame is not a reliable way to that key. Reversing time changes the key. The question wording does not already give the key. The keyed option is not much longer than the others, and an abstain option does not repeat the question more than the other options do. The published option index points at the program's key. A canary string sits on the record and is not in the question or the options.

For a harness run, every clip passes, and the set also has all of these. A false question has a true twin with the same wording, so "it did not happen" is not always the right line. A twin changes the plant's frames and the key changes with it. Two clips are not the same scene with the names swapped. The keyed option is not always in the same slot.

## Checks kept

Each row is one hard check. `pass: true` means the clip is all right on that point.

| Check | What it asks | Why it is here |
| --- | --- | --- |
| `record_before_code` | The trace records the scene before it writes renderer code | The score is a process check as well as a picture check. A record written afterwards can be fitted to whatever the code happened to draw. |
| `plant_not_deleted` | After the plant shows up in the trace, no later snapshot removes it | A plant that is written and then deleted is a miss even if a later snapshot puts it back. |
| `plant_in_record` | The record names one plant, with a color and a list of frames | The plant is a declared fact, not a vibe. |
| `plant_in_frames` | Those frames are exactly the frames where the log draws it, same color. The result includes the overlap | Hard Times scores a time window by overlap and reports recall at 0.3, 0.5, and 0.7. A human span is fuzzy. This log is the generator's own record, so the bar is exact overlap (1.00). An overlap of 0.50 still fails, and the detail says so. |
| `plant_visible` | Smallest side at least 8 px, area at least 64 px, and the color is at least 48 levels away from the background | A speck, or a plant the same color as the wall, is unfair. The item never gave the model a fair look. This is the hard-versus-unfair split, done with pixels instead of a second model. |
| `plant_survives_1fps` | On every phase of 1 frame per second, the plant is hit at least twice. The detail includes how many seconds it is on screen | Gemini's video docs say the default sampler takes 1 frame per second and can miss a fast change. A plant shorter than that tests the sampler. Two hits on the worst phase is the bar. The on-screen time is the automatic version of EgoSchema's certificate: how much of the clip the evidence actually occupies. |
| `pixels_match_log` | The center pixel of every logged box matches the logged color in the raw PNG | The log is not trusted on its own. CLEVRER and Kubric answer from symbolic state that was saved with the render. Here the PNG is the other copy of that state. |
| `plant_survives_encode` | The same center, read back from `clip.mp4`, still matches | H.264 4:2:0 can wash out a small saturated mark. The file a model is sent is the mp4, not the PNG. The checker decodes the mp4 with ffmpeg. |
| `something_on_screen` | Every frame has an object, and the PNG is not one flat color | A blank frame must not pass. |
| `question_is_false` | The asked claim is false of the log. On a true twin the check is named `question_is_true` and the claim must hold | Hard Times: the correct response to an absent thing is that it is not answerable. VGIBench's public hard-negative options use the line "This does not happen in the video." The program decides which one it is. It does not believe the writer's explanation. |
| `key_matches_log` | `writer_key` equals that computed answer | CLEVRER's oracle answers from symbolic state. If the writer and the log disagree, the key is broken. |
| `nearby_anchor` | The nearby object is on screen during the plant | Hard Times: the trap is about something close to a real object, and wrong answers often name that real object. The nearby object has to actually be there. |
| `no_single_frame_shortcut` | A closed-world reading of one frame matches the key on fewer than half the frames, the most common frame does not match, and a real proof needs at least two frames | TVBench showed popular video sets can be solved from one frame, from the words, or from world knowledge. The atemporal probe (ATP) asks from the single best frame. Singularity showed a single-frame model matching multi-frame models on sets with static appearance bias. This is that test on the log, with no vision model. |
| `frame_order_sensitive` | Reversing the frames changes the key | TOMATO reports frame-order sensitivity: accuracy should drop when order is destroyed. VBenchComp calls an item temporal only when shuffled frames are not enough. Reversal is the deterministic form. TempCompass builds conflicting clips by reversing time. |
| `text_does_not_solve` | The question text does not already state the key, repeat the explanation, or say the thing is missing when the key is abstention | Video-MME removed questions a text-only model could answer, then reported the leftover text-only score. TVBench's second failure mode is the same. This check is the part a program can do without calling a model: a wording leak. It will not catch a subtle language prior. |
| `options_unbiased` | The keyed option is not 12 or more characters longer than the others. If the key is abstention, it also does not share more question-words than the other options | MVBench found longer options tend to be the correct ones, and rewrote options to similar lengths. Hypothesis-only baselines (Poliak et al.) show that word overlap with the question can leak the label. A true description is allowed to name the objects. The abstain line is not allowed to be the option that retells the question. |
| `published_index` | `correct_answer` is the index of the program's key, and rotating the list still selects that same text | VGIBench's public split scores an option index by exact match. MMBench CircularEval asks again with the options rotated so a lucky slot cannot count as a solve. Rotation here does not call a model. It checks that the index is glued to the text. |
| `canary_kept_out` | The record carries a canary GUID, and that marker is not in the question, the explanation, or the options | BIG-bench's canary, which VGIBench copies. Ours is a different GUID from Seldon's. Do not put theirs on our rows, and do not put ours in a prompt. |

A run adds four more. They do not change a single clip's pass bit.

| Check | What it asks | Why it is here |
| --- | --- | --- |
| `abstention_pair` | The same question has one abstain key and one key that is not abstain | MM-UPD and VideoHallucer: if the model always says the thing did not happen, it should miss the true twin. |
| `plant_pair` | A twin changes the plant's frame list, and the key changes with it | TempCompass conflicting clips, and Vinoground's group score on a counterfactual pair. A blind reader who sees only the question cannot get both halves. |
| `option_position_skew` | The keyed slot is not the same on every item | Perception Test reports a frequency baseline, the score you get by always picking the most common slot. |
| rename pair | Two clips with the same objects, colors, frames, and question are a rename | A renamed copy is not a new item. Twins are not renames, because their frames differ. |

Tags on a clip, in the `tags` list:

- `valid` — nothing above failed
- `broken_key` — the writer's key is missing or disagrees with the log
- `not_a_trap` — a clip that was supposed to be false is actually true
- `unfair` — the plant is missing, tiny, low-contrast, missed at 1 fps, wiped by the mp4, or the pixels disagree
- `shortcut` — one frame, the wording, the options, or time-reversal gives the key away
- `process` — the record came after the code, or the trace dropped the plant

Unfair means the item should be dropped or redrawn. Shortcut means the picture may be fine and the question is still too easy. Both can be true at once.

## How to read a score

`pass` is the only yes or no for the clip. It is true only when every hard check passed.

`oracle_key` is the answer the program computed. `claim_holds` is whether the asked claim is true of the log. For a normal clip you want `claim_holds: false` and an oracle key of `This does not happen in the video.`

`hard_passed` and `hard_total` are a count, not a grade. Six out of seventeen is not a 35% quality score. It is six gates. The clip still fails.

`taste.scored: false` means look was not judged. Do not average it in.

On a run, `clip_pass` means every clip passed its own gates. `pass` means that, plus the twin, rename, and option-slot gates. A single good clip is not yet a run.

Export with `check.py export <clip>` writes one JSON object in the public VGIBench shape: `question_id`, `video_id`, `video_url`, `question`, `question_type`, `answers`, `correct_answer`, `canary`. The index is the program's key, not the writer's. This is a compatible row for a pitch. It is not a row in their dataset, it does not use their canary, and their `vgibench score` tool is for their videos and their responses.

## What was looked at, and what was left out

Two piles of notes were used together. Neither outranked the other. Seldon's posts and the public VGIBench repo were checked directly. The papers below are the ones the kept checks actually use. A longer survey is in `internal/eval-research.md`.

Left out on purpose:

- A live blind model, three tries, rotated options, and a weak vision model. Video-MME, TVBench, and MMStar all do this with a model. The public VGIBench README does not describe a blind gate or a Flash-Lite gate. The only free Go models on this job are the generators, and the named judge is billed, so it is not called. The lexical, single-frame, reversal, and option checks are the part that does not need one. A later pass can add a free text model that is not the generator. Until then, do not quote a blind accuracy number.
- Item-response theory, M3IRT, tinyBenchmarks, signal-to-noise across seeds, and error-overlap across a model panel. Those need a grid of model answers. There is no grid yet. Fitting one now would be invented.
- Adversarial filtering, and reporting scores only on models that were not used to filter. That is a way to build the set. It is not a check on one clip.
- A failure-discovery loop over skill and difficulty. That is the harness's job. This checker only says whether an item is valid.
- Detector and segmenter models (Grounding DINO, OWLv2, SAM 2) and learned video judges (VideoScore, a VLM pool). On these flat frames the pixel at the logged box is the specialist. MLLM-as-a-judge work finds absolute scores and majority votes unreliable. The log stays the ground truth.
- FVD, VBench smoothness, EvalCrafter's fitted quality number. FVD can prefer a still frame, and those suites grade look. They are the wrong tool for "did the plant survive."
- A 30 to 50 item human spot-check. Worth doing before a Seldon pitch, on items that already pass this program. It was not faked here.
- Physics judges (VideoPhy, PhyGenBench). For a rendered clip the engine log is the physics. No clip in this checker is a collision item yet. The same log pattern would cover one later: the program answers from the logged event, not from a caption.

ETVA and Davidsonian scene graphs are the reason the score is many small facts instead of one grade. Their published method asks a video model. Here the log answers the facts, and a child fact is not treated as a save when the plant itself is missing.

## Public VGIBench, stated carefully

Checked against the README at `https://github.com/Seldon-Foundation/VGIBench` and the dataset card `Seldon-Technologies/VGIBench` (tag v1.0.1).

The README calls it ten visual and audio-visual skills and 550 human-curated questions. The public split is multiple choice and scored by exact match. The held-out split is open-ended: options are withheld, and a judge maps a free-form answer onto the hidden options. Prompts are pinned. `vgibench run` uses temperature 0. Every record has a canary. The card's public split at v1.0.1 is 439 questions. Fields are `question_id`, `video_id`, `video_url`, `question`, `question_type`, `answers`, `correct_answer`, `canary`. Question types include `contrastive-hard-negative/*` and `infinibench/*`. The hard-negative options include "This does not happen in the video."

The README that was fetched does not describe a blind text model, a "right 3 times out of 3" rule, a Gemini Flash-Lite gate, or twelve skills. Those details live in the collaboration briefing and in earlier notes. Keep them as briefing. Do not cite them as what Seldon has published.

A different paper, arXiv 2608.19583, is also named VGI-Bench. It grades generated video with a vision-model judge. It is not this dataset. Seldon's Infinibench-v0 is the `infinibench/*` question family, not the CVPR spatial InfiniBench and not that paper.

## The fixture

`internal/eval-checks/fixtures/bad-clip` is a clip a person could call a trap. The asked bottle is not in the scene, so `question_is_false` passes. The rest does not. The fern in the record covers frames 2–5. The log draws it as a 1×1 pixel on frame 2 only (overlap 0.25). The worst 1 fps phase hits it 0 times. The raw PNG matches that speck. The mp4 was encoded from a copy with the speck painted out, and the decoded center is the background `(202, 183, 144)` against the logged green `(47, 125, 74)`. The question says "There is no water bottle," which is the key. The writer's key says the bottle is blue. The published index points at blue. The abstain option is 107 characters longer than the other one. Reversing time does not change the key. One frame is enough: a random frame matches the key 100% of the time. The trace writes code at seq 1 and the record at seq 2, then drops the plant.

Command and result, from `python3 check.py selftest` in `internal/eval-checks`:

```
bad_pass: false
bad_failed:
  record_before_code, plant_not_deleted, plant_in_frames, plant_visible,
  plant_survives_1fps, plant_survives_encode, key_matches_log,
  no_single_frame_shortcut, frame_order_sensitive, text_does_not_solve,
  options_unbiased, published_index
bad_tags: broken_key, unfair, shortcut, process
good_pass: true
run_pass: true
```

The full JSON is `internal/eval-checks/fixtures/bad-clip/last-result.json`.

`fixtures/good-clip` is the control, so the checker is not a script that always fails. The fern is on screen for 2.00 seconds at 2 fps, and both 1 fps phases hit it twice. Window overlap is 1.00. The decoded mp4 keeps the plant color on all 4 plant frames. The question is "Does the fern appear before the gold flash?" The flash starts first, so the key is abstention. One frame matches that key 0% of the time. Reversing the clip makes the fern come first, so the key changes. The two options are the same length. The record is seq 1 and the code is seq 2.

`fixtures/paired-run` puts that clip next to a true twin. Same question. The fern's frames move in front of the flash, and the key becomes "The fern appears before the flash." Keyed slots are 1 and 0. The run passes. A rename of the good clip shares its signature; the self-test checks that.

Rebuild the pictures with `python3 make_fixtures.py`, then `python3 check.py selftest`. The self-test exits non-zero if the bad clip starts passing, or the good clip starts failing.

## Run it on a real clip

From the eval-checks directory:

```
python3 check.py clip /path/to/clip
python3 check.py run /path/to/run
python3 check.py export /path/to/clip
```

A clip directory needs `record.json`, `log.json`, `trap.json`, `trace.jsonl`, `frames/f_000.png` and up, and `clip.mp4`. Missing pieces fail closed. A harness folder that only has a log and a trap can still be pointed at the checker. It will fail the record, the frames, and the mp4, which is the right result until those exist.

`record.json` names `fps`, `background`, `canary`, and `plant` with `id`, `color`, and `frames` as a list of indices. `log.json` is `{"frames":[{"index":0,"objects":[{"id","kind","color","x","y","w","h"}]}]}`. `trap.json` carries `question`, `why_false`, `claim`, `nearby_id`, `writer_key`, `answers`, `correct_answer`, and `role`. `role` is `false_premise` or `true_twin`. A claim is either `{"type":"order","earlier":"fern","later":"flash"}` or `{"type":"absent","object":"water_bottle"}`. An absent claim may set `during` to an object id when the absence is only inside that object's frames. Without `during`, a missing object is visible to every frame, and the single-frame check fails. That is deliberate. A bottle that is simply never drawn is a false question and a bad item.

The trace is JSON lines. A record step is `{"event":"record","seq":1}` or a snapshot with `"kind":"record"`. A code step is `{"event":"write_code","seq":2}` or a snapshot with `"kind":"code"`. Plant snapshots set `has_plant` true or false.

This pass did not write scores into the harness clip folders. Those runs are still in progress.

## Harness clips, scored as they were

Scored with `check.py clip` after the harness finished. Nothing was added to these folders. No record was invented. Every clip fails.

All eight are missing `record.json`. They do have `log.json`, `trap.json`, `trace.jsonl`, `frames/`, and `clip.mp4`. `trap.json` has a question and an asked id. It has no `writer_key`, no `answers`, and no `correct_answer`. The trace has no record step.

Because there is no record, these gates fail on every clip: `record_before_code`, `plant_in_record`, `plant_in_frames`, `plant_visible`, `plant_survives_1fps`, `plant_survives_encode`, `nearby_anchor`, `key_matches_log`, `options_unbiased`, `published_index`, `canary_kept_out`. The checker will not guess which logged object is the plant.

The traps are global absence questions, so `no_single_frame_shortcut` and `frame_order_sensitive` also fail on every clip that has a key. One frame matches the key every time, and reversing time does not change it.

What still passed, and what else failed:

| Clip | Result | Also failed | Passed |
| --- | --- | --- | --- |
| `media/desk-mug/plain/plain-low` | Fail | `plant_not_deleted` (a later snapshot removed it). `pixels_match_log` (pencil center does not match the log). | `something_on_screen`, `question_is_false`, `text_does_not_solve` |
| `media/workshop-bench/plain/plain-low` | Fail | No extras beyond the shared list. | Those three, plus `plant_not_deleted` and `pixels_match_log` |
| `media/kitchen-counter/plain/plain-low` | Fail | `plant_not_deleted`. `pixels_match_log` (knife). | `something_on_screen`, `question_is_false`, `text_does_not_solve` |
| `media/porch-step/plain/plain-low` | Fail | `pixels_match_log` (ivy). | `plant_not_deleted`, `something_on_screen`, `question_is_false`, `text_does_not_solve` |
| `media/library-shelf/plain/holdout-1` | Fail | `plant_not_deleted`. `question_is_false`: the asked lamp is in the log, so the claim is true and no key could be computed. `text_does_not_solve`, `no_single_frame_shortcut`, and `frame_order_sensitive` fail for that missing key. | `pixels_match_log`, `something_on_screen` |
| `media/window-sill/plain/holdout-1` | Fail | `pixels_match_log` (bowl: the log says blue, the pixel is pale). | `plant_not_deleted`, `something_on_screen`, `question_is_false`, `text_does_not_solve` |
| `media/dock-post/plain/holdout-1` | Fail | `pixels_match_log` (crate). | `plant_not_deleted`, `something_on_screen`, `question_is_false`, `text_does_not_solve` |
| `media/bakery-counter/plain/holdout-1` | Fail | `plant_not_deleted`. `pixels_match_log` (box). | `something_on_screen`, `question_is_false`, `text_does_not_solve` |

Seven questions are false of the log. The library shelf is not. None of the eight is a passing item.
