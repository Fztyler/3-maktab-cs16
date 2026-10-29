"""Share identical window BSP submodels, keeping separate entities and damage.
Run after RAD. Accepts MAP/BSP paths so manual edits use the same optimization.
"""
import re,struct,math,sys,json
from pathlib import Path
map_path=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name('de_3_maktab.map')
bsp_path=Path(sys.argv[2]) if len(sys.argv)>2 else map_path.with_suffix('.bsp')
def map_entities(text):
    depth=0;block=[]
    for line in text.splitlines():
        stripped=line.strip()
        if depth==0 and stripped!='{':continue
        block.append(line)
        if stripped=='{':depth+=1
        elif stripped=='}':
            depth-=1
            if depth==0:yield block;block=[]
def fingerprint(lines,origin):
    shapes=[];faces=[]
    for line in lines:
        if line.strip()=='{' and faces:raise ValueError('Unexpected nested brush')
        if line.strip()=='}':
            if faces:shapes.append(tuple(sorted(faces)));faces=[]
        if not line.lstrip().startswith('('):continue
        prefix,tail=line.rsplit(')',1);prefix+=')'
        points=[tuple(map(float,p.split())) for p in re.findall(r'\(\s*([^()]*)\)',prefix)]
        a,b,c=points;u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
        n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];length=math.sqrt(sum(x*x for x in n));n=[x/length for x in n]
        distance=sum(n[i]*(a[i]-origin[i]) for i in range(3))
        parts=tail.split();texture=parts[0]
        if '[' in tail:
            vectors=[list(map(float,x.split())) for x in re.findall(r'\[([^]]+)\]',tail)]
            after=tail.rsplit(']',1)[1].split();scale=list(map(float,after[1:3]));tu,tv=vectors[0][:3],vectors[1][:3];shift=[vectors[0][3],vectors[1][3]]
        else:
            su,sv,rotation,sx,sy=map(float,parts[1:6]);assert rotation==0,'Use Valve220 for rotated manual UVs'
            axis=max([2,0,1],key=lambda i:abs(n[i]));tu,tv=((1,0,0),(0,-1,0)) if axis==2 else ((0,1,0),(0,0,-1)) if axis==0 else ((1,0,0),(0,0,-1));shift=[su,sv];scale=[sx,sy]
        uv=[]
        for vector,offset,size in zip((tu,tv),shift,scale):uv+=list(x/size for x in vector)+[offset+sum(vector[i]*origin[i] for i in range(3))/size]
        faces.append((tuple(round(x,5) for x in n),round(distance,4),texture,tuple(round(x,4) for x in uv)))
    return tuple(sorted(shapes))
keys={}
for lines in map_entities(map_path.read_text(encoding='utf8')):
    kv=dict(re.findall(r'^"([^"\n]+)" "([^"\n]*)"$','\n'.join(lines),re.M));name=kv.get('targetname','')
    if not name.startswith(('maktab_glass_','maktab_frame_')):continue
    assert name not in keys, 'Duplicate window target name: '+name
    origin=tuple(map(float,kv.get('origin','0 0 0').split()));keys[name]=fingerprint(lines,origin)
d=bytearray(bsp_path.read_bytes());lumps=[struct.unpack_from('<ii',d,4+8*i) for i in range(15)];p,n=lumps[0];text=bytes(d[p:p+n]).decode('latin1');entities=re.findall(r'\{[^{}]*\}',text)
p,n=lumps[14];models=[bytes(d[i:i+64]) for i in range(p,p+n,64)];reps={};replacements={}
for block in entities:
    kv=dict(re.findall(r'"([^"\n]+)" "([^"\n]*)"',block));name=kv.get('targetname','')
    if name not in keys:continue
    index=int(kv['model'][1:]);key=keys[name]
    if key in reps:
        rep=reps[key];a=struct.unpack('<9f7i',models[index]);b=struct.unpack('<9f7i',models[rep]);assert all(abs(x-y)<.01 for x,y in zip(a[:9],b[:9])),('Shared model bounds differ',name,a[:9],b[:9]);replacements[index]=rep
    else:reps[key]=index
keep=[i for i in range(len(models)) if i not in replacements];remap={i:j for j,i in enumerate(keep)}
for i,j in replacements.items():remap[i]=remap[j]
newtext=re.sub(r'"model" "\*(\d+)"',lambda m:'"model" "*'+str(remap[int(m[1])])+'"',text)
newlumps=[bytes(d[a:a+b]) for a,b in lumps];newlumps[0]=newtext.encode('latin1');newlumps[14]=b''.join(models[i] for i in keep)
out=bytearray(d[:124]);descriptors=[]
for data in newlumps:
    while len(out)%4:out.append(0)
    descriptors.append((len(out),len(data)));out.extend(data)
for i,pair in enumerate(descriptors):struct.pack_into('<ii',out,4+8*i,*pair)
assert len(keep)+26+150<512, 'Insufficient model budget after deduplication'
bsp_path.write_bytes(out)
report={'before':len(models),'after':len(keep),'independent_parts':len(keys),'shared_shapes':len(reps)}
bsp_path.with_suffix('.window_models.json').write_text(json.dumps(report,indent=2));print('Window submodels:',report)
