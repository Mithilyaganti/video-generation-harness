"""Score a timed picture, then apply the clip checker's shortcut tests.

A false question is not enough. The question has to stay unanswered by the
words alone, by one frame, and by a clip whose frames are reversed or shuffled.
"""

from __future__ import annotations

import importlib.util
import json
import random
import re
from pathlib import Path

from PIL import Image


NEAR = 35
MIN_PIXELS = 80
MAX_FRACTION = 0.08
OUTSIDE_MAX = 40
EVAL_PATH = Path("/cursor/stores/bc-f9fe9480-5b96-4277-be5d-c761609be7ed/internal/eval-checks/check.py")

_EVAL = None


def eval_checks():
    global _EVAL
    if _EVAL is None:
        spec = importlib.util.spec_from_file_location("vgh_eval_checks", EVAL_PATH)
        if spec is None or spec.loader is None:
            raise SystemExit(f"cannot load clip checker at {EVAL_PATH}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _EVAL = module
    return _EVAL


def _hex(value: str) -> tuple[int, int, int]:
    text = value.strip().lstrip("#")
    return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))


def _same_question(saved: str, expected: str) -> bool:
    fold = lambda text: re.sub(r"\s+", " ", (text or "").strip().lower())
    return fold(saved) == fold(expected)


def _frame_paths(run_dir: Path) -> dict[int, Path]:
    frames = run_dir / "frames"
    found = {}
    if not frames.exists():
        return found
    for path in frames.glob("f_*.png"):
        match = re.search(r"(\d+)", path.stem)
        if match:
            found[int(match.group(1))] = path
    return found


def _scan(path: Path, specs: list[tuple[str, tuple[int, int, int]]], board: tuple[int, int] | None):
    image = Image.open(path).convert("RGB")
    data = image.tobytes()
    width, height = image.size
    acc = {name: [0, 0, 0] for name, _rgb in specs}
    limit = NEAR * NEAR
    pixel_i = 0
    for offset in range(0, len(data), 3):
        red, green, blue = data[offset], data[offset + 1], data[offset + 2]
        x = pixel_i % width
        pixel_i += 1
        for name, rgb in specs:
            dist = (red - rgb[0]) ** 2 + (green - rgb[1]) ** 2 + (blue - rgb[2]) ** 2
            if dist <= limit:
                slot = acc[name]
                slot[0] += 1
                slot[1] += x
                if board is not None and board[0] <= x < board[1]:
                    slot[2] += 1
    return acc, width * height


def _bursts(labels: list[str], name: str) -> list[tuple[int, int]]:
    runs = []
    start = None
    for index, label in enumerate(labels):
        if label == name and start is None:
            start = index
        if label != name and start is not None:
            runs.append((start, index - 1))
            start = None
    if start is not None:
        runs.append((start, len(labels) - 1))
    merged = []
    for run in runs:
        if merged and run[0] - merged[-1][1] - 1 <= 1:
            merged[-1] = (merged[-1][0], run[1])
        else:
            merged.append(run)
    return merged


def _span(run: tuple[int, int]) -> int:
    return run[1] - run[0] + 1


def _indices(run: tuple[int, int]) -> set[int]:
    return set(range(run[0], run[1] + 1))


def _same_id(got, wanted: str) -> bool:
    text = str(got or "")
    if text == wanted:
        return True
    return text.startswith(wanted + "_") or text.startswith(wanted + "-")


def _logged(log: dict, obj_id: str) -> set[int]:
    found = set()
    for frame in log.get("frames") or []:
        index = int(frame.get("index", -1))
        for obj in frame.get("objects") or []:
            if _same_id(obj.get("id"), obj_id):
                found.add(index)
                break
    return found


def _overlap(expected: set[int], present: set[int]) -> float:
    union = expected | present
    if not union:
        return 1.0
    return len(expected & present) / len(union)


def _oracle_trap(brief: dict, saved: dict | None) -> dict:
    checks = eval_checks()
    trap = dict(brief["trap"])
    trap["why_false"] = str((saved or {}).get("why_false") or trap.get("why_false") or "")
    trap["false_key"] = checks.ABSTAIN
    trap["true_key"] = "Yes"
    trap["answers"] = [checks.ABSTAIN, "Yes"]
    return trap


def _checker_frames(count: int, present: dict[str, set[int]]) -> list[dict]:
    frames = []
    for index in range(count):
        objects = []
        for obj_id, indices in present.items():
            if index in indices:
                objects.append({"id": obj_id, "color": "#000000", "x": 0, "y": 0, "w": 8, "h": 8})
        frames.append({"index": index, "objects": objects})
    return frames


def _shuffle_changes(frames: list[dict], trap: dict, key: str) -> tuple[bool, str]:
    checks = eval_checks()
    rng = random.Random(1)
    contents = [frame.get("objects", []) for frame in frames]
    changed = 0
    usable = 0
    for _trial in range(20):
        order = list(range(len(frames)))
        rng.shuffle(order)
        if order == list(range(len(frames))):
            continue
        shuffled = [{"index": frames[i]["index"], "objects": contents[order[i]]} for i in range(len(frames))]
        flipped, _holds = checks.oracle_key(shuffled, trap)
        if flipped is None:
            continue
        usable += 1
        if flipped != key:
            changed += 1
    if usable == 0:
        return False, "a shuffled clip could not be keyed"
    return changed > 0, f"shuffling changed the key in {changed} of {usable} mixes"


