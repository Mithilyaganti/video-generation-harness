"""Score a known-good compile and the bad clips the metric has to reject."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from PIL import Image

from checker.score import score_run
from harness.briefs import load_brief
from harness.compile_scene import render_record
from harness.validate import record_from_brief, validate_record


SCENES = [
    "desk-mug",
    "workshop-bench",
    "kitchen-counter",
    "porch-step",
    "library-shelf",
    "window-sill",
]


def _trace_for_compile() -> list[dict]:
    return [
        {"event": "record_frozen", "seq": 1},
        {"event": "snapshot", "seq": 2, "has_plant": True},
        {"event": "render_start", "seq": 3},
        {"event": "snapshot", "seq": 4, "has_plant": True},
    ]


def _expect(name: str, result: dict, passed: bool) -> None:
    if result["pass"] is not passed:
        raise SystemExit(f"{name}: expected pass={passed}, got {json.dumps(result, indent=2)}")


def main() -> None:
    previous = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for scene_id in SCENES:
            brief = load_brief(scene_id)
            record = record_from_brief(brief)
            problems = validate_record(record, brief)
            if problems:
                raise SystemExit(f"{scene_id} fallback record is invalid: {problems}")
            out = root / scene_id
            render_record(record, out, write_video=False)
            result = score_run(out, brief, _trace_for_compile(), previous)
            _expect(scene_id, result, True)
            previous.append({"kinds": result["kinds"], "trap_sig": result["trap_sig"]})
            print(f"pass {scene_id}")

        brief = load_brief("desk-mug")
        good = root / "desk-mug"
        # Plant painted on every frame should fail the hidden-window check.
        always = root / "always"
        shutil.copytree(good, always)
        plant_frame = Image.open(always / "frames" / "f_010.png")
        for path in (always / "frames").glob("f_*.png"):
            plant_frame.save(path)
        # Log still matches the record, so only the pixel check should fail.
        always_score = score_run(always, brief, _trace_for_compile(), [])
        if always_score["hard"]["plant_in_frames"]:
            raise SystemExit("a plant that stays on screen the whole time passed")
        print("rejected always-on plant")

        # Blank frames must not pass.
        blank = root / "blank"
        shutil.copytree(good, blank)
        for path in (blank / "frames").glob("f_*.png"):
            Image.new("RGB", (640, 360), "#cbb892").save(path)
        blank_score = score_run(blank, brief, _trace_for_compile(), [])
        if blank_score["hard"]["something_on_screen"] or blank_score["hard"]["plant_in_frames"]:
            raise SystemExit("blank frames passed a look or plant check")
        print("rejected blank frames")

        # A later record that drops the plant fails, even if the first draft had it.
        dropped = root / "dropped"
        shutil.copytree(good, dropped)
        record = json.loads((dropped / "scene-record.json").read_text())
        (dropped / "scene-record-v1.json").write_text(json.dumps(record))
        record["objects"] = [obj for obj in record["objects"] if obj["id"] != "fern"]
        (dropped / "scene-record.json").write_text(json.dumps(record))
        (dropped / "scene-record-v2.json").write_text(json.dumps(record))
        dropped_score = score_run(dropped, brief, _trace_for_compile(), [])
        if dropped_score["hard"]["plant_not_deleted"]:
            raise SystemExit("deleting the plant still passed")
        print("rejected a deleted plant")

        # Code written before the record fails the order check.
        late = score_run(
            good,
            brief,
            [
                {"event": "write_code", "seq": 1},
                {"event": "record_frozen", "seq": 2},
                {"event": "snapshot", "seq": 3, "has_plant": True},
            ],
            [],
        )
        if late["hard"]["record_before_render"]:
            raise SystemExit("a record written after the code still passed the order check")
        print("rejected a late record")

        # Repeating desk after desk fails the object and trap checks.
        desk = score_run(good, brief, _trace_for_compile(), [])
        repeat = score_run(good, brief, _trace_for_compile(), [{"kinds": desk["kinds"], "trap_sig": desk["trap_sig"]}])
        if repeat["hard"]["objects_changed"] or repeat["hard"]["trap_moved"]:
            raise SystemExit("a repeated scene still counted as new objects")
        print("rejected a repeated scene")

    print("selftest ok")


if __name__ == "__main__":
    main()
