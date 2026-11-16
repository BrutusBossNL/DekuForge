# Windows game-build progress

The launcher is usable. An experimental independent Windows game executable is
linked locally, but world loading and readable rendering are not yet verified.
The runtime library and generated C described below are local artifacts and must
never be presented as a playable release or uploaded as a game.

## Verified development stages

- All 112 selected Windows host-runtime translation units compile with Clang
  23.1.5 from an explicitly supplied MSYS2 UCRT64 toolchain. The separate static
  archive is approximately 20 MiB. Vulkan execution and guest shader translation
  are exercised in isolated tests; they have not passed the playable-build gate.
- A complete, real SDK-generated C chunk compiles with the same compiler using
  the portable SIMD path. Unsupported instructions elsewhere in the SDK remain
  fatal build blockers.
- Full main generation covers 249,960 functions and found four unsupported UDOT
  sites in one chunk. That 657-function chunk has been regenerated with the new
  lowering and compiles with zero unsupported instructions in a separate validation
  folder. The movie module's 1,547 functions generate without unsupported sites.
- Constructor-array assertions are derived from verified local module metadata:
  the selected main/subsdk0/sdk have 9,783/0/96 entries. These are local
  observations for the selected build, not hardcoded port constants.
- The loader's old constructor-flag decoder assumed a prologue without PACIBSP.
  The original extension handles both prologues with bounded reads and checks
  that the complete flag fits in module data. Thirty synthetic native checks and
  all three local module prologues pass. This does not execute constructors.
- Return projection, acquire loads, half-vector negation and byte-vector dot
  products have separate validation, documented in `CPU_COMPATIBILITY.md`.

## Reproducing the host compilation

Prepare and generate a module first so its authoritative layout exists. Then:

```text
python run_builder.py --runtime build/prepared-ID --toolchain PATH_TO_UCRT64_BIN
python tools/check_constructor.py --compiler PATH_TO_CLANG_EXE --prepared build/prepared-ID
python tools/check_dot_product.py --compiler PATH_TO_CLANG_EXE
python tools/check_port_chunks.py --prepared build/prepared-ID --module main --compiler PATH_TO_CLANG_EXE
```

The host command records compiler identity, layout hash, per-object hashes and
failures in `build/windows-runtime/report.json`, with individual compiler logs.
It uses the explicit toolchain directory on subprocess PATH; it does not depend
on a system-wide MSYS2 installation or launch an existing game. Installation-
specific sources and final executable resources remain separate from the archive.

## Remaining delivery gates

Local integration status (2026-11-15): all three modules generate without
unsupported instructions and the experimental executable links 670 objects.
The launcher still stops short of offering this as a verified independent build.
The game window now uses the DekuForge title, application identity and project icon.

An isolated run reaches the title sequence with an original asynchronous dav1d
AV1 adapter and NVN2 compute constant/resource-table support. A 50-second run
presented over 1,600 frames; this is not a playability or visual-quality pass.
The owner reports a pixelated title and missing background movie. Texture-table
bindings have subsequently been extended, but correct movie rendering remains
unverified. The frame viewer hit its output limit, so image pixel statistics are
only evidence that the captured frame is not uniformly black, not a visual review.

A copy of the owner's existing save now passes the runtime's working-copy setup.
The original save remains untouched. The initial world-load failure was an
unimplemented `nvnCommandBufferDrawMeshTasks` (exit 70 at main+0x273694).
Direct and indirect mesh commands now have a Vulkan execution path. Native tests use
`tools/test_native_game.py`, its optional owned input script and frame capture;
they explicitly keep `playability_verified` false.

