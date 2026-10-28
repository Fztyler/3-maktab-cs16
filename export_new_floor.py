import bpy,json
from pathlib import Path
from mathutils import Vector
out=[]
for o in bpy.data.objects:
    if o.type!='MESH': continue
    verts=[tuple(o.matrix_world@v.co) for v in o.data.vertices]
    out.append({'name':o.name,'verts':verts,'faces':[list(p.vertices) for p in o.data.polygons]})
Path(r'N:\3_maktab_map\cs16_build\new_floor_meshes.json').write_text(json.dumps(out,ensure_ascii=False),encoding='utf8')
