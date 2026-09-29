"""Fair strict comparison.

Both sides see the same brief and the same record schema. Plain writes the
record and the drawing script in one reply. The staged run writes the record
first, then asks for a script that draws that record. Neither side is drawn
by a compiler.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path

from checker.task_score import shortcut_report
from harness.briefs import load_brief, prose
from harness.extract import extract_json, extract_python
from harness.go_client import chat, redact
from harness.loop import Trace, _adopt_output
from harness.sandbox import run_scene, safety_problems
from harness.strict_item import ABSTAIN, CANARY, _checker, _encode

DRAW = """
Drawing rules:
- Use Pillow. Fill solid rectangles with ImageDraw.rectangle. No ellipse, no outline, no text.
- Run as python scene.py OUTPUT_DIR.
- Write OUTPUT_DIR/frames/f_000.png onward, three digits.
- Write OUTPUT_DIR/log.json as {"frames":[{"index":0,"objects":[{"id":"","kind":"","color":"#hex","x":0,"y":0,"w":0,"h":0}]}]}.
- Write OUTPUT_DIR/trap.json with question, why_false, role, claim, nearby_id, writer_key, false_key, true_key, answers, and correct_answer.
- Draw an object only on the frames listed for it. Log it only on those frames, with that color and box.
- The center of a logged box has to be the logged color.
- Use only json, sys, and PIL. The output directory is sys.argv[1].
""".strip()

SCHEMA = f"""
record.json shape:
{{
  "scene_id": "",
  "fps": 12,
  "width": 320,
  "height": 180,
  "frame_count": 48,
  "background": "#hex",
  "canary": "{CANARY}",
  "plant": {{"id":"","kind":"","color":"#hex","frames":[14, 15, 16],"x":0,"y":0,"w":0,"h":0}},
  "objects": [{{"id":"","kind":"","color":"#hex","frames":[0, 1, 2],"x":0,"y":0,"w":0,"h":0}}],
  "trap": {{
    "question": "",
    "why_false": "",
    "role": "false_premise",
    "claim": {{"type": "order", "earlier": "", "later": ""}},
    "nearby_id": "",
    "writer_key": "{ABSTAIN}",
    "false_key": "{ABSTAIN}",
    "true_key": "The full true sentence.",
    "answers": ["The full true sentence.", "{ABSTAIN}"],
    "correct_answer": 1
  }}
}}
frames is every visible index, one integer per frame. [14, 37] means only frame 14 and frame 37. A span from 14 through 37 is 14, 15, 16, and so on through 37.
answers[0] is the true_key sentence copied in full. answers[1] is the abstain sentence copied in full. Neither answer may be empty.
Put the canary on the record only. Do not put it in the question, the explanation, or the answers.
writer_key is exactly: {ABSTAIN}
correct_answer is the index of that abstain sentence in answers.
""".strip()

FAIR_SCENES = (
    "attic-compass",
    "creek-paddle",
    "office-stamp",
    "nursery-rattle",
)


def _span(obj: dict, last: int) -> list[int]:
    if obj.get("frames"):
        return [int(n) for n in obj["frames"]]
    return list(range(int(obj.get("from_frame", 0)), int(obj.get("to_frame", last)) + 1))


def facts(brief: dict) -> str:
    """The brief, including the frame lists, in the same words for both sides."""
    last = int(brief["frame_count"]) - 1
    lines = [prose(brief), "", "Copy these facts into the record:"]
    plant_id = brief["plant"]["id"]
    rows = []
    for obj in list(brief.get("objects") or []) + list(brief.get("events") or []):
        if obj.get("id") == plant_id:
            continue
        rows.append(obj)
    rows.append(brief["plant"])
    for obj in rows:
        frames = _span(obj, last)
        role = "plant" if obj.get("id") == plant_id else "object"
        listed = ", ".join(str(n) for n in frames)
        lines.append(
            f"- {role} {obj['id']}, kind {obj.get('kind', obj['id'])}, color {obj['color']}, "
            f"x={obj['x']}, y={obj['y']}, w={obj['w']}, h={obj['h']}, frames [{listed}]"
        )
    trap = brief["trap"]
    lines.append(f"- question: {trap['question']}")
    lines.append(f"- why_false: {trap.get('explain') or trap.get('why_false')}")
    lines.append(f"- claim earlier {trap['earlier']} later {trap['later']}")
    lines.append(f"- nearby_id {trap['nearby_id']}")
    lines.append(f"- true_key: {trap['true_key']}")
    lines.append(f"- answers: [{trap['true_key']!r}, {ABSTAIN!r}]")
    lines.append(f"- background {brief['background']}, fps {brief['fps']}, frame_count {brief['frame_count']}")
    return "\n".join(lines)


def packet(brief: dict) -> str:
    return facts(brief) + "\n\n" + SCHEMA + "\n\n" + DRAW


def _brace_object(text: str) -> dict | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(text[start:], start):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(text[start : index + 1])
                except json.JSONDecodeError:
                    return None
                return parsed if isinstance(parsed, dict) else None
    return None


def split_reply(text: str) -> tuple[dict | None, str | None, bool | None]:
    """Return record, script, and whether the record fence starts before the script fence."""
    json_fence = re.search(r"```json\s*(.*?)```", text, re.DOTALL)
    python_fence = re.search(r"```python\s*(.*?)```", text, re.DOTALL)
    record = _brace_object(json_fence.group(1)) if json_fence else None
    script = python_fence.group(1).strip() if python_fence else None
    json_at = json_fence.start() if json_fence else None
    script_at = python_fence.start() if python_fence else None
    if record is None:
        record = extract_json(text)
        json_at = text.find("{") if record is not None else None
    if not script:
        script = extract_python(text)
        script_at = text.find(script[:30]) if script else None
    if json_at is None and script_at is None:
        return record, script, None
    if json_at is None:
        return record, script, False
    if script_at is None:
        return record, script, True
    return record, script, json_at < script_at


def _plant_flag(record: dict | None, plant_id: str) -> bool:
    if not record:
        return False
    plant = record.get("plant") or {}
    if plant.get("id") == plant_id and plant.get("frames"):
        return True
    return any(obj.get("id") == plant_id for obj in record.get("objects") or [])


def _render(script_path: Path, out_dir: Path, trace: Trace, fps: int, count: int) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="vgh-fair-"))
    try:
        ran = run_scene(script_path, tmp)
        trace.add("render_done", exit=ran["exit"], stderr=redact(ran["stderr"])[:1500])
        _adopt_output(out_dir, tmp)
    except Exception as exc:
        ran = {"exit": -1, "stderr": redact(str(exc))[:1500], "stdout": ""}
        trace.add("render_done", exit=-1, stderr=ran["stderr"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    frames = out_dir / "frames"
    if ran["exit"] == 0 and frames.exists() and any(frames.glob("f_*.png")) and not (out_dir / "clip.mp4").exists():
        try:
            _encode(frames, out_dir / "clip.mp4", fps, count)
        except Exception as exc:
            trace.add("encode_failed", detail=redact(str(exc))[:500])
    return ran


def _ask_messages(model: str, messages: list[dict], session: str, trace: Trace, step: str, max_tokens: int) -> str:
    trace.add("prompt", step=step, text=messages[-1]["content"][:4000])
    reply = chat(model, messages, session, max_tokens=max_tokens)
    text = redact(reply["content"])
    trace.add(
        "response",
        step=step,
        finish_reason=reply.get("finish_reason"),
        reasoning_len=reply.get("reasoning_len"),
        text=text[:12000],
    )
    return text


def _ask(model: str, prompt: str, session: str, trace: Trace, step: str, max_tokens: int) -> str:
    return _ask_messages(model, [{"role": "user", "content": prompt}], session, trace, step, max_tokens)


def _save_record(out_dir: Path, record: dict | None) -> None:
    if record is not None:
        (out_dir / "record.json").write_text(json.dumps(record, indent=2))


def run_one_shot(brief: dict, model: str, out_dir: Path, session: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    trace = Trace()
    prompt = (
        packet(brief)
        + "\n\nIn this single reply, write the record in a ```json fence and the drawing script in a ```python fence."
    )
    text = _ask(model, prompt, session, trace, "one_shot", 6000)
    plant_id = brief["plant"]["id"]
    _apply_reply(out_dir, brief, text, trace, plant_id, "one_shot")
    trace.add("snapshot", kind="log", has_plant=_log_plant(out_dir, plant_id))
    return _finish(out_dir, brief, trace, "one_shot", model, "model_code")


def run_staged(brief: dict, model: str, out_dir: Path, session: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    trace = Trace()
    plant_id = brief["plant"]["id"]
    record_text = _ask(
        model,
        packet(brief) + "\n\nWrite only the record, in a ```json fence. Do not write the drawing script.",
        session,
        trace,
        "record",
        4000,
    )
    record, _script, _order = split_reply(record_text)
    trace.add("record", has_plant=_plant_flag(record, plant_id), source="model")
    _save_record(out_dir, record)
    if record is None:
        trace.add("snapshot", kind="log", has_plant=False)
        return _finish(out_dir, brief, trace, "staged", model, "model_code")
    code_text = _ask(
        model,
        "The record below is frozen. Write only the drawing script in a ```python fence.\n"
        "Draw this record. Do not change its frames, colors, or boxes.\n\n"
        + DRAW
        + "\n\nFrozen record:\n"
        + json.dumps(record),
        session + "-code",
        trace,
        "code",
        6000,
    )
    _ignored, script, _order = split_reply(code_text)
    _write_script(out_dir, script, trace, plant_id)
    if script and not safety_problems(script):
        _render(out_dir / "scene.py", out_dir, trace, int(brief["fps"]), int(brief["frame_count"]))
    trace.add("snapshot", kind="log", has_plant=_log_plant(out_dir, plant_id))
    return _finish(out_dir, brief, trace, "staged", model, "model_code")


def _write_script(out_dir: Path, script: str | None, trace: Trace, plant_id: str) -> None:
    if not script:
        trace.add("snapshot", kind="code", has_plant=False, note="no python in the reply")
        return
    problems = safety_problems(script)
    has = plant_id in script
    trace.add("snapshot", kind="code", has_plant=has)
    (out_dir / "scene.py").write_text(script)
    trace.add("write_code", path="scene.py")
    if problems:
        trace.add("code_rejected", problems=problems)


def _log_plant(out_dir: Path, plant_id: str) -> bool:
    path = out_dir / "log.json"
    if not path.exists():
        return False
    try:
        log = json.loads(path.read_text())
    except json.JSONDecodeError:
        return False
    for frame in log.get("frames") or []:
        for obj in frame.get("objects") or []:
            if obj.get("id") == plant_id:
                return True
    return False


def plant_in_decoded(out_dir: Path, brief: dict) -> dict:
    """The plant color is on the brief's plant frames in the decoded mp4."""
    checker = _checker()
    mp4 = out_dir / "clip.mp4"
    plant = brief["plant"]
    wanted = list(range(int(plant["from_frame"]), int(plant["to_frame"]) + 1))
    if not mp4.exists():
        return {"picture": False, "hits": 0, "wanted": len(wanted), "reason": "no clip.mp4"}
    color = checker.hex_rgb(plant["color"])
    hits = 0
    try:
        with tempfile.TemporaryDirectory() as tmp:
            paths = checker.decode_mp4(mp4, Path(tmp))
            decoded = {int(path.stem.split("_")[-1]): path for path in paths}
            for index in wanted:
                path = decoded.get(index)
                if path is None:
                    continue
                _w, _h, pixels = checker.read_png(path)
                count = sum(
                    1
                    for row in pixels
                    for pix in row
                    if checker.chebyshev(pix, color) <= checker.ENCODE_COLOR_TOL
                )
                if count >= 64:
                    hits += 1
    except Exception as exc:
        return {"picture": False, "hits": 0, "wanted": len(wanted), "reason": str(exc)[:300]}
    return {
        "picture": hits == len(wanted) and len(wanted) > 0,
        "hits": hits,
        "wanted": len(wanted),
        "reason": f"plant color on {hits} of {len(wanted)} decoded plant frames",
    }


