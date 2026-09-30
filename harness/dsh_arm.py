"""Score one DeepSeek-harness arm of the twelve checkpoint 06 scenes.

The key is read from the environment. This runner does not print it.
Arm C scores files the agent wrote. It does not extract or run a script.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from harness.briefs import load_brief
from harness.dsh_bridge import score_saved, task_text
from harness.go_client import redact

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
    "B": ("deepseek-v4.1-flash", True),
    "C": ("deepseek-v4.1-flash", False),
    "E": ("space-bunny-free", True),
}

ROOT = Path(__file__).resolve().parents[1]
DSH_BIN = os.environ.get("DSH_BIN", "/tmp/dsh-cli/node_modules/@deepseek-ai/dsh/lib/bin.js")
SCENE_TIMEOUT = 1500


def _load_key_env(base: dict) -> dict:
    env = dict(base)
    path = env.get("OPENCODE_GO_ENV", "")
    if not path:
        return env
    text = Path(path).read_text(encoding="utf-8")
    for line in text.splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#") or "=" not in trimmed:
            continue
        name, value = trimmed.split("=", 1)
        if name in ("OPENCODE_API_KEY", "OPENCODE_BASE_URL") and not env.get(name):
            env[name] = value.strip().strip('"').strip("'")
    return env


def _row(summary: dict) -> dict:
    keys = (
        "arm",
        "scene_id",
        "model",
        "valid_clip",
        "strict_pass",
        "strict_passed",
        "strict_total",
        "picture",
        "shortcuts",
        "crash_rounds",
        "note_rounds",
        "rounds_used",
        "kept_attempt",
        "first_valid",
        "first_strict_pass",
        "first_strict_passed",
        "first_picture",
        "first_shortcuts",
        "seconds",
        "error",
    )
    return {key: summary.get(key) for key in keys if key in summary or key == "error"}


def _first_from_attempt(out: Path, summary: dict) -> dict:
    path = out / "attempts" / "0" / "fair-score.json"
    if not path.exists():
        summary["first_valid"] = bool(summary.get("valid_clip"))
        summary["first_strict_pass"] = bool(summary.get("strict_pass"))
        summary["first_strict_passed"] = summary.get("strict_passed")
        summary["first_picture"] = bool(summary.get("picture"))
        summary["first_shortcuts"] = summary.get("shortcuts")
        return summary
    packed = json.loads(path.read_text(encoding="utf-8"))
    first = packed.get("summary") or {}
    summary["first_valid"] = bool(first.get("valid_clip"))
    summary["first_strict_pass"] = bool(first.get("strict_pass"))
    summary["first_strict_passed"] = first.get("strict_passed")
    summary["first_picture"] = bool(first.get("picture"))
    summary["first_shortcuts"] = first.get("shortcuts")
    return summary


def _plugin_summary(out: Path, scene: str, model: str) -> dict:
    score_path = out / "fair-score.json"
    if not score_path.exists():
        return {"scene_id": scene, "model": model, "error": "no kept score"}
    packed = json.loads(score_path.read_text(encoding="utf-8"))
    summary = dict(packed.get("summary") or {})
    loop_path = out / "loop.json"
    if loop_path.exists():
        summary.update(json.loads(loop_path.read_text(encoding="utf-8")))
    summary["scene_id"] = scene
    summary["model"] = model
    return _first_from_attempt(out, summary)


def _run_dsh(arm: str, scene: str, out: Path, prompt: str, plugins: bool) -> subprocess.CompletedProcess[str]:
    patches = [ROOT / "dsh" / f"arm-{arm.lower()}.patch.yml"]
    if plugins:
        patches.insert(0, ROOT / "dsh" / "cordis.patch.yml")
    env = _load_key_env(os.environ.copy())
    env["DSH_BIN"] = DSH_BIN
    env["DSH_HOME"] = f"/tmp/dsh-home-arm-{arm}"
    if plugins:
        env["VGH_OUT"] = str(out)
        env["VGH_SCENE"] = scene
    else:
        env.pop("VGH_OUT", None)
        env.pop("VGH_SCENE", None)
    command = [
        "node",
        str(ROOT / "dsh" / "run-dsh.mjs"),
        "--profile",
        "headless",
    ]
    for patch in patches:
        command.extend(["--patch", str(patch)])
    command.append("-")
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        command,
        input=prompt,
        text=True,
        cwd=str(work if plugins else out),
        env=env,
        capture_output=True,
        timeout=SCENE_TIMEOUT,
        start_new_session=True,
    )


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: python3 -m harness.dsh_arm ARM MEDIA LOG")
    arm = sys.argv[1]
    media = Path(sys.argv[2])
    log = Path(sys.argv[3])
    if arm not in ARMS:
        raise SystemExit(f"{arm} is not a dsh arm")
    model, plugins = ARMS[arm]
    log.parent.mkdir(parents=True, exist_ok=True)
    for scene in SCENES:
        out = media / scene / "full" / f"arm-{arm.lower()}"
        if (out / "fair-score.json").exists():
            print(f"skip {arm} {scene}", flush=True)
            continue
        out.mkdir(parents=True, exist_ok=True)
        if (out / "attempts").exists():
            shutil.rmtree(out / "attempts")
        brief = load_brief(scene)
        prompt = task_text(brief)
        (out / "task.txt").write_text(prompt, encoding="utf-8")
        if "record.json shape" not in prompt or "Neither answer may be empty." not in prompt:
            raise SystemExit(f"{scene} task is missing the shared schema")
        started = time.time()
        try:
            completed = _run_dsh(arm, scene, out, prompt, plugins)
            (out / "reply.txt").write_text(redact(completed.stdout)[-20000:], encoding="utf-8")
            (out / "dsh.err").write_text(redact(completed.stderr)[-20000:], encoding="utf-8")
            if plugins and (out / "fair-score.json").exists():
                summary = _plugin_summary(out, scene, model)
            elif plugins:
                summary = {"scene_id": scene, "model": model, "error": redact(completed.stderr)[-500:] or f"exit {completed.returncode}"}
            elif completed.returncode != 0 and not any(out.rglob("clip.mp4")):
                summary = {"scene_id": scene, "model": model, "error": redact(completed.stderr)[-500:] or f"exit {completed.returncode}"}
            else:
                summary = score_saved(out, scene)
                summary["model"] = model
                summary["first_valid"] = bool(summary.get("valid_clip"))
                summary["first_strict_pass"] = bool(summary.get("strict_pass"))
                summary["first_strict_passed"] = summary.get("strict_passed")
                summary["first_picture"] = bool(summary.get("picture"))
                summary["first_shortcuts"] = summary.get("shortcuts")
        except subprocess.TimeoutExpired:
            summary = {"scene_id": scene, "model": model, "error": f"timeout {SCENE_TIMEOUT}s"}
        except Exception as exc:
            summary = {"scene_id": scene, "model": model, "error": redact(str(exc))[:500]}
        summary["arm"] = arm
        summary["seconds"] = round(time.time() - started, 1)
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(summary) + "\n")
        print(json.dumps(_row(summary)), flush=True)


if __name__ == "__main__":
    main()
