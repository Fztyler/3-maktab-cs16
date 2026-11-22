"""Restore the outdoor court from the original photographic reconstruction."""
import json
import math

(bx0,bx1),(by0,by1),_=bounds("баскет больное поле")
mid_x,mid_y=(bx0+bx1)/2,(by0+by1)/2
by0-=5.5  # West edge after rotating the original plan.
by1+=5.2  # East edge.


def basketball_point(x,y):
    # The earlier court faced north/south and sat 1.5 m south of its pivot.
    return mid_x+y-mid_y,mid_y-(x-mid_x)-1.5


def court_box(x0,y0,z0,x1,y1,z1,material,solid=False):
    ax,ay=basketball_point(x0,y0)
    bx,by=basketball_point(x1,y1)
    if solid:
        add(ax,ay,z0,bx,by,z1,material)
    else:
        piece=brush(ax,ay,z0,bx,by,z1,material)
        if piece:
            static_details.append(piece)


def court_line(x0,y0,x1,y1):
    court_box(min(x0,x1)-.025,min(y0,y1)-.025,3,
             max(x0,x1)+.025,max(y0,y1)+.025,4,"ROAD_WHITE")


def court_arc(cx,cy,radius,start=0,end=math.tau,z=3,material="ROAD_WHITE"):
    count=max(12,round(48*(end-start)/math.tau)) if radius>=1 else 16
    half_width=.025
    for i in range(count):
        a=start+(end-start)*i/count
        b=start+(end-start)*(i+1)/count
        ring=[basketball_point(cx+r*math.cos(v),cy+r*math.sin(v))
              for r,v in ((radius-half_width,a),(radius+half_width,a),
                          (radius+half_width,b),(radius-half_width,b))]
        vertices=[((x+28)*S,(y-20)*S,h) for h in (z,z+1) for x,y in ring]
        faces=((0,3,2),(4,5,6),(0,1,5),(1,2,6),(2,3,7),(3,0,4))
        center=[sum(p[axis] for p in vertices)/8 for axis in range(3)]
        lines=[]
        for index,(ia,ib,ic) in enumerate(faces):
            p,q,r=vertices[ia],vertices[ib],vertices[ic]
            u=[q[j]-p[j] for j in range(3)]
            v=[r[j]-p[j] for j in range(3)]
            normal=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
            if sum(normal[j]*(center[j]-p[j]) for j in range(3))<0:
                q,r=r,q
            points=' '.join('( '+' '.join(f'{v:.3f}' for v in pt)+' )' for pt in (p,q,r))
            texture="NULL" if z==3 and index!=1 else material
            lines.append(f"{points} {texture} 0 0 0 1 1")
        static_details.append('{\n'+'\n'.join(lines)+'\n}')


def basketball_hoop(x,y,direction):
    court_box(x-.60,y-.90,4,x+.60,y+.90,28,"PHOTO_METAL",solid=True)
    for dx in (-.59,.59):
        for dy in (-.68,.68):
            court_box(x+dx-.10,y+dy-.10,2,x+dx+.10,y+dy+.10,10,"TIRE_BLACK")
    court_box(x-.08,y-.10,28,x+.08,y+.10,120,"PHOTO_METAL",solid=True)
    back=x+direction*.90
    court_box(min(x,back),y-.06,115,max(x,back)+.06,y+.06,120,"PHOTO_METAL")
    court_box(back-.055,y-.90,113,back+.055,y+.90,161,"SCHOOL_WHITE")
    front=back+direction*.065
    for yy in (y-.28,y+.28):
        court_box(front-.02,yy-.022,118,front+.02,yy+.022,137,"ROAD_WHITE")
    for z in (118,137):
        court_box(front-.02,y-.28,z,front+.02,y+.28,z+1,"ROAD_WHITE")
    hoop_x=back+direction*.35
    court_arc(hoop_x,y,.30,z=117,material="SCHOOL_RED")
    for i in range(8):
        angle=i*math.tau/8
        xx=hoop_x+.24*math.cos(angle)
        yy=y+.24*math.sin(angle)
        court_box(xx-.018,yy-.018,103,xx+.018,yy+.018,117,"SCHOOL_WHITE")


court_box(bx0,by0,0,bx1,by1,3,"PHOTO_ASPHALT",solid=True)
for xx in (bx0+.6,bx1-.6):
    court_line(xx,by0+.6,xx,by1-.6)
for yy in (by0+.6,by1-.6):
    court_line(bx0+.6,yy,bx1-.6,yy)
court_line(mid_x,by0+.6,mid_x,by1-.6)
court_arc(mid_x,mid_y,1.8)
hoop_bases=[]
for xx,d in ((bx0+1.2,1),(bx1-1.2,-1)):
    basketball_hoop(xx,mid_y,d)
    hoop_bases.append(basketball_point(xx,mid_y))
    end=xx+d*4.5
    for yy in (mid_y-1.8,mid_y+1.8):
        court_line(xx,yy,end,yy)
    court_line(end,mid_y-1.8,end,mid_y+1.8)
    start=-math.pi/2 if d==1 else math.pi/2
    court_arc(end,mid_y,1.8,start,start+math.pi)

