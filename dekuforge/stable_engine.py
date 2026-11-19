"""Pinned 0.10.1 source backend for the DekuForge migration build."""
import hashlib
import io
import importlib.util
import json
import os
import re
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
from urllib.request import urlopen
from .core import ROOT

REVISION = "5ae55db41c7d11c4e997d2676019939a936e560b"
REFERENCE = ROOT.parent / "NX2Navi/Contribute/NX2navi-cheat-manager"
RELEASE_URL = "https://github.com/tangerineturtle1/NX2navi/releases/download/v0.10.1/NX2navi-app-0.10.1.zip"
RELEASE_SHA256 = "0aad51adec03196d2cb1a65dc6e697c0da2146cb1614b22105beab067151f0f7"
RELEASE_SIZE = 98116018
FRAMEGEN_FILES = (
    'nx2navi_dlssg.dll', 'sl.interposer.dll', 'sl.common.dll', 'sl.dlss_g.dll',
    'sl.pcl.dll', 'sl.reflex.dll', 'nvngx_dlssg.dll', 'dlssg-NOTICE.txt',
    'streamline-LICENSE.txt', 'nvidia-rtx-sdks-LICENSE.txt',
)
FSR_FILES = (
    'amd_fidelityfx_vk.dll', 'amd_fidelityfx_loader_vk.dll',
    'amd_fidelityfx_upscaler_vk.dll', 'amd_fidelityfx_framegeneration_vk.dll',
)
FSR_NOTICES = {
    'FidelityFX-SDK-LICENSE.txt': 'ffx_api',
    'FSR-SDK-LICENSE.txt': 'ffx_sdk',
}


def build_failure_message(returncode, detail=""):
    """Preserve an interrupted child status even when the builder exits with 1."""
    child = re.search(r"(?:exit status|exit code)\s+(-?\d+)", detail)
    status = int(child.group(1)) if child else returncode
    if status & 0xffffffff == 0xc000013a:
        return "build_interrupted"
    return "Stable engine build failed; see build log"


def source_manifest():
    record = json.loads(Path(__file__).with_name("stable_engine_source.json").read_text(encoding="utf-8"))
    if record["revision"] != REVISION:
        raise ValueError("Stable source manifest revision mismatch")
    return record["files"]


