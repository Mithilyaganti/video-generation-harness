"""OpenCode Go chat client. The key is read from the environment and never logged."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

ALLOWED_GENERATION = {"space-bunny-free", "longcat-2.5-preview-free"}
ALLOWED_FINAL = {"deepseek-v4.1-flash"}
USER_AGENT = "video-generation-harness/0.1"


def redact(text: str) -> str:
    cleaned = re.sub(r"oc_sk_[A-Za-z0-9_\-]+", "[redacted]", text)
    cleaned = re.sub(r"Bearer\s+\S+", "Bearer [redacted]", cleaned)
    return cleaned


def _load_key() -> tuple[str, str]:
    key = os.environ.get("OPENCODE_API_KEY", "").strip()
    base = os.environ.get("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1").strip()
    env_file = os.environ.get("OPENCODE_GO_ENV", "").strip()
    if not key and env_file:
        for line in open(env_file, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name == "OPENCODE_API_KEY" and not key:
                key = value.strip()
            if name == "OPENCODE_BASE_URL":
                base = value.strip()
    if not key:
        raise SystemExit("Set OPENCODE_API_KEY or OPENCODE_GO_ENV. Do not commit the key.")
    return key, base.rstrip("/")


def chat(model: str, messages: list[dict], session: str, max_tokens: int = 2500, allow_final: bool = False) -> dict:
    if model in ALLOWED_FINAL and not allow_final:
        raise SystemExit("deepseek-v4.1-flash is only for the final comparison. Pass allow_final.")
    if model not in ALLOWED_GENERATION and not (allow_final and model in ALLOWED_FINAL):
        raise SystemExit(f"{model} is not a free generation model for this harness")
    if "muse" in model or "mimo" in model or model.startswith("grok") or "claude" in model:
        raise SystemExit(f"refusing {model}")
    key, base = _load_key()
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.2,
        # Default thinking filled the whole token budget and returned no clip.
        "reasoning_effort": "low",
    }
    request = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "x-opencode-session": session,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = redact(exc.read().decode("utf-8", errors="replace")[:2000])
        raise RuntimeError(f"HTTP {exc.code} from Go: {detail}") from None
    choice = (body.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict):
                texts.append(str(part.get("text") or part.get("content") or ""))
            else:
                texts.append(str(part))
        content = "\n".join(texts)
    reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
    if not isinstance(reasoning, str):
        reasoning = str(reasoning)
    return {
        "content": content or "",
        "reasoning_len": len(reasoning),
        "finish_reason": choice.get("finish_reason"),
        "usage": body.get("usage") or {},
        "model": body.get("model") or model,
    }
