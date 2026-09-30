/**
 * Offline plugin checks. No network. No key file.
 */

import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { ClipKeeper, apply as applyLoop, assistantText, crashFeedback, followupMessage, noteFeedback } from "./clip-loop.mjs";
import {
  THINKING_EFFORT,
  USER_AGENT,
  buildGoRequest,
  loadCredentials,
  parseChatCompletion,
  publicHeaders,
  redact,
} from "./go-request.mjs";
import { apply as applyGo } from "./opencode-go.mjs";
import { ALLOW_PLUGIN, STOCK_BLOCKS_OS_PATHLIB } from "./sandbox-policy.mjs";
import { SAVE_DEADLINE_MS, apply as applyWindow, applyDeadline, isSceneCall, renderSceneTool } from "./save-window.mjs";
import { SCENES } from "./scenes.mjs";

const failures = [];

async function check(name, fn) {
  try {
    await fn();
    console.log(`pass ${name}`);
  } catch (error) {
    failures.push(name);
    console.error(`fail ${name}: ${error && error.stack ? error.stack : error}`);
  }
}

await check("thinking cap and go headers", () => {
  const request = buildGoRequest({
    model: "space-bunny-free",
    messages: [{ role: "user", content: [{ type: "text", text: "draw" }] }],
    session: "sess-offline",
    apiKey: "oc_sk_selftest_only",
    baseURL: "https://opencode.ai/zen/go/v1",
    attribution: { "user-agent": "deepseek-harness/0.2.0" },
    maxTokens: 6000,
  });
  assert.equal(request.body.reasoning_effort, THINKING_EFFORT);
  assert.equal(request.body.temperature, 0.2);
  assert.equal(request.body.max_tokens, 6000);
  assert.equal(request.headers["User-Agent"], USER_AGENT);
  assert.equal(request.headers["x-opencode-session"], "sess-offline");
  assert.equal(Object.keys(request.headers).filter((name) => name.toLowerCase() === "user-agent").length, 1);
  const shown = JSON.stringify(publicHeaders(request.headers));
  assert.equal(shown.includes("oc_sk_"), false);
  assert.equal(shown.includes("selftest_only"), false);
  assert.throws(() => buildGoRequest({
    model: "muse-spark-1.3-contributor",
    messages: [],
    session: "s",
    apiKey: "k",
    baseURL: "https://example.test",
  }), /refusing/);
  assert.throws(() => buildGoRequest({
    model: "deepseek-v4.1-flash",
    messages: [],
    session: "s",
    apiKey: "k",
    baseURL: "https://example.test",
    reasoningEffort: "high",
  }), /thinking cap/);
  assert.throws(() => buildGoRequest({
    model: "space-bunny-free",
    messages: [],
    session: "",
    apiKey: "k",
    baseURL: "https://example.test",
  }), /x-opencode-session/);
});