def _shortcuts(out_dir: Path) -> dict:
    checker = _checker()
    clip = checker.load_clip(out_dir)
    log = clip.get("log") or {}
    trap = clip.get("trap") or {}
    frames = checker.frame_list(log) if log.get("frames") else []
    if not frames or not trap:
        return {"no_video": False, "single_frame": False, "shuffled": False, "reason": "no log or trap"}
    report = shortcut_report(frames, trap)
    return {
        "no_video": report["no_video"],
        "single_frame": report["single_frame"],
        "shuffled": report["shuffled"],
        "claim": (trap.get("claim") or {}).get("type"),
        "detail": report.get("detail"),
    }


def _finish(out_dir: Path, brief: dict, trace: Trace, mode: str, model: str, renderer: str) -> dict:
    trace.dump(out_dir / "trace.jsonl")
    try:
        strict = _checker().score_clip(out_dir)
        failed = [name for name, item in strict["hard"].items() if not item["pass"]]
        strict_pass = bool(strict["pass"])
        passed = strict["hard_passed"]
        total = strict["hard_total"]
    except Exception as exc:
        strict_pass = False
        failed = ["score_error"]
        passed = 0
        total = 18
        strict = {"error": str(exc)[:300]}
    picture = plant_in_decoded(out_dir, brief)
    shortcuts = _shortcuts(out_dir)
    summary = {
        "scene_id": brief["scene_id"],
        "mode": mode,
        "model": model,
        "renderer": renderer,
        "strict_pass": strict_pass,
        "strict_passed": passed,
        "strict_total": total,
        "failed": failed,
        "picture": picture["picture"],
        "picture_detail": picture,
        "shortcuts": {key: shortcuts[key] for key in ("no_video", "single_frame", "shuffled")},
        "shortcut_detail": {key: shortcuts.get(key) for key in ("claim", "reason", "detail") if key in shortcuts},
    }
    summary["fail_lines"] = _fail_lines(strict, picture)
    (out_dir / "fair-score.json").write_text(json.dumps({"summary": summary, "strict": strict}, indent=2))
    return summary