def shortcut_report(frames: list[dict], trap: dict) -> dict:
    checks = eval_checks()
    claim = trap.get("claim") or {}
    holds = checks.claim_holds(frames, claim) if frames and claim else None
    key = None
    if frames and claim:
        key, _holds = checks.oracle_key(frames, trap)
    empty = {
        "no_video": False,
        "single_frame": False,
        "reversed": False,
        "shuffled": False,
        "detail": {"error": "the log cannot decide the claim"},
    }
    if not frames or holds is None or key is None:
        return empty
    single = checks.check_single_frame(frames, claim, holds, key, trap)
    reversed_check = checks.check_order(frames, trap, key)
    solved, why = checks.text_solves(trap.get("question", ""), trap.get("why_false") or "", key)
    shuffled, shuffle_why = _shuffle_changes(frames, trap, key)
    return {
        "no_video": not solved,
        "single_frame": bool(single["pass"]),
        "reversed": bool(reversed_check["pass"]),
        "shuffled": shuffled,
        "detail": {
            "no_video": why,
            "single_frame": single["detail"],
            "reversed": reversed_check["detail"],
            "shuffled": shuffle_why,
            "key": key,
            "claim_holds": holds,
        },
    }


def _finish_report(plant_ok: bool, notes: list[str], saved: dict | None, brief: dict, frames: list[dict]) -> dict:
    trap = _oracle_trap(brief, saved)
    question_ok = _same_question((saved or {}).get("question", ""), brief["trap"]["question"])
    if not question_ok:
        notes.append("saved question does not match the brief")
    report = shortcut_report(frames, trap)
    holds = (report.get("detail") or {}).get("claim_holds")
    trap_false = question_ok and holds is False
    if holds is True:
        notes.append("the asked order is actually true in the picture")
    if holds is None:
        notes.append("the picture does not show both events, so the question has no answer")
    temporal = report["reversed"] or report["shuffled"]
    trap_working = bool(trap_false and report["no_video"] and report["single_frame"] and temporal)
    if trap_false and not report["no_video"]:
        notes.append("the question text gives the answer away")
    if trap_false and not report["single_frame"]:
        notes.append("one frame is enough to answer")
    if trap_false and not temporal:
        notes.append("reversing or shuffling the frames leaves the answer unchanged")
    return {
        "plant_ok": plant_ok,
        "trap_false": trap_false,
        "trap_working": trap_working,
        "shortcuts": {key: report[key] for key in ("no_video", "single_frame", "reversed", "shuffled")},
        "shortcut_detail": report.get("detail") or {},
        "notes": notes,
    }


def _load_run(run_dir: Path) -> tuple[dict, dict | None]:
    log_path = run_dir / "log.json"
    trap_path = run_dir / "trap.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {"frames": []}
    saved = json.loads(trap_path.read_text()) if trap_path.exists() else None
    return log, saved


def _colors(brief: dict) -> dict[str, tuple[int, int, int]]:
    found = {}
    for obj in list(brief["objects"]) + list(brief.get("events") or []):
        found[obj["id"]] = _hex(obj["color"])
    return found


def score_delay(run_dir: Path, brief: dict) -> dict:
    notes = []
    paths = _frame_paths(run_dir)
    count = int(brief["frame_count"])
    if len(paths) < count:
        notes.append(f"expected {count} frames, found {len(paths)}")
        return _finish_report(False, notes, None, brief, [])
    spec = brief["delay"]
    colors = _colors(brief)
    trigger = spec["trigger"]
    plant = spec["plant"]
    prop = brief["objects"][0]["id"]
    watches = [(name, colors[name]) for name in (trigger, plant, prop)]
    tallies = []
    ceiling = None
    for index in range(count):
        acc, area = _scan(paths[index], watches, None)
        ceiling = int(area * MAX_FRACTION)
        tallies.append(acc)
    labels = []
    prop_hits = 0
    for acc in tallies:
        labels.append(_label_pair(acc, trigger, plant, ceiling))
        if acc[prop][0] >= MIN_PIXELS:
            prop_hits += 1
    plant_ok = prop_hits >= int(count * 0.9)
    if not plant_ok:
        notes.append("the lasting object is missing from too many frames")
    trigger_runs = _bursts(labels, "trigger")
    plant_runs = _bursts(labels, "plant")
    both = sum(1 for label in labels if label == "both")
    if both:
        plant_ok = False
        notes.append("the plant and the earlier object are on screen together")
    if len(trigger_runs) != 1 or len(plant_runs) != 1:
        plant_ok = False
        notes.append(f"expected one short appearance each, saw trigger {trigger_runs} plant {plant_runs}")
    else:
        trig, leaf = trigger_runs[0], plant_runs[0]
        gap = leaf[0] - trig[1] - 1
        trigger_max = int(spec.get("trigger_max_span", spec["max_span"]))
        if not (spec["min_span"] <= _span(trig) <= trigger_max):
            plant_ok = False
            notes.append(f"the earlier object lasts {_span(trig)} frames")
        if not (spec["min_span"] <= _span(leaf) <= spec["max_span"]):
            plant_ok = False
            notes.append(f"the plant lasts {_span(leaf)} frames")
        if not (spec["min_gap"] <= gap <= spec["max_gap"]):
            plant_ok = False
            wanted = spec.get("gap_words", "about 0.8 seconds")
            notes.append(f"the wait after the first object is {gap} frames, not {wanted}")
        if trig[0] > spec["trigger_start_max"]:
            plant_ok = False
            notes.append("the first object does not appear near the start")
        if leaf[0] <= trig[1]:
            plant_ok = False
            notes.append("the plant does not come after the first object")
        log, saved = _load_run(run_dir)
        if not brief.get("pixels_are_enough"):
            for name, run in ((trigger, trig), (plant, leaf)):
                logged = _logged(log, name)
                if _overlap(_indices(run), logged) < 0.8:
                    plant_ok = False
                    notes.append(f"the log does not match the frames for {name}")
        notes.append(f"trigger frames {trig[0]}-{trig[1]}, plant frames {leaf[0]}-{leaf[1]}, gap {gap}")
        present = {trigger: _indices(trig), plant: _indices(leaf)}
        return _finish_report(plant_ok, notes, saved, brief, _checker_frames(count, present))
    log, saved = _load_run(run_dir)
    return _finish_report(False, notes, saved, brief, _checker_frames(count, {}))


