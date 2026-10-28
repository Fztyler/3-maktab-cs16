"""Rebuild the main school from the first-floor sketch's actual floor polygons.
Executed by build_map.py, sharing its GoldSrc brush/entity helpers.
"""
import json
from collections import defaultdict

PLAN_SCALE=.28
def PX(x): return round(-17.62+(x+12.784)*PLAN_SCALE,4)
def PY(y): return round(-10+(y+63.737)*PLAN_SCALE,4)
H=168
UP=8+H
ROOF=UP+H
source=json.loads((ROOT/'new_floor_meshes.json').read_text(encoding='utf8'))
rooms=[]; floor_polys=[]
for obj in source:
    name=obj['name']
    if name.startswith(('Plane','shift','ZP')) or name in ('Stairs','Staris_2'): continue
    polys=[]
    for face in obj['faces']:
        pts=[obj['verts'][i] for i in face]
        if len(pts)>=3 and all(abs(p[2])<.02 for p in pts):
            polys.append([(round(p[0],2),round(p[1],2)) for p in pts])
    floor_polys.extend(polys)
    if polys and not name.startswith('Coridor'):
        pts=[p for poly in polys for p in poly]
        rooms.append(dict(name=name,polys=polys,box=(min(p[0] for p in pts),max(p[0] for p in pts),min(p[1] for p in pts),max(p[1] for p in pts))))

stairs=[(17.24,30.0,-5.97,9.21),(124.90,137.70,-25.05,-8.0)]
stair_landings=[(a,b,c-4.0,c) for a,b,c,d in stairs]
rectpoly=lambda b:[(b[0],b[2]),(b[1],b[2]),(b[1],b[3]),(b[0],b[3])]
floor_polys.extend(map(rectpoly,stairs))
floor_polys.extend(map(rectpoly,stair_landings))
def inside(p,poly):
    x,y=p; result=False
    for a,b in zip(poly,poly[1:]+poly[:1]):
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]: result=not result
    return result
def inrect(x,y,b): return b[0]<x<b[1] and b[2]<y<b[3]
xs=sorted({p[0] for poly in floor_polys for p in poly}); ys=sorted({p[1] for poly in floor_polys for p in poly})
cells={}
for ix,(a,b) in enumerate(zip(xs,xs[1:])):
    for iy,(c,d) in enumerate(zip(ys,ys[1:])):
        p=((a+b)/2,(c+d)/2)
        if any(inside(p,poly) for poly in floor_polys):
            label=0
            for k,r in enumerate(rooms,1):
                if any(inside(p,poly) for poly in r['polys']): label=k; break
            cells[ix,iy]=label
gym_label=next(i for i,r in enumerate(rooms,1) if r['name']=='zal')

def merged_rectangles(select):
    active={}; done=[]
    for iy in range(len(ys)-1):
        runs=[]; start=None; last=None
        for ix in range(len(xs)-1):
            value=select(ix,iy)
            if value!=last:
                if last is not None: runs.append((start,ix,last))
                start=ix; last=value
        if last is not None: runs.append((start,len(xs)-1,last))
        nxt={}
        for a,b,label in runs:
            key=(a,b,label)
            nxt[key]=(*active[key][:3],iy+1) if key in active else (a,b,iy,iy+1)
        for key,rect in active.items():
            if key not in nxt: done.append((*rect,key[2]))
        active=nxt
    done.extend((*r,k[2]) for k,r in active.items())
    return done

for a,b,c,d,label in merged_rectangles(lambda i,j:cells.get((i,j))):
    tex='SPORT_FLOOR' if label==gym_label else 'CLASS_FLOOR' if label else 'HALL_FLOOR'
    add(PX(xs[a]),PY(ys[c]),-8,PX(xs[b]),PY(ys[d]),8,'CLASS_WALL',top=tex)
    add(PX(xs[a]),PY(ys[c]),ROOF,PX(xs[b]),PY(ys[d]),ROOF+12,'CEILING_WHITE',top='Core_Urban_040')
def upper_select(i,j):
    label=cells.get((i,j))
    p=((xs[i]+xs[i+1])/2,(ys[j]+ys[j+1])/2)
    return None if label is None or label==gym_label or any(inrect(*p,b) for b in stairs) else label
for a,b,c,d,label in merged_rectangles(upper_select):
    add(PX(xs[a]),PY(ys[c]),UP-10,PX(xs[b]),PY(ys[d]),UP,'CLASS_WALL',top='CLASS_FLOOR' if label else 'HALL_FLOOR')

# Extract each shared room/corridor boundary once, preserving the sketch's U shape.
edges=defaultdict(list)
for (ix,iy),label in cells.items():
    for axis,fixed,a,b,nb in [('x',xs[ix],ys[iy],ys[iy+1],(ix-1,iy)),('x',xs[ix+1],ys[iy],ys[iy+1],(ix+1,iy)),('y',ys[iy],xs[ix],xs[ix+1],(ix,iy-1)),('y',ys[iy+1],xs[ix],xs[ix+1],(ix,iy+1))]:
        other=cells.get(nb,-1)
        if other==label or (other>=0 and label<other): continue
        edges[axis,fixed,label,other].append((a,b))
