"""Score one custom-harness arm of the twelve checkpoint 06 scenes.

The key is read by the Go client from the environment. This runner does not print it.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from harness.briefs import load_brief
from harness.fair_run import run_full

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

CUSTOM = {
    "A": ("deepseek-v4.1-flash", True),
    "D": ("space-bunny-free", False),
}


def _brief_row(summary: dict) -> dict:
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
    return {key: summary.get(key) for key in keys if key in summary}


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: python3 -m harness.arm_run ARM MEDIA LOG")
    arm = sys.argv[1]
    media = Path(sys.argv[2])
    log = Path(sys.argv[3])
    if arm not in CUSTOM:
        raise SystemExit(f"{arm} is not a custom arm")
    model, allow_final = CUSTOM[arm]
    log.parent.mkdir(parents=True, exist_ok=True)
    for scene in SCENES:
        out = media / scene / "full" / f"arm-{arm.lower()}"
        if (out / "fair-score.json").exists():
            print(f"skip {arm} {scene}", flush=True)
            continue
        brief = load_brief(scene)
        session = f"vgh-matrix-{arm}-{scene}"
        started = time.time()
        try:
            summary = run_full(brief, model, out, session, allow_final=allow_final)
        except Exception as exc:
            summary = {"scene_id": scene, "model": model, "error": str(exc)[:500]}
        summary["arm"] = arm
        summary["seconds"] = round(time.time() - started, 1)
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(summary) + "\n")
        print(json.dumps(_brief_row(summary)), flush=True)


if __name__ == "__main__":
    main()
