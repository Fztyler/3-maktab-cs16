"""Keep door frames and hardware proportionate for every physical leaf width."""
from pathlib import Path
import json
import struct
from PIL import Image

root=Path(__file__).resolve().parent

def read_wad(path):
    raw=path.read_bytes()
    magic,count,directory=struct.unpack_from('<4sii',raw)
    assert magic==b'WAD3'
    entries={}
    for i in range(count):
        pos,size,_,kind,compressed,_,label=struct.unpack_from('<iiiBBH16s',raw,directory+i*32)
        assert not compressed
        entries[label.rstrip(b'\0').decode('ascii')]=(kind,raw[pos:pos+size])
    return entries

def open_tile(raw):
    w,h,offset,_,_,last=struct.unpack_from('<6I',raw,16)
    pal=last+w*h//64+2
    im=Image.frombytes('P',(w,h),raw[offset:offset+w*h])
    im.putpalette(raw[pal:pal+768])
    return im.convert('RGB')

def fit_art(im,width,height,style):
    # Normalize the hardware and stiles to a single physical scale. A broad
    # leaf adds space to the center fields while the side details keep shape.
    design_width=round(height*(.66 if style=='ENTRY_DOOR' else .60))
    image=im.resize((design_width,height),Image.Resampling.LANCZOS)
    left=round(design_width*.23)
    right=round(design_width*.31)
    if width<=left+right+2:
        return image.resize((width,height),Image.Resampling.LANCZOS)
    art=Image.new('RGB',(width,height))
    art.paste(image.crop((0,0,left,height)),(0,0))
    art.paste(image.crop((design_width-right,0,design_width,height)),(width-right,0))
    center=image.crop((left,0,design_width-right,height))
    art.paste(center.resize((width-left-right,height),Image.Resampling.BICUBIC),(left,0))
    if style=='TOILET_DOOR':
        # The WC plaque is a discrete fitting, centered at its original height.
        mark_width=round(design_width*.57)
        z0,z1=round(height*.16),round(height*.44)
        a=(design_width-mark_width)//2
        plaque=image.crop((a,z0,a+mark_width,z1))
        art.paste(plaque,((width-mark_width)//2,z0))
    return art

def miptex(name,image):
    w,h=image.size
    palette=image.quantize(colors=256,method=Image.Quantize.MEDIANCUT)
    layers=[image.resize((w>>i,h>>i),Image.Resampling.LANCZOS).quantize(palette=palette).tobytes() for i in range(4)]
    offsets=[40+sum(map(len,layers[:i])) for i in range(4)]
    return struct.pack('<16s6I',name.encode('ascii'),w,h,*offsets)+b''.join(layers)+struct.pack('<H',256)+bytes(palette.getpalette()).ljust(768,b'\0')+b'\0\0'

entry=root/'insomnia_entry.wad'
materials={name:value for name,value in read_wad(entry).items() if not name.startswith('DOOR0')}
styles=read_wad(root/'3_maktab.wad')
fits=json.loads((root/'door_materials.json').read_text())
for name,(style,width,height) in fits.items():
    leaf=fit_art(open_tile(styles[style][1]),width,height,style)
    materials[name]=(67,miptex(name,leaf))
body=bytearray()
directory=[]
for name,(kind,data) in materials.items():
    directory.append(struct.pack('<iiiBBH16s',12+len(body),len(data),len(data),kind,0,0,name.encode('ascii')))
    body.extend(data)
entry.write_bytes(struct.pack('<4sii',b'WAD3',len(directory),12+len(body))+body+b''.join(directory))
print(f'Embedded proportional art for {len(fits)} door variants')
