"""Bounded play check of the owned stable 0.10.1 migration installation."""
import json
import os
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/"build/stable-windows-game"
    if folder.resolve()!=folder or not (folder/".dekuforge-stable-build").is_file():
        raise ValueError("Use only the owned stable migration build")
    exe=folder/"DekuForgeGame.exe"
    if not exe.is_file():
        raise ValueError("Stable executable has not been built")
    script=ROOT/"local/test-field-moving.txt"
    env={k:v for k,v in os.environ.items() if not k.startswith(("NX2NAVI_","DEKUFORGE_"))}
    env.update(NX2NAVI_GPU="vulkan",NX2NAVI_TRACE="present",NX2NAVI_INPUT_SCRIPT=str(script))
    shot=folder/"test-stable-world.png"
    command=[str(exe),"--seconds","20","--shot",str(shot)]
    started=time.monotonic();timed_out=False;fatal=False
    with (folder/"test-stable.log").open("w",encoding="utf-8") as log:
        with subprocess.Popen(command,cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)) as game:
            while game.poll() is None:
                time.sleep(0.5)
                text=(folder/"test-stable.log").read_text(encoding="utf-8",errors="replace")
                fatal=any(line.startswith("FATAL:") for line in text.splitlines())
                timed_out=time.monotonic()-started>180
                if fatal or timed_out:
                    game.kill();break
            code=game.wait()
    record={"engine":"0.10.1","exit_code":code,"timed_out":timed_out,"fatal_error":fatal,
        "elapsed":round(time.monotonic()-started,2),"screenshot":str(shot),
        "screenshot_exists":shot.is_file(),"visually_verified":False}
    (folder/"test-stable.json").write_text(json.dumps(record,indent=2),encoding="utf-8")
    print(json.dumps(record,indent=2))
    raise SystemExit(1 if timed_out or fatal or code else 0)


if __name__=="__main__":main()
