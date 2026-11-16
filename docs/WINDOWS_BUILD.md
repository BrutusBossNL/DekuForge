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

Windows now paints a forest-green startup screen with measured shader, pipeline
and compute-shader counts before guest execution. Cache discovery remains
indeterminate until its inventory is known. Progress does not invent an overall percentage. The native
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

The combined compiler translated 19,780 required inputs without failures on the
first cold-cache boot. All 526 recorded pipelines built successfully. Translation
took 292 seconds and first driver compilation took another 149 seconds, with a
sampled process working set around 20 GB during compilation. This is a cold-cache
cost, not gameplay memory or frame timing. Native-window screenshots and Windows
OCR independently confirmed the displayed pipeline and compute counts; this
checks the loading UI, not the correctness of the rendered game world.

With that cache populated, the next test reached guest execution in 2.1 seconds
and exited normally. Frames 2500–3300 measured 27.07 FPS average and 23.62 FPS
for the slowest one percent. The movie still took about 63–66 ms per frame.
The following core-validation run reached the world capture at frame 2200 with
no reported validation errors; it did report unused fragment colour outputs in
depth-only draws. Its shutdown exceeded the 210-second test deadline and was
terminated by the harness, so it is not a clean-exit result. Validation timing
is not comparable to the normal performance run. Local image output remains
unavailable in the agent session; captures are saved, not visually approved.

### Multi-result optimizer liveness