def _fail_lines(strict: dict, picture: dict) -> list[str]:
    lines = []
    for name, item in (strict.get("hard") or {}).items():
        if isinstance(item, dict) and not item.get("pass"):
            lines.append(f"{name}: {item.get('detail')}")
    if not picture.get("picture"):
        lines.append("picture: " + str(picture.get("reason") or "plant not visible in the decoded mp4"))
    return lines


def _apply_reply(out_dir: Path, brief: dict, text: str, trace: Trace, plant_id: str, source: str) -> None:
    record, script, record_first = split_reply(text)
    if record_first:
        if record is not None:
            trace.add("record", has_plant=_plant_flag(record, plant_id), source=source)
            _save_record(out_dir, record)
        _write_script(out_dir, script, trace, plant_id)
    else:
        _write_script(out_dir, script, trace, plant_id)
        if record is not None:
            trace.add("record", has_plant=_plant_flag(record, plant_id), source=source)
            _save_record(out_dir, record)
    script_ok = bool(script) and not safety_problems(script)
    if script_ok:
        frames = out_dir / "frames"
        if frames.exists():
            for image in frames.glob("f_*.png"):
                image.unlink()
        for name in ("clip.mp4", "log.json", "trap.json"):
            stale = out_dir / name
            if stale.exists():
                stale.unlink()
        _render(out_dir / "scene.py", out_dir, trace, int(brief["fps"]), int(brief["frame_count"]))


