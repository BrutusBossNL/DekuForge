"""Original bounded MOD0/ELF64 linking model; no upstream linker code is used.

Only ordinary AArch64 pointer relocations and RELR are supported. TLS, IFUNC,
instruction relocations and symbol-version semantics must not be guessed.
"""
from dataclasses import dataclass
import struct

from .guest_memory import GuestFault

MAX_SYMBOLS = 262144
MAX_RELOCATIONS = 1000000
MAX_STRINGS = 16 * 1024**2
GNU_HASH = 0x6ffffef5


@dataclass(frozen=True)
class Symbol:
    name: bytes
    info: int
    visibility: int
    section: int
    value: int
    size: int

    @property
    def binding(self):
        return self.info >> 4


@dataclass(frozen=True)
class Image:
    module: object
    tags: dict
    symbols: tuple
    rela: tuple
    relr: tuple


def _read(space, module, offset, size):
    if offset < 0 or size < 0 or offset + size > module.mapped_size:
        raise GuestFault('Link metadata exceeds its module')
    address = module.base + offset
    if any(region.owner != module.name for region, *_ in space._spans(address, size, 'r')):
        raise GuestFault('Link metadata belongs to another module')
    return space.read(address, size)


def _symbol_count(space, module, tags):
    if 4 in tags:
        buckets, count = struct.unpack('<II', _read(space, module, tags[4], 8))
        if not 0 < buckets <= MAX_SYMBOLS or not 0 < count <= MAX_SYMBOLS:
            raise GuestFault('Invalid SysV symbol hash dimensions')
        _read(space, module, tags[4]+8, 4*(buckets+count))
        return count
    if GNU_HASH not in tags:
        raise GuestFault('No bounded dynamic symbol extent')
    offset = tags[GNU_HASH]
    buckets, first, bloom, shift = struct.unpack('<IIII', _read(space, module, offset, 16))
    if (not 0 < buckets <= MAX_SYMBOLS or not 0 < first <= MAX_SYMBOLS or
            not 0 < bloom <= MAX_SYMBOLS or bloom & (bloom-1) or shift >= 64):
        raise GuestFault('Invalid GNU symbol hash dimensions')
    table = offset+16+8*bloom
    heads = struct.unpack('<'+'I'*buckets, _read(space, module, table, 4*buckets))
    chains = table+4*buckets
    seen, count = set(), first
    for head in heads:
        if not head:
            continue
        index = head
        while True:
            if index < first or index >= MAX_SYMBOLS or index in seen:
                raise GuestFault('Invalid or overlapping GNU symbol hash chains')
            seen.add(index)
            value, = struct.unpack('<I', _read(space, module, chains+4*(index-first), 4))
            count = max(count, index+1)
            if value & 1:
                break
            index += 1
    return count


def inspect_image(space, module):
    mod0, = struct.unpack('<I', _read(space, module, 4, 4))
    magic, relative = struct.unpack('<4si', _read(space, module, mod0, 8))
    if magic != b'MOD0':
        raise GuestFault('Module has no MOD0 header')
    dynamic = mod0+relative
    tags = {}
    for index in range(4096):
        tag, value = struct.unpack('<qQ', _read(space, module, dynamic+index*16, 16))
        if not tag:
            break
        if tag == 1:  # DT_NEEDED: all dependency modules must already be mapped.
            continue
        if tag in tags:
            raise GuestFault('Duplicate dynamic metadata tag')
        tags[tag] = value
    else:
        raise GuestFault('Unterminated dynamic table')
    # REL, Android packed tables and symbol versioning have no implementation yet.
    if any(tags.get(tag) for tag in (17,18,19,0x6000000f,0x60000010,0x60000011,0x60000012,
                                     0x6ffffff0,0x6ffffffc,0x6ffffffe)):
        raise GuestFault('Unsupported relocation or symbol-version metadata')
    rela = []
    for pointer, length in ((7,8),(23,2)):
        size = tags.get(length,0)
        if size:
            if pointer not in tags or size % 24 or tags.get(9,24) != 24 or (pointer == 23 and tags.get(20) != 7):
                raise GuestFault('Invalid RELA table description')
            if size//24 + len(rela) > MAX_RELOCATIONS:
                raise GuestFault('Too many RELA entries')
            rela.extend(struct.iter_unpack('<QQq', _read(space,module,tags[pointer],size)))
    relr = ()
    size = tags.get(35,0)
    if size:
        if 36 not in tags or tags.get(37) != 8 or size % 8 or size//8 > MAX_RELOCATIONS:
            raise GuestFault('Invalid RELR table description')
        relr = tuple(value for value, in struct.iter_unpack('<Q',_read(space,module,tags[36],size)))
    symbols = ()
    if 6 in tags:
        if tags.get(11) != 24 or 5 not in tags or not 0 < tags.get(10,0) <= MAX_STRINGS:
            raise GuestFault('Invalid dynamic symbol/string table')
        strings = _read(space,module,tags[5],tags[10])
        raw = _read(space,module,tags[6],_symbol_count(space,module,tags)*24)
        values = []
        for name, info, other, section, value, size in struct.iter_unpack('<IBBHQQ',raw):
            end = strings.find(b'\0',name)
            if name >= len(strings) or end < 0:
                raise GuestFault('Unterminated symbol name')
            values.append(Symbol(strings[name:end],info,other & 3,section,value,size))
        symbols = tuple(values)
    return Image(module,tags,symbols,tuple(rela),relr)


