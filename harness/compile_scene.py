"""Draw a scene record into frames and a log. The plant is not optional."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw


def _shift(record: dict, frame: int, x: int) -> int:
    camera = record.get("camera") or {}
    kind = camera.get("kind", "static")
    pixels = int(camera.get("pixels") or 0)
    span = max(1, int(record.get("frame_count", 1)) - 1)
    t = frame / span
    if kind == "pan_right":
        return x - int(pixels * t)
    if kind == "pan_left":
        return x + int(pixels * t)
    return x


def _draw_shape(draw: ImageDraw.ImageDraw, shape: str, box: tuple[int, int, int, int], color: str) -> None:
    x, y, w, h = box
    if shape == "plant":
        pot = (x + w // 4, y + h // 2, x + 3 * w // 4, y + h)
        draw.rectangle(pot, fill="#6b4423")
        draw.ellipse((x, y + h // 5, x + w, y + 2 * h // 3), fill=color)
        draw.ellipse((x + w // 5, y, x + 4 * w // 5, y + h // 2), fill=color)
        return
    if shape == "cup":
        draw.rounded_rectangle((x, y, x + w, y + h), radius=8, fill=color)
        draw.arc((x + w - 8, y + h // 4, x + w + 16, y + 3 * h // 4), 270, 90, fill=color, width=4)
        return
    if shape == "book":
        draw.rectangle((x, y, x + w, y + h), fill=color)
        draw.line((x + 8, y, x + 8, y + h), fill="#1b1b1b", width=3)
        return
    if shape == "cloth":
        draw.ellipse((x, y, x + w, y + h), fill=color)
        return
    if shape == "sphere":
        draw.ellipse((x, y, x + w, y + h), fill=color)
        return
    if shape == "boot":
        draw.rounded_rectangle((x, y, x + int(w * 0.45), y + h), radius=6, fill=color)
        draw.rounded_rectangle((x, y + int(h * 0.55), x + w, y + h), radius=6, fill=color)
        return
    draw.rectangle((x, y, x + w, y + h), fill=color)


def render_record(record: dict, out_dir: Path, write_video: bool = True) -> None:
    out_dir = Path(out_dir)
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    width = int(record["width"])
    height = int(record["height"])
    count = int(record["frame_count"])
    log_frames = []
    for index in range(count):
        image = Image.new("RGB", (width, height), record.get("background", "#888888"))
        draw = ImageDraw.Draw(image)
        visible = []
        for obj in record.get("objects") or []:
            start = int(obj.get("from_frame", 0))
            end = int(obj.get("to_frame", count - 1))
            if index < start or index > end:
                continue
            x = _shift(record, index, int(obj["x"]))
            y = int(obj["y"])
            w = int(obj["w"])
            h = int(obj["h"])
            _draw_shape(draw, obj.get("shape", "box"), (x, y, w, h), obj["color"])
            visible.append(
                {
                    "id": obj["id"],
                    "kind": obj["kind"],
                    "color": obj["color"],
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                }
            )
        image.save(frames_dir / f"f_{index:03d}.png")
        log_frames.append({"index": index, "objects": visible})
    (out_dir / "log.json").write_text(json.dumps({"frames": log_frames}))
    trap = record.get("trap") or {}
    (out_dir / "trap.json").write_text(json.dumps(trap, indent=2))
    (out_dir / "scene-record.json").write_text(json.dumps(record, indent=2))
    if write_video:
        _write_video(frames_dir, out_dir / "clip.mp4", int(record.get("fps", 12)))


def _write_video(frames_dir: Path, dest: Path, fps: int) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-framerate",
            str(fps),
            "-i",
            str(frames_dir / "f_%03d.png"),
            "-pix_fmt",
            "yuv420p",
            str(dest),
        ],
        check=False,
    )
