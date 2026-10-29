"""Check map objectives, spawn clearance and packed custom textures."""

import re
import struct
from pathlib import Path

root = Path(__file__).parent
data = (root / "de_3_maktab.bsp").read_bytes()
version = struct.unpack_from("<i", data)[0]
lumps = [struct.unpack_from("<ii", data, 4 + i * 8) for i in range(15)]
entities = data[lumps[0][0]:lumps[0][0] + lumps[0][1]].decode("latin1")
blocks = re.findall(r"\{([^{}]*)\}", entities)

def props(block):
    return dict(re.findall(r'"([^"]+)" "([^"]*)"', block))

objects = [props(block) for block in blocks]
by_class = lambda kind: [obj for obj in objects if obj.get("classname") == kind]

model_start, model_size = lumps[14]
models = [struct.unpack_from("<9f7i", data, at)
          for at in range(model_start, model_start + model_size, 64)]
plane_start, plane_size = lumps[1]
planes = [struct.unpack_from("<4fi", data, at)
          for at in range(plane_start, plane_start + plane_size, 20)]
clip_start, clip_size = lumps[9]
clips = [struct.unpack_from("<ihh", data, at)
         for at in range(clip_start, clip_start + clip_size, 8)]
node_start, node_size = lumps[5]
nodes = [struct.unpack_from("<i2h6h2H", data, at)
         for at in range(node_start, node_start + node_size, 24)]
leaf_start, leaf_size = lumps[10]
leaves = [struct.unpack_from("<i", data, at)[0]
          for at in range(leaf_start, leaf_start + leaf_size, 28)]

def contents(point):
    node = models[0][10]  # World model hull 1, standing player collision.
    while node >= 0:
        plane, front, back = clips[node]
        nx, ny, nz, dist, _ = planes[plane]
        node = front if nx*point[0] + ny*point[1] + nz*point[2] >= dist else back
    return node

def world_solid(point):
    node = models[0][9]  # Render hull: opaque walls blocking sight.
    while node >= 0:
        plane, front, back = nodes[node][:3]
        nx, ny, nz, dist, _ = planes[plane]
        node = front if nx*point[0] + ny*point[1] + nz*point[2] >= dist else back
    return leaves[-node-1] == -2


import json, math
from collections import Counter
layout=json.loads((root/'new_big_layout.json').read_text(encoding='utf8'))
def scene_point(x,y,z): return (round((x+28)*40),round((y-20)*40),z)
assert version==30
assert len(models)<430, f"Too many brush models: {len(models)}"
assert len(by_class('info_player_start'))==20 and len(by_class('info_player_deathmatch'))==20
assert len(by_class('func_bomb_target'))==2 and len(by_class('func_buyzone'))==2
assert len(by_class('func_door_rotating'))>=50
assert by_class('worldspawn')[0]['skyname']=='Des'
for kind in ('info_player_start','info_player_deathmatch'):
    for obj in by_class(kind):
        assert contents(tuple(map(float,obj['origin'].split())))==-1, 'Blocked spawn '+str(obj)
        team='2' if kind=='info_player_start' else '1'
        zone=next(z for z in by_class('func_buyzone') if z['team']==team)
        box=models[int(zone['model'][1:])][:6]
        p=list(map(float,obj['origin'].split()))
        assert all(box[i]<=p[i]<=box[i+3] for i in range(3)), 'Spawn outside buyzone'
for room in layout['rooms']:
    assert room['door'] is not None, 'No door '+room['name']
# Standing player clearance on every tread and both turning landings.
for ax,bx,ay,by in layout['stairs']:
    mid=(ax+bx)/2; end=by-1.1
    for side,xx in enumerate(((ax+mid-.18)/2,(mid+.18+bx)/2)):
        for i in range(11):
            yy=ay+(end-ay)*(i+.5)/11
            half=layout['floor_height']/2
            top=8+(i+1)*half/11 if side==0 else layout['upper_floor_z']-i*half/11
            assert contents(scene_point(xx,yy,top+54))==-1, f'Blocked staircase {side} {i}'
    assert contents(scene_point(mid,(end+by)/2,8+layout['floor_height']/2+53))==-1, 'Blocked turning landing'
# Both original corridor centerlines must remain walkable on both floors.
for sx,sy in ((5,0),(5,5),(110,-20),(110,-10),(110,0)):
    x=-17.62+(sx+12.784)*.336; y=-10+(sy+63.737)*.42
    for z in (48,layout['upper_floor_z']+40): assert contents(scene_point(x,y,z))==-1, ('Blocked corridor',sx,sy,z)
