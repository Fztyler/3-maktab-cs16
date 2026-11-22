"""Replace NAV geometry inside the enlarged court, preserving routes elsewhere."""
import json
from pathlib import Path
from types import SimpleNamespace

from update_local_nav import read_nav, write_nav

root=Path(__file__).resolve().parent
previous=root.parent/'insomnia_north_campus'
name='de_insomnia_project_t'
header,previous_areas=read_nav(previous/(name+'.nav'))
scope={'__file__':str(root/'verify_map.py')}
exec((root/'verify_map.py').read_text(encoding='utf8').split('import json, math')[0],scope)
bsp=SimpleNamespace(**{key:scope[key] for key in ('contents','by_class')})

def X(x): return round((x+28)*40)
def Y(y): return round((y-20)*40)
def box(a,b,c,d): return (X(a),Y(c),X(b),Y(d))
def rect(bounds): return (bounds[0],bounds[1],bounds[3],bounds[4])
def intersect(a,b):
    out=max(a[0],b[0]),max(a[1],b[1]),min(a[2],b[2]),min(a[3],b[3])
    return out if out[2]>out[0] and out[3]>out[1] else None

def subtract(a,b):
    overlap=intersect(a,b)
    if not overlap:
        return [a]
    x,y,u,v=a
    p,q,r,s=overlap
    return [n for n in ((x,y,p,v),(r,y,u,v),(p,y,r,q),(p,s,r,v)) if min(n[2]-n[0],n[3]-n[1])>=12]

def z_at(bounds,x,y):
    a,b,c,d=rect(bounds)
    u=(x-a)/(c-a)
    v=(y-b)/(d-b)
    return (1-v)*((1-u)*bounds[2]+u*bounds[6])+v*((1-u)*bounds[7]+u*bounds[5])

def edges(a,b):
    x,y,u,v=a
    p,q,r,s=b
    h=min(u,r)-max(x,p)
    w=min(v,s)-max(y,q)
    return ((y-s,h),(p-u,w),(q-v,h),(x-r,w))

def resized(bounds, area):
    x,y,u,v=area
    return [x,y,z_at(bounds,x,y),u,v,z_at(bounds,u,v),z_at(bounds,u,y),z_at(bounds,x,v)]

layout=json.loads((root/'basketball_layout.json').read_text())
west,east,south,north=layout['bounds']
court=box(west,east,south,north)
reserved=[court,box(west-.97,west-.83,south,north)]
for axis,fixed,lo,hi in layout['fences']:
    reserved.append(box(fixed-.47,fixed+.47,lo-.37,hi+.37) if axis=='x' else
                    box(lo-.37,hi+.37,fixed-.47,fixed+.47))
for a,b in layout['planting']:
    reserved.append(box(a-.62,a+.62,b-.62,b+.62))
old_court=json.loads((previous/'basketball_layout.json').read_text())
# Discard the route channel around the vanished east sideline.
_,old_east,_,_=old_court['bounds']
dirty=box(west-2,east+3,south-2,north+4)
static_nodes={}
source_parts={}
reconnect=set()
next_id=max(previous_areas)+1
for ident,old in previous_areas.items():
    r=rect(old['bounds'])
    parts=[r]
    low=min(old['bounds'][2],old['bounds'][5])<45
    if low and intersect(r,dirty):
        for obstacle in reserved:
            parts=[piece for part in parts for piece in subtract(part,obstacle)]
    source_parts[ident]=[]
    for i,part in enumerate(parts):
        key=ident
        if i:
            key=next_id
            next_id+=1
        changed=part!=r
        static_nodes[key]=dict(old,bounds=resized(old['bounds'],part) if changed else old['bounds'],
                               connections=[[],[],[],[]])
        if changed:
            static_nodes[key].update(hiding=[],approach=[],encounters=[])
        if low and intersect(part,dirty):
            reconnect.add(key)
        source_parts[ident].append(key)

