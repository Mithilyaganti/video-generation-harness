"""Offline checks for the dsh plugins. No model call and no key."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from harness.briefs import load_brief
from harness.dsh_bridge import apply_reply, crash_feedback, note_feedback, render, report, score_saved, task_text
from harness.fair_run import SCHEMA, packet
from harness.sandbox import run_scene


ROOT = Path(__file__).resolve().parents[1]
KEY_FILE = Path("/cursor/stores/bc-f9fe9480-5b96-4277-be5d-c761609be7ed/internal/opencode-go.env")
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


def _node_feedback() -> dict:
    script = """
import { crashFeedback, noteFeedback } from './dsh/clip-loop.mjs'
console.log(JSON.stringify({
  crash: crashFeedback('Traceback: boom'),
  notes: noteFeedback(['plant_in_frames: expected spoon'], 'RECORD', 'SCRIPT'),
}))
"""
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def main() -> None:
    if not KEY_FILE.is_file() or KEY_FILE.stat().st_size <= 0:
        raise SystemExit("opencode go env file is missing")
    ignored = subprocess.run(["git", "check-ignore", "-q", "opencode-go.env"], cwd=ROOT)
    if ignored.returncode != 0:
        raise SystemExit("opencode-go.env is not gitignored")

    listed = (ROOT / "dsh" / "scenes.mjs").read_text()
    for scene_id in SCENES:
        if f'"{scene_id}"' not in listed:
            raise SystemExit(f"{scene_id} missing from the plugin scene list")
        brief = load_brief(scene_id)
        text = packet(brief)
        if "record.json shape" not in text or "Neither answer may be empty." not in text:
            raise SystemExit(f"{scene_id} task is missing the shared schema")
        if '["",' in SCHEMA:
            raise SystemExit("schema still allows an empty answer")

    node = subprocess.run(["node", "dsh/selftest.mjs"], cwd=ROOT)
    if node.returncode != 0:
        raise SystemExit("plugin selftest failed")

    feedback = _node_feedback()
    if feedback["crash"] != crash_feedback("Traceback: boom"):
        raise SystemExit("plugin crash text does not match the checkpoint 06 line")
    if feedback["notes"] != note_feedback(["plant_in_frames: expected spoon"], "RECORD", "SCRIPT"):
        raise SystemExit("plugin note text does not match the checkpoint 06 line")
    if "expected" in feedback["crash"]:
        raise SystemExit("crash follow-up included a checker note")

    if run_scene.__defaults__ != (120,):
        raise SystemExit(f"scene runner timeout is {run_scene.__defaults__}, expected 120 seconds")

    probe = ROOT / "dsh" / "sandbox-policy.mjs"
    if "ALLOW_PLUGIN = false" not in probe.read_text():
        raise SystemExit("an os allow plugin was registered")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        script = root / "scene.py"
        script.write_text(
            "import os\nimport pathlib\nimport sys\n"
            "frames = pathlib.Path(sys.argv[1]) / 'frames'\n"
            "frames.mkdir(parents=True, exist_ok=True)\n"
            "(frames / 'f_000.png').write_bytes(b'ok')\n"
            "print(os.path.isdir(frames))\n"
        )
        out = root / "out"
        ran = render(script, out)
        if ran["exit"] != 0 or not (out / "frames" / "f_000.png").exists():
            raise SystemExit(f"os and pathlib probe failed: {ran}")
        broken = root / "broken.py"
        broken.write_text("import pathlib\nraise RuntimeError('no frames')\n")
        crashed = root / "crashed"
        ran = render(broken, crashed)
        if ran["exit"] == 0 or "RuntimeError" not in ran["stderr"]:
            raise SystemExit("a crashed script did not keep its traceback")
        text = crash_feedback(ran["stderr"])
        if not text.startswith("The script failed.\n") or "expected" in text:
            raise SystemExit("crash text was not the traceback")
        summary = report(crashed, "orchard-basket")
        if summary["validClip"] or summary["strictPass"]:
            raise SystemExit("a crashed script counted as a clip")
        if "RuntimeError" not in summary["crashText"]:
            raise SystemExit("report dropped the traceback")

    patch = (ROOT / "dsh" / "cordis.patch.yml").read_text()
    if "oc_sk_" in patch:
        raise SystemExit("the patch file contains a key")
    for name in ("opencode-go.mjs", "save-window.mjs", "clip-loop.mjs"):
        if f"./{name}" not in patch or not (ROOT / "dsh" / name).is_file():
            raise SystemExit(f"plugin patch does not point at {name}")
    for scene_id in SCENES:
        told = task_text(load_brief(scene_id))
        if "```json fence" not in told or "record.json shape" not in told:
            raise SystemExit(f"{scene_id} dsh task dropped the schema")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        empty = apply_reply(root / "empty", "orchard-basket", "no fences here")
        if empty["validClip"] or "The script failed." not in empty["crashText"]:
            raise SystemExit("a reply with no script counted as a clip")
        plain = root / "plain"
        plain.mkdir()
        (plain / "scene.py").write_text("print('not run')\n", encoding="utf-8")
        saved = score_saved(plain, "orchard-basket")
        if saved["valid_clip"] or (plain / "clip.mp4").exists():
            raise SystemExit("plain scoring ran a script")
    for name in ("arm-b.patch.yml", "arm-c.patch.yml", "arm-e.patch.yml"):
        text = (ROOT / "dsh" / name).read_text()
        if "oc_sk_" in text or "record.json shape" in text:
            raise SystemExit(f"{name} carries a key or the schema")
    print("dsh plugin selftest ok")


if __name__ == "__main__":
    main()
