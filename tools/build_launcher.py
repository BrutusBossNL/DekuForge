"""Package the unchanged brand artwork as a Windows icon and compile the bootstrap."""

import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain", type=Path, help="compiler bin directory")
    parser.add_argument("--assets-only", action="store_true", help="export the Windows icon without running a compiler")
    args = parser.parse_args()
    if not args.assets_only and not args.toolchain:
        parser.error("--toolchain is required to compile the launcher")
    from PIL import Image, ImageOps
    icon = ROOT / "assets" / "branding" / "launcher.ico"
    master = ROOT / "assets" / "branding" / "icon.png"
    with Image.open(master) as source:
        fitted = ImageOps.contain(source.convert("RGBA"), (256, 256), Image.Resampling.LANCZOS)
        square = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        square.alpha_composite(fitted, ((256 - fitted.width) // 2, (256 - fitted.height) // 2))
        square.save(icon, sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
    if args.assets_only:
        print("Exported icon:", icon)
        return
    output = ROOT / "build" / "launcher"
    output.mkdir(parents=True, exist_ok=True)
    pins=json.loads((ROOT/"dekuforge/components.json").read_text(encoding="utf-8"))
    runtime_id=pins["python"]["id"]
    if not all(c.isalnum() or c in ".-" for c in runtime_id):
        raise ValueError("Invalid runtime component identity")
    (output/"runtime_pin.h").write_text('#define DEKU_PYTHON_ID L"'+runtime_id+'"\n',encoding="ascii")
    resource = output / "brand.rc"
    version=pins["launcher"]["version"]
    numeric=",".join(version.split("-")[0].split(".")+["0"])
    resource.write_text(('101 ICON "' + icon.as_posix() + '"\n' + '''
1 VERSIONINFO
FILEVERSION 0,1,0,0
PRODUCTVERSION 0,1,0,0
FILEOS 0x40004
FILETYPE 0x1
BEGIN
 BLOCK "StringFileInfo"
 BEGIN
  BLOCK "040904b0"
  BEGIN
   VALUE "FileDescription", "DekuForge launcher\\0"
   VALUE "ProductName", "DekuForge\\0"
   VALUE "FileVersion", "0.1.0-dev\\0"
   VALUE "OriginalFilename", "DekuForge.exe\\0"
  END
 END
 BLOCK "VarFileInfo"
 BEGIN
  VALUE "Translation", 0x409, 1200
 END
END
''').replace("0,1,0,0",numeric).replace("0.1.0-dev",version), encoding="utf-8")
    obj = output / "brand.o"
    environment = os.environ.copy()
    environment["PATH"] = str(args.toolchain.resolve()) + os.pathsep + environment.get("PATH", "")
    subprocess.run([str(args.toolchain / "windres.exe"), "-i", str(resource), "-o", str(obj)], check=True, env=environment)
    executable = ROOT / "DekuForge.exe"
    subprocess.run([str(args.toolchain / "clang.exe"), "-O2", "-Wall", "-Wextra", "-Werror", "-municode", "-mwindows",
                    "-I",str(output),str(ROOT / "launcher" / "main.c"), str(obj), "-o", str(executable)], check=True, env=environment)
    print("Built:", executable)


if __name__ == "__main__":
    main()
