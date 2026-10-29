from pathlib import Path
import re,math
root=Path(__file__).parent
src=root/'de_3_maktab.map';dst=root/'editor_validation/de_3_maktab.map';dst.parent.mkdir(exist_ok=True)
pattern=re.compile(r'^(\(.*\)) (\S+) ([-\d.e]+) ([-\d.e]+) ([-\d.e]+) ([-\d.e]+) ([-\d.e]+)$')
count=0;lines=[]
for line in src.read_text(encoding='utf8').splitlines():
 m=pattern.match(line)
 if m:
  prefix,texture,shiftu,shiftv,rotate,scaleu,scalev=m.groups();assert float(rotate)==0
  points=[tuple(map(float,x.split())) for x in re.findall(r'\(\s*([^()]*)\s*\)',prefix)]
  a,b,c=points;u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
  normal=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
  # Standard Quake axial projection; Z wins ties, then X, then Y.
  axis=max([2,0,1],key=lambda i:abs(normal[i]))
  tu,tv=('1 0 0','0 -1 0') if axis==2 else ('0 1 0','0 0 -1') if axis==0 else ('1 0 0','0 0 -1')
  line=f'{prefix} {texture} [ {tu} {shiftu} ] [ {tv} {shiftv} ] 0 {scaleu} {scalev}';count+=1
 lines.append(line)
 if line=='"classname" "worldspawn"':lines.append('"mapversion" "220"')
dst.write_text('\n'.join(lines)+'\n',encoding='utf8');print('Valve 220 projection exported:',count,'faces')