await check("credential file is redacted", () => {
  const dir = mkdtempSync(join(tmpdir(), "vgh-go-"));
  const envFile = join(dir, "go.env");
  writeFileSync(envFile, "OPENCODE_API_KEY=oc_sk_selftest_only\n");
  try {
    const loaded = loadCredentials({ OPENCODE_GO_ENV: envFile }, {});
    assert.equal(loaded.key, "oc_sk_selftest_only");
    assert.equal(redact(`Bearer ${loaded.key} in ${loaded.key}`).includes("oc_sk_"), false);
    assert.match(redact(`Bearer ${loaded.key}`), /Bearer \[redacted\]/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

await check("chat completion parser ignores reasoning text", () => {
  const parsed = parseChatCompletion({
    choices: [{
      message: { content: "script", reasoning_content: "x".repeat(50) },
      finish_reason: "length",
    }],
    usage: { prompt_tokens: 3, completion_tokens: 4 },
  });
  assert.equal(parsed.content, "script");
  assert.equal(parsed.finish, "max-tokens");
  assert.equal(parsed.usage.inputTokens, 3);
});

await check("adapter sets both headers and the thinking cap", async () => {
  const seen = [];
  const ctx = {
    llm: {
      registerAdapter(providers, adapter) {
        seen.push({ providers, adapter });
      },
    },
  };
  applyGo(ctx, { providers: ["vgh-go"], apiKey: "oc_sk_selftest_only", baseURL: "http://127.0.0.1:9" });
  assert.deepEqual(seen[0].providers, ["vgh-go"]);
  const adapter = seen[0].adapter;
  const info = await adapter.resolveModel("vgh-go", "space-bunny-free");
  assert.deepEqual(info.reasoning.efforts.map((item) => String(item.id)), ["low"]);
  const models = await adapter.listModels("vgh-go");
  assert.deepEqual(models.map((item) => item.id), ["space-bunny-free", "deepseek-v4.1-flash"]);
  let captured;
  const original = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    captured = { url, init };
    return {
      ok: true,
      json: async () => ({
        choices: [{ message: { content: "hello" }, finish_reason: "stop" }],
        usage: { prompt_tokens: 1, completion_tokens: 1 },
      }),
      text: async () => "",
    };
  };
  try {
    const chunks = [];
    for await (const chunk of adapter.stream({
      provider: "vgh-go",
      model: "deepseek-v4.1-flash",
      messages: [{ role: "user", content: "brief" }],
      sessionId: "sess-wire",
      maxTokens: 6000,
    })) {
      chunks.push(chunk);
    }
    const headers = captured.init.headers;
    const body = JSON.parse(captured.init.body);
    assert.equal(headers["User-Agent"], USER_AGENT);
    assert.equal(headers["x-opencode-session"], "sess-wire");
    assert.equal(body.reasoning_effort, "low");
    assert.equal(JSON.stringify(chunks).includes("oc_sk_"), false);
    assert.equal(chunks.at(-1).reason.kind, "stop");
    globalThis.fetch = async () => ({
      ok: false,
      status: 400,
      text: async () => "missing oc_sk_selftest_only",
      json: async () => ({}),
    });
    await assert.rejects(
      async () => {
        for await (const _chunk of adapter.stream({
          provider: "vgh-go",
          model: "space-bunny-free",
          messages: [{ role: "user", content: "brief" }],
          sessionId: "sess-wire",
        })) {
          /* consume */
        }
      },
      (error) => {
        assert.equal(String(error.message).includes("oc_sk_"), false);
        assert.match(error.message, /\[redacted\]/);
        return true;
      },
    );
    let calls = 0;
    globalThis.fetch = async () => {
      calls += 1;
      throw new Error("fetch should not run");
    };
    await assert.rejects(
      async () => {
        for await (const _chunk of adapter.stream({
          provider: "vgh-go",
          model: "space-bunny-free",
          messages: [],
          sessionId: "sess-wire",
          reasoningEffort: "high",
        })) {
          /* consume */
        }
      },
      (error) => error.code === "UNSUPPORTED_REASONING_EFFORT",
    );
    assert.equal(calls, 0);
  } finally {
    globalThis.fetch = original;
  }
});

await check("save window is 120 seconds for the scene script", async () => {
  assert.equal(SAVE_DEADLINE_MS, 120_000);
  assert.equal(renderSceneTool.timeoutMs, 120_000);
  assert.equal(isSceneCall({ name: "bash", arguments: { command: "ls" } }), false);
  const exec = { name: "render_scene", signal: new AbortController().signal };
  let seen;
  const result = applyDeadline(exec, () => {
    seen = exec.signal;
    return new Promise((resolve) => {
      exec.signal.addEventListener("abort", () => resolve("aborted"), { once: true });
    });
  }, 30);
  assert.equal(await result, "aborted");
  assert.equal(seen.aborted, true);
  const plain = { name: "bash", arguments: { command: "pwd" }, signal: null };
  let passed = false;
  applyDeadline(plain, () => {
    passed = plain.signal === null;
    return "next";
  });
  assert.equal(passed, true);
  const tools = [];
  let listener;
  applyWindow({
    tools: { register(tool) { tools.push(tool); } },
    on(event, fn) {
      assert.equal(event, "tools/execute");
      listener = fn;
    },
  });
  assert.equal(tools[0].name, "render_scene");
  assert.equal(typeof listener, "function");
  const dir = mkdtempSync(join(tmpdir(), "vgh-render-"));
  const script = join(dir, "scene.py");
  const out = join(dir, "out");
  writeFileSync(
    script,
    "import os\nimport pathlib\nimport sys\nframes = pathlib.Path(sys.argv[1]) / 'frames'\nframes.mkdir(parents=True, exist_ok=True)\n(frames / 'f_000.png').write_bytes(b'ok')\nprint(os.path.isdir(frames))\n",
  );
  try {
    const ran = await renderSceneTool.execute({ script_path: script, output_dir: out }, { signal: new AbortController().signal });
    assert.equal(ran.exit, 0);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

await check("stock sandbox does not need an os allow plugin", () => {
  assert.equal(STOCK_BLOCKS_OS_PATHLIB, false);
  assert.equal(ALLOW_PLUGIN, false);
  assert.equal(SCENES.length, 12);
  assert.equal(SCENES.includes("orchard-basket"), true);
  assert.equal(SCENES.includes("chapel-candle"), true);
});

await check("crash retry then notes, keep the best", () => {
  const keeper = new ClipKeeper();
  const first = keeper.observe({
    validClip: false,
    strictPass: false,
    strictPassed: 0,
    picture: false,
    crashText: crashFeedback("Traceback: boom"),
    noteLines: ["plant_in_frames: expected spoon"],
    shortcuts: { no_video: false, single_frame: false, shuffled: false },
  });
  assert.equal(first.kind, "crash");
  assert.equal(first.text, "The script failed.\nTraceback: boom");
  assert.equal(first.text.includes("expected"), false);
  const second = keeper.observe({
    validClip: false,
    strictPass: false,
    strictPassed: 0,
    picture: false,
    crashText: crashFeedback("NameError: sys"),
    noteLines: ["plant_in_frames: expected spoon"],
    shortcuts: { no_video: false, single_frame: false, shuffled: false },
  });
  assert.equal(second.kind, "crash");
  const third = keeper.observe({
    validClip: true,
    strictPass: false,
    strictPassed: 10,
    picture: true,
    crashText: crashFeedback("ignored"),
    noteLines: ["plant_in_frames: expected spoon found plant"],
    recordText: "RECORD",
    scriptText: "SCRIPT",
    shortcuts: { no_video: false, single_frame: false, shuffled: false },
  });
  assert.equal(third.kind, "notes");
  assert.match(third.text, /Checks that failed:/);
  assert.match(third.text, /expected spoon found plant/);
  assert.match(third.text, /Current record:\nRECORD/);
  assert.equal(third.text.startsWith("The script failed."), false);
  const fourth = keeper.observe({
    validClip: true,
    strictPass: true,
    strictPassed: 18,
    picture: true,
    noteLines: [],
    shortcuts: { no_video: true, single_frame: true, shuffled: true },
  });
  assert.equal(fourth.action, "keep");
  assert.equal(fourth.crashRounds, 2);
  assert.equal(fourth.noteRounds, 1);
  assert.equal(fourth.kept, 3);
  assert.deepEqual(fourth.shortcuts, { no_video: true, single_frame: true, shuffled: true });
});

await check("two note rounds then restore the better clip", () => {
  const keeper = new ClipKeeper();
  const opening = keeper.observe({
    validClip: true,
    strictPass: false,
    strictPassed: 10,
    picture: true,
    noteLines: ["key_matches_log: expected writer_key"],
    shortcuts: { no_video: false, single_frame: false, shuffled: false },
  });
  assert.equal(opening.kind, "notes");
  assert.equal(keeper.crashUsed, 0);
  keeper.observe({
    validClip: true,
    strictPass: false,
    strictPassed: 9,
    picture: false,
    noteLines: ["still wrong"],
    shortcuts: { no_video: false, single_frame: false, shuffled: false },
  });
  const done = keeper.observe({
    validClip: false,
    strictPass: false,
    strictPassed: 0,
    picture: false,
    crashText: crashFeedback("later crash"),
    noteLines: ["still wrong"],
    shortcuts: { no_video: false, single_frame: false, shuffled: false },
  });
  assert.equal(done.action, "keep");
  assert.equal(done.noteRounds, 2);
  assert.equal(done.crashRounds, 0);
  assert.equal(done.kept, 0);
  assert.equal(done.restored, true);
  assert.equal(done.shortcuts.no_video, false);
});

await check("passing first reply does not follow up", () => {
  const keeper = new ClipKeeper();
  const decision = keeper.observe({
    validClip: true,
    strictPass: true,
    strictPassed: 18,
    picture: true,
    noteLines: [],
    shortcuts: { no_video: true, single_frame: true, shuffled: true },
  });
  assert.equal(decision.action, "keep");
  assert.equal(decision.roundsUsed, 0);
});

await check("turn-stopping followup is the traceback only", async () => {
  let handler;
  applyLoop({
    on(event, fn) {
      assert.equal(event, "agent/turn-stopping");
      handler = fn;
    },
  }, {
    readAttempt: async () => ({
      validClip: false,
      strictPass: false,
      strictPassed: 0,
      picture: false,
      crashText: crashFeedback("Traceback: boom"),
      noteLines: ["plant_in_frames: expected spoon"],
    }),
  });
  const calls = [];
  const decision = await handler({
    agent: {
      id: "scene",
      followup(message) {
        calls.push(message);
      },
    },
  });
  assert.equal(decision.kind, "crash");
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0], followupMessage("The script failed.\nTraceback: boom"));
  assert.equal(noteFeedback(["a"], "", "").includes("```json"), true);
});

await check("assistant text is the current turn", () => {
  const agent = {
    session: {
      seq: 4,
      eventAt(seq) {
        return [
          { type: "turn/start", data: { turn: 1 } },
          { type: "assistant/message", data: { message: { content: [{ type: "text", text: "old" }] } } },
          { type: "turn/start", data: { turn: 2 } },
          { type: "assistant/message", data: { message: { content: [{ type: "text", text: "```python\nprint(1)\n```" }] } } },
        ][seq];
      },
    },
  };
  assert.equal(assistantText(agent, 2).includes("print(1)"), true);
  assert.equal(assistantText(agent, 2).includes("old"), false);
});

await check("patch does not carry a key", () => {
  const patch = readFileSync(new URL("./cordis.patch.yml", import.meta.url), "utf8");
  assert.equal(patch.includes("oc_sk_"), false);
  assert.equal(patch.includes("vgh-go"), true);
  assert.equal(patch.includes("vgh-save-window"), true);
  assert.equal(patch.includes("vgh-clip-loop"), true);
  assert.equal(patch.includes("./opencode-go.mjs"), true);
  assert.equal(patch.includes("./save-window.mjs"), true);
  assert.equal(patch.includes("./clip-loop.mjs"), true);
  assert.equal(patch.includes("record.json shape"), false);
});

if (failures.length) {
  console.error(`plugin selftest failed: ${failures.join(", ")}`);
  process.exit(1);
}
console.log("plugin selftest ok");
