"""Create entrance and bombsite signs in one WAD3 file."""

import struct
import sys
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).with_name("vendor")))
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).parent
large = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 29)
small = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 14)


def sign(title, subtitle, bg, fg):
    im = Image.new("RGB", (256, 64), bg)
    draw = ImageDraw.Draw(im)
    draw.rectangle((2, 2, 253, 61), outline=fg, width=4)
    draw.rectangle((7, 7, 248, 56), outline=tuple((a+b)//2 for a,b in zip(bg,fg)), width=2)
    box = draw.textbbox((0,0), title, font=large)
    draw.text(((256-(box[2]-box[0]))/2, 5), title, font=large, fill=fg)
    box = draw.textbbox((0,0), subtitle, font=small)
    draw.text(((256-(box[2]-box[0]))/2, 42), subtitle, font=small, fill=fg)
    return im


def miptex(name, im):
    pal = im if im.mode == "P" else im.quantize(colors=255)
    palette = bytes(pal.getpalette()[:768]).ljust(768, b"\0")
    levels = [pal]
    for divisor in (2,4,8):
        size = (im.width//divisor, im.height//divisor)
        if im.mode == "P":
            levels.append(im.resize(size, Image.Resampling.NEAREST))
        else:
            levels.append(im.resize(size, Image.Resampling.BOX).quantize(palette=pal))
    offsets = [40]
    for level in levels[:-1]:
        offsets.append(offsets[-1] + level.width * level.height)
    namebytes = name.encode("ascii").ljust(16,b"\0")
    body = bytearray(namebytes + struct.pack("<6I",im.width,im.height,*offsets))
    for level in levels:
        body.extend(level.tobytes())
    body.extend(struct.pack("<H",256))
    body.extend(palette)
    while len(body) % 4:
        body.append(0)
    return namebytes, body


def fence():
    im = Image.new("P", (64,64), 255)
    palette = [0,0,0]*256
    palette[3:6] = [72,82,84]
    palette[6:9] = [138,148,151]
    palette[765:768] = [0,0,255]
    im.putpalette(palette)
    draw = ImageDraw.Draw(im)
    for shift in (-64,0,64):
        for k in range(0,65,16):
            draw.line((k+shift,0,k+32+shift,64),fill=1,width=2)
            draw.line((k+shift,64,k+32+shift,0),fill=2,width=2)
    return im


def spray(letter):
    im = Image.new("P", (128,128), 255)
    palette = [0,0,0]*256
    palette[3:6] = [185,28,22]
    palette[6:9] = [128,18,15]
    palette[765:768] = [0,0,255]
    im.putpalette(palette)
    draw = ImageDraw.Draw(im)
    draw.ellipse((8,8,119,119), outline=2, width=8)
    draw.arc((13,13,114,114), 48, 207, fill=1, width=5)
    font = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 79)
    box = draw.textbbox((0,0), letter, font=font)
    draw.text(((128-(box[2]-box[0]))/2-box[0],
               (128-(box[3]-box[1]))/2-box[1]-4), letter, font=font, fill=1,
              stroke_width=2, stroke_fill=2)
    return im


def glass():
    im = Image.new("RGB", (64,64), (102,137,153))
    draw = ImageDraw.Draw(im)
    for d in range(-64,128,22):
        draw.line((d,0,d+64,64),fill=(139,174,189),width=2)
    draw.rectangle((1,1,62,62),outline=(77,112,127),width=2)
    return im


def plaster(base, seed, grain=7):
    rng = random.Random(seed)
    im = Image.new("RGB", (128,128), base)
    pixels = im.load()
    for y in range(128):
        for x in range(128):
            n = rng.randrange(-grain, grain+1)
            pixels[x,y] = tuple(max(0,min(255,c+n)) for c in base)
    return im


def blackboard():
    im = Image.new("RGB", (256,128), (32,68,61))
    d = ImageDraw.Draw(im)
    d.rectangle((2,2,253,125),outline=(122,82,49),width=6)
    font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 21)
    d.text((22,24), "DARS MAVZUSI", font=font, fill=(207,220,201))
    d.line((22,61,234,61), fill=(184,204,179), width=2)
    d.text((25,75), "a² + b² = c²", font=font, fill=(206,217,198))
    return im


def classroom_poster(title, subtitle, color):
    im=Image.new("RGB",(128,128),(230,226,207))
    d=ImageDraw.Draw(im)
    d.rectangle((4,4,123,123),outline=color,width=5)
    d.rectangle((12,12,115,36),fill=color)
    font=ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf",17)
    smallfont=ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf",13)
    d.text((19,14),title,font=font,fill="white")
    d.text((16,48),subtitle,font=smallfont,fill=(55,59,54))
    for row in range(4):
        d.line((18,76+row*10,106-row*7,76+row*10),fill=color,width=2)
    return im


def plank_floor(base, seed, sport=False):
    im=plaster(base,seed,5)
    d=ImageDraw.Draw(im)
    for y in range(0,128,16 if sport else 24):
        d.line((0,y,127,y),fill=tuple(max(0,c-16) for c in base),width=2)
        for x in range(0,128,64):
            offset=32 if (y//16)%2 else 0
            xx=(x+offset)%128
            d.line((xx,y,xx,y+(16 if sport else 24)-2),
                   fill=tuple(max(0,c-9) for c in base),width=1)
    return im


def hall_floor():
    im=plaster((184,179,164),23,5)
    d=ImageDraw.Draw(im)
    for v in (0,64,127):
        d.line((v,0,v,127),fill=(153,148,137),width=2)
        d.line((0,v,127,v),fill=(153,148,137),width=2)
    return im


def classroom_door():
    im=plaster((139,96,57),26,5)
    d=ImageDraw.Draw(im)
    for x in range(5,124,7):
        d.line((x,3,x+2,125),fill=(127+(x%3)*4,85,48),width=1)
    d.rectangle((5,4,122,123),outline=(84,54,32),width=4)
    for box in ((18,15,107,58),(18,70,107,111)):
        d.rectangle(box,outline=(97,62,34),width=3)
    d.rectangle((99,61,106,79),fill=(112,105,85))
    d.rectangle((101,67,117,71),fill=(190,180,144))
    return im


def scoreboard():
    im=Image.new("RGB",(256,128),(31,41,40))
    d=ImageDraw.Draw(im)
    d.rectangle((2,2,253,125),outline=(160,169,151),width=4)
    font=ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf",25)
    digits=ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf",45)
    d.text((29,14),"3-MAKTAB  SPORT",font=font,fill=(232,233,203))
    d.text((68,58),"00 : 00",font=digits,fill=(210,82,63))
    return im


def entry_door():
    im=Image.new('RGB',(128,256),(231,236,229));d=ImageDraw.Draw(im)
    d.rectangle((7,7,120,245),fill=(42,91,125),outline=(174,188,189),width=3)
    d.rectangle((14,16,113,174),fill=(84,130,155))
    d.line((17,22,109,75),fill=(126,160,173),width=3)
    d.line((9,65,119,65),fill=(227,234,230),width=6)
    d.line((9,180,119,180),fill=(227,234,230),width=7)
    d.rectangle((97,158,104,192),fill=(198,206,205))
    return im

def school_roof():
    im=plaster((100,48,44),42,4);d=ImageDraw.Draw(im)
    for y in range(0,128,32):d.line((0,y,127,y),fill=(75,37,35),width=2)
    for x in range(0,128,16):d.line((x,0,x,127),fill=(127,65,59),width=2)
    return im

textures = [
    miptex("ENTRY_DOOR",entry_door()),
    miptex("ROOF_BURGUNDY",school_roof()),
    miptex("MAKTAB_SIGN", sign("3-MAKTAB", "O'ZBEKISTON MAKTABI", (221,227,217), (29,67,100))),
    miptex("SITE_A", sign("A", "KATTA SPORT ZAL", (224,227,216), (127,39,31))),
    miptex("SITE_B", sign("B", "HOJATXONA", (220,226,220), (127,39,31))),
    miptex("{NETFENCE", fence()),
    miptex("{SPRAY_A", spray("A")),
    miptex("{SPRAY_B", spray("B")),
    miptex("WINDOW_GLASS", glass()),
    miptex("SCHOOL_CREAM",plaster((224,217,196),1,5)),
    miptex("SCHOOL_RED",plaster((137,65,55),2,5)),
    miptex("SCHOOL_GREEN",plaster((43,105,70),3,5)),
    miptex("SCHOOL_WHITE",plaster((225,231,223),4,4)),
    miptex("DESK_WOOD",plaster((157,112,69),5,10)),
    miptex("SINK_TILE",plaster((215,224,222),6,3)),
    miptex("CAR_BLUE",plaster((67,101,126),7,4)),
    miptex("CAR_RED",plaster((133,58,51),8,4)),
    miptex("CAR_WHITE",plaster((197,201,193),9,4)),
    miptex("ROAD_WHITE",plaster((214,211,181),10,3)),
    miptex("BLACKBOARD", blackboard()),
    miptex("POSTER_MATH",classroom_poster("MATEMATIKA","FORMULALAR",(55,104,132))),
    miptex("POSTER_GEO",classroom_poster("GEOGRAFIYA","O'ZBEKISTON",(76,122,83))),
    miptex("CLASS_WALL",plaster((219,207,178),20,3)),
    miptex("HALL_FLOOR",hall_floor()),
    miptex("CLASS_FLOOR",plank_floor((139,104,68),22)),
    miptex("SPORT_FLOOR",plank_floor((180,135,80),24,True)),
    miptex("STAIR_STONE",plaster((162,119,89),25,6)),
    miptex("CEILING_WHITE",plaster((226,224,210),27,2)),
    miptex("CLASS_DOOR",classroom_door()),
    miptex("CAR_GLASS",plaster((69,99,115),28,5)),
    miptex("TIRE_BLACK",plaster((35,38,38),29,4)),
    miptex("HEADLIGHT",plaster((219,210,172),30,2)),
    miptex("SCOREBOARD",scoreboard()),
]
data = bytearray(b"WAD3" + b"\0"*8)
entries = []
for name, body in textures:
    pos = len(data)
    data.extend(body)
    entries.append(struct.pack("<iiiBBH16s",pos,len(body),len(body),0x43,0,0,name))
directory_offset = len(data)
for entry in entries:
    data.extend(entry)
struct.pack_into("<II",data,4,len(entries),directory_offset)
target = root / "3_maktab.wad"
target.write_bytes(data)
print(target, len(data), [name.rstrip(b"\0").decode("ascii") for name,_ in textures])
