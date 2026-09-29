"""Run model-written scene code without the API key in the environment."""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path


BANNED_IMPORTS = {
    "subprocess",
    "socket",
    "urllib",
    "requests",
    "http",
    "ctypes",
    "pickle",
    "shutil",
    "pathlib",
    "os",
}
BANNED_SNIPPETS = ("oc_sk_", "OPENCODE", "/cursor/stores", "subprocess", "socket")


def safety_problems(source: str) -> list[str]:
    problems = []
    for snippet in BANNED_SNIPPETS:
        if snippet in source:
            problems.append(f"banned snippet {snippet}")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"syntax error: {exc}"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in BANNED_IMPORTS:
                    problems.append(f"banned import {root}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in BANNED_IMPORTS:
                problems.append(f"banned import {root}")
    return problems


def run_scene(source_path: Path, out_dir: Path, timeout: int = 40) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/tmp",
        "PYTHONDONTWRITEBYTECODE": "1",
        "SDL_VIDEODRIVER": "dummy",
        "PYTHONNOUSERSITE": "0",
    }
    # Pillow may live in the user site, which PYTHONNOUSERSITE would hide.
    user_site = Path.home() / ".local" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    if user_site.exists():
        env["PYTHONPATH"] = str(user_site)
    completed = subprocess.run(
        [sys.executable, str(source_path), str(out_dir)],
        cwd=str(source_path.parent),
        env=env,
        timeout=timeout,
        capture_output=True,
        text=True,
    )
    stderr = completed.stderr[-4000:]
    stderr = re.sub(r"oc_sk_[A-Za-z0-9_\-]+", "[redacted]", stderr)
    return {"exit": completed.returncode, "stderr": stderr, "stdout": completed.stdout[-2000:]}
