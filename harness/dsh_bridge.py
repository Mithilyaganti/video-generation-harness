"""Run a scene script and score it for the dsh plugins.

No model call. The key is never read.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from harness.briefs import load_brief
from harness.fair_run import (
    _apply_reply,
    _crash_text,
    _finish,
    _log_plant,
    _shortcuts,
    concrete_lines,
    packet,
    plant_in_decoded,
)
from harness.loop import Trace
from harness.sandbox import run_scene, safety_problems
from harness.strict_item import _checker

FENCE = (
    "In this single reply, write the record in a ```json fence and the drawing script in a ```python fence."
)


def crash_feedback(stderr: str) -> str:
    detail = stderr if stderr and str(stderr).strip() else "the script failed"
    return "The script failed.\n" + str(detail)


def note_feedback(lines: list[str], record_text: str, script_text: str) -> str:
    listed = "\n".join(f"- {line}" for line in lines)
    return (
        "Checks that failed:\n"
        + listed
        + "\n\nCurrent record:\n"
        + record_text
        + "\n\nCurrent script:\n"
        + script_text
        + "\n\nReply with the corrected record in a ```json fence and the full drawing script in a ```python fence. "
        + "The script must still write the frames, log.json, and trap.json."
    )


def render(script: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    source = script.read_text(encoding="utf-8")
    problems = safety_problems(source)
    if problems:
        result = {"exit": -1, "stderr": "; ".join(problems), "stdout": ""}
    else:
        try:
            result = run_scene(script, out, timeout=120)
        except subprocess.TimeoutExpired:
            result = {"exit": -1, "stderr": "timeout", "stdout": ""}
    (out / "render.json").write_text(json.dumps(result))
    return result


def report(out: Path, scene_id: str) -> dict:
    brief = load_brief(scene_id)
    render_path = out / "render.json"
    rendered = json.loads(render_path.read_text()) if render_path.exists() else {}
    exit_code = rendered.get("exit")
    valid = exit_code == 0 and (out / "clip.mp4").exists()
    try:
        strict = _checker().score_clip(out)
        failed = [name for name, item in (strict.get("hard") or {}).items() if not item.get("pass")]
        strict_pass = bool(strict.get("pass"))
        passed = int(strict.get("hard_passed") or 0)
    except Exception as exc:
        strict = {"hard": {}, "error": str(exc)[:300]}
        failed = ["score_error"]
        strict_pass = False
        passed = 0
    picture = plant_in_decoded(out, brief)
    shortcuts = _shortcuts(out)
    lines = concrete_lines(out, brief, strict, picture)
    record = (out / "record.json").read_text() if (out / "record.json").exists() else ""
    script = (out / "scene.py").read_text() if (out / "scene.py").exists() else ""
    return {
        "validClip": valid,
        "strictPass": strict_pass,
        "strictPassed": passed,
        "failed": failed,
        "picture": bool(picture.get("picture")),
        "pictureDetail": picture,
        "crashText": crash_feedback(str(rendered.get("stderr") or "")),
        "noteLines": lines,
        "noteText": note_feedback(lines, record, script) if lines else "",
        "recordText": record,
        "scriptText": script,
        "shortcuts": {key: bool(shortcuts.get(key)) for key in ("no_video", "single_frame", "shuffled")},
    }


def task_text(brief: dict) -> str:
    """Same task as checkpoint 06 run_full, including the schema."""
    return packet(brief) + "\n\n" + FENCE


def apply_reply(out: Path, scene_id: str, text: str) -> dict:
    """Extract the fences, run the script, and return one clip-loop attempt."""
    brief = load_brief(scene_id)
    out.mkdir(parents=True, exist_ok=True)
    trace = Trace()
    plant_id = brief["plant"]["id"]
    _apply_reply(out, brief, text, trace, plant_id, "dsh")
    trace.add("snapshot", kind="log", has_plant=_log_plant(out, plant_id))
    summary = _finish(out, brief, trace, "dsh", "dsh", "model_code")
    packed = json.loads((out / "fair-score.json").read_text())
    strict = packed.get("strict") or {}
    picture = summary.get("picture_detail") or {}
    lines = concrete_lines(out, brief, strict, picture)
    record = (out / "record.json").read_text() if (out / "record.json").exists() else ""
    script = (out / "scene.py").read_text() if (out / "scene.py").exists() else ""
    return {
        "validClip": bool(summary.get("valid_clip")),
        "strictPass": bool(summary.get("strict_pass")),
        "strictPassed": int(summary.get("strict_passed") or 0),
        "picture": bool(summary.get("picture")),
        "crashText": crash_feedback(_crash_text(trace)),
        "noteLines": lines,
        "noteText": note_feedback(lines, record, script) if lines else "",
        "recordText": record,
        "scriptText": script,
        "shortcuts": {key: bool((summary.get("shortcuts") or {}).get(key)) for key in ("no_video", "single_frame", "shuffled")},
    }


def _clip_dir(out: Path) -> Path:
    clips = [path for path in out.rglob("clip.mp4") if "attempts" not in path.parts and path.is_file() and path.stat().st_size > 0]
    if not clips:
        return out
    return max(clips, key=lambda path: path.stat().st_mtime).parent


def score_saved(out: Path, scene_id: str) -> dict:
    """Score files already on disk. Does not extract a script or run one."""
    brief = load_brief(scene_id)
    target = _clip_dir(out)
    clip = target / "clip.mp4"
    valid = clip.exists() and clip.stat().st_size > 0
    try:
        strict = _checker().score_clip(target)
        failed = [name for name, item in (strict.get("hard") or {}).items() if not item.get("pass")]
        strict_pass = bool(strict.get("pass"))
        passed = int(strict.get("hard_passed") or 0)
        total = int(strict.get("hard_total") or 18)
    except Exception as exc:
        strict = {"error": str(exc)[:300]}
        failed = ["score_error"]
        strict_pass = False
        passed = 0
        total = 18
    picture = plant_in_decoded(target, brief)
    shortcuts = _shortcuts(target)
    summary = {
        "scene_id": scene_id,
        "mode": "plain",
        "valid_clip": valid,
        "strict_pass": strict_pass,
        "strict_passed": passed,
        "strict_total": total,
        "failed": failed,
        "picture": bool(picture.get("picture")),
        "picture_detail": picture,
        "shortcuts": {key: bool(shortcuts.get(key)) for key in ("no_video", "single_frame", "shuffled")},
        "crash_rounds": 0,
        "note_rounds": 0,
        "rounds_used": 0,
        "kept_attempt": 0,
    }
    (out / "fair-score.json").write_text(json.dumps({"summary": summary, "strict": strict}, indent=2))
    return summary


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: python3 -m harness.dsh_bridge render|report|apply-reply|score-saved ...")
    cmd = sys.argv[1]
    if cmd == "render":
        result = render(Path(sys.argv[2]), Path(sys.argv[3]))
        print(json.dumps({"exit": result["exit"]}))
        return
    if cmd == "report":
        print(json.dumps(report(Path(sys.argv[2]), sys.argv[3])))
        return
    if cmd == "apply-reply":
        print(json.dumps(apply_reply(Path(sys.argv[2]), sys.argv[3], sys.stdin.read())))
        return
    if cmd == "score-saved":
        print(json.dumps(score_saved(Path(sys.argv[2]), sys.argv[3])))
        return
    raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    main()
