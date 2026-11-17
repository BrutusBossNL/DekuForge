"""Bounded play check of the owned stable 0.10.1 migration installation."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture",action="store_true",help="Record bounded consecutive frames and in-game settings pages")
    parser.add_argument("--deterministic-shot",action="store_true",help="Use synchronous pipelines for a deterministic final screenshot")
    args=parser.parse_args()
    folder=ROOT/"build/stable-windows-game"
    if folder.resolve()!=folder or not (folder/".dekuforge-stable-build").is_file():
        raise ValueError("Use only the owned stable migration build")
    exe=folder/"DekuForgeGame.exe"
    if not exe.is_file():
        raise ValueError("Stable executable has not been built")
    script=ROOT/"local/test-stable-moving.txt"
    if not script.is_file():
        script.parent.mkdir(exist_ok=True)
        script.write_text("650 A 4\n850 A 4\n1050 A 4\n1250 A 4\n1450 A 4\n"
            "@3000 LSTICK 0 14000 2000\n@9000 RSTICK 8000 0 1500\n"
            "@14000 LSTICK 0 -10000 2000\n",encoding="ascii")
    env={k:v for k,v in os.environ.items() if not k.startswith(("NX2NAVI_","DEKUFORGE_"))}
    env.update(NX2NAVI_GPU="vulkan",NX2NAVI_TRACE="present",NX2NAVI_INPUT_SCRIPT=str(script))
    if args.capture:
        env.update(NX2NAVI_FLIGHT="1",NX2NAVI_FLIGHT_FRAMES="90",
            NX2NAVI_FLIGHT_AT="3650,3900",NX2NAVI_FLIGHT_SPIKE_MS="0",NX2NAVI_FLIGHT_FLASH="0",
            NX2NAVI_FLIGHT_DIR=str(folder/"validation-frames"),
            NX2NAVI_MENU_TEST="1200:20",NX2NAVI_MENU_TEST_DIR=str(folder))
    shot=folder/"test-stable-world.png"
    shot.unlink(missing_ok=True)
    command=[str(exe),"--seconds","20"]
    captures=folder/"normal-start-captures"
    if args.deterministic_shot:
        command += ["--shot",str(shot)]
    else:
        captures.mkdir(exist_ok=True)
        for previous in captures.glob("shot_*.png"):
            previous.unlink()
        env.update(NX2NAVI_SHOT_EVERY="8",NX2NAVI_SHOT_DIR=str(captures))
    started=time.monotonic();timed_out=False;fatal=False
    with (folder/"test-stable.log").open("w",encoding="utf-8") as log:
        with subprocess.Popen(command,cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)) as game:
            while game.poll() is None:
                time.sleep(0.5)
                text=(folder/"test-stable.log").read_text(encoding="utf-8",errors="replace")
                fatal=any(line.startswith("FATAL:") for line in text.splitlines())
                timed_out=time.monotonic()-started>600
                if fatal or timed_out:
                    game.kill();break
            code=game.wait()
    if not args.deterministic_shot:
        saved=sorted(captures.glob("shot_*.png"))
        if saved:
            shutil.copy2(saved[-1],shot)
    record={"normal_start":not args.deterministic_shot,"engine":"0.10.1","exit_code":code,"timed_out":timed_out,"fatal_error":fatal,
        "elapsed":round(time.monotonic()-started,2),"screenshot":str(shot),
        "screenshot_exists":shot.is_file(),"visually_verified":False}
    (folder/"test-stable.json").write_text(json.dumps(record,indent=2),encoding="utf-8")
    print(json.dumps(record,indent=2))
    raise SystemExit(1 if timed_out or fatal or code else 0)


if __name__=="__main__":main()
