from pathlib import Path
import re,struct,json,shutil,hashlib,zipfile
import verify_map as v
b=Path(__file__).parent;r=b.parent/'github_publish';out=r/'mini';out.mkdir(exist_ok=True);g=Path(r'N:\Counter-Strike 1.6\cstrike')
before=hashlib.sha256((g/'maps/de_3_maktab.bsp').read_bytes()).hexdigest()
# Same geometry and objectives: mini means a closer engagement with both teams in big corpus.
spots=[]
for yi in range(3000,1450,-100):
 for xi in range(-1680,-1030,90):
  x,y=xi/100,yi/100;p=v.scene_point(x,y,48)
  if v.contents(p)==-1 and v.world_solid(v.scene_point(x,y,7)):
   spots.append(p)
  if len(spots)==20:break
 if len(spots)==20:break
assert len(spots)==20
offset=(1166,-1220,-128)
data=(b/'de_3_maktab.bsp').read_bytes();lumps=[data[a:a+n] for a,n in [struct.unpack_from('<ii',data,4+i*8) for i in range(15)]]
ents=re.findall(r'\{[^{}]*\}',lumps[0].decode('latin1'));index=0
for i,e in enumerate(ents):
 kv=v.props(e)
 if kv.get('classname')=='worldspawn':
  e=e.replace('"message" "3-MAKTAB | School, Uzbekistan"','"message" "Day3 Map Mini"');e=e[:-1]+'"maxrange" "8192"\n}'
 if kv.get('classname')=='info_player_deathmatch':
  e=re.sub(r'"origin" "[^"]+"','"origin" "'+' '.join(map(str,spots[index]))+'"',e);index+=1
 if kv.get('classname')=='func_buyzone' and kv.get('team')=='1':
  box=v.models[int(kv['model'][1:])][:6]
  # Center the existing buy trigger on the selected northern spawn grid.
  center=[sum(p[j] for p in spots)/len(spots) for j in range(3)]
  offset=tuple(round(center[j]-(box[j]+box[j+3])/2) for j in range(3))
  assert all(all(box[j]+offset[j]<=p[j]<=box[j+3]+offset[j] for j in range(3)) for p in spots)
  e=e[:-1]+'"origin" "'+' '.join(map(str,offset))+'"\n}'
 ents[i]=e
lumps[0]=('\n'.join(ents)+'\n\0').encode('latin1');raw=bytearray(data[:124])
for i,lump in enumerate(lumps):
 while len(raw)%4:raw.append(0)
 struct.pack_into('<ii',raw,4+i*8,len(raw),len(lump));raw.extend(lump)
(out/'de_3_maktab_mini.bsp').write_bytes(raw)
nav=bytearray((g/'maps/de_3_maktab.nav').read_bytes());struct.pack_into('<I',nav,8,len(raw));(out/'de_3_maktab_mini.nav').write_bytes(nav)
# Navigation geometry is byte-for-byte unchanged; only its BSP-size identity changes.
assert all(lumps[i]==data[a:a+n] for i,(a,n) in enumerate([struct.unpack_from('<ii',data,4+i*8) for i in range(15)]) if i!=0)
source=(b/'maktab_penetration.sma').read_text().replace('"de_3_maktab"','"de_3_maktab_mini"').replace('register_plugin("Maktab wall penetration"','register_plugin("Day3 Mini support"').replace('new map[32];','set_cvar_float("sv_zmax",8192.0);\n    new map[32];')
(out/'maktab_mini.sma').write_text(source)
cfg=(b/'de_3_maktab.cfg').read_text();(out/'de_3_maktab_mini.cfg').write_text(cfg)
(out/'plugins-de_3_maktab_mini.ini').write_text('maktab_mini.amxx\n')
shutil.copy2(b/'de_3_maktab.res',out/'de_3_maktab_mini.res')
(out/'spawn_layout.json').write_text(json.dumps({'T':spots,'buyzone_translation':offset,'geometry':'unchanged','view_distance':8192},indent=2))
(out/'README.md').write_text('''# Day3 Map Mini — de_3_maktab_mini

[Download MINI installer](https://github.com/Fztyler/3-maktab-cs16/raw/refs/heads/main/mini/DAY3_MAP_MINI.zip)

Распакуй архив, закрой CS, запусти INSTALL.cmd, выбери папку с hl.exe. Затем запусти PLAY_DAY3_MINI.cmd в папке игры.

Отдельная карта: оригинальная de_3_maktab не заменяется. Обе команды появляются внутри большого корпуса. T — первый этаж, северо-западная часть; CT — второй этаж на юго-востоке. Геометрия, двор и плент A/B сохранены: Mini отличается близким размещением команд, а не обрезанием территории. Дальность maxrange и sv_zmax — 8192. В комплекте все ресурсы и серверная поддержка для Windows.

Проверены 20 свободных спаунов T, зона покупки, неизменность геометрии/NAV и сохранность основной карты. Полный игровой матч этой версии не проводился.
''',encoding='utf8')
shutil.copy2(__file__,out/'create_mini.py')
assert hashlib.sha256((g/'maps/de_3_maktab.bsp').read_bytes()).hexdigest()==before
print('MINI generated; T spawns:',spots)


