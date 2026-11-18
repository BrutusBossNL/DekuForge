"""Provision build wheels only into DekuForge's explicitly owned interpreter."""
from importlib.metadata import PackageNotFoundError, version
import os
from pathlib import Path
import subprocess
import sys

from .core import ROOT
from . import COMPONENTS

PACKAGES = {'numpy': '2.5.4', 'lz4': '4.4.5', 'fonttools': '4.68.0'}


def provision(notify=print):
    missing = []
    for name, expected in PACKAGES.items():
        try:
            if version(name) != expected:
                missing.append(name)
        except PackageNotFoundError:
            missing.append(name)
    if not missing:
        return
    executable = Path(sys.executable).absolute()
    own = ROOT/'python'/COMPONENTS['python']['id']/'python.exe'
    if executable != own or executable.resolve() != executable or not (own.parent/'.dekuforge-runtime.json').is_file():
        raise RuntimeError('Install requirements-open-engine.txt in your chosen development environment; external Python is never modified automatically')
    notify('Installing hash-pinned generic build wheels into the owned DekuForge interpreter.')
    env = dict(os.environ, PIP_CONFIG_FILE=os.devnull, PIP_DISABLE_PIP_VERSION_CHECK='1')
    subprocess.run([str(own), '-I', '-m', 'pip', '--isolated', 'install', '--no-input', '--only-binary=:all:',
                    '--no-deps', '--require-hashes', '-r', str(ROOT/'requirements-open-engine.txt')],
                   env=env, check=True)
    for name, expected in PACKAGES.items():
        if version(name) != expected:
            raise RuntimeError('Generic build dependency verification failed: '+name)
