import { spawn } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { createUserMessage } from "@deepseek-ai/dsh-llm";

/**
 * Crash retry, then expected-versus-found notes.
 *
 * Same limits as checkpoint 06: at most two traceback follow-ups, then at
 * most two note rounds. The kept clip is the best attempt. The plugin does
 * not pick a winner inside the model. Shortcut tests are recorded after the
 * clip is kept. They are not another follow-up.
 */

export const name = "vgh-clip-loop";
export const inject = ["agents"];
export const CRASH_ROUNDS = 2;
export const NOTE_ROUNDS = 2;

export function crashFeedback(stderr) {
  const detail = stderr && String(stderr).trim() ? String(stderr) : "the script failed";
  return `The script failed.\n${detail}`;
}

export function noteFeedback(lines, recordText, scriptText) {
  const listed = (lines || []).map((line) => `- ${line}`).join("\n");
  return (
    "Checks that failed:\n" +
    listed +
    "\n\nCurrent record:\n" +
    (recordText || "") +
    "\n\nCurrent script:\n" +
    (scriptText || "") +
    "\n\nReply with the corrected record in a ```json fence and the full drawing script in a ```python fence. " +
    "The script must still write the frames, log.json, and trap.json."
  );
}

export function followupMessage(text) {
  return {
    role: "user",
    content: [{ type: "text", text }],
    source: { kind: "user" },
  };
}

function rank(summary) {
  return [
    summary.validClip ? 1 : 0,
    summary.strictPass ? 1 : 0,
    Number(summary.strictPassed || 0),
    summary.picture ? 1 : 0,
  ];
}

export function betterClip(next, prev) {
  const left = rank(next);
  const right = rank(prev);
  for (let i = 0; i < left.length; i += 1) {
    if (left[i] !== right[i]) return left[i] > right[i];
  }
  return false;
}

export class ClipKeeper {
  constructor({ crashRounds = CRASH_ROUNDS, noteRounds = NOTE_ROUNDS } = {}) {
    this.crashLimit = crashRounds;
    this.noteLimit = noteRounds;
    this.crashUsed = 0;
    this.noteUsed = 0;
    this.attempt = 0;
    this.bestN = 0;
    this.best = null;
    this.phase = "crash";
  }

  observe(summary) {
    const index = this.attempt;
    if (this.best === null || betterClip(summary, this.best)) {
      this.best = summary;
      this.bestN = index;
    }
    if (this.phase === "crash") {
      if (!summary.validClip && this.crashUsed < this.crashLimit) {
        this.crashUsed += 1;
        this.attempt += 1;
        return {
          action: "followup",
          kind: "crash",
          text: summary.crashText || crashFeedback(""),
          kept: this.bestN,
        };
      }
      this.phase = "notes";
    }
    if (summary.strictPass && summary.picture) {
      return this.keep(index);
    }
    const lines = summary.noteLines || [];
    if (this.noteUsed < this.noteLimit && lines.length > 0) {
      this.noteUsed += 1;
      this.attempt += 1;
      return {
        action: "followup",
        kind: "notes",
        text: summary.noteText || noteFeedback(lines, summary.recordText, summary.scriptText),
        kept: this.bestN,
      };
    }
    return this.keep(index);
  }

  keep(index) {
    return {
      action: "keep",
      kept: this.bestN,
      restored: this.bestN !== index,
      crashRounds: this.crashUsed,
      noteRounds: this.noteUsed,
      roundsUsed: this.crashUsed + this.noteUsed,
      shortcuts: this.best?.shortcuts || null,
    };
  }
}

const KEEP_NAMES = ["record.json", "trap.json", "log.json", "scene.py", "trace.jsonl", "clip.mp4", "fair-score.json"];

export function assistantText(agent, turn) {
  const session = agent?.session;
  if (!session || typeof session.seq !== "number" || typeof session.eventAt !== "function") return "";
  let active = false;
  const parts = [];
  for (let seq = 0; seq < session.seq; seq += 1) {
    const event = session.eventAt(seq);
    if (!event) continue;
    if (event.type === "turn/start") {
      active = turn == null || event.data?.turn === turn;
      if (active) parts.length = 0;
      continue;
    }
    if (!active || event.type !== "assistant/message") continue;
    const content = event.data?.message?.content || [];
    const text = content.filter((block) => block && block.type === "text").map((block) => String(block.text || "")).join("");
    if (text.trim()) parts.push(text);
  }
  return parts.join("\n\n");
}

function repoRoot() {
  return fileURLToPath(new URL("..", import.meta.url));
}

function publishAttempt(src, dest) {
  mkdirSync(dest, { recursive: true });
  for (const name of KEEP_NAMES) {
    const from = join(src, name);
    if (!existsSync(from)) continue;
    copyFileSync(from, join(dest, name));
  }
}

export function applyReply(outDir, sceneId, text) {
  return new Promise((resolve, reject) => {
    const child = spawn("python3", ["-m", "harness.dsh_bridge", "apply-reply", outDir, sceneId], {
      cwd: repoRoot(),
      stdio: ["pipe", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(stderr.slice(-800) || `apply-reply exit ${code}`));
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch (error) {
        reject(error);
      }
    });
    child.stdin.write(text);
    child.stdin.end();
  });
}

async function liveAttempt(payload, keeper) {
  const root = process.env.VGH_OUT;
  const scene = process.env.VGH_SCENE;
  const dir = join(root, "attempts", String(keeper.attempt));
  mkdirSync(dir, { recursive: true });
  const text = assistantText(payload.agent, payload.turn);
  try {
    return await applyReply(dir, scene, text);
  } catch (error) {
    return {
      validClip: false,
      strictPass: false,
      strictPassed: 0,
      picture: false,
      crashText: crashFeedback(String(error && error.message ? error.message : error).slice(0, 800)),
      noteLines: [],
      recordText: "",
      scriptText: "",
      shortcuts: { no_video: false, single_frame: false, shuffled: false },
    };
  }
}

function liveMessage(text) {
  return createUserMessage({
    content: [{ type: "text", text }],
    source: { kind: "user" },
  });
}

export function apply(ctx, config = {}) {
  const keepers = new Map();
  const live = Boolean(process.env.VGH_OUT && process.env.VGH_SCENE);
  const readAttempt = config.readAttempt || (live ? liveAttempt : null);
  const create = config.createMessage || (live ? liveMessage : followupMessage);
  ctx.on("agent/turn-stopping", async (payload) => {
    const id = payload.agent?.id ?? "main";
    let keeper = keepers.get(id);
    if (!keeper) {
      keeper = new ClipKeeper(config);
      keepers.set(id, keeper);
    }
    if (!readAttempt) throw new Error("clip loop needs readAttempt");
    const attempt = await readAttempt(payload, keeper);
    const decision = keeper.observe(attempt);
    if (decision.action === "followup") {
      payload.agent.followup(create(decision.text));
    } else if (live && process.env.VGH_OUT) {
      const src = join(process.env.VGH_OUT, "attempts", String(decision.kept));
      writeFileSync(
        join(process.env.VGH_OUT, "loop.json"),
        JSON.stringify({
          crash_rounds: decision.crashRounds,
          note_rounds: decision.noteRounds,
          rounds_used: decision.roundsUsed,
          kept_attempt: decision.kept,
          shortcuts: decision.shortcuts,
        }),
      );
      if (existsSync(src)) publishAttempt(src, process.env.VGH_OUT);
    }
    return decision;
  });
}