segments=[]
for (axis,fixed,label,other),intervals in edges.items():
    intervals.sort(); a,b=intervals[0]
    for c,d in intervals[1:]:
        if abs(c-b)<.03: b=d
        else: segments.append((axis,fixed,a,b,label,other)); a,b=c,d
    segments.append((axis,fixed,a,b,label,other))
doors={}
for k,r in enumerate(rooms,1):
    choices=[(idx,s) for idx,s in enumerate(segments) if s[4]==k and s[5]==0 and (s[3]-s[2])*PLAN_SCALE*S>60]
    if not choices:
        choices=[(idx,s) for idx,s in enumerate(segments) if k in s[4:6] and s[5]>=0 and (s[3]-s[2])*PLAN_SCALE*S>60]
    if choices: doors[k]=max(choices,key=lambda pair:pair[1][3]-pair[1][2])[0]

def new_wall(axis,fixed,a,b,z0,z1,door=None,window=False):
    # The wall helpers accept scene coordinates; cutouts use GoldSrc heights.
    if axis=='x': wall_x(PX(fixed),PY(a),PY(b),z0,z1,'CLASS_WALL',door=door,window=window)
    else: wall_y(PY(fixed),PX(a),PX(b),z0,z1,'CLASS_WALL',door=door,window=window)
def new_door(axis,fixed,opening,z):
    a,b=opening
    hinged_door(axis,PX(fixed) if axis=='x' else PY(fixed),a,b,z)

for idx,(axis,fixed,a,b,label,other) in enumerate(segments):
    exterior=other==-1
    convert=PY if axis=='x' else PX
    lo,hi=convert(a),convert(b)
    opening=None
    if exterior and axis=='x' and abs(fixed+12.78)<.05 and a<-16<b:
        opening=(PY(-22),PY(-13))
    # Internal room doors are centered on their longest corridor frontage.
    if idx in doors.values():
        mid=(lo+hi)/2; half=min(1,(hi-lo-.35)/2); opening=(mid-half,mid+half)
    if exterior:
        # Fewer, larger windows keep model precaching below GoldSrc's limit.
        panes=False
        if hi-lo>2.8 and opening is None:
            mid=(lo+hi)/2; width=min(2.1,(hi-lo)*.5)
            panes=([(mid-width/2,mid+width/2,ROOF-100,ROOF-45)] if label==gym_label else
                   [(mid-width/2,mid+width/2,50,105),(mid-width/2,mid+width/2,UP+42,UP+97)])
            # wall_y uses its own regular window placement.
        if axis=='x': new_wall(axis,fixed,a,b,8,ROOF,door=opening,window=panes)
        else: new_wall(axis,fixed,a,b,8,ROOF,door=opening,window=panes)
    else:
        for z in (8,UP):
            floor_opening=None if z==UP and gym_label in (label,other) else opening
            new_wall(axis,fixed,a,b,z,z+H,door=floor_opening)
            if floor_opening: new_door(axis,fixed,floor_opening,z)

# Comfortable switchback stairs at both markers, with continuous solid parapets.
for x0,x1,y0,y1 in stairs:
    ax,bx,ay,by=PX(x0),PX(x1),PY(y0),PY(y1)
    center=(ax+bx)/2; gap=.18; landing=1.1; end=by-landing; n=11; half=H/2
    for i in range(n):
        y=ay+(end-ay)*i/n; yy=ay+(end-ay)*(i+1)/n
        add(ax,y,8,center-gap,yy,8+(i+1)*half/n,'STAIR_STONE')
        add(center+gap,y,8,bx,yy,UP-i*half/n,'STAIR_STONE')
    add(ax,end,8,bx,by,8+half,'STAIR_STONE')
    # Center infill joins the flights with no disconnected posts.
    prism_yz([(ay,8),(end,8),(end,8+half+40),(ay,48)],center-.08,center+.08,'CLASS_WALL')
    # Short landing guard on the upper opening's outside edge.
    add(bx-.1,ay,UP,bx+.1,end,UP+40,'CLASS_WALL')
    ent('light',((ax+bx)/2,(ay+by)/2,ROOF-35),_light='255 236 205 160')

