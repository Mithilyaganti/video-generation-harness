"""Plain run, then the same brief with the scene-record ideas."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from checker.score import score_run
from harness.briefs import RECORD_SCHEMA, prose
from harness.compile_scene import _write_video, render_record
from harness.extract import extract_json, extract_python
from harness.go_client import chat, redact
from harness.sandbox import run_scene, safety_problems
from harness.validate import record_from_brief, validate_record


SKILL_PATH = Path(__file__).resolve().parents[1] / "skills" / "plant-trap.md"

PLAIN_CONTRACT = """
Write one Python 3 script using Pillow (from PIL import Image, ImageDraw).
When it is run as `python scene.py OUTPUT_DIR` it must create:
- OUTPUT_DIR/frames/f_000.png onward, one file per frame, three digits
- OUTPUT_DIR/log.json shaped as {"frames":[{"index":0,"objects":[{"id":"","kind":"","color":"#hex","x":0,"y":0,"w":0,"h":0}]}]}
- OUTPUT_DIR/trap.json with the question, why_false, asked_id, asked_kind, asked_attribute, and nearby_id
Use only json, sys, and PIL. The output directory is sys.argv[1].
Reply with the script only.
""".strip()


def _skill() -> str:
    return SKILL_PATH.read_text(encoding="utf-8").strip()


class Trace:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.seq = 0

    def add(self, event: str, **fields) -> None:
        self.seq += 1
        body = {"event": event, "seq": self.seq}
        body.update(fields)
        self.events.append(body)

    def dump(self, path: Path) -> None:
        lines = [json.dumps(event) for event in self.events]
        path.write_text("\n".join(lines) + "\n")


def _has_plant(record: dict | None, plant_id: str) -> bool:
    if not record:
        return False
    return any(obj.get("id") == plant_id for obj in record.get("objects") or [])


def _save_version(out_dir: Path, record: dict, number: int) -> None:
    (out_dir / f"scene-record-v{number}.json").write_text(json.dumps(record, indent=2))


def _ask_record(brief: dict, model: str, out_dir: Path, session: str, trace: Trace, allow_final: bool) -> tuple[dict, str]:
    plant_id = brief["plant"]["id"]
    messages = [
        {
            "role": "user",
            "content": _skill() + "\n\n" + RECORD_SCHEMA + "\n\n" + prose(brief),
        }
    ]
    record = None
    source = "brief_fallback"
    for attempt in range(1, 4):
        trace.add("prompt", step="record", attempt=attempt, text=messages[-1]["content"][:4000])
        reply = chat(model, messages, session, max_tokens=2500, allow_final=allow_final)
        text = redact(reply["content"])
        trace.add(
            "response",
            step="record",
            attempt=attempt,
            finish_reason=reply.get("finish_reason"),
            reasoning_len=reply.get("reasoning_len"),
            usage=reply.get("usage") or {},
            text=text[:8000],
        )
        parsed = extract_json(text)
        messages.append({"role": "assistant", "content": text})
        if parsed is None:
            problems = ["the reply did not contain a JSON object"]
        else:
            problems = validate_record(parsed, brief)
            _save_version(out_dir, parsed, attempt)
            trace.add("snapshot", kind="record", attempt=attempt, has_plant=_has_plant(parsed, plant_id))
        if not problems and parsed is not None:
            record = parsed
            source = "model" if attempt == 1 else "model_repair"
            break
        trace.add("record_problems", attempt=attempt, problems=problems)
        if attempt == 3:
            break
        messages.append(
            {
                "role": "user",
                "content": "Repair the scene record. Problems:\n- "
                + "\n- ".join(problems)
                + "\nKeep the hidden plant and keep the question false. Reply with the full JSON only.",
            }
        )
    if record is None:
        record = record_from_brief(brief)
        source = "brief_fallback"
        _save_version(out_dir, record, 9)
        trace.add("snapshot", kind="record", attempt=9, has_plant=True, note="brief fallback")
    return record, source


def _ask_code(brief: dict, record: dict, model: str, out_dir: Path, session: str, trace: Trace, allow_final: bool) -> str | None:
    plant = brief["plant"]
    prompt = (
        "The scene record below is frozen. Write the Python script that draws it.\n"
        "Do not drop the hidden plant. Do not add the object the trap says is missing.\n"
        "Draw each object only on its from_frame through to_frame.\n\n"
        + PLAIN_CONTRACT
        + "\n\nFrozen record:\n"
        + json.dumps(record)
    )
    messages = [{"role": "user", "content": prompt}]
    trace.add("prompt", step="code", text=prompt[:4000])
    reply = chat(model, messages, session, max_tokens=6000, allow_final=allow_final)
    text = redact(reply["content"])
    trace.add(
        "response",
        step="code",
        finish_reason=reply.get("finish_reason"),
        reasoning_len=reply.get("reasoning_len"),
        usage=reply.get("usage") or {},
        text=text[:12000],
    )
    source = extract_python(text)
    if not source:
        trace.add("snapshot", kind="code", has_plant=False, note="no python in the reply")
        return None
    has = plant["id"] in source and plant["color"].lower() in source.lower()
    trace.add("snapshot", kind="code", has_plant=has)
    path = out_dir / "scene.py"
    path.write_text(source)
    trace.add("write_code", path="scene.py")
    problems = safety_problems(source)
    if problems:
        trace.add("code_rejected", problems=problems)
        return None
    return source


def _log_has_plant(out_dir: Path, plant_id: str) -> bool:
    log_path = out_dir / "log.json"
    if not log_path.exists():
        return False
    try:
        log = json.loads(log_path.read_text())
    except json.JSONDecodeError:
        return False
    for frame in log.get("frames") or []:
        for obj in frame.get("objects") or []:
            if obj.get("id") == plant_id:
                return True
    return False


def _render_script(script: Path, out_dir: Path, trace: Trace) -> None:
    """Draw on local disk. The media store is slow enough to cut a script off mid-frame."""
    tmp = Path(tempfile.mkdtemp(prefix="vgh-render-"))
    trace.add("render_start")
    try:
        try:
            ran = run_scene(script, tmp)
        except subprocess.TimeoutExpired:
            ran = {"exit": -1, "stderr": "timeout", "stdout": ""}
        trace.add("render_done", exit=ran["exit"], stderr=redact(ran["stderr"])[:2000])
        _adopt_output(out_dir, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _finish(out_dir: Path, brief: dict, trace: Trace, previous: list[dict], extra: dict) -> dict:
    frames = out_dir / "frames"
    if frames.exists() and any(frames.glob("f_*.png")) and not (out_dir / "clip.mp4").exists():
        _write_video(frames, out_dir / "clip.mp4", int(brief["fps"]))
    trace.dump(out_dir / "trace.jsonl")
    result = score_run(out_dir, brief, trace.events, previous)
    if brief.get("task"):
        from checker.task_score import score_task

        task = score_task(out_dir, brief)
        result["hard"]["plant_in_frames"] = task["plant_ok"]
        result["hard"]["question_is_false"] = task["trap_false"]
        result["trap_working"] = task["trap_working"]
        result["shortcuts"] = task["shortcuts"]
        result["notes"] = [note for note in result["notes"] if not str(note).startswith("task score:")]
        result["notes"].extend(task["notes"])
        result["pass"] = all(result["hard"].values())
    result.update(extra)
    (out_dir / "score.json").write_text(json.dumps(result, indent=2))
    return result


def run_plain(brief: dict, model: str, out_dir: Path, session: str, previous: list[dict] | None = None, allow_final: bool = False) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    trace = Trace()
    prompt = prose(brief) + "\n\n" + PLAIN_CONTRACT
    trace.add("prompt", step="plain", text=prompt)
    reply = chat(model, [{"role": "user", "content": prompt}], session, max_tokens=6000, allow_final=allow_final)
    text = redact(reply["content"])
    trace.add(
        "response",
        step="plain",
        finish_reason=reply.get("finish_reason"),
        reasoning_len=reply.get("reasoning_len"),
        usage=reply.get("usage") or {},
        text=text[:12000],
    )
    source = extract_python(text)
    plant = brief["plant"]
    if source:
        has = plant["id"] in source and plant["color"].lower() in source.lower()
        trace.add("snapshot", kind="code", has_plant=has)
        path = out_dir / "scene.py"
        path.write_text(source)
        trace.add("write_code", path="scene.py")
        problems = safety_problems(source)
        if problems:
            trace.add("code_rejected", problems=problems)
        else:
            _render_script(path, out_dir, trace)
    else:
        trace.add("snapshot", kind="code", has_plant=False, note="no python in the reply")
    trace.add("snapshot", kind="log", has_plant=_log_has_plant(out_dir, plant["id"]))
    return _finish(
        out_dir,
        brief,
        trace,
        previous or [],
        {"mode": "plain", "model": model, "renderer": "model_code", "record_source": "none"},
    )


def run_ideas(
    brief: dict,
    model: str,
    out_dir: Path,
    session: str,
    previous: list[dict] | None = None,
    renderer: str = "code",
    allow_final: bool = False,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    trace = Trace()
    record, source = _ask_record(brief, model, out_dir, session, trace, allow_final)
    frozen_path = out_dir / "scene-record.json"
    frozen_path.write_text(json.dumps(record, indent=2))
    trace.add("record_frozen", record_source=source, has_plant=_has_plant(record, brief["plant"]["id"]))
    trace.add("snapshot", kind="record_frozen", has_plant=_has_plant(record, brief["plant"]["id"]))
    if renderer == "compile":
        trace.add("render_start", renderer="compile")
        render_record(record, out_dir)
    else:
        code = _ask_code(brief, record, model, out_dir, session, trace, allow_final)
        if code:
            trace.add("renderer", name="model_code")
            _render_script(out_dir / "scene.py", out_dir, trace)
    trace.add("snapshot", kind="log", has_plant=_log_has_plant(out_dir, brief["plant"]["id"]))
    return _finish(
        out_dir,
        brief,
        trace,
        previous or [],
        {
            "mode": "ideas",
            "model": model,
            "renderer": renderer,
            "record_source": source,
            "model_kept_plant": source != "brief_fallback",
        },
    )


def _adopt_output(out_dir: Path, produced: Path) -> None:
    """Copy frames, log, and trap up if the script wrote them in the folder we gave it."""
    if not produced.exists():
        return
    import shutil

    for name in ("log.json", "trap.json"):
        src = produced / name
        if src.exists():
            shutil.copy2(src, out_dir / name)
    dest = out_dir / "frames"
    dest.mkdir(parents=True, exist_ok=True)
    frames = produced / "frames"
    sources = list(frames.glob("f_*.png")) if frames.exists() else []
    sources.extend(produced.glob("f_*.png"))
    for image in sources:
        shutil.copy2(image, dest / image.name)
