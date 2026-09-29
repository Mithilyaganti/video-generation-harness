"""Pass or fail a clip from its record, log, frames, and trace.

Hard checks stay separate from the light look at motion.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image


PLANT_NEAR = 35
PLANT_MIN_PIXELS = 80
PLANT_MAX_FRACTION = 0.08
OUTSIDE_MAX_PIXELS = 40


def _load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _hex_rgb(value: str) -> tuple[int, int, int] | None:
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if not re.fullmatch(r"#?[0-9a-f]{6}", text):
        return None
    text = text[-6:]
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def _norm_hex(value: str) -> str:
    rgb = _hex_rgb(value)
    if rgb is None:
        return str(value).strip().lower()
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _norm_question(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def frame_iou(start: int, end: int, present: set[int]) -> float:
    expected = set(range(int(start), int(end) + 1))
    if not expected and not present:
        return 1.0
    union = expected | present
    if not union:
        return 0.0
    return len(expected & present) / len(union)


def _objects_of(record: dict | None) -> list[dict]:
    if not record:
        return []
    objects = record.get("objects") or []
    return [obj for obj in objects if isinstance(obj, dict)]


def _kind_sig(objects: list[dict]) -> tuple:
    return tuple(sorted(str(obj.get("kind", "")) for obj in objects))


def _trap_sig(trap: dict | None) -> tuple:
    trap = trap or {}
    return (
        str(trap.get("asked_kind", "")),
        str(trap.get("asked_attribute", "")),
        str(trap.get("why_false", "")),
        _norm_question(trap.get("question", "")),
    )


def _count_near(image: Image.Image, rgb: tuple[int, int, int]) -> int:
    pixels = image.convert("RGB").load()
    width, height = image.size
    count = 0
    limit = PLANT_NEAR * PLANT_NEAR
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            dist = (r - rgb[0]) ** 2 + (g - rgb[1]) ** 2 + (b - rgb[2]) ** 2
            if dist <= limit:
                count += 1
    return count


def _frame_paths(run_dir: Path) -> list[Path]:
    frames = run_dir / "frames"
    if not frames.exists():
        return []
    return sorted(frames.glob("f_*.png"))


def _plant_snapshots(trace: list[dict], plant_id: str) -> list[bool]:
    flags = []
    for event in trace:
        if event.get("event") != "snapshot":
            continue
        if "has_plant" in event:
            flags.append(bool(event["has_plant"]))
    return flags


def _record_before_render(trace: list[dict], run_dir: Path) -> bool:
    record_seq = None
    later_seq = None
    for event in trace:
        name = event.get("event")
        seq = event.get("seq")
        if name in {"record_frozen", "write_record"} and record_seq is None:
            record_seq = seq
        if name in {"write_code", "render_start"} and later_seq is None:
            later_seq = seq
    if record_seq is not None and later_seq is not None:
        return record_seq < later_seq
    record = run_dir / "scene-record.json"
    code = run_dir / "scene.py"
    if record.exists() and code.exists():
        return record.stat().st_mtime <= code.stat().st_mtime
    return False


def _question_is_false(brief: dict, log: dict | None, trap_file: dict | None, record: dict | None) -> tuple[bool, str]:
    expected = brief["trap"]
    trap = trap_file or (record or {}).get("trap") or {}
    if _norm_question(trap.get("question", "")) != _norm_question(expected["question"]):
        return False, "saved question does not match the brief"
    # The scene decides whether the question is false. A prose reason is enough
    # when it does not claim the asked thing is truly there.
    frames = (log or {}).get("frames") or []
    seen = []
    for frame in frames:
        seen.extend(frame.get("objects") or [])
    asked_id = expected["asked_id"]
    asked_kind = expected["asked_kind"]
    if expected["why_false"] == "absent":
        for obj in seen:
            if obj.get("id") == asked_id or obj.get("kind") == asked_kind:
                return False, "the asked object is actually in the log"
        nearby = expected["nearby_id"]
        if not any(obj.get("id") == nearby for obj in seen):
            return False, "the nearby object is missing, so the trap is not anchored"
        return True, "asked object is absent and the neighbor is there"
    if expected["why_false"] == "wrong_attribute":
        target = next((obj for obj in seen if obj.get("id") == asked_id), None)
        if target is None:
            return False, "the object the false attribute is about is missing"
        actual = _norm_hex(str(target.get("color", "")))
        true_obj = next(obj for obj in brief["objects"] if obj["id"] == asked_id)
        if actual != _norm_hex(true_obj["color"]):
            return False, "logged color does not match the true color"
        if expected.get("claimed_value") == expected.get("true_value"):
            return False, "the claim is not actually false"
        return True, "the claimed attribute is not the logged color"
    return False, "unknown why_false"


def _look(brief: dict, log: dict | None) -> dict:
    frames = (log or {}).get("frames") or []
    camera = brief.get("camera") or {}
    kind = camera.get("kind")
    motion_ok = True
    if kind in {"pan_right", "pan_left"} and frames:
        ids = [obj["id"] for obj in brief["objects"]]
        anchor = ids[0] if ids else None
        xs = []
        for frame in frames:
            for obj in frame.get("objects") or []:
                if obj.get("id") == anchor:
                    xs.append(obj.get("x", 0))
                    break
        if len(xs) >= 2:
            delta = xs[-1] - xs[0]
            motion_ok = delta < -8 if kind == "pan_right" else delta > 8
        else:
            motion_ok = False
    watchable = len(_frame_paths_from_log(frames)) >= 0 and len(frames) >= 24
    return {"motion_ok": motion_ok, "watchable": watchable and len(frames) >= 24}


def _frame_paths_from_log(frames: list) -> list:
    return frames


def score_run(run_dir: Path, brief: dict, trace: list[dict] | None = None, previous: list[dict] | None = None) -> dict:
    run_dir = Path(run_dir)
    trace = trace or []
    previous = previous or []
    notes = []
    record = _load_json(run_dir / "scene-record.json")
    log = _load_json(run_dir / "log.json")
    trap_file = _load_json(run_dir / "trap.json")
    paths = _frame_paths(run_dir)
    plant = brief["plant"]
    plant_id = plant["id"]

    record_exists = bool(record and _objects_of(record) and (record.get("trap") or trap_file))
    record_before = _record_before_render(trace, run_dir) if record_exists else False
    render_ran = bool(paths) and bool(log and log.get("frames"))

    log_matches = False
    if record and log and log.get("frames"):
        log_matches = True
        by_id: dict[str, set[int]] = {}
        colors: dict[str, set[str]] = {}
        for frame in log["frames"]:
            index = int(frame.get("index", -1))
            for obj in frame.get("objects") or []:
                by_id.setdefault(obj.get("id"), set()).add(index)
                colors.setdefault(obj.get("id"), set()).add(_norm_hex(str(obj.get("color", ""))))
        for obj in _objects_of(record):
            present = by_id.get(obj.get("id"), set())
            iou = frame_iou(obj.get("from_frame", 0), obj.get("to_frame", -1), present)
            if iou < 0.8:
                log_matches = False
                notes.append(f"{obj.get('id')} frame overlap {iou:.2f}")
            wanted = _norm_hex(str(obj.get("color", "")))
            if wanted not in colors.get(obj.get("id"), set()):
                log_matches = False
                notes.append(f"{obj.get('id')} color missing from the log")
    else:
        notes.append("no record or no log to match")

    if brief.get("task"):
        # The old window is an exact frame range. Timed tasks are scored from the picture after this.
        q_ok, q_note = False, "task score: the false question is checked from the picture"
        notes.append(q_note)
    else:
        q_ok, q_note = _question_is_false(brief, log, trap_file, record)
        if not q_ok:
            notes.append(q_note)

    current_objects = _objects_of(record) or []
    if not current_objects and log:
        # Fall back to the first frame's objects plus any id seen later.
        bag = {}
        for frame in log.get("frames") or []:
            for obj in frame.get("objects") or []:
                bag[obj.get("id")] = obj
        current_objects = list(bag.values())
    kinds = _kind_sig(current_objects)
    trap = (trap_file or (record or {}).get("trap") or {})
    sig = _trap_sig(trap)
    objects_changed = True
    trap_moved = True
    for prior in previous:
        if prior.get("kinds") == kinds:
            objects_changed = False
            notes.append("object kinds repeat an earlier clip")
        if prior.get("trap_sig") == sig:
            trap_moved = False
            notes.append("trap repeats an earlier clip")

    snapshots = _plant_snapshots(trace, plant_id)
    plant_not_deleted = True
    if any(snapshots) and not snapshots[-1]:
        plant_not_deleted = False
        notes.append("the last snapshot has no plant")
    versions = sorted(run_dir.glob("scene-record-v*.json"))
    earlier_had = False
    for path in versions:
        body = _load_json(path) or {}
        if any(obj.get("id") == plant_id for obj in _objects_of(body)):
            earlier_had = True
    final_record = record or {}
    final_has = any(obj.get("id") == plant_id for obj in _objects_of(final_record))
    if earlier_had and not final_has:
        plant_not_deleted = False
        notes.append("the final record dropped the plant")

    if brief.get("task"):
        plant_in_frames, pixel_note = False, "task score: timing is checked from the picture"
        notes.append(pixel_note)
    else:
        plant_in_frames, pixel_note = _plant_pixels(paths, brief)
        if pixel_note:
            notes.append(pixel_note)

    on_screen = False
    if paths:
        spreads = []
        for path in paths[:: max(1, len(paths) // 6)]:
            image = Image.open(path).convert("L")
            hist = image.histogram()
            total = sum(hist) or 1
            mean = sum(i * hist[i] for i in range(256)) / total
            var = sum(hist[i] * (i - mean) ** 2 for i in range(256)) / total
            spreads.append(var ** 0.5)
        on_screen = max(spreads) > 12
        if not on_screen:
            notes.append("frames look blank")

    hard = {
        "record_exists": record_exists,
        "record_before_render": record_before,
        "log_matches_record": log_matches,
        "question_is_false": q_ok,
        "objects_changed": objects_changed,
        "trap_moved": trap_moved,
        "plant_not_deleted": plant_not_deleted,
        "plant_in_frames": plant_in_frames,
        "render_ran": render_ran,
        "something_on_screen": on_screen,
    }
    passed = all(hard.values())
    return {
        "scene_id": brief["scene_id"],
        "pass": passed,
        "hard": hard,
        "look": _look(brief, log),
        "notes": notes,
        "kinds": kinds,
        "trap_sig": sig,
    }


def _plant_pixels(paths: list[Path], brief: dict) -> tuple[bool, str]:
    if not paths:
        return False, "no frames to search for the plant"
    plant = brief["plant"]
    rgb = _hex_rgb(plant["color"])
    if rgb is None:
        return False, "plant color is not hex"
    start = int(plant["from_frame"])
    end = int(plant["to_frame"])
    inside_ok = 0
    inside_n = 0
    outside_bad = 0
    outside_n = 0
    width, height = Image.open(paths[0]).size
    ceiling = int(width * height * PLANT_MAX_FRACTION)
    for path in paths:
        match = re.search(r"(\d+)", path.stem)
        if not match:
            continue
        index = int(match.group(1))
        count = _count_near(Image.open(path), rgb)
        if start <= index <= end:
            inside_n += 1
            if PLANT_MIN_PIXELS <= count <= ceiling:
                inside_ok += 1
        else:
            outside_n += 1
            if count > OUTSIDE_MAX_PIXELS:
                outside_bad += 1
    if inside_n == 0:
        return False, "plant frame range is not in the frames"
    inside_frac = inside_ok / inside_n
    outside_frac = (outside_bad / outside_n) if outside_n else 0
    ok = inside_frac >= 0.8 and outside_frac <= 0.1
    if ok:
        return True, ""
    return False, f"plant pixels inside {inside_frac:.2f}, outside leaks {outside_frac:.2f}"
