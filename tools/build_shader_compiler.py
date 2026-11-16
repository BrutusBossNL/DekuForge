"""Compose permitted shader sources and publish a standalone Vulkan translator."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    baseline = ROOT / "engine" / "tools"
    extension = ROOT / "engine_overrides" / "shader"
    patches = [*sorted((baseline / "xlate" / "patches").glob("*.patch")), extension / "ampere.patch",
               *sorted(extension.glob("mesh-*.patch"))]
    digest = hashlib.sha256(b"DekuForge shader composition LF v2\0")
    for path in [Path(__file__).resolve(), *sorted((baseline / "vendor" / "ryujinx").rglob("*")), *patches, baseline / "xlate" / "Program.cs",
                 extension / "MeshDispatch.cs", ROOT / "tools/mesh_shader_worker.py", ROOT / "dekuforge/mesh_stage.py"]:
        if path.is_file():
            digest.update(path.relative_to(ROOT).as_posix().encode() + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    identity = digest.hexdigest()
    work = ROOT / "build" / "shader-compiler" / identity[:16]
    if work.resolve() != work:
        raise ValueError("Shader workspace must not be a link")
    marker = work / "prepared.json"
    if not marker.is_file():
        if work.exists():
            raise ValueError("Incomplete shader preparation exists; use a separate owned workspace")
        work.mkdir(parents=True)
        vendor = work / "ryujinx"
        shutil.copytree(baseline / "vendor" / "ryujinx", vendor)
        # Git patches must see the same source lines under every Windows Git
        # configuration. Normalize only the disposable copy, never the pin.
        for source in vendor.rglob("*.cs"):
            content = source.read_bytes()
            if b"\r\n" in content:
                source.write_bytes(content.replace(b"\r\n", b"\n"))
        for patch in patches:
            for extra in (["--check"], []):
                command = ["git", "apply", *extra, "--whitespace=nowarn", "--directory", "ryujinx", str(patch)]
                result = subprocess.run(command, cwd=work, capture_output=True, text=True)
                if result.returncode:
                    raise RuntimeError(f"Shader patch failed: {patch.name}\n{result.stdout}{result.stderr}")
            print("Applied", patch.name, flush=True)
        program = (baseline / "xlate" / "Program.cs").read_text(encoding="utf-8")
        program = program.replace('            int bytes = off0 * 4;', '''            int bytes = off0 * 4;
            if (cbufSlot == 0 && _job["nvn2_tex_base"] is JsonNode start && _job["nvn2_tex_count"] is JsonNode count)
            {
                int relative = bytes - (int)start;
                return relative >= 0 && relative % 8 == 0 && relative / 8 < (int)count ? relative / 8 : -1;
            }''')
        program = program.replace('        public SamplerType QuerySamplerType(', '''        SamplerType NumericType(int slot)
        {
            string numeric = _job["tex"] is JsonObject table && slot >= 0 && table[slot.ToString()] is JsonObject entry
                ? (string)entry["numeric"] : null;
            return numeric == "uint" ? SamplerType.UnsignedInteger : numeric == "sint" ? SamplerType.SignedInteger : 0;
        }
        public SamplerType QuerySamplerType(''')
        program = program.replace('        public TextureFormat QueryTextureFormat(int handle, int cbufSlot = -1)', '''        int ImageSlot(int handle, int cbufSlot)
        {
            if (cbufSlot == 0 && _job["nvn2_img_base"] is JsonNode start && _job["nvn2_img_count"] is JsonNode count)
            {
                (int offset, _, _) = TextureHandle.UnpackOffsets(handle);
                int relative = offset * 4 - (int)start;
                return relative >= 0 && relative % 8 == 0 && relative / 8 < (int)count ? relative / 8 : -1;
            }
            return TexSlot(handle, cbufSlot);
        }
        public TextureFormat QueryTextureFormat(int handle, int cbufSlot = -1)''')
        program = program.replace('int slot = TexSlot(handle, cbufSlot);\n            if (slot >= 0) ImgQueried',
                                  'int slot = ImageSlot(handle, cbufSlot);\n            if (slot >= 0) ImgQueried')
        program = program.replace('            return t switch', '            return (t switch')
        program = program.replace('                _ => SamplerType.Texture2D,\n            };',
                                  '                _ => SamplerType.Texture2D,\n            }) | NumericType(slot);')
        program = program.replace('byte[] code = File.ReadAllBytes((string)job["code"]);',
                                  'if ((string)job["stage"] == "ts" || (string)job["stage"] == "ms") return MeshDispatch.Translate(job, outDir);\n'
                                  '                byte[] code = File.ReadAllBytes((string)job["code"]);')
        anchor = "var ctx = Translator.CreateContext(0, acc,"
        if program.count(anchor) != 1:
            raise ValueError("Shader entry point differs from the pinned source")
        program = program.replace(anchor, 'if (job["ampere"] is JsonNode amp && (bool)amp) flags |= TranslationFlags.Ampere;\n                ' + anchor)
        program = program.replace("public uint ConstantBuffer1Read(int offset)",
                                  'public int[] QueryAmpereStageMemory() => _job["stage_memory"] is JsonArray a ? a.Select(n => (int)n).ToArray() : null;\n'
                                  "        public int QueryConstantBuffer1Size() => _c1.Length;\n        public uint ConstantBuffer1Read(int offset)")
        program = program.replace("TargetLanguage.Spirv, TargetApi.Vulkan",
                                  '(job["emit_glsl"] is JsonValue gl && gl.TryGetValue<bool>(out bool emit) && emit ? TargetLanguage.Glsl : TargetLanguage.Spirv), TargetApi.Vulkan')
        program = program.replace('File.WriteAllBytes(Path.Combine(outDir, key + ".spv"), p.BinaryCode);',
                                  'if (p.Language == TargetLanguage.Glsl) File.WriteAllText(Path.Combine(outDir, key + ".comp"), p.Code);\n'
                                  '                else File.WriteAllBytes(Path.Combine(outDir, key + ".spv"), p.BinaryCode);')
        (work / "Program.cs").write_text(program, encoding="utf-8")
        shutil.copy2(extension / "MeshDispatch.cs", work / "MeshDispatch.cs")
        project = (baseline / "xlate" / "nx2navi_xlate.csproj").read_text(encoding="utf-8")
        project = project.replace("<OutputType>Exe</OutputType>", "<OutputType>Exe</OutputType><AssemblyName>DekuForgeShader</AssemblyName>")
        project = project.replace("<Nullable>disable</Nullable>", "<Nullable>disable</Nullable><EnableDefaultCompileItems>false</EnableDefaultCompileItems>")
        project = project.replace("</Project>", '<ItemGroup><Compile Include="Program.cs" /><Compile Include="MeshDispatch.cs" /></ItemGroup></Project>')
        (work / "DekuForgeShader.csproj").write_text(project, encoding="utf-8")
        marker.write_text(json.dumps({"identity": identity}) + "\n", encoding="utf-8")
    print("Shader source workspace:", work, flush=True)
    if args.prepare_only:
        return
    portable = ROOT / "local" / "build-tools" / "dotnet-10.0.404" / "dotnet.exe"
    dotnet = str(portable) if portable.is_file() else shutil.which("dotnet") or str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "dotnet" / "dotnet.exe")
    environment = os.environ.copy()
    environment["DOTNET_CLI_HOME"] = str(ROOT / "local" / "dotnet")
    environment["NUGET_PACKAGES"] = str(ROOT / "build" / "nuget")
    environment["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"
    environment["DOTNET_GENERATE_ASPNET_CERTIFICATE"] = "false"
    output = work / "publish"
    command = [dotnet, "publish", str(work / "DekuForgeShader.csproj"), "-c", "Release", "-r", "win-x64",
               "--self-contained", "true", "-p:PublishAot=false", "-p:PublishSingleFile=true",
               "-p:InvariantGlobalization=true", "-p:RestoreSources=https://api.nuget.org/v3/index.json",
               f"-p:RyuSrc={work / 'ryujinx'}", "-o", str(output)]
    log = work / "publish.log"
    with log.open("w", encoding="utf-8") as stream, subprocess.Popen(command, env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace") as process:
        for line in process.stdout:
            stream.write(line)
            if " error " in line or " -> " in line or "Restored " in line:
                print(line.rstrip(), flush=True)
        if process.wait():
            raise RuntimeError(f"Shader compiler build failed; see {log}")
    (output / "DekuForgeShader.id").write_text(identity + "\n", encoding="ascii")
    active = {"executable": str((output / "DekuForgeShader.exe").relative_to(ROOT)), "identity": identity,
              "sha256": hashlib.sha256((output / "DekuForgeShader.exe").read_bytes()).hexdigest()}
    (ROOT / "build" / "shader-compiler" / "active.json").write_text(json.dumps(active, indent=2) + "\n", encoding="utf-8")
    print("Published shader translator:", output / "DekuForgeShader.exe")


if __name__ == "__main__":
    main()