Task/mesh work in progress: the isolated world-load failure was reproduced again
with exit 70 after 17.52 seconds. The shader compiler now includes the permitted
stage-memory, uniform bit-reverse and output-payload-read extensions. Twelve real
task/mesh kernels pass SPIR-V validation; their native Vulkan task/mesh wrappers
also pass Vulkan 1.2 validation. The standalone shader service was checked with
one real task and one real mesh request, including the native wrapper worker.
The RTX 2080 reports task/mesh support, 256 output vertices/primitives, 28 KiB mesh
shared memory and 16 KiB task payload. These checks do not execute a world draw.
The composed runtime now enables mesh features, builds task/mesh/fragment
pipelines, and forwards direct draws. Indirect draws copy the GPU-produced
count into a Vulkan XYZ command and preserve the first index in GPU memory,
read by the shader through a buffer device address. Neither value is sampled
prematurely on the CPU. Both updated wrapper stages pass SPIR-V validation.
World-load tests also exposed missing geometry-mode and shading-rate entry
points. Geometry is selected by each draw's pipeline; shading rates use the
full-pixel-quality fallback. Descriptor banks and actual world rendering still
need validation. The owner reports severely pixelated, unreadable text; this
is an unresolved rendering defect, not acceptable visual quality.
`tools/mesh_shader_worker.py` is a local development bridge; its tool paths are
recorded in the ignored build output, not a portable distribution contract.

Launcher management validation: 62 Python tests pass; the native launcher renders
40 views across five languages with one window and verified Windows icons. Save
imports retain the destination backup, reject unsafe archives and inherit the
profile directory's Windows ACL. Public release checks and channel selection
work; automatic installation, rollback and cache cleanup are not implemented.
The synthetic native compute-bank test covers dispatch dimensions, inline data,
buffer boundaries, texture/image slots and isolation from older shader stages.
It now also checks the task/mesh storage tables, including the final slot beyond
the legacy 2 KiB constant bank. `tools/check_shader_interfaces.py` verifies that
arrayed fragment inputs consume their complete location range.

Development shader preparation is available through
`tools/prepare_game_shaders.py --romfs build/game-input/romfs --output build/windows-game`.
It inventories local NVN2 packages and writes native seed records in the owned
build, then runs the native shader preparation mode. The tested inventory has
19,207 unique shaders, including 3 task and 9 mesh stages. A ten-shader pilot
translated and warmed all ten successfully. Full preparation and gameplay remain
validation gates; graphics combinations still need recorded pipeline keys, and
the launcher must not advertise this route as complete yet.

An isolated run passed the earlier play-report completion crash and captured
`build/windows-game/test-screen-before-mesh-bank.png`. It still encountered
shader validation errors and long pipeline stalls. That capture has **not** been
visually verified as sharp or playable. `tools/measure_game_frames.py` measures
explicit presentation-frame ranges, includes stalls and requires 120 samples;
it does not infer that the scene is gameplay. No verified gameplay FPS is available.

The latest runtime work adds physical-pointer shader address maps, a device-local
GPU write log with host readback, and task/mesh constant-buffer tables. The map
snapshot now holds its pool read lock across range resolution, GPU-address lookup
and generation capture. A separate later lookup previously raced with pool
changes during world loading. Its native test covers overlaps, virtual-page holes,
lock ownership and address snapshots before and after a backing change. Readback barriers and copies
all go through the command recorder, avoiding concurrent command-pool access.
Indirect compute dimensions follow the NVN2 layout, and sampled texture views
honour their requested format. Raw-global validation currently requires explicit
`--raw-global-memory` (imported memory); default mirrored memory is not supported
by that path yet.

Cache round-trip fixes align the pipeline-key and prepared-shader readers with
the headers their writers actually emit. Previously both rejected their own
files at the next boot. The isolated boot now discovers 19,569 prepared/recorded
variants and translates missing entries before guest execution. Completion,
pipeline reuse on a subsequent boot and gameplay are checked independently.
The isolated run with compiler `6d54554b0e75f866` translated all 19,569 inputs
with zero failures, then built all 184 recorded pipelines with zero failures
before guest execution (294.9 seconds combined). This is preparation evidence,
not a successful gameplay test.

Sampled texture metadata now distinguishes float, unsigned integer and signed
integer formats. Three synthetic variants pass SPIR-V validation with matching
image scalar types; runtime validation remains necessary. The NVN2 constant-bank
binding also now publishes its allocation to the indirect-dispatch copy path.
`tools/check_indirect_constants.py` exercises the composed native function and
checks that GPU dimensions target the bound allocation, leaving earlier dispatch
allocations and task-stage bindings isolated.

