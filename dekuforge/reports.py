"""User-reviewed issue reports: bounded text logs and hardware, never game files."""
from datetime import datetime, timezone
import ctypes
import json
import os
from pathlib import Path
import platform
import re
import shutil
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from . import COMPONENTS
from .update_package import atomic_json
from .update_service import AssetRedirect, github_token

REPOSITORY="BrutusBossNL/DekuForge"
MAX_LOG=16000


def sanitize(text):
    text=re.sub(r"(?i)\b(?:github_pat_[A-Za-z0-9_]+|gh[pousr]_[A-Za-z0-9_]+)\b","[REDACTED TOKEN]",text)
    text=re.sub(r"(?im)((?:authorization|access_token|refresh_token|password|secret)\s*[:=]\s*)([^\r\n]+)",r"\1[REDACTED]",text)
    text=re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+","Bearer [REDACTED]",text)
    text=re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}","[REDACTED EMAIL]",text)
    text=re.sub(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\r\n\"<>|]+","[LOCAL PATH]",text)
    text=re.sub(r"\\\\[^\\\s]+\\[^\r\n\"<>|]+","[NETWORK PATH]",text)
    text=re.sub(r"(?:/home/|/Users/|/tmp/)[^\r\n\"<>]+","[LOCAL PATH]",text)
    # Compiler excerpts and memory/shader disassembly are not safe diagnostic attachments.
    text=re.sub(r"(?m)^\s*\d+\s*\|[^\n]*$","[SOURCE CONTEXT OMITTED]",text)
    text=re.sub(r"(?m)^\s*\|[^\n]*$","",text)
    text=re.sub(r"(?m)^\s*(?:%[0-9A-Za-z_]+\s*=\s*)?Op[A-Z]\w+[^\n]*$","[SHADER CONTEXT OMITTED]",text)
    text=re.sub(r"(?im)^\s*(?:[0-9a-f]{8,16}[:\s])(?:[0-9a-f]{2,16}[\s,]){8,}[^\n]*$","[MEMORY DUMP OMITTED]",text)
    return "".join(char for char in text if char in "\n\t" or ord(char)>=32).replace("```","'''_log")


def hardware():
    data={"os":platform.platform(),"architecture":platform.machine(),"cpu":platform.processor() or "Unknown",
          "logical_processors":os.cpu_count(),"ram_gib":None,"gpus":[]}
    if os.name!="nt":
        return data
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            data["cpu"]=winreg.QueryValueEx(key,"ProcessorNameString")[0].strip()
    except OSError:pass
    class Memory(ctypes.Structure):
        _fields_=[("length",ctypes.c_ulong),("load",ctypes.c_ulong)]+[(name,ctypes.c_ulonglong) for name in
            ("physical","available","pagefile","available_pagefile","virtual","available_virtual","extended")]
    memory=Memory();memory.length=ctypes.sizeof(memory)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        data["ram_gib"]=round(memory.physical/1024**3,1)
    class Display(ctypes.Structure):
        _fields_=[("size",ctypes.c_ulong),("name",ctypes.c_wchar*32),("description",ctypes.c_wchar*128),
                  ("flags",ctypes.c_ulong),("id",ctypes.c_wchar*128),("key",ctypes.c_wchar*128)]
    seen=set()
    for index in range(32):
        display=Display();display.size=ctypes.sizeof(display)
        if not ctypes.windll.user32.EnumDisplayDevicesW(None,index,ctypes.byref(display),0):break
        if display.flags&8 or display.description in seen:continue
        seen.add(display.description)
        gpu={"model":display.description,"driver":"Unknown",
             "virtual":any(word in display.description.casefold() for word in ("virtual","remote","mirror"))}
        try:
            key_path=display.key.removeprefix("\\Registry\\Machine\\")
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,key_path) as key:
                gpu["driver"]=winreg.QueryValueEx(key,"DriverVersion")[0]
                try:
                    size=winreg.QueryValueEx(key,"HardwareInformation.qwMemorySize")[0]
                    if isinstance(size,bytes):size=int.from_bytes(size,"little")
                    gpu["vram_gib"]=round(size/1024**3,1)
                except OSError:pass
        except OSError:pass
        data["gpus"].append(gpu)
    return data


