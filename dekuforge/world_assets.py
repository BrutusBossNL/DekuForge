"""Prepare and select local map resources without modifying the user's RomFS."""
import hashlib
import json
from pathlib import Path
import re
import struct
import uuid
import zlib

from . import world_byml, world_extra, world_extra_art, world_map_art, world_map_night
from .world_assets_codec import Romfs, compress

ASSET_FOLDER = '.world-markers'
TABLE = 'System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs'
ASSETS = ('Common.bntx', 'Common.blarc', 'extra-world.bin', 'skull-night.bin',
          'overlay/' + world_extra.MAP, 'overlay/' + TABLE)
CONFLICTS = {path.casefold() for path in (world_map_art.ARCHIVE, world_map_night.TEXTURES, world_extra.MAP, TABLE)}


def _raise_sizes(blob, increases):
    result = bytearray(blob)
    if result[:6] != b'RESTBL':
        raise ValueError('Invalid world map resource-size table')
    count = struct.unpack_from('<I', result, 14)[0]
    if count > (len(blob) - 22) // 8:
        raise ValueError('Invalid world map size table bounds')
    for i in range(count):
        at = 22 + i * 8
        key, size = struct.unpack_from('<II', blob, at)
        if key in increases:
            struct.pack_into('<I', result, at+4, size + increases.pop(key))
    if increases:
        raise ValueError('Missing size table entries for the world map')
    return result


def selected(game):
    folder = Path(game)/ASSET_FOLDER
    try:
        receipt = folder/'current.json'
        if not receipt.is_file() or receipt.stat().st_size > 4096:
            return None
        current = json.loads(receipt.read_text(encoding='utf-8'))
        if not re.fullmatch('[0-9a-f]{20}', current['id']):
            return None
        directory = folder/current['id']
        if directory.resolve() != directory or any(len(str(directory/path).encode('utf-8')) >= 260 for path in ASSETS):
            return None
        for path in ASSETS:
            item = directory/path
            if item.resolve() != item or not item.is_file() or item.stat().st_size != current['size'][path]:
                return None
        return directory
    except (OSError, ValueError, KeyError, TypeError):
        return None


def prepare(game, romfs_root, notify):
    """Generate native layout/texture variants and read-only collectible metadata."""
    game = Path(game).absolute()
    romfs = Romfs(romfs_root)
    prompts = game/'prompts'
    table = (prompts/'rsizetable.zs').read_bytes()
    reference = (world_extra.MAP, world_map_art.ARCHIVE, world_map_night.TEXTURES)
    digest = hashlib.sha256(table)
    for path in reference:
        digest.update(hashlib.sha256(romfs.raw(path)).digest())
    for module in (world_extra, world_extra_art, world_map_art, world_map_night, world_byml):
        digest.update(Path(module.__file__).read_bytes())
    for name in (__file__, Path(__file__).with_name('world_assets_codec.py')):
        digest.update(Path(name).read_bytes())
    key = digest.hexdigest()[:20]
    old = selected(game)
    if old and old.name == key:
        return old

    archive, _ = romfs.load(world_map_art.ARCHIVE)
    textures, _ = romfs.load(world_map_night.TEXTURES)

    def ordinary_shadows(body):
        for name in world_map_night.SHADOWS + world_extra_art.SHADOWS:
            old = name.encode() + b'\0'
            new = name.replace('Sh_', '_').encode() + b'\0'
            body = body.replace(old, new.ljust(len(old), b'\0'))
        return body

    layout = world_map_art.archive_replace(archive, world_map_art.MEMBER, world_map_art.collectible_layout, ordinary_shadows)
    layout = world_map_art.archive_replace(layout, world_extra_art.MEMBER, world_extra_art.layout)
    decorated = world_map_night.apply_texture_patch(
        textures, world_map_night.texture_patch(textures) + world_extra_art.textures(textures))
    map_data, dictionary, marker_records, _ = world_extra.build(romfs)
    nocturnal = world_map_night.night_ids(romfs)
    night_records = struct.pack(f'<8sI{len(nocturnal)}Q', b'NXWNT001', len(nocturnal), *nocturnal)
    import zstandard as zs
    table_dictionary = romfs.dicts.get(zs.get_frame_parameters(table).dict_id)
    sizes = zs.ZstdDecompressor(dict_data=table_dictionary).decompress(table, max_output_size=32 << 20)
    paths = ((world_map_art.ARCHIVE, len(layout) - len(archive)),
             (world_extra.MAP, len(map_data) - len(romfs.load(world_extra.MAP)[0])))
    additions = {zlib.crc32(path.removesuffix('.zs').encode()): (delta + 0xfff) & ~0xfff
                 for path, delta in paths if delta > 0}
    changed = _raise_sizes(sizes, additions)
    files = {'Common.bntx': decorated, 'Common.blarc': layout,
             'extra-world.bin': marker_records, 'skull-night.bin': night_records,
             'overlay/' + world_extra.MAP: compress(map_data, dictionary),
             'overlay/' + TABLE: compress(changed, table_dictionary)}
    folder = game/ASSET_FOLDER
    if folder.resolve() != folder:
        raise ValueError('World map output cannot be a link')
    folder.mkdir(exist_ok=True)
    workspace = folder/('stage-' + uuid.uuid4().hex)
    workspace.mkdir()
    product = folder/key
    if product.resolve() != product:
        raise ValueError('World map output cannot be a link')
    for path, data in files.items():
        target = workspace/path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    if product.exists():
        for path in files:
            if (product/path).resolve() != product/path or (product/path).read_bytes() != files[path]:
                raise ValueError('Existing world map cache differs from its generated data')
        for path in sorted(workspace.rglob('*'), key=lambda x: -len(x.parts)):
            (path.rmdir if path.is_dir() else path.unlink)()
        workspace.rmdir()
    else:
        workspace.rename(product)
    from .update_package import atomic_json
    atomic_json(folder/'current.json', {'id': key, 'size': {k: len(v) for k, v in files.items()}})
    notify('log', f'World map artwork and {len(nocturnal)} night-only locations prepared locally\n')
    return product
