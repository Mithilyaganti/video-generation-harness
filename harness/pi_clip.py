"""Run the twelve checkpoint 06 scenes through bare Pi.

The extension arm loads pi/clip-harness.ts. Plain Pi loads no extension.
Both arms get the same schema text in the task. The extension asks for one
more turn from agent_before_settle, at most two crash rounds and two note
rounds, and it keeps the best clip.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from harness.briefs import load_brief
from harness.fair_run import (
    _checker,
    _scored,
    _shortcuts,
    concrete_lines,
    packet,
    plant_in_decoded,
)
from harness.go_client import redact
from harness.loop import Trace

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "pi" / "opencode-go.json"
EXTENSION = ROOT / "pi" / "clip-harness.ts"
ENV_FILE = Path(
    os.environ.get(
        "OPENCODE_GO_ENV",
        "/cursor/stores/bc-f9fe9480-5b96-4277-be5d-c761609be7ed/internal/opencode-go.env",
    )
)
MEDIA_ROOT = Path(
    os.environ.get(
        "PI_MEDIA_ROOT",
        "/cursor/stores/bc-f9fe9480-5b96-4277-be5d-c761609be7ed/media",
    )
)
SCENES = (
    "orchard-basket",
    "pantry-jar",
    "quay-cleat",
    "ridge-flag",
    "study-globe",
    "terrace-jug",
    "trail-flask",
    "ward-chart",
    "yard-hose",
    "annex-badge",
    "booth-token",
    "chapel-candle",
)
ARMS = {
    "pi-ext-flash": {"extension": True, "model": "deepseek-v4.1-flash"},
    "pi-plain-flash": {"extension": False, "model": "deepseek-v4.1-flash"},
    "pi-ext-bunny": {"extension": True, "model": "space-bunny-free"},
}
CRASH_CAP = 2
NOTE_CAP = 2
KEEP_NAMES = ("record.json", "trap.json", "log.json", "scene.py", "trace.jsonl", "clip.mp4", "fair-score.json")

TASK_TAIL = """
Write these files in the current directory. Write record.json before scene.py.
Then run `python3 scene.py .`
The script may import os and pathlib.
It must write frames/f_000.png onward, log.json, and trap.json.
Draw solid rectangles with Pillow. The output directory is the argument, which is `.` here.
""".strip()


def task_text(brief: dict) -> str:
    return packet(brief) + "\n\n" + TASK_TAIL


def _load_key_env() -> None:
    if os.environ.get("OPENCODE_API_KEY"):
        return
    if not ENV_FILE.exists():
        raise SystemExit("Set OPENCODE_API_KEY or OPENCODE_GO_ENV. Do not commit the key.")
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name, value.strip())
    if not os.environ.get("OPENCODE_API_KEY"):
        raise SystemExit("OPENCODE_API_KEY is missing. Do not commit the key.")


def _clean_env() -> dict:
    env = {}
    for name, value in os.environ.items():
        upper = name.upper()
        if "KEY" in upper or "TOKEN" in upper or "SECRET" in upper or name.startswith("OPENCODE"):
            continue
        env[name] = value
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def traceback_only(stderr: str) -> str:
    text = redact(stderr or "").strip()
    if not text:
        return "the script failed"
    marker = "Traceback (most recent call last):"
    index = text.rfind(marker)
    if index >= 0:
        return text[index:]
    return text


def _read_json(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _extract_fences(work: Path) -> None:
    replies = work / ".pi-replies.txt"
    if not replies.exists():
        return
    text = replies.read_text(encoding="utf-8", errors="replace")
    if not (work / "record.json").exists():
        match = re.search(r"```json\s*(.*?)```", text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1))
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                (work / "record.json").write_text(json.dumps(parsed, indent=2), encoding="utf-8")
    if not (work / "scene.py").exists():
        match = re.search(r"```python\s*(.*?)```", text, re.DOTALL)
        if match and match.group(1).strip():
            (work / "scene.py").write_text(match.group(1).strip() + "\n", encoding="utf-8")


def _encode(frame_dir: Path, mp4: Path, fps: int, count: int) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            str(fps),
            "-start_number",
            "0",
            "-i",
            str(frame_dir / "f_%03d.png"),
            "-frames:v",
            str(count),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "18",
            str(mp4),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _adopt(work: Path, tmp: Path) -> None:
    for name in ("log.json", "trap.json", "clip.mp4"):
        src = tmp / name
        if src.exists():
            shutil.copy2(src, work / name)
    src_frames = tmp / "frames"
    if not src_frames.exists():
        return
    dest = work / "frames"
    dest.mkdir(parents=True, exist_ok=True)
    for image in src_frames.glob("f_*.png"):
        shutil.copy2(image, dest / image.name)


def render_dir(work: Path, script_name: str = "scene.py") -> dict:
    """Run the model's script with a normal Python. No import denylist.

    Frames are written on local disk. The media store is slow enough to cut a
    script off while it is still saving pictures.
    """
    _extract_fences(work)
    script = work / script_name
    if not script.exists():
        return {"exit": 1, "stderr": "", "stdout": ""}
    for name in ("clip.mp4", "log.json", "trap.json"):
        stale = work / name
        if stale.exists():
            stale.unlink()
    frames = work / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    tmp = Path(tempfile.mkdtemp(prefix="vgh-pi-"))
    try:
        shutil.copy2(script, tmp / "scene.py")
        if (work / "record.json").exists():
            shutil.copy2(work / "record.json", tmp / "record.json")
        try:
            completed = subprocess.run(
                [sys.executable, str(tmp / "scene.py"), "."],
                cwd=str(tmp),
                env=_clean_env(),
                timeout=120,
                capture_output=True,
                text=True,
            )
            ran = {
                "exit": completed.returncode,
                "stderr": redact(completed.stderr[-4000:]),
                "stdout": completed.stdout[-2000:],
            }
        except subprocess.TimeoutExpired as exc:
            err = exc.stderr
            text = err.decode("utf-8", errors="replace") if isinstance(err, bytes) else (err or "")
            ran = {"exit": -1, "stderr": redact(text[-4000:]) or "timeout", "stdout": ""}
        local_frames = tmp / "frames"
        if ran["exit"] == 0 and local_frames.exists() and any(local_frames.glob("f_*.png")) and not (tmp / "clip.mp4").exists():
            try:
                brief_fps = 12
                count = len(list(local_frames.glob("f_*.png")))
                record = _read_json(tmp / "record.json")
                if record.get("fps"):
                    brief_fps = int(record["fps"])
                _encode(local_frames, tmp / "clip.mp4", brief_fps, count)
            except Exception as exc:
                ran = {"exit": -1, "stderr": redact(str(exc))[:1500], "stdout": ran["stdout"]}
        _adopt(work, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return ran


def _plant_in_record(record: dict, plant_id: str) -> bool:
    plant = record.get("plant") or {}
    return plant.get("id") == plant_id and bool(plant.get("frames"))


def _script_has_plant(script: str, record: dict | None, plant_id: str) -> bool:
    """The drawing script still has the plant.

    A literal id counts. So does a script that draws the record's plant, or
    every object, when that object list already contains the plant. A script
    that never names the plant and never reads it from the record does not.
    """
    if plant_id and plant_id in script:
        return True
    if not script or not isinstance(record, dict):
        return False
    plant = record.get("plant") or {}
    if plant.get("id") != plant_id:
        return False
    if re.search(r"""['"]plant['"]""", script):
        return True
    objects = record.get("objects") or []
    if any(isinstance(obj, dict) and obj.get("id") == plant_id for obj in objects):
        if re.search(r"""['"]objects['"]""", script):
            return True
    return False


