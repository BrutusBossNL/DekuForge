"""Original, bounded A64-to-C block translator; deliberately incomplete.

Encoding source: Arm A64 ISA reference (ADD/SUB immediate, MOVZ/MOVK, RET).
No upstream engine decoder, generator or runtime implementation is imported.
"""
from dataclasses import dataclass
from itertools import islice


class UnsupportedInstruction(ValueError):
    pass


@dataclass(frozen=True)
class Instruction:
    operation: str
    destination: int = 0
    source: int = 0
    immediate: int = 0
    shift: int = 0


def decode(word):
    if not isinstance(word, int) or not 0 <= word <= 0xffffffff:
        raise ValueError('Instruction must be one unsigned 32-bit word')
    if word & 0xbf800000 == 0x91000000:
        return Instruction('sub' if word & (1 << 30) else 'add', word & 31,
                           (word >> 5) & 31, ((word >> 10) & 4095) << (12 if word & (1 << 22) else 0))
    if word & 0xff800000 in (0xd2800000, 0xf2800000):
        return Instruction('movz' if word & 0xff800000 == 0xd2800000 else 'movk',
                           word & 31, immediate=(word >> 5) & 65535, shift=((word >> 21) & 3)*16)
    if word & 0xfffffc1f == 0xd65f0000 and (word >> 5) & 31 != 31:
        return Instruction('ret', source=(word >> 5) & 31)
    raise UnsupportedInstruction(f'Unsupported A64 instruction: 0x{word:08x}')


def emit_c(words, address=0x1000):
    """Emit a single straight-line block; unknown instructions stop generation."""
    words = tuple(islice(words, 257))
    if not 1 <= len(words) <= 256 or not isinstance(address, int) or not 0 <= address <= (1 << 64)-1-4*len(words) or address % 4:
        raise ValueError('Invalid block size or address')
    instructions = [decode(word) for word in words]
    if any(item.operation == 'ret' for item in instructions[:-1]):
        raise ValueError('A block cannot contain instructions after a return')
    lines = ['// DEKUFORGE_'+'RECOMP_GENERATED_FROM_GAME_CODE', '#include <stdint.h>',
             'typedef struct { uint64_t x[31], sp, pc, nzcv; } DekuCpu;',
             'int deku_block(DekuCpu *s) {', f'  if (s->pc != UINT64_C({address})) return 1;']
    for index, item in enumerate(instructions):
        target = 's->sp' if item.destination == 31 else f's->x[{item.destination}]'
        source = 's->sp' if item.source == 31 else f's->x[{item.source}]'
        if item.operation in ('add', 'sub'):
            operator = '+' if item.operation == 'add' else '-'
            lines.append(f'  {target} = {source} {operator} UINT64_C({item.immediate});')
        elif item.operation in ('movz', 'movk') and item.destination != 31:
            value = item.immediate << item.shift
            expression = f'UINT64_C({value})'
            if item.operation == 'movk':
                mask = ((1 << 64)-1) ^ (65535 << item.shift)
                expression = f'({target} & UINT64_C({mask})) | {expression}'
            lines.append(f'  {target} = {expression};')
        elif item.operation == 'ret':
            lines += [f'  s->pc = {source};', '  return 0;', '}']
            return '\n'.join(lines)+'\n'
        lines.append(f'  s->pc = UINT64_C({address+4*(index+1)});')
    return '\n'.join(lines+['  return 0;', '}'])+'\n'
