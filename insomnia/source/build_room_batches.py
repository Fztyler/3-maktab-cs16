"""Build local lighting groups without increasing the number of precached models."""
from collections import defaultdict
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parent
BUILD = ROOT.parent
MODEL_COUNT = 6
GROUP_SIZE = 31
MODELS = ROOT / 'custom_assets/cstrike/models/maktab'
SOURCE = ROOT / 'room_batch_source'
SOURCE.mkdir(exist_ok=True)
spec = importlib.util.spec_from_file_location('mesh_tools', BUILD / 'tools/runtime_compat/build_furniture_batches.py')
mesh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mesh)
mesh.SOURCE = SOURCE


def read_map_entities(data):
    offset, size = struct.unpack_from('<II', data, 4)
    return [dict(re.findall(r'"([^"\n]+)" "([^"\n]*)"', raw))
            for raw in re.findall(r'\{[^{}]*\}', data[offset:offset+size].decode('latin1'))]


def room_zones():
    classrooms = json.loads((ROOT / 'classroom_layouts.json').read_text(encoding='utf-8'))
    big = json.loads((ROOT / 'new_big_layout.json').read_text(encoding='utf-8'))
    zones = []
    for room in classrooms:
        zones.append((room['box'], room['floor'], 24))
    for room in big['rooms']:
        floors = (8,) if room['name'] == 'zal' else (8, big['upper_floor_z'])
        zones.extend((room['bounds'], floor, 2) for floor in floors)
    locker = json.loads((ROOT/'north_locker_layout.json').read_text())
    zones.append((locker['room'],8,24))
    return zones


def zone_key(origin, zones):
    x, y, z = origin
    for i, ((x0, x1, y0, y1), floor, margin) in enumerate(zones):
        if ((x0+28)*40-margin <= x <= (x1+28)*40+margin and
            (y0-20)*40-margin <= y <= (y1-20)*40+margin and floor <= z < floor+115):
            return i
    return None


def batches(props, zones):
    by_room = defaultdict(list)
    loose = [[], [], []]
    for prop in props:
        kind = prop['kind']
        room = zone_key(prop['origin'], zones) if kind == 0 else None
        (by_room[room] if room is not None else loose[kind]).append(prop)

    def emit(members, origin=None):
        kind = members[0]['kind']
        for bit, prop in enumerate(members):
            prop['bit'] = bit
        if origin is None:
            origin = list(members[0]['origin'])
            # Frames and glass face the exterior. Sampling at a wall or
            # inside an adjacent dark room turns the whole window group black.
            if kind in (1, 2):
                origin[2] = 1024.0
            elif kind == 0:
                origin[2] += 28.0
        return dict(props=members, origin=origin, transparent=kind == 2, kind=kind)

    for room, members in sorted(by_room.items()):
        _, floor, _ = zones[room]
        center = [sum(p['origin'][axis] for p in members) / len(members) for axis in (0, 1)]
        # Prefer a known furniture position inside the occupied room. A room
        # centroid can fall behind a partition in a nonrectangular classroom.
        anchor = min(members, key=lambda p: sum((p['origin'][axis]-center[axis])**2 for axis in (0, 1)))
        origin = [*anchor['origin'][:2], float(floor + 55)]
        members.sort(key=lambda p: (p['origin'][1], p['origin'][0], p['name']))
        for start in range(0, len(members), GROUP_SIZE):
            yield emit(members[start:start+GROUP_SIZE], origin)

    for remaining in loose:
        remaining.sort(key=lambda p: (p['origin'][2], p['origin'][0], p['origin'][1]))
        while remaining:
            first = remaining.pop(0)
            anchor = first['origin']
            candidates = sorted(remaining, key=lambda p: sum((p['origin'][i]-anchor[i])**2*(4 if i==2 else 1) for i in range(3)))
            members = [first, *candidates[:GROUP_SIZE-1]]
            for prop in members[1:]:
                remaining.remove(prop)
            yield emit(members)


def source_winding(triangle):
    # Studio triangle commands use the opposite order from SMD faces.
    # Match the stored normal when re-emitting geometry and keep UVs on
    # their corresponding vertices.
    a,b,c=triangle
    u=[b[i]-a[i] for i in range(3)]
    v=[c[i]-a[i] for i in range(3)]
    cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
    return (a,c,b) if sum(cross[i]*(a[i+3]+b[i+3]+c[i+3]) for i in range(3))<0 else triangle