The next unchanged-compiler boot reused the shader cache without translating any
entries and prepared 203 recorded pipelines in 725 ms. Integer-sampled texture
validation errors no longer appeared in the subsequent world-load trace.
Zero-valued clears now also initialize integer textures when the guest calls its
float clear entry point. Typed shadow arrays use depth stand-ins for unrelated
colour slots, instead of invalid colour descriptors.

NVN2 public stage numbers 6/7 now map to internal task/mesh slots 3/4 when commands
record buffer and texture bindings, including deferred handles. The earlier
trace explicitly logged stage-6 handle binds being dropped, and buffer binds
were silently ignored by the same six-stage bound. `tools/check_stage_bindings.py`
exercises the composed command helpers with synthetic records. The corresponding
in-game test passed the former failing draw and completed a later pass containing
119 draws. It then lost the device in a different mesh pass (input ID beginning
`d9f364976029a0cc`). This remains a failed gameplay test.
For targeted diagnosis, `tools/test_native_game.py --gpu-validation-shader ID`
selectively instruments that shader through the local Vulkan validation layer.
It implies combined pipelines to avoid the observed independent-layout crash in
the validation layer. Instrumented timings are not performance results.

World-load validation still reports missing mesh outputs; the typed-shadow
descriptor errors did not recur after the depth-stand-in fix. Earlier runs repeatedly lost the Vulkan device at a specific
mesh draw. Shader patch 0031 makes the shared-word compare/exchange loop's initial
read atomic; a later run presented multiple world frames, but shader stalls
exhausted the test timeout, and another run crashed inside the validation layer.
Neither is a completed playability test. A captured loading
frame is black, not evidence of readable gameplay. Short 60 FPS loading intervals
and approximately 15 FPS earlier intervals must not be reported as gameplay FPS.
The image viewer's session output limit also prevents visual inspection here.

The synchronous recorder comparison (`--no-recorder`) still lost the device in
the same mesh pass. Selective GPU-assisted mesh validation after the atomic
address-map fix also ended in device loss followed by a validation-layer access
violation, without identifying a shader access error. Neither diagnostic is a
successful gameplay test. `--trace-mesh-counts` optionally copies indirect draw
records to an isolated diagnostic buffer and prints its last entries after
device loss; these snapshots are diagnostic only and do not alter draw counts.
The captured last sixteen records had workgroup counts from 0 to 54, not an
obviously excessive indirect launch; the same mesh pass still lost the device.

Shader compiler `22c1964f1b4e6706` removes unused SPIR-V interface variables left
by the mesh GLSL round trip, then rejects any remaining descriptor absent from
resource reflection. The cache audit found 19 such declaration mismatches among
333 task/mesh modules. All 19 cleaned copies passed SPIR-V validation; the
synthetic `tools/check_mesh_resources.py` fixture also confirms that live read
and write buffers survive cleanup. The subsequent full preparation translated
19,584 variants with zero failures and built all 383 recorded pipelines. That
first preparation took 390.5 seconds, including 101.1 seconds in pipeline creation.
This preparation evidence does not establish playability or rendering quality.

The subsequent instrumented native run stopped at a concrete task-output error:
404,275,200 emitted mesh groups versus the device limit of 4,194,304. Earlier
completed task emissions reached 32 groups. The new check suppresses the invalid
launch and reports it after GPU completion instead of letting it reset the device.
Primitive counts and vertex indices are checked through the same per-submission
feedback buffer. This is an explicit failed test, not a rendering workaround.

A control-section audit then identified underallocated payloads in 17 of 51
unique task/mesh controls: byte 0x5a contains flags, byte 0x5b counts 256-byte data
units, and task payloads include an additional 32-byte header. The parser now
keeps these separate, including the minimum data allocation for a zero encoded
size. Synthetic tests cover flag independence, the header, and matching task/mesh
sizes. The follow-up run still failed: shader `0fef5f51` emitted 135,745,536
groups, so payload sizing alone did not resolve the crash.