def stage_stable():
    output = ROOT / "build/engine-0.10.1"
    if output.resolve() != output:
        raise ValueError("Stable engine workspace must not be a link")
    marker = output / ".dekuforge-stable-engine"
    if output.exists() and not marker.is_file():
        raise ValueError("Stable engine workspace is not owned")
    output.mkdir(parents=True, exist_ok=True)
    marker.write_text(REVISION, encoding="utf-8")
    cache=ROOT / "local/build-tools" / ("engine-source-"+REVISION+".zip")
    cache_id=cache.with_suffix(".sha256")
    cached=cache.is_file() and cache_id.is_file() and cache.stat().st_size<=384*1024**2
    if cached:
        archive=cache.read_bytes()
        cached=hashlib.sha256(archive).hexdigest()==cache_id.read_text(encoding="ascii").strip()
    if cached:
        pass
    elif REFERENCE.is_dir():
        archive = subprocess.check_output(["git", "-c", "safe.directory=" + REFERENCE.as_posix(),
            "-C", str(REFERENCE), "archive", "--format=zip", REVISION])
    else:
        url = "https://api.github.com/repos/tangerineturtle1/NX2navi/zipball/" + REVISION
        with urlopen(url, timeout=90) as response:
            archive = response.read(384 * 1024 * 1024 + 1)
        if len(archive) > 384 * 1024 * 1024:
            raise ValueError("Stable source archive exceeds its size limit")
    expected = source_manifest()
    with zipfile.ZipFile(io.BytesIO(archive)) as package:
        prefix="" if set(package.namelist()) & expected.keys() else package.namelist()[0].split("/",1)[0]+"/"
    hashes = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        for item in source.infolist():
            if item.is_dir():
                continue
            if prefix and not item.filename.startswith(prefix):
                raise ValueError("Unexpected archive root")
            relative = Path(item.filename[len(prefix):])
            if relative.parts[0] not in {"runtime", "recomp", "tools", "docs"} and relative.as_posix() not in {"launcher/__init__.py", "launcher/net.py", "launcher/toolchain.py"} and relative.name not in {
                "VERSION", "LICENSE", "LICENSE-ADDITIONS", "THIRD_PARTY_NOTICES.md", "config.example.toml"}:
                continue
            target = output / relative
            if not target.resolve().is_relative_to(output.resolve()) or target.is_symlink():
                raise ValueError("Unsafe stable engine path")
            data = source.read(item)
            digest = hashlib.sha256(data).hexdigest()
            if expected.get(relative.as_posix()) != digest:
                raise ValueError("Stable source hash mismatch: " + relative.as_posix())
            hashes[relative.as_posix()] = digest
            # Keep renderer behavior intact; adapt only visible application identity.
            if relative.suffix in {".c", ".cpp", ".py"}:
                text = data.decode("utf-8")
                text = text.replace('"NX2navi Recomp', '"DekuForge').replace('"NX2navi"', '"DekuForge"')
                text = text.replace('"NX2navi %s  -  game %s"', '"DekuForge %s  -  game %s"')
                if relative.as_posix() == "tools/make_game.py":
                    text = text.replace("'ocarina.exe'", "'DekuForgeGame.exe'")
                data = text.encode("utf-8")
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.is_file() or target.read_bytes() != data:
                target.write_bytes(data)
    if hashes != expected:
        raise ValueError("Incomplete stable engine source archive")
    if not cached:
        cache.parent.mkdir(parents=True,exist_ok=True)
        temporary=cache.with_suffix(".zip.part");temporary.write_bytes(archive);temporary.replace(cache)
        cache_id.write_text(hashlib.sha256(archive).hexdigest()+"\n",encoding="ascii")
    icon = ROOT / "assets/branding/launcher.ico"
    if icon.is_file():
        (output / "runtime/nx2navi.ico").write_bytes(icon.read_bytes())
    marker.write_text(REVISION, encoding="utf-8")
    (output / "DEKUFORGE-SOURCE.json").write_text(json.dumps({"revision": REVISION,
        "version": "0.10.1", "files": hashes}, indent=2), encoding="utf-8")
    return output


def prepare_release_data(source, notify):
    """Prepare verified prewarm data, button art and vendor graphics libraries."""
    archive = ROOT / "local/build-tools/NX2navi-app-0.10.1.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    def verified(path):
        if not path.is_file() or path.stat().st_size != RELEASE_SIZE:
            return False
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest() == RELEASE_SHA256
    if not verified(archive):
        notify("log", "Downloading verified stable 0.10.1 pipeline metadata and controller art\n")
        partial = archive.with_suffix(".part")
        with urlopen(RELEASE_URL, timeout=90) as response, partial.open("wb") as output:
            size = 0
            while block := response.read(1024 * 1024):
                size += len(block)
                if size > RELEASE_SIZE:
                    raise ValueError("Stable release archive exceeds its size limit")
                output.write(block)
        if not verified(partial):
            raise ValueError("Stable release archive checksum mismatch")
        partial.replace(archive)
    with zipfile.ZipFile(archive) as package:
        framegen = {'bin/dlssg/' + name for name in FRAMEGEN_FILES}
        if not framegen.issubset(package.namelist()):
            raise ValueError("Stable release Frame Generation libraries or notices are missing")
        fsr = {'bin/' + name for name in FSR_FILES}
        if not fsr.issubset(package.namelist()):
            raise ValueError("Stable release AMD FSR libraries are missing")
        selected = [item for item in package.infolist() if not item.is_dir() and (
            item.filename in {"tools/data/pipeline_list.bin", "toolchain.lock.json", "THIRD_PARTY_NOTICES.md"}
            or item.filename in framegen or item.filename in fsr
            or item.filename.startswith("prompt-art/") and Path(item.filename).suffix.lower() in {".png", ".txt"})]
        if len(selected) > 1024 or sum(item.file_size for item in selected) > 128 * 1024**2:
            raise ValueError("Stable release data exceeds its limits")
        if not any(item.filename == "tools/data/pipeline_list.bin" for item in selected):
            raise ValueError("Stable release pipeline list is missing")
        for item in selected:
            name = "RELEASE-NOTICES.md" if item.filename == "THIRD_PARTY_NOTICES.md" else item.filename
            target = source / name
            if not target.resolve().is_relative_to(source.resolve()) or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Unsafe stable release data path")
            data = package.read(item)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.is_file() or target.read_bytes() != data:
                target.write_bytes(data)
    notify("log", "Stable release pipeline list, controller art, AMD FSR and NVIDIA Frame Generation files are ready\n")


