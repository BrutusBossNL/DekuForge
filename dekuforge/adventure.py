"""Read the current adventure from a supported local game save."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import struct

from .saves import is_link
from .world_extra import murmur


# Account used by the pinned Hookshot runtime. Imported profiles are copied into it.
ACCOUNT = '5a3c9e1f0b7d24680000000000000001'
LANGUAGE_ARCHIVES = dict(en='EUen', nl='EUnl', de='EUde', es='EUes', fr='EUfr')
SAVE_LIMIT = 2 << 20
TIME_FIELDS = (0x9811A3F7, 0xDFD840D3, 0xBD46F485, 0x23F3D75E, 0x27853BF7, 0x5EE50BED)
SONGS = ('ZeldaLullaby', 'EponaSong', 'SariaSong', 'SunSong', 'TimeSong', 'StormSong',
         'ForestMinuet', 'FireBolero', 'WaterSerenade', 'ShadowNocturne', 'SpiritRequiem',
         'LightPrelude', 'ScarecrowSong')
FAIRY_GIFTS = ('Item_DinFire', 'Item_FaroreWind', 'Item_NayruLove', 'Item_FairyBless_DefenseDouble')
BOTTLES = (0xF39CE410, 0x000FF6EA, 0xF63B1194, 0xB7F052CE, 0xE27B136D)
UPGRADES = ('Item_Scale_Silver', 'Item_Scale_Gold', 'Item_Wallet_Medium', 'Item_Wallet_Large',
            'Item_BombBag_Large', 'Item_Quiver_Large', 'Item_BulletBag_Large',
            'Item_StickBag_Large', 'Item_NutBag_Large', 'Armor_Child_Gauntlet_Goron',
            'Armor_Adult_Gauntlet_Silver', 'Armor_Adult_Gauntlet_Gold')
DUNGEON_REWARDS = (
    'Item_Stone_Forest', 'Item_Stone_Fire', 'Item_Stone_Water', 'Item_Medal_Forest',
    'Item_Medal_Fire', 'Item_Medal_Water', 'Item_Medal_Shadow', 'Item_Medal_Spirit', 'Item_Medal_Light',
)
EQUIPMENT = (
    'Weapon_Sword_Kokiri', 'Weapon_Sword_Master', 'Weapon_Sword_Biggoron', 'Weapon_Shield_Deku',
    'Weapon_Shield_Hylian', 'Weapon_Shield_Mirror', 'Armor_Adult_Goron', 'Armor_Adult_Zora',
    'Armor_Adult_HeavyBoot', 'Armor_Adult_HoverBoot', 'Weapon_Range_SlingShot', 'Weapon_Range_Bow',
    'Item_Boomerang', 'Item_Hookshot', 'Item_Longshot', 'Item_Hammer', 'Armor_GlassTruth',
    'Item_Arrow_Fire', 'Item_Arrow_Ice', 'Item_Arrow_Light',
)
STORY = (
    ('recap_deku', 'Gohma'), ('recap_dodongo', 'Dodongo'), ('recap_jabu', 'Barinade'),
    ('recap_forest', 'PhantomGanon'), ('recap_fire', 'Volvagia'), ('recap_water', 'Morpha'),
    ('recap_shadow', 'BongoBongo'), ('recap_spirit', 'Twinrova'), ('recap_final', 'Ganon'),
)
SIDE_QUESTS = (
    ('recap_epona', 'Get_Epona'), ('recap_masks', 'SubEvent_MaskSalesman'),
    ('recap_meet_fairy', 'Meet_GreatFairy'), ('recap_scarecrow', 'SubEvent_GetScarecrow'),
    ('recap_biggoron', 'SubEvent_GetSwordBigGoron'), ('recap_well', 'SubEvent_GetStormSong'),
    ('recap_skull_rewards', 'GatheringTokenGold'),
)
EVENT_REWARDS = (
    ('recap_fishing', 'MiniGame_Fishing_GetHeartPiece'),
    ('recap_archery', 'MiniGame_HorseBackArchery_Get_Quiver'),
    ('recap_market_target', 'MiniGame_HitTarget_HrlCity_Get_BulletBag'),
    ('recap_kakariko_target', 'MiniGame_HitTarget_Kakariko_Get_Quiver'),
    ('recap_richard', 'SubEvent_FindRichard_GetHeartPiece'),
)


def read_save(data, data_start):
    if not data_start <= len(data) <= SAVE_LIMIT or struct.unpack_from('<III', data) != (
            0x01020304, 0x002D80EB, data_start):
        raise ValueError('Unsupported adventure save format')
    fields = {}
    kind = 0
    for key, value in struct.iter_unpack('<II', data[40:data_start]):
        if not key:
            if not kind < value <= 32:
                raise ValueError('Invalid adventure save section')
            kind = value
        elif key in fields:
            raise ValueError('Duplicate adventure save field')
        else:
            fields[key] = (kind, value)
    return fields


def _number(fields, key, kind):
    value = fields.get(key if isinstance(key, int) else murmur(key))
    return value[1] if value and value[0] == kind else None


def _flag(fields, key):
    value = _number(fields, key, 0)
    return bool(value) if value in (0, 1) else None


def _binary(fields, data, kind, size):
    keys = [offset for field_kind, offset in fields.values() if field_kind == kind and offset]
    if len(keys) != 1 or not struct.unpack_from('<I', data, 8)[0] <= keys[0] <= len(data) - size:
        return None
    return keys[0]


def _objects(fields, data):
    if [value for kind, value in fields.values() if kind == 32] == [0]:
        return set()
    offset = _binary(fields, data, 32, 8)
    if offset is None or (len(data) - offset) % 8:
        return None
    values = [key for key, in struct.iter_unpack('<Q', data[offset:]) if key]
    return set(values) if values == sorted(set(values)) else None


def _read(path):
    if is_link(path) or not path.is_file():
        raise ValueError('Save entry is not a regular file')
    with path.open('rb') as stream:
        return stream.read(SAVE_LIMIT + 1)


def _area(value):
    return re.sub(r'_(?:Child|Adult|Static|Dynamic|Alternative)(?=_|$)', '', value)


@dataclass(frozen=True)
class Slot:
    name: str
    saved: datetime | None
    auto: bool | None
    scene: str
    thumbnail: bytes
    progress: bytes
    fields: dict


def _caption(data):
    fields = read_save(data, 0x2A0)
    try:
        parts = [_number(fields, key, 2) for key in TIME_FIELDS]
        date = datetime(*parts[:5], parts[5] or 0)
        if not 1980 <= date.year <= 2107:
            date = None
    except (ValueError, TypeError):
        date = None
    scene = data[684:748].split(b'\0', 1)[0].decode('ascii', errors='ignore')
    scene = scene if re.fullmatch(r'[A-Za-z0-9_]{1,64}', scene) else ''
    offset = _binary(fields, data, 18, 4)
    image = b''
    if offset is not None:
        size = struct.unpack_from('<I', data, offset)[0]
        if 2 <= size <= 512 << 10 and size <= len(data) - offset - 4:
            image = data[offset + 4:offset + 4 + size]
            if not image.startswith(b'\xff\xd8'):
                image = b''
    auto = _flag(fields, 0x25F03CAA)
    if auto is None:
        auto = _number(fields, 0x25F03CAA, 2)
    return date, auto, scene, image


def newest_slot(profile):
    if profile.resolve() != profile or not profile.is_dir():
        return None
    slots = []
    for index in range(6):
        folder = profile / f'slot_{index:02d}'
        if is_link(folder) or not folder.is_dir():
            continue
        source = folder / 'progress.sav'
        try:
            before = source.stat()
            progress = _read(source)
            fields = read_save(progress, 0x175D8)
        except (OSError, ValueError):
            continue
        caption = folder / 'caption.sav'
        try:
            caption_before = caption.stat()
            saved, auto, scene, image = _caption(_read(caption))
            caption_after = caption.stat()
            if (caption_before.st_size, caption_before.st_mtime_ns) != (
                    caption_after.st_size, caption_after.st_mtime_ns):
                continue
        except (OSError, ValueError):
            saved, auto, scene, image = None, None, '', b''
        try:
            after = source.stat()
        except OSError:
            continue
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            continue
        slot = Slot(folder.name, saved, None if auto not in (0, 1) else bool(auto),
                    scene, image, progress, fields)
        slots.append(((saved or datetime.min, 0 if saved else after.st_mtime_ns, -index), slot))
    return max(slots, key=lambda entry: entry[0])[1] if slots else None


@dataclass(frozen=True)
class Objective:
    label: str
    done: int
    total: int
    unknown: int = 0
    started: bool = False


def tally(label, states):
    states = tuple(states)
    return Objective(label, states.count(True), len(states), states.count(None))


def _collectible_counter(label, value, total):
    return Objective(label, value, total) if value is not None and 0 <= value <= total else Objective(label, 0, total, total)


def _quest(fields, label, quest):
    value = _number(fields, f'Step_{quest}', 6)
    if value is None:
        return Objective(label, 0, 1, 1)
    complete = value == murmur('Complete')
    return Objective(label, int(complete), 1, started=not complete and value not in (
        0, murmur('NotReady'), murmur('Ready'), murmur('None')))


def _world(romfs, slot):
    from .world_map_night import byml

    world = byml(romfs.load('Banc/BancBasedResource/MapParam.byml.zs')[0])
    flags = _objects(slot.fields, slot.progress)
    hearts = {}
    for zone_name, zone in sorted(world.items()):
        for row in zone.get('CollectHeartAll', ()):
            actor = row.get('ActorHash', 0)
            if row['Type'] == 0 and actor:
                done = actor in flags if flags is not None else None
            elif row['Type'] == 1 and actor:
                done = _flag(slot.fields, f'IsTreasureBoxOpen.{actor}')
            elif row['Type'] == 2 and row.get('GameDataHashName'):
                done = _flag(slot.fields, row['GameDataHashName'])
            else:
                done = None
            identity = row['InstanceID']
            previous = hearts.get(identity)
            if previous is None or previous[1] is None:
                hearts[identity] = (_area(zone_name), done)
            elif done is not None and previous[1] != done:
                raise ValueError('Conflicting heart piece markers')
    heart_states = tuple(hearts.values()) if len(hearts) == 36 else (('', None),) * 36
    skulls = {}
    if flags is not None:
        for path in sorted(romfs.paths()):
            if not path.endswith('.bcett.byml.zs'):
                continue
            data, _ = romfs.load(path)
            if b'Enemy_Skulltula_Gold' in data:
                area = _area(Path(path).name.split('.', 1)[0])
                for actor in byml(data).get('Actors', ()):
                    if actor.get('Gyaml') == 'Enemy_Skulltula_Gold':
                        skulls.setdefault(actor['Hash'], area)
    skull_states = ()
    if flags is not None and len(skulls) == 100 and len(skulls.keys() & flags) == _number(slot.fields, 0x04735978, 2):
        skull_states = tuple((area, identity in flags) for identity, area in skulls.items())
    return heart_states, skull_states


def _area_totals(entries, names):
    totals = {}
    for area, state in entries:
        totals.setdefault(names.get(area, ''), []).append(state)
    return tuple(tally(name, totals[name]) for name in sorted(totals, key=lambda n: (not n, n.casefold())))


def _locations(romfs, language):
    """Read plain UTF-8 location labels from a local message archive."""
    from .world_assets_codec import sarc_files

    prefix = LANGUAGE_ARCHIVES.get(language, 'EUen')
    archive, _ = romfs.load(f'Mals/{prefix}.Product.110.sarc.zs')
    data = next((body for name, body in sarc_files(archive) if name == 'LocationMsg/Location.msbt'), b'')
    if data[:10] != b'MsgStdBn\xff\xfe' or not 32 <= len(data) <= 1 << 20 or data[12] != 0:
        return {}
    sections = {}
    at = 32
    while at + 16 <= len(data):
        size = struct.unpack_from('<I', data, at + 4)[0]
        end = at + 16 + size
        if end > len(data):
            return {}
        sections[data[at:at + 4]] = data[at + 16:end]
        at = (end + 15) & ~15
    labels, texts = sections[b'LBL1'], sections[b'TXT2']
    text_count = struct.unpack_from('<I', texts)[0]
    if not 1 <= text_count <= 4096 or 4 + text_count * 4 > len(texts):
        return {}
    offsets = struct.unpack_from(f'<{text_count}I', texts, 4) + (len(texts),)
    if offsets != tuple(sorted(offsets)) or offsets[0] < 4 + text_count * 4:
        return {}
    result = {}
    group_count = struct.unpack_from('<I', labels)[0]
    if not 1 <= group_count <= 4096 or 4 + group_count * 8 > len(labels):
        return {}
    groups = tuple(struct.iter_unpack('<II', labels[4:4 + group_count * 8]))
    if sum(count for count, _ in groups) > 4096:
        return {}
    for count, cursor in groups:
        for _ in range(count):
            end = cursor + 1 + labels[cursor]
            name = labels[cursor + 1:end].decode('ascii')
            index = struct.unpack_from('<I', labels, end)[0]
            cursor = end + 4
            if index >= text_count:
                continue
            body = texts[offsets[index]:offsets[index + 1]]
            plain = bytearray()
            pos = 0
            while pos < len(body) and body[pos]:
                if body[pos] == 14:
                    pos += 7 + struct.unpack_from('<H', body, pos + 5)[0]
                else:
                    plain.append(body[pos])
                    pos += 1
            value = plain.decode('utf-8').strip()
            if value and value.isprintable():
                result[name] = value
    return result


@dataclass(frozen=True)
class Adventure:
    slot: Slot
    location: str
    max_hearts: int | None
    loose_pieces: int | None
    groups: tuple
    skull_areas: tuple
    heart_areas: tuple


def load_adventure(executable, language):
    from .open_engine_runtime import launch_options
    from .world_assets_codec import Romfs

    options = launch_options(executable)
    if not options:
        return None
    args = options['args']
    slot = newest_slot(Path(args[-1]) / 'save' / ACCOUNT)
    if slot is None:
        return None
    fields = slot.fields
    main = tuple(tally(label, (None if value is None else value > 0,)) for label, boss in STORY
                 for value in [_number(fields, f'DefeatedEnemyNum.Enemy_DungeonBoss_{boss}', 2)])
    side = tuple(_quest(fields, label, name) for label, name in SIDE_QUESTS)
    side += tuple(tally(label, (_flag(fields, key),)) for label, key in EVENT_REWARDS)
    location_names, skulls = {}, ()
    hearts = (('', None),) * 36
    try:
        romfs = Romfs(Path(args[3]))
    except (ImportError, OSError, ValueError, RuntimeError, struct.error):
        romfs = None
    if romfs is not None:
        try:
            location_names = _locations(romfs, language)
        except (KeyError, IndexError, OSError, ValueError, RuntimeError, struct.error):
            pass
        try:
            hearts, skulls = _world(romfs, slot)
        except (KeyError, IndexError, OSError, ValueError, RuntimeError, struct.error):
            pass
    def ever(names):
        return (_flag(fields, f'IsGet.{key}') for key in names)

    magic = _number(fields, 0x12D63A97, 2)
    fairy = (*ever(FAIRY_GIFTS), None if magic is None else magic >= 240,
             None if magic is None else magic >= 480)
    collectibles = (
        _collectible_counter('recap_skulls', _number(fields, 0x04735978, 2), 100),
        tally('recap_heart_pieces', (state for _, state in hearts)),
        tally('recap_dungeon_rewards', ever(DUNGEON_REWARDS)),
        tally('recap_songs', ever(f'Item_Melody_{song}' for song in SONGS)),
        tally('recap_bottles', (_flag(fields, key) for key in BOTTLES)),
        tally('recap_fairy_gifts', fairy),
        tally('recap_upgrades', ever(UPGRADES)),
        tally('recap_equipment', ever(EQUIPMENT)),
    )
    max_life = _number(fields, 'PlayerStatus.MaxLife', 2)
    pieces = _number(fields, 'PouchData.Obj_Heart_Piece.StockNum', 2)
    return Adventure(slot, location_names.get(slot.scene, ''),
                     max_life // 4 if max_life in range(12, 81, 4) else None,
                     pieces if pieces in range(4) else None, (main, side, collectibles),
                     _area_totals(skulls, location_names),
                     _area_totals(hearts, location_names) if any(area for area, _ in hearts) else ())
