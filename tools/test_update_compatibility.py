"""Exercise a previous release's frozen updater against real packages in a temporary app."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dekuforge.update_package import install, validate_package, validate_launcher_health
from dekuforge import COMPONENTS


def previous_release():
    """Keep the oldest supported frozen updater pinned in packaging acceptance."""
    from urllib.request import urlopen
    target = ROOT/'local/build-tools/DekuForge-launcher-0.2.0-windows.zip'
    expected = 'd4b20693da7cbdbfce40734f6a941384ccfca475936e82b8ba55f626e5e8a7a5'
    size = 12556443
    if target.is_file() and target.stat().st_size == size and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    with urlopen('https://github.com/BrutusBossNL/DekuForge/releases/download/v0.2.0/DekuForge-launcher-0.2.0-windows.zip', timeout=90) as response:
        data = response.read(size+1)
    if len(data) != size or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Previous-release package size or hash mismatch')
    target.write_bytes(data)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--candidate', type=Path, default=ROOT/'build/releases'/('DekuForge-launcher-'+COMPONENTS['launcher']['version']+'-windows.zip'))
    parser.add_argument('--runtime', type=Path, default=ROOT/'python'/COMPONENTS['python']['id'])
    parser.add_argument('--known-bad', type=Path)
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('This acceptance test exercises the Windows updater')
    args.previous = args.previous or previous_release()
    previous = validate_package(args.previous)
    candidate = validate_package(args.candidate)
    assert previous['components']['python']['id'] == candidate['components']['python']['id']
    result = {'previous': previous['components']['launcher']['version'],
              'candidate': candidate['components']['launcher']['version']}
    with tempfile.TemporaryDirectory(prefix='update-compatibility-', dir=ROOT/'build') as temporary:
        app = Path(temporary).resolve()
        assert app.parent == (ROOT/'build').resolve()
        install(args.previous, app, log=lambda _: None)
        pin = previous['components']['python']['id']
        shutil.copytree(args.runtime, app/'python'/pin)
        sentinels = {'local/settings.json': b'{"language":"nl","check_updates":false}',
                     'build/existing/profile/save.dat': b'synthetic save; never replace',
                     'local/build-tools/keep.txt': b'synthetic tool cache'}
        for name, data in sentinels.items():
            path = app/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        jobs = app/'local/update-jobs'; jobs.mkdir()
        with zipfile.ZipFile(args.previous) as package:
            frozen_worker = package.read('tools/update_worker.py')
            frozen_package = package.read('dekuforge/update_package.py')

        def update(archive, label):
            job = jobs/label; job.mkdir()
            (job/'worker.py').write_bytes(frozen_worker)
            (job/'update_package.py').write_bytes(frozen_package)
            version = validate_package(archive)['components']['launcher']['version']
            (job/'job.json').write_text(json.dumps({'root': str(app), 'archive': str(archive.resolve()),
                'parent_pid': 0, 'release': 'v'+version, 'restart': False}), encoding='utf-8')
            run = subprocess.run([sys.executable, str(job/'worker.py'), str(job/'job.json')],
                cwd=app, capture_output=True, text=True, timeout=180,
                creationflags=subprocess.CREATE_NO_WINDOW)
            if run.returncode:
                raise RuntimeError(run.stdout+run.stderr)
            return json.loads((app/'local/update-result.json').read_text(encoding='utf-8'))

        if args.known_bad:
            bad = update(args.known_bad, 'known-bad')
            assert bad['success'] is False and 'health check' in bad['error'], bad
            assert json.loads((app/'dekuforge/components.json').read_text()) == previous['components']
            result['known_bad_rollback_reproduced'] = True
        good = update(args.candidate, 'candidate')
        assert good['success'] is True, good
        assert json.loads((app/'dekuforge/components.json').read_text()) == candidate['components']
        proof = json.loads((app/'local/launcher-selftest.json').read_text())
        validate_launcher_health(proof, candidate['components'])
        for name, expected in candidate['sha256'].items():
            assert hashlib.sha256((app/name).read_bytes()).hexdigest() == expected, name
        for name, data in sentinels.items():
            assert (app/name).read_bytes() == data, name
        result.update(success=True, frozen_updater_used=True, settings_saves_tools_preserved=True,
                      legacy_views=len(proof['screens']), mod_views=len(proof.get('mod_screens',[])))
    (ROOT/'local/update-compatibility-check.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
