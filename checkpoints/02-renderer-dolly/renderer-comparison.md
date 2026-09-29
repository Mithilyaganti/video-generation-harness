# Which renderer fits a cheap hidden-plant test

Python with PyGame fits best for the cheap smoke test. On the same four scenes, PyGame and Three.js both kept the plant and the false question every time. Blender kept the plant on three scenes and lost it on one. The free model wrote the PyGame files in about 34 seconds, the Three.js files in about 94 seconds, and the Blender files in about 6 minutes. The model charge was $0.

Every scored clip in that table is 480 by 270, 16 frames, about 2 seconds. That is a smoke test. The Three.js mp4s from that test are byte-identical to the PyGame mp4s. They are not copies. Headless Chrome re-rendered the four Three.js files and landed on the same pixels, because both sides were told to draw the same solid rectangles with smoothing off. A separate 10-second clip with a moving camera does not match: PyGame, Three.js, and Blender disagree on every frame.

Clips, frames, and the scene records are in `/cursor/stores/bc-f9fe9480-5b96-4277-be5d-c761609be7ed/media/renderers/`.

## What was compared

`space-bunny-free` wrote every scene file. The same four records went to each renderer, with the same instructions, plus a short note on how that renderer saves a frame. No paid model. No second repair if the pictures were wrong. A repair was allowed only if the file crashed. None of the twelve files crashed.

Each scored clip is 16 frames, 480 by 270, 8 frames a second, about two seconds. That size is only a smoke test. The pictures were written as PNGs, then ffmpeg made the mp4. Three.js sought one frame at a time and captured that canvas. It was not a screen recording of a playing clip. Blender ran headless Cycles, one sample, real renders.

The script kept a plant when the plant’s color was on the frames named in the record, covering at least 60% of the listed rectangle, and was missing on the other frames. A trap worked when the question was false, the false thing was absent from the pictures, and the true object’s color was in the pictures.

The four scenes use different objects:

- Shed shelf. A yellow watering can, a brown crate, white gloves. A green sprout shows only on frames 10–13. The question “How many red watering cans are on the shelf?” is false. There is one yellow can.
- Market stall. Three orange lanterns, a teal awning, a steel-blue scale. A purple onion rolls across on frames 4–9. “Is the scale gold?” is false.
- Station bench. One blue suitcase, a green bench, a black clock. A yellow ticket shows only on frames 12–15. “How many blue suitcases?” claiming two is false.
- Shop tank. A cyan bowl, one yellow fish, two grey boxes. A brown snail sits on the bowl on frames 6–10. “What color is the red fish?” is false. The fish is yellow.

## The numbers

Write time is the model call. Draw time is rendering the 16 PNGs. Token counts include the model’s hidden reasoning, so they are larger than the files. PyGame files were about 1,400–1,700 characters. Three.js files were about the same. Blender files were about 4,400–4,900 characters. Space Bunny Free is listed as free, so the bill is $0.

| Renderer | Plant kept | Trap works | Write time | Draw time | Prompt tokens | Completion tokens |
| --- | --- | --- | --- | --- | --- | --- |
| Python / PyGame | 4 of 4 | 4 of 4 | 33.6 s | 34.3 s | 4,804 | 3,475 |
| Three.js | 4 of 4 | 4 of 4 | 94.0 s | 44.6 s | 5,756 | 6,087 |
| Blender Cycles | 3 of 4 | 4 of 4 | 369.4 s | 31.2 s | 6,604 | 25,381 |

Per scene:

| Scene | Python plant / trap | Python write + draw | Three.js plant / trap | Three.js write + draw | Blender plant / trap | Blender write + draw |
| --- | --- | --- | --- | --- | --- | --- |
| Shed shelf | yes / yes | 6.5 s + 11.6 s | yes / yes | 20.4 s + 8.1 s | yes / yes | 122.5 s + 6.2 s |
| Market stall | yes / yes | 7.4 s + 11.6 s | yes / yes | 35.8 s + 11.2 s | yes / yes | 87.8 s + 6.9 s |
| Station bench | yes / yes | 6.3 s + 5.7 s | yes / yes | 27.1 s + 8.4 s | yes / yes | 77.9 s + 8.8 s |
| Shop tank | yes / yes | 13.3 s + 5.4 s | yes / yes | 10.8 s + 16.9 s | no / yes | 81.2 s + 9.3 s |

The Blender shop tank is the miss. The log named the snail on frames 6–10, and the question stayed false. In the pictures the snail is a speck: 60 brown pixels, where the record asked for a 34 by 30 rectangle (about 1,020 pixels). The snail sits on the bowl, and both planes were at the same depth, so Cycles showed only the two-pixel strip that sticks past the bowl. PyGame and Three.js draw the later shape on top, so the snail stayed full size (1,020 pixels).

Making the mp4 took under 1.2 seconds a clip. The twelve clips ran one after another, about 18 minutes of wall clock, almost all of it the Blender writes.

PyGame 2.6.1 installed with pip and ran. Chrome was already on the machine. Blender was not. The 4.2.23 Linux build is a 334 MB download, and headless Cycles ran.

## The matching mp4s are real Three.js

Mithil checked the shop-tank clips. `media/renderers/python/tank-glass/clip.mp4` and `media/renderers/three/tank-glass/clip.mp4` share an md5 that starts `3bcf6ea8`. The other three scenes match the same way. Shed shelf starts `41f8ee6b1ad5`, market stall `9b4b4c80dcda`, station bench `f76ce88ea9f4`.

