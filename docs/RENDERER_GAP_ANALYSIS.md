> Historical investigation of the retired experimental renderer. The current
> Windows engine uses Hookshot's Vulkan renderer. See
> [INDEPENDENT_EVIDENCE.md](INDEPENDENT_EVIDENCE.md) for current measurements and
> [STABLE_ENGINE_MIGRATION.md](STABLE_ENGINE_MIGRATION.md) for the Legacy comparison.

# Windows renderer gap analysis

Historical status: experimental Windows rendering acceptance failed. That engine
was retired; this finding does not describe the replacement stable backend.
The investigation paths below may refer to captures removed during cleanup.

## Decision

Continue to use the installed NX2navi game as the behavioral acceptance reference.
The current DekuForge engine is not equivalent to its renderer. A renamed launcher
or a few configuration defaults cannot establish equivalence. Preserve the working
reference installation and saves. Keep the existing DekuForge launcher, archive
reader, build inventory and source-only repository while reviewing the rendering
backend as a complete subsystem rather than assuming each missing feature is isolated.

A complete replacement with the current reference source is not presently a
redistributable MIT backend: its LICENSE-ADDITIONS grants no license to later changes.
The imported MIT baseline and independently licensed components can be reused with
notices. Study the reference behavior and implement or import permitted components;
do not strip its notices or present the later source as newly authored open source.
This restriction does not prevent local comparison or independent fixes.

## Compared inputs

- Included engine: revision `0478c13e4503a8c1a75155b1e277b8cc53ce149a`, VERSION 0.3.10.
- Local reference source: `NX2Navi/Contribute/NX2navi-cheat-manager`, revision
  `8cb3f1c`, VERSION 0.10.1. This is a local snapshot, not a claim to be latest upstream.
- Game input: verified 1.1.1, extracted and generated only in ignored build folders.
- Hardware in existing measurements: RTX 2080. Compare on the same machine and
  copied save, with resolution, fullscreen, frame limit and reconstruction recorded.
- Reference AUDIT.md reviewed: its subsystem map is useful; its findings explicitly
  distinguish confirmed failures from suspected leads. Its results on other GPUs
  do not establish DekuForge performance or validate our implementation.

## Subsystem gaps

| Area | Evidence in our path | Reference behavior | Consequence / acceptance gate |
|---|---|---|---|
| CPU generation and game timing | Previously generated RT_PATCH_COUNT=0; manual log says no patch table | Version-specific game patch table and real-time framework updates | Four original timing sites now generated and checked; measured host clock ratio near 1 at 26?32 FPS. Validate movement, menus, physics and day clock separately. |
| Task/mesh constant banks | Task, mesh and compute shared cache slot 2 despite different table layouts | Separate stage cache slots | Fixed five independent caches; identical-input native regression passes. Owner still reports holes, so this was not the full cause. |
| Shader translation | Ampere adapter, compute SPIR-V to GLSL to mesh SPIR-V | AmpereLowering.cs plus direct MeshSpirv.cs wrapping | GLSL round trip already lost Fma NoContraction; repaired, but not a comprehensive instruction-semantics proof. Compare stage outputs and resources, not only successful compilation. |
| Visibility counters | Original 256-entry pending ring, then independent serial/frame ledger | Larger replay-aware state and ordered counter writes/fills | Improved owner imagery. Sixteen-frame trace skipped no draws through render conditions. Remaining holes also occur when shader/pipeline work is awaited. |
| Texture lifetime/aliasing | Older image lookup and memory tracking plus local adapters | Larger texture lifetime, alias, format, synchronization and view handling | Audit address reuse and depth aliases before changing sampler or contrast defaults. Shadow and sky errors are not demonstrated to be missing asset files. |
| Depth passes | Read-only EQUAL colour passes after earlier depth production/copies | Matching scene geometry and preserved depth contents | GEQUAL/ALWAYS diagnostics exposed surfaces but broke occlusion. Never enable those diagnostics as a fix. Capture exact float depth and copy/clear ordering. |
| Pipeline preparation | Stored shader inputs and encountered pipeline keys prepared at startup | Preparation and worker machinery integrated with newer renderer | Boot preparation exists; it does not cover every future state. Manual session had repeated ~50 ms waits/skips. Synchronous diagnostic now genuinely awaits translation/creation; owner still sees holes. |
| Reconstruction and movies | Portable cubic reconstruction and AV1 adapter | Integrated movie, resolution, upscaling and temporal settings | Menu/HUD improved; sky/world still fail. Do not attribute all scene defects to upscaling. |
| Performance measurement | Full perf instrumentation reduced FPS to 15?16 in timing test | Lightweight play plus targeted profiling | Use DEKUFORGE_TRACE_CLOCK for clock ratios and separate GPU profiling. Report scene, instrumentation and cache warmth. |
| Build delivery | Native CLI links and boots; launcher wizard still stops after generation | Launcher completes the local pipeline | Complete native build orchestration only after rendering acceptance, with honest stage reporting and rollback. |
| Video settings / cheats | Baseline in-game menu exists; full DLSS integration not verified | Broader settings and custom branch features | Menu presence does not establish working DLSS, frame generation or cheat parity. |

