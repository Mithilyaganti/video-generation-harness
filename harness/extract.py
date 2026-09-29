"""Pull JSON or Python out of a model reply."""

from __future__ import annotations

import json
import re


def extract_json(text: str) -> dict | None:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
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
                    return json.loads(text[start : index + 1])
                except json.JSONDecodeError:
                    return None
    return None


def extract_python(text: str) -> str | None:
    fenced = re.findall(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    blocks = [block.strip() for block in fenced if "import" in block or "Image" in block or "def " in block]
    if blocks:
        return max(blocks, key=len)
    stripped = text.strip()
    if stripped.startswith("import ") or stripped.startswith("from ") or stripped.startswith("#!"):
        return stripped
    return None