The PNG files are not the same bytes. A shed frame is 1,161 bytes from PyGame and 1,150 bytes from Three.js, and the file times are about a minute apart, which is when the Three.js pass ran. The pixels inside those PNGs are the same on all 16 frames of all four scenes. ffmpeg then writes the same mp4 from the same pixels.

The Three.js sources are separate files (`scene.js`, about 1,300–1,800 characters) that build a `THREE.Scene`, an orthographic camera, and `MeshBasicMaterial` rectangles. I ran them again in headless Chrome 148.0.7778.96. Each scene reported WebGL as `ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)`, with no page errors. The new pictures match the stored Three.js frames on 16 of 16 frames in every scene, and those pixels also match PyGame. The proof is `media/renderers/three/chrome-proof.json`.

So the 4 of 4 tie stays. It is a tie on flat rectangles, not a copied file. The recipe asked both renderers for the same top-left, the same width and height, and no smoothing. A WebGL clear of those rectangles can hit the same pixels as `pygame.Surface.fill`.

## A 10-second dolly, where they differ

The smoke test cannot show a camera move. I added one clip, `aisle-dolly`, written to one spec in PyGame, Three.js, and Blender. This one was not written by `space-bunny-free`. It is a check that the renderers can disagree. It is 640 by 360, 80 frames, 8 frames a second, 10 seconds. A view dollies from left to right past an orange crate and a blue cabinet. A green fern is drawn only on frames 40–55. The question “Is the cabinet red?” is false.

| Renderer | Plant only on frames 40–55 | Frames that match PyGame | Pixels changed from first frame to last | Draw time |
| --- | --- | --- | --- | --- |
| PyGame | yes, 3,220 green pixels | — | 35,000 | 77 s |
| Three.js in Chrome | yes, 566–684 green pixels | 0 of 80 | 60,907 | 73 s |
| Blender Cycles | yes, 4,299–4,613 green pixels | 0 of 80 | 157,902 | 70 s |

On a middle frame, PyGame against Three.js differs in all 230,400 pixels. The three mp4s have different md5s (`a77afa402a41`, `61ee079b727a`, `09f11a517c4d`). PyGame is a flat scroll. Three.js is a lit perspective view from SwiftShader. Blender is a lit Cycles view. None of them contain a red cabinet. The blue cabinet is exact `#2f6fdb` in PyGame (12,600 pixels). In Three.js and Blender the cabinet is blue under a light, so the exact hex is gone and the shape is still there.

Those draw times are mostly writing 80 PNGs. They are not the cost of the pixels themselves.

## Why Python

The hard checks on the smoke test are the plant and the false question. Python and Three.js tied on those flat rectangles. Python cost less model time, and the pictures are plain rectangles the script can count without a browser or a 3D install. That is the right fit for a low-cost hidden-plant benchmark at this size.

Three.js is the next choice when a clip needs a moving camera. The 10-second dolly is the evidence: Chrome drew a lit perspective view, and none of its 80 frames match PyGame. Blender is the one that can do real depth and light. On the flat scenes it was the slow write, and it hid a plant that overlapped another object. On the dolly, Cycles kept the fern and the picture moved.

## What I kept from the research note

Mithil’s note is in `internal/threejs-blender-research.md`. These parts made the comparison stronger, and they are in the numbers above.

- Seek one frame, capture that frame, then ffmpeg. Three.js did that. The WebGL renderer string on this machine is SwiftShader: `ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero)))`.
- The canvas was created with `preserveDrawingBuffer` on, and Chrome was started with the SwiftShader flags. The sprout came back as 2,268 pixels, which is 42 by 54, so the capture was exact.
- The plant check counts pixels. It does not ask another model whether the clip looks right.
- A short placement recipe went in each prompt, so the model was not left to discover PyGame, Three.js, or bpy on its own.
- A crashed file would have had one repair. None needed one. Two Blender calls timed out and were sent again. Those retries are inside the write times.
- The mp4s are tagged BT.709, and the plant check was run again on frames decoded from the video. Same result: 11 of 12. The untagged encode had only shifted the sprout by about one color level.
- His timing on this kind of machine: a heavier 10-second Three.js clip, 640 by 360, finished in 4.1 seconds. I timed the shed scene after Chrome was open. Drawing 300 frames took 8 milliseconds. Capturing 16 canvases took 0.46 seconds. Opening Chrome took 1.3 seconds. The 8–17 second Three.js draw times in the table are mostly starting a browser per clip.
- People with a GPU use EEVEE for agent Blender loops. I tried EEVEE Next here. It needed `libEGL`. Then the same 16 simple frames took 204 seconds. Cycles at one sample, which is what the scored clips use, took 6–9 seconds a clip including starting Blender. The scored path stays Cycles.
- Write time and draw time are reported apart.

## What I skipped from that note

- I did not make Three.js the default. On the smoke test it tied Python, and the model took longer to write it. The 10-second dolly shows the pictures can differ once the camera moves.
- I did not score EEVEE. On this machine it was the slow renderer.
- I did not use a Blender MCP server, Remotion, React Three Fiber, a physics library, or a pipeline that builds models in Blender and draws them in Three.js.
- I did not ask a vision model, Muse, or a text-only model to judge the trick questions. The trap score is the script. A judge would give the same answer for every renderer.
- I did not add a second ID-color pass or Cryptomatte. Each object already has its own flat color, and the script counts that color.
- I did not have a model look at contact sheets.
- I did not let the renderer invent the scene record. The record was written first. The pictures were checked against it.
- I looked for `Math.random`, `Date.now`, and `performance.now` in the twelve files. None of them used those, so there was nothing to reject.
- I left Chrome’s frame-rate limit as it was for the scored runs. His measurement showed that flag changes full-page screenshots. These runs grabbed the canvas, which was already exact.
