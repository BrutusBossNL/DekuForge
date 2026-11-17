"""Read-only independent module coverage; never generates or launches a game."""
from collections import Counter
import hashlib
from pathlib import Path
import struct

from .gameplan import (FIRST_ADDRESS, MODULE_ALIGNMENT, MODULE_ORDER,
                       MAX_MODULE_SIZE, inspect_nso)
from .independent_cpu import decode, UnsupportedInstruction
from .modules import normalize_module


def analyze_module(payload, name, base=FIRST_ADDRESS):
    if len(payload) > MAX_MODULE_SIZE:
        raise ValueError('Module exceeds the analysis budget')
    normalized = normalize_module(payload, name)
    metadata = inspect_nso(name, normalized, base)
    text = metadata.segments[0]
    size = text['size']
    data = memoryview(normalized)[text['file_offset']:text['file_offset'] + size - size % 4]
    operations = Counter()
    unsupported = 0
    for word, in struct.iter_unpack('<I', data):
        try:
            operations[decode(word).operation] += 1
        except UnsupportedInstruction:
            unsupported += 1
    return {'name': name, 'build_id': metadata.build_id, 'sha256': hashlib.sha256(payload).hexdigest(),
            'base': base, 'mapped_size': metadata.mapped_size,
            'segments': [{'memory_offset': item['memory_offset'], 'size': item['size']}
                         for item in metadata.segments], 'bss_size': metadata.bss_size,
            'static_text_words': len(data) // 4, 'trailing_text_bytes': size % 4,
            'supported_words': sum(operations.values()), 'unsupported_words': unsupported,
            'operations': dict(sorted(operations.items())),
            'scope': 'Static text includes literal pools; coverage is not executable-code or gameplay validation.'}


def analyze_exefs(directory):
    directory = directory.resolve(strict=True)
    modules, base = [], FIRST_ADDRESS
    for name in MODULE_ORDER:
        path = directory / name
        if not path.exists():
            continue
        if not path.is_file() or path.resolve() != path or path.stat().st_size > MAX_MODULE_SIZE:
            raise ValueError('Analysis input must be a bounded regular module file')
        with path.open('rb') as source:
            payload = source.read(MAX_MODULE_SIZE + 1)
        result = analyze_module(payload, name, base)
        modules.append(result)
        base = (base + result['mapped_size'] + MODULE_ALIGNMENT - 1) // MODULE_ALIGNMENT * MODULE_ALIGNMENT
    if not modules:
        raise ValueError('No executable modules found')
    source = Path(__file__).parent
    fingerprints = {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
                    for name in ('independent_analysis.py', 'independent_cpu.py', 'modules.py', 'gameplan.py')}
    return {'schema': 1, 'backend': 'independent', 'playable': False,
            'source_sha256': fingerprints,
            'writes_game_inputs': False, 'modules': modules,
            'remaining': ['memory/SIMD/FP/atomics instruction coverage', 'complete module linker',
                          'guest services', 'shader translation and Vulkan renderer',
                          'audio/input/movie integration', 'native game linking', 'gameplay parity']}
