"""Embed the launcher-only package in a standalone native Windows setup executable."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.package_launcher import package
from dekuforge import COMPONENTS


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain",type=Path,required=True)
    parser.add_argument("--tag",default="v"+COMPONENTS["launcher"]["version"])
    args=parser.parse_args()
    if args.tag != "v"+COMPONENTS["launcher"]["version"]:
        raise ValueError("Release tag must match the launcher component version")
    out=ROOT/"build/setup";out.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env["PATH"]=str(args.toolchain.resolve())+os.pathsep+env.get("PATH","")
    uninstall_resource=out/"uninstall.rc"
    uninstall_resource.write_text('101 ICON "'+(ROOT/"assets/branding/launcher.ico").as_posix()+'"\n103 RCDATA "'+(ROOT/"installer/uninstall.ps1").as_posix()+'"\n',encoding="utf-8")
    subprocess.run([str(args.toolchain/"windres.exe"),str(uninstall_resource),"-o",str(out/"uninstall.o")],env=env,check=True)
    subprocess.run([str(args.toolchain/"clang.exe"),"-O2","-Wall","-Wextra","-Werror","-municode","-mwindows",
        str(ROOT/"installer/uninstall.c"),str(out/"uninstall.o"),"-o",str(ROOT/"DekuForge-Uninstall.exe")],env=env,check=True)
    archive=package()
    script=(ROOT/"installer/install.ps1").read_text(encoding="utf-8")
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    script=script.replace("$ProgressPreference = 'SilentlyContinue'","$ProgressPreference = 'SilentlyContinue'\n"
        +"if ((File-Sha256 $Payload) -ne '"+digest+"') { throw 'Installer payload checksum mismatch' }")
    (out/"install.ps1").write_text(script,encoding="utf-8")
    resource=out/"setup.rc"
    resource.write_text('101 ICON "'+(ROOT/"assets/branding/launcher.ico").as_posix()+'"\n'
        +'102 RCDATA "'+archive.as_posix()+'"\n103 RCDATA "'+(out/"install.ps1").as_posix()+'"\n',encoding="utf-8")
    env=os.environ.copy();env["PATH"]=str(args.toolchain.resolve())+os.pathsep+env.get("PATH","")
    subprocess.run([str(args.toolchain/"windres.exe"),str(resource),"-o",str(out/"setup.o")],env=env,check=True)
    executable=ROOT/"build/releases/DekuForge-Setup.exe"
    subprocess.run([str(args.toolchain/"clang.exe"),"-O2","-Wall","-Wextra","-Werror","-municode","-mwindows",
        str(ROOT/"installer/setup.c"),str(out/"setup.o"),"-lshell32","-lole32","-lgdi32","-o",str(executable)],env=env,check=True)
    with zipfile.ZipFile(archive) as content:
        manifest=json.loads(content.read("launcher-package.json"))
    release={"schema":1,"tag":args.tag,"components":manifest["components"],"contains_game_files":False,
        "package":{"name":archive.name,"size":archive.stat().st_size,"sha256":digest},
        "installer":{"name":executable.name,"size":executable.stat().st_size,"sha256":hashlib.sha256(executable.read_bytes()).hexdigest()}}
    (ROOT/"build/releases/DekuForge-release.json").write_text(json.dumps(release,indent=2)+'\n',encoding="utf-8")
    print("Built standalone setup:",executable,flush=True)


if __name__=="__main__":main()
