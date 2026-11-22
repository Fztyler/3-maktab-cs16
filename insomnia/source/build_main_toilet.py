"""Import the update's two WC wings and its original washing station."""
import json


def build_main_toilet(east, center_y):
    mesh = json.loads((ROOT/'main_toilet_mesh.json').read_text())
    scale, z_scale = .93, 36
    floor = round(.2153*z_scale)
    wall, tile = 'SCHOOL_CREAM','SINK_TILE'

    def bounds_of(name):
        xyz=mesh[name]['xyz']
        return [[min(v[i] for v in xyz),max(v[i] for v in xyz)] for i in range(3)]

    foundation=bounds_of('M_MT_OBJ_fd')
    wash=bounds_of('WTF_main')
    wash_back=bounds_of('WTR_adt')
    east_limit=foundation[1][1]
    x=lambda along: east+(along-east_limit)*scale
    y=lambda across: center_y-across*scale

    def box(a,b,bottom,c,d,top,texture,top_texture=None):
        add(x(b),y(a),bottom*z_scale,x(d),y(c),top*z_scale,texture,top=top_texture)

    def exact_box(bounds,texture):
        (a,c),(b,d),(lo,hi)=bounds
        box(a,b,lo,c,d,hi,texture)

    def break_wall(a,b,low,c,d,high,texture):
        x0,x1=sorted((x(b),x(d)))
        y0,y1=sorted((y(a),y(c)))
        z0,z1=round(low*z_scale),round(high*z_scale)
        piece=brush(x0,y0,z0,x1,y1,z1,texture)
        axis,fixed,start,end=('y',(y0+y1)/2,x0,x1) if x1-x0>=y1-y0 else ('x',(x0+x1)/2,y0,y1)
        panel=emit_heavy_panel([piece],'building_wall',axis,fixed,start,end,z0,z1,4,())
        breakable_walls.append(panel)
        return panel

    # The slab, roof and door headers are fixed. The wall bays use the same
    # independent breakable panels as the other structures on the map.
    breakable_walls=[]
    fixtures=[]
    entrances=[]
    aisles=[]
    wing_bounds=[]
    for sex,mirror,names in (
        ('M',1,('M_MT','M_MT_OBJ1','M_MT_OBJ_fd','M_MT.6','M_MT_sprator','M_MT_door')),
        ('F',-1,('Female_FMT.001','Female_FMT_OBJ1.001','Female_FMT_OBJ_fd.001',
                 'Female_FMT.002','Female_FMT_sprator.001','Female_FMT_door.001'))
    ):
        body,end,base,stalls,separator,rear=map(bounds_of,names)
        across=body[0][1] if mirror==1 else -body[0][0]
        lo,hi=body[1]
        roof=body[2][1]
        ceiling=roof-.2153
        outer=across-.2153
        base_lo,base_hi=base[1]
        baffle_low,baffle_high=sorted(abs(v) for v in end[0])
        baffle_inner,baffle_outer=end[1]
        depth=max(map(abs,stalls[0]))
        stall_height=stalls[2][1]
        privacy=.7327
        door_top=104/z_scale

        def wing(a,b,bottom,c,d,top,tex,top_tex=None):
            box(a*mirror,b,bottom,c*mirror,d,top,tex,top_tex)

        wing(0,base_lo,base[2][0],across,base_hi,0,wall,'YARD_CONCRETE')

        wing(0,lo,0,across,hi,.2153,wall,tile)
        wing(0,lo,ceiling,across,hi,roof,'CEILING_WHITE','Core_Urban_040')
        for a,b in zip((lo,2,9),(2,9,hi)):
            break_wall(outer*mirror,a,.2153,across*mirror,b,ceiling,wall)
        break_wall(.2153*mirror,separator[1][0],.2153,outer*mirror,separator[1][1],ceiling,tile)
        break_wall(privacy*mirror,rear[1][0],.2153,across*mirror,rear[1][1],ceiling,wall)
        wing(baffle_low,baffle_inner,.2153,baffle_high,baffle_outer,ceiling,wall)
        wing(baffle_high,baffle_inner,door_top,outer,baffle_outer,ceiling,wall)
        room_door=sorted((y(mirror*baffle_high),y(mirror*outer)))
        hinged_door('x',x(baffle_inner),*room_door,floor,hinge_end=(mirror<0),texture='TOILET_DOOR')
        restroom_sign('west',x(baffle_inner),sum(room_door)/2,sex)
        entrances.append([x(baffle_inner),*room_door])
        aisle_y=sorted((y(depth*mirror),y(outer*mirror)))
        aisles.append([x(lo),x(separator[1][0]),*aisle_y])
        wing_bounds.append([x(lo),x(hi),*sorted((y(0),y(across*mirror)))])

        edges=sorted({v[1] for v in mesh[names[3]]['xyz']})
        for a,b in zip(edges[::2],edges[1::2]):
            wing(privacy,a,.2153,depth,b,stall_height,tile)
        stalls_open=[(lo+.42,edges[0]),*zip(edges[1::2],edges[2::2]),(edges[-1],separator[1][0])]
        for a,b in stalls_open:
            position=(x((a+b)/2),y((privacy+.53)*mirror))
            yaw=0 if mirror==1 else 180
            prop('wc_ceramic',*position,floor,yaw=yaw)
            fixtures.append([*position,yaw])
        for along in (-3.1,1.9,7.2,12.4):
            ent('light',(x(along),y(3.05*mirror),round(ceiling*z_scale)-20),_light='220 228 213 126')

    for a,b in zip((base_lo,-.25,8.1),(-.25,8.1,base_hi)):
        break_wall(-privacy,a,0,privacy,b,base[2][1],wall)
    (a,c),(b,d),(lo,hi)=bounds_of('Sprator_Main')
    break_wall(a,b,lo,c,d,hi,wall)

    # Keep the wash trough, backsplash and curved taps from Blender as a
    # single studio detail. Match their solid footprints with clip brushes.
    from mathutils import Vector
    anchor_x=x((wash[1][0]+wash[1][1])/2)
    header='version 1\nnodes\n0 "root" -1\nend\nskeleton\ntime 0\n0 0 0 0 0 0 0\nend\ntriangles\n'
    lines=[header]
    for name,uv in (('WTF_main',(.36,.63)),('WTR_adt',(.36,.63)),('KRAN',(.63,.63))):
        detail=mesh[name]
        # The source basin bottom is below the map's outdoor ground plane.
        # Compress the portion below the rim so its visible floor stays above grass.
        def height(z):
            if name=='WTF_main' and z<1:
                return 4+(z-wash[2][0])/(1-wash[2][0])*(z_scale-4)
            return z*z_scale

        vertices=[Vector(((x(p[1])-anchor_x)*40,(y(p[0])-center_y)*40,height(p[2])-75))
                  for p in detail['xyz']]
        for face in detail['faces']:
            a,b,c=(vertices[i] for i in face)
            normal=(b-a).cross(c-a)
            if normal.length<.001:
                continue
            normal.normalize()
            lines.append('insomnia.bmp\n')
            for v in (a,b,c):
                values=(*v,*normal,*uv)
                lines.append('0 '+' '.join(f'{n:.6f}' for n in values)+'\n')
    (ROOT/'custom_assets/source/main_toilet_wash.smd').write_text(''.join(lines)+'end\n',encoding='ascii')
    prop('main_toilet_wash',anchor_x,center_y,75)
    exact_box(wash,'CLIP')
    exact_box(wash_back,'CLIP')

    wash_rect=[x(wash[1][0]),x(wash_back[1][1]),*sorted(map(y,wash[0]))]
    site=[wash_rect[0],east,min(w[2] for w in wing_bounds),max(w[3] for w in wing_bounds)]
    annex_layouts['new_toilet']=site
    WASH_STATION.update(bounds=wash_rect,height=round(wash[2][1]*z_scale),facing='west')
    data=dict(source='MAIN_toilet_structure1.blend',bounds=site,roof=round(roof*z_scale),
              wings=wing_bounds,entrances=entrances,floor=floor,aisles=aisles,wash=wash_rect,
              taps=len(mesh['KRAN']['faces']),breakable_walls=breakable_walls,fixtures=fixtures)
    (ROOT/'main_toilet_layout.json').write_text(json.dumps(data,indent=2),encoding='utf8')
    return site
