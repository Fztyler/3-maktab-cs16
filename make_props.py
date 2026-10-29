"""Original low-poly GoldSrc props and a quiet, original looping music cue.

Python + Pillow; compile generated QC files with the Sven Co-op StudioMDL.
All geometry uses GoldSrc units, with +Z up. No downloaded art/audio is used.
"""
from pathlib import Path
import math, random, struct, sys, subprocess, array, json
sys.path.insert(0, str(Path(__file__).with_name('vendor')))
from PIL import Image, ImageDraw

ROOT = Path(__file__).parent
SRC = ROOT / 'custom_assets' / 'source'
OUT = ROOT / 'custom_assets' / 'cstrike'
SRC.mkdir(parents=True, exist_ok=True)
(OUT / 'models' / 'maktab').mkdir(parents=True, exist_ok=True)
(OUT / 'sound' / 'maktab').mkdir(parents=True, exist_ok=True)
rng = random.Random(316)
colors = [(132,91,53),(55,83,70),(83,89,91),(157,83,55),
          (60,101,49),(203,194,163),(119,47,42),(48,78,112),
          (39,73,77),(196,185,151),(34,36,36),(187,99,34),
          (149,156,151),(90,68,49),(183,164,111),(37,50,47)]
atlas = Image.new('RGB',(256,256))
for k,color in enumerate(colors):
    ox,oy=(k%4)*64,(k//4)*64
    for yy in range(64):
        for xx in range(64):
            n=rng.randrange(-5,6)
            if k==0: n+=int(6*math.sin(yy*.6+math.sin(xx*.09)))
            atlas.putpixel((ox+xx,oy+yy),tuple(max(0,min(255,c+n)) for c in color))
d=ImageDraw.Draw(atlas)
# Radio speaker grille, CRT screen and striped ball material.
for yy in range(195,252,4):
    for xx in range(195,252,4): d.ellipse((xx,yy,xx+1,yy+1),fill=(12,19,16))
d.rectangle((3,131,60,188),outline=(25,39,41),width=3)
for yy in range(139,178,7): d.line((12,yy,46-(yy%3)*5,yy),fill=(86,131,125))
for xx in (198,224,250): d.line((xx,128,xx,191),fill=(55,37,24),width=2)
# Clock dial in tile 14.
d.ellipse((130,194,189,253),fill=(224,218,193),outline=(70,69,59),width=2)
for i in range(12):
    a=i*math.pi/6
    d.line((160+22*math.sin(a),224-22*math.cos(a),160+26*math.sin(a),224-26*math.cos(a)),fill=(51,55,49),width=2)
d.line((160,224,160,204),fill=(42,48,46),width=2)
d.line((160,224,175,231),fill=(42,48,46),width=3)
atlas.quantize(colors=256).save(SRC/'props.bmp')

class Mesh:
    def __init__(self): self.tris=[]
    def tri(self,a,b,c,mat,uv=((0,0),(1,0),(1,1))):
        u=[b[i]-a[i] for i in range(3)]; v=[c[i]-a[i] for i in range(3)]
        n=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        length=math.sqrt(sum(q*q for q in n))
        if length<1e-7: return
        n=tuple(q/length for q in n)
        tex=[(((mat%4)*64+2+s*59)/256,1-((mat//4)*64+2+t*59)/256) for s,t in uv]
        self.tris.append((a,b,c,n,tex))
    def quad(self,a,b,c,e,mat):
        self.tri(a,b,c,mat); self.tri(a,c,e,mat,((0,0),(1,1),(0,1)))
    def box(self,a,b,mat):
        x,y,z=a; X,Y,Z=b
        for q in [((x,y,z),(x,y,Z),(x,Y,Z),(x,Y,z)),
                  ((X,y,z),(X,Y,z),(X,Y,Z),(X,y,Z)),
                  ((x,y,z),(X,y,z),(X,y,Z),(x,y,Z)),
                  ((x,Y,z),(x,Y,Z),(X,Y,Z),(X,Y,z)),
                  ((x,y,z),(x,Y,z),(X,Y,z),(X,y,z)),
                  ((x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z))]: self.quad(*q,mat)
    def cylinder(self,a,b,r,mat,n=12,r2=None):
        r2=r if r2 is None else r2
        axis=[b[i]-a[i] for i in range(3)]; ln=math.sqrt(sum(v*v for v in axis)); w=[v/ln for v in axis]
        t=(0,0,1) if abs(w[2])<.9 else (0,1,0)
        u=(w[1]*t[2]-w[2]*t[1],w[2]*t[0]-w[0]*t[2],w[0]*t[1]-w[1]*t[0])
        ln=math.sqrt(sum(v*v for v in u)); u=[v/ln for v in u]
        v=(w[1]*u[2]-w[2]*u[1],w[2]*u[0]-w[0]*u[2],w[0]*u[1]-w[1]*u[0])
        ring=lambda p,rad:[tuple(p[j]+rad*(u[j]*math.cos(i*2*math.pi/n)+v[j]*math.sin(i*2*math.pi/n)) for j in range(3)) for i in range(n)]
        lo,hi=ring(a,r),ring(b,r2)
        for i in range(n):
            k=(i+1)%n
            self.quad(lo[i],lo[k],hi[k],hi[i],mat)
            self.tri(a,lo[k],lo[i],mat)
            self.tri(b,hi[i],hi[k],mat)
    def sphere(self,c,r,mat,n=12,rows=6):
        def p(i,j):
            a=2*math.pi*i/n; b=math.pi*j/rows
            return (c[0]+r*math.sin(b)*math.cos(a),c[1]+r*math.sin(b)*math.sin(a),c[2]+r*math.cos(b))
        for j in range(rows):
            for i in range(n): self.quad(p(i,j),p(i,j+1),p(i+1,j+1),p(i+1,j),mat)
    def save(self,name):
        head='version 1\nnodes\n0 "root" -1\nend\nskeleton\ntime 0\n0 0 0 0 0 0 0\nend\n'
        lines=[head,'triangles\n']
        for a,b,c,n,uv in self.tris:
            lines.append('props.bmp\n')
            for p,t in zip((a,b,c),uv): lines.append('0 '+' '.join(f'{x:.6f}' for x in (*p,*n,*t))+'\n')
        lines.append('end\n'); (SRC/f'{name}.smd').write_text(''.join(lines),encoding='ascii')
        (SRC/'idle.smd').write_text(head.replace('end\n', 'end\n',1),encoding='ascii')
        model=(OUT/'models'/'maktab'/f'{name}.mdl').as_posix()
        qc=f'$modelname "{model}"\n$cd "{SRC.as_posix()}"\n$cdtexture "{SRC.as_posix()}"\n$scale 1\n$body studio "{name}"\n$sequence idle "idle" fps 1 rotate -90\n'
        (SRC/f'{name}.qc').write_text(qc,encoding='ascii')
        return len(self.tris)

meshes={}
m=Mesh()
for x in (-29,29):
    m.box((x-2,-9,0),(x+2,10,21),1)
    m.box((x-2,7,18),(x+2,10,43),1)
for y in (-8,-2,4): m.box((-39,y,19),(39,y+4,22),0)
for z in (29,36): m.box((-39,8,z),(39,11,z+5),0)
m.box((-31,-2,8),(31,1,11),1)
meshes['bench']=m

m=Mesh(); m.cylinder((0,0,2),(0,0,28),9,1,12,r2=11)
m.cylinder((0,0,28),(0,0,30),12,2,12); m.cylinder((0,0,30),(0,0,30.5),9,10,12)
for x in (-12,12): m.box((x-1,-2,23),(x+1,2,29),2)
meshes['bin']=m

m=Mesh(); m.cylinder((0,0,0),(0,0,17),7,3,12,r2=10)
m.cylinder((0,0,15),(0,0,19),11,3,12); m.cylinder((0,0,19),(0,0,19.4),9,13,12)
for i in range(9):
    a=i*2.4; tip=(math.cos(a)*13,math.sin(a)*13,28+i%3*4)
    m.cylinder((0,0,18),tip,.5,4,5)
    p=(tip[0]*.7,tip[1]*.7,tip[2]+7)
    m.quad((0,0,19),(tip[0]-3,tip[1]+2,tip[2]),p,(tip[0]+3,tip[1]-2,tip[2]),4)
    m.quad((0,0,19),(tip[0]+3,tip[1]-2,tip[2]),p,(tip[0]-3,tip[1]+2,tip[2]),4)
meshes['planter']=m

m=Mesh()
for i,mat in enumerate((6,7,1,6)):
    x=(i%2)*2; z=i*3
    m.box((-8+x,-6,z),(8+x,6,z+.6),mat)
    m.box((-7+x,-5.5,z+.6),(7+x,5.5,z+2.4),5)
    m.box((-8+x,-6,z+2.4),(8+x,6,z+3),mat)
    m.box((-8+x,5,z),(8+x,6,z+3),mat)
meshes['books']=m

m=Mesh(); m.box((-10,-8,0),(10,6,2),9)
m.box((-3,-2,2),(3,3,5),9); m.box((-10,-5,5),(10,8,20),9)
m.box((-8,-5.5,7),(8,-5,18),8)
m.box((-12,-17,0),(10,-10,1.5),9)
for y in (-16,-14,-12):
    for x in range(-10,9,3): m.box((x,y,1.5),(x+2,y+1,2),2)
m.box((14,-15,0),(19,-8,2),9)
m.box((15,0,0),(25,14,20),9)
m.box((16,-.5,14),(24,0,16),10)
meshes['computer']=m

m=Mesh(); m.box((-13,-4,0),(13,4,15),0)
m.box((-11,-4.5,2),(3,-4,12),15)
m.box((5,-4.5,9),(11,-4,12),8)
for x in (6,10): m.cylinder((x,-4,5),(x,-6,5),1.5,12,8)
m.box((-7,-1,15),(-5,1,20),10); m.box((5,-1,15),(7,1,20),10)
m.box((-7,-1,19),(7,1,21),10)
m.cylinder((10,1,15),(15,1,34),.45,12,6)
meshes['radio']=m

m=Mesh()
for x,r,h in ((-10,7,10),(10,5,7)):
    m.cylinder((x,0,0),(x,0,h),r,12,12)
    m.cylinder((x,0,h),(x,0,h+1),r+.7,2,12)
    m.cylinder((x,0,h+1),(x,0,h+2),1.5,10,8)
    for side in (-1,1): m.box((x+side*(r+2)-2,-2,h-3),(x+side*(r+2)+2,2,h-1),10)
m.box((-18,12,0),(18,23,1),0)
for i in range(3): m.cylinder((-10+i*10,17,1),(-10+i*10,17,3),4,5,10)
meshes['kitchenware']=m

m=Mesh(); m.cylinder((0,1,0),(0,-1,0),10,2,20)
for i in range(20):
    a=i*math.tau/20; b=(i+1)*math.tau/20
    p=(9*math.cos(a),-1.2,9*math.sin(a)); q=(9*math.cos(b),-1.2,9*math.sin(b))
    m.tri((0,-1.2,0),p,q,14,((.5,.5),(.5+p[0]/20,.5-p[2]/20),(.5+q[0]/20,.5-q[2]/20)))
meshes['clock']=m

m=Mesh()
for x in (-24,24):
    for y in (-8,8): m.cylinder((x,y,0),(x,y,38),1,2,6)
for z in (7,25):
    for y in (-7,7): m.cylinder((-24,y,z),(24,y,z),1,2,6)
    for x in (-15,0,15): m.sphere((x,0,z+6),6,11,10,5)
meshes['ballrack']=m

# Upholstered audience chair, ready for the assembly-hall seating rows.
m=Mesh()
for x in (-8,8):
    for y in (-7,7): m.cylinder((x,y,0),(x,y,19),.9,2,6)
    m.cylinder((x,7,17),(x,9,37),.9,2,6)
m.box((-10,-9,17),(10,9,19),2)
m.box((-9,-8,19),(9,8,22),7)
m.box((-10,8,25),(10,11,38),2)
m.box((-9,7.5,26),(9,8.5,37),7)
meshes['hall_chair']=m

stats={name:mesh.save(name) for name,mesh in meshes.items()}
compiler=ROOT/'tools'/'studiomdl'/'studiomdl.exe'
for name in meshes:
    result=subprocess.run([str(compiler),str(SRC/f'{name}.qc')],cwd=SRC,capture_output=True,text=True)
    (SRC/f'{name}.log').write_text(result.stdout+result.stderr)
    if result.returncode or not (OUT/'models'/'maktab'/f'{name}.mdl').exists():
        raise RuntimeError(result.stdout+result.stderr)

# A 32-second D-major pentatonic ambient miniature: soft pad and bell notes.
# Fully synthesized here, with wrap-around tails for an inaudible loop seam.
rate=22050; duration=32; count=rate*duration
samples=[0.0]*count
def note(start,secs,midi,amp,bell=False):
    hz=440*2**((midi-69)/12)
    for j in range(int(secs*rate)):
        t=j/rate
        env=(1-math.exp(-t/(.012 if bell else .8)))*math.exp(-t/(1.4 if bell else 3))
        env*=min(1,(secs-t)/.5)
        tone=math.sin(2*math.pi*hz*t)+(.2 if bell else .12)*math.sin(2*math.pi*hz*2*t)
        samples[(int(start*rate)+j)%count]+=amp*env*tone
for bar,chord in enumerate(((50,57,66),(47,54,62),(43,50,59),(45,52,61))):
    for p in chord: note(bar*8,10,p,.07)
melody=(74,78,81,78,76,74,71,74,78,81,83,81,78,76,74,69)
for i,p in enumerate(melody): note(i*2+.5,3.5,p,.095,True)
# A short room-like delay, circular so the boundary stays seamless.
mixed=[samples[i]+.18*samples[(i-int(rate*.23))%count]+.10*samples[(i-int(rate*.41))%count] for i in range(count)]
peak=max(abs(v) for v in mixed)
pcm=array.array('h',(round(v/max(peak,1)*17000) for v in mixed)).tobytes()
def chunk(name,payload): return name+struct.pack('<I',len(payload))+payload+(b'\0' if len(payload)%2 else b'')
fmt=struct.pack('<HHIIHH',1,1,rate,rate*2,2,16)
cue=struct.pack('<I',1)+struct.pack('<II4sIII',1,0,b'data',0,0,0)
body=b'WAVE'+chunk(b'fmt ',fmt)+chunk(b'cue ',cue)+chunk(b'data',pcm)
(OUT/'sound'/'maktab'/'courtyard_radio.wav').write_bytes(b'RIFF'+struct.pack('<I',len(body))+body)
(ROOT/'custom_assets'/'asset_manifest.json').write_text(json.dumps({'models_triangles':stats,'music_seconds':duration,'music_peak':peak},indent=2))
print(json.dumps(stats)); print('Music: 32 sec, 22050 Hz mono PCM, loop cue included')

