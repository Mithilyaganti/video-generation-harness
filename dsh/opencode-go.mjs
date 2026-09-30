/**
 * OpenCode Go adapter plugin.
 *
 * stream() owns the HTTP request, so it can set User-Agent and
 * x-opencode-session. Stock llm-pi-ai strips User-Agent (attribution wins)
 * and sends the harness session id as x-opencode-session only when pi-ai's
 * OpenCode wrapper is on that route. The checkpoint 06 client sends
 * video-generation-harness/0.1, which the stock adapter cannot set.
 * This plugin registers its own route. The deepseek-ai/deepseek-harness
 * core is not forked.
 *
 * The thinking cap is reasoning_effort "low" on every Go request, the same
 * cap as checkpoint 06. The record schema stays in the task text.
 */

import { LlmAdapter, LlmError, ReasoningEffortId, attributionHeaders } from "@deepseek-ai/dsh-llm";
import Schema from "@deepseek-ai/schemastery";

import {
  DEFAULT_BASE_URL,
  DEFAULT_MAX_TOKENS,
  THINKING_EFFORT,
  USER_AGENT,
  buildGoRequest,
  loadCredentials,
  parseChatCompletion,
  redact,
} from "./go-request.mjs";

export const name = "vgh-opencode-go";
export const inject = ["llm"];

export const Config = Schema.object({
  providers: Schema.array(Schema.string()).default(["vgh-go"]),
  baseURL: Schema.string().default(DEFAULT_BASE_URL),
});

const LOW = ReasoningEffortId(THINKING_EFFORT);

export class OpenCodeGoAdapter extends LlmAdapter {
  constructor(config = {}) {
    super();
    this.config = config;
  }

  listModels(provider) {
    return Promise.resolve([
      { provider, id: "space-bunny-free", name: "space-bunny-free" },
      { provider, id: "deepseek-v4.1-flash", name: "deepseek-v4.1-flash" },
    ]);
  }

  resolveModel(provider, model) {
    return Promise.resolve({
      provider,
      id: model,
      name: model,
      defaultMaxTokens: DEFAULT_MAX_TOKENS,
      reasoning: {
        efforts: [{ id: LOW, name: "Low" }],
        defaultEffort: LOW,
      },
    });
  }

  async *stream(options) {
    let credentials;
    try {
      credentials = loadCredentials(process.env, {
        apiKey: this.config.apiKey,
        baseURL: this.config.baseURL || options.baseURL,
      });
    } catch (error) {
      throw new LlmError(redact(error.message || "missing credential"), "MISSING_CREDENTIAL");
    }
    let request;
    try {
      request = buildGoRequest({
        model: options.model,
        messages: options.messages,
        system: options.system,
        session: options.sessionId,
        maxTokens: options.maxTokens,
        apiKey: credentials.key,
        baseURL: credentials.base,
        attribution: attributionHeaders(),
        reasoningEffort: options.reasoningEffort,
      });
    } catch (error) {
      const code = String(error.message || "").startsWith("thinking cap")
        ? "UNSUPPORTED_REASONING_EFFORT"
        : "INVALID_REQUEST";
      throw new LlmError(redact(error.message || "bad request"), code);
    }
    const response = await fetch(request.url, {
      method: "POST",
      headers: request.headers,
      body: JSON.stringify(request.body),
      signal: options.signal,
    });
    if (!response.ok) {
      const detail = redact(await response.text());
      throw new LlmError(`HTTP ${response.status} from Go: ${detail.slice(0, 2000)}`, "PROVIDER_HTTP_ERROR");
    }
    const parsed = parseChatCompletion(await response.json());
    const text = parsed.content;
    yield { type: "block-start", index: 0, blockType: "text" };
    if (text) yield { type: "text-delta", index: 0, text };
    yield { type: "block-end", index: 0, block: { type: "text", text } };
    yield { type: "usage", usage: parsed.usage };
    yield { type: "finish", reason: { kind: parsed.finish } };
  }
}

export function apply(ctx, config = {}) {
  const providers = config.providers?.length ? [...config.providers] : ["vgh-go"];
  ctx.llm.registerAdapter(providers, new OpenCodeGoAdapter(config));
}

export { USER_AGENT, THINKING_EFFORT };
