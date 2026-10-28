"""Build a GoldSrc school map from the named blockout objects in 3m.blend.

Run with Blender: blender -b 3m.blend -P cs16_build/build_map.py
The original .blend is read only. Coordinates in the source are metres.
"""

import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(r"N:\3_maktab_map\cs16_build")
OUT = ROOT / "de_3_maktab.map"
GAME = Path(r"N:\Counter-Strike 1.6")
TOOL_WAD = ROOT / "tools" / "sdhlt" / "sdhlt-v1.3.1" / "tools" / "sdhlt.wad"
S = 40.0
T = 4.0 / S
world = []
entities = []
decor_groups = {}


def X(x):
    return round((x + 28) * S)


def Y(y):
    return round((y - 20) * S)


def bounds(name):
    obj = bpy.data.objects[name]
    p = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
    return tuple((min(v[i] for v in p), max(v[i] for v in p)) for i in range(3))


def fmt(n):
    return str(int(round(n)))


def brush(x0, y0, z0, x1, y1, z1, tex, top=None, sides=None,
          shift_u=0, shift_v=0, scale_u=1, scale_v=1):
    x0, x1 = sorted((X(x0), X(x1)))
    y0, y1 = sorted((Y(y0), Y(y1)))
    z0, z1 = sorted((round(z0), round(z1)))
    if min(x1-x0, y1-y0, z1-z0) < 1:
        return ""
    face = [
        ((x0,y0,z0),(x0,y0,z1),(x0,y1,z1),sides or tex),
        ((x1,y1,z0),(x1,y1,z1),(x1,y0,z1),sides or tex),
        ((x1,y0,z0),(x1,y0,z1),(x0,y0,z1),sides or tex),
        ((x0,y1,z0),(x0,y1,z1),(x1,y1,z1),sides or tex),
        ((x0,y0,z0),(x1,y1,z0),(x1,y0,z0),tex),
        ((x0,y1,z1),(x1,y0,z1),(x1,y1,z1),top or tex),
    ]
    lines = ["{"]
    for a,b,c,t in face:
        # GoldSrc MAP planes point into the convex brush volume.
        pts = " ".join("( " + " ".join(fmt(v) for v in p) + " )" for p in (a,c,b))
        lines.append(f"{pts} {t} {shift_u} {shift_v} 0 {scale_u} {scale_v}")
    return "\n".join(lines + ["}"])


def add(x0,y0,z0,x1,y1,z1,tex,top=None,sides=None):
    b=brush(x0,y0,z0,x1,y1,z1,tex,top,sides)
    if b:
        world.append(b)


def prism_xz(points,y0,y1,tex):
    """Convex low-poly prism, with scene x and GoldSrc z coordinates."""
    back=[(X(x),Y(y0),round(z)) for x,z in points]
    front=[(X(x),Y(y1),round(z)) for x,z in points]
    faces=[back,front]
    faces.extend([[back[i],back[(i+1)%len(back)],front[(i+1)%len(back)],front[i]]
                  for i in range(len(back))])
    center=(sum(p[0] for p in back)/len(back),
            (Y(y0)+Y(y1))/2,
            sum(p[2] for p in back)/len(back))
    lines=["{"]
    for face in faces:
        a,b,c=face[:3]
        u=[b[j]-a[j] for j in range(3)]
        v=[c[j]-a[j] for j in range(3)]
        normal=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        inside=sum(normal[j]*(center[j]-a[j]) for j in range(3))
        if inside<0:
            b,c=c,b
        pts=" ".join("( "+" ".join(fmt(q) for q in p)+" )" for p in (a,b,c))
        lines.append(f"{pts} {tex} 0 0 0 1 1")
    world.append("\n".join(lines+["}"]))


def prism_yz(points,x0,x1,tex):
    """One solid sloped beam following a staircase, extruded along x."""
    back=[(X(x0),Y(y),round(z)) for y,z in points]
    front=[(X(x1),Y(y),round(z)) for y,z in points]
    faces=[back,front]
    faces.extend([[back[i],back[(i+1)%len(back)],front[(i+1)%len(back)],front[i]]
                  for i in range(len(back))])
    center=((X(x0)+X(x1))/2,
            sum(p[1] for p in back)/len(back),
            sum(p[2] for p in back)/len(back))
    lines=["{"]
    for face in faces:
        a,b,c=face[:3]
        u=[b[j]-a[j] for j in range(3)]
        v=[c[j]-a[j] for j in range(3)]
        normal=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        if sum(normal[j]*(center[j]-a[j]) for j in range(3))<0:
            b,c=c,b
        pts=" ".join("( "+" ".join(fmt(q) for q in p)+" )" for p in (a,b,c))
        lines.append(f"{pts} {tex} 0 0 0 1 1")
    world.append("\n".join(lines+["}"]))


def ent(kind, xyz=None, brushes=None, **kv):
    data = {"classname":kind, **{k:str(v) for k,v in kv.items()}}
    if xyz is not None:
        x,y,z=xyz
        data["origin"] = f"{X(x)} {Y(y)} {round(z)}"
    lines = ["{", *(f'"{k}" "{v}"' for k,v in data.items())]
    lines.extend(brushes or [])
    lines.append("}")
    entities.append("\n".join(lines))


