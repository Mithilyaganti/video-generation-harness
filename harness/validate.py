"""Reject a scene record that drops the plant or makes the trap true."""

from __future__ import annotations


def _by_id(record: dict) -> dict[str, dict]:
    found = {}
    for obj in record.get("objects") or []:
        if isinstance(obj, dict) and obj.get("id"):
            found[obj["id"]] = obj
    return found


def validate_record(record: dict, brief: dict) -> list[str]:
    errors = []
    if not isinstance(record, dict):
        return ["record is not an object"]
    if record.get("scene_id") != brief["scene_id"]:
        errors.append("scene_id does not match the brief")
    for key in ("width", "height", "fps", "frame_count", "background"):
        if record.get(key) != brief[key]:
            errors.append(f"{key} does not match the brief")
    camera = record.get("camera") or {}
    if camera.get("kind") != brief["camera"]["kind"] or int(camera.get("pixels") or 0) != int(brief["camera"]["pixels"]):
        errors.append("camera does not match the brief")
    found = _by_id(record)
    for obj in brief["objects"]:
        got = found.get(obj["id"])
        if not got:
            errors.append(f"missing object {obj['id']}")
            continue
        if got.get("kind") != obj["kind"] or str(got.get("color", "")).lower() != obj["color"].lower():
            errors.append(f"{obj['id']} kind or color does not match the brief")
        if int(got.get("from_frame", -1)) != 0 or int(got.get("to_frame", -1)) != brief["frame_count"] - 1:
            errors.append(f"{obj['id']} should stay for every frame")
    plant = brief["plant"]
    got = found.get(plant["id"])
    if not got:
        errors.append(f"missing hidden plant {plant['id']}")
    else:
        if got.get("kind") != "plant" or not got.get("hidden"):
            errors.append("plant must be kind plant and hidden true")
        if str(got.get("color", "")).lower() != plant["color"].lower():
            errors.append("plant color does not match the brief")
        if int(got.get("from_frame", -1)) != plant["from_frame"] or int(got.get("to_frame", -1)) != plant["to_frame"]:
            errors.append("plant frame range does not match the brief")
    trap = record.get("trap") or {}
    expected = brief["trap"]
    for key in ("question", "asked_id", "asked_kind", "asked_attribute", "why_false", "nearby_id"):
        if trap.get(key) != expected[key]:
            errors.append(f"trap.{key} does not match the brief")
    if expected["why_false"] == "absent":
        for obj in record.get("objects") or []:
            if obj.get("id") == expected["asked_id"] or obj.get("kind") == expected["asked_kind"]:
                errors.append("record drew the object the trap says is missing")
    if expected["nearby_id"] not in found:
        errors.append("nearby object is not in the record")
    width = int(brief["width"])
    height = int(brief["height"])
    count = int(brief["frame_count"])
    for obj in record.get("objects") or []:
        if not isinstance(obj, dict) or "x" not in obj:
            continue
        start = int(obj.get("from_frame", 0))
        end = int(obj.get("to_frame", 0))
        for frame in {start, end}:
            x = int(obj["x"])
            pixels = int(brief["camera"]["pixels"])
            span = max(1, count - 1)
            t = frame / span
            if brief["camera"]["kind"] == "pan_right":
                x -= int(pixels * t)
            elif brief["camera"]["kind"] == "pan_left":
                x += int(pixels * t)
            y = int(obj.get("y", 0))
            w = int(obj.get("w", 0))
            h = int(obj.get("h", 0))
            if x < 0 or y < 0 or x + w > width or y + h > height:
                errors.append(f"{obj.get('id')} leaves the frame")
                break
    return errors


def record_from_brief(brief: dict) -> dict:
    """Last resort layout taken from the brief itself."""
    objects = []
    last = brief["frame_count"] - 1
    for obj in brief["objects"]:
        objects.append({**obj, "from_frame": 0, "to_frame": last, "hidden": False})
    plant = dict(brief["plant"])
    objects.append(plant)
    return {
        "scene_id": brief["scene_id"],
        "width": brief["width"],
        "height": brief["height"],
        "fps": brief["fps"],
        "frame_count": brief["frame_count"],
        "background": brief["background"],
        "camera": dict(brief["camera"]),
        "objects": objects,
        "trap": dict(brief["trap"]),
    }
