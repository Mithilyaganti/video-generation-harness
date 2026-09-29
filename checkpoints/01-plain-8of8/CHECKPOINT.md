# Checkpoint 01: plain plant+trap 8/8 holdouts

- **Time:** 03:34 IST (Asia/Calcutta), Wednesday 30 Sep 2026
- **Source SHA:** `5a5747cc5b4f608b5096d5d9b0b977c6bf50067a` (`cursor/video-harness-f8db` tip at checkpoint time)
- **Branch:** `checkpoint/01-plain-8of8` (new numbered snapshot; does not rewrite project branches)

## Commands run (no paid model calls)

| Command | Result |
| --- | --- |
| `python -m harness.selftest` | **pass** — 6 scene paths ok (`desk-mug`, `workshop-bench`, `kitchen-counter`, `porch-step`, `library-shelf`, `window-sill`); 5 negative cases rejected (always-on plant, blank frames, deleted plant, late record, repeated scene); `selftest ok` |
| `python -m pytest --collect-only -q` | no tests collected (repo has no pytest suite here) |
| `python …/offline_check.py verify-out <store>` | **FAILS 0** — Part A render+score fallback records: **8/8 PASS**; Part B decode holdout `clip.mp4` plant-pixel check: **4/4 PASS** (library-shelf, window-sill, dock-post, bakery-counter) |

## Measured harness progress (from `harness-progress.md`)

- Plant+trap before fix: **0/3** (desk/workshop/kitchen never drew).
- After thinking-cap + allow `os` + trap-from-pixels: **4/4** (desk, workshop, kitchen, porch).
- Four new holdouts (library / window / dock / bakery), after allow `pathlib` + finish-save timing: **4/4** plant+trap.
- Combined plain plant+trap: **8/8** including those 4 holdouts.
- **Full hard pass still false:** plain mode writes no `record.json`; the stricter eval checker that requires a scene record fails all 8 for that reason alone.

## Honest caveats

- Traps here are easy global-absence questions (one frame can answer “is X present?”).
- Stricter eval checker fails all 8 for missing `record.json` even when plant+trap pixels/questions look good.
- Harness thread was moving on to harder temporal tasks after this plateau.
- Cloud-agent launch models are unverified from transcript dumps; do not treat dump text as proof of model id.

## Bundled artifacts

- `harness-progress.md` — snapshot of the store progress note at checkpoint time
- `clips/*-plain-holdout-1.mp4` — four small holdout clips (library-shelf, window-sill, dock-post, bakery-counter)
