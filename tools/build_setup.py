"""Embed the launcher-only package in a standalone native Windows setup executable.

The setup verifies, unpacks and installs that package natively; it starts no script host."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.package_launcher import package
from dekuforge import COMPONENTS
from tools.native_resources import NATIVE_SOURCES, RUNTIME_SOURCES, digest_header, packaged_sha256, runtime_pin_header, write_resources


def package_recomplauncher(archive, version):
    # The in-app updater still uses its existing, checksummed package format.
    manifest = ROOT / "recomplauncher.json"
    shutil.copyfile(manifest, archive.parent / manifest.name)
    portable = archive.parent / f"DekuForge-{version}-windows-x64.zip"
    temporary = portable.with_suffix(".zip.part")
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as target:
        for name in source.namelist():
            if name not in {"launcher-package.json", "DekuForge-Uninstall.exe"}:
                target.writestr(name, source.read(name))
        target.write(manifest, manifest.name)
    temporary.replace(portable)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain",type=Path,required=True)
    parser.add_argument("--tag",default="v"+COMPONENTS["launcher"]["version"])
    args=parser.parse_args()
    if args.tag != "v"+COMPONENTS["launcher"]["version"]:
        raise ValueError("Release tag must match the launcher component version")
    out=ROOT/"build/setup";out.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env["PATH"]=str(args.toolchain.resolve())+os.pathsep+env.get("PATH","")
    icon=ROOT/"assets/branding/launcher.ico"
    version=COMPONENTS["launcher"]["version"]
    compile_flags=["-O2","-Wall","-Wextra","-Werror","-municode","-mwindows","-I",str(out),"-I",str(ROOT/"launcher")]
    (out/"runtime_pin.h").write_text(runtime_pin_header(COMPONENTS),encoding="ascii")
    # The uninstaller runs the installed helper only when it matches this packaged digest.
    (out/"uninstall_script.h").write_text(digest_header("DEKU_UNINSTALL_SCRIPT_SHA256",
        packaged_sha256(ROOT/"installer/uninstall.ps1")),encoding="ascii")
    uninstall_resource=write_resources(out,"uninstall",description="DekuForge uninstaller",
        filename="DekuForge-Uninstall.exe",version=version,icon=icon)
    subprocess.run([str(args.toolchain/"windres.exe"),str(uninstall_resource),"-o",str(out/"uninstall.o")],env=env,check=True)
    subprocess.run([str(args.toolchain/"clang.exe"),*compile_flags,str(ROOT/"installer/uninstall.c"),*map(str,NATIVE_SOURCES),
        str(out/"uninstall.o"),"-lbcrypt","-o",str(ROOT/"DekuForge-Uninstall.exe")],env=env,check=True)
    archive=package()
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    (out/"setup_payload.h").write_text(digest_header("DEKU_SETUP_PAYLOAD_SHA256",digest),encoding="ascii")
    resource=write_resources(out,"setup",description="DekuForge setup",filename="DekuForge-Setup.exe",
        version=version,icon=icon,extra=['102 RCDATA "'+archive.resolve().as_posix()+'"'])
    subprocess.run([str(args.toolchain/"windres.exe"),str(resource),"-o",str(out/"setup.o")],env=env,check=True)
    executable=ROOT/"build/releases/DekuForge-Setup.exe"
    subprocess.run([str(args.toolchain/"clang.exe"),*compile_flags,str(ROOT/"installer/setup.c"),*map(str,RUNTIME_SOURCES),
        str(out/"setup.o"),"-lshell32","-lole32","-luuid","-lgdi32","-ladvapi32","-lwinhttp","-lbcrypt",
        "-o",str(executable)],env=env,check=True)
    with zipfile.ZipFile(archive) as content:
        manifest=json.loads(content.read("launcher-package.json"))
    release={"schema":1,"tag":args.tag,"components":manifest["components"],"contains_game_files":False,
        "package":{"name":archive.name,"size":archive.stat().st_size,"sha256":digest},
        "installer":{"name":executable.name,"size":executable.stat().st_size,"sha256":hashlib.sha256(executable.read_bytes()).hexdigest()}}
    (ROOT/"build/releases/DekuForge-independent-release.json").write_text(json.dumps(release,indent=2)+'\n',encoding="utf-8")
    package_recomplauncher(archive, version)
    print("Built standalone setup:",executable,flush=True)


if __name__=="__main__":main()
