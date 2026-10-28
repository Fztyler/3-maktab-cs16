"""135 trees (three times the previous 45), with small trunk collision boxes."""
import random,json,math
rng=random.Random(316135)
protected=[]
for name in ('small_corpus','sport зал.Mini','new_toilet','old_toiled','t_toilet',
             'футбольное поле','баскет больное поле','игровая площадка with sand'):
    (a,b),(c,d),_=bounds(name)
    margin=2.0 if name=='small_corpus' else 1.5
    protected.append((a-margin,b+margin,c-margin,d+margin))
def available(x,y):
    if any(a<x<b and c<y<d for a,b,c,d in protected): return False
    if any(inside_big_scene(x+dx,y+dy) for dx,dy in ((0,0),(2,0),(-2,0),(0,2),(0,-2))): return False
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
tree_count=len(chosen)
for i,(x,y) in enumerate(chosen):
    model='models/bigtree.mdl' if i%4==0 else 'models/pi_tree1.mdl' if i%2 else 'models/pi_tree2.mdl'
    ent('cycler_sprite',(x,y,0),model=model,angles=f'0 {(i*97)%360} 0',framerate='0')
    add(x-.22,y-.22,0,x+.22,y+.22,104,'CLIP')
(ROOT/'tree_positions.json').write_text(json.dumps(chosen,indent=2))
