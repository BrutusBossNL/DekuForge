# Original DekuForge map extension, BrutusBossNL (MIT).
"""Prepare native night-only location metadata and crescent badges locally from the player's resources."""
import base64
import hashlib
import json
import struct

TEXTURES = 'UI/Layout2Archive/Common.Product.100.Nin_Ounce_NVN2.bntx.zs'
SHADOWS = ('MapIconCollectHeartPieceCheckSh_00','MapIconCollectSkullSignCheckSh_00')


def byml(blob):
    if blob[:2] not in (b'YB',b'BY'):
        raise ValueError('unrecognized placement resource')
    order='<' if blob[:2]==b'YB' else '>'
    def word(at): return struct.unpack_from(order+'I',blob,at)[0]
    def small(at): return int.from_bytes(blob[at:at+3],'little' if order=='<' else 'big')
    def strings(at):
        return [blob[at+word(at+4+i*4):].split(b'\0',1)[0].decode() for i in range(small(at+1))] if at else []
    keys,values=strings(word(4)),strings(word(8))
    def scalar(kind,value):
        if kind==0xa0:return values[value]
        if kind==0xd1:return value if value<0x80000000 else value-0x100000000
        if kind==0xd2:return struct.unpack(order+'f',struct.pack(order+'I',value))[0]
        if kind==0xd4:return struct.unpack_from(order+'q',blob,value)[0]
        if kind==0xd5:return struct.unpack_from(order+'Q',blob,value)[0]
        if kind==0xd6:return struct.unpack_from(order+'d',blob,value)[0]
        if kind in (0xd0,0xd3):return value
        if kind in (0xc0,0xc1):return node(value)
        if kind==0xff:return None
        return None
    def node(at):
        kind,count=blob[at],small(at+1)
        if kind==0xc1:return {keys[small(at+4+i*8)]:scalar(blob[at+7+i*8],word(at+8+i*8)) for i in range(count)}
        if kind==0xc0:
            start=(at+4+count+3)&~3
            return [scalar(blob[at+4+i],word(start+4*i)) for i in range(count)]
        raise ValueError('unsupported placement node')
    return node(word(12))


def night_ids(romfs):
    found=set()
    for path in romfs.paths():
        if not (path.startswith('Banc/') and path.endswith('.bcett.byml.zs')):continue
        blob,_=romfs.load(path)
        if b'Enemy_Skulltula_Gold_Nocturnal' not in blob:continue
        data=byml(blob)
        if not isinstance(data,dict):continue
        for actor in data.get('Actors',[]):
            if actor.get('Gyaml')=='Enemy_Skulltula_Gold' and actor.get('Dynamic',{}).get('Enemy_Skulltula_Gold_Nocturnal'):
                found.add(actor['Hash'])
    if not found or len(found)>1000:raise ValueError('night-only Skulltula placements missing or changed')
    return sorted(found)


def badge(image):
    """Draw a code-defined crescent beside the native skull/check, preserving both meanings."""
    from PIL import Image,ImageDraw,ImageFilter,ImageChops
    size=256
    canvas=Image.new('RGBA',(size,size))
    bounds=image.getchannel('A').point(lambda a:255 if a>16 else 0).getbbox()
    crop=image.crop(bounds)
    scale=204/max(crop.size)
    crop=crop.resize((round(crop.width*scale),round(crop.height*scale)),Image.Resampling.LANCZOS)
    canvas.alpha_composite(crop,(size-crop.width,size-crop.height))
    mask=Image.new('L',(size,size));draw=ImageDraw.Draw(mask)
    draw.ellipse((2,2,101,101),fill=255)
    cut=Image.new('L',(size,size));ImageDraw.Draw(cut).ellipse((32,-8,120,80),fill=255)
    mask=ImageChops.subtract(mask,cut)
    outline=mask.filter(ImageFilter.MaxFilter(9))
    stroke=Image.new('RGBA',(size,size),(35,25,12,0));stroke.putalpha(outline)
    moon=Image.new('RGBA',(size,size),(255,229,130,0));moon.putalpha(mask)
    canvas.alpha_composite(stroke);canvas.alpha_composite(moon)
    return canvas.resize((64,64),Image.Resampling.LANCZOS)


def texture_patch(textures):
    from .world_assets_codec import bntx_textures, texture_image, pack_icon
    entries=bntx_textures(textures)
    count,table=struct.unpack_from('<IQ',textures,0x24)
    infos={}
    for i in range(count):
        info=struct.unpack_from('<Q',textures,table+8*i)[0]
        at=struct.unpack_from('<Q',textures,info+0x60)[0]
        name=textures[at+2:at+2+struct.unpack_from('<H',textures,at)[0]].decode()
        infos[name]=info
    patches=[]
    for target,source in zip(SHADOWS,('MapIconCollectSkullSign_00','MapIconCollectSkullSignCheck_00')):
        old,new=entries[target],entries[source]
        if old['fmt']!=0x1d01 or old['size']<4096 or new['fmt']!=0x2d06 or new['mips']!=1:
            raise ValueError('collectible icon texture format changed')
        image = badge(texture_image(textures, new))
        properties=bytearray(textures[infos[source]+0xc:infos[source]+0x60])
        struct.pack_into('<II',properties,0x24-0xc,64,64)
        struct.pack_into('<I',properties,0x34-0xc,1)
        struct.pack_into('<I',properties,0x50-0xc,old['size'])
        struct.pack_into('<I',properties,0x54-0xc,struct.unpack_from('<I',textures,infos[target]+0x54)[0])
        pixels = pack_icon(image, old['size'])
        original=textures[infos[target]+0xc:infos[target]+0x60]+textures[old['start']:old['start']+old['size']]
        patches.append(dict(name=target,old=hashlib.sha256(original).hexdigest(),
                            properties=base64.b64encode(properties).decode(),pixels=base64.b64encode(pixels).decode()))
    return patches


def apply_texture_patch(textures,patches):
    from .world_assets_codec import bntx_textures
    entries=bntx_textures(textures)
    count,table=struct.unpack_from('<IQ',textures,0x24)
    infos={}
    for i in range(count):
        info=struct.unpack_from('<Q',textures,table+8*i)[0]
        at=struct.unpack_from('<Q',textures,info+0x60)[0]
        name=textures[at+2:at+2+struct.unpack_from('<H',textures,at)[0]].decode();infos[name]=info
    result=bytearray(textures)
    for patch in patches:
        info=infos[patch['name']];t=entries[patch['name']]
        properties,pixels=map(base64.b64decode,(patch['properties'],patch['pixels']))
        old=textures[info+0xc:info+0x60]+textures[t['start']:t['start']+t['size']]
        if old==properties+pixels:continue
        if hashlib.sha256(old).hexdigest()!=patch['old'] or len(pixels)!=t['size']:
            raise ValueError('collectible icon texture differs from the prepared original')
        result[info+0xc:info+0x60]=properties
        result[t['start']:t['start']+t['size']]=pixels
    assert len(result)==len(textures)
    return bytes(result)