def prop(name,x,y,z=0,yaw=0,solid=None):
    ent("cycler_sprite",(x,y,z),model=f"models/maktab/{name}.mdl",
        angles=f"0 {yaw} 0",framerate="0")
    if solid:
        w,d,h=solid
        if yaw%180==90:
            w,d=d,w
        add(x-w/80,y-d/80,z,x+w/80,y+d/80,z+h,"CLIP")


def deco(x0,y0,z0,x1,y1,z1,tex,**kv):
    b=brush(x0,y0,z0,x1,y1,z1,tex)
    if not b:
        return
    # GoldSrc precaches every brush entity as a model. Keep nearby, equally
    # rendered details in one model to leave room for CS weapons and players.
    props=tuple(sorted((k,str(v)) for k,v in kv.items()))
    cx=(x0+x1)/2
    cy=(y0+y1)/2
    cz=(z0+z1)/2
    bucket=(math.floor(cx/16),math.floor(cy/16),math.floor(cz/128))
    decor_groups.setdefault((props,bucket),[]).append(b)


def glass_pane(x0,y0,z0,x1,y1,z1):
    ent("func_breakable", brushes=[brush(x0,y0,z0,x1,y1,z1,"WINDOW_GLASS")],
        material="0", health="20", rendermode="2", renderamt="105")


def hinged_door(axis,fixed,a,b,z):
    # A visible opaque leaf, rotating about an explicit hinge; E toggles it.
    if axis=="x":
        panel=brush(fixed-.05,a+.05,z,fixed+.05,b-.05,z+94,"CLASS_DOOR",scale_u=.75,scale_v=.75)
        hinge=(fixed,a+.05)
    else:
        panel=brush(a+.05,fixed-.05,z,b-.05,fixed+.05,z+94,"CLASS_DOOR",scale_u=.75,scale_v=.75)
        hinge=(a+.05,fixed)
    hx,hy=hinge
    origin=brush(hx-.1,hy-.1,z+44,hx+.1,hy+.1,z+52,"ORIGIN")
    ent("func_door_rotating",brushes=[panel,origin],angles="0 0 0",distance="90",
        speed="100",wait="-1",dmg="0",movesnd="8",stopsnd="0",spawnflags="288",
        rendermode="0",renderamt="255")


def toilet_door(x0,y0,door_side,door_loc):
    hinged_door("x" if door_side=="west" else "y",x0 if door_side=="west" else y0,*door_loc,8)


def classroom_door(x,a,b,z):
    hinged_door("x",x,a,b,z)


def floor_spray(cx,cy,z,tex):
    size=3.2  # 128 units: one complete copy of the 128px spray texture.
    x0,x1=cx-size/2,cx+size/2
    y0,y1=cy-size/2,cy+size/2
    panel=brush(x0,y0,z,x1,y1,z+1,"NULL",top=tex,sides="NULL",
                shift_u=(-X(x0))%128,shift_v=Y(y1)%128)
    ent("func_illusionary",brushes=[panel],rendermode="4",renderamt="255")


def sink(x,y,z=8,face="west"):
    # A shallow ceramic basin with a tap, kept close to the wall.
    add(x-.40,y-.32,z+31,x+.40,y+.32,z+35,"SINK_TILE")
    add(x-.29,y-.24,z+35,x+.29,y+.24,z+38,"SINK_TILE")
    deco(x-.10,y-.07,z+37,x+.10,y+.07,z+43,"CSTRIKE_ME4METL")
    if face=="west":
        deco(x-.24,y-.04,z+42,x-.07,y+.04,z+44,"CSTRIKE_ME4METL")