### Source size cross-check

These are file lengths in the imported baseline and local reference, not a count
of missing fixes or proof that longer source is better:

| File | Baseline lines | Reference lines |
|---|---:|---:|
| runtime/vk_exec_draw.c | 3279 | 7620 |
| runtime/vk_texture.c | 1969 | 6841 |
| runtime/vk_exec_xfer.c | 618 | 1420 |
| runtime/frame_rate.c | 292 | 1356 |
| runtime/vk_pipeline.c | 3516 | 9324 |
| runtime/vk_dlaa.c | 1273 | 3473 |

Our composed overrides must also be considered; comparing the baseline alone
understates the work already added. Conversely, successful source tests cover
neither the entire composed renderer nor the reference's gameplay behavior.

## New exact-depth evidence

Local run: `build/windows-game/render-dump-2200-1794890891025877300`.
D32 host copies are exported only when DEKUFORGE_DUMP_RAW_DEPTH is set. PNG depth
previews normalize independently and must not be treated as raw depth.

- Source/target pass 215 to 227: 56.6681% of depth values match exactly;
  575042 values differ by more than one float ULP; maximum absolute difference
  0.0262801. Both contain 1536x864 floats.
- Passes 239 and 241: depth values match exactly, despite 318 draws in pass 241.
- These facts locate a divergence before the read-only colour pass. They do not
  prove the image copy is wrong: intervening intended passes or partial regions
  must be checked. A single first-vertex sample per workgroup cannot prove every
  vertex matches across depth and colour stages.
- Owner screenshot still shows large flat dark rock regions, missing sky/ground
  detail and temporal flicker. The synchronous diagnostic also fails visually.

A subsequent lightweight copy trace at replay frame 2200 confirms a full-size
1536x864 depth copy from guest address 0x8000000000 to 0x8000a80400. Thus a small
copy rectangle is not supported as the cause in this frame. This was a separate
run; it does not identify the exact ordering of the operations in the raw dump.
In the raw run, the early 318-draw depth pass 174 and the colour-pass depth
buffer 239 match at 78.1153% of pixels. That result strengthens the need to
capture immediately around the copy, rather than compare arbitrarily separated
passes and declare the copy broken.

## Ordered next investigations

1. Trace the selected frame's depth copies and clears: source/destination address,
   image identity, exact regions, conditional result and submission order. Compare
   immediately before/after each relevant operation using raw float copies.
2. Identify the first divergent image operation. Check texture aliases and resource
   lifetime against the reference's documented behavior, including delayed recorder
   commands and guest address reuse. Fix only an evidenced ordering/layout defect.
3. If depth contents are intentional, capture matching vertex identities and all
   positions for a bounded set of failing draws, including task payloads and c0
   inputs. Compare depth and colour outputs bitwise, with pipeline/raster state.
4. Validate shader instructions used by those draws independently. Prioritize
   texture coordinate/LOD/compare handling and shared-memory/warp ordering only
   when an affected shader or buffer identifies that route.
5. Re-run the same moving scene with normal rendering, then targeted validation.
   Confirm stable terrain, sky, shadow, foliage and HUD across a sequence, not one
   attractive frame. Measure warmed and first-visit frame times separately.
6. Repeat Market Square, Hyrule Field and a dungeon against the reference before
   connecting the launcher to an installation advertised as playable.

## Release gate

No known missing terrain, sky or shadow corruption; no reproducible flicker;
normal game speed; repeatable save/load and controller behavior; Windows CI green;
measured performance with instrumentation identified. Keep the repository private
and local game artifacts excluded until the owner's release priorities are met.