def _label_pair(acc: dict, trigger: str, plant: str, ceiling: int) -> str:
    trig_on = MIN_PIXELS <= acc[trigger][0] <= ceiling
    plant_on = MIN_PIXELS <= acc[plant][0] <= ceiling
    if trig_on and plant_on:
        return "both"
    if trig_on:
        return "trigger"
    if plant_on:
        return "plant"
    return "off"


def score_cover(run_dir: Path, brief: dict) -> dict:
    notes = []
    paths = _frame_paths(run_dir)
    count = int(brief["frame_count"])
    if len(paths) < count:
        notes.append(f"expected {count} frames, found {len(paths)}")
        return _finish_report(False, notes, None, brief, [])
    spec = brief["cover"]
    colors = _colors(brief)
    mover = spec["mover"]
    board = spec["board"]
    board_obj = next(obj for obj in brief["objects"] if obj["id"] == board)
    span = (int(board_obj["x"]), int(board_obj["x"]) + int(board_obj["w"]))
    watches = [(mover, colors[mover]), (board, colors[board])]
    labels = []
    board_hits = 0
    for index in range(count):
        acc, _area = _scan(paths[index], watches, span)
        mover_count, sum_x, on_board = acc[mover]
        if acc[board][0] >= MIN_PIXELS:
            board_hits += 1
        labels.append(_cover_label(mover_count, sum_x, on_board, span))
    plant_ok = board_hits >= int(count * 0.9)
    if not plant_ok:
        notes.append("the board is missing from too many frames")
    on_board = [index for index, label in enumerate(labels) if label == "on_board"]
    left = [index for index, label in enumerate(labels) if label == "left"]
    right = [index for index, label in enumerate(labels) if label == "right"]
    if on_board:
        plant_ok = False
        notes.append(f"the mover is visible across the board on {len(on_board)} frames")
    if len(left) < spec["side_min"] or len(right) < spec["side_min"]:
        plant_ok = False
        notes.append(f"left sightings {len(left)}, right sightings {len(right)}")
    hidden: set[int] = set()
    if left and right and min(right) > max(i for i in left if i < min(right)):
        last_left = max(i for i in left if i < min(right))
        first_right = min(right)
        hidden = set(range(last_left + 1, first_right))
        if len(hidden) < spec["min_hidden"]:
            plant_ok = False
            notes.append(f"the mover is hidden for {len(hidden)} frames while it crosses")
        if any(labels[index] != "off" for index in hidden):
            plant_ok = False
            notes.append("the crossing is not a clean gap")
        if min(left) > count // 2:
            plant_ok = False
            notes.append("the mover does not start on the left")
    else:
        plant_ok = False
        notes.append("the mover does not travel from the left to the right")
    log, saved = _load_run(run_dir)
    logged = _logged(log, mover)
    if left and right and hidden:
        left_seen = len(set(left) & logged) / len(left)
        right_seen = len(set(right) & logged) / len(right)
        if left_seen < 0.8 or right_seen < 0.8:
            plant_ok = False
            notes.append("the log misses the mover on a side where it is visible")
        leaked = len(hidden & logged) / len(hidden)
        if leaked > 0.1:
            plant_ok = False
            notes.append("the log still lists the mover while it is behind the board")
    left_before = {index for index in left if not right or index < min(right)}
    right_after = {index for index in right if left_before and index > max(left_before)}
    claim_ids = {
        brief["trap"]["claim"]["earlier"]: right_after if brief["trap"]["claim"]["earlier"].endswith("right") else left_before,
        brief["trap"]["claim"]["later"]: left_before if brief["trap"]["claim"]["later"].endswith("left") else right_after,
    }
    if plant_ok and left and right:
        notes.append(f"left {min(left)}-{max(left)}, hidden {len(hidden)} frames, right {min(right)}-{max(right)}")
    return _finish_report(plant_ok, notes, saved, brief, _checker_frames(count, claim_ids))


def _cover_label(count: int, sum_x: int, on_board: int, span: tuple[int, int]) -> str:
    if on_board > OUTSIDE_MAX and count >= MIN_PIXELS:
        return "on_board"
    if count < MIN_PIXELS:
        return "off"
    center = sum_x / count
    if center < span[0]:
        return "left"
    if center >= span[1]:
        return "right"
    return "on_board"