def classroom(room_x0,room_x1,a,b,z,variant):
    if b-a < 3.35 or room_x1-room_x0 < 5.0:
        return
    mid=(room_x0+room_x1)/2
    room_decor=[]
    def detail(x0,y0,z0,x1,y1,z1,tex):
        room_decor.append(brush(x0,y0,z0,x1,y1,z1,tex))
    # North wall teaching board, one of two wall charts, and a low cupboard.
    detail(mid-1.65,b-.16,z+44,mid+1.65,b-.09,z+82,"BLACKBOARD")
    theme=variant%4
    poster="POSTER_MATH" if theme in (0,2) else "POSTER_GEO"
    detail(room_x0+.35,b-.16,z+55,room_x0+1.5,b-.09,z+86,poster)
    add(room_x1-1.0,b-.68,z,room_x1-.3,b-.25,z+56,
        "SCHOOL_WHITE" if theme==2 else "DESK_WOOD")
    # Teacher's desk and varied pupil rows. The room doorway and a central
    # aisle remain unobstructed for players and bots.
    add(mid-.75,b-1.18,z+29,mid+.75,b-.58,z+34,"DESK_WOOD")
    rows=2 if b-a>4.7 else 1
    if theme==2:
        # Science classroom: paired long work benches and a washing corner.
        for yy in (a+1.05,a+2.4)[:rows]:
            add(mid-2.4,yy-.34,z+29,mid-.45,yy+.34,z+34,"SINK_TILE")
            add(mid+.45,yy-.34,z+29,mid+2.4,yy+.34,z+34,"SINK_TILE")
        sink(room_x1-1.55,b-1.0,z)
    elif theme==3:
        # Art room: grouped square tables and display panels.
        for xx in (mid-1.8,mid+1.8):
            add(xx-.58,a+.68,z+28,xx+.58,a+1.55,z+32,"DESK_WOOD")
            detail(xx-.46,a+.33,z,xx+.46,a+.62,z+20,"SCHOOL_RED")
        detail(room_x1-.18,a+.40,z+50,room_x1-.10,a+1.7,z+82,"POSTER_GEO")
    else:
        for row in range(rows):
            yy=a+1.08+row*1.18
            for xx in (mid-1.65,mid+1.65):
                add(xx-.51,yy-.28,z+27,xx+.51,yy+.28,z+31,"DESK_WOOD")
                detail(xx-.34,yy-.57,z,xx+.34,yy-.25,z+20,"SCHOOL_GREEN")
    if theme==1:
        detail(room_x0+.30,a+.28,z+12,room_x0+1.25,a+.9,z+68,"DESK_WOOD")
    # Small original studio props give the rooms distinct functions.
    if theme==0:
        prop("computer",mid,b-.88,z+34)
    else:
        prop("books",mid,b-.88,z+34,yaw=90 if theme==2 else 0)
    if theme in (0,2):
        prop("clock",room_x1-.7,b-.23,z+83)
    if theme==3:
        prop("planter",room_x0+.7,b-.7,z,solid=(22,22,19))
    ent("func_illusionary",brushes=room_decor)


def wall_x(x,y0,y1,z0,z1,tex,door=None,window=False):
    # Plane at constant x, optional ground-floor opening and paired windows.
    cuts=[]
    panes=[]
    if door:
        cuts.append((door[0],door[1],z0,z0+96))
    if isinstance(window, (tuple, list)):
        cuts.extend(window)
        panes.extend(window)
    elif window:
        span=y1-y0
        for f in (0.27,0.63):
            a=y0+span*f
            levels = [(z0+151,z0+200)] if window == "high" else ([(z0+39,z0+88)] if window == "low" else [(z0+39,z0+88),(z0+151,z0+200)])
            panes.extend((a,a+min(1.8,span*.12),c,d) for c,d in levels if d <= z1)
        cuts.extend(panes)
    ys=sorted({y0,y1,*[v for a,b,c,d in cuts for v in (a,b) if y0<v<y1]})
    zs=sorted({z0,z1,*[v for a,b,c,d in cuts for v in (c,d) if z0<v<z1]})
    for a,b in zip(ys,ys[1:]):
        for c,d in zip(zs,zs[1:]):
            mid=((a+b)/2,(c+d)/2)
            if any(p<mid[0]<q and r<mid[1]<s for p,q,r,s in cuts):
                continue
            add(x-T/2,a,c,x+T/2,b,d,tex)
    for a,b,c,d in panes:
        glass_pane(x-.04,a+.05,c+1,x+.04,b-.05,d-1)


def wall_y(y,x0,x1,z0,z1,tex,door=None,window=False):
    cuts=[]
    panes=[]
    if door:
        cuts.append((door[0],door[1],z0,z0+96))
    if isinstance(window, (tuple, list)):
        cuts.extend(window)
        panes.extend(window)
    elif window:
        span=x1-x0
        for f in (0.23,0.56,0.78):
            a=x0+span*f
            levels = [(z0+151,z0+200)] if window == "high" else ([(z0+39,z0+88)] if window == "low" else [(z0+39,z0+88),(z0+151,z0+200)])
            panes.extend((a,a+min(1.7,span*.12),c,d) for c,d in levels if d <= z1)
        cuts.extend(panes)
    xs=sorted({x0,x1,*[v for a,b,c,d in cuts for v in (a,b) if x0<v<x1]})
    zs=sorted({z0,z1,*[v for a,b,c,d in cuts for v in (c,d) if z0<v<z1]})
    for a,b in zip(xs,xs[1:]):
        for c,d in zip(zs,zs[1:]):
            mid=((a+b)/2,(c+d)/2)
            if any(p<mid[0]<q and r<mid[1]<s for p,q,r,s in cuts):
                continue
            add(a,y-T/2,c,b,y+T/2,d,tex)
    for a,b,c,d in panes:
        glass_pane(a+.05,y-.04,c+1,b-.05,y+.04,d-1)


