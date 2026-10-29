"""135 trees (three times the previous 45), with small trunk collision boxes."""
import random,json,math
import sys
sys.path.insert(0,str(ROOT))
from studio_mesh import studio_triangles
rng=random.Random(316135)
tree_models=('models/bigtree.mdl','models/pi_tree1.mdl','models/pi_tree2.mdl')
base_profiles={}; canopy=0
for index,model in enumerate(tree_models):
    triangles,_=studio_triangles(GAME/'cstrike'/model,ROOT/'custom_assets'/'source','collision_tree'+str(index))
    vertices=[v for _,tri in triangles for v in tri]
    bottom=min(v[2] for v in vertices)
    base_profiles[model]=[v[:3] for v in vertices if v[2]<=bottom+20]
    canopy=max(canopy,max(math.hypot(v[0],v[1]) for v in vertices)/S+.5)
protected=[]
for name in ('small_corpus','sport зал.Mini','new_toilet','old_toiled','t_toilet',
             'футбольное поле','баскет больное поле','игровая площадка with sand'):
    (a,b),(c,d),_=bounds(name)
    margin=1.5 if name in ('футбольное поле','баскет больное поле','игровая площадка with sand') else canopy
    if name=='small_corpus': a,b,c,d=small
    elif name=='sport зал.Mini': a=-24.11;b+=2;c-=.5;d+=.5
    elif name in ('new_toilet','old_toiled','t_toilet'): a-=.6;b+=.6;c-=.4;d+=.4
    protected.append((a-margin,b+margin,c-margin,d+margin))
def available(x,y):
    if any(a<x<b and c<y<d for a,b,c,d in protected): return False
    if any(inside_big_scene(x+dx,y+dy) for dx in (-canopy,-canopy/2,0,canopy/2,canopy) for dy in (-canopy,-canopy/2,0,canopy/2,canopy)): return False
    # Southern gate, approaches, primary routes and the road's driving lanes.
    if -33<x<-22 and -78<y<24: return False
    if -55<x<-20 and 19<y<25: return False
    if -36<x<-27 and 20<y<69: return False
    if -45<y<-36: return False
    if 8<x<20 and 32<y<49: return False
    return True
candidates=[]
for iy in range(42):
    for ix in range(34):
        x=-77+ix*3.7+rng.uniform(-.6,.6); y=-73+iy*3.9+rng.uniform(-.6,.6)
        if x<47 and y<88 and available(x,y): candidates.append((x,y))
# Farthest-point placement spreads trees throughout the available grounds.
chosen=[]
while len(chosen)<135:
    if not candidates: raise RuntimeError('Not enough clear tree locations')
    if not chosen:
        pick=min(candidates,key=lambda p:(p[0]+72)**2+(p[1]-75)**2)
    else:
        pick=max(candidates,key=lambda p:min((p[0]-q[0])**2+(p[1]-q[1])**2 for q in chosen))
    chosen.append(pick); candidates.remove(pick)
tree_count=len(chosen); collisions=[]
for i,(x,y) in enumerate(chosen):
    model='models/bigtree.mdl' if i%4==0 else 'models/pi_tree1.mdl' if i%2 else 'models/pi_tree2.mdl'
    yaw=(i*97)%360
    ent('cycler_sprite',(x,y,0),model=model,angles=f'0 {yaw} 0',framerate='0')
    co=math.cos(math.radians(yaw));si=math.sin(math.radians(yaw))
    points=[(x+(a*co-b*si)/S,y+(a*si+b*co)/S) for a,b,z in base_profiles[model]]
    a=min(p[0] for p in points)-.06;b=max(p[0] for p in points)+.06
    c=min(p[1] for p in points)-.06;d=max(p[1] for p in points)+.06
    add(a,c,0,b,d,112,'CLIP')
    collisions.append(dict(model=model,origin=[x,y],box=[a,b,c,d],center=[(a+b)/2,(c+d)/2]))
(ROOT/'tree_positions.json').write_text(json.dumps(chosen,indent=2))
(ROOT/'tree_collisions.json').write_text(json.dumps(collisions,indent=2))
