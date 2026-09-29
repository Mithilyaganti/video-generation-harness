# Checkpoint 02: renderer comparison and aisle dolly

- **Time (UTC):** 2026-09-29T22:16:19Z
- **Source SHA:** `149d2ab29bbc2df71a2626ce7321941386e15118` (tip of `origin/checkpoint/01-plain-8of8` when this branch was created)
- **This branch:** `checkpoint/02-renderer-dolly`
- **Not updated:** `main`, `cursor/video-harness-f8db`, and `checkpoint/01-plain-8of8`. No merge, no force push, no delete, no deploy.

This commit copies the renderer writeup, the Chrome re-render proof, and the three 10-second aisle-dolly mp4s. Frame folders were not copied. `opencode-go.env` is not in this commit.

## Commands run

No model calls. Both commands below finished at 2026-09-29T22:15:57Z, on this branch, before the commit.

| Command | Result |
| --- | --- |
| `python3 -m harness --selftest` | **Pass.** Exit 0. Printed `pass` for 6/6 scenes: desk-mug, workshop-bench, kitchen-counter, porch-step, library-shelf, window-sill. Rejected 5/5 negative cases: always-on plant, blank frames, deleted plant, late record, repeated scene. Last line: `selftest ok`. |
| `python3 check.py selftest` in `/cursor/stores/bc-f9fe9480-5b96-4277-be5d-c761609be7ed/internal/eval-checks` | **Pass.** Exit 0. `problems: []`, `bad_pass: false` (12 expected failing checks on the bad fixture: `frame_order_sensitive`, `key_matches_log`, `no_single_frame_shortcut`, `options_unbiased`, `plant_in_frames`, `plant_not_deleted`, `plant_survives_1fps`, `plant_survives_encode`, `plant_visible`, `published_index`, `record_before_code`, `text_does_not_solve`), `good_pass: true` (`good_failed: []`), `run_pass: true`. |
| pytest | **No suite.** This repo has no pytest suite: no `tests/` directory, no `pytest.ini`, and no `test_*.py` modules. `python3 -m pytest` is not installed (`No module named pytest`). That is not a pass. |

## Smoke clips

Smoke clips are 480 by 270, 16 frames, about 2 seconds. Python and Three.js mp4s are byte-identical on all four scenes (shed shelf, market stall, station bench, shop tank). Chrome 148 with SwiftShader re-rendered the four `scene.js` files. The match is because both drew the same solid rectangles with smoothing off, not because the Three.js file was a copy of the PyGame mp4. Blender differs on those four, and lost the snail on the shop tank.

The proof file copied here is `chrome-proof.json`. It names Chrome/148.0.7778.96 and, for each of the four scenes, WebGL `ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)`, no page errors, and 16 frames. The writeup is `renderer-comparison.md`.

## Aisle dolly

The 10-second aisle dolly, 640 by 360, 80 frames, was not written by `space-bunny-free`. The three mp4s in `aisle-dolly/` differ. Full md5s checked on the copies in this commit:

| Renderer | Path | md5 |
| --- | --- | --- |
| Python | `aisle-dolly/python/clip.mp4` | `a77afa402a4106fdbf8e04530b98ebbc` (starts `a77afa402a41`) |
| Three.js | `aisle-dolly/three/clip.mp4` | `61ee079b727a5163cd4ffe5113303a98` (starts `61ee079b727a`) |
| Blender | `aisle-dolly/blender/clip.mp4` | `09f11a517c4d8847439ff7f51e0d7282` (starts `09f11a517c4d`) |

`ffprobe` on these three files: 640 by 360, 80 frames, 8 fps, 10.000 seconds. The writeup says 0 of 80 frames match PyGame.

## Which renderer fits

Python still fits the cheap smoke test. Three.js is the one that shows a moving camera. The smoke-test tie does not prove the renderers look the same once the camera moves.