def score_count(run_dir: Path, brief: dict) -> dict:
    notes = []
    paths = _frame_paths(run_dir)
    count = int(brief["frame_count"])
    if len(paths) < count:
        notes.append(f"expected {count} frames, found {len(paths)}")
        return _finish_report(False, notes, None, brief, [])
    spec = brief["count"]
    colors = _colors(brief)
    color_id = spec["color_id"]
    prop = brief["objects"][0]["id"]
    watches = [(color_id, colors[color_id]), (prop, colors[prop])]
    area = int(spec["unit_w"]) * int(spec["unit_h"])
    labels = []
    prop_hits = 0
    for index in range(count):
        acc, _pixels = _scan(paths[index], watches, None)
        if acc[prop][0] >= MIN_PIXELS:
            prop_hits += 1
        labels.append(_count_label(acc[color_id][0], area, spec["first"], spec["second"]))
    plant_ok = prop_hits >= int(count * 0.9)
    if not plant_ok:
        notes.append("the lasting object is missing from too many frames")
    if any(label == "other" for label in labels):
        plant_ok = False
        notes.append("a frame has a block count that is neither empty, two, nor four")
    first_runs = _bursts(labels, "first")
    second_runs = _bursts(labels, "second")
    if len(first_runs) != 1 or len(second_runs) != 1:
        plant_ok = False
        notes.append(f"expected one pair of counts, saw two-block {first_runs} four-block {second_runs}")
    else:
        first, second = first_runs[0], second_runs[0]
        gap = second[0] - first[1] - 1
        if not (spec["min_span"] <= _span(first) <= spec["max_span"]):
            plant_ok = False
            notes.append(f"the first count lasts {_span(first)} frames")
        if not (spec["min_span"] <= _span(second) <= spec["max_span"]):
            plant_ok = False
            notes.append(f"the second count lasts {_span(second)} frames")
        if not (spec["min_gap"] <= gap <= spec["max_gap"]):
            plant_ok = False
            notes.append(f"the wait between counts is {gap} frames, not about 0.8 seconds")
        if first[0] > spec["trigger_start_max"] or second[0] <= first[1]:
            plant_ok = False
            notes.append("the two blocks do not come first")
        gap_idx = set(range(first[1] + 1, second[0]))
        if any(labels[index] != "empty" for index in gap_idx):
            plant_ok = False
            notes.append("blocks stay on screen between the two counts")
        log, saved = _load_run(run_dir)
        logged = _logged(log, color_id)
        if _overlap(_indices(first) | _indices(second), logged) < 0.8:
            plant_ok = False
            notes.append("the log misses the blocks while they are visible")
        if gap_idx and len(gap_idx & logged) / len(gap_idx) > 0.1:
            plant_ok = False
            notes.append("the log still lists blocks during the wait")
        present = {"blocks_two": _indices(first), "blocks_four": _indices(second)}
        notes.append(f"two blocks {first[0]}-{first[1]}, four blocks {second[0]}-{second[1]}, gap {gap}")
        return _finish_report(plant_ok, notes, saved, brief, _checker_frames(count, present))
    _log, saved = _load_run(run_dir)
    return _finish_report(False, notes, saved, brief, _checker_frames(count, {}))


def _count_label(pixels: int, area: int, first: int, second: int) -> str:
    if pixels <= OUTSIDE_MAX:
        return "empty"
    ratio = pixels / float(area)
    if abs(ratio - first) <= 0.45:
        return "first"
    if abs(ratio - second) <= 0.55:
        return "second"
    return "other"


def _on_labels(rows: list[dict], names: list[str], ceiling: int) -> list[str]:
    labels = []
    for acc in rows:
        showing = [name for name in names if MIN_PIXELS <= acc[name][0] <= ceiling]
        if len(showing) > 1:
            labels.append("mix")
        elif len(showing) == 1:
            labels.append(showing[0])
        else:
            labels.append("off")
    return labels


def score_order(run_dir: Path, brief: dict) -> dict:
    notes = []
    paths = _frame_paths(run_dir)
    count = int(brief["frame_count"])
    if len(paths) < count:
        return _finish_report(False, [f"expected {count} frames, found {len(paths)}"], None, brief, [])
    spec = brief["order"]
    steps = list(spec["steps"])
    colors = _colors(brief)
    prop = brief["objects"][0]["id"]
    watches = [(name, colors[name]) for name in steps + [prop]]
    rows = []
    ceiling = 0
    prop_hits = 0
    for index in range(count):
        acc, area = _scan(paths[index], watches, None)
        ceiling = int(area * MAX_FRACTION)
        rows.append(acc)
        if acc[prop][0] >= MIN_PIXELS:
            prop_hits += 1
    labels = _on_labels(rows, steps, ceiling)
    plant_ok = prop_hits >= int(count * 0.9)
    if not plant_ok:
        notes.append("the lasting object is missing from too many frames")
    if any(label == "mix" for label in labels):
        plant_ok = False
        notes.append("two events are on screen together")
    runs = {name: _bursts(labels, name) for name in steps}
    if any(len(runs[name]) != 1 for name in steps):
        plant_ok = False
        notes.append("each event should appear once: " + ", ".join(f"{name} {runs[name]}" for name in steps))
        _log, saved = _load_run(run_dir)
        return _finish_report(False, notes, saved, brief, _checker_frames(count, {}))
    ordered = [(name, runs[name][0]) for name in steps]
    for name, run in ordered:
        if not (spec["min_span"] <= _span(run) <= spec["max_span"]):
            plant_ok = False
            notes.append(f"{name} lasts {_span(run)} frames")
    if ordered[0][1][0] > spec["first_start_max"]:
        plant_ok = False
        notes.append("the first event is not near the start")
    for (prev_name, prev), (next_name, nxt) in zip(ordered, ordered[1:]):
        gap = nxt[0] - prev[1] - 1
        if nxt[0] <= prev[1]:
            plant_ok = False
            notes.append(f"{next_name} does not come after {prev_name}")
        elif not (spec["min_gap"] <= gap <= spec["max_gap"]):
            plant_ok = False
            notes.append(f"the wait between {prev_name} and {next_name} is {gap} frames")
    present = {name: _indices(run) for name, run in ordered}
    log, saved = _load_run(run_dir)
    if not brief.get("pixels_are_enough"):
        for name, run in ordered:
            if _overlap(_indices(run), _logged(log, name)) < 0.8:
                plant_ok = False
                notes.append(f"the log does not match the frames for {name}")
    notes.append(", ".join(f"{name} {run[0]}-{run[1]}" for name, run in ordered))
    return _finish_report(plant_ok, notes, saved, brief, _checker_frames(count, present))


