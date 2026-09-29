# Checkpoint 01: plain script 8/8, strict checker 0/8

- **Time (UTC):** 2026-09-29T22:10:40Z
- **Source SHA:** `5a5747cc5b4f608b5096d5d9b0b977c6bf50067a` (tip of `origin/cursor/video-harness-f8db` when this branch was created)
- **This branch:** `checkpoint/01-plain-8of8`
- **Not updated:** `main`, and `cursor/video-harness-f8db` (still `5a5747cc`). No merge, no force push, no deploy.

The 8/8 is the plain script after plumbing fixes (thinking cap, `os` and `pathlib` allowed, longer timeout). It is one easy plant check (`kind: plant`), a static extra object, and one trap style. It is not a strict-checker pass.

## Commands run

No model calls. The key file was not read and is not in this commit.

| Command | Result |
| --- | --- |
| `python3 -m harness --selftest` on a detached checkout of `5a5747cc` | **Pass.** Exit 0. Printed `pass` for 6/6 scenes in the self-test list: desk-mug, workshop-bench, kitchen-counter, porch-step, library-shelf, window-sill. Rejected 5/5 negative cases: always-on plant, blank frames, deleted plant, late record, repeated scene. Last line: `selftest ok`. |
| `python3 check.py selftest` in `internal/eval-checks` | **Pass on retry.** First run exit 1: `OSError: [Errno 5] Input/output error` while writing `fixtures/paired-run/last-result.json` on the store filesystem. No summary was printed. Immediate retry exit 0, `problems: []`, `bad_pass: false` (12 expected failing checks on the bad fixture), `good_pass: true` (`good_failed: []`), `run_pass: true`. |
| `python3 check.py clip` on the eight media folders below | **0/8 pass.** Read-only. Counts are in the strict-checker table. |
| pytest / unittest | **Not run.** This repo has no pytest or unittest suite. That is not a pass. There is no `offline_check.py` in the repo. |

The harness self-test does not include bakery-counter or dock-post. Those two are in the eight clips, not in the 6/6 self-test.

## Plain-script numbers

From `results/scores-holdout.jsonl` on `5a5747cc` (8 rows, plain mode, `space-bunny-free`, `record_source: none`):

| Gate | Count |
| --- | --- |
| `plant_in_frames` true | 8/8 |
| harness `question_is_false` true | 8/8 |
| full `pass` true | 0/8 |
| `record_exists` true | 0/8 |

Narrative from the copied `harness-progress.md`, same source:

- Before the plumbing fixes, desk, workshop, and kitchen never became clips. Plant and trap: **0/3**.
- Thinking cap alone: the scripts named the plant, and nothing was drawn. **0/2**.
- After `os` was allowed: desk, workshop, kitchen, porch. Plant in frames and harness trap-false: **4/4**.
- After `pathlib` was allowed and the save was given time to finish: library, window, dock, bakery. **4/4**.
- Combined plain plant-in-frames and harness trap-false: **8/8**. Full harness pass stays false because plain mode writes no scene record.

Plant ids in the briefs are fern, succulent, basil, ivy, cactus, parsley, kelp, and thyme. All are `kind: plant`. The names are not eight different tests.

## Strict checker: 0/8

`python3 check.py clip` on 2026-09-29. Each clip has 18 hard checks. None passed. None of the eight directories has `record.json`.

| Clip | Pass | Failed | `question_is_false` | One frame | Time reversal |
| --- | --- | --- | --- | --- | --- |
| `media/desk-mug/plain/plain-low` | no | 15/18 | pass | fail | fail |
| `media/workshop-bench/plain/plain-low` | no | 13/18 | pass | fail | fail |
| `media/kitchen-counter/plain/plain-low` | no | 15/18 | pass | fail | fail |
| `media/porch-step/plain/plain-low` | no | 14/18 | pass | fail | fail |
| `media/library-shelf/plain/holdout-1` | no | 16/18 | **fail** | fail | fail |
| `media/window-sill/plain/holdout-1` | no | 14/18 | pass | fail | fail |
| `media/dock-post/plain/holdout-1` | no | 14/18 | pass | fail | fail |
| `media/bakery-counter/plain/holdout-1` | no | 15/18 | pass | fail | fail |

Seven briefs are global absence (`why_false: absent`). One frame gives that key, and reversing time does not change it, so `no_single_frame_shortcut` and `frame_order_sensitive` fail on every clip that has a key.

Library is not an absence question. The brief asks "What color is the red lamp?" with `why_false: wrong_attribute`, and the lamp is an object in the brief. The strict checker says the asked claim is true of the log, `oracle_key` is null, and the tags include `not_a_trap`. The harness log had marked that same clip `question_is_false: true`. Those two scores disagree. The strict checker did not pass library, and it did not pass the other seven.

Shared misses on every clip, because there is no record and no answer key in `trap.json`: `record_before_code`, `plant_in_record`, `plant_in_frames`, `plant_visible`, `plant_survives_1fps`, `plant_survives_encode`, `key_matches_log`, `nearby_anchor`, `options_unbiased`, `published_index`, `canary_kept_out`.

## Caveats

- 8/8 is the plain script's plant-in-frames and trap-false bits after the plumbing fixes. It is not 8/8 strict passes.
- The strict checker failed all eight clips.
- The harness self-test covers 6 scenes, not these 8 clips.
- The checker self-test's first run died on a store write error. The retry is the green run.
- Clips here are the small mp4s only (about 6–15 KB each). Frame PNGs were not copied.
- `evaluation.md` and `harness-progress.md` in this folder are copies of the store docs at checkpoint time.