room_report=[]
for k,r in enumerate(rooms,1):
    a,b,c,d=r['box']; x0,x1,y0,y1=PX(a),PX(b),PY(c),PY(d); mx,my=(x0+x1)/2,(y0+y1)/2
    room_report.append({'name':r['name'],'bounds':[x0,x1,y0,y1],'door':doors.get(k)})
    for floor,z in enumerate((8,UP)):
        if k==gym_label:
            if floor: continue
            ent('light',(mx,my,ROOF-40),_light='255 239 218 230')
            prop('ballrack',x1-1,y0+1,8,solid=(50,18,35))
            for yy in (y0+1.2,y1-1.2):
                prop('bench',x0+2,yy,8,solid=(80,22,22))
            deco(x1-.2,my-1.5,105,x1-.12,my+1.5,140,'SCOREBOARD')
            continue
        if min(x1-x0,y1-y0)<1.8:
            continue # Narrow vestibules remain clear, as in the source sketch.
        ent('light',(mx,my,z+H-28),_light='255 238 210 150')
        if r['name']=='i-kitchen' and floor:
            continue # Clear, safe southeast CT spawn room.
        if r['name']=='o-kitchen' and floor:
            # Assembly hall above the dining room, with a stage and three aisles.
            add(x0+.5,y1-1.8,z,x1-.5,y1-.4,z+20,'DESK_WOOD')
            for row in range(5):
                yy=y0+1.0+row*.95
                for offset in (-3.1,-2.3,-1.5,1.5,2.3,3.1):
                    if x0+.6<mx+offset<x1-.6 and yy<y1-2:
                        prop('hall_chair',mx+offset,yy,z)
            continue
        if 'kitchen' in r['name']:
            add(x0+.5,y1-1.0,z,x1-.5,y1-.3,z+34,'SINK_TILE',top='DESK_WOOD')
            for xx in (x0+1.3,x1-1.3): prop('kitchenware',xx,y1-.65,z+34)
            prop('radio',mx,y1-.65,z+34)
            if r['name']=='i-kitchen':
                ent('ambient_generic',(mx,y1-.65,z+45),targetname='maktab_radio_music',message='maktab/courtyard_radio.wav',health='3',pitch='100',spawnflags='2')
            continue
        if r['name']=='C7' and floor:
            for xx in (x0+.45,x1-.45):
                add(xx-.22,y0+.5,z,xx+.22,y1-.5,z+85,'DESK_WOOD')
                for yy in (y0+1,y0+2,y1-1):
                    for zz in (z+25,z+50,z+75): prop('books',xx,yy,zz)
            add(mx-.7,my-.6,z+29,mx+.7,my+.6,z+34,'DESK_WOOD')
            prop('books',mx,my,z+34)
            continue
        # Rooms follow the plan; upstairs changes function and desk arrangement.
        computer=(r['name']=='STEM' and floor) or (r['name']=='Lab' and not floor)
        office=r['name'] in ('Drk','sub_Drk')
        add(mx-.7,y1-1.1,z+29,mx+.7,y1-.5,z+34,'DESK_WOOD')
        prop('books',mx,y1-.8,z+34)
        prop('clock',mx,y1-.2,z+H-35)
        if not office:
            for yy in (y0+1.2,y0+2.6):
                if yy>y1-1.7: continue
                for xx in ([mx] if x1-x0<4.5 else [mx-1.5,mx+1.5]):
                    add(xx-.55,yy-.3,z+27,xx+.55,yy+.3,z+31,'DESK_WOOD')
                    prop('hall_chair',xx,yy-.65,z)
                    if computer: prop('computer',xx,yy,z+31)
        deco(x0+.25,y1-.18,z+53,x1-.25,y1-.1,z+92,'POSTER_GEO' if r['name']=='ENGLISH' else 'BLACKBOARD')

# Corridor lights follow its actual floor runs, rather than a full bounding box.
for a,b,c,d,label in merged_rectangles(lambda i,j:0 if cells.get((i,j))==0 else None):
    if (xs[b]-xs[a])*(ys[d]-ys[c])<20: continue
    xx=PX((xs[a]+xs[b])/2); yy=PY((ys[c]+ys[d])/2)
    for z in (H-15,ROOF-25): ent('light',(xx,yy,z),_light='255 239 215 140')

gym=next(r for r in room_report if r['name']=='zal')['bounds']
kitch=next(r for r in room_report if r['name']=='i-kitchen')['bounds']
gx0,gx1,gy0,gy1=gym
site_a=((gx0+gx1)/2,(gy0+gy1)/2)
ct_room=kitch
big=(PX(-12.784),PX(209.46),PY(-63.737),PY(33.053))
def inside_big_scene(x,y,polys=tuple(floor_polys)):
    p=((x+17.62)/PLAN_SCALE-12.784,(y+10)/PLAN_SCALE-63.737)
    return any(inside(p,poly) for poly in polys)
(ROOT/'new_big_layout.json').write_text(json.dumps({'rooms':room_report,'stairs':[[PX(a),PX(b),PY(c),PY(d)] for a,b,c,d in stairs],'site_a':site_a,'ct_room':ct_room,'upper_floor_z':UP},ensure_ascii=False,indent=2),encoding='utf8')