trees=json.loads((root/'tree_positions.json').read_text())
assert len(trees)==135
for t in json.loads((root/'tree_collisions.json').read_text()):
    x,y=t['center']; assert contents(scene_point(x,y,48))==-2, 'Tree lacks aligned trunk collision'
for door in by_class('func_door_rotating'):
    assert door['spawnflags']=='32' and door['rendermode']=='0' and door['distance']=='90'
small=json.loads((root/'small_stair_layout.json').read_text())
sx0,sx1,sy0,sy1=small['stairs']; lx0,lx1,ly0,ly1=small['lane']
assert lx1-lx0>=1.49 and abs(sx0-lx1)<.01
assert sx1>small['bounds'][1]-.5 and sy0>54
for x,y,z in (((lx0+lx1)/2,59.3,48),((lx0+lx1)/2,59.3,small['upper_floor_z']+40),((sx0+sx1)/2,63.35,small['upper_floor_z']+40)):
    assert contents(scene_point(x,y,z))==-1, ('Blocked northeast staircase access',x,y,z)
for i in range(14):
    y=sy0+(sy1-sy0)*(i+.5)/14
    assert contents(scene_point((sx0+sx1)/2,y,8+(i+1)*(small['upper_floor_z']-8)/14+52))==-1, 'Blocked small staircase tread'
# Check continuous, supported corridor-to-stair landing paths on BOTH floors.
for first,last in (((5,-8.97),(25,-8.97)),((110,-28.05),(134,-28.05))):
    for i in range(81):
        x=first[0]+(last[0]-first[0])*i/80; y=first[1]+(last[1]-first[1])*i/80
        px=-17.62+(x+12.784)*.336;py=-10+(y+63.737)*.42
        for floor in (8,layout['upper_floor_z']):
            assert contents(scene_point(px,py,floor+40))==-1, ('Blocked stair corridor portal',x,y,floor)
            assert world_solid(scene_point(px,py,floor-1)), ('Missing stair corridor floor',x,y,floor)
assert len(by_class('func_illusionary'))<=12, 'Too many static network brush entities'
assert len(by_class('cycler_sprite'))<230, 'Static props need clustering'
assert len(by_class('cycler_sprite'))+len(by_class('env_sprite'))<=30
networked=sum(len(by_class(c)) for c in ('cycler_sprite','env_sprite','func_breakable','func_door_rotating','func_illusionary'))
assert networked<=380, 'No headroom for player/entity packets'
clusters=json.loads((root/'detail_clusters.json').read_text())
assert sum(c.get('trees',0) for c in clusters)==135
# The open U-shaped inner yard must have no roof or accidental floor slab.
for z in (40,210,400): assert not world_solid(scene_point(9.524,14,z)), 'Courtyard filled'
ax,ay=layout['site_a']
assert contents(scene_point(ax,ay,48))==-1, 'Gym plant obstructed'
# No direct spawn-to-spawn view, sampled against opaque world walls.
def clear(a,b):
    n=math.ceil(math.dist(a,b)/12)
    return all(not world_solid(tuple(a[j]+(b[j]-a[j])*i/n for j in range(3))) for i in range(1,n))
ct=[tuple(map(float,o['origin'].split())) for o in by_class('info_player_start')]
terror=[tuple(map(float,o['origin'].split())) for o in by_class('info_player_deathmatch')]
visible=sum(clear((a[0],a[1],a[2]+24),(b[0],b[1],b[2]+24)) for a in ct for b in terror)
assert visible==0, 'Exposed spawn sightline'
custom={o['model'] for o in by_class('cycler_sprite')+by_class('env_sprite') if o.get('model','').startswith('models/maktab/')}
for name in custom:
    model=(root/'custom_assets'/'cstrike'/name).read_bytes()
    assert struct.unpack_from('<4si',model)==(b'IDST',10)
    bone=struct.unpack_from('<i',model,144)[0];seq=struct.unpack_from('<i',model,168)[0];anim=struct.unpack_from('<i',model,seq+124)[0]
    base=struct.unpack_from('<6f',model,bone+64);scale=struct.unpack_from('<6f',model,bone+88);offsets=struct.unpack_from('<6H',model,anim)
    pose=[base[i]+(struct.unpack_from('<h',model,anim+off+2)[0]*scale[i] if off else 0) for i,off in enumerate(offsets)]
    assert all(abs(v)<.0001 for v in pose), ('Unexpected animated model transform',name,pose)
