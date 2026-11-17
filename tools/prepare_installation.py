"""Prepare the complete Windows build tools without reading any game input."""
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dekuforge.stable_engine import stage_stable, ensure_native_tools, prepare_release_data


def main():
    from dekuforge import COMPONENTS
    if COMPONENTS['engine'].get('backend') == 'independent':
        raise RuntimeError('Independent runtime/toolchain provisioning is not packaged. No NX2navi source or runtime will be downloaded.')
    source=stage_stable()
    prepare_release_data(source,lambda kind,value:print(value,flush=True))
    ensure_native_tools(source,lambda kind,value:print(value,flush=True))
    subprocess.run([sys.executable,str(ROOT/"tools/bootstrap_build_tools.py"),"--dotnet"],check=True)
    subprocess.run([sys.executable,str(ROOT/"tools/prepare_decompressor.py")],check=True)
    print("DekuForge build tools are ready. No game files were downloaded or generated.",flush=True)


if __name__=="__main__":main()
