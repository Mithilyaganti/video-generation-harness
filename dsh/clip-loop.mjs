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

export function apply(ctx, config = {}) {
  const keepers = new Map();
  const create = config.createMessage || followupMessage;
  ctx.on("agent/turn-stopping", async (payload) => {
    const id = payload.agent?.id ?? "main";
    let keeper = keepers.get(id);
    if (!keeper) {
      keeper = new ClipKeeper(config);
      keepers.set(id, keeper);
    }
    const attempt = await config.readAttempt(payload, keeper);
    const decision = keeper.observe(attempt);
    if (decision.action === "followup") {
      payload.agent.followup(create(decision.text));
    }
    return decision;
  });
}