def emit_model(index, groups, furniture, frames, glass, textures):
    stem = (f'insomnia_facade_frame_{index:02d}' if any(group['kind'] == 1 for group in groups)
            else f'insomnia_facade_room_{index:02d}')
    output = MODELS / (stem + '.mdl')
    choices = defaultdict(list)
    materials = {}
    texture_owners = {}
    for skin, group in enumerate(groups):
        origin = group['origin']
        group['skin'] = skin
        group['model'] = 'models/maktab/' + output.name
        vertices = []
        for prop in group['props']:
            kind = prop['kind']
            ass = (furniture[prop['type']] if kind == 0 else frames[prop['name']] if kind == 1 else glass[prop['type']])
            offset = [p-q for p, q in zip(prop['origin'], origin)]
            for name, triangle in ass:
                triangle=source_winding(triangle)
                tile = (skin, kind, name)
                if tile not in materials:
                    _, *bitmap = textures[kind][name]
                    filename = f'r12_{len(materials):02d}.bmp'
                    mesh.bmp(filename, *bitmap)
                    materials[tile] = filename
                    texture_owners[filename] = skin
                transformed = tuple(mesh.move_vertex(v, offset, prop['angles'][1]) for v in triangle)
                choices[prop['bit']].append((materials[tile], transformed))
                vertices.extend(transformed)
        group['lo'] = [min(v[i] for v in vertices)-1 for i in range(3)]
        group['hi'] = [max(v[i] for v in vertices)+1 for i in range(3)]

    bodies = []
    for bit, triangles in sorted(choices.items()):
        name = f'{stem}_{bit:02d}'
        lines = [mesh.HEADER, 'triangles\n']
        for material, vertices in triangles:
            lines.append(material+'\n')
            lines.extend('0 '+' '.join(f'{value:.6f}' for value in v)+'\n' for v in vertices)
        (SOURCE / (name+'.smd')).write_text(''.join(lines)+'end\n', encoding='ascii')
        bodies.append(f'$bodygroup prop{bit:02d}\n{{\n studio "{name}"\n blank\n}}')
    corners = [min(g['lo'][i] for g in groups) for i in range(3)] + [max(g['hi'][i] for g in groups) for i in range(3)]
    box = ' '.join(map(str, corners))
    qc = SOURCE / (stem+'.qc')
    qc.write_text(f'$modelname "{output.as_posix()}"\n$cd "{SOURCE.as_posix()}"\n'
                  f'$cdtexture "{SOURCE.as_posix()}"\n$bbox {box}\n$cbox {box}\n'
                  +'\n'.join(bodies)+'\n$sequence idle "idle" fps 1 rotate -90\n', encoding='ascii')
    result = subprocess.run([str(BUILD/'tools/studiomdl/studiomdl.exe'), str(qc)], cwd=SOURCE, capture_output=True, text=True)
    if result.returncode or 'ERROR' in result.stdout:
        raise RuntimeError(result.stdout+result.stderr)
    actual, tiles = mesh.read_model(output)
    if len(actual) != len(choices) or any(not mesh.geometry_matches(choices[i], body[0]) for i, body in enumerate(actual)):
        raise ValueError(f'Unexpected geometry in {stem}')

    if len(groups) > 1:
        replace_material_table(output, groups, texture_owners, tiles)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    for group in groups:
        group['sha256'] = digest


def replace_material_table(output, groups, owners, tiles):
    # Studio MDLs share an indexed mesh between skin families. Hide the other
    # rooms with a completely masked texture, keeping body damage bits separate.
    data = bytearray(output.read_bytes())
    count, table_at = struct.unpack_from('<2i', data, 180)
    refs, families, old_skins_at = struct.unpack_from('<3i', data, 192)
    assert count == refs and families == 1 and count < 63
    table = bytearray(data[table_at:table_at+count*80])
    old_skins = struct.unpack_from(f'<{refs}h', data, old_skins_at)
    skin_entries = [old if owners[tiles[old][0]] == skin else count
                    for skin in range(len(groups)) for old in old_skins]
    table.extend(struct.pack('<64s4i', b'{room_hidden.bmp', 64, 8, 8, 0))
    pixels = bytearray()
    skins_at = table_at + len(table)
    pixels_at = skins_at + len(skin_entries)*2
    for i, (_, _, _, indices, palette) in enumerate(tiles):
        struct.pack_into('<i', table, i*80+76, pixels_at+len(pixels))
        pixels.extend(indices+palette)
    struct.pack_into('<i', table, count*80+76, pixels_at+len(pixels))
    pixels.extend(bytes([255])*64+bytes(768))
    packed = data[:table_at]+table+struct.pack(f'<{len(skin_entries)}h', *skin_entries)+pixels
    struct.pack_into('<i', packed, 72, len(packed))
    struct.pack_into('<3i', packed, 180, count+1, table_at, pixels_at)
    struct.pack_into('<3i', packed, 192, refs, len(groups), skins_at)
    output.write_bytes(packed)