def school(name, corridor, bands, entrance="south", stair=True):
    (x0,x1),(y0,y1),_=bounds(name)
    x0,x1,y0,y1=map(lambda n:round(n,2),(x0,x1,y0,y1))
    if name=="big_corpus1":
        x0-=2.0
        y0-=2.0
    elif name=="small_corpus":
        x0-=2.5
        y1=64.0
    c0,c1=corridor
    add(x0,y0,-8,c0,y1,8,"CLASS_WALL",top="CLASS_FLOOR")
    add(c0,y0,-8,c1,y1,8,"CLASS_WALL",top="HALL_FLOOR")
    add(c1,y0,-8,x1,y1,8,"CLASS_WALL",top="CLASS_FLOOR")
    # Leave a stairwell void in the second floor slab.
    if stair:
        cut_y=bands[1]
        add(x0,cut_y,110,c0,y1,120,"CLASS_WALL",top="CLASS_FLOOR")
        add(c0,y0,110,c1,y1,120,"CLASS_WALL",top="HALL_FLOOR")
        add(c1,y0,110,x1,y1,120,"CLASS_WALL",top="CLASS_FLOOR")
    else:
        add(x0,y0,110,x1,y1,120,"CLASS_WALL",top="CLASS_FLOOR")
    add(x0,y0,224,x1,y1,236,"CEILING_WHITE",top="Core_Urban_040")
    # External masonry; the courtyard side of each school is the main facade.
    west_windows=True
    if name=="small_corpus":
        # Two distinct second-floor windows face west from the library.
        west_windows=[(a,a+1.5,39,88) for a in (28.5,33.0,37.5,42.5,50.0,58.5)]
        west_windows += [(a,a+1.5,159,208) for a in (28.5,33.0,37.5,42.5,50.0,58.5)]
    west_door=(44.9,48.5) if name=="small_corpus" else None
    wall_x(x0,y0,y1,8,224,"SCHOOL_CREAM", door=west_door if entrance=="west" else None, window=west_windows)
    east_door = (-3.9,-1.1) if name=="big_corpus1" else (41.0,44.0) if name=="small_corpus" else None
    wall_x(x1,y0,y1,8,224,"SCHOOL_CREAM",door=east_door,window=True)
    wall_y(y0,x0,x1,8,224,"SCHOOL_CREAM",door=(c0,c1) if entrance=="south" else None,window=True)
    if name=="big_corpus1":
        wall_y(y1,x0,c0,8,224,"SCHOOL_CREAM")
        wall_y(y1,c1,x1,8,224,"SCHOOL_CREAM")
    else:
        wall_y(y1,x0,x1,8,224,"SCHOOL_CREAM",window=True)
    # Red plinth, white roof edge and pale window surrounds mirror the school.
    for z0,z1,material in ((8,22,"SCHOOL_RED"),(219,230,"SCHOOL_WHITE")):
        ny=math.ceil((y1-y0+.26)/8)
        for i in range(ny):
            a=y0-.13+(y1-y0+.26)*i/ny
            b=y0-.13+(y1-y0+.26)*(i+1)/ny
            deco(x0-.17,a,z0,x0-.10,b,z1,material)
            deco(x1+.10,a,z0,x1+.17,b,z1,material)
        nx=math.ceil((x1-x0)/8)
        for i in range(nx):
            a=x0+(x1-x0)*i/nx
            b=x0+(x1-x0)*(i+1)/nx
            deco(a,y0-.17,z0,b,y0-.10,z1,material)
    # Classrooms on each side of a north-south corridor.
    corridor_trim=[]
    for a,b in zip(bands,bands[1:]):
        for z in (8,120):
            # Stair room has an opening at opposite ends on the two floors.
            west_door=(a+.30,a+2.30) if stair and a==bands[0] and z==8 else (b-2.30,b-.30)
            if not (stair and a==bands[0]):
                west_door=((a+b)/2-1.0,(a+b)/2+1.0)
            east_door=((a+b)/2-1.0,(a+b)/2+1.0)
            wall_x(c0,a,b,z,z+102,"CLASS_WALL",door=west_door)
            wall_x(c1,a,b,z,z+102,"CLASS_WALL",door=east_door)
            classroom_door(c0,*west_door,z)
            classroom_door(c1,*east_door,z)
            for lo,hi in ((a,west_door[0]),(west_door[1],b)):
                if hi-lo>.20:
                    corridor_trim.append(brush(c0+.10,lo,z+2,c0+.18,hi,z+18,"SCHOOL_RED"))
            for lo,hi in ((a,east_door[0]),(east_door[1],b)):
                if hi-lo>.20:
                    corridor_trim.append(brush(c1-.18,lo,z+2,c1-.10,hi,z+18,"SCHOOL_RED"))
        if b != bands[-1]:
            wall_y(b,x0,c0,8,224,"CLASS_WALL")
            wall_y(b,c1,x1,8,224,"CLASS_WALL")
    # Solid 8-unit steps, comfortable for GoldSrc player collision.
    if stair:
        step_y0=y0+.45
        step_y1=bands[1]-.25
        n=14
        rail_x=x0+3.27
        for i in range(n):
            a=step_y0+(step_y1-step_y0)*i/n
            b=step_y0+(step_y1-step_y0)*(i+1)/n
            rise=8+(i+1)*8
            add(x0+.55,a,8,x0+3.15,b,rise,"STAIR_STONE",top="STAIR_STONE")
        # A single solid parapet follows the steps and reaches the lower floor.
        # Separate balusters read as floating pieces at GoldSrc resolution.
        prism_yz([(step_y0,8),(step_y1,8),(step_y1,160),(step_y0,56)],
                 rail_x-.12,rail_x+.12,"CLASS_WALL")
        ent("light",(c0-.9,(y0+bands[1])/2,185),_light="215 222 255 170")
    ent("func_illusionary",brushes=corridor_trim)
    # Corridor lighting, plus room lighting on both levels.
    for z in (101,213):
        for a,b in zip(bands,bands[1:]):
            yc=(a+b)/2
            ent("light",((c0+c1)/2,yc,z),_light="255 240 205 145")
            ent("light",((x0+c0)/2,yc,z),_light="255 240 215 125")
            ent("light",((c1+x1)/2,yc,z),_light="255 240 215 125")
    for band_index,(a,b) in enumerate(zip(bands,bands[1:])):
        for floor,z in enumerate((8,120)):
            for side,(lo,hi) in enumerate(((x0,c0),(c1,x1))):
                if stair and band_index==0 and side==0:
                    continue
                if name=="small_corpus" and floor==1 and side==0 and band_index in (2,3,4):
                    continue  # Library and Terrorist spawn rooms.
                if name=="big_corpus1" and floor==1 and side==1 and band_index in (0,1):
                    continue  # CT spawn rooms.
                classroom(lo+.35,hi-.35,a+.18,b-.18,z,band_index+2*side+3*floor)
    return (x0,x1,y0,y1)