def score_reappear(run_dir: Path, brief: dict) -> dict:
    notes = []
    paths = _frame_paths(run_dir)
    count = int(brief["frame_count"])
    if len(paths) < count:
        return _finish_report(False, [f"expected {count} frames, found {len(paths)}"], None, brief, [])
    spec = brief["reappear"]
    colors = _colors(brief)
    mover = spec["mover"]
    board = spec["board"]
    board_obj = next(obj for obj in brief["objects"] if obj["id"] == board)
    span = (int(board_obj["x"]), int(board_obj["x"]) + int(board_obj["w"]))
    area = int(spec["unit_w"]) * int(spec["unit_h"])
    watches = [(mover, colors[mover]), (board, colors[board])]
    labels = []
    board_hits = 0
    for index in range(count):
        acc, _area = _scan(paths[index], watches, span)
        if acc[board][0] >= MIN_PIXELS:
            board_hits += 1
        labels.append(_reappear_label(acc[mover], span, area, int(spec["enter"]), int(spec["leave"])))
    plant_ok = board_hits >= int(count * 0.9)
    if not plant_ok:
        notes.append("the board is missing from too many frames")
    if any(label == "on_board" for label in labels):
        plant_ok = False
        notes.append("the mover is visible on the board")
    if any(label == "other" for label in labels):
        plant_ok = False
        notes.append("a frame has the wrong count or the wrong side")
    enter_runs = _bursts(labels, "enter")
    leave_runs = _bursts(labels, "leave")
    if len(enter_runs) != 1 or len(leave_runs) != 1:
        plant_ok = False
        notes.append(f"expected one entrance and one exit, saw {enter_runs} {leave_runs}")
        _log, saved = _load_run(run_dir)
        return _finish_report(False, notes, saved, brief, _checker_frames(count, {}))
    enter, leave = enter_runs[0], leave_runs[0]
    hidden = set(range(enter[1] + 1, leave[0]))
    if leave[0] <= enter[1] or len(hidden) < spec["min_hidden"]:
        plant_ok = False
        notes.append(f"the hide between the two counts lasts {len(hidden)} frames")
    if any(labels[index] != "off" for index in hidden):
        plant_ok = False
        notes.append("the crossing is not a clean gap")
    if _span(enter) < spec["side_min"] or _span(leave) < spec["side_min"]:
        plant_ok = False
        notes.append("one side of the crossing is too short")
    if enter[0] > spec["first_start_max"]:
        plant_ok = False
        notes.append("the first ball does not start near the beginning")
    present = {spec["enter_id"]: _indices(enter), spec["leave_id"]: _indices(leave)}
    _log, saved = _load_run(run_dir)
    if plant_ok:
        notes.append(f"enter {enter[0]}-{enter[1]}, hidden {len(hidden)}, leave {leave[0]}-{leave[1]}")
    return _finish_report(plant_ok, notes, saved, brief, _checker_frames(count, present))


def _reappear_label(slot: list[int], span: tuple[int, int], area: int, enter: int, leave: int) -> str:
    count, sum_x, on_board = slot
    if on_board > OUTSIDE_MAX and count >= MIN_PIXELS:
        return "on_board"
    if count <= OUTSIDE_MAX:
        return "off"
    center = sum_x / count
    ratio = count / float(area)
    if abs(ratio - enter) <= 0.45 and center < span[0]:
        return "enter"
    if abs(ratio - leave) <= 0.55 and center >= span[1]:
        return "leave"
    return "other"


def score_pan_cross(run_dir: Path, brief: dict) -> dict:
    notes = []
    paths = _frame_paths(run_dir)
    count = int(brief["frame_count"])
    if len(paths) < count:
        return _finish_report(False, [f"expected {count} frames, found {len(paths)}"], None, brief, [])
    spec = brief["pan_cross"]
    colors = _colors(brief)
    mover = spec["mover"]
    anchor = spec["anchor"]
    watches = [(mover, colors[mover]), (anchor, colors[anchor])]
    anchor_x = []
    mover_x = []
    for index in range(count):
        acc, _area = _scan(paths[index], watches, None)
        anchor_x.append(acc[anchor][1] / acc[anchor][0] if acc[anchor][0] >= MIN_PIXELS else None)
        mover_x.append(acc[mover][1] / acc[mover][0] if acc[mover][0] >= MIN_PIXELS else None)
    seen = [(index, x) for index, x in enumerate(anchor_x) if x is not None]
    plant_ok = len(seen) >= int(count * 0.9)
    if not plant_ok:
        notes.append("the post is missing from too many frames")
    if seen:
        delta = seen[-1][1] - seen[0][1]
        want = int(spec["min_shift"])
        if spec["direction"] == "pan_right" and delta > -want:
            plant_ok = False
            notes.append(f"the post shifted {delta:.0f} pixels, so the camera pan is missing")
        if spec["direction"] == "pan_left" and delta < want:
            plant_ok = False
            notes.append(f"the post shifted {delta:.0f} pixels, so the camera pan is missing")
    labels = []
    for index in range(count):
        if mover_x[index] is None or anchor_x[index] is None:
            labels.append("off")
        elif mover_x[index] < anchor_x[index] - 8:
            labels.append("left")
        elif mover_x[index] > anchor_x[index] + 8:
            labels.append("right")
        else:
            labels.append("cross")
    left_runs = _bursts(labels, "left")
    right_runs = _bursts(labels, "right")
    if len(left_runs) != 1 or len(right_runs) != 1:
        plant_ok = False
        notes.append(f"expected the mover on each side once, saw left {left_runs} right {right_runs}")
        _log, saved = _load_run(run_dir)
        return _finish_report(False, notes, saved, brief, _checker_frames(count, {}))
    left, right = left_runs[0], right_runs[0]
    if right[0] <= left[1]:
        plant_ok = False
        notes.append("the mover is on the right before it finishes the left side")
    if _span(left) < spec["side_min"] or _span(right) < spec["side_min"]:
        plant_ok = False
        notes.append("one side of the post is too brief")
    present = {spec["left_id"]: _indices(left), spec["right_id"]: _indices(right)}
    _log, saved = _load_run(run_dir)
    if plant_ok:
        notes.append(f"left {left[0]}-{left[1]}, right {right[0]}-{right[1]}")
    return _finish_report(plant_ok, notes, saved, brief, _checker_frames(count, present))