def _write_trace(work: Path, brief: dict, ran: dict) -> Trace:
    plant_id = brief["plant"]["id"]
    order_path = work / ".pi-write-order.txt"
    order = []
    if order_path.exists():
        order = [line.strip() for line in order_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        order_path.unlink()
    record = _read_json(work / "record.json") if (work / "record.json").exists() else None
    script = (work / "scene.py").read_text(encoding="utf-8") if (work / "scene.py").exists() else ""
    trace = Trace()
    record_at = order.index("record") if "record" in order else None
    code_at = order.index("code") if "code" in order else None
    record_first = record_at is not None and (code_at is None or record_at < code_at)
    code_first = code_at is not None and record_at is not None and code_at < record_at

    def emit_record(source: str) -> None:
        if record is None:
            return
        trace.add("record", has_plant=_plant_in_record(record, plant_id), source=source)

    def emit_code() -> None:
        if not script:
            return
        trace.add("snapshot", kind="code", has_plant=_script_has_plant(script, record, plant_id))
        trace.add("write_code", path="scene.py")

    if code_first:
        emit_code()
        emit_record("model")
    elif record_first:
        emit_record("model")
        emit_code()
    else:
        if record is not None:
            emit_record("kept")
        emit_code()
    trace.add("render_done", exit=ran["exit"], stderr=redact(ran.get("stderr") or "")[:1500])
    from harness.fair_run import _log_plant

    trace.add("snapshot", kind="log", has_plant=_log_plant(work, plant_id))
    trace.dump(work / "trace.jsonl")
    return trace


def score_work(work: Path, brief: dict, ran: dict, model: str) -> dict:
    try:
        _write_trace(work, brief, ran)
    except Exception:
        pass
    try:
        strict = _checker().score_clip(work)
        failed = [name for name, item in strict["hard"].items() if not item["pass"]]
        strict_pass = bool(strict["pass"])
        passed = strict["hard_passed"]
        total = strict["hard_total"]
    except Exception as exc:
        strict = {"error": redact(str(exc))[:300]}
        failed = ["score_error"]
        strict_pass = False
        passed = 0
        total = 18
    picture = plant_in_decoded(work, brief)
    shortcuts = _shortcuts(work)
    summary = {
        "scene_id": brief["scene_id"],
        "model": model,
        "strict_pass": strict_pass,
        "strict_passed": passed,
        "strict_total": total,
        "failed": failed,
        "picture": picture["picture"],
        "picture_detail": picture,
        "shortcuts": {key: shortcuts[key] for key in ("no_video", "single_frame", "shuffled")},
        "valid_clip": ran["exit"] == 0 and (work / "clip.mp4").exists(),
        "exit": ran["exit"],
    }
    (work / "fair-score.json").write_text(
        json.dumps({"summary": summary, "strict": strict}, indent=2),
        encoding="utf-8",
    )
    return summary


def _rank(summary: dict) -> tuple:
    return (
        int(bool(summary.get("valid_clip"))),
        int(bool(summary.get("strict_pass"))),
        int(summary.get("strict_passed") or 0),
        int(bool(summary.get("picture"))),
    )


def _better(new: dict, old: dict) -> bool:
    return _rank(new) > _rank(old)


def next_action(summary: dict, state: dict, note_lines: list[str], crash_text: str) -> dict:
    """One more turn, or stop. The message is only the traceback or the failing lines."""
    crash_used = int(state.get("crash_used") or 0)
    note_used = int(state.get("note_used") or 0)
    if not summary.get("valid_clip") and crash_used < CRASH_CAP:
        crash_used += 1
        return {
            "continue": True,
            "kind": "crash",
            "message": crash_text,
            "crash_used": crash_used,
            "note_used": note_used,
        }
    if not (summary.get("strict_pass") and summary.get("picture")) and note_used < NOTE_CAP and note_lines:
        note_used += 1
        return {
            "continue": True,
            "kind": "note",
            "message": "\n".join(note_lines),
            "crash_used": crash_used,
            "note_used": note_used,
        }
    return {
        "continue": False,
        "kind": "stop",
        "message": "",
        "crash_used": crash_used,
        "note_used": note_used,
    }


def _snapshot(work: Path, number: int) -> None:
    dest = work / ".attempts" / str(number)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for name in KEEP_NAMES:
        src = work / name
        if src.exists():
            shutil.copy2(src, dest / name)
    frames = dest / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    if (work / "frames").exists():
        for image in (work / "frames").glob("f_*.png"):
            shutil.copy2(image, frames / image.name)


def _restore(work: Path, number: int) -> None:
    src = work / ".attempts" / str(number)
    if not src.exists():
        return
    for name in KEEP_NAMES:
        file = src / name
        target = work / name
        if file.exists():
            shutil.copy2(file, target)
        elif target.exists() and name != "fair-score.json":
            target.unlink()
    dest = work / "frames"
    dest.mkdir(parents=True, exist_ok=True)
    keep = {image.name for image in (src / "frames").glob("f_*.png")} if (src / "frames").exists() else set()
    for image in dest.glob("f_*.png"):
        if image.name not in keep:
            image.unlink()
    for image in (src / "frames").glob("f_*.png") if (src / "frames").exists() else []:
        shutil.copy2(image, dest / image.name)


def _load_state(work: Path) -> dict:
    path = work / ".pi-harness-state.json"
    if not path.exists():
        return {"attempt": -1, "crash_used": 0, "note_used": 0, "best_n": 0, "best_rank": [0, 0, 0, 0]}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_state(work: Path, state: dict) -> None:
    (work / ".pi-harness-state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def _note_lines(work: Path, brief: dict, summary: dict) -> list[str]:
    packed = _read_json(work / "fair-score.json")
    strict = packed.get("strict") or {}
    picture = summary.get("picture_detail") or {"picture": summary.get("picture"), "reason": ""}
    return concrete_lines(work, brief, strict, picture)


def settle(work: Path, scene: str) -> dict:
    brief = load_brief(scene)
    state = _load_state(work)
    state["attempt"] = int(state.get("attempt", -1)) + 1
    attempt = state["attempt"]
    ran = render_dir(work)
    summary = score_work(work, brief, ran, os.environ.get("PI_MODEL", ""))
    _snapshot(work, attempt)
    best_rank = tuple(state.get("best_rank") or [0, 0, 0, 0])
    if attempt == 0 or _rank(summary) > best_rank:
        state["best_n"] = attempt
        state["best_rank"] = list(_rank(summary))
        best_rank = _rank(summary)
    if "first" not in state:
        state["first"] = {
            "first_valid": bool(summary.get("valid_clip")),
            "first_strict_pass": bool(summary.get("strict_pass")),
            "first_strict_passed": summary.get("strict_passed"),
            "first_picture": bool(summary.get("picture")),
            "first_shortcuts": summary.get("shortcuts"),
            "first_failed": list(summary.get("failed") or []),
        }
    action = next_action(summary, state, _note_lines(work, brief, summary), traceback_only(ran.get("stderr") or ""))
    state["crash_used"] = action["crash_used"]
    state["note_used"] = action["note_used"]
    if action["kind"] == "note" and state["best_n"] != attempt:
        _restore(work, state["best_n"])
        restored = json.loads((work / "fair-score.json").read_text(encoding="utf-8"))["summary"]
        lines = _note_lines(work, brief, restored)
        if lines:
            action["message"] = "\n".join(lines)
        else:
            action = {"continue": False, "kind": "stop", "message": "", "crash_used": state["crash_used"], "note_used": state["note_used"]}
    if not action["continue"] and state["best_n"] != attempt:
        _restore(work, state["best_n"])
        summary = json.loads((work / "fair-score.json").read_text(encoding="utf-8"))["summary"]
    summary["crash_rounds"] = state["crash_used"] if not action["continue"] else max(0, state["crash_used"] - (1 if action["kind"] == "crash" else 0))
    if action["continue"]:
        summary["crash_rounds"] = state["crash_used"] - (1 if action["kind"] == "crash" else 0)
        summary["note_rounds"] = state["note_used"] - (1 if action["kind"] == "note" else 0)
    else:
        summary["crash_rounds"] = state["crash_used"]
        summary["note_rounds"] = state["note_used"]
        summary["kept_attempt"] = state["best_n"]
        summary["mode"] = "pi"
        summary.update(state["first"])
        (work / "fair-score.json").write_text(json.dumps({"summary": summary}, indent=2), encoding="utf-8")
    state["last_summary"] = summary
    _save_state(work, state)
    return action


def _pi_bin() -> str:
    local = Path.home() / ".local" / "bin" / "pi"
    if local.exists():
        return str(local)
    return "pi"


def _agent_dir(extension: bool) -> Path:
    dest = Path(tempfile.mkdtemp(prefix="pi-agent-"))
    if not extension:
        spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
        base = os.environ.get("OPENCODE_BASE_URL")
        if base:
            spec["baseUrl"] = base
        (dest / "models.json").write_text(
            json.dumps({"providers": {"opencode-go": spec}}, indent=2),
            encoding="utf-8",
        )
    return dest


def run_pi(work: Path, scene: str, model: str, extension: bool) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    brief = load_brief(scene)
    prompt = task_text(brief)
    (work / "task.md").write_text(prompt, encoding="utf-8")
    _load_key_env()
    env = os.environ.copy()
    env["PI_SCENE"] = scene
    env["PI_MODEL"] = model
    env["PI_HARNESS_ROOT"] = str(ROOT)
    env["PI_PROVIDER_SPEC"] = str(SPEC_PATH)
    env["PI_OPENCODE_SESSION"] = f"vgh-pi-{scene}-{model}-{'ext' if extension else 'plain'}"
    env["PI_CODING_AGENT_DIR"] = str(_agent_dir(extension))
    env["PATH"] = str(Path.home() / ".local" / "bin") + os.pathsep + env.get("PATH", "")
    cmd = [
        _pi_bin(),
        "--print",
        "--mode",
        "text",
        "--approve",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-context-files",
        "--thinking",
        "low",
        "--provider",
        "opencode-go",
        "--model",
        model,
        "--session-dir",
        str(work / "sessions"),
    ]
    if extension:
        cmd.extend(["--extension", str(EXTENSION), "--scene", scene])
    cmd.extend(["--", prompt])
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(work),
            env=env,
            timeout=1800,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return {"scene_id": scene, "model": model, "error": "pi timeout", "strict_pass": False, "valid_clip": False}
    (work / "pi-stdout.txt").write_text(redact(completed.stdout)[-20000:], encoding="utf-8")
    (work / "pi-stderr.txt").write_text(redact(completed.stderr)[-20000:], encoding="utf-8")
    if (work / "fair-score.json").exists():
        summary = json.loads((work / "fair-score.json").read_text(encoding="utf-8"))["summary"]
        summary["pi_exit"] = completed.returncode
        return summary
    if completed.returncode != 0:
        return {
            "scene_id": scene,
            "model": model,
            "error": redact(completed.stderr)[-1500:] or f"pi exit {completed.returncode}",
            "strict_pass": False,
            "valid_clip": False,
            "picture": False,
            "pi_exit": completed.returncode,
        }
    ran = render_dir(work)
    summary = score_work(work, brief, ran, model)
    summary["crash_rounds"] = 0
    summary["note_rounds"] = 0
    summary["kept_attempt"] = 0
    summary["mode"] = "pi-plain"
    summary["pi_exit"] = completed.returncode
    summary.update(
        {
            "first_valid": bool(summary.get("valid_clip")),
            "first_strict_pass": bool(summary.get("strict_pass")),
            "first_strict_passed": summary.get("strict_passed"),
            "first_picture": bool(summary.get("picture")),
            "first_shortcuts": summary.get("shortcuts"),
            "first_failed": list(summary.get("failed") or []),
        }
    )
    (work / "fair-score.json").write_text(json.dumps({"summary": summary}, indent=2), encoding="utf-8")
    return summary


def _assert(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(message)


def selftest() -> None:
    crash = "Traceback (most recent call last):\nNameError: name 'sys' is not defined"
    notes = ["key_matches_log: expected writer_key. Found writer_key 'x' and computed key 'y'."]
    state = {"crash_used": 0, "note_used": 0}
    summary = {"valid_clip": False, "strict_pass": False, "picture": False}
    first = next_action(summary, state, notes, crash)
    _assert(first["kind"] == "crash" and first["message"] == crash, "crash round was not the traceback")
    _assert("record.json" not in first["message"] and "Current script" not in first["message"], "crash note added extra text")
    state["crash_used"] = first["crash_used"]
    second = next_action(summary, state, notes, crash)
    _assert(second["kind"] == "crash" and second["crash_used"] == 2, "second crash round did not stop at two")
    state["crash_used"] = second["crash_used"]
    third = next_action(summary, state, notes, crash)
    _assert(third["kind"] == "note" and third["message"] == notes[0], "notes did not replace the traceback")
    state["note_used"] = third["note_used"]
    fourth = next_action(summary, state, notes, crash)
    _assert(fourth["kind"] == "note" and fourth["note_used"] == 2, "note rounds exceeded two")
    state["note_used"] = fourth["note_used"]
    fifth = next_action(summary, state, notes, crash)
    _assert(fifth["continue"] is False, "settle continued after two crash rounds and two note rounds")
    done = {"valid_clip": True, "strict_pass": True, "picture": True}
    _assert(next_action(done, {"crash_used": 0, "note_used": 0}, notes, crash)["continue"] is False, "a passing clip continued")
    text = traceback_only("noise\nTraceback (most recent call last):\nValueError: bad\n")
    _assert(text.startswith("Traceback"), "traceback was not isolated")
    _assert("noise" not in text, "traceback kept the lines above it")
    told = task_text(load_brief("orchard-basket"))
    _assert("one integer per frame" in told, "plain task is missing the schema")
    _assert("answers[0]" in told, "plain task is missing the answer schema")
    source = EXTENSION.read_text(encoding="utf-8")
    _assert("os" not in source.split("pathlib")[0] or "denylist" not in source, "extension mentions a denylist")
    _assert("BANNED_IMPORTS" not in source and "import denylist" not in source.lower(), "extension adds an import denylist")
    _assert("agent_before_settle" in source and "setThinkingLevel(\"low\")" in source, "extension misses settle or the thinking cap")
    _assert("registerProvider" in source and "registerTool" in source, "extension misses the provider or the tool")
    _assert("CRASH_CAP = 2" in source and "NOTE_CAP = 2" in source, "extension does not cap the rounds")
    listed = Path(tempfile.mkdtemp(prefix="vgh-list-log-"))
    (listed / "log.json").write_text('[{"index":0,"objects":[]}]', encoding="utf-8")
    (listed / "record.json").write_text("{}", encoding="utf-8")
    (listed / "trap.json").write_text("{}", encoding="utf-8")
    from harness.fair_run import _log_plant

    side = {"plant": {"id": "flask", "frames": [15]}, "objects": [{"id": "map"}]}
    _assert(
        _script_has_plant('objects = rec["objects"] + [rec["plant"]]', side, "flask"),
        "a script that draws record.plant was marked deleted",
    )
    inside = {"plant": {"id": "badge", "frames": [19]}, "objects": [{"id": "badge"}]}
    _assert(
        _script_has_plant('objs = rec["objects"]', inside, "badge"),
        "a script that draws every object missed a plant stored there",
    )
    _assert(not _script_has_plant("print('map')", side, "flask"), "a script that skips the plant counted")
    _assert(
        not _script_has_plant('objs = rec["objects"]', side, "flask"),
        "objects without the plant counted as the plant",
    )
    kept = Path(tempfile.mkdtemp(prefix="vgh-record-script-"))
    (kept / "record.json").write_text(json.dumps(side), encoding="utf-8")
    (kept / "scene.py").write_text('objects = rec["objects"] + [rec["plant"]]\n', encoding="utf-8")
    (kept / "log.json").write_text(
        json.dumps({"frames": [{"index": 15, "objects": [{"id": "flask"}]}]}),
        encoding="utf-8",
    )
    _write_trace(kept, {"plant": {"id": "flask"}, "scene_id": "trail-flask"}, {"exit": 0, "stderr": ""})
    kept_events = [json.loads(line) for line in (kept / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    kept_gate = _checker().check_plant_not_deleted(kept_events)
    _assert(kept_gate["pass"], "record-driven script failed plant_not_deleted")
    skipped = Path(tempfile.mkdtemp(prefix="vgh-skipped-plant-"))
    (skipped / "record.json").write_text(json.dumps(side), encoding="utf-8")
    (skipped / "scene.py").write_text("print('map')\n", encoding="utf-8")
    (skipped / "log.json").write_text(
        json.dumps({"frames": [{"index": 15, "objects": [{"id": "flask"}]}]}),
        encoding="utf-8",
    )
    _write_trace(skipped, {"plant": {"id": "flask"}, "scene_id": "trail-flask"}, {"exit": 0, "stderr": ""})
    skipped_events = [json.loads(line) for line in (skipped / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    skipped_gate = _checker().check_plant_not_deleted(skipped_events)
    _assert(not skipped_gate["pass"], "a script that skips the plant passed plant_not_deleted")
    shutil.rmtree(kept, ignore_errors=True)
    shutil.rmtree(skipped, ignore_errors=True)
    _assert(_log_plant(listed, "token") is False, "a list log counted as frames")
    listed_score = _checker().score_clip(listed)
    _assert("hard" in listed_score, "a list log crashed the checker")
    shutil.rmtree(listed, ignore_errors=True)
    cafe = Path("/cursor/stores/bc-f9fe9480-5b96-4277-be5d-c761609be7ed/media/cafe-spoon/repair/schema-1")
    if (cafe / "record.json").exists():
        packed = _read_json(cafe / "fair-score.json")
        lines = concrete_lines(
            cafe,
            load_brief("cafe-spoon"),
            _scored(cafe, packed),
            packed.get("summary", {}).get("picture_detail") or {"picture": True, "reason": ""},
        )
        blob = "\n".join(lines)
        _assert("spoon" in blob and "record.plant.id" in blob, "notes lost the cafe wording")
    print("pi clip selftest ok")


def _smoke_one(extension: bool) -> str:
    _load_key_env()
    work = Path(tempfile.mkdtemp(prefix="pi-smoke-"))
    env = os.environ.copy()
    env["PI_SCENE"] = "smoke"
    env["PI_HARNESS_ROOT"] = str(ROOT)
    env["PI_PROVIDER_SPEC"] = str(SPEC_PATH)
    env["PI_OPENCODE_SESSION"] = f"vgh-pi-smoke-{'ext' if extension else 'plain'}"
    env["PI_CODING_AGENT_DIR"] = str(_agent_dir(extension))
    env["PATH"] = str(Path.home() / ".local" / "bin") + os.pathsep + env.get("PATH", "")
    cmd = [
        _pi_bin(),
        "--print",
        "--mode",
        "text",
        "--approve",
        "--no-session",
        "--no-extensions",
        "--no-skills",
        "--thinking",
        "low",
        "--provider",
        "opencode-go",
        "--model",
        "space-bunny-free",
    ]
    if extension:
        cmd.extend(["--extension", str(EXTENSION)])
    cmd.extend(["--", "Reply with the single word pong. Do not use tools."])
    completed = subprocess.run(cmd, cwd=str(work), env=env, timeout=120, capture_output=True, text=True)
    body = redact(completed.stdout + "\n" + completed.stderr)
    if "oc_sk_" in (completed.stdout + completed.stderr):
        raise SystemExit("smoke printed the key")
    if completed.returncode != 0 or "pong" not in completed.stdout.lower():
        raise SystemExit(f"smoke failed extension={extension} exit={completed.returncode} body={body[-800:]}")
    return f"smoke {'extension' if extension else 'plain'} ok"


def smoke() -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_smoke_one, flag) for flag in (True, False)]
        for future in as_completed(futures):
            print(future.result())


_STORE_LOCK = threading.Lock()


def _drop_store_junk(dest: Path) -> None:
    """Remove frames and session logs left on the media store.

    One delete at a time. Parallel deletes on that filesystem stall.
    """
    with _STORE_LOCK:
        for name in ("frames", "sessions"):
            path = dest / name
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)


def _publish(work: Path, dest: Path) -> None:
    """Copy the scored clip onto the media store after the run.

    Pi's working directory stays on local disk. The store keeps the clip, the
    score, and the script. Frames stay on local disk until scoring finishes,
    then the store copy of frames is removed so a later look does not mix an
    old picture with the new clip.
    """
    dest.mkdir(parents=True, exist_ok=True)
    names = list(KEEP_NAMES) + ["task.md", "pi-stdout.txt", "pi-stderr.txt", ".pi-harness-state.json"]
    for name in names:
        src = work / name
        if src.is_file():
            shutil.copy2(src, dest / name)
    _drop_store_junk(dest)


def _load_done(path: Path) -> dict:
    done = {}
    if not path.exists():
        return done
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = (row.get("arm"), row.get("scene_id"))
        if key[0] and key[1] and row.get("strict_total"):
            done[key] = row
    return done


def matrix(workers: int) -> list[dict]:
    jobs = [(arm, scene) for arm in ARMS for scene in SCENES]
    out = ROOT / "results" / "pi-arms.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = _load_done(out)
    rows = list(done.values())
    pending = [job for job in jobs if job not in done]
    lock = threading.Lock()

    def one(arm: str, scene: str) -> dict:
        spec = ARMS[arm]
        work = Path(tempfile.mkdtemp(prefix=f"vgh-{arm}-{scene}-"))
        dest = MEDIA_ROOT / scene / arm / "pi-1"
        summary = {"arm": arm, "scene_id": scene, "error": "missing", "strict_pass": False, "valid_clip": False}
        try:
            summary = run_pi(work, scene, spec["model"], spec["extension"])
            summary["arm"] = arm
        except Exception as exc:
            summary["error"] = redact(str(exc))[:800]
        line = json.dumps(summary)
        print(line, flush=True)
        with lock:
            with out.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        try:
            _publish(work, dest)
        except Exception as exc:
            print(json.dumps({"arm": arm, "scene_id": scene, "publish_error": redact(str(exc))[:500]}), flush=True)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        return summary

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, arm, scene) for arm, scene in pending]
        for future in as_completed(futures):
            rows.append(future.result())
    out = ROOT / "results" / "pi-arms.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    ordered = []
    by_key = {(row.get("arm"), row.get("scene_id")): row for row in rows}
    with out.open("w", encoding="utf-8") as handle:
        for arm in ARMS:
            for scene in SCENES:
                row = by_key.get((arm, scene)) or {"arm": arm, "scene_id": scene, "error": "missing"}
                handle.write(json.dumps(row) + "\n")
                ordered.append(row)
    return ordered


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("command", nargs="?", choices=["render", "settle"])
    parser.add_argument("--dir", dest="directory", type=Path)
    parser.add_argument("--scene")
    parser.add_argument("--script", default="scene.py")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return
    if args.smoke:
        smoke()
        return
    if args.matrix:
        matrix(args.workers)
        return
    if args.command == "render":
        if args.directory is None:
            raise SystemExit("--dir is required")
        ran = render_dir(args.directory, args.script)
        text = traceback_only(ran.get("stderr") or "") if ran["exit"] != 0 else f"exit 0"
        print(text)
        return
    if args.command == "settle":
        if args.directory is None or not args.scene:
            raise SystemExit("--dir and --scene are required")
        decision = settle(args.directory, args.scene)
        print(json.dumps(decision))
        return
    raise SystemExit("pass --selftest, --smoke, --matrix, render, or settle")


if __name__ == "__main__":
    main()