# Coordinates are read from the actual named objects in the user's scene.
exec(compile((ROOT/'rebuild_big.py').read_text(encoding='utf8'),str(ROOT/'rebuild_big.py'),'exec'))

small=school("small_corpus",(-38.4,-34.5),[24.98,31.2,35.78,45.63,54.67,64.0],"west")

# The western middle room upstairs is the library. Bookcases keep the
# central planting area clear and leave its corridor doorway accessible.
for x0,x1,y0,y1 in ((-47.7,-47.0,35.9,37.2),(-47.7,-47.0,44.2,45.2),
                    (-40.0,-39.3,36.4,38.8),(-40.0,-39.3,42.7,44.9)):
    add(x0,y0,120,x1,y1,185,"DESK_WOOD",top="DESK_WOOD")
    for z in (140,160,180):
        add(x0,y0,z,x1,y1,z+3,"DESK_WOOD")
add(-45.8,44.1,120,-43.8,44.8,149,"DESK_WOOD")
prop("books",-45.2,44.4,149)
prop("radio",-44.3,44.4,149)
ent("ambient_generic",(-44.3,44.4,160),targetname="maktab_library_music",
    message="maktab/courtyard_radio.wav",health="2",pitch="100",spawnflags="2")


def annex(name,height,tex,door_side,door_loc):
    (x0,x1),(y0,y1),_=bounds(name)
    x0,x1,y0,y1=map(lambda n:round(n,2),(x0,x1,y0,y1))
    if name=="sport зал":
        x1=22.0
        y0=10.85
        y1=29.2
    elif name=="sport зал.Mini":
        x0=-24.11
        x1+=2.0
        y0-=0.5
        y1+=0.5
    elif name=="kitchen":
        x1=20.8
        y0-=0.8
        y1=4.1
    else:
        x0-=0.6
        x1+=0.6
        y0-=0.4
        y1+=0.4
    floor_tex=("SPORT_FLOOR" if name=="sport зал" else
               "SINK_TILE" if name in ("new_toilet","old_toiled","t_toilet") else
               "HALL_FLOOR")
    add(x0,y0,-8,x1,y1,8,"CLASS_WALL",top=floor_tex)
    add(x0,y0,height,x1,y1,height+12,"CEILING_WHITE",top="Core_Urban_040")
    window_style=False if name in ("new_toilet","old_toiled","t_toilet") else ("high" if name.startswith("sport зал") else "low")
    wall_x(x0,y0,y1,8,height,tex,door=door_loc if door_side=="west" else None,window=window_style)
    wall_x(x1,y0,y1,8,height,tex,door=door_loc if door_side=="east" else None,window=window_style)
    wall_y(y0,x0,x1,8,height,tex,door=door_loc if door_side=="south" else None,window=window_style)
    wall_y(y1,x0,x1,8,height,tex,door=door_loc if door_side=="north" else None,window=window_style)
    if name in ("new_toilet","old_toiled","t_toilet"):
        toilet_door(x0,y0,door_side,door_loc)
        # Wash basins and cubicle dividers sit against the far wall.
        for i in range(2 if x1-x0>5 else 1):
            sink(x1-.85,y0+1.65+i*1.45)
        if y1-y0>6:
            for yy in (y1-2.9,y1-1.6):
                add(x1-2.7,yy,8,x1-1.2,yy+.08,72,"SINK_TILE")
        deco(x0-.18,y0,8,x0-.10,y1,23,"SCHOOL_RED")
        deco(x1+.10,y0,8,x1+.18,y1,23,"SCHOOL_RED")
        deco(x0,y1+.10,8,x1,y1+.18,23,"SCHOOL_RED")
    ent("light",((x0+x1)/2,(y0+y1)/2,height-20),_light="255 240 215 230")
    return (x0,x1,y0,y1)


annex("sport зал.Mini",248,"SCHOOL_CREAM","west",(41.0,44.0))