def verify_framegen_runtime(source, output):
    """A successful build must deliver the complete verified set beside its executable."""
    verify_runtime_files(source/'bin/dlssg', output, FRAMEGEN_FILES, 'Frame Generation')


def verify_runtime_files(staged, output, names, component):
    for name in names:
        original, placed = staged/name, output/name
        if (not original.is_file() or not placed.is_file() or placed.is_symlink()
                or placed.stat().st_size != original.stat().st_size):
            raise ValueError(component + ' runtime is incomplete: ' + name)
        with original.open('rb') as expected, placed.open('rb') as actual:
            if hashlib.file_digest(expected, 'sha256').digest() != hashlib.file_digest(actual, 'sha256').digest():
                raise ValueError(component + ' runtime verification failed: ' + name)


def place_fsr_runtime(source, output):
    """Install the verified files even when the native compile step was reused."""
    files = {name: source/'bin'/name for name in FSR_FILES}
    files.update({name: source/'runtime/third_party'/directory/'LICENSE.txt'
                  for name, directory in FSR_NOTICES.items()})
    for name, original in files.items():
        target = output/name
        if target.is_symlink():
            raise ValueError('Unsafe AMD FSR runtime path: ' + name)
        if target.is_file():
            if name in FSR_NOTICES:
                if target.read_bytes() == original.read_bytes():
                    continue
            else:
                try:
                    verify_runtime_files(original.parent, output, (name,), 'AMD FSR')
                    continue
                except ValueError:
                    pass
        with tempfile.NamedTemporaryFile(dir=output, prefix='.fsr-', delete=False) as temp:
            temporary = Path(temp.name)
        try:
            shutil.copyfile(original, temporary)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    verify_runtime_files(source/'bin', output, FSR_FILES, 'AMD FSR')


def prepare_dlss(source, notify):
    """Use the stable kit's exact vendor-library pin and retain its notice."""
    spec=importlib.util.spec_from_file_location("stable_dlss_pin",source / "tools/dlss_pin.py")
    pin=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pin)
    folder=source / "bin"
    folder.mkdir(exist_ok=True)
    target=folder / pin.NAME
    if target.is_file() and target.stat().st_size==pin.SIZE and hashlib.sha256(target.read_bytes()).hexdigest()==pin.SHA256:
        (folder / pin.NOTICE).write_text(pin.notice_text(),encoding="utf-8")
        return
    local=ROOT.parent / "NX2Navi/Play" / pin.NAME
    if local.is_file() and local.stat().st_size==pin.SIZE and hashlib.sha256(local.read_bytes()).hexdigest()==pin.SHA256:
        data=local.read_bytes()
    else:
        notify("log","Downloading the pinned DLSS runtime from NVIDIA\n")
        with urlopen(pin.URL,timeout=90) as response:
            data=response.read(pin.SIZE+1)
    if len(data)!=pin.SIZE or hashlib.sha256(data).hexdigest()!=pin.SHA256:
        raise ValueError("DLSS runtime size or hash mismatch")
    temporary=folder / (pin.NAME+".part")
    temporary.write_bytes(data)
    temporary.replace(target)
    (folder / pin.NOTICE).write_text(pin.notice_text(),encoding="utf-8")