assert len(by_class('ambient_generic'))==2
print('PASS:',len(models),'brush models;',len(layout['rooms']),'rooms; two switchback stairs; spawns/buyzones/A/B; no direct spawn sightlines')
print('Entities:',dict(Counter(o.get('classname') for o in objects)))

units=json.loads((root/'window_units.json').read_text())
assert {'big_corpus','small_corpus'} <= {w['building'] for w in units}
windows={o.get('targetname'):o for o in by_class('func_breakable')}
for unit in units:
    glass,frame=windows[unit['glass']],windows[unit['frame']]
    assert glass['material']=='0' and glass.get('target','')=='', ('Glass must leave frame intact',unit)
    assert frame['material']=='1' and frame['target']==unit['glass'], ('Frame must break remaining glass',unit)
    assert unit['frame_brushes']>=7 and frame['rendermode']=='0', ('Incomplete painted wooden frame',unit)
assert len(models)+len(custom)+80<512, 'Insufficient model precache budget'
print('PASS:',len(units),'independent glass/frame pairs; visibility filtering requires the map helper')

annexes=json.loads((root/'annex_layouts.json').read_text())
for name in ('new_toilet','old_toiled','t_toilet'):
    assert abs(annexes[name][1]-69.0)<.02, ('Toilet must be at east boundary',name,annexes[name])
zone=by_class('func_bomb_target')[1];box=models[int(zone['model'][1:])][:6]
assert box[0]>=scene_point(58.9,34,0)[0] and box[3]<=scene_point(69.3,48,96)[0], 'B target did not move with toilets'
print('PASS: all three toilets aligned at east edge x=69, B relocated')

# Measure actual render-hull ceiling elevations, without stretching furniture.
def ceiling_above(x,y,z):
    for height in range(z+2,600):
        if world_solid(scene_point(x,y,height)):
            return height
    raise AssertionError(('No ceiling',x,y,z))
assert layout['upper_floor_z']==192 and small['upper_floor_z']==136
for floor,wanted in ((8,182),(192,376)):
    x=-17.62+(5+12.784)*.336; y=-10+(0+63.737)*.42
    assert ceiling_above(x,y,floor)==wanted, ('Wrong main ceiling',floor)
for floor,wanted in ((8,126),(136,256)):
    assert ceiling_above(-36,30,floor)==wanted, ('Wrong small ceiling',floor)

# Jambs and lintels meet the closed leaf exactly; no daylight strips.
doors=json.loads((root/'door_units.json').read_text())
assert len(doors)==len(by_class('func_door_rotating'))
for door in doors:
    a,b=door['opening']; z=door['floor']; f=door['fixed'];j=door['jamb']
    for along,height in ((a+j/2,z+45),(b-j/2,z+45),((a+b)/2,z+95)):
        x,y=(f,along) if door['axis']=='x' else (along,f)
        assert world_solid(scene_point(x,y,height)), ('Door box has a gap',door,along,height)
    center=scene_point(f,(a+b)/2,z+47) if door['axis']=='x' else scene_point((a+b)/2,f,z+47)
    matched=[]
    for obj in by_class('func_door_rotating'):
        m=models[int(obj['model'][1:])];origin=tuple(map(float,obj.get('origin','0 0 0').split()))
        bounds=tuple(m[i]+origin[i%3] for i in range(6))
        if all(bounds[i]<=center[i]<=bounds[i+3] for i in range(3)): matched.append(bounds)
    assert len(matched)==1, ('Missing or overlapping leaf',door,matched)
    bounds=matched[0];axis=1 if door['axis']=='x' else 0
    low=scene_point(f,a+j,z)[axis] if axis==1 else scene_point(a+j,f,z)[axis]
    high=scene_point(f,b-j,z)[axis] if axis==1 else scene_point(b-j,f,z)[axis]
    assert abs(bounds[axis]-low)<.1 and abs(bounds[axis+3]-high)<.1, ('Leaf does not meet jambs',door,bounds)

source=(root/'de_3_maktab.map').read_text()
assert len(re.findall(r'\) MAKTAB_SIGN ',source))==6, 'Exactly one entrance plaque must remain'
assert not re.search(r'\) (?:SITE_A|SITE_B|BLACKBOARD|POSTER_MATH|POSTER_GEO|SCOREBOARD) ',source), 'Unwanted window-covering panel'
print('PASS: ceilings +16 units per story; fitted frames/closed leaves for',len(doors),'doors; only main entrance plaque remains')
