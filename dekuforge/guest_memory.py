"""Original bounded guest address-space and NSO loading prototype.

This is a correctness model for the independent engine, not its native hot path.
Mappings carry permissions; a rejected write/load/relocation commits no bytes.
"""
from dataclasses import dataclass
from itertools import islice
import struct

from .gameplan import ADDRESS_LIMIT, inspect_nso
from .modules import normalize_module


class GuestFault(ValueError):
    pass


@dataclass
class Region:
    base: int
    data: bytearray
    permissions: str
    owner: str

    @property
    def end(self):
        return self.base + len(self.data)


class AddressSpace:
    def __init__(self, byte_budget=64 * 1024 * 1024):
        if type(byte_budget) is not int or not 0 < byte_budget <= 1024 * 1024 * 1024:
            raise ValueError('Invalid guest memory budget')
        self.byte_budget = byte_budget
        self._regions = []
        self._modules = {}

    @property
    def mappings(self):
        return tuple({'base': r.base, 'size': len(r.data), 'permissions': r.permissions,
                      'owner': r.owner} for r in self._regions)

    @property
    def modules(self):
        return tuple(self._modules.values())

    def relocate_pointers(self, entries):
        """Commit a validated multi-module pointer plan as one model transaction."""
        pending, targets = [], set()
        for index, (base, name, offset, value) in enumerate(entries):
            if index >= 1000000:
                raise GuestFault('Too many pointer relocations')
            module = self._modules.get(base)
            if module is None or module.name != name:
                raise GuestFault('Unknown relocation module')
            if (type(offset) is not int or type(value) is not int or offset < 0 or
                    offset % 8 or offset + 8 > module.mapped_size or not 0 <= value < 1 << 64):
                raise GuestFault('Invalid pointer relocation')
            address = base + offset
            spans = self._spans(address, 8, 'w')
            if address in targets or any(r.owner != name for r, *_ in spans):
                raise GuestFault('Duplicate relocation or wrong module owner')
            targets.add(address)
            pending.append((address, struct.pack('<Q', value)))
        for address, data in pending:
            self.write(address, data)

    def _range(self, address, size):
        if (type(address) is not int or type(size) is not int or size < 0 or
                address < 0 or address >= ADDRESS_LIMIT or size > ADDRESS_LIMIT - address):
            raise GuestFault('Guest range exceeds the address space')

    def _admit(self, candidates):
        regions = sorted(self._regions + candidates, key=lambda r: r.base)
        if sum(len(r.data) for r in regions) > self.byte_budget:
            raise GuestFault('Guest memory budget exceeded')
        for left, right in zip(regions, regions[1:]):
            if left.end > right.base:
                raise GuestFault('Guest mappings overlap')
        self._regions = regions

    def map(self, address, size, permissions='rw', content=b'', owner='anonymous'):
        self._range(address, size)
        if not size or not permissions or set(permissions) - set('rwx') or ('w' in permissions and 'x' in permissions):
            raise GuestFault('Invalid mapping permissions or size')
        if len(content) > size:
            raise GuestFault('Initial bytes exceed the mapping')
        if sum(len(r.data) for r in self._regions) + size > self.byte_budget:
            raise GuestFault('Guest memory budget exceeded')
        if any(address < r.end and address + size > r.base for r in self._regions):
            raise GuestFault('Guest mappings overlap')
        data = bytearray(size)
        data[:len(content)] = content
        self._admit([Region(address, data, permissions, owner)])

    def _spans(self, address, size, permission):
        self._range(address, size)
        if size > self.byte_budget:
            raise GuestFault('Guest access exceeds memory budget')
        spans, cursor, end = [], address, address + size
        for region in self._regions:
            if cursor == end:
                break
            if region.end <= cursor:
                continue
            if region.base > cursor or permission not in region.permissions:
                raise GuestFault('Unmapped guest memory or denied access')
            count = min(end, region.end) - cursor
            spans.append((region, cursor - region.base, count))
            cursor += count
        if cursor != end:
            raise GuestFault('Unmapped guest memory')
        return spans

    def read(self, address, size):
        return b''.join(bytes(r.data[offset:offset + count]) for r, offset, count in self._spans(address, size, 'r'))

    def write(self, address, content):
        content = bytes(content)
        spans = self._spans(address, len(content), 'w')
        cursor = 0
        for region, offset, count in spans:
            region.data[offset:offset + count] = content[cursor:cursor + count]
            cursor += count

    def fetch32(self, address):
        if address % 4:
            raise GuestFault('Misaligned instruction fetch')
        spans = self._spans(address, 4, 'x')
        data = b''.join(bytes(r.data[offset:offset + count]) for r, offset, count in spans)
        return struct.unpack('<I', data)[0]

    def load_nso(self, payload, name, base):
        if not isinstance(name, str) or not name or any(item.name == name for item in self._modules.values()):
            raise GuestFault('Module name must be nonempty and unique')
        if type(base) is not int or base % 4096:
            raise GuestFault('Module base must be a page-aligned guest address')
        self._range(base, 1)
        payload = normalize_module(payload, name)
        metadata = inspect_nso(name, payload, base)
        # Validate the complete mapping and allocation before allocating or committing.
        sizes = [segment['size'] + (metadata.bss_size if i == 2 else 0)
                 for i, segment in enumerate(metadata.segments)]
        self._range(base, metadata.mapped_size)
        if sum(sizes) + sum(len(r.data) for r in self._regions) > self.byte_budget:
            raise GuestFault('Guest memory budget exceeded')
        planned = []
        for index, (segment, size) in enumerate(zip(metadata.segments, sizes)):
            if size:
                start = base + segment['memory_offset']
                self._range(start, size)
                planned.append((start, start + size))
        ranges = sorted(planned + [(r.base, r.end) for r in self._regions])
        if any(left[1] > right[0] for left, right in zip(ranges, ranges[1:])):
            raise GuestFault('Module segments/BSS overlap a mapping')
        candidates = []
        for index, (segment, size) in enumerate(zip(metadata.segments, sizes)):
            if not size:
                continue
            data = bytearray(size)
            offset, count = segment['file_offset'], segment['size']
            data[:count] = payload[offset:offset + count]
            candidates.append(Region(base + segment['memory_offset'], data,
                                     ('rx', 'r', 'rw')[index], name))
        self._admit(candidates)
        self._modules[base] = metadata
        return metadata

    def relocate_relative(self, module_base, module_name, entries):
        """Apply ELF64 RELA (offset, info, signed addend), AArch64 RELATIVE only.

        Symbol, TLS, instruction and cross-module relocations are rejected until
        their implementations exist. There is no permissive placeholder linker.
        """
        self._range(module_base, 1)
        metadata = self._modules.get(module_base)
        if metadata is None or metadata.name != module_name:
            raise GuestFault('Relocations require the exact loaded module identity')
        entries = tuple(islice(entries, 65537))
        if len(entries) > 65536:
            raise GuestFault('Too many relocations')
        pending, targets = [], set()
        for offset, info, addend in entries:
            if (any(type(x) is not int for x in (offset, info, addend)) or offset < 0 or
                    info != 1027 or not -(1 << 63) <= addend < (1 << 63)):
                raise GuestFault('Unsupported or malformed AArch64 RELA relocation')
            address, value = module_base + offset, module_base + addend
            self._range(value, 1)
            if address + 8 > module_base + metadata.mapped_size:
                raise GuestFault('Relocation target exceeds its module mapping')
            if address % 8 or address in targets:
                raise GuestFault('Misaligned or duplicate relocation target')
            spans = self._spans(address, 8, 'w')
            if any(r.owner != module_name for r, *_ in spans):
                raise GuestFault('Relocation target belongs to another module')
            targets.add(address)
            pending.append((address, struct.pack('<Q', value)))
        for address, value in pending:
            self.write(address, value)