volleyball_posts=[]
for yy in (mid_y-7.1,mid_y+7.1):
    court_box(mid_x-.055,yy-.055,3,mid_x+.055,yy+.055,148,"PHOTO_METAL",solid=True)
    volleyball_posts.append(basketball_point(mid_x,yy))
goal_x,goal_y=bx0+1.4,by0+3.0
for yy in (goal_y-1.5,goal_y+1.5):
    court_box(goal_x-.035,yy-.035,4,goal_x+.035,yy+.035,84,"PHOTO_METAL",solid=True)
    court_box(goal_x-.40,yy-.035,3,goal_x+.40,yy+.035,6,"PHOTO_METAL")
court_box(goal_x-.035,goal_y-1.535,81,goal_x+.035,goal_y+1.535,84,"PHOTO_METAL",solid=True)
for y in (by0-.9,):
    for z in (10,30):
        court_box(bx0,y-.025,z,bx1,y+.025,z+2,"PHOTO_METAL")
    for i in range(15):
        x=bx0+(bx1-bx0)*i/14
        court_box(x-.025,y-.025,0,x+.025,y+.025,34,"PHOTO_METAL")
for x in (bx0+4,bx1-4):
    prop("bench",*basketball_point(x,by1+1.6),3,yaw=270)
    prop("bin",*basketball_point(x+1.5,by1+1.6),3,yaw=270)

corners=[basketball_point(x,y) for x in (bx0,bx1) for y in (by0,by1)]
basketball_bounds=(min(x for x,y in corners),max(x for x,y in corners),
                   min(y for x,y in corners),max(y for x,y in corners))
# Plant along the north and east, with openings on both sides of the corner.
west,east,south,north=basketball_bounds
screen_east=east+1.55
screen_north=north+1.62
basketball_planting=[]
screen_fences=[]
net_brushes=[]
for axis,fixed,ranges in (
    ('x',screen_east,((south+.4,south+11.0),(south+13.8,north-1.75),(north+.9,screen_north))),
    ('y',screen_north,((west+.25,west+9.2),(west+11.8,east-2.25),(east+.22,screen_east))),
):
    for low,high in ranges:
        screen_fences.append((axis,fixed,low,high))
        def fence(a,b,c,d,z0,z1):
            q=(fixed+a,c,z0,fixed+b,d,z1) if axis=='x' else (c,fixed+a,z0,d,fixed+b,z1)
            add(*q,'PHOTO_METAL')
        for z in (12,34,53):
            fence(-.043,.043,low,high,z,z+2)
        sections=max(1,math.ceil((high-low)/1.75))
        for i in range(sections+1):
            along=low+(high-low)*i/sections
            fence(-.071,.071,along-.045,along+.045,0,58)
        if axis=='x':
            q=(fixed-.034,low,1,fixed+.034,high,54)
        else:
            q=(low,fixed-.034,1,high,fixed+.034,54)
        add(*q,'CLIP')
        net_brushes.append(brush(*q,'{NETFENCE'))
        # Place the trunks beyond the fence and stagger low foliage between them.
        trees=max(1,round((high-low)/3.6))
        for i in range(trees):
            along=low+(i+.5)*(high-low)/trees
            index=len(basketball_planting)
            line=fixed+1.18+(i%2)*.24
            x,y=(line,along) if axis=='x' else (along,line)
            if high-low<2.5:
                continue
            stock_prop(('pi_tree1','pi_tree2')[index%2],x,y,0,yaw=29+index*51,height=209+(index%4)*12)
            add(x-.21,y-.21,0,x+.21,y+.21,94,'CLIP')
            basketball_planting.append((x,y))
        shrubs=math.ceil((high-low)/.95)
        for i in range(shrubs):
            along=low+(i+.5)*(high-low)/shrubs
            line=fixed+.51+(i%2)*.22
            x,y=(line,along) if axis=='x' else (along,line)
            ent('cycler_sprite',(x,y,0),model='models/'+('bush','pi_bush','pi_fern')[i%3]+'.mdl',
                angles=f'0 {37+i*55} 0',framerate='0',_insomnia_height=42+(i%4)*5,_insomnia_card=1)

ent('func_illusionary',brushes=net_brushes,rendermode='4',renderamt='255',
    targetname='insomnia_basketball_garden_fence')
(ROOT/"basketball_layout.json").write_text(json.dumps(dict(
    bounds=basketball_bounds,hoops=hoop_bases,volleyball=volleyball_posts,
    goal_posts=[basketball_point(goal_x,y) for y in (goal_y-1.5,goal_y+1.5)],
    surface="PHOTO_ASPHALT",rotation_clockwise=90,planting=basketball_planting,fences=screen_fences),indent=2))
