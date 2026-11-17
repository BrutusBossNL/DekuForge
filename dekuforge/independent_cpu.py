"""Original bounded A64 integer/control-flow translator, not a complete CPU.

Encodings and architectural behavior follow the Arm A64 instruction reference.
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
    width: int = 64
    flags: bool = False
    second: int = 0
    mode: int = 0
    memory_size: int = 0
    sign_extend: bool = False
    writeback: int = 0

    @property
    def terminates(self):
        return self.operation in {'b', 'bl', 'br', 'blr', 'ret', 'bcond',
                                  'cbz', 'cbnz', 'tbz', 'tbnz', 'svc'}


def _signed(value, width):
    return value - (1 << width) if value & (1 << (width - 1)) else value


def decode(word):
    if type(word) is not int or not 0 <= word <= 0xffffffff:
        raise ValueError('Instruction must be one unsigned 32-bit word')
    width = 64 if word >> 31 else 32
    rd, rn, rm = word & 31, (word >> 5) & 31, (word >> 16) & 31
    if word & 0x1f800000 == 0x11000000:
        return Instruction('sub' if word & (1 << 30) else 'add', rd, rn,
                           ((word >> 10) & 4095) << (12 if word & (1 << 22) else 0),
                           width=width, flags=bool(word & (1 << 29)))
    if word & 0x1f200000 == 0x0b000000:
        mode, shift = (word >> 22) & 3, (word >> 10) & 63
        if mode != 3 and shift < width:
            return Instruction('subreg' if word & (1 << 30) else 'addreg', rd, rn,
                               shift=shift, width=width, flags=bool(word & (1 << 29)),
                               second=rm, mode=mode)
    if word & 0x1f000000 == 0x0a000000:
        shift = (word >> 10) & 63
        if shift < width:
            return Instruction(('and', 'orr', 'eor', 'ands')[(word >> 29) & 3], rd, rn,
                               immediate=(word >> 21) & 1, shift=shift, width=width,
                               second=rm, mode=(word >> 22) & 3)
    if word & 0x1f800000 == 0x12800000:
        opcode, shift = (word >> 29) & 3, ((word >> 21) & 3) * 16
        if opcode != 1 and shift < width:
            return Instruction({0: 'movn', 2: 'movz', 3: 'movk'}[opcode], rd,
                               immediate=(word >> 5) & 65535, shift=shift, width=width)
    if word & 0x3b000000 == 0x39000000 or word & 0x3b200000 == 0x38000000:
        size, opcode = (word >> 30) & 3, (word >> 22) & 3
        scaled = word & 0x3b000000 == 0x39000000
        mode = 0 if scaled else (word >> 10) & 3
        valid = opcode < 2 or (opcode == 2 and size < 3) or (opcode == 3 and size < 2)
        if valid and mode != 2 and not (mode and rn == rd and rn != 31):
            immediate = (((word >> 10) & 4095) << size) if scaled else _signed((word >> 12) & 511, 9)
            return Instruction('store' if opcode == 0 else 'load', rd, rn, immediate,
                               width=64 if size == 3 or opcode == 2 else 32,
                               mode=mode, memory_size=1 << size, sign_extend=opcode >= 2,
                               writeback=immediate if mode else 0)
    if word & 0x3b000000 == 0x18000000:
        opcode = word >> 30
        if opcode < 3:
            return Instruction('loadliteral', rd, immediate=_signed((word >> 5) & 0x7ffff, 19) * 4,
                               width=64 if opcode else 32, memory_size=8 if opcode == 1 else 4,
                               sign_extend=opcode == 2)
    if word & 0x1f000000 == 0x10000000:
        offset = _signed(((word >> 5) & 0x7ffff) * 4 + ((word >> 29) & 3), 21)
        return Instruction('adrp' if word >> 31 else 'adr', rd, immediate=offset)
    if word & 0x7c000000 == 0x14000000:
        return Instruction('bl' if word >> 31 else 'b', immediate=_signed(word & 0x3ffffff, 26) * 4)
    if word & 0xff000010 == 0x54000000:
        return Instruction('bcond', immediate=_signed((word >> 5) & 0x7ffff, 19) * 4, mode=word & 15)
    if word & 0x7e000000 == 0x34000000:
        return Instruction('cbnz' if word & (1 << 24) else 'cbz', source=rd,
                           immediate=_signed((word >> 5) & 0x7ffff, 19) * 4, width=width)
    if word & 0x7e000000 == 0x36000000:
        return Instruction('tbnz' if word & (1 << 24) else 'tbz', source=rd,
                           immediate=_signed((word >> 5) & 0x3fff, 14) * 4,
                           shift=((word >> 31) << 5) | ((word >> 19) & 31))
    opcode = word & 0xfffffc1f
    if opcode in (0xd61f0000, 0xd63f0000, 0xd65f0000) and rn != 31:
        return Instruction({0xd61f0000: 'br', 0xd63f0000: 'blr', 0xd65f0000: 'ret'}[opcode], source=rn)
    if word & 0xffe0001f == 0xd4000001:
        return Instruction('svc', immediate=(word >> 5) & 65535)
    if word == 0xd503201f:
        return Instruction('nop')
    raise UnsupportedInstruction(f'Unsupported A64 instruction: 0x{word:08x}')


def _read(register, width=64, sp=False):
    value = ('s->sp' if sp else 'UINT64_C(0)') if register == 31 else f's->x[{register}]'
    return f'((uint32_t)({value}))' if width == 32 else value


def _write(register, expression, width=64, sp=False):
    if register == 31 and not sp:
        return []
    target = 's->sp' if register == 31 else f's->x[{register}]'
    return [f'  {target} = (uint{width}_t)({expression});']


def _shift(value, mode, amount, width):
    if not amount:
        return value
    mask = (1 << width) - 1
    if mode == 0:
        return f'(((uint64_t)({value}) << {amount}) & UINT64_C({mask}))'
    if mode == 1:
        return f'({value} >> {amount})'
    if mode == 2:
        # Portable arithmetic right shift without implementation-defined signed shifts.
        sign = 1 << (width - 1)
        return f'(((({value} >> {amount}) ^ UINT64_C({sign >> amount})) - UINT64_C({sign >> amount})) & UINT64_C({mask}))'
    return f'((({value} >> {amount}) | ((uint64_t)({value}) << {width - amount})) & UINT64_C({mask}))'


def _condition(condition):
    n, z, c, v = ('((s->nzcv >> %d) & 1)' % bit for bit in (31, 30, 29, 28))
    expressions = (z, c, n, v, f'({c} && !{z})', f'({n} == {v})', f'(!{z} && ({n} == {v}))', '1')
    value = expressions[condition >> 1]
    return f'!({value})' if condition & 1 and condition != 15 else value


def _body(item, pc, memory=False):
    op, width = item.operation, item.width
    mask = (1 << width) - 1
    next_pc = (pc + 4) & ((1 << 64) - 1)
    lines = []
    if op in {'load', 'store', 'loadliteral'}:
        if not memory:
            raise UnsupportedInstruction('Memory instructions require emit_machine and an explicit address space')
        base = f'UINT64_C({pc})' if op == 'loadliteral' else _read(item.source, sp=True)
        offset = 0 if item.mode == 1 else item.immediate
        # Unsigned addition preserves architectural address wrap; the accessor then
        # rejects out-of-range guest addresses without converting them to host pointers.
        lines += ['  {', f'    uint64_t base = {base};',
                  f'    uint64_t address = base + UINT64_C({offset & ((1 << 64) - 1)});',
                  f'    uint64_t value = {_read(item.destination)};' if op == 'store' else '    uint64_t value = 0;',
                  f'    if (deku_access(m, address, {item.memory_size}, {1 if op == "store" else 0}, &value)) return 3;']
        if item.sign_extend:
            sign = 1 << (item.memory_size * 8 - 1)
            lines += [f'    value = (value ^ UINT64_C({sign})) - UINT64_C({sign});']
        if op != 'store':
            lines += _write(item.destination, 'value', width)
        if item.mode:
            lines += _write(item.source, f'base + UINT64_C({item.writeback & ((1 << 64) - 1)})', sp=True)
        lines += ['  }']
    elif op in {'add', 'sub', 'addreg', 'subreg'}:
        register_form = op.endswith('reg')
        source = _read(item.source, width, sp=not register_form)
        rhs = _shift(_read(item.second, width), item.mode, item.shift, width) if register_form else f'UINT64_C({item.immediate})'
        subtract = op.startswith('sub')
        lines += ['  {', f'    uint64_t a = {source}, b = {rhs};',
                  f'    uint64_t r = (a {"-" if subtract else "+"} b) & UINT64_C({mask});']
        if item.flags:
            carry = 'a >= b' if subtract else 'r < a'
            overflow = '(a ^ b) & (a ^ r)' if subtract else '~(a ^ b) & (a ^ r)'
            lines += [f'    s->nzcv = ((r >> {width - 1}) << 31) | ((uint64_t)(r == 0) << 30)',
                      f'      | ((uint64_t)({carry}) << 29) | ((({overflow}) >> {width - 1}) & 1) << 28;']
        lines += _write(item.destination, 'r', width, sp=not register_form and not item.flags) + ['  }']
    elif op in {'and', 'orr', 'eor', 'ands'}:
        rhs = _shift(_read(item.second, width), item.mode, item.shift, width)
        if item.immediate:
            rhs = f'(~({rhs}) & UINT64_C({mask}))'
        operator = {'and': '&', 'ands': '&', 'orr': '|', 'eor': '^'}[op]
        lines += ['  {', f'    uint64_t r = {_read(item.source, width)} {operator} ({rhs});']
        if op == 'ands':
            lines += [f'    s->nzcv = ((r >> {width - 1}) << 31) | ((uint64_t)(r == 0) << 30);']
        lines += _write(item.destination, 'r', width) + ['  }']
    elif op in {'movz', 'movk', 'movn'}:
        value = item.immediate << item.shift
        expression = f'UINT64_C({value})'
        if op == 'movn':
            expression = f'UINT64_C({mask ^ value})'
        if op == 'movk':
            expression = f'({_read(item.destination, width)} & UINT64_C({mask ^ (65535 << item.shift)})) | {expression}'
        lines += _write(item.destination, expression, width)
    elif op in {'adr', 'adrp'}:
        value = ((pc & ~4095) + (item.immediate << 12)) if op == 'adrp' else pc + item.immediate
        lines += _write(item.destination, f'UINT64_C({value & ((1 << 64) - 1)})')
    elif op in {'br', 'blr', 'ret'}:
        lines += ['  {', f'    uint64_t target = {_read(item.source)};']
        if op == 'blr':
            lines += [f'    s->x[30] = UINT64_C({next_pc});']
        return lines + ['    s->pc = target;', '  }', '  return 0;']
    elif op in {'b', 'bl', 'bcond', 'cbz', 'cbnz', 'tbz', 'tbnz'}:
        target = (pc + item.immediate) & ((1 << 64) - 1)
        condition = '1'
        if op == 'bl':
            lines += [f'  s->x[30] = UINT64_C({next_pc});']
        elif op == 'bcond':
            condition = _condition(item.mode)
        elif op in {'cbz', 'cbnz'}:
            condition = f'({_read(item.source, width)} {"==" if op == "cbz" else "!="} 0)'
        elif op in {'tbz', 'tbnz'}:
            condition = f'((({_read(item.source)} >> {item.shift}) & 1) {"==" if op == "tbz" else "!="} 0)'
        return lines + [f'  s->pc = ({condition}) ? UINT64_C({target}) : UINT64_C({next_pc});', '  return 0;']
    elif op == 'svc':
        # A host service must handle this at the faulting PC; never silently skip it.
        return ['  return 2;']
    elif op != 'nop':
        raise UnsupportedInstruction(op)
    return lines + [f'  s->pc = UINT64_C({next_pc});']


HEADER = ('// DEKUFORGE_' + 'RECOMP_GENERATED_FROM_GAME_CODE\n#include <stdint.h>\n'
          'typedef struct { uint64_t x[31], sp, pc, nzcv; } DekuCpu;\n')


def _block(words, address, limit):
    words = tuple(islice(words, limit + 1))
    if (not 1 <= len(words) <= limit or type(address) is not int or address % 4 or
            not 0 <= address <= (1 << 64) - 1 - 4 * len(words)):
        raise ValueError('Invalid block size or address')
    return [decode(word) for word in words]


def emit_c(words, address=0x1000):
    """Emit one straight-line block ending at a branch or host-service boundary."""
    instructions = _block(words, address, 256)
    if any(item.terminates for item in instructions[:-1]):
        raise ValueError('A block cannot contain instructions after a terminator')
    lines = [HEADER.rstrip(), 'int deku_block(DekuCpu *s) {', f'  if (s->pc != UINT64_C({address})) return 1;']
    for index, item in enumerate(instructions):
        lines += _body(item, address + index * 4)
    if not instructions[-1].terminates:
        lines += ['  return 0;']
    return '\n'.join(lines + ['}']) + '\n'


def _program(words, address, memory):
    instructions = _block(words, address, 4096)
    name = 'deku_machine' if memory else 'deku_run'
    arguments = 'DekuCpu *s, DekuMemory *m, ' if memory else 'DekuCpu *s, '
    lines = [HEADER.rstrip()]
    if memory:
        lines += [MEMORY_HEADER]
    lines += [f'int {name}({arguments}uint64_t budget, uint64_t *executed) {{',
              '  *executed = 0;', '  while (*executed < budget) {', '    switch (s->pc) {']
    for index, item in enumerate(instructions):
        pc = address + index * 4
        body = _body(item, pc, memory)
        if body[-1] == '  return 0;':
            body = body[:-1]
        lines += [f'    case UINT64_C({pc}): {{']
        lines += body
        lines += ['      ++*executed;', '      break;', '    }']
    return '\n'.join(lines + ['    default: return 1;', '    }', '  }', '  return 0;', '}']) + '\n'


def emit_program(words, address=0x1000):
    """Bounded development runner: execute at most budget guest instructions.

    Status: 0 budget exhausted, 1 unknown/misaligned PC, 2 host-service boundary.
    This correctness runner is not the final game's hot-path dispatcher.
    """
    return _program(words, address, False)


def emit_machine(words, address=0x1000):
    """Native correctness runner with explicit, permission-checked guest memory.

    Adds status 3 for memory faults. Failed accesses preserve CPU and guest bytes;
    the memory fault_address records the first denied address. Permissions: R=1,
    W=2, X=4. Host pointers are supplied only by trusted runtime mappings.
    """
    return _program(words, address, True)


MEMORY_HEADER = r'''
typedef struct { uint64_t base, size; uint8_t *data; uint32_t permissions; } DekuRegion;
typedef struct { DekuRegion *regions; uint64_t count, fault_address; } DekuMemory;
static int deku_access(DekuMemory *m, uint64_t address, unsigned size, int write, uint64_t *value) {
    uint8_t *bytes[8];
    if (!m || !size || size > 8) return 1;
    if (address >= (UINT64_C(1) << 39) || size > (UINT64_C(1) << 39) - address || m->count > 4096) {
        m->fault_address = address;
        return 1;
    }
    for (unsigned i = 0; i < size; ++i) {
        bytes[i] = 0;
        for (uint64_t j = 0; j < m->count; ++j) {
            const DekuRegion *r = &m->regions[j];
            uint64_t at = address + i;
            if (at >= r->base && at - r->base < r->size) {
                if ((r->permissions & (write ? 2u : 1u)) && r->data)
                    bytes[i] = &r->data[at - r->base];
                break;
            }
        }
        if (!bytes[i]) { m->fault_address = address + i; return 1; }
    }
    if (write) {
        for (unsigned i = 0; i < size; ++i) *bytes[i] = (uint8_t)(*value >> (8 * i));
    } else {
        *value = 0;
        for (unsigned i = 0; i < size; ++i) *value |= (uint64_t)*bytes[i] << (8 * i);
    }
    return 0;
}
'''
