/**
 * The save window is the time the scene script gets to finish writing frames.
 * Checkpoint 06 uses 120 seconds. A 40 second cut stopped the picture while
 * frames were still being saved.
 *
 * The tools registry re-fuses the caller signal, so this wrapper cannot
 * outlive a shorter caller deadline. render_scene therefore owns a 120 second
 * timeoutMs, and the scene runner's subprocess timeout is the same 120 seconds.
 */

export const SAVE_DEADLINE_MS = 120_000;
export const name = "vgh-save-window";
export const inject = ["tools"];

export function isSceneCall(exec) {
  const tool = String(exec?.name || "");
  if (tool === "render_scene") return true;
  const args = exec?.arguments || exec?.args || {};
  const command = String(args.command || args.cmd || "");
  return command.includes("scene.py");
}

export function applyDeadline(exec, next, deadlineMs = SAVE_DEADLINE_MS) {
  if (!isSceneCall(exec)) return next();
  const previous = exec.signal;
  const timeout = new AbortController();
  const timer = setTimeout(() => timeout.abort(), deadlineMs);
  exec.signal = previous ? AbortSignal.any([previous, timeout.signal]) : timeout.signal;
  return Promise.resolve(next()).finally(() => {
    clearTimeout(timer);
    exec.signal = previous;
  });
}

export const renderSceneTool = {
  name: "render_scene",
  description: "Run scene.py and wait until it finishes writing frames.",
  parameters: {
    type: "object",
    properties: {
      script_path: { type: "string" },
      output_dir: { type: "string" },
    },
    required: ["script_path", "output_dir"],
  },
  timeoutMs: SAVE_DEADLINE_MS,
  output: {
    schema: { type: "object" },
    render(_args, value) {
      return [{ type: "text", text: `exit ${value?.exit}` }];
    },
  },
  async execute(args, exec) {
    const { spawn } = await import("node:child_process");
    const { fileURLToPath } = await import("node:url");
    const root = fileURLToPath(new URL("..", import.meta.url));
    const script = String(args.script_path);
    const out = String(args.output_dir);
    return await new Promise((resolve) => {
      const py = spawn(
        "python3",
        ["-m", "harness.dsh_bridge", "render", script, out],
        { cwd: root, stdio: ["ignore", "pipe", "pipe"] },
      );
      let stderr = "";
      py.stderr.on("data", (chunk) => {
        stderr += chunk.toString();
      });
      const onAbort = () => py.kill("SIGKILL");
      exec?.signal?.addEventListener("abort", onAbort, { once: true });
      py.on("close", (code) => {
        exec?.signal?.removeEventListener("abort", onAbort);
        resolve({ exit: code ?? -1, stderr: stderr.slice(-4000) });
      });
    });
  },
};

export function apply(ctx) {
  ctx.tools.register(renderSceneTool);
  ctx.on("tools/execute", (exec, next) => applyDeadline(exec, next));
}