def read_log(path, maximum=MAX_LOG):
    with path.open("rb") as stream:
        head=stream.read(min(4000,maximum))
        if b"\0" in head or head.startswith((b"MZ",b"NSO0",b"NUP\1",b"PFS0",b"\x7fELF")):
            raise ValueError("Binary data refused in diagnostic log")
        size=stream.seek(0,2)
        if size>len(head):
            stream.seek(max(len(head),size-(maximum-len(head))))
            tail=stream.read(maximum-len(head))
            data=head+(b"\n[... bounded log excerpt ...]\n" if size>maximum else b"\n")+tail
        else:data=head
    return sanitize(data.decode("utf-8",errors="replace"))


def collect(root, executable="", incident=None):
    metadata={"versions":{"launcher":COMPONENTS["launcher"]["version"],"engine":COMPONENTS["engine"]["version"],
        "base_engine":COMPONENTS["engine"]["base_version"],"buildkit":COMPONENTS["buildkit"]["version"]},
        "system":hardware(),"incident":incident or {},
              "collected_utc":datetime.now(timezone.utc).isoformat()}
    paths=[];folder=Path(executable).parent if executable else None
    if folder:
        try:
            info=json.loads((folder/"dekuforge-build-info.json").read_text(encoding="utf-8"))
            metadata["game_build"]={key:info[key] for key in ("engine_version","base_engine_version","game_version","build_id","runtime_sha256") if key in info}
        except (OSError,ValueError):pass
        config=folder/"nx2navi.ini"
        if config.is_file():
            with config.open("rb") as stream:ini=stream.read(65536).decode("utf-8",errors="replace")
            names={"game_res","dlss","dlaa","framegen","fps_limit","hdr","fullscreen","shadow","taa","fsr4","fsr4_fg","ocarina_realtime","prewarm_full","lib_warm"}
            metadata["graphics_settings"]={match[1]:sanitize(match[2]) for match in re.finditer(r"(?m)^\s*([a-z_]+)\s*=([^\r\n]*)",ini) if match[1] in names}
        for directory in (folder/"logs",):
            if directory.is_dir():paths.extend(p for p in directory.glob("*.log") if p.is_file())
        for name in ("nx2navi.log","DekuForge.log"):
            if (folder/name).is_file():paths.append(folder/name)
        try:metadata["game_disk_free_gib"]=round(shutil.disk_usage(folder).free/1024**3,1)
        except OSError:pass
    local=root/"local"
    for path in (local/"launcher-crash.log",local/"runtime-bootstrap.log"):
        if path.is_file():paths.append(path)
    if (local/"logs").is_dir():paths.extend((local/"logs").glob("*.log"))
    from .update_status import log_paths
    update_logs = log_paths(root, incident or {})
    candidates=update_logs + sorted(set(paths)-set(update_logs),key=lambda p:p.stat().st_mtime,reverse=True)
    logs=[];remaining=24000
    for path in candidates[:3]:
        if path.is_symlink() or path.suffix!=".log":continue
        try:
            text=read_log(path,min(MAX_LOG,remaining));remaining-=len(text)
            logs.append({"name":path.name,"text":text})
        except (OSError,ValueError):continue
        if remaining<=0:break
    return {"metadata":metadata,"logs":logs}


def body(draft, context, log_limit=20000):
    details=sanitize(draft.get("details","").strip())[:12000]
    if not draft.get("title","").strip() or not details:
        raise ValueError("report_required")
    if re.search(r"(?:DEKUFORGE|NX2NAVI)_RECOMP_GENERATED_FROM_GAME_CODE",details):
        raise ValueError("Only diagnostic text is allowed; remove generated game source from the report")
    chunks=["## What happened / reproduction",details,"","## Expected behavior",sanitize(draft.get("expected","").strip())[:4000] or "Not supplied",
            "","## Diagnostics","```json",sanitize(json.dumps(context["metadata"],indent=2)),"```",
            "","No ROMs, game assets, keys, saves, generated game code or compiled game files are attached."]
    if draft.get("include_logs",True):
        remaining=log_limit
        for log in context["logs"]:
            excerpt=log["text"][-remaining:]
            chunks += ["", "## Log: "+log["name"],"```text",excerpt,"```"]
            remaining-=len(excerpt)
            if remaining<=0:break
    return "\n".join(chunks)[:50000]