That task shader exposed a separate control-flow error in the Ampere translator:
the final predicated instruction could branch directly to the next block and
skip commits of earlier, unconditional deferred register writes. Patch 0033 keeps
the predicate join inside the block so both paths execute those commits.
`tools/check_shader_scoreboards.py` builds eight synthetic instruction streams
and checks the translated stores against independent population counts. All
eight pass with the patch; the preceding compiler demonstrably keeps 5 instead
of the correct population count 2 on the inactive path. This is a compiler
regression result. The following in-game run passed the previous fault, kept
task emissions at 32 groups and drew frames through 1909. It then stopped in
the SDK's nonlocal return to `main+0x1661690`, a continuation inside a function
that the dispatch table intentionally does not register.

The Windows continuation extension captures the translated caller through x64
unwind metadata and restores it for guest `longjmp`, along with guest ABI
registers, stack and host-call tracking depth. It rejects unknown buffers and
cross-thread or cross-stack destinations. The optimized native fixture in
`tools/check_guest_continuations.py` passes 100 nested/repeated returns, including
the zero-to-one return convention and preservation of vector upper halves.
The next isolated game run passed the previous font-rendering failure and
continued through frame 3356 without a fatal error; it was then stopped by the
test operator. This implementation is Windows-specific, not Linux or iOS.

The frame-2400 screenshot still has an entirely black central region, with
nonblack content around the edges. OCR finds no readable text. Frames 2500–3300
measure 13.23 average presentation FPS across 801 samples, including a 30.024
second stall; median interval is 37.662 ms. These are incomplete-render
diagnostics, not verified gameplay FPS, image-quality or playability evidence.

Vulkan validation identified mismatched primitive-rate mesh/fragment varyings.
The runtime now transfers the mesh output decorations to matching fragment
inputs, upgrading legacy SPIR-V to 1.4 and expanding its entry interface for
global variables. The native synthetic fixture validates this conversion and
its idempotence. Two point-mesh pairs needed point-sprite coordinates at location
5, which their fragment programs actively read. The point adapter supplies
`vec4(gl_PointCoord, 0, 1)` through private inputs, including scalar component
accesses. Synthetic modules and the recorded local fragment shader validate.
All 504 recorded pipelines subsequently built with zero Vulkan validation
errors during preparation. The subsequent ordinary run still captured a black
central image. Optional mesh-output
telemetry now samples primitive counts and positions after submission completion
to distinguish missing geometry from later image-composition errors: the run
reported 99–102 primitives per batch and finite position samples. A further
test with combined pipelines and synchronous pipeline creation still showed
black world output. Its frames 2500–3300 measured 26.62 average presentation FPS,
23.47 FPS for the slowest one percent, and 44.817 ms maximum interval (801 samples).
The earlier 30-second stall was a pipeline wait that skipped its draw after
timeout. Neither performance result verifies gameplay while the world is black.

A per-pass render dump subsequently showed a coloured scene before post-processing,
then black compute output before the HUD. The dump adapter now resolves NVN2
compute image and texture slots through the same mapping as descriptor binding,
so it captures storage outputs instead of incorrectly reporting missing handles.
The captured RG16UI image was written by a float-typed shader: host image-format
answers were absent, compute image-table offsets were not mapped, and formatted
surface instructions dropped the constant-bank index. Patch 0034 and the host
adapter preserve those formats and declare extended storage-image capabilities.
`tools/check_shader_image_formats.py` validates unsigned, signed and float stores,
integer bit preservation and queried image slots using synthetic instructions.

The pinned texture allocator also relied on NVN1's IMAGE flag. The NVN2 adapter
now permits storage use for supported single-sample colour images at allocation,
so later compute binds can use their real output. These changes require a new
in-game capture; passing compiler fixtures does not establish image quality.

The next capture restored compute output but revealed invalid colours: the
scene sampler followed the live R11G11B10 target at its address while losing its
RGB9E5 descriptor interpretation. The adapter preserves that sampling view and
restricts its usage to sampling. This removed NaNs at the network output, but
the translated network still produced a nearly white scene. Native tensor
reconstruction therefore remains unverified.

