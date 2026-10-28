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
assert len(models)<340, f"Too many brush models: {len(models)}"
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
            top=8+(i+1)*84/11 if side==0 else 176-i*84/11
            assert contents(scene_point(xx,yy,top+54))==-1, f'Blocked staircase {side} {i}'
    assert contents(scene_point(mid,(end+by)/2,145))==-1, 'Blocked turning landing'
# Both original corridor centerlines must remain walkable on both floors.
for sx,sy in ((5,0),(5,5),(110,-20),(110,-10),(110,0)):
    x=-17.62+(sx+12.784)*.28; y=-10+(sy+63.737)*.28
    for z in (48,216): assert contents(scene_point(x,y,z))==-1, ('Blocked corridor',sx,sy,z)
trees=json.loads((root/'tree_positions.json').read_text())
assert len(trees)==135
for x,y in trees: assert contents(scene_point(x,y,48))==-2, 'Tree lacks trunk collision'
for door in by_class('func_door_rotating'):
    assert door['spawnflags']=='288' and door['rendermode']=='0' and door['distance']=='90'
# The open U-shaped inner yard must have no roof or accidental floor slab.
for z in (40,210,400): assert not world_solid(scene_point(5,6,z)), 'Courtyard filled'
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
custom={o['model'] for o in by_class('cycler_sprite') if o.get('model','').startswith('models/maktab/')}
for name in custom:
    model=(root/'custom_assets'/'cstrike'/name).read_bytes()
    assert struct.unpack_from('<4si',model)==(b'IDST',10)
assert len(by_class('ambient_generic'))==2
print('PASS:',len(models),'brush models;',len(layout['rooms']),'rooms; two switchback stairs; spawns/buyzones/A/B; no direct spawn sightlines')
print('Entities:',dict(Counter(o.get('classname') for o in objects)))
