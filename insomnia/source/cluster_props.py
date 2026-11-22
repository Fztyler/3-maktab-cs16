"""Merge static studio details to keep GoldSrc's entity packets below 256.
The original per-object collision brushes remain in the world.
"""
import re,subprocess,math,json,struct
from collections import defaultdict
groups=defaultdict(list); retained=[]
import sys
sys.path.insert(0,str(ROOT))
from studio_mesh import studio_triangles
studio_cache={}
tree_names={"models/pi_tree1.mdl","models/pi_tree2.mdl"}
stock_names={f"models/{name}.mdl" for name in (
    "bush","pi_bush","fern","pi_fern","pi_stlamp","pi_outlamp1","winebottle","lv_bottle"
)}
for block in entities:
    kv=dict(re.findall(r'"([^\"]+)" "([^\"]*)"',block))
    model=kv.get('model','')
    if kv.get('classname')=='cycler_sprite' and (model.startswith('models/maktab/') or model in tree_names or model in stock_names):
        origin=tuple(map(float,kv['origin'].split())); yaw=float(kv.get('angles','0 0 0').split()[1])
        bucket=(model in tree_names,math.floor(origin[0]/2048),math.floor(origin[1]/2048),math.floor(origin[2]/112))
        groups[bucket].append((model,origin,yaw,float(kv.get("_insomnia_height",0)),kv.get("_insomnia_card")=="1"))
    else: retained.append(block)
