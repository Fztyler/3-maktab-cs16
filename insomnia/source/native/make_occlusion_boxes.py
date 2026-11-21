"""Export only provably solid, axis-aligned map brushes for conservative culling."""
from pathlib import Path
import json, re, struct, zlib, sys

def entities(text):
    depth=0; lines=[]
    for line in text.splitlines():
        if depth==0 and line.strip()!='{':continue
        lines.append(line)
        if line.strip()=='{':depth+=1
        elif line.strip()=='}':
            depth-=1
            if depth==0:yield lines;lines=[]

def box(faces):
    if len(faces)!=6:return None
    points=[];planes=set()
    for line in faces:
        matches=re.findall(r'\(([^()]+)\)',line)
        if len(matches)!=3:return None
        p=[tuple(map(float,m.split())) for m in matches]
        texture=line.rsplit(')',1)[1].split()[0].upper()
        if texture.startswith(('{','!')) or texture in ('SKY','CLIP','ORIGIN','NULL','HINT','SKIP','AAATRIGGER'):return None
        axes=[i for i in range(3) if max(v[i] for v in p)-min(v[i] for v in p)<0.001]
        if len(axes)!=1:return None
        planes.add((axes[0],p[0][axes[0]]));points+=p
    if len(planes)!=6 or any(sum(a==i for a,d in planes)!=2 for i in range(3)):return None
    # MAP stores plane-defining points, which need not be actual brush vertices.
    lo=[min(d for a,d in planes if a==i) for i in range(3)]
    hi=[max(d for a,d in planes if a==i) for i in range(3)]
    if min(hi[i]-lo[i] for i in range(3))<1.0:return None
    return lo+hi

def export(source,bsp,output):
    records=[];names=set();skipped=0
    bsp_data=bsp.read_bytes()
    entity_offset,entity_length=struct.unpack_from('<II',bsp_data,4)
    compiled={}
    for raw in re.findall(r'\{[^{}]*\}',bsp_data[entity_offset:entity_offset+entity_length].decode('latin1')):
        kv=dict(re.findall(r'"([^"\n]+)" "([^"\n]*)"',raw))
        if kv.get('targetname'):compiled[kv['targetname']]=kv
    for entity in entities(source.read_text(encoding='utf-8')):
        raw='\n'.join(entity)
        kv=dict(re.findall(r'^"([^"\n]+)" "([^"\n]*)"$',raw,re.M))
        kind=kv.get('classname','')
        if kind not in ('worldspawn','func_detail','func_wall','func_breakable'):continue
        if kv.get('rendermode','0')!='0':continue
        name='' if kind in ('worldspawn','func_detail') else kv.get('targetname','')
        if not name and kind not in ('worldspawn','func_detail'):continue
        if name.startswith('maktab_glass_'):continue
        if name and name not in compiled:continue
        origin=list(map(float,compiled[name].get('origin','0 0 0').split())) if name else [0.0]*3
        faces=[]
        for line in entity[1:]:
            if line.strip()=='}' and faces:
                bounds=box(faces);faces=[]
                if bounds is None:skipped+=1;continue
                assert len(name.encode())<48
                records.append(struct.pack('<48s9f',name.encode(),*bounds,*origin));names.add(name)
            elif line.lstrip().startswith('('):faces.append(line)
    output.parent.mkdir(parents=True,exist_ok=True)
    crc=zlib.crc32(bsp_data)
    output.write_bytes(struct.pack('<8sII',b'INSOCC01',crc,len(records))+b''.join(records))
    info={'bsp':str(bsp),'bsp_crc32':f'{crc:08x}','records':len(records),'owners':len(names),'skipped_nonboxes':skipped}
    output.with_suffix('.json').write_text(json.dumps(info,indent=2))
    print(json.dumps(info))

if __name__=='__main__':export(*(Path(x) for x in sys.argv[1:4]))
