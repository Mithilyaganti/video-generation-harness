/**
 * This Node build does not set import.meta.main, so the published dsh bin
 * returns without booting. Call the same runCli. This is not a fork.
 *
 * DSH_BIN points at the installed package entry. ESM does not search NODE_PATH.
 */
import { pathToFileURL } from "node:url";

const bin = process.env.DSH_BIN || "/tmp/dsh-cli/node_modules/@deepseek-ai/dsh/lib/bin.js";
const { runCli } = await import(pathToFileURL(bin).href);
process.argv = ["node", "dsh", ...process.argv.slice(2)];
await runCli();
