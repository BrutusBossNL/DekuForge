"""Synthetic MOD0/ELF metadata; no game-derived fixtures."""
import struct
import unittest

from dekuforge.gameplan import FIRST_ADDRESS
from dekuforge.guest_memory import AddressSpace, GuestFault
from dekuforge.guest_linker import inspect_image, link, plan_link


def symbol(name, value=0, section=1, binding=1, kind=2, visibility=0):
    return (name.encode(), binding << 4 | kind, visibility, section, value, 0)


def payload(symbols=(), rela=(), relr=(), pointers=None, gnu=False, extra_tags=None):
    text, ro, data = bytearray(512), bytearray(4096), bytearray(4096)
    struct.pack_into('<I',text,4,64)
    struct.pack_into('<4si',text,64,b'MOD0',64)
    strings, entries = bytearray(b'\0'), [(0,0,0,0,0,0)]
    for name, info, visibility, section, value, size in symbols:
        offset=len(strings);strings.extend(name+b'\0')
        entries.append((offset,info,visibility,section,value,size))
    ro[0x500:0x500+len(strings)]=strings
    for i,entry in enumerate(entries):
        struct.pack_into('<IBBHQQ',ro,0x100+i*24,*entry)
    tags={6:0x1100,11:24,5:0x1500,10:len(strings)}
    if gnu:
        struct.pack_into('<IIIIQ',ro,0xd00,1,1,1,5,0)
        struct.pack_into('<I',ro,0xd18,1 if len(entries)>1 else 0)
        for i in range(len(entries)-1):
            struct.pack_into('<I',ro,0xd1c+i*4,1 if i==len(entries)-2 else 2)
        tags[0x6ffffef5]=0x1d00
    else:
        struct.pack_into('<II',ro,0,1,len(entries))
        tags[4]=0x1000
    if rela:
        for i,entry in enumerate(rela):struct.pack_into('<QQq',ro,0x800+i*24,*entry)
        tags.update({7:0x1800,8:len(rela)*24,9:24})
    if relr:
        for i,entry in enumerate(relr):struct.pack_into('<Q',ro,0xb00+i*8,entry)
        tags.update({36:0x1b00,35:len(relr)*8,37:8})
    tags.update(extra_tags or {})
    for i,entry in enumerate([*tags.items(),(0,0)]):struct.pack_into('<qQ',text,128+i*16,*entry)
    for offset,value in (pointers or {}).items():struct.pack_into('<Q',data,offset-0x2000,value)
    result=bytearray(256);result[:4]=b'NSO0'
    for i,content in enumerate((text,ro,data)):
        struct.pack_into('<III',result,16+i*16,len(result),i*4096,len(content))
        result.extend(content)
    return bytes(result)


