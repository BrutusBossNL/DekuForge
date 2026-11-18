"""Finish the Windows driver's ordinary-play cache before reporting a build ready.

The pinned provider deliberately does not accept its prepare-only cache as an
ordinary-play cache on NVIDIA. Let the real runtime finish its own validation;
never manufacture its completion marker or disable pipeline waits.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid


def ready(status):
    return (status.get('ok') is True and type(status.get('frame')) is int
            and status['frame'] >= 2 and type(status.get('replayed')) is int
            and status['replayed'] >= 2 and isinstance(status.get('renderer'), str)
            and 'Vulkan' in status['renderer'])


class Control:
    def __init__(self, name):
        import ctypes
        import msvcrt
        self.stream = open('\\\\.\\pipe\\'+name, 'r+b', buffering=0)
        self.handle = msvcrt.get_osfhandle(self.stream.fileno())
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.PeekNamedPipe.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong,
                                             ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p]
        self.kernel.PeekNamedPipe.restype = ctypes.c_int
        self.sequence = 0

    def request(self, command, timeout=10):
        import ctypes
        self.sequence += 1
        self.stream.write((json.dumps({'id': self.sequence, 'cmd': command})+'\n').encode('utf-8'))
        deadline = time.monotonic()+timeout
        data = bytearray()
        while time.monotonic() < deadline:
            available = ctypes.c_ulong()
            if not self.kernel.PeekNamedPipe(self.handle, None, 0, None, ctypes.byref(available), None):
                raise OSError('Build runtime control pipe closed')
            if not available.value:
                time.sleep(.02)
                continue
            byte = self.stream.read(1)
            if not byte:
                raise OSError('Build runtime control pipe closed')
            if byte == b'\n':
                reply = json.loads(data)
                if not isinstance(reply, dict) or reply.get('id') != self.sequence:
                    raise ValueError('Unexpected build runtime control reply')
                return reply
            data.extend(byte)
            if len(data) > 1024*1024:
                raise ValueError('Oversized build runtime control reply')
        raise TimeoutError('Build runtime control timed out')

    def close(self):
        self.stream.close()


def warm(executable, work, notify, *, timeout=3600):
    if os.name != 'nt':
        raise RuntimeError('Ordinary-play cache acceptance currently requires Windows')
    from .open_engine_runtime import launch_options
    executable, work = Path(executable), Path(work)
    options = launch_options(executable)
    if options is None:
        raise ValueError('Build runtime metadata is required for cache acceptance')
    # No user save/configuration is opened by this preparation process.
    user = work/'.dekuforge-cache-user'
    user.mkdir(exist_ok=True)
    if user.resolve() != user:
        raise ValueError('Cache preparation profile must not be a link')
    arguments = list(options['args'])
    arguments[arguments.index('--user')+1] = str(user)
    name = 'dekuforge-build-'+uuid.uuid4().hex
    env = dict(options['env'], HOS_CONTROL=name, HOS_AUDIO='0', HOS_WINDOW_NOACTIVATE='1')
    notify('phase', {'phase': 'pipelines', 'done': 0, 'total': 0})
    notify('log', 'Validating the ordinary-play driver cache; first-time preparation can take several minutes.\n')
    control = None
    log_path = work/'dekuforge-play-cache.log'
    started = time.monotonic()
    try:
        with log_path.open('w', encoding='utf-8') as log:
            with subprocess.Popen(arguments, cwd=executable.parent, env=env, stdout=log, stderr=subprocess.STDOUT,
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)) as process:
                try:
                    with log_path.open(encoding='utf-8', errors='replace') as reader:
                        while process.poll() is None and time.monotonic()-started < timeout:
                            for line in reader:
                                notify('log', line)
                                match = re.search(r'start-up: pipelines (\d+) of (\d+)', line)
                                if match:
                                    notify('progress', {'phase': 'pipelines', 'done': int(match[1]), 'total': int(match[2])})
                            if control is None:
                                try:
                                    control = Control(name)
                                except OSError:
                                    time.sleep(.25)
                                    continue
                            if ready(control.request('status')):
                                control.request('quit')
                                if process.wait(timeout=30) != 0:
                                    raise RuntimeError('Cache validation runtime did not exit normally')
                                notify('log', 'Ordinary-play driver cache validated and runtime exited normally.\n')
                                return {'ordinary_play_cache_validated': True,
                                        'validation_seconds': round(time.monotonic()-started, 2)}
                            time.sleep(.25)
                    raise RuntimeError('Runtime did not present frames after cache preparation; see '+str(log_path))
                finally:
                    if process.poll() is None:
                        if control is not None:
                            try:
                                control.request('quit', timeout=2)
                                process.wait(timeout=30)
                            except (OSError, ValueError, TimeoutError, subprocess.TimeoutExpired):
                                pass
                        if process.poll() is None:
                            # Only this function's new child, never an existing game.
                            process.terminate()
                            process.wait(timeout=15)
    finally:
        if control is not None:
            control.close()