entities[:]=retained
src=ROOT/'custom_assets'/'source'
header='version 1\nnodes\n0 "root" -1\nend\nskeleton\ntime 0\n0 0 0 0 0 0 0\nend\n'
manifest=[]
scene_batches=[]
for index,(bucket,items) in enumerate(sorted(groups.items())):
    name=(f'insomnia_r5_tree_{index:03d}' if bucket[0] else f'insomnia_r5_detail_{index:03d}')
    center=tuple(round(sum(p[1][j] for p in items)/len(items)) for j in range(3))
    if bucket[0]:
        # Keep the studio lighting probe above ground at a real trunk position.
        _,anchor,*_=min(items,key=lambda item: math.dist(item[1],center))
        center=(int(anchor[0]),int(anchor[1]),int(anchor[2])+48)
    triangles=[]; masked=set(); bbmin=[float("inf")]*3; bbmax=[-float("inf")]*3
    for model,origin,yaw,height,card in items:
        factor=1; local_center=(0,0,0)
        if model in tree_names or model in stock_names:
            if model not in studio_cache:
                tris,alpha=studio_triangles(GAME/'cstrike'/model,src,'source_prop'+str(len(studio_cache)))
                if model.startswith(("models/pi_stlamp","models/pi_outlamp")):
                    tris=[(mat,verts) for mat,verts in tris if not mat.endswith("_2.bmp")]
                vertices=[v for _,triangle in tris for v in triangle]
                low=tuple(min(v[j] for v in vertices) for j in range(3))
                high=tuple(max(v[j] for v in vertices) for j in range(3))
                studio_cache[model]=(tris,alpha,low,high)
            raw,alpha,low,high=studio_cache[model]
            masked.update(alpha)
            if height>0:
                local_center=((low[0]+high[0])/2,(low[1]+high[1])/2,low[2])
                factor=height/(high[2]-low[2])
        else:
            lines=(src/(model.rsplit('/',1)[1][:-4]+'.smd')).read_text().splitlines()
            at=lines.index('triangles')+1; raw=[]
            while at<len(lines) and lines[at]!='end':
                raw.append((lines[at],[list(map(float,row.split()[1:])) for row in lines[at+1:at+4]])); at+=4
        if card:
            # Three crossed, two-sided cutout cards give a dense hedge at a
            # small fraction of the triangles of a row of full stock models.
            raw=[]
            factor=1
            local_center=(0,0,0)
            for face in range(3):
                a=face*math.pi/3
                c,s=math.cos(a),math.sin(a)
                radius=height*.66
                points=((-c*radius,-s*radius,0,0,0),(c*radius,s*radius,0,1,0),
                        (c*radius,s*radius,height,1,1),(-c*radius,-s*radius,height,0,1))
                for side in (1,-1):
                    for indices in ((0,1,2),(0,2,3)):
                        raw.append((alpha[0],[(x,y,z,-s*side,c*side,0,u,v)
                                  for x,y,z,u,v in (points[i] for i in (indices if side==1 else indices[::-1]))]))
        c=math.cos(math.radians(yaw)); s=math.sin(math.radians(yaw))
        for material,vertices in raw:
            tri=[material+'\n']
            for x,y,z,nx,ny,nz,u,v in vertices:
                x,y,z=((value-center)*factor for value,center in zip((x,y,z),local_center))
                values=(x*c-y*s+origin[0]-center[0],x*s+y*c+origin[1]-center[1],z+origin[2]-center[2],nx*c-ny*s,nx*s+ny*c,nz,u,v)
                for j in range(3): bbmin[j]=min(bbmin[j],values[j]); bbmax[j]=max(bbmax[j],values[j])
                tri.append('0 '+' '.join(f'{n:.6f}' for n in values)+'\n')
            triangles.append(''.join(tri))
    bodies=[]
    meshes=[]
    for part in range(0,len(triangles),1600):
        mesh=f'{name}_{part//1600}'
        meshes.append(mesh)
        (src/(mesh+'.smd')).write_text(header+'triangles\n'+''.join(triangles[part:part+1600])+'end\n')
        bodies.append(f'$body studio "{mesh}"')
    path=ROOT/'custom_assets'/'cstrike'/'models'/'maktab'/(name+'.mdl')
    bbox=' '.join(str(math.floor(v)) for v in bbmin)+' '+' '.join(str(math.ceil(v)) for v in bbmax)
    qc=f'$bbox {bbox}\n$cbox {bbox}\n$modelname "{path.as_posix()}"\n$cd "{src.as_posix()}"\n$cdtexture "{src.as_posix()}"\n'+ '\n'.join(bodies)+'\n'+'\n'.join(f'$texrendermode {t} masked' for t in sorted(masked))+'\n$sequence idle "idle" fps 1 rotate -90\n'
    (src/(name+'.qc')).write_text(qc)
    result=subprocess.run([str(TOOLS/'studiomdl'/'studiomdl.exe'),str(src/(name+'.qc'))],capture_output=True,text=True)
    if result.returncode or 'ERROR' in result.stdout: raise RuntimeError(result.stdout+result.stderr)
    manifest.append({'model':name,'instances':len(items),'triangles':len(triangles),'trees':len(items) if bucket[0] else 0,'mins':bbmin,'maxs':bbmax,'meshes':meshes,'origin':center})
    # Studio entities are centered in GoldSrc space; do not apply X/Y twice.
    scene_batches.append('{\n"classname" "env_sprite"\n"model" "models/maktab/'+name+'.mdl"\n"origin" "'+' '.join(map(str,center))+'"\n"angles" "0 0 0"\n"framerate" "0"\n"spawnflags" "1"\n"rendermode" "0"\n"renderamt" "255"\n}')
# Put several independent scenery bodies in each file to save precache slots.
pack_groups=[]
current=[]
parts=0
for batch,item in zip(scene_batches,manifest):
    meshes=item['meshes']
    if current and parts+len(meshes)>8:
        pack_groups.append(current)
        current=[]
        parts=0
    current.append((batch,item,meshes))
    parts+=len(meshes)
    if len(current)==6:
        pack_groups.append(current)
        current=[]
        parts=0
if current:
    pack_groups.append(current)