def ensure_native_tools(source, notify):
    required=("bin/clang.exe","bin/clang++.exe","bin/SDL3.dll","lib/libSDL3.dll.a","include/vma")
    own=ROOT / "local/build-tools/native/msys64/ucrt64"
    # The pinned installer compares lock identity and reuses verified packages.
    toolchain=own
    command=[sys.executable,str(ROOT / "tools/bootstrap_stable_toolchain.py")]
    with subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
            text=True,encoding="utf-8",errors="replace",creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)) as worker:
        for line in worker.stdout:
            notify("log",line)
        if worker.wait():
            raise RuntimeError("Native build tool preparation failed")
    toolchain=own
    if not all((toolchain/name).exists() for name in required):
        raise RuntimeError("Native build tools are incomplete")
    with subprocess.Popen([sys.executable,str(ROOT / "tools/bootstrap_shader_tools.py")],cwd=ROOT,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace",
            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)) as worker:
        for line in worker.stdout:
            notify("log",line)
        if worker.wait():
            raise RuntimeError("Shader build tool preparation failed")
    notify("log","Native build tools: " + str(toolchain) + "\n")
    return toolchain


def build_input_arguments(filename, output):
    """Reuse extracted input only for the same archive identity recorded by the stable builder."""
    filename=Path(filename).absolute()
    stat=filename.stat()
    identity=f"nup {filename} {stat.st_size} {int(stat.st_mtime)}"
    try:
        state=json.loads((output / "build-cache/state.json").read_text(encoding="utf-8"))
        steps=state.get("steps",{})
        if state.get("version")==2 and state.get("input")==identity and all(key in steps for key in ("exefs","romfs")):
            return ["--rebuild"]
    except (OSError,ValueError,AttributeError,TypeError):
        pass
    return ["--nup",str(filename)]


def release_preparation_changed(output):
    marker = output / ".dekuforge-release-data"
    if marker.is_file() and marker.read_text(encoding="ascii").strip() == RELEASE_SHA256:
        return False
    state_path = output / "build-cache/state.json"
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state.get("steps", {}).pop("shaders", None)
        temporary = state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=1), encoding="utf-8")
        temporary.replace(state_path)
    return True