# Courtyard buildings. Doorways point to the open paths.
annex("new_toilet",112,"SCHOOL_CREAM","south",(-2.0,0.0))
old_toilet=annex("old_toiled",104,"SCHOOL_CREAM","west",(37.0,39.0))
annex("t_toilet",104,"SCHOOL_CREAM","west",(44.0,46.0))
deco(old_toilet[0]-.23,39.2,18,old_toilet[0]-.15,41.9,44,"SITE_B")
add(9.0,34.2,0,14.0,42.15,3,"CSTRIKE_FT4APHT")
add(9.0,42.2,0,16.6,47.8,3,"CSTRIKE_FT4APHT")

# Mid-century school colors and glazed entrance canopy, with Uzbek signs.
for x0,x1,y in ((-32.5,-23.2,-23.0),(-52.8,-49.0,47.9)):
    add(x0,y-.30,120,x1,y+.30,132,"SCHOOL_WHITE")
    add(x0,y-.30,80,x0+.25,y+.30,120,"SCHOOL_WHITE")
    add(x1-.25,y-.30,80,x1,y+.30,120,"SCHOOL_WHITE")
# The smaller school's white sloping entrance supports and blue glazing.
for yy in (45.1,48.25):
    for i in range(5):
        xx=-53.5+i*.45
        add(xx,yy-.13,8,xx+.24,yy+.13,39+i*18,"SCHOOL_WHITE")
deco(-51.50,45.3,9,-51.43,48.0,80,"WINDOW_GLASS",rendermode="2",renderamt="130")
deco(-45.3,24.60,140,-39.1,24.70,187,"MAKTAB_SIGN")

# Outdoor world shell. All air and buildings are inside a sealed sky volume.
add(-83,-80,-96,53,96,-16,"CSTRIKE_FT2DIRT")
add(-83,-80,-16,53,96,0,"CSTRIKE_FT3GRAS")
add(-84,-81,-96,-82.5,97,576,"sky")
add(52.5,-81,-96,54,97,576,"sky")
add(-84,-81,-96,54,-79.5,576,"sky")
add(-84,95.5,-96,54,97,576,"sky")
add(-84,-81,576,54,97,608,"sky")
# Distant facades hide the hard edge of the playable ground from upper floors.
for x0,x1 in ((-82.2,-80.9),(51.1,52.0)):
    add(x0,-79.2,0,x1,94.8,278,"SCHOOL_CREAM",top="Core_Urban_040")
    deco(x0,-79.2,0,x1,-79.1,22,"SCHOOL_RED")
    for yy in (-70,-50,-30,-13,9,32,55,77):
        for zz in (46,122,198):
            face=x1+.02 if x0<0 else x0-.09
            deco(face,yy-.95,zz,face+.07,yy+.95,zz+35,"WINDOW_GLASS")
add(-82.2,93.1,0,52.0,94.8,254,"SCHOOL_CREAM",top="Core_Urban_040")
for xx in range(-75,51,9):
    for zz in (45,120,195):
        deco(xx-.95,93.00,zz,xx+.95,93.08,zz+34,"WINDOW_GLASS")

# Ground paths preserve the original courtyard and southern gateway.
add(-32,-23.35,0,-23,-8,2,"CSTRIKE_FT4APHT")
add(-29,-8,0,-3,24,2,"CSTRIKE_FT4APHT")
add(-54,20,0,-22,24,2,"CSTRIKE_FT4APHT")
add(-42,55,0,-38,68,2,"CSTRIKE_FT4APHT")
add(-34,20,0,-29,55,2,"CSTRIKE_FT4APHT")

# Four solid walls around the school, except the south fence and its gate.
add(-80.4,-23.0,0,-79.7,92.0,176,"SCHOOL_CREAM",top="Core_Urban_040")
add(50.0,-23.0,0,50.7,92.0,176,"SCHOOL_CREAM",top="Core_Urban_040")
add(-80.4,91.3,0,50.7,92.0,176,"SCHOOL_CREAM",top="Core_Urban_040")
for a,b in ((-80.4,-32.81),(-22.95,50.7)):
    # CLIP ensures the open-looking metal rail cannot be jumped through.
    add(a,-23.2,0,b,-22.75,112,"CLIP")
    add(a,-23.2,8,b,-22.75,12,"CSTRIKE_ME4METL")
    add(a,-23.2,70,b,-22.75,74,"CSTRIKE_ME4METL")
    add(a,-23.2,106,b,-22.75,110,"CSTRIKE_ME4METL")
    n=math.ceil((b-a)/2.8)
    for i in range(n+1):
        x=a+(b-a)*i/n
        add(x-.07,-23.22,0,x+.07,-22.73,110,"CSTRIKE_ME4METL")
# Open school entrance in the middle of the southern fence.
add(-32.81,-23.3,0,-32.50,-22.5,124,"SCHOOL_CREAM")
add(-23.25,-23.3,0,-22.95,-22.5,124,"SCHOOL_CREAM")
for xx in (-32.84,-23.29):
    deco(xx,-23.41,0,xx+.36,-23.33,24,"SCHOOL_RED")
