"""Run an isolated, bounded development test of the independently linked executable."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("loader", "boot", "play"), default="loader")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--trace", help="Override runtime trace categories for diagnosis")
    parser.add_argument("--no-descriptor-templates", action="store_true", help="Use explicit descriptor writes for validation diagnosis")
    parser.add_argument("--fullscreen", action="store_true", help="Match the monitor's fullscreen presentation size")
    parser.add_argument("--validation", action="store_true", help="Enable locally installed Vulkan validation")
    parser.add_argument("--gpu-validation", action="store_true", help="Instrument GPU accesses; implies validation and combined pipelines")
    parser.add_argument("--gpu-validation-shader", help="Scope GPU instrumentation to one 64-character shader input ID")
    parser.add_argument("--combined-pipelines", action="store_true", help="Diagnose shader interfaces without pipeline libraries")
    parser.add_argument("--synchronous-pipelines", action="store_true", help="Build newly encountered pipelines on the replay thread")
    parser.add_argument("--no-recorder", action="store_true", help="Record Vulkan commands synchronously for diagnosis")
    parser.add_argument("--no-uniform-snapshot", action="store_true", help="Diagnose live uniform reads versus submit-time snapshots")
    parser.add_argument("--trace-mesh-counts", action="store_true", help="Copy indirect draw records for a device-loss report")
    parser.add_argument("--trace-mesh-output", action="store_true", help="Read bounded primitive/position samples after GPU completion")
    parser.add_argument("--raw-global-memory", action="store_true", help="Use coherent imported pools for raw-global shader validation")
    parser.add_argument("--capture-frame", type=int, help="Capture one presented test frame in the owned output")
    parser.add_argument("--dump-frame", type=int, help="Capture intermediate render targets for one isolated frame")
    parser.add_argument("--profile-frame", type=int, help="Measure GPU pass times in one isolated frame")
    parser.add_argument("--input-script", type=Path, help="Owned local button script for the isolated profile")
    args = parser.parse_args()
    if args.gpu_validation_shader:
        if len(args.gpu_validation_shader) != 64 or any(c not in "0123456789abcdef" for c in args.gpu_validation_shader):
            parser.error("GPU validation shader ID must be 64 lowercase hexadecimal characters")
        args.gpu_validation = True
    if args.gpu_validation:
        args.validation = args.combined_pipelines = True
    folder = ROOT / "build" / "windows-game"
    executable = folder / "DekuForgeGame.exe"
    if executable.resolve() != executable or not (folder / ".dekuforge-native").is_file():
        raise ValueError("Use only the owned experimental game build")
    environment = {key: value for key, value in os.environ.items() if not key.startswith("NX2NAVI_")}
    environment["NX2NAVI_GPU"] = "vulkan" if args.mode == "play" else "null"
    environment["NX2NAVI_TRACE"] = "host,ipc" if args.mode != "play" else "gfx,present"
    if args.trace:
        environment["NX2NAVI_TRACE"] = args.trace
    if args.no_descriptor_templates:
        environment["NX2NAVI_DESC_TEMPLATE"] = "0"
    if args.fullscreen:
        environment["NX2NAVI_FULLSCREEN"] = "1"
    if args.combined_pipelines:
        environment["NX2NAVI_GPL"] = "0"
    if args.synchronous_pipelines:
        environment["NX2NAVI_PIPE_WAIT"] = "draw"
        environment["NX2NAVI_PIPE_SKIP"] = "strict"
    if args.no_recorder:
        environment["NX2NAVI_VK_RECORDER"] = "0"
    if args.no_uniform_snapshot:
        environment["NX2NAVI_UBO_SNAPSHOT"] = "0"
    if args.trace_mesh_counts:
        environment["DEKUFORGE_TRACE_MESH_COUNTS"] = "1"
    if args.trace_mesh_output:
        environment["DEKUFORGE_TRACE_MESH_OUTPUT"] = "1"
    if args.raw_global_memory:
        environment["NX2NAVI_MEMORY"] = "import"
    if args.profile_frame is not None:
        if args.mode != "play" or args.profile_frame < 1:
            parser.error("GPU pass timing requires play mode and a positive frame")
        environment["DEKUFORGE_PROFILE_FRAME"] = str(args.profile_frame)
    if args.validation:
        shader_tools = ROOT / "local/build-tools/shaders/ucrt64"
        environment["NX2NAVI_VK_VALIDATION"] = "1"
        if args.gpu_validation:
            environment["VK_LAYER_GPUAV_ENABLE"] = "1"
            # Core validation is covered by --validation runs. Avoid duplicating
            # it alongside the much heavier GPU instrumentation.
            environment["VK_LAYER_VALIDATE_CORE"] = "0"
            environment["NX2NAVI_LIB_PREBUILD"] = "0"
            if args.gpu_validation_shader:
                environment["VK_LAYER_GPUAV_SELECT_INSTRUMENTED_SHADERS"] = "1"
                environment["DEKUFORGE_GPU_VALIDATION_SHADER"] = args.gpu_validation_shader
        environment["VK_LAYER_PATH"] = str(shader_tools / "bin")
        environment["PATH"] = str(shader_tools / "bin") + os.pathsep + environment.get("PATH", "")
        mesh_config = folder / "DekuForgeMesh.json"
        if mesh_config.is_file():
            toolchain = json.loads(mesh_config.read_text(encoding="utf-8"))["toolchain"]
            environment["PATH"] = str(shader_tools / "bin") + os.pathsep + toolchain + os.pathsep + environment["PATH"]
    if args.input_script:
        script = args.input_script.resolve()
        if not script.is_file() or not script.is_relative_to((ROOT / "local").resolve()):
            parser.error("Input scripts must be existing files inside local/")
        environment["NX2NAVI_INPUT_SCRIPT"] = str(script)
    if args.capture_frame is not None:
        if args.mode != "play" or args.capture_frame < 1:
            parser.error("Frame capture requires play mode and a positive frame number")
        capture = folder / "test-screen.png"
        capture.unlink(missing_ok=True)
        environment["DEKUFORGE_TEST_SCREEN"] = str(capture)
        environment["DEKUFORGE_TEST_SCREEN_FRAME"] = str(args.capture_frame)
    dump_folder = None
    if args.dump_frame is not None:
        if args.mode != "play" or args.dump_frame < 1:
            parser.error("Render-target capture requires play mode and a positive frame")
        dump_folder = folder / f"render-dump-{args.dump_frame}-{time.time_ns()}"
        dump_folder.mkdir()
        environment["NX2NAVI_DUMP"] = str(args.dump_frame)
        environment["NX2NAVI_DUMP_DIR"] = str(dump_folder)
        environment["NX2NAVI_DUMP_SKIP_RUNS"] = "1"
    command = [str(executable), *({"loader": ["--probe-loader"], "boot": ["--boot"], "play": []}[args.mode])]
    started = time.monotonic()
    log = folder / ("test-" + args.mode + ".log")
    timed_out = False
    fatal_error = False
    with log.open("w", encoding="utf-8") as stream:
        with subprocess.Popen(command, cwd=folder, env=environment, stdout=stream, stderr=subprocess.STDOUT,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) as process:
            # A native fatal-error dialog can leave the failed test alive. Detect
            # the explicit fatal line and terminate only this owned child.
            with log.open("r", encoding="utf-8", errors="replace") as reader:
                while process.poll() is None:
                    fatal_error |= any(line.startswith("FATAL:") for line in reader.readlines())
                    timed_out = time.monotonic() - started >= args.timeout
                    if fatal_error or timed_out:
                        process.kill()
                        break
                    time.sleep(0.5)
            code = process.wait()
    report = {"mode": args.mode, "exit_code": code, "timed_out": timed_out, "fatal_error": fatal_error,
              "elapsed": round(time.monotonic() - started, 2), "log": str(log.relative_to(ROOT)),
              "validation": args.validation, "gpu_validation": args.gpu_validation,
              "gpu_validation_shader": args.gpu_validation_shader,
              "memory_mode": "import" if args.raw_global_memory else "default",
              "experimental_counter_staging": environment.get("DEKUFORGE_STAGE_COMPUTE_COUNTERS") == "1",
              "experimental_counter_max_bytes": environment.get("DEKUFORGE_STAGE_COMPUTE_COUNTER_MAX", "64"),
              "experimental_counter_raw_reads": environment.get("DEKUFORGE_STAGE_COMPUTE_RAW_READS") == "1",
              "descriptor_templates_disabled": args.no_descriptor_templates,
              "diagnostic_depth_equal": environment.get("DEKUFORGE_DIAGNOSTIC_DEPTH_EQUAL"),
              "fullscreen_requested": args.fullscreen,
              "scene_reconstruction": "edge-adaptive" if environment.get("DEKUFORGE_SCENE_EASU") == "1" else "cubic",
              "portable_movie_reconstruction": environment.get("DEKUFORGE_PORTABLE_MOVIES") != "0",
              "portable_tensor_scratch_skip": environment.get("DEKUFORGE_PORTABLE_MOVIES") != "0" and environment.get("DEKUFORGE_SKIP_TENSOR_SCRATCH") != "0",
              "combined_pipelines": args.combined_pipelines,
              "synchronous_pipelines": args.synchronous_pipelines,
              "recorder_disabled": args.no_recorder,
              "uniform_snapshot_disabled": args.no_uniform_snapshot,
              "mesh_count_diagnostics": args.trace_mesh_counts,
              "mesh_output_diagnostics": args.trace_mesh_output,
              "capture_frame_requested": args.capture_frame,
              "profile_frame_requested": args.profile_frame,
              "render_dump": str(dump_folder.relative_to(ROOT)) if dump_folder else None,
              "screenshot": str(capture.relative_to(ROOT)) if args.capture_frame is not None and capture.is_file() else None,
              "playability_verified": False}
    (folder / ("test-" + args.mode + ".json")).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    print(log.read_text(encoding="utf-8", errors="replace")[-10000:])
    return 1 if timed_out or fatal_error or code else 0


if __name__ == "__main__":
    raise SystemExit(main())