def score_task(run_dir: Path, brief: dict) -> dict:
    kind = brief.get("task")
    if kind == "delay":
        return score_delay(run_dir, brief)
    if kind == "cover":
        return score_cover(run_dir, brief)
    if kind == "count":
        return score_count(run_dir, brief)
    if kind == "order":
        return score_order(run_dir, brief)
    if kind == "reappear":
        return score_reappear(run_dir, brief)
    if kind == "pan_cross":
        return score_pan_cross(run_dir, brief)
    return _finish_report(False, [f"unknown task {kind}"], None, brief, [])


def report_saved_clip(directory: Path) -> dict:
    """Shortcut checks for a clip that already has a log. Absent traps are filled in."""
    directory = Path(directory)
    log = json.loads((directory / "log.json").read_text())
    trap = json.loads((directory / "trap.json").read_text())
    checks = eval_checks()
    if "claim" not in trap and trap.get("asked_id"):
        trap = dict(trap)
        trap["claim"] = {"type": "absent", "object": trap["asked_id"]}
    trap.setdefault("false_key", checks.ABSTAIN)
    trap.setdefault("true_key", "Yes")
    frames = checks.frame_list(log)
    return shortcut_report(frames, trap)


def _solid(draw, box, color: str) -> None:
    x, y, w, h = box
    draw.rectangle((x, y, x + w - 1, y + h - 1), fill=color)


def _paint_cover(out_dir: Path, brief: dict, hide: bool) -> None:
    from PIL import ImageDraw

    out_dir.mkdir(parents=True)
    frames = out_dir / "frames"
    frames.mkdir()
    board = brief["objects"][0]
    marble = brief["events"][0]
    log_frames = []
    for index in range(int(brief["frame_count"])):
        image = Image.new("RGB", (brief["width"], brief["height"]), brief["background"])
        draw = ImageDraw.Draw(image)
        _solid(draw, (board["x"], board["y"], board["w"], board["h"]), board["color"])
        x = 40 + int(round(480 * index / 47))
        overlaps = x < board["x"] + board["w"] and x + marble["w"] > board["x"]
        objects = [
            {"id": "board", "kind": "board", "color": board["color"], "x": board["x"], "y": board["y"], "w": board["w"], "h": board["h"]}
        ]
        if not overlaps or not hide:
            _solid(draw, (x, marble["y"], marble["w"], marble["h"]), marble["color"])
            objects.append(
                {"id": "marble", "kind": "marble", "color": marble["color"], "x": x, "y": marble["y"], "w": marble["w"], "h": marble["h"]}
            )
        image.save(frames / f"f_{index:03d}.png")
        log_frames.append({"index": index, "objects": objects})
    (out_dir / "log.json").write_text(json.dumps({"frames": log_frames}))
    (out_dir / "trap.json").write_text(json.dumps(brief["trap"]))


def _paint_counts(out_dir: Path, brief: dict, correct: bool) -> None:
    from PIL import ImageDraw

    out_dir.mkdir(parents=True)
    frames = out_dir / "frames"
    frames.mkdir()
    bowl = brief["objects"][0]
    block = brief["events"][0]
    log_frames = []
    for index in range(int(brief["frame_count"])):
        image = Image.new("RGB", (brief["width"], brief["height"]), brief["background"])
        draw = ImageDraw.Draw(image)
        _solid(draw, (bowl["x"], bowl["y"], bowl["w"], bowl["h"]), bowl["color"])
        if correct and 2 <= index <= 6:
            how_many = 2
        elif correct and 16 <= index <= 21:
            how_many = 4
        elif not correct:
            how_many = 4
        else:
            how_many = 0
        objects = [
            {"id": "bowl", "kind": "bowl", "color": bowl["color"], "x": bowl["x"], "y": bowl["y"], "w": bowl["w"], "h": bowl["h"]}
        ]
        for number in range(how_many):
            x = 80 + number * 60
            _solid(draw, (x, block["y"], block["w"], block["h"]), block["color"])
            objects.append(
                {"id": "block", "kind": "block", "color": block["color"], "x": x, "y": block["y"], "w": block["w"], "h": block["h"]}
            )
        image.save(frames / f"f_{index:03d}.png")
        log_frames.append({"index": index, "objects": objects})
    (out_dir / "log.json").write_text(json.dumps({"frames": log_frames}))
    (out_dir / "trap.json").write_text(json.dumps(brief["trap"]))


def _paint_labeled(out_dir: Path, brief: dict, frames_of) -> None:
    from PIL import ImageDraw

    out_dir.mkdir(parents=True)
    frames = out_dir / "frames"
    frames.mkdir()
    log_frames = []
    for index in range(int(brief["frame_count"])):
        image = Image.new("RGB", (brief["width"], brief["height"]), brief["background"])
        draw = ImageDraw.Draw(image)
        objects = []
        for box in frames_of(index):
            _solid(draw, (box["x"], box["y"], box["w"], box["h"]), box["color"])
            objects.append(box)
        image.save(frames / f"f_{index:03d}.png")
        log_frames.append({"index": index, "objects": objects})
    (out_dir / "log.json").write_text(json.dumps({"frames": log_frames}))
    (out_dir / "trap.json").write_text(json.dumps(brief["trap"]))