def read_frame_textures(names):
    from PIL import Image
    textures = {}
    for name in names:
        with Image.open(SOURCE / name) as bitmap:
            assert bitmap.mode == 'P'
            textures[name] = (name, bitmap.width, bitmap.height, bitmap.tobytes(), bytes(bitmap.getpalette()))
    return textures


def write_include(groups):
    lines = ['new const BATCH_MODELS[][]={', *('"'+g['model']+'",' for g in groups), '};']
    for label, key in [('BATCH_TRANSPARENT', 'transparent'), ('BATCH_SKIN', 'skin')]:
        lines.extend([f'new const {label}[]={{', *(str(int(g[key]))+',' for g in groups), '};'])
    for label, key in [('BATCH_POS', 'origin'), ('BATCH_LO', 'lo'), ('BATCH_HI', 'hi')]:
        lines.extend([f'new const Float:{label}[][3]={{', *('{'+','.join(f'{v:.6f}' for v in g[key])+'},' for g in groups), '};'])
    lines.append('new const BATCH_MAP[][4]={')
    lines.extend('{'+f'{int(p["name"].rsplit("_",1)[1])},{i},{p["bit"]},{p["kind"]}'+'},'
                 for i,g in enumerate(groups) for p in g['props'])
    lines.append('};')
    (ROOT / 'insomnia_batches_data.inc').write_text('\n'.join(lines)+'\n', encoding='ascii')


def main():
    (SOURCE / 'idle.smd').write_text(mesh.HEADER, encoding='ascii')
    bsp = (ROOT / 'de_insomnia_project_t.bsp').read_bytes()
    entities = read_map_entities(bsp)
    frames = mesh.read_frame_meshes(bsp, entities)
    furniture, furniture_textures = mesh.read_model(MODELS / 'insomnia_furniture.mdl')
    glass, glass_textures = mesh.read_model(MODELS / 'insomnia_glass.mdl')
    decorations = []
    for ent in entities:
        name = ent.get('targetname', '')
        kind = next((i for i,prefix in enumerate(('insomnia_furniture_', 'maktab_frame_', 'maktab_glass_')) if name.startswith(prefix)), None)
        if kind is None:
            continue
        decorations.append(dict(name=name, origin=list(map(float, ent['origin'].split())),
                                angles=list(map(float, ent.get('angles', '0 0 0').split())),
                                kind=kind, type=-1 if kind == 1 else int(ent['netname'])))
    frame_materials = {key for tris in frames.values() for key,_ in tris}
    lookup = [{t[0]:t for t in furniture_textures},
              read_frame_textures(frame_materials),
              {t[0]:t for t in glass_textures}]
    groups = list(batches(decorations, room_zones()))
    assert sum(len(g['props']) for g in groups) == len(decorations)
    # Exterior panes can be visible while the rooms are behind solid walls.
    # Pack them together so their models no longer carry hidden room meshes.
    rooms=[group for group in groups if group['kind']==0]
    panes=[group for group in groups if group['kind']!=0]
    for index in range(MODEL_COUNT-1):
        families=rooms[index::MODEL_COUNT-1]
        if families:
            emit_model(index,families,furniture[0],frames,glass[0],lookup)
    if panes:
        emit_model(MODEL_COUNT-1,panes,furniture[0],frames,glass[0],lookup)
    write_include(groups)
    (ROOT / 'batches_manifest.json').write_text(json.dumps(groups, indent=2), encoding='utf-8')
    print(f'{len(groups)} local-light groups in {min(MODEL_COUNT, len(groups))} models, {len(decorations)} independent objects')


if __name__ == '__main__':
    main()
