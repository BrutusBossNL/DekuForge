"""Codecs for locally generated world-map assets, using the pinned provider."""
from pathlib import Path
import struct


def sarc_files(data):
    if data[:6] != b'SARC\x14\x00' or data[6:8] != b'\xff\xfe':
        raise ValueError('Unexpected resource archive')
    base = struct.unpack_from('<I', data, 12)[0]
    count = struct.unpack_from('<H', data, 26)[0]
    names = 40 + 16 * count
    for i in range(count):
        _, name, first, last = struct.unpack_from('<IIII', data, 32 + 16 * i)
        start = names + 4 * (name & 0xffffff)
        end = data.index(0, start, base)
        if not 0 <= first <= last <= len(data) - base:
            raise ValueError('Unexpected resource member bounds')
        yield data[start:end].decode('utf-8'), data[base + first:base + last]


class Romfs:
    def __init__(self, root):
        import zstandard as zs
        self.root = Path(root)
        packed = zs.ZstdDecompressor().decompress(self.raw('Pack/ZsDic.pack.zs'), max_output_size=8 << 20)
        self.dicts = {dictionary.dict_id(): dictionary for _, data in sarc_files(packed)
                      for dictionary in [zs.ZstdCompressionDict(data)]}

    def paths(self):
        yield from (path.relative_to(self.root).as_posix() for path in self.root.glob('Banc/**/*.bcett.byml.zs'))
        yield from (path.relative_to(self.root).as_posix() for path in self.root.glob('Logic/*'))

    def raw(self, name):
        path = self.root/name
        if path.stat().st_size > 128 << 20:
            raise ValueError('World map input exceeds its size limit')
        return path.read_bytes()

    def load(self, name):
        import zstandard as zs
        raw = self.raw(name)
        if not name.endswith('.zs'):
            return raw, None
        dictionary = self.dicts.get(zs.get_frame_parameters(raw).dict_id)
        return zs.ZstdDecompressor(dict_data=dictionary).decompress(raw, max_output_size=192 << 20), dictionary


def compress(blob, dictionary):
    import zstandard as zs
    return zs.ZstdCompressor(level=9, dict_data=dictionary).compress(blob)


def bntx_textures(data):
    import prompt_assets
    return {name: dict(start=start, fmt=fmt, w=width, h=height, gobs=gobs,
                       size=struct.unpack_from('<I', data, info + 0x50)[0],
                       mips=struct.unpack_from('<H', data, info + 0x16)[0])
            for name, (info, fmt, width, height, gobs, start) in prompt_assets.bntx_textures(data).items()}


def texture_image(data, texture):
    import prompt_assets
    return prompt_assets.decode(data, (0, texture['fmt'], texture['w'], texture['h'],
                                       texture['gobs'], texture['start']))


def pack_icon(image, size):
    import prompt_assets
    if image.size != (64, 64) or size < 4096:
        raise ValueError('Unexpected destination for world icon')
    encoded = prompt_assets.encode_astc(image, True)
    pixels = bytearray(size)
    for y in range(16):
        for x in range(16):
            offset = prompt_assets.gob_offset(x * 16, y, 2, 4)
            first = 16 * (16*y + x)
            pixels[offset:offset+16] = encoded[first:first+16]
    return pixels
