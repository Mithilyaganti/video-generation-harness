/**
 * Stock dsh 0.2.0-rc.2 confines filesystem writes (bwrap, then Landlock).
 * It does not deny Python stdlib imports. Checkpoint 06 already allows
 * `os` and `pathlib` so the script can create the frames folder.
 * No allow plugin is registered.
 */
export const STOCK_BLOCKS_OS_PATHLIB = false;
export const ALLOW_PLUGIN = false;

export const PROBE_SOURCE = `
import os
import pathlib
import sys
out = pathlib.Path(sys.argv[1])
frames = out / "frames"
frames.mkdir(parents=True, exist_ok=True)
(frames / "f_000.png").write_bytes(b"ok")
if not os.path.isdir(frames):
    raise SystemExit("frames folder missing")
`.trim() + "\n";
