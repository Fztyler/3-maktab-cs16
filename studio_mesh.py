"""Read static studio-model geometry for grove batching; keep indexed textures."""
import struct,math
from pathlib import Path
from mathutils import Matrix,Vector,Euler

def studio_triangles(path,destination,prefix):
    data=Path(path).read_bytes()
    def ints(off,n): return struct.unpack_from('<'+'i'*n,data,off)
    def vec(off): return Vector(struct.unpack_from('<3f',data,off))
    bones,bo=ints(140,2); transforms=[]
    for i in range(bones):
        at=bo+i*112; parent=ints(at+32,1)[0]
        p=vec(at+64); angles=tuple(vec(at+76))
        local=Matrix.Translation(p)@Euler(angles,'XYZ').to_matrix().to_4x4()
        transforms.append(transforms[parent]@local if parent>=0 else local)
    nt,ti=ints(180,2); texture=[]; masked=[]
    for i in range(nt):
        flags,w,h,pixel=ints(ti+i*80+64,4); name=f'{prefix}_{i}.bmp'
        pixels=data[pixel:pixel+w*h]; palette=data[pixel+w*h:pixel+w*h+768]
        if len(palette)!=768: raise ValueError('External studio texture required')
        stride=(w+3)&~3
        rows=b''.join(pixels[y*w:(y+1)*w]+b'\0'*(stride-w) for y in range(h-1,-1,-1))
        pal=b''.join(bytes((palette[j+2],palette[j+1],palette[j],0)) for j in range(0,768,3))
        header=b'BM'+struct.pack('<IHHI',1078+len(rows),0,0,1078)+struct.pack('<IiiHHIIiiII',40,w,h,1,8,0,len(rows),0,0,256,256)
        (destination/name).write_bytes(header+pal+rows)
        texture.append((name,w,h))
        if flags&64: masked.append(name)
    nskin=ints(192,1)[0]; skinat=ints(200,1)[0]
    skins=struct.unpack_from('<'+'h'*nskin,data,skinat)
    nbody,body=ints(204,2); triangles=[]
    for part in range(nbody):
        model=ints(body+part*76+72,1)[0]
        nm,meshat,nv,vbi,vat,nn,nbi,nat=ints(model+72,8)
        vertices=[transforms[data[vbi+i]]@vec(vat+i*12) for i in range(nv)]
        normals=[(transforms[data[nbi+i]].to_3x3()@vec(nat+i*12)).normalized() for i in range(nn)]
        for mesh in range(nm):
            _,commands,skin,_,_=ints(meshat+mesh*20,5)
            material,w,h=texture[skins[skin]]
            while True:
                count=struct.unpack_from('<h',data,commands)[0]; commands+=2
                if not count: break
                entries=[]
                for i in range(abs(count)):
                    vi,ni,s,t=struct.unpack_from('<4h',data,commands); commands+=8
                    entries.append((*vertices[vi],*normals[ni],s/w,1-t/h))
                for i in range(2,abs(count)):
                    a,b,c=(entries[0],entries[i-1],entries[i]) if count<0 else ((entries[i-2],entries[i-1],entries[i]) if i%2==0 else (entries[i-1],entries[i-2],entries[i]))
                    normal=(Vector(b[:3])-Vector(a[:3])).cross(Vector(c[:3])-Vector(a[:3]))
                    if normal.dot(Vector(a[3:6])+Vector(b[3:6])+Vector(c[3:6]))<0: b,c=c,b
                    triangles.append((material,(a,b,c)))
    return triangles,masked