scene_batches=[]
def restore_blue_cutout_mask(path):
    data=bytearray(path.read_bytes())
    count,table=struct.unpack_from('<2i',data,180)
    repaired=[]
    for i in range(count):
        record=table+i*80
        name,flags,width,height,pixels=struct.unpack_from('<64s4i',data,record)
        name=name.rstrip(b'\0')
        end=pixels+width*height
        # Imported cutout models reserve palette index 255 for a pure-blue key.
        # StudioMDL can omit that flag on a repeated texture in another body.
        if (name.startswith(b'source_prop') and not flags&64
            and data[end+765:end+768]==b'\0\0\xff'
            and data[pixels:end].count(255)>width*height//10):
            struct.pack_into('<i',data,record+64,flags|64)
            repaired.append(name.decode('ascii'))
    if repaired:
        path.write_bytes(data)
    return repaired

for pack_index,items in enumerate(pack_groups):
    packed_name=f"insomnia_r7_scene_{pack_index:03d}"
    path=ROOT/"custom_assets/cstrike/models/maktab"/(packed_name+".mdl")
    bodies=[]
    body_bit=0
    minimum=[min(item["mins"][j] for _,item,_ in items) for j in range(3)]
    maximum=[max(item["maxs"][j] for _,item,_ in items) for j in range(3)]
    all_textures=set()
    for block,item,meshes in items:
        mask=0
        for mesh in meshes:
            body_name=f"part_{body_bit}"
            bodies.append(f'$bodygroup {body_name}\n{{\n blank\n studio "{mesh}"\n}}')
            mask+=1<<body_bit
            body_bit+=1
            for line in (src/(mesh+".smd")).read_text().splitlines():
                if line.endswith(".bmp"):
                    all_textures.add(line)
        new_model="models/maktab/"+packed_name+".mdl"
        block=re.sub(r'"model" "[^"]+"',f'"model" "{new_model}"',block)
        bounds_text=" ".join(map(str,[math.floor(v)-4 for v in item["mins"]]+
                                     [math.ceil(v)+4 for v in item["maxs"]]))
        block=block[:-1]+f'"body" "{mask}"\n"targetname" "insomnia_scenery_{pack_index:03d}_{mask}"\n"netname" "{bounds_text}"\n}}'
        item["packed_model"]=new_model
        item["body"]=mask
        scene_batches.append(block)
    # Every material already extracted from a masked stock prop remains masked.
    alpha_textures=set()
    for _,item,_ in items:
        alpha_textures.update(re.findall(r'\$texrendermode ([^ ]+) masked',
                              (src/(item["model"]+".qc")).read_text()))
    bbox=" ".join(str(math.floor(v)) for v in minimum)+" "+" ".join(str(math.ceil(v)) for v in maximum)
    qc=f'$bbox {bbox}\n$cbox {bbox}\n$modelname "{path.as_posix()}"\n$cd "{src.as_posix()}"\n$cdtexture "{src.as_posix()}"\n'
    qc+="\n".join(bodies)+"\n"+"\n".join(f"$texrendermode {t} masked" for t in sorted(alpha_textures))
    qc+='\n$sequence idle "idle" fps 1 rotate -90\n'
    (src/(packed_name+".qc")).write_text(qc)
    result=subprocess.run([str(TOOLS/"studiomdl/studiomdl.exe"),str(src/(packed_name+".qc"))],capture_output=True,text=True)
    if result.returncode or "ERROR" in result.stdout:
        raise RuntimeError(result.stdout+result.stderr)
    restore_blue_cutout_mask(path)

# Keep large scenery groups ahead of the per-room furniture in the packet order.
# CT start entities remain the first entities after worldspawn.
spawn_count=sum('"classname" "info_player_start"' in block for block in entities)
wall_blocks=[block for block in entities if '"targetname" "insomnia_partition_' in block]
entities[:]=[block for block in entities if '"targetname" "insomnia_partition_' not in block]
entities[spawn_count:spawn_count]=scene_batches+wall_blocks
(ROOT/'detail_clusters.json').write_text(json.dumps(manifest,indent=2))
print('Clustered',sum(len(v) for v in groups.values()),'details into',len(groups),'studio entities')
