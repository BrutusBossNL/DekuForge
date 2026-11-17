import ctypes
from itertools import repeat
import json
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from dekuforge.independent_cpu import decode, emit_c, UnsupportedInstruction
from dekuforge import engine
from dekuforge.independent_engine import report


class IndependentContractTests(unittest.TestCase):
    def test_doctor_reports_missing_stages_without_claiming_a_playable_game(self):
        result = engine.engine_report()
        self.assertEqual(result['backend'], 'independent')
        self.assertFalse(result['playable_build_available'])
        self.assertFalse(result['upstream_fallback'])
        self.assertIn('vulkan_renderer', result['missing'])

    def test_incomplete_build_does_not_extract_download_or_fall_back(self):
        events = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with patch('dekuforge.stable_engine.build_stable') as vendor, patch('dekuforge.engine.prepare_game') as extract:
                with self.assertRaisesRegex(RuntimeError, 'independent_backend_incomplete'):
                    engine.build_independent(root/'own.nup', lambda *args:events.append(args),workspace=root)
                vendor.assert_not_called();extract.assert_not_called()
            self.assertEqual(list(root.iterdir()), [])
        self.assertTrue(events)

    def test_unknown_or_neighboring_instructions_stop_before_output(self):
        for word in (0, 0xffffffff, 0xb1000400, 0x11000400, 0x92800000, 0xd65f03e0):
            with self.assertRaises(UnsupportedInstruction): emit_c([word])
        for words in ([], [0xd65f03c0,0x91000400], [0x91000400]*257):
            with self.assertRaises(ValueError): emit_c(words)
        with self.assertRaises(ValueError): emit_c(repeat(0x91000400))
        for address in (-1, 1, 2**64, 4096.0, 2**64-4):
            with self.assertRaises(ValueError): emit_c([0x91000400], address)
        self.assertEqual(decode(0x91000400).operation, 'add')
        self.assertIn('UINT64_C(18446744073709486080)', emit_c([0xf2800000]))

    def test_packaging_and_vendor_tool_preparation_are_blocked(self):
        from tools import build_setup, prepare_installation, package_launcher
        with self.assertRaisesRegex(RuntimeError, 'not ready'): build_setup.main()
        with patch('dekuforge.stable_engine.stage_stable') as vendor:
            with self.assertRaisesRegex(RuntimeError, 'No NX2navi'): prepare_installation.main()
            vendor.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'not a distributable'): package_launcher.package()

    def test_native_c_matches_independent_arm64_oracle(self):
        compiler = os.environ.get('DEKUFORGE_TEST_CC') or shutil.which('clang') or shutil.which('cc')
        if not compiler: self.skipTest('C compiler unavailable')
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
        import unicorn.arm64_const as arm
        words = []
        for sub in (0,1):
            for rn in (0,1,30,31):
                for rd in (0,1,30,31):
                    for shift in (0,1):
                        for immediate in (0,1,4095):
                            words.append(0x91000000 | sub<<30 | shift<<22 | immediate<<10 | rn<<5 | rd)
        for keep in (0,1):
            for rd in (0,1,30,31):
                for shift in range(4):
                    for immediate in (0,1,65535):
                        words.append(0xd2800000 | keep<<29 | shift<<21 | immediate<<5 | rd)
        words += [0xd65f0000 | rn<<5 for rn in (0,1,30)]
        header = emit_c([words[0]]).split('int deku_block',1)[0]
        functions = [emit_c([word]).split('int deku_block',1)[1] for word in words]
        export = '__declspec(dllexport) ' if os.name == 'nt' else ''
        text = header+'\n'.join(export+'int deku_'+str(i)+body for i,body in enumerate(functions))
        class State(ctypes.Structure):
            _fields_ = [('x',ctypes.c_uint64*31),('sp',ctypes.c_uint64),('pc',ctypes.c_uint64),('nzcv',ctypes.c_uint64)]
        cpu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        cpu.mem_map(0x1000,0x3000)
        registers = [getattr(arm,'UC_ARM64_REG_X'+str(i)) for i in range(31)]
        randomizer = random.Random(17112026)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve();source=root/'blocks.c';source.write_text(text)
            library=root/('blocks.dll' if os.name=='nt' else 'blocks.so')
            command=[str(compiler),'-O2','-shared',str(source),'-o',str(library)]
            if os.name!='nt': command.insert(1,'-fPIC')
            result=subprocess.run(command,capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stderr)
            native=ctypes.CDLL(str(library))
            try:
                for index,word in enumerate(words):
                    function=getattr(native,'deku_'+str(index));function.argtypes=[ctypes.POINTER(State)];function.restype=ctypes.c_int
                    for iteration in range(4):
                        values=[randomizer.getrandbits(64) for _ in range(31)]
                        if decode(word).operation=='ret': values[decode(word).source]=0x2000
                        stack=randomizer.getrandbits(64) & ~15
                        state=State((ctypes.c_uint64*31)(*values),stack,0x1000,0xa0000000)
                        for register,value in zip(registers,values): cpu.reg_write(register,value)
                        cpu.reg_write(arm.UC_ARM64_REG_SP,stack);cpu.reg_write(arm.UC_ARM64_REG_NZCV,state.nzcv)
                        cpu.mem_write(0x1000,struct.pack('<I',word));cpu.ctl_remove_cache(0x1000,0x1004)
                        cpu.emu_start(0x1000,0x1004,count=1)
                        self.assertEqual(function(ctypes.byref(state)),0)
                        self.assertEqual(list(state.x),[cpu.reg_read(register) for register in registers],hex(word))
                        self.assertEqual(state.sp,cpu.reg_read(arm.UC_ARM64_REG_SP),hex(word))
                        self.assertEqual(state.pc,cpu.reg_read(arm.UC_ARM64_REG_PC),hex(word))
                        self.assertEqual(state.nzcv,cpu.reg_read(arm.UC_ARM64_REG_NZCV),hex(word))
                        before=bytes(state)
                        self.assertEqual(function(ctypes.byref(state)),1)
                        self.assertEqual(bytes(state),before)
            finally:
                if os.name=='nt':
                    import _ctypes
                    _ctypes.FreeLibrary(native._handle)