class GuestLinkerTests(unittest.TestCase):
    def test_linked_import_executes_natively_across_module_boundaries(self):
        import ctypes
        from dekuforge.independent_cpu import emit_image
        from test_independent_control import State, export, native_library
        from test_independent_memory import Region, Memory
        # LDR X2,[X3]; BLR X2; SVC #7. Provider: ADD X0,X0,#5; RET.
        caller=[0xf9400062,0xd63f0040,0xd40000e1]
        provider=[0x91001400,0xd65f03c0]
        main_raw=bytearray(payload([symbol('function',section=0)],[(0x2000,(1<<32)|1026,0)]))
        sdk_raw=bytearray(payload([symbol('function',value=32)]))
        text_file=struct.unpack_from('<I',main_raw,16)[0]
        struct.pack_into('<III',main_raw,text_file+32,*caller)
        text_file=struct.unpack_from('<I',sdk_raw,16)[0]
        struct.pack_into('<II',sdk_raw,text_file+32,*provider)
        space=AddressSpace()
        main=space.load_nso(bytes(main_raw),'main',FIRST_ADDRESS)
        sdk=space.load_nso(bytes(sdk_raw),'sdk',FIRST_ADDRESS+0x10000)
        link(space)
        buffers=[(ctypes.c_uint8*len(r.data)).from_buffer(r.data) for r in space._regions]
        mappings=(Region*len(buffers))(*[Region(r.base,len(r.data),buffer,
            sum(v for key,v in (('r',1),('w',2),('x',4)) if key in r.permissions))
            for r,buffer in zip(space._regions,buffers)])
        memory=Memory(mappings,len(mappings),0)
        source=export(emit_image([(main.base+32,caller),(sdk.base+32,provider)]),'deku_machine')
        with native_library(self,source) as library:
            function=library.deku_machine
            function.argtypes=[ctypes.POINTER(State),ctypes.POINTER(Memory),ctypes.c_uint64,ctypes.POINTER(ctypes.c_uint64)]
            state,done=State(pc=main.base+32),ctypes.c_uint64()
            state.x[0],state.x[3]=37,main.base+0x2000
            self.assertEqual(function(ctypes.byref(state),ctypes.byref(memory),20,ctypes.byref(done)),2)
            self.assertEqual((state.x[0],state.pc,done.value),(42,main.base+40,4))

    def test_relative_relr_bitmap_and_cross_module_symbol_resolution(self):
        space=AddressSpace()
        main=space.load_nso(payload([symbol('function',section=0)],
            [(0x2000,(1<<32)|1026,4),(0x2020,1027,32)],
            [0x2008,3],{0x2008:64,0x2010:128}), 'main', FIRST_ADDRESS)
        sdk=space.load_nso(payload([symbol('function',value=32)],gnu=True),'sdk',FIRST_ADDRESS+0x10000)
        before=space.read(main.base+0x2000,40)
        plan=plan_link(space)
        self.assertEqual(space.read(main.base+0x2000,40),before)
        self.assertEqual(len(plan),4)
        result=link(space)
        self.assertEqual(result['pointer_relocations'],4)
        self.assertEqual(struct.unpack('<QQQ',space.read(main.base+0x2000,24)),
                         (sdk.base+36,main.base+64,main.base+128))
        self.assertEqual(struct.unpack('<Q',space.read(main.base+0x2020,8))[0],main.base+32)

    def test_unresolved_and_unsupported_relocations_leave_every_module_unchanged(self):
        for kind,syms in ((1031,[symbol('tls',kind=6)]),(1025,[symbol('missing',section=0)])):
            space=AddressSpace()
            first=space.load_nso(payload(rela=[(0x2000,1027,16)]),'main',FIRST_ADDRESS)
            second=space.load_nso(payload(syms,[(0x2000,(1<<32)|kind,0)]),'sdk',FIRST_ADDRESS+0x10000)
            before=[space.read(m.base+0x2000,8) for m in (first,second)]
            with self.assertRaises(GuestFault):link(space)
            self.assertEqual([space.read(m.base+0x2000,8) for m in (first,second)],before)

    def test_weak_undefined_absolute_and_protected_symbols(self):
        space=AddressSpace()
        symbols=[symbol('optional',section=0,binding=2),symbol('absolute',value=42,section=0xfff1),
                 symbol('protected',value=32,visibility=3)]
        main=space.load_nso(payload(symbols,[(0x2000,(1<<32)|257,8),(0x2008,(2<<32)|1025,-2),
            (0x2010,(3<<32)|1026,0),(0x2018,257,19)]),'main',FIRST_ADDRESS)
        space.load_nso(payload([symbol('protected',value=64)]),'sdk',FIRST_ADDRESS+0x10000)
        link(space)
        self.assertEqual(struct.unpack('<QQQQ',space.read(main.base+0x2000,32)),(8,40,main.base+32,19))

    def test_metadata_limits_wrong_owners_and_unsupported_forms(self):
        variants=[payload(extra_tags={8:25,7:0x1800}),payload(extra_tags={35:8,36:0x1b00,37:16}),
                  payload(relr=[3]),payload(rela=[(0x2001,1027,0)]),
                  payload(rela=[(0x2000,1027,0),(0x2000,1027,1)]),
                  payload(rela=[(0,1027,0)]),payload(extra_tags={0x6ffffff0:1}),
                  payload(extra_tags={5:0x10000}),payload(extra_tags={10:17*1024**2})]
        for raw in variants:
            with self.subTest(size=len(raw)):
                space=AddressSpace();module=space.load_nso(raw,'main',FIRST_ADDRESS)
                before=space.read(module.base+0x2000,4096)
                with self.assertRaises(GuestFault):link(space)
                self.assertEqual(space.read(module.base+0x2000,4096),before)

    def test_relr_bitmap_high_bit_advances_exactly_63_words(self):
        offsets=[0x2000,0x2008,0x21f8,0x2200]
        space=AddressSpace()
        module=space.load_nso(payload(relr=[0x2000,3 | 1<<63,3],
            pointers={offset:offset for offset in offsets}),'main',FIRST_ADDRESS)
        self.assertEqual(len(plan_link(space)),4)
        link(space)
        for offset in offsets:
            self.assertEqual(struct.unpack('<Q',space.read(module.base+offset,8))[0],module.base+offset)

    def test_bad_gnu_hash_and_unterminated_strings_fail_before_writes(self):
        for offset,value in ((0xd04,0),(0xd08,0),(0xd18,0xffffffff),(0x100,0xffffffff)):
            raw=bytearray(payload([symbol('f',value=32)],gnu=True))
            ro_file=struct.unpack_from('<I',raw,32)[0]
            struct.pack_into('<I',raw,ro_file+offset,value)
            space=AddressSpace();module=space.load_nso(bytes(raw),'main',FIRST_ADDRESS)
            with self.assertRaises(GuestFault):inspect_image(space,module)
