"""Merge static studio details to keep GoldSrc's entity packets below 256.
The original per-object collision brushes remain in the world.
"""
import re,subprocess,math,json
from collections import defaultdict
groups=defaultdict(list); retained=[]
import sys
sys.path.insert(0,str(ROOT))
from studio_mesh import studio_triangles
tree_cache={}
tree_names={"models/bigtree.mdl","models/pi_tree1.mdl","models/pi_tree2.mdl"}
for block in entities:
    kv=dict(re.findall(r'"([^\"]+)" "([^\"]*)"',block))
    model=kv.get('model','')
    if kv.get('classname')=='cycler_sprite' and (model.startswith('models/maktab/') or model in tree_names):
        origin=tuple(map(float,kv['origin'].split())); yaw=float(kv.get('angles','0 0 0').split()[1])
        bucket=(model in tree_names,math.floor(origin[0]/2048),math.floor(origin[1]/2048),math.floor(origin[2]/112))
        groups[bucket].append((model,origin,yaw))
    else: retained.append(block)
entities[:]=retained
src=ROOT/'custom_assets'/'source'
header='version 1\nnodes\n0 "root" -1\nend\nskeleton\ntime 0\n0 0 0 0 0 0 0\nend\n'
manifest=[]
for index,(bucket,items) in enumerate(sorted(groups.items())):
    name=(f'tree_grove_{index:03d}' if bucket[0] else f'detail_{index:03d}')
    center=tuple(round(sum(p[1][j] for p in items)/len(items)) for j in range(3))
    triangles=[]; masked=set(); bbmin=[float("inf")]*3; bbmax=[-float("inf")]*3
    for model,origin,yaw in items:
        if model in tree_names:
            if model not in tree_cache:
                tree_cache[model]=studio_triangles(GAME/'cstrike'/model,src,'tree'+str(len(tree_cache)))
            raw,alpha=tree_cache[model]; masked.update(alpha)
        else:
            lines=(src/(model.rsplit('/',1)[1][:-4]+'.smd')).read_text().splitlines()
            at=lines.index('triangles')+1; raw=[]
            while at<len(lines) and lines[at]!='end':
                raw.append((lines[at],[list(map(float,row.split()[1:])) for row in lines[at+1:at+4]])); at+=4
        c=math.cos(math.radians(yaw)); s=math.sin(math.radians(yaw))
        for material,vertices in raw:
            tri=[material+'\n']
            for x,y,z,nx,ny,nz,u,v in vertices:
                values=(x*c-y*s+origin[0]-center[0],x*s+y*c+origin[1]-center[1],z+origin[2]-center[2],nx*c-ny*s,nx*s+ny*c,nz,u,v)
                for j in range(3): bbmin[j]=min(bbmin[j],values[j]); bbmax[j]=max(bbmax[j],values[j])
                tri.append('0 '+' '.join(f'{n:.6f}' for n in values)+'\n')
            triangles.append(''.join(tri))
    bodies=[]
    for part in range(0,len(triangles),1600):
        mesh=f'{name}_{part//1600}'
        (src/(mesh+'.smd')).write_text(header+'triangles\n'+''.join(triangles[part:part+1600])+'end\n')
        bodies.append(f'$body studio "{mesh}"')
    path=ROOT/'custom_assets'/'cstrike'/'models'/'maktab'/(name+'.mdl')
    bbox=' '.join(str(math.floor(v)) for v in bbmin)+' '+' '.join(str(math.ceil(v)) for v in bbmax)
    qc=f'$bbox {bbox}\n$cbox {bbox}\n$modelname "{path.as_posix()}"\n$cd "{src.as_posix()}"\n$cdtexture "{src.as_posix()}"\n'+ '\n'.join(bodies)+'\n'+'\n'.join(f'$texrendermode {t} masked' for t in sorted(masked))+'\n$sequence idle "idle" fps 1 rotate -90\n'
    (src/(name+'.qc')).write_text(qc)
    result=subprocess.run([str(ROOT/'tools'/'studiomdl'/'studiomdl.exe'),str(src/(name+'.qc'))],capture_output=True,text=True)
    if result.returncode or 'ERROR' in result.stdout: raise RuntimeError(result.stdout+result.stderr)
    manifest.append({'model':name,'instances':len(items),'triangles':len(triangles),'trees':len(items) if bucket[0] else 0,'mins':bbmin,'maxs':bbmax})
    # Studio entities are centered in GoldSrc space; do not apply X/Y twice.
    entities.append('{\n"classname" "env_sprite"\n"model" "models/maktab/'+name+'.mdl"\n"origin" "'+' '.join(map(str,center))+'"\n"angles" "0 0 0"\n"framerate" "0"\n"spawnflags" "1"\n"rendermode" "0"\n"renderamt" "255"\n}')
(ROOT/'detail_clusters.json').write_text(json.dumps(manifest,indent=2))
print('Clustered',sum(len(v) for v in groups.values()),'details into',len(groups),'studio entities')