def _shrink(brief: dict, count: int) -> dict:
    copy = json.loads(json.dumps(brief))
    copy["frame_count"] = count
    return copy


def _check_harder_prompts() -> None:
    from harness.briefs import load_brief, prose

    for scene_id in ("order-band", "reappear-balls", "pan-moth", "buried-glint"):
        text = prose(load_brief(scene_id)).lower()
        if "plant" in text or "from_frame" in text or "through" in text:
            raise SystemExit(f"{scene_id} prompt names a plant or gives frame numbers")


def _check_harder_pictures(root: Path) -> None:
    from harness.briefs import load_brief

    order = _shrink(load_brief("order-band"), 24)
    order["order"].update({"min_gap": 3, "max_gap": 6, "min_span": 2, "max_span": 5, "first_start_max": 2})
    stool = {"id": "stool", "kind": "stool", "color": "#5c6b73", "x": 480, "y": 160, "w": 70, "h": 80}
    horn = {"id": "horn", "kind": "horn", "color": "#e2c14a", "x": 200, "y": 170, "w": 70, "h": 40}
    bell = {"id": "bell", "kind": "bell", "color": "#2a62c9", "x": 300, "y": 150, "w": 48, "h": 48}
    drum = {"id": "drum", "kind": "drum", "color": "#c0392b", "x": 120, "y": 160, "w": 64, "h": 48}

    def boxes_for(spans):
        def draw(index):
            boxes = [dict(stool)]
            for box, start, end in spans:
                if start <= index <= end:
                    boxes.append(dict(box))
            return boxes
        return draw

    _paint_labeled(root / "order-good", order, boxes_for([(horn, 0, 2), (bell, 7, 9), (drum, 14, 16)]))
    good = score_task(root / "order-good", order)
    if not good["plant_ok"] or not good["trap_working"]:
        raise SystemExit(f"a correct three-event order failed: {json.dumps(good, indent=2)}")
    print("pass three-event order")
    _paint_labeled(root / "order-bad", order, boxes_for([(drum, 0, 2), (bell, 7, 9), (horn, 14, 16)]))
    if score_task(root / "order-bad", order)["plant_ok"]:
        raise SystemExit("mention order still passed the horn-first rule")
    print("rejected drum-first order")

    balls = _shrink(load_brief("reappear-balls"), 24)
    balls["reappear"].update({"min_hidden": 3, "side_min": 3, "first_start_max": 2})
    board = {"id": "board", "kind": "board", "color": "#6b4423", "x": 280, "y": 70, "w": 80, "h": 210}

    def ball_at(x, index_ok):
        return {"id": "ball", "kind": "ball", "color": "#d42323", "x": x, "y": 160, "w": 28, "h": 28}

    def re_draw(correct):
        def draw(index):
            boxes = [dict(board)]
            if 0 <= index <= 4:
                boxes.append(ball_at(40, True))
            if 12 <= index <= 16:
                xs = (420, 460, 500) if correct else (420,)
                for x in xs:
                    boxes.append(ball_at(x, True))
            return boxes
        return draw

    _paint_labeled(root / "re-good", balls, re_draw(True))
    re_good = score_task(root / "re-good", balls)
    if not re_good["plant_ok"] or not re_good["trap_working"]:
        raise SystemExit(f"a count change after a hide failed: {json.dumps(re_good, indent=2)}")
    print("pass hide then three balls")
    _paint_labeled(root / "re-bad", balls, re_draw(False))
    if score_task(root / "re-bad", balls)["plant_ok"]:
        raise SystemExit("one ball coming back out still passed")
    print("rejected a hide that does not change the count")

    pan = _shrink(load_brief("pan-moth"), 24)
    pan["pan_cross"]["min_shift"] = 30
    pan["pan_cross"]["side_min"] = 3

    def pan_draw(cross):
        def draw(index):
            post_x = 360 - index * 2
            boxes = [{"id": "post", "kind": "post", "color": "#e07a2f", "x": post_x, "y": 80, "w": 24, "h": 200}]
            if index <= 8:
                moth_x = post_x - 50
            elif cross and index >= 12:
                moth_x = post_x + 40
            elif not cross:
                moth_x = post_x - 50
            else:
                return boxes
            boxes.append({"id": "moth", "kind": "moth", "color": "#f4f7f2", "x": moth_x, "y": 150, "w": 22, "h": 16})
            return boxes
        return draw

    _paint_labeled(root / "pan-good", pan, pan_draw(True))
    pan_good = score_task(root / "pan-good", pan)
    if not pan_good["plant_ok"] or not pan_good["trap_working"]:
        raise SystemExit(f"a crossing during a pan failed: {json.dumps(pan_good, indent=2)}")
    print("pass left-to-right after a camera pan")
    _paint_labeled(root / "pan-bad", pan, pan_draw(False))
    if score_task(root / "pan-bad", pan)["plant_ok"]:
        raise SystemExit("a moth that stays left of the post still passed")
    print("rejected a moth that never crosses")

    glint = _shrink(load_brief("buried-glint"), 24)
    glint["delay"].update({"min_gap": 4, "max_gap": 8, "min_span": 2, "max_span": 4, "trigger_max_span": 4, "trigger_start_max": 2})
    tray = {"id": "tray", "kind": "tray", "color": "#6b4423", "x": 470, "y": 180, "w": 110, "h": 36}
    kettle = {"id": "kettle", "kind": "kettle", "color": "#2a62c9", "x": 80, "y": 140, "w": 70, "h": 80}
    spark = {"id": "glint", "kind": "glint", "color": "#e38b2f", "x": 300, "y": 160, "w": 16, "h": 16}

    def glint_draw(show):
        def draw(index):
            boxes = [dict(tray)]
            if 0 <= index <= 2:
                boxes.append(dict(kettle))
            if show and 8 <= index <= 10:
                boxes.append(dict(spark))
            return boxes
        return draw

    _paint_labeled(root / "glint-good", glint, glint_draw(True))
    glint_good = score_task(root / "glint-good", glint)
    if not glint_good["plant_ok"] or not glint_good["trap_working"]:
        raise SystemExit(f"a buried glint failed: {json.dumps(glint_good, indent=2)}")
    print("pass a short glint that is not called a plant")
    _paint_labeled(root / "glint-bad", glint, glint_draw(False))
    if score_task(root / "glint-bad", glint)["plant_ok"]:
        raise SystemExit("a clip with no glint still passed")
    print("rejected a missing glint")