def _address(image, symbol):
    if (symbol.info & 15) not in (0,1,2):
        raise GuestFault('TLS, IFUNC or other unsupported symbol type')
    if symbol.section == 0xfff1:  # SHN_ABS
        return symbol.value
    if not symbol.section or symbol.section >= 0xff00 or symbol.value >= image.module.mapped_size:
        raise GuestFault('Unsupported or out-of-module symbol definition')
    return image.module.base+symbol.value


def plan_link(space):
    """Resolve all supported relocations without changing any guest bytes."""
    if not 0 < len(space.modules) <= 16:
        raise GuestFault('Invalid linked module count')
    images = [inspect_image(space,module) for module in space.modules]
    exports = {}
    for image in images:
        for symbol in image.symbols:
            if symbol.name and symbol.section and symbol.binding in (1,2) and symbol.visibility not in (1,2):
                previous = exports.get(symbol.name)
                if previous is None or previous[1].binding == 2 and symbol.binding == 1:
                    exports[symbol.name] = (image,symbol)
    pending, seen = [], set()

    def append(image, offset, value):
        if len(pending) >= MAX_RELOCATIONS:
            raise GuestFault('Too many expanded relocations')
        address = image.module.base+offset
        if (offset % 8 or offset < 0 or offset+8 > image.module.mapped_size or address in seen
                or not 0 <= value < 1 << 64):
            raise GuestFault('Duplicate, misaligned or invalid relocation')
        if any(r.owner != image.module.name for r,*_ in space._spans(address,8,'w')):
            raise GuestFault('Relocation targets another module')
        seen.add(address)
        pending.append((image.module.base,image.module.name,offset,value))

    for image in images:
        cursor = None
        for entry in image.relr:
            if not entry & 1:
                offsets = (entry,)
                cursor = entry+8
            else:
                if cursor is None:
                    raise GuestFault('RELR bitmap precedes an address')
                start = cursor
                cursor += 63*8
                offsets = (start+8*bit for bit in range(63) if entry & (1 << (bit+1)))
            for offset in offsets:
                addend, = struct.unpack('<Q',_read(space,image.module,offset,8))
                append(image,offset,(image.module.base+addend) & ((1 << 64)-1))
        for offset, info, addend in image.rela:
            kind, index = info & 0xffffffff, info >> 32
            if kind == 0:
                continue
            if kind == 1027 and not index:
                value = image.module.base+addend
            elif kind in (257,1025,1026) and index < len(image.symbols):
                symbol = image.symbols[index]
                if (symbol.info & 15) not in (0,1,2) or symbol.binding not in (0,1,2):
                    raise GuestFault('Unsupported relocation symbol type or binding')
                if index == 0 and not any((symbol.name,symbol.info,symbol.section,symbol.value,symbol.size)):
                    value = 0
                elif symbol.section and (symbol.binding == 0 or symbol.visibility in (1,2,3)):
                    value = _address(image,symbol)
                elif symbol.name in exports:
                    provider, definition = exports[symbol.name]
                    value = _address(provider,definition)
                elif symbol.binding == 2 and not symbol.section:
                    value = 0
                else:
                    raise GuestFault('Unresolved strong import: '+symbol.name.decode('utf-8','replace')[:160])
                value = (value+addend) & ((1 << 64)-1)
            else:
                raise GuestFault('Unsupported AArch64 relocation kind or symbol index')
            append(image,offset,value)
    return tuple(pending)


def link(space):
    plan = plan_link(space)
    space.relocate_pointers(plan)
    return {'modules':len(space.modules),'pointer_relocations':len(plan),'tls_implemented':False}