A separate host-owned cubic reconstruction shader now handles only the tensor
route with an RGB9E5 scene input and a larger, matching-aspect R11G11B10 output.
It bounds interpolation ringing and converts the square-root encoded input back
to linear light. Other compute shaders retain their normal execution. This is
spatial reconstruction, not DLSS or a claim of correct native network execution;
`DEKUFORGE_NATIVE_SCENE_NETWORK=1` retains that route for diagnosis. Its GLSL is
compiled and SPIR-V-validated before host linking. An isolated frame-2400 dump
now contains finite, varied scene colours through final presentation; the output
image is saved as `build/windows-game/test-portable-scene-frame2400.png`. The
frame viewer is unavailable, so these numeric checks do not verify sharpness.
Frames 2500–3300 measured 26.74 average presentation FPS and 23.41 FPS for the
slowest one percent (801 samples over 29.960 seconds). This is below parity.
An ordinary-defaults repeat reached frame 3300 without a fatal error and measured
26.13 FPS average / 22.98 FPS for the slowest one percent over the same interval.
Fresh launches now default to imported memory, combined pipelines and waiting for
required draws; explicit configuration overrides still take precedence.

The title movie's final compute output required a compatible UNORM storage view
of its sRGB image. Extended image usage and restricted sRGB view usage restore
that output. A title run reported no Vulkan validation errors; a later frame-1000
capture contains varied colours, but neither movie quality nor motion is visually
confirmed. Movie GPU time remains around 63 ms.

`DEKUFORGE_PROFILE_FRAME` enables bounded per-pass GPU timestamps for one frame.
The isolated frame-2500 profile measured 36.33 ms across 291 passes. The largest
render pass took 7.69 ms; two compute passes took 6.52 and 4.96 ms. A small-counter
device-memory staging experiment is disabled by default and requires
`DEKUFORGE_STAGE_COMPUTE_COUNTERS=1`; it is not a validated performance fix.
With that experiment and the command recorder disabled, frames 2500–3300
measured 33.83 average presentation FPS and 28.69 FPS for the slowest one percent
(801 samples, 23.674 seconds). At the profiled frame, the two compute passes fell
to 2.92 and 0.04 ms. This does not establish visual equivalence. The synthetic
`tools/check_compute_counter_stage.py` fixture checks copy-back, deferred release,
overlapping descriptor rejection, raw-global rejection and allocation fallback.
Whole-game validation still encounters an access violation inside the validation
DLL's push-template path; the opt-in `DEKUFORGE_NO_PUSH_DESCRIPTORS=1` diagnostic
route allows testing ordinary descriptor sets separately. Its first run timed
out during cache preparation and therefore did not validate gameplay. Disabling
descriptor templates alone also crashed inside the validation DLL during title
rendering, before the counter optimization was used. No clean whole-game
validation run is claimed. Both diagnostic paths leave the normal route unchanged.

The renderer capability check read only an explicit GPL setting and ignored its
new default, leaving independent layouts active while library builds were off.
It now uses the effective boolean setting. A subsequent edge-adaptive reconstruction
test reached frame 2400 with core Vulkan validation and no reported validation
errors or fatal error. This was a bounded run, not a successful clean game exit.
The optional reconstruction comparison uses `DEKUFORGE_SCENE_EASU=1` and the
engine's unmodified AMD FSR 1 headers; the HUD is composed afterwards.

User-supplied screenshots then established severe texture corruption, not merely
soft reconstruction: repeated block patterns in HUD images, magenta stripes and
holes in the world. The independent host menu text remains legible. The synthetic
ASTC probe passed 30,212 blocks / 1,740,602 texels against the CPU decoder. The
upload still used X1 byte ordering within each 512-byte GOB, whereas this NVN2
input exchanges the inner x[4] and y[1] address bits. The workspace adapter now
applies that permutation to both addressing and the optimized copy segments.
`tools/check_nvn2_texture_layout.py` checks the complete byte permutation and 672
geometry/padding round trips against a coordinate-bit oracle. The owner confirmed
that HUD and title/menu textures now render correctly. World surfaces still
disappear/flicker and the intro movie remains pixelated. The corrected-layout
test measured 27.82 average presentation FPS over frames 2500–3300, with 21.26
FPS for the slowest one percent. This remains a defective-image measurement,
not a playable-build result. The texture probe fixture now retains its pool's
CPU access flags, matching actual texture initialization. The corrected native
probe passed 343 deswizzle cases, 186,758 ASTC blocks and 41 GPU checks.