def browser_url(draft, context):
    # Full report remains exportable; URL transport includes a smaller log excerpt.
    short=dict(draft);short["details"]=draft.get("details","")[:1000];short["expected"]=draft.get("expected","")[:400]
    limit=1000
    prefix=f"https://github.com/{REPOSITORY}/issues/new?"
    title=sanitize(draft["title"].strip())[:180]
    while True:
        report=body(short,context,log_limit=limit)
        url=prefix+urlencode({"title":title,"body":report,"labels":"bug"})
        if len(url)<=7500:return url
        if limit:
            limit=max(0,limit-200)
            if not limit:short["include_logs"]=False
        elif len(short["details"])>200:short["details"]=short["details"][:-100]
        elif len(short["expected"])>100:short["expected"]=short["expected"][:-100]
        else:raise ValueError("Hardware report is too long for a browser URL; export it instead")


def submit(draft, context):
    token=github_token()
    if not token:raise ValueError("report_signin")
    content=body(draft,context)
    request=Request(f"https://api.github.com/repos/{REPOSITORY}/issues",
        data=json.dumps({"title":sanitize(draft["title"].strip())[:180],"body":content}).encode("utf-8"),method="POST",
        headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
                 "Content-Type":"application/json","User-Agent":"DekuForge","X-GitHub-Api-Version":"2022-11-28"})
    with build_opener(AssetRedirect()).open(request,timeout=30) as response:
        data=json.loads(response.read(1024**2))
    url=data.get("html_url","")
    if not re.fullmatch(r"https://github\.com/BrutusBossNL/DekuForge/issues/\d+",url):
        raise ValueError("Unexpected GitHub issue response")
    return url


def record_run(root, process, executable, *, copied_gpu_buffers=False):
    pid=process.pid if isinstance(process.pid,int) else None
    atomic_json(root/"local/last-game-run.json",{"pid":pid,"executable":str(executable),
        "started_utc":datetime.now(timezone.utc).isoformat(),"exit_code":None,
        "copied_gpu_buffers":copied_gpu_buffers})


def _game_incident(state):
    incident = {"kind": "game_exit", "exit_code": state["exit_code"],
                "time": state.get("ended_utc", "")}
    for key in ("gpu_memory_import_errors", "copied_gpu_buffers"):
        if state.get(key):
            incident[key] = state[key]
    if state["exit_code"] & 0xffffffff == 0xc0000409:
        incident["windows_status"] = "0xC0000409"
    return incident


def record_exit(root, code):
    path=root/"local/last-game-run.json"
    try:state=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError):state={}
    state.update(exit_code=int(code),ended_utc=datetime.now(timezone.utc).isoformat())
    if code and state.get("executable") and state.get("started_utc"):
        folder = Path(state["executable"]).parent
        for name in ("nx2navi.log", "DekuForge.log", "hookshot_log.txt"):
            log = folder/name
            try:
                if log.is_symlink() or log.stat().st_mtime < datetime.fromisoformat(state["started_utc"]).timestamp():
                    continue
                count = len(re.findall(r"(?:host memory import failed \(|not imported \(VkResult )-1000072003\)",
                                       read_log(log)))
                if count:
                    state["gpu_memory_import_errors"] = count
                    break
            except (OSError, ValueError):
                continue
    atomic_json(path,state)
    return _game_incident(state) if code else None


def previous_incident(root):
    try:state=json.loads((root/"local/last-game-run.json").read_text(encoding="utf-8"))
    except (OSError,ValueError):state={}
    if state.get("exit_code"):
        return _game_incident(state)
    log=root/"local/launcher-crash.log"
    if log.is_file():return {"kind":"launcher_error_log","time":str(log.stat().st_mtime_ns)}
    return None


def can_retry_copied_buffers(root, executable):
    try:
        run = json.loads((root/"local/last-game-run.json").read_text(encoding="utf-8"))
        return bool(executable and run.get("executable") == str(executable)
                    and run.get("exit_code") and run["exit_code"] & 0xffffffff == 0xc0000409
                    and run.get("gpu_memory_import_errors") and not run.get("copied_gpu_buffers"))
    except (OSError, ValueError):
        return False
