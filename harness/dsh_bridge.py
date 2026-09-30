"""Run a scene script and score it for the dsh plugins.

No model call. The key is never read.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from harness.briefs import load_brief
from harness.fair_run import _shortcuts, concrete_lines, plant_in_decoded
from harness.sandbox import run_scene, safety_problems
from harness.strict_item import _checker


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


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: python3 -m harness.dsh_bridge render|report ...")
    cmd = sys.argv[1]
    if cmd == "render":
        result = render(Path(sys.argv[2]), Path(sys.argv[3]))
        print(json.dumps({"exit": result["exit"]}))
        return
    if cmd == "report":
        print(json.dumps(report(Path(sys.argv[2]), sys.argv[3])))
        return
    raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    main()
