"""Run one scene, or the local self-test."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from harness.briefs import load_brief
from harness.loop import run_ideas, run_plain
from harness.selftest import main as selftest


def _history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if "kinds" in row and "trap_sig" in row:
            rows.append({"kinds": row["kinds"], "trap_sig": row["trap_sig"]})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--scene", default="desk-mug")
    parser.add_argument("--mode", choices=["plain", "ideas"], default="plain")
    parser.add_argument("--model", default="space-bunny-free")
    parser.add_argument("--renderer", choices=["code", "compile"], default="code")
    parser.add_argument("--media", type=Path, required=False)
    parser.add_argument("--pass-id", default="p1")
    parser.add_argument("--history", type=Path, default=Path("results/scores.jsonl"))
    parser.add_argument("--allow-final", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return
    if args.media is None:
        raise SystemExit("--media is required for a generation run")
    brief = load_brief(args.scene)
    out = args.media / args.scene / args.mode / args.pass_id
    session = f"vgh-{args.scene}-{args.mode}-{args.pass_id}"
    previous = _history(args.history)
    if args.mode == "plain":
        result = run_plain(brief, args.model, out, session, previous, allow_final=args.allow_final)
    else:
        result = run_ideas(
            brief,
            args.model,
            out,
            session,
            previous,
            renderer=args.renderer,
            allow_final=args.allow_final,
        )
    args.history.parent.mkdir(parents=True, exist_ok=True)
    with args.history.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result) + "\n")
    print(json.dumps({"scene": result["scene_id"], "pass": result["pass"], "hard": result["hard"], "out": str(out)}))


if __name__ == "__main__":
    main()