Compute image-store bindings now mark their images GPU-owned, as attachment and
transfer writes already did. Previously only their fence was recorded; stale
CPU storage could replace compute output and aliases could miss it. Read-only
storage-image bindings retain their original ownership. A native regression
case checks both ownership paths and reads a GPU-written colour back while the
CPU backing still contains unrelated texels. The expanded probe passes 45 GPU
checks with zero validation errors. Whole-game visual equivalence is pending.

Windows now paints a forest-green startup screen with measured pipeline and
compute-shader counts before guest execution. Shader-cache loading has an
indeterminate label. Progress does not invent an overall percentage. The native
display is limited to Windows; other platforms use a no-op progress hook until
their window backend is implemented. A bounded test with the startup display
reached frame 2200, captured a world frame and closed normally (exit 0), but this
does not establish correct rendering. Fullscreen presentation was confirmed at
2560x1440 in the preceding validation run, which reached frame 2204 without a
reported fatal error before the test timeout.

The owner's `NX2Navi/Play/ocarina.exe` was also tested using its existing settings
and a separate save copy. Its log confirms real DLSS processing, 1280x720 scene
reconstruction to 1920x1080, and 2560x1440 presentation. The movie interval measured
60 FPS; a later world interval (frames 3500–4300) measured 36.32 FPS average,
16.03 FPS for the slowest one percent, including periodic screenshot capture.
The owner supplied a clear world screenshot with a 35 FPS overlay. This is the
reference, not proof that DekuForge has reached equivalent quality or stability.

Boot now joins the known compute-preparation workers before entering guest code,
in addition to warming the recorded complete pipeline combinations. Pipeline
combinations first encountered during play still need their initial compilation.

Complete remaining game-specific
host imports, boot checkpoints, NVN2 object layouts and shader translation, then
link against the independently assembled RomFS. Boot, rendering, audio, input,
save/load and repeatable play sessions must pass in a separate installation.
The older baseline's boot checkpoints and other title-specific runtime constants
are still unvalidated; adapting constructor metadata does not establish a full
port. No FPS, frame-time or memory parity claims are supported yet.

The working installation and saves remain separate throughout this work.

### Half arithmetic investigation

The Ampere half-pair translator treated operand swizzle 1 as the high 16-bit
half, instead of broadcasting the operand's 32-bit float. Uniform operands also
ignored their half swizzle. `mesh-0035.patch` corrects both paths and preserves
MUFU's separate half-selection interpretation. The underlying instruction
semantics are described in the upstream translator's
[half-pair investigation](https://github.com/seedds/nxnative/blob/main/docs/reference/shaders.md#half-pair-swizzle-on-a-constant-and-f32).
Exact hardware rounding of non-representable scalar inputs remains unverified.

`tools/check_shader_half_swizzle.py` uses synthetic instructions. The old
compiler emits 1.9375 for a scalar 1.5 operand; the corrected compiler emits 1.5
in both lanes. Low/high uniform broadcasts and SPIR-V validation also pass.
Existing deferred-write and typed-image-store translator checks still pass.
The local game shader cache must be rebuilt under the new compiler identity;
these isolated checks alone do not establish that movie or world corruption is
fixed. The last pre-correction world interval measured 27.02 average FPS and
23.69 FPS for the slowest one percent over 801 frames at fullscreen presentation.

`mesh-0036.patch` snapshots a deferred instruction's issue-time predicate and
commits the result only for active lanes. A later guarded pending write also
preserves an earlier pending result that may still win. The extended synthetic
scoreboard test changes the predicate before the wait and tests complementary
pending writes. Before the correction a skipped operation restores stale 42
over a newer 123; afterwards all twelve cases produce their independent expected
values. Scalar/uniform half and typed-image checks still pass. The upstream
[deferred-write investigation](https://github.com/seedds/nxnative/blob/main/docs/reference/shaders.md#a-deferred-write-under-a-false-guard)
describes the instruction-level issue; DekuForge's whole-game retest is separate.
