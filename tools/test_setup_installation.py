"""Cold-install the real Windows EXE through an aliased/dotted temporary path.

No game input, build-tool download, shortcut or visible launcher is used. The
native setup still verifies/extracts its embedded payload, provisions Python,
installs the application and performs its real hidden launcher health check.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installer',type=Path,default=ROOT/'build/releases/DekuForge-Setup.exe')
    args=parser.parse_args()
    if os.name!='nt':
        parser.error('Windows setup acceptance requires Windows')
    installer=args.installer.resolve()
    work=Path(tempfile.mkdtemp(prefix='setup-acceptance-',dir=ROOT/'build')).resolve()
    if not work.is_relative_to((ROOT/'build').resolve()):
        raise ValueError('Acceptance workspace outside build')
    # Match a user's TEMP layout independently of the source checkout's length.
    temporary=Path(tempfile.mkdtemp(prefix='DekuForgeQA-')).resolve()
    temp_parent=Path(tempfile.gettempdir()).resolve()
    if temporary.parent!=temp_parent:
        raise ValueError('Acceptance TEMP directory outside the selected temp root')
    (temporary/'through').mkdir()
    alias=ctypes.create_unicode_buffer(32768)
    if ctypes.windll.kernel32.GetShortPathNameW(str(temporary),alias,len(alias)):
        temp_argument=alias.value+'\\through\\..'
    else:
        temp_argument=str(temporary/'through/..')
    destination=work/'installed application'
    report={'installer':installer.name,'sha256':hashlib.sha256(installer.read_bytes()).hexdigest(),
            'temporary_path':temp_argument,'used_short_alias':'~' in temp_argument,'tools_skipped':True}
    success=False
    try:
        env=dict(os.environ,TEMP=temp_argument,TMP=temp_argument)
        result=subprocess.run([str(installer),'/SILENT','/NOLAUNCH','/NOSHORTCUT','/SKIPTOOLS',
                               '/DIR='+str(destination)],env=env,timeout=480,check=False)
        logs=sorted(temporary.glob('DekuForge-setup-*/setup.log'))
        log=logs[-1].read_text(encoding='utf-8',errors='replace') if logs else 'No setup log produced'
        report['exit_code']=result.returncode
        report['log']=log
        if result.returncode:
            raise RuntimeError('Native setup failed:\n'+log[-10000:])
        outcome=json.loads((destination/'local/setup-result.json').read_text(encoding='utf-8'))
        health=json.loads((destination/'local/launcher-selftest.json').read_text(encoding='utf-8'))
        report.update(version=outcome['components']['launcher']['version'],healthcheck=health,
                      installed_executable=(destination/'DekuForge.exe').is_file())
        if not outcome['success'] or not health['success'] or health.get('window_was_mapped') or not report['installed_executable']:
            raise RuntimeError('Installed application failed hidden health-check acceptance')
        success=True
        print('Cold native setup passed:',report['version'],'; short alias:',report['used_short_alias'],
              '; hidden health check:',health['success'],flush=True)
    finally:
        report['success']=success
        output=ROOT/'local/setup-installation-acceptance.json'
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        if success:
            # Only the fresh owned acceptance tree; never touch a real install.
            if work.resolve()!=work or not work.is_relative_to(ROOT/'build'):
                raise ValueError('Unsafe acceptance cleanup root')
            for owned in (work,temporary):
                if owned.resolve()!=owned or owned==temporary and owned.parent!=temp_parent:
                    raise ValueError('Unsafe acceptance TEMP cleanup root')
                for base,dirs,files in os.walk(owned,followlinks=False):
                    for name in dirs+files:
                        path=Path(base)/name
                        if path.is_symlink() or getattr(path,'is_junction',lambda:False)():
                            raise ValueError('Acceptance cleanup contains a link')
                shutil.rmtree(owned)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