def _rank(summary: dict) -> tuple:
    return (int(bool(summary.get("strict_pass"))), int(summary.get("strict_passed") or 0), int(bool(summary.get("picture"))))


_KEEP_NAMES = ("record.json", "trap.json", "log.json", "scene.py", "trace.jsonl", "clip.mp4", "fair-score.json")


def _snapshot(out_dir: Path, number: int) -> None:
    dest = Path(tempfile.mkdtemp(prefix=f"vgh-attempt-{number}-"))
    marker = out_dir / ".attempt-paths"
    paths = []
    if marker.exists():
        paths = [line for line in marker.read_text().splitlines() if line.strip()]
    paths.append(str(dest))
    marker.write_text("\n".join(paths) + "\n")
    for name in _KEEP_NAMES:
        src = out_dir / name
        if src.exists():
            shutil.copy2(src, dest / name)
    frames = dest / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    for image in (out_dir / "frames").glob("f_*.png") if (out_dir / "frames").exists() else []:
        shutil.copy2(image, frames / image.name)


def _restore(out_dir: Path, number: int) -> None:
    marker = out_dir / ".attempt-paths"
    paths = [line for line in marker.read_text().splitlines() if line.strip()]
    src = Path(paths[number])
    for name in _KEEP_NAMES:
        file = src / name
        if file.exists():
            shutil.copy2(file, out_dir / name)
    dest = out_dir / "frames"
    dest.mkdir(parents=True, exist_ok=True)
    keep = {image.name for image in (src / "frames").glob("f_*.png")} if (src / "frames").exists() else set()
    for image in dest.glob("f_*.png"):
        if image.name not in keep:
            image.unlink()
    for image in (src / "frames").glob("f_*.png") if (src / "frames").exists() else []:
        shutil.copy2(image, dest / image.name)


