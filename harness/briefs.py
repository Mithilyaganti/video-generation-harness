"""Load a scene brief and say it in plain sentences."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIEFS = ROOT / "briefs"


def load_brief(scene_id: str) -> dict:
    path = BRIEFS / f"{scene_id}.json"
    if not path.exists():
        known = ", ".join(sorted(p.stem for p in BRIEFS.glob("*.json")))
        raise SystemExit(f"unknown scene {scene_id}. known: {known}")
    return json.loads(path.read_text())


def prose(brief: dict) -> str:
    camera = brief["camera"]
    if camera["kind"] == "static":
        camera_line = "The camera stays still."
    elif camera["kind"] == "pan_right":
        camera_line = f"The camera pans right by about {camera['pixels']} pixels across the clip."
    else:
        camera_line = f"The camera pans left by about {camera['pixels']} pixels across the clip."
    lines = [
        f"Scene {brief['scene_id']}: {brief['setting']}.",
        f"Picture size {brief['width']} by {brief['height']}. {brief['frame_count']} frames. {brief['fps']} frames a second.",
        f"Background color {brief['background']}.",
        camera_line,
        "Objects that stay visible the whole time:",
    ]
    last = brief["frame_count"] - 1
    for obj in brief["objects"]:
        lines.append(
            f"- {obj['id']}, a {obj['kind']}, color {obj['color']}, shape {obj['shape']}, "
            f"at x={obj['x']}, y={obj['y']}, size {obj['w']} by {obj['h']}, frames 0 through {last}."
        )
    plant = brief["plant"]
    lines.append("Hidden plant:")
    lines.append(
        f"- {plant['id']}, a {plant['kind']}, color {plant['color']}, shape {plant['shape']}, "
        f"only on frames {plant['from_frame']} through {plant['to_frame']} inclusive, then it is gone. "
        f"Place it at x={plant['x']}, y={plant['y']}, size {plant['w']} by {plant['h']}. Keep it small."
    )
    trap = brief["trap"]
    if trap["why_false"] == "absent":
        reason = (
            f"the {trap['asked_kind']} is not in the scene. "
            f"The nearby object is {trap['nearby_id']}. Do not draw a {trap['asked_kind']}."
        )
    else:
        reason = (
            f"the {trap['asked_id']} is {trap['true_value']}, not {trap['claimed_value']}. "
            f"Draw the true color only."
        )
    lines.append(f'False question to save with the clip: "{trap["question"]}"')
    lines.append(f"This question is false because {reason}")
    lines.append("Do not write words on the picture.")
    return "\n".join(lines)


RECORD_SCHEMA = """
Reply with one JSON object and nothing else. Use this shape:
{
  "scene_id": "the brief id",
  "width": 640,
  "height": 360,
  "fps": 12,
  "frame_count": 48,
  "background": "#hex from the brief",
  "camera": {"kind": "pan_right or pan_left or static", "pixels": 0},
  "objects": [
    {"id": "", "kind": "", "color": "#hex", "shape": "cup|book|stick|box|plant|cloth|sphere|blade|boot",
     "x": 0, "y": 0, "w": 0, "h": 0, "from_frame": 0, "to_frame": 0, "hidden": false}
  ],
  "trap": {
    "question": "",
    "asked_id": "",
    "asked_kind": "",
    "asked_attribute": "",
    "why_false": "absent or wrong_attribute",
    "nearby_id": ""
  }
}
Include every lasting object and the hidden plant. Copy colors, frames, and the question from the brief.
The plant stays hidden: short frame range, hidden true. The trap stays false.
""".strip()
