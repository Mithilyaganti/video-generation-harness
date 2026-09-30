import { readFileSync, appendFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { Type } from "typebox";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const CRASH_CAP = 2;
const NOTE_CAP = 2;

function providerSpec(): Record<string, unknown> {
  const specPath = process.env.PI_PROVIDER_SPEC;
  if (!specPath) {
    throw new Error("PI_PROVIDER_SPEC is not set");
  }
  const spec = JSON.parse(readFileSync(specPath, "utf8")) as Record<string, unknown>;
  const base = process.env.OPENCODE_BASE_URL;
  if (base) {
    spec.baseUrl = base;
  }
  return spec;
}

function sceneId(): string {
  return process.env.PI_SCENE || "";
}

function noteWrite(cwd: string, kind: "record" | "code"): void {
  mkdirSync(cwd, { recursive: true });
  appendFileSync(join(cwd, ".pi-write-order.txt"), kind + "\n");
}

function assistantText(message: { content?: unknown }): string {
  const content = message.content;
  if (typeof content === "string") {
    return content;
  }
  if (!Array.isArray(content)) {
    return "";
  }
  return content
    .map((part) => {
      if (!part || typeof part !== "object") {
        return "";
      }
      const block = part as { type?: string; text?: string };
      return block.type === "text" ? block.text || "" : "";
    })
    .filter(Boolean)
    .join("\n");
}

export default function (pi: ExtensionAPI) {
  pi.registerProvider("opencode-go", providerSpec());

  pi.registerFlag("scene", {
    type: "string",
    description: "Scene id for the clip harness",
  });

  pi.registerTool({
    name: "render_clip",
    label: "Render clip",
    description:
      "Run the scene script with python3 for up to 120 seconds and encode clip.mp4 when it exits 0. os and pathlib are allowed.",
    promptSnippet: "Run scene.py and encode the clip",
    promptGuidelines: [
      "Use render_clip after scene.py and record.json are on disk.",
      "The script may import os and pathlib. The run waits 120 seconds so the frames can finish.",
    ],
    parameters: Type.Object({
      script: Type.Optional(Type.String({ description: "Script path relative to the working directory. Default scene.py" })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const root = process.env.PI_HARNESS_ROOT;
      if (!root) {
        throw new Error("PI_HARNESS_ROOT is not set");
      }
      const script = params.script || "scene.py";
      const ran = await pi.exec(
        "python3",
        ["-m", "harness.pi_clip", "render", "--dir", ctx.cwd, "--script", script],
        { cwd: root, timeout: 150000 },
      );
      const text = (ran.stdout || ran.stderr || "the script failed").trim();
      return {
        content: [{ type: "text", text }],
        details: { exit: ran.code },
      };
    },
  });

  pi.on("session_start", async () => {
    pi.setThinkingLevel("low");
  });

  pi.on("thinking_level_select", async (event) => {
    if (event.level !== "low") {
      pi.setThinkingLevel("low");
    }
  });

  pi.on("tool_execution_end", async (event, ctx) => {
    const args = (event.args || {}) as { path?: string; command?: string };
    const path = String(args.path || "");
    const command = String(args.command || "");
    if (path.endsWith("record.json") || command.includes("record.json")) {
      noteWrite(ctx.cwd, "record");
    }
    if (path.endsWith("scene.py") || command.includes("scene.py") || event.toolName === "render_clip") {
      if (path.endsWith("scene.py") || command.includes("scene.py")) {
        noteWrite(ctx.cwd, "code");
      }
    }
  });

  pi.on("message_end", async (event, ctx) => {
    const message = event.message as { role?: string; content?: unknown };
    if (message.role !== "assistant") {
      return;
    }
    const text = assistantText(message);
    if (!text) {
      return;
    }
    appendFileSync(join(ctx.cwd, ".pi-replies.txt"), text + "\n\n");
  });

  pi.on("agent_before_settle", async (_event, ctx) => {
    const root = process.env.PI_HARNESS_ROOT;
    const scene = (pi.getFlag("scene") as string | undefined) || sceneId();
    if (!root || !scene) {
      return { continue: false };
    }
    const ran = await pi.exec(
      "python3",
      ["-m", "harness.pi_clip", "settle", "--dir", ctx.cwd, "--scene", scene],
      { cwd: root, timeout: 180000 },
    );
    if (ran.code !== 0) {
      return { continue: false };
    }
    let decision: { continue?: boolean; message?: string; kind?: string } = {};
    try {
      const line = ran.stdout.trim().split("\n").filter(Boolean).pop() || "{}";
      decision = JSON.parse(line);
    } catch {
      return { continue: false };
    }
    const message = (decision.message || "").trim();
    if (!decision.continue || !message) {
      return { continue: false };
    }
    const kind = decision.kind === "note" ? "note" : "crash";
    if (kind === "crash" && Number(decision.crash_used) > CRASH_CAP) {
      return { continue: false };
    }
    if (kind === "note" && Number(decision.note_used) > NOTE_CAP) {
      return { continue: false };
    }
    return {
      continue: true,
      entries: [
        {
          type: "custom_message",
          customType: "clip-note",
          content: message,
          display: true,
        },
      ],
    };
  });
}
