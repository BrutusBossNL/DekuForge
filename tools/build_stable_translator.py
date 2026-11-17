"""Build the pinned stable translator as a self-contained Windows executable."""
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    source=ROOT/"build/engine-0.10.1"
    if not (source/".dekuforge-stable-engine").is_file():
        raise ValueError("Stable source workspace is not owned")
    spec=importlib.util.spec_from_file_location("stable_xlate",source/"tools/build_xlate.py")
    driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
    executable=driver.BUILD/"nx2navi_xlate.exe"
    identity_file=driver.BUILD/"nx2navi_xlate.id"
    def identity():
        return hashlib.sha256((driver.identity()+"\nmanaged-single-file-net10").encode()).hexdigest()
    if executable.is_file() and identity_file.is_file() and identity_file.read_text().strip()==identity():
        print("Stable translator matches its sources",flush=True)
        return
    driver.verify_vendor()
    # All preparation/deletion in the reference driver stays under this owned root.
    if not driver.BUILD.resolve().is_relative_to(source.resolve()):
        raise ValueError("Invalid translator build directory")
    tree=driver.prepare_sources()
    work=driver.BUILD/"xlate";work.mkdir(parents=True,exist_ok=True)
    for name in ("Program.cs","AmpereLowering.cs","MeshSpirv.cs","nx2navi_xlate.csproj"):
        shutil.copy2(driver.XLATE/name,work/name)
    dotnet=ROOT/"local/build-tools/dotnet-10.0.404/dotnet.exe"
    if not dotnet.is_file():
        subprocess.run([sys.executable,str(ROOT/"tools/bootstrap_build_tools.py"),"--dotnet"],check=True)
    if not dotnet.is_file():
        raise RuntimeError("The pinned .NET SDK could not be prepared")
    env=os.environ.copy();env["DOTNET_ROOT"]=str(dotnet.parent)
    env["DOTNET_CLI_HOME"]=str(ROOT/"local/dotnet-home")
    publish=driver.BUILD/"publish"
    command=[str(dotnet),"publish",str(work/"nx2navi_xlate.csproj"),"-c","Release","-r","win-x64",
        "--self-contained","true","-p:PublishSingleFile=true","-p:IncludeNativeLibrariesForSelfExtract=true",
        "-p:InvariantGlobalization=true",f"-p:RyuSrc={tree}","-o",str(publish),
        "--source","https://api.nuget.org/v3/index.json"]
    subprocess.run(command,env=env,check=True)
    shutil.copy2(publish/"nx2navi_xlate.exe",executable)
    identity_file.write_text(identity()+"\n",encoding="ascii")
    print("Stable translator built",flush=True)


if __name__=="__main__":
    main()
