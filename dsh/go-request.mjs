import { readFileSync } from "node:fs";

/**
 * OpenCode Go request body and headers.
 *
 * Checkpoint 06 sends reasoning_effort "low", User-Agent
 * video-generation-harness/0.1, and x-opencode-session. Stock llm-pi-ai
 * (dsh 0.2.0-rc.2) can add x-opencode-session from sessionId, and it strips
 * User-Agent from profile headers so the harness attribution wins. This
 * request builder sets both headers on a plugin adapter. The core is not forked.
 */

export const USER_AGENT = "video-generation-harness/0.1";
export const THINKING_EFFORT = "low";
export const DEFAULT_MAX_TOKENS = 6000;
export const TEMPERATURE = 0.2;
export const DEFAULT_BASE_URL = "https://opencode.ai/zen/go/v1";

const ALLOWED = new Set(["space-bunny-free", "deepseek-v4.1-flash"]);

export function redact(text) {
  return String(text)
    .replace(/oc_sk_[A-Za-z0-9_\-]+/g, "[redacted]")
    .replace(/Bearer\s+\S+/g, "Bearer [redacted]");
}

export function assertModel(model) {
  const name = String(model || "");
  if (name.includes("muse") || name.includes("mimo") || name.startsWith("grok") || name.includes("claude")) {
    throw new Error(`refusing ${name}`);
  }
  if (!ALLOWED.has(name)) {
    throw new Error(`${name} is not a generation model for this harness`);
  }
}

export function flattenContent(content) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return content == null ? "" : String(content);
  const parts = [];
  for (const block of content) {
    if (typeof block === "string") parts.push(block);
    else if (block && typeof block === "object") parts.push(String(block.text ?? block.content ?? ""));
    else parts.push(String(block));
  }
  return parts.join("\n");
}

export function toGoMessages(messages, system) {
  const out = [];
  if (system) out.push({ role: "system", content: String(system) });
  for (const message of messages || []) {
    const role = message.role || "user";
    if (role === "tool") continue;
    const mapped = role === "assistant" ? "assistant" : role === "system" ? "system" : "user";
    out.push({ role: mapped, content: flattenContent(message.content) });
  }
  return out;
}

export function loadCredentials(env = process.env, config = {}) {
  let key = String(config.apiKey || env.OPENCODE_API_KEY || "").trim();
  let base = String(config.baseURL || env.OPENCODE_BASE_URL || DEFAULT_BASE_URL).trim();
  const envFile = String(env.OPENCODE_GO_ENV || "").trim();
  if (!key && envFile) {
    const text = readEnvFile(envFile);
    for (const line of text.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
      const name = trimmed.slice(0, trimmed.indexOf("="));
      const value = trimmed.slice(trimmed.indexOf("=") + 1).trim();
      if (name === "OPENCODE_API_KEY" && !key) key = value;
      if (name === "OPENCODE_BASE_URL") base = value.trim();
    }
  }
  if (!key) {
    throw new Error("Set OPENCODE_API_KEY or OPENCODE_GO_ENV. Do not commit the key.");
  }
  return { key, base: base.replace(/\/+$/, "") };
}

function readEnvFile(path) {
  return readFileSync(path, "utf8");
}

export function goHeaders({ apiKey, session, attribution }) {
  if (!session) throw new Error("x-opencode-session is required");
  const headers = {
    Authorization: `Bearer ${apiKey}`,
    "Content-Type": "application/json",
    Accept: "application/json",
    ...(attribution || {}),
  };
  for (const name of Object.keys(headers)) {
    if (name.toLowerCase() === "user-agent") delete headers[name];
  }
  headers["User-Agent"] = USER_AGENT;
  headers["x-opencode-session"] = String(session);
  return headers;
}

export function publicHeaders(headers) {
  const copy = { ...headers };
  for (const name of Object.keys(copy)) {
    if (name.toLowerCase() === "authorization") delete copy[name];
  }
  return copy;
}

export function buildGoRequest({ model, messages, system, session, maxTokens, apiKey, baseURL, attribution, reasoningEffort }) {
  assertModel(model);
  if (reasoningEffort != null && String(reasoningEffort) !== THINKING_EFFORT) {
    throw new Error(`thinking cap is ${THINKING_EFFORT}`);
  }
  const headers = goHeaders({ apiKey, session, attribution });
  const body = {
    model,
    messages: toGoMessages(messages, system),
    max_tokens: maxTokens ?? DEFAULT_MAX_TOKENS,
    temperature: TEMPERATURE,
    reasoning_effort: THINKING_EFFORT,
  };
  return {
    url: `${String(baseURL).replace(/\/+$/, "")}/chat/completions`,
    headers,
    body,
  };
}

export function parseChatCompletion(payload) {
  const choice = (payload.choices || [{}])[0] || {};
  const message = choice.message || {};
  let content = message.content;
  if (Array.isArray(content)) content = flattenContent(content);
  const finish = choice.finish_reason === "length" ? "max-tokens" : "stop";
  const usage = payload.usage || {};
  return {
    content: content || "",
    finish,
    usage: {
      inputTokens: usage.prompt_tokens ?? usage.input_tokens ?? 0,
      outputTokens: usage.completion_tokens ?? usage.output_tokens ?? 0,
    },
  };
}
