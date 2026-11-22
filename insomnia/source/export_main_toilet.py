"""Export the WC source geometry used by the GoldSrc map and studio models."""
import json
from pathlib import Path

import bmesh
import bpy

result={}
for obj in bpy.context.scene.objects:
    if obj.type != 'MESH':
        continue
    mesh=obj.data
    xyz=[[round(v,5) for v in obj.matrix_world @ vert.co] for vert in mesh.vertices]
    result[obj.name]={'xyz':xyz,'faces':[list(poly.vertices) for poly in mesh.polygons]}
    if obj.name in ('WTF_main','WTR_adt','KRAN'):
        bm=bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        bmesh.ops.triangulate(bm,faces=list(bm.faces))
        bm.verts.index_update()
        result[obj.name]['faces']=[tuple(v.index for v in face.verts) for face in bm.faces]
        bm.free()
Path(__file__).with_name('main_toilet_mesh.json').write_text(json.dumps(result,indent=2))
print('Exported',len(result),'WC meshes')