add(-32.81,-23.3,124,-22.95,-22.5,140,"SCHOOL_GREEN")
add(-32.0,-23.3,140,-23.75,-22.5,151,"SCHOOL_GREEN")
add(-30.5,-23.3,151,-25.25,-22.5,160,"SCHOOL_GREEN")
deco(-31.9,-23.41,127,-23.9,-23.31,136,"MAKTAB_SIGN")

# Road beyond the school gate. It runs to the distant sky, with no dead-end wall.
add(-82,-79.0,0,52,-23.5,3,"CSTRIKE_FT4APHT")
add(-82,-23.5,0,52,-23.3,5,"SCHOOL_WHITE")
for xx in range(-77,24,8):
    deco(xx,-40.5,3,xx+3.7,-40.35,4,"ROAD_WHITE")
for yy in range(-75,-29,8):
    deco(-28.2,yy,3,-28.05,yy+3.5,4,"ROAD_WHITE")

def parked_car(x,y,paint):
    # Low-poly sedan with a tapered glazed cabin and octagonal tires.
    add(x-2.12,y-.90,11,x+2.12,y+.90,20,"TIRE_BLACK")
    add(x-2.04,y-.84,19,x+2.04,y+.84,30,paint)
    prism_xz([(x-1.27,30),(x+1.18,30),(x+.72,51),(x-.77,51)],
             y-.72,y+.72,"CAR_GLASS")
    add(x-.82,y-.77,49,x+.76,y+.77,53,paint)
    add(x-2.06,y-.83,29,x-1.27,y+.83,34,paint)
    add(x+1.18,y-.83,29,x+2.06,y+.83,34,paint)
    for yy in (y-.95,y+.95):
        for xx in (x-1.35,x+1.36):
            points=[(xx+math.cos(i*math.tau/8)*.38,
                     15+math.sin(i*math.tau/8)*15) for i in range(8)]
            prism_xz(points,yy-.15,yy+.15,"TIRE_BLACK")
        deco(x-.77,yy-.04,31,x-.70,yy+.04,50,paint)
        deco(x+.67,yy-.04,31,x+.74,yy+.04,50,paint)
        deco(x-.05,yy-.05,18,x+.02,yy+.05,30,"TIRE_BLACK")
    for yy in (y-.57,y+.57):
        deco(x+2.04,yy-.22,24,x+2.12,yy+.22,30,"HEADLIGHT")
        deco(x-2.12,yy-.22,24,x-2.04,yy+.22,30,"CAR_RED")
    deco(x+2.05,y-.42,19,x+2.14,y+.42,24,"TIRE_BLACK")

for spec in ((-68,-47,"CAR_BLUE"),(-51,-29,"CAR_RED"),(-4,-47,"CAR_WHITE"),(14,-29,"CAR_BLUE")):
    parked_car(*spec)
for xx in (-73,-57,-12,19):
    add(xx,-26.3,3,xx+.13,-26.17,176,"CSTRIKE_ME4METL")
    deco(xx-.3,-26.5,174,xx+.43,-25.7,183,"HEADLIGHT")

# Football field and playground in their marked Blender locations.
(fx0,fx1),(fy0,fy1),_=bounds("футбольное поле")
add(fx0,fy0,0,fx1,fy1,16,"Core_Urban_028",top="CSTRIKE_FT3GRAS")
add(fx1,73,0,fx1+1.2,77,8,"Core_Urban_028",top="CSTRIKE_FT3GRAS")
for xx in (fx0+1,fx1-1):
    deco(xx-.04,fy0+1,16,xx+.04,fy1-1,17,"CSTRIKE_FE2SQRS")
for yy in (fy0+1,fy1-1):
    deco(fx0+1,yy-.04,16,fx1-1,yy+.04,17,"CSTRIKE_FE2SQRS")
deco((fx0+fx1)/2-.04,fy0+1,16,(fx0+fx1)/2+.04,fy1-1,17,"CSTRIKE_FE2SQRS")
for gx in (fx0+.2,fx1-.2):
    add(gx-.08,(fy0+fy1)/2-1.8,16,gx+.08,(fy0+fy1)/2-1.7,92,"CSTRIKE_ME4METL")
    add(gx-.08,(fy0+fy1)/2+1.7,16,gx+.08,(fy0+fy1)/2+1.8,92,"CSTRIKE_ME4METL")
    add(gx-.08,(fy0+fy1)/2-1.8,88,gx+.08,(fy0+fy1)/2+1.8,92,"CSTRIKE_ME4METL")

def net_x(x, y0, y1):
    add(x-.06,y0,16,x+.06,y1,160,"CLIP")
    deco(x-.08,y0,16,x+.08,y1,160,"{NETFENCE",rendermode="4",renderamt="255")
    for z in (16,92,156):
        add(x-.10,y0,z,x+.10,y1,z+4,"CSTRIKE_ME4METL")
    for i in range(math.ceil((y1-y0)/3)+1):
        y=y0+(y1-y0)*i/max(1,math.ceil((y1-y0)/3))
        add(x-.12,y-.12,16,x+.12,y+.12,160,"CSTRIKE_ME4METL")