for ident,old in previous_areas.items():
    for key in source_parts[ident]:
        a=rect(static_nodes[key]['bounds'])
        for side,group in enumerate(old['connections']):
            for old_dest in group:
                for dest in source_parts[old_dest]:
                    if key==ident and dest==old_dest and key not in reconnect and dest not in reconnect:
                        static_nodes[key]['connections'][side].append(dest)
                        continue
                    gap,width=edges(a,rect(static_nodes[dest]['bounds']))[side]
                    old_gap,_=edges(rect(old['bounds']),rect(previous_areas[old_dest]['bounds']))[side]
                    if width>=16 and abs(gap-old_gap)<3:
                        static_nodes[key]['connections'][side].append(dest)
        for dest in source_parts[ident]:
            if key==dest:
                continue
            for side,(gap,width) in enumerate(edges(a,rect(static_nodes[dest]['bounds']))):
                if abs(gap)<2 and width>=19:
                    static_nodes[key]['connections'][side].append(dest)

parts=[court]
for x,y in layout['hoops']:
    parts=[piece for part in parts for piece in subtract(part,box(x-1.38,x+1.38,y-1.10,y+1.10))]
for x,y in layout['volleyball']+layout['goal_posts']:
    parts=[piece for part in parts for piece in subtract(part,box(x-.47,x+.47,y-.47,y+.47))]
new_nodes=[]
for a,b,c,d in parts:
    key=next_id
    next_id+=1
    static_nodes[key]=dict(bounds=[a,b,3,c,d,3,3,3], flags=0, connections=[[],[],[],[]],
                           hiding=[],approach=[],encounters=[],place=0)
    new_nodes.append(key)

def join(a,b,side):
    first=static_nodes[a]['connections'][side]
    second=static_nodes[b]['connections'][(side+2)%4]
    if b not in first:
        first.append(b)
    if a not in second:
        second.append(a)

for key in new_nodes:
    a=rect(static_nodes[key]['bounds'])
    for other in (*reconnect,*new_nodes):
        if other==key:
            continue
        b=rect(static_nodes[other]['bounds'])
        for side,(gap,width) in enumerate(edges(a,b)):
            if not 0<=gap<=21 or width<18:
                continue
            x,y,u,v=a
            p,q,r,s=b
            if side%2:
                along=(max(y,q)+min(v,s))/2
                start=(u,along) if side==1 else (x,along)
                finish=(p,along) if side==1 else (r,along)
            else:
                along=(max(x,p)+min(u,r))/2
                start=(along,v) if side==2 else (along,y)
                finish=(along,q) if side==2 else (along,s)
            z=z_at(static_nodes[other]['bounds'],*finish)
            if abs(z-3)>13:
                continue
            if all(bsp.contents((start[0]+(finish[0]-start[0])*t,start[1]+(finish[1]-start[1])*t,max(3,z)+38))==-1
                   for t in (0,.5,1)):
                join(key,other,side)

def find(x,y,z):
    def distance(area):
        a,b,c,d=rect(area['bounds'])
        px=min(max(a,x),c)
        py=min(max(b,y),d)
        return (px-x)**2+(py-y)**2+(z_at(area['bounds'],px,py)-z)**2
    return min(static_nodes,key=lambda key: distance(static_nodes[key]))

def reach(key):
    seen=set()
    todo=[key]
    while todo:
        i=todo.pop()
        if i in seen:
            continue
        seen.add(i)
        todo.extend(d for group in static_nodes[i]['connections'] for d in group)
    return seen

spawns=[]
for cls in ('info_player_start','info_player_deathmatch'):
    x,y,z=map(float,bsp.by_class(cls)[0]['origin'].split())
    spawns.append(find(x,y,z-40))
site=json.loads((root/'new_big_layout.json').read_text(encoding='utf8'))
a0,a1,c0,c1=site['site_a_bounds']
sites=tuple(find(X(x),Y((c0+c1)/2+off),site['site_a_floor'])
            for x,off in ((a0+.65,1.13),(a1-.38,-1.13)))
for spawn in spawns:
    reachable=reach(spawn)
    assert all(n in reachable for n in (*spawns,*sites,*new_nodes)),(spawn,sites,set(new_nodes)-reachable)
print(f'{len(static_nodes)} areas; {len(new_nodes)} court rectangles; A access {sites}; CT and T connected')
write_nav(root/(name+'.nav'),header,static_nodes,(root/(name+'.bsp')).stat().st_size)