def carry_active_configuration(output, active):
    """Carry preferences from the same engine revision into a fresh owned build."""
    target = output / "nx2navi.ini"
    if target.exists() or not active:
        return False
    folder = Path(active).parent
    try:
        info = json.loads((folder / "dekuforge-build-info.json").read_text(encoding="utf-8"))
        if info.get("engine_revision") != REVISION or not Path(active).is_file():
            return False
        source = folder / "nx2navi.ini"
        if source.stat().st_size > 256 * 1024:
            return False
        data = source.read_bytes()
    except (OSError, ValueError, AttributeError):
        return False
    with tempfile.NamedTemporaryFile(dir=output, prefix="settings-", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    temporary.replace(target)
    return True


def build_stable(filename, notify, destination):
    output = Path(destination).absolute()
    if output.resolve() != output:
        raise ValueError("Build destination must not be a link")
    marker = output / ".dekuforge-stable-build"
    if output.exists() and any(output.iterdir()) and not marker.is_file():
        raise ValueError("Build destination is not an owned stable build")
    output.mkdir(parents=True, exist_ok=True)
    marker.touch()
    (output / ".dekuforge-owned").write_text("DekuForge stable build\n",encoding="utf-8")
    from .core import load_installation
    if carry_active_configuration(output, load_installation()):
        notify("log", "Carried graphics and controller preferences from the matching active engine\n")
    notify("phase", {"phase":"checking"})
    notify("log", "Preparing stable 0.10.1 source " + REVISION + "\n")
    source = stage_stable()
    from .runtime_layer import compose, ENGINE_VERSION, BUILD_KIT_VERSION
    layer = compose(source)
    prepare_release_data(source, notify)
    if release_preparation_changed(output):
        notify("log", "Preparing the complete stable release pipeline list before play\n")
    prepare_dlss(source,notify)
    if importlib.util.find_spec("zbic") is None:
        with subprocess.Popen([sys.executable,str(ROOT/"tools/prepare_decompressor.py")],cwd=ROOT,
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace",
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)) as dependencies:
            for line in dependencies.stdout: notify("log",line)
            if dependencies.wait(): raise RuntimeError("Game decompressor preparation failed")
    notify("phase", {"phase":"shaders"})
    preparation = [sys.executable, str(ROOT / "tools/build_stable_translator.py")]
    with subprocess.Popen(preparation, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)) as worker:
        for line in worker.stdout:
            notify("log",line)
        if worker.wait():
            raise RuntimeError("Stable shader translator preparation failed")
    toolchain = ensure_native_tools(source, notify)
    env = os.environ.copy()
    env["PATH"] = str(ROOT / "local/build-tools/shaders/ucrt64/bin") + os.pathsep + str(toolchain / "bin") + os.pathsep + env.get("PATH", "")
    command = [sys.executable, str(ROOT / "tools/run_stable_build.py"), *build_input_arguments(filename,output),
        "--out", str(output), "--msys", str(toolchain), "--jobs", "6", "--events"]
    notify("log", "Building pinned stable engine 0.10.1: " + REVISION + "\n")
    pipeline_progress = False
    error_detail = ""
    with subprocess.Popen(command, cwd=source, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)) as process:
        for line in process.stdout:
            notify("log", line)
            if line.startswith("prepare-pipelines: progress "):
                fields = line.split()
                try:
                    done, total = int(fields[2]), int(fields[3])
                    pipeline_progress = True
                    notify("progress", {"phase":"pipelines", "done":done, "total":total})
                except (ValueError, IndexError):
                    pass
            if line.startswith("@@"):
                try:
                    event = json.loads(line[2:])
                    if event.get("ev") == "error":
                        error_detail = str(event.get("message", ""))[:16384]
                    phases = {"check":"checking", "exefs":"prepared", "romfs":"extracting",
                              "lift":"generating", "compile":"compiling", "shaders":"shaders",
                              "prompts":"prompts", "scan":"checking"}
                    phase = phases.get(event.get("step"), "checking")
                    if event.get("ev") == "progress":
                        detail = event.get("detail", "")
                        if pipeline_progress and event.get("step") == "shaders":
                            if detail.startswith("Translated"):
                                continue
                            pipeline_progress = False
                        fraction=event.get("fraction")
                        if isinstance(fraction,(int,float)) and 0<=fraction<=1:
                            notify("progress", {"phase":phase,"done":fraction,"total":1})
                        else:
                            notify("progress", {"phase":phase,"done":event.get("done",0),"total":event.get("total",0)})
                    elif event.get("ev") == "step" and event.get("state") == "start":
                        notify("phase", {"phase":phase})
                except (ValueError, TypeError):
                    pass
        returncode = process.wait()
        if returncode:
            raise RuntimeError(build_failure_message(returncode, error_detail))
    exe = output / "DekuForgeGame.exe"
    if not exe.is_file():
        raise RuntimeError("Stable build did not produce its executable")
    verify_framegen_runtime(source, output)
    place_fsr_runtime(source, output)
    notify('log', 'Verified NVIDIA Frame Generation and AMD FSR libraries and notices beside the game\n')
    from . import __version__
    with exe.open("rb") as binary:
        runtime_hash = hashlib.file_digest(binary,"sha256").hexdigest()
    info = {"engine_version":ENGINE_VERSION,"engine_revision":REVISION,
            "base_engine_version":"0.10.1","launcher_version":__version__,
            "build_kit_version":BUILD_KIT_VERSION,"source_layer_sha256":layer["layer_sha256"],
            "build_id":runtime_hash[:12],"runtime_sha256":runtime_hash,
            "game_version":"1.1.1","experimental":True}
    temporary=output / "dekuforge-build-info.tmp"
    temporary.write_text(json.dumps(info,indent=2),encoding="utf-8")
    temporary.replace(output / "dekuforge-build-info.json")
    (output / ".dekuforge-release-data").write_text(RELEASE_SHA256 + "\n", encoding="ascii")
    from .build_library import BuildLibrary
    BuildLibrary(ROOT).register(exe,dump=str(filename),version=ENGINE_VERSION+" / 1.1.1",owned=True)
    return exe