def net_y(y, x0, x1):
    add(x0,y-.06,16,x1,y+.06,160,"CLIP")
    deco(x0,y-.08,16,x1,y+.08,160,"{NETFENCE",rendermode="4",renderamt="255")
    for z in (16,92,156):
        add(x0,y-.10,z,x1,y+.10,z+4,"CSTRIKE_ME4METL")
    for i in range(math.ceil((x1-x0)/3)+1):
        x=x0+(x1-x0)*i/max(1,math.ceil((x1-x0)/3))
        add(x-.12,y-.12,16,x+.12,y+.12,160,"CSTRIKE_ME4METL")

net_x(fx0,fy0,fy1)
net_x(fx1,fy0,73)
net_x(fx1,77,fy1)
net_y(fy0,fx0,fx1)
net_y(fy1,fx0,fx1)

# Benches and bins live along the field perimeter, outside the playing area.
for yy in (fy0+4,(fy0+fy1)/2,fy1-4):
    prop("bench",fx0-1.5,yy,0,yaw=90,solid=(80,22,22))
    prop("bin",fx0-1.5,yy+1.6,0,solid=(24,24,30))
for xx in (-17,5):
    prop("bench",xx,-18,0,solid=(80,22,22))
    prop("bin",xx+1.6,-18,0,solid=(24,24,30))
for xx,yy,zz in ((-11.5,-10.7,0),(-1.7,-10.7,0),(-52.1,44.2,0),(-52.1,49.3,0)):
    prop("planter",xx,yy,zz,solid=(22,22,19))

(bx0,bx1),(by0,by1),_=bounds("баскет больное поле")
add(bx0,by0,0,bx1,by1,5,"CSTRIKE_FT4APHT")
for xx in (bx0+.5,bx1-.5):
    deco(xx-.04,by0+.5,5,xx+.04,by1-.5,6,"CSTRIKE_FE2SQRS")
for yy in (by0+.5,by1-.5):
    deco(bx0+.5,yy-.04,5,bx1-.5,yy+.04,6,"CSTRIKE_FE2SQRS")
deco((bx0+bx1)/2-.04,by0+.5,5,(bx0+bx1)/2+.04,by1-.5,6,"CSTRIKE_FE2SQRS")
for x in (bx0+2,bx1-2):
    add(x-.10,(by0+by1)/2-.1,5,x+.10,(by0+by1)/2+.1,112,"CSTRIKE_ME4METL")
    deco(x-.8,(by0+by1)/2-.08,105,x+.8,(by0+by1)/2+.08,130,"CSTRIKE_WB6PLN1")

(px0,px1),(py0,py1),_=bounds("игровая площадка with sand")
px0-=3.4
add(px0,py0,0,px1,py1,4,"SandRoad")

exec(compile((ROOT/"plant_trees.py").read_text(encoding="utf8"),str(ROOT/"plant_trees.py"),"exec"))

# Yard lights and gameplay entities.
ent("light_environment",(0,0,440),angles="-55 225 0",_light="255 238 201 295",_ambient="160 158 145 65")
ent("info_map_parameters",(0,0,64),buying="0")
cx0,cx1,cy0,cy1=ct_room
for row in range(4):
    for col in range(5):
        ent("info_player_start",(cx0+1.1+col*1.0,cy0+1.1+row*1.3,UP+40),angle="180")
for y in (49,51,57,60):
    for x in (-48,-46,-44,-42,-40):
        ent("info_player_deathmatch",(x,y,160),angle="270")
ent("func_buyzone",brushes=[brush(cx0+.2,cy0+.2,UP,cx1-.2,cy1-.2,UP+96,"AAATRIGGER")],team="2")
ent("func_buyzone",brushes=[brush(-50.0,46.5,120,-39.5,62.5,216,"AAATRIGGER")],team="1")
# A is inside the large gym; B covers the two eastern toilets.
# Keep this order so the first bomb target is A in implementations that
# assign site letters by entity order.
ent("func_bomb_target",brushes=[brush(site_a[0]-3,site_a[1]-2,8,site_a[0]+3,site_a[1]+2,100,"AAATRIGGER")])
ent("func_bomb_target",brushes=[brush(9.0,36.0,0,18.2,47.5,96,"AAATRIGGER")])
floor_spray(*site_a,8,"{SPRAY_A")
floor_spray(11.5,40.0,3,"{SPRAY_B")

wad=";".join(map(str,[TOOL_WAD,GAME/"cstrike"/"cstrike.wad",GAME/"cstrike"/"cs_office.wad",GAME/"cstrike"/"cs_dust.wad",GAME/"valve"/"halflife.wad",ROOT/"3_maktab.wad"]))
for (props,_bucket),brushes in decor_groups.items():
    ent("func_illusionary",brushes=brushes,**dict(props))
lines=["{",'"classname" "worldspawn"',f'"wad" "{wad}"','"skyname" "Des"','"message" "3-MAKTAB | School, Uzbekistan"',*world,"}",*entities]
OUT.write_text("\n".join(lines)+"\n",encoding="utf-8")
print(f"WROTE {OUT}, {len(world)} world brushes, {len(entities)} entities, {tree_count} trees")