def run_repair(brief: dict, model: str, out_dir: Path, session: str, rounds: int = 2) -> dict:
    """Same first reply as one-shot, then at most two rounds of checker messages."""
    out_dir.mkdir(parents=True, exist_ok=True)
    trace = Trace()
    plant_id = brief["plant"]["id"]
    prompt = (
        packet(brief)
        + "\n\nIn this single reply, write the record in a ```json fence and the drawing script in a ```python fence."
    )
    messages = [{"role": "user", "content": prompt}]
    text = _ask_messages(model, messages, session, trace, "one_shot", 6000)
    messages.append({"role": "assistant", "content": text})
    _apply_reply(out_dir, brief, text, trace, plant_id, "one_shot")
    trace.add("snapshot", kind="log", has_plant=_log_plant(out_dir, plant_id))
    summary = _finish(out_dir, brief, trace, "repair", model, "model_code")
    _snapshot(out_dir, 0)
    best_rank = _rank(summary)
    best_n = 0
    used = 0
    for round_i in range(1, rounds + 1):
        if summary.get("strict_pass") and summary.get("picture"):
            break
        lines = summary.get("fail_lines") or []
        if not lines:
            break
        feedback = "Checks that failed:\n" + "\n".join(f"- {line}" for line in lines)
        messages.append({"role": "user", "content": feedback})
        text = _ask_messages(model, messages, session, trace, f"repair-{round_i}", 6000)
        messages.append({"role": "assistant", "content": text})
        used = round_i
        _apply_reply(out_dir, brief, text, trace, plant_id, "repair")
        trace.add("snapshot", kind="log", has_plant=_log_plant(out_dir, plant_id))
        summary = _finish(out_dir, brief, trace, "repair", model, "model_code")
        _snapshot(out_dir, round_i)
        rank = _rank(summary)
        if rank > best_rank:
            best_rank = rank
            best_n = round_i
    if best_n != used:
        _restore(out_dir, best_n)
        saved = json.loads((out_dir / "fair-score.json").read_text())
        summary = saved["summary"]
    summary["repairs_used"] = used
    summary["kept_attempt"] = best_n
    summary["mode"] = "repair"
    (out_dir / "fair-score.json").write_text(json.dumps({"summary": summary}, indent=2))
    return summary


def self_check() -> None:
    text = "```json\n{\"scene_id\": \"x\", \"plant\": {\"id\": \"fern\", \"frames\": [1]}}\n```\n```python\nimport sys\nprint(1)\n```"
    record, script, record_first = split_reply(text)
    if not record or not script or record_first is not True:
        raise SystemExit(f"json-first reply parsed wrong: {record_first}")
    flipped = "```python\nimport sys\nprint(1)\n```\n" + text[text.find("```json") :]
    _record, _script, record_first = split_reply(flipped)
    if record_first:
        raise SystemExit("a script-first reply was marked record-first")
    media = Path("/cursor/stores/bc-f9fe9480-5b96-4277-be5d-c761609be7ed/media/stable-bridle/strict/strict-1")
    if media.exists():
        brief = load_brief("stable-bridle")
        picture = plant_in_decoded(media, brief)
        if not picture["picture"]:
            raise SystemExit(f"known strict clip is not visible in the mp4: {picture}")
        shortcuts = _shortcuts(media)
        if not (shortcuts["no_video"] and shortcuts["single_frame"] and shortcuts["shuffled"]):
            raise SystemExit(f"known order trap failed a shortcut: {shortcuts}")
    if '["",' in SCHEMA or "Neither answer may be empty." not in SCHEMA:
        raise SystemExit("schema still allows an empty answer")
    if "one integer per frame" not in SCHEMA:
        raise SystemExit("schema does not say that frames lists every index")
    sample = load_brief("shed-wrench")
    told = facts(sample)
    if "frames [0, 1, 2, 3," not in told or "through" in told.split("frames [")[-1][:40]:
        raise SystemExit("facts still describe a frame span instead of each index")
    print("fair self-check ok")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--selfcheck", action="store_true")
    parser.add_argument("--scene")
    parser.add_argument("--mode", choices=["one-shot", "staged", "repair"])
    parser.add_argument("--model", default="space-bunny-free")
    parser.add_argument("--media", type=Path)
    parser.add_argument("--pass-id", default="fair-1")
    args = parser.parse_args()
    if args.selfcheck:
        self_check()
        return
    if not args.scene or not args.mode or args.media is None:
        raise SystemExit("--scene, --mode, and --media are required")
    brief = load_brief(args.scene)
    out = args.media / args.scene / args.mode / args.pass_id
    session = f"vgh-fair-{args.scene}-{args.mode}-{args.pass_id}"
    if args.mode == "one-shot":
        summary = run_one_shot(brief, args.model, out, session)
    elif args.mode == "repair":
        summary = run_repair(brief, args.model, out, session)
    else:
        summary = run_staged(brief, args.model, out, session)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