`mesh-0037.patch` preserves a producer's input uses while any of its results is
still live. Previously, removing a consumer of one dead image-read channel could
strip the coordinate's use even though another channel was still consumed.
`tools/check_shader_optimizer.py` constructs synthetic IR graphs and exercises
the actual compiler assembly: the old compiler loses the coordinate use, the
corrected compiler preserves it. Fully dead producers still release their input
uses, and side-effecting producers keep theirs. Deferred-write and half-swizzle
regressions also pass. This corrects the independently reproduced issue described
in the upstream [multi-output optimization investigation](https://github.com/seedds/nxnative/blob/main/docs/reference/shaders.md#dead-code-removal-dropped-a-coordinate-of-a-multi-output-instruction).
Its effect on the game picture remains subject to an isolated retest.

### Floating-point reductions

The translator omitted F32 atomic additions, emitting no update for the
synthetic global-reduction fixture. `mesh-0038.patch` implements the operation
with integer compare-and-swap over the original float bits. Retry comparison is
bitwise, including for NaN. Global inputs/results flush subnormals to signed
zero; shared-memory arithmetic retains them, following
[NVIDIA's atomic-add semantics](https://docs.nvidia.com/cuda/archive/12.8.1/parallel-thread-execution/index.html#data-movement-and-conversion-instructions-atom).

`tools/check_shader_float_atomics.py` validates SPIR-V for reductions and returned
global/shared atomics. Its optional assembly check interprets the emitted IR
against an independent memory model: ordinary addition, forced contention,
signed flush-to-zero, underflow, shared subnormals and NaN termination all pass.
The old translator fails the missing-update check. These are compiler tests;
they do not replace GPU execution or prove corrected in-game exposure. The
upstream [float-reduction investigation](https://github.com/seedds/nxnative/blob/main/docs/reference/shaders.md#float-atomics-in-storage-memory)
identifies these operations in scene exposure analysis. No native float-atomic
performance optimization is enabled by this correction.

The isolated optimizer-only game run completed normally at 27.25 average FPS
and 23.95 FPS for the slowest one percent over frames 2500–3300. Intro timing
remained around 67–69 ms per frame. Its capture is not visually verified.

The native mesh wrapper now declares position invariant, matching the existing
vertex-stage contract. Depth-only and colour programs can depend on matching
positions. `tools/check_mesh_resources.py` compiles the synthetic wrapper,
validates SPIR-V and verifies the invariant decoration on the actual position
member. This closes an interface gap; the combined in-game retest is still
required before attributing the remaining flicker to it.

The combined float-atomic/invariant build completed its isolated world test
normally, but has a severe performance regression: frames 2201–2340 measured
5.29 FPS average (140 samples, including a 379 ms outlier). Correctly executing
the previously omitted operations is not yet fast enough. The cached restart
reached guest code in 2.27 seconds. With the existing 64-byte counter experiment,
a GPU profile at frame 2300 attributed 118.75 ms and 37.52 ms to two compute
dispatches; the largest measured render passage was 8.30 ms. The movie still
takes roughly 68 ms per frame. This build is not ready for use as a playable
replacement.

For diagnosis only, counter staging accepts
`DEKUFORGE_STAGE_COMPUTE_COUNTER_MAX` from 4 through 8192 bytes, in multiples of
four. It still requires `DEKUFORGE_STAGE_COMPUTE_COUNTERS=1`, defaults to 64
bytes, and retains the alias and ambiguous-buffer rejection checks.
The synthetic command-model test covers a 192-byte copy-back and invalid limits;
the game harness records the selected bound. This is not a default performance
fix or a claim of alias equivalence across different Vulkan buffers.

An additional `DEKUFORGE_STAGE_COMPUTE_RAW_READS=1` experiment permits a
read-only raw-address table. It creates a private table for the dispatch and
redirects every matching physical interval, including virtual aliases, to the
staged counter. Raw writes, overlapping descriptor ranges, indirect dispatches
and malformed or overflowing maps remain rejected. Synthetic tests cover map
splitting, alias resolution, failure fallback and successful descriptor updates.

The 4-KiB experiment completed normally at 15.64 average FPS. Resource inspection
identified the remaining exposure buffer as 4160 bytes. With the 8-KiB bound and
raw-read remapping, frames 2500–3300 measured 33.81 average FPS and 26.02 FPS for
the slowest one percent (801 samples, median 29.472 ms, maximum 51.329 ms).
The remaining expensive compute dispatch dropped from 36.13 ms to 0.30 ms in
the frame-2300 GPU profile. This run exited normally. The source compiler
identity was `3be8bb71dc1e9c81`; hardware and driver match the reference above.
The experiment remains opt-in, and its saved world capture has not been
visually verified. It does not fix the roughly 68-ms movie frames or establish
rendering parity. A Vulkan validation run is separate from these measurements.

The counter validation run reached gameplay and frame 2200 without reported
Vulkan validation errors. After the close request, rendering stopped but the
process did not exit before the 360-second harness deadline (362.41 seconds
including termination). This is a shutdown timeout, not a clean validation
pass. Normal runs of the same counter configuration exited successfully.

### Portable movie experiment

The default movie route replaces only a recognized final tensor movie
output: a 10-bit intermediate and a unique decoded RGBA8 source of matching
dimensions must be bound, and the output must be a single-sample RGBA8 image
with the same aspect ratio. Ambiguous inputs, scene HDR formats, unsupported
views and unrelated dispatches retain their normal execution. Reconstruction
uses bounded cubic sampling and preserves the video's existing display
encoding; it does not apply the scene network's square operation.
`DEKUFORGE_PORTABLE_MOVIES=0` restores native movie execution for diagnosis.
The earlier opt-in implementation was not active when the launcher started the
game normally; its test-only results did not describe that normal launch.

The new GLSL shader compiles and passes SPIR-V validation. In an actual frame
1000 capture, `tools/check_movie_capture.py` compared its GPU output against
an independent scalar CPU reconstruction at 1028 positions. The largest error
was 0.55 on an 8-bit channel, RMS 0.18. This proves agreement with the decoded
source, not visual correctness of that source or of later composition passes.
The movie-only experiment still took about 64 ms per frame; its subsequent
world run measured 34.12 average FPS and exited normally.

The portable route skips direct tensor
dispatches with no declared image output while portable movies are enabled.
Their buffer results are not consumed by the tested portable final image.
This now matches the reference renderer's default tensor bypass behavior.
`DEKUFORGE_SKIP_TENSOR_SCRATCH=0` restores intermediate execution for diagnosis;
other tensor workloads still require separate validation.
The measured intro interval, frames 500–900, reached 60.00 average FPS and
59.47 FPS for the slowest one percent. The same-frame GPU reconstruction still
matched the scalar reference (maximum 0.553, RMS 0.178 channel units).
The following world interval, frames 2500–3300, measured 33.35 average FPS and
27.10 FPS for the slowest one percent; the 112.60-second run exited normally.
All 63 project tests pass. Captures remain local and not visually approved;
counter staging remains opt-in. Movie reconstruction and tensor scratch skipping
are now renderer defaults, including direct executable and launcher starts.

The ordinary-start regression test uses neither movie override. Frames 500–900
and menu navigation at 1050–1600 both measured 60.00 average FPS, with a maximum
16.683 ms in the latter interval. The frame-1000 diagnostic render dump stalls
the game while copying all targets; it is excluded from navigation timing.
The default test exited normally after 68.06 seconds. These measurements do
not resolve the separately reported missing world surfaces and silhouettes.

### World visibility investigation

The world is not visually validated. The read-only EQUAL depth-test diagnostic
(`DEKUFORGE_DIAGNOSTIC_DEPTH_EQUAL=always`) exposes additional surfaces but
breaks occlusion and leaves incorrect materials. It is disabled by default and
is not a rendering fix. Disabling uniform snapshots with the test harness's
`--no-uniform-snapshot` option did not remove the white character silhouette.
Both experiments exited normally; neither establishes parity.

`DEKUFORGE_TRACE_MESH_FRAME=N` captures the first emitted vertex of nonempty mesh
workgroups during the selected frame. Each submission retains at most 2048
records (expanded from 512 after a truncated capture), with shader identifier,
workgroup, indirect first index, primitive count
and the exact four position bit patterns. Requested and captured counts expose
truncation. The buffer is read only after submission completion. This diagnostic
does not modify position values or depth tests and allocates the extra records
only on the selected frame. It is intended to investigate cross-pass position
agreement; matching isolated samples alone cannot validate full geometry.

The directional depth diagnostics (`lequal` and `gequal`) remain opt-in.
The measured white-pixel fraction in the character region was 18.05% with
normal depth, 16.63% with LEQUAL, and 0.25% with GEQUAL or ALWAYS. This is
evidence of a cross-pass depth discrepancy, not visual acceptance of either
override. The first 512-position trace contained no nonfinite values but
truncated 342 further samples. Its world interval measured 34.05 average FPS
with experimental counter staging; the process exited normally.

The mesh GLSL round trip was found to discard `NoContraction` decorations on
`GLSL.std.450 Fma`. A sampled world shader retained all 46 precise add/multiply
operations but lost the decoration on all 52 fused operations. The native
stage now restores this decoration to Fma results, preserving single-rounding
FFMA semantics. A synthetic precise-FMA shader reproduces the loss and checks
the repair, its idempotence, and SPIR-V validity. All 63 unit tests pass.
The in-game regression with ordinary depth tests remains a separate gate.

The FMA repair alone did not resolve the reported flicker: the user supplied a
new capture with missing rock surfaces and white character regions. Its 1004
position samples were finite and untruncated, with 185 exact position patterns
shared across different shaders. Viewport and depth-range tracing did not show
a mismatch between the scene's depth and colour passes.

A separate experiment retained conservative visibility decisions for reports
within one replayed frame. The white-pixel fraction in the fixed character
region fell from 13.15% to 0.53%, but that is not visual confirmation. The
temporary override has been replaced by an original replay counter ledger:
timestamp values and completed occlusion values belong to their report, not
to subsequently re-armed CPU memory. Serial numbers reject stale callbacks;
later buffer fills are merged before a deferred report writes guest memory.
The ledger is protected across replay/completion threads and reuses completed
old-frame entries without evicting pending reports. Synthetic native tests
cover completion, CPU re-arm isolation, partial fills, stale callbacks,
capacity exhaustion and 4096 address rotations.

The first ledger run exited cleanly after 135.61 seconds and retained a 0.58%
white-pixel fraction. Frames 2500–3300 measured 29.40 average FPS, 22.66 FPS for
the slowest one percent, with experimental counter staging enabled. All 63
unit tests pass. Visual acceptance and reference performance parity remain open.
The preceding raster/visibility diagnostics reached their harness deadlines;
they are not clean-shutdown evidence.

The bounded compute-counter staging path is now enabled by default, with an
8192-byte maximum and guarded raw-read remapping. Explicit environment values
of zero still disable staging or raw-read remapping for diagnosis. Overlap,
raw-write and unsupported-dispatch guards remain in force. Native regression
tests cover the new defaults as well as fallback and deferred copy-back.

A normal recorder-enabled run with BC3 texture decoding requested measured
29.33 average FPS and 25.20 FPS for the slowest one percent (frames 2500?3300).
The character-region white-pixel fraction was 0.58%. This run reached its
181.22-second harness deadline; it does not establish clean shutdown. BC3 did
not demonstrate a substantial speed gain and its default policy is unchanged.
These image statistics are diagnostic only: temporal flicker and complete
world rendering still require visual acceptance.

The subsequent ordinary-default run (recorder enabled, no compression override
or conditional-render diagnostic) exited normally after 104.08 seconds.
Frames 2500?3300 measured 29.64 average FPS and 25.59 FPS for the slowest one
percent. Its character-region white-pixel fraction was 0.56%. The local capture
is `build/windows-game/test-ledger-defaults-frame2200.png`; it remains visually
unapproved because the session image viewer cannot open additional images.