def self_check() -> None:
    import tempfile

    from harness.briefs import load_brief, prose
    from harness.compile_scene import render_record

    delay = load_brief("delay-cart")
    needle = load_brief("needle-thread")
    if "from_frame" in prose(needle) or "through" in prose(needle) or "96" not in prose(needle):
        raise SystemExit("the needle prompt leaked frames or dropped the longer clip")
    text = prose(delay)
    if "from_frame" in text or "through" in text or "min_gap" in text:
        raise SystemExit("the delay prompt still gives the frame window away")
    if "0.8" not in text:
        raise SystemExit("the delay prompt dropped the timing rule")

    def delay_record(plant_start: int) -> dict:
        objects = []
        for obj in delay["objects"]:
            objects.append({**obj, "from_frame": 0, "to_frame": 47})
        objects.append({**delay["events"][0], "from_frame": 2, "to_frame": 6})
        objects.append({**delay["events"][1], "from_frame": plant_start, "to_frame": plant_start + 5})
        return {
            "scene_id": delay["scene_id"],
            "width": 640,
            "height": 360,
            "fps": 12,
            "frame_count": 48,
            "background": delay["background"],
            "camera": delay["camera"],
            "objects": objects,
            "trap": delay["trap"],
        }

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        good = root / "good"
        render_record(delay_record(16), good, write_video=False)
        good_score = score_task(good, delay)
        if not good_score["plant_ok"] or not good_score["trap_working"]:
            raise SystemExit(f"a correct delay failed: {json.dumps(good_score, indent=2)}")
        print("pass delay timing and shortcut checks")
        renamed = json.loads((good / "log.json").read_text())
        for frame in renamed["frames"]:
            for obj in frame["objects"]:
                if obj["id"] in {"cart", "marigold", "crate"}:
                    obj["id"] = obj["id"] + "_1"
        (good / "log.json").write_text(json.dumps(renamed))
        suffix_score = score_task(good, delay)
        if not suffix_score["plant_ok"] or not suffix_score["trap_working"]:
            raise SystemExit(f"a suffixed id failed: {json.dumps(suffix_score, indent=2)}")
        print("pass delay when the log adds a suffix to each id")

        early = root / "early"
        render_record(delay_record(8), early, write_video=False)
        early_score = score_task(early, delay)
        if early_score["plant_ok"]:
            raise SystemExit("a plant that follows too soon still passed")
        print("rejected a delay that is too short")

        cover = load_brief("cover-marble")
        if "from_frame" in prose(cover) or "through" in prose(cover):
            raise SystemExit("the cover prompt still gives frame numbers")
        _paint_cover(root / "cover-good", cover, hide=True)
        cover_good = score_task(root / "cover-good", cover)
        if not cover_good["plant_ok"] or not cover_good["trap_working"]:
            raise SystemExit(f"a covered crossing failed: {json.dumps(cover_good, indent=2)}")
        print("pass covered crossing and shortcut checks")
        _paint_cover(root / "cover-bad", cover, hide=False)
        if score_task(root / "cover-bad", cover)["plant_ok"]:
            raise SystemExit("a marble drawn across the board still passed")
        print("rejected a marble that stays visible on the board")

        counted = load_brief("count-blocks")
        if "from_frame" in prose(counted) or "through" in prose(counted):
            raise SystemExit("the count prompt still gives frame numbers")
        _paint_counts(root / "count-good", counted, correct=True)
        count_good = score_task(root / "count-good", counted)
        if not count_good["plant_ok"] or not count_good["trap_working"]:
            raise SystemExit(f"a changing count failed: {json.dumps(count_good, indent=2)}")
        print("pass changing counts and shortcut checks")
        _paint_counts(root / "count-bad", counted, correct=False)
        if score_task(root / "count-bad", counted)["plant_ok"]:
            raise SystemExit("a clip that keeps four blocks still passed")
        print("rejected a count that never changes")

        _check_harder_prompts()
        _check_harder_pictures(root)
        absent_frames = [
            {"index": i, "objects": [{"id": "mug", "color": "#e07a2f", "x": 1, "y": 1, "w": 8, "h": 8}]}
            for i in range(48)
        ]
        absent_trap = {
            "question": "What color is the water bottle beside the mug?",
            "why_false": "absent",
            "claim": {"type": "absent", "object": "water_bottle"},
            "false_key": eval_checks().ABSTAIN,
            "true_key": "Yes",
        }
        absent = shortcut_report(absent_frames, absent_trap)
        if absent["single_frame"] or absent["reversed"]:
            raise SystemExit(f"an absent-object trap passed a shortcut check: {absent}")
        print("absent trap fails single-frame and reverse")

    print("task checks ok")
