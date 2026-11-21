"""Fill the deep baked shadows on the opaque exterior along the rear stairs."""
from collections import defaultdict
import json
from pathlib import Path
import re
import struct
import sys


def fill_stair_facade(path):
    data = bytearray(path.read_bytes())
    lumps = [struct.unpack_from('<ii', data, 4 + i * 8) for i in range(15)]

    def raw(index):
        start, size = lumps[index]
        return data[start:start + size]

    models = list(struct.iter_unpack('<9f7i', raw(14)))
    faces = list(struct.iter_unpack('<Hhihh4Bi', raw(7)))
    planes = list(struct.iter_unpack('<4fi', raw(1)))
    vertices = list(struct.iter_unpack('<3f', raw(3)))
    edges = list(struct.iter_unpack('<2H', raw(12)))
    surfedges = [edge[0] for edge in struct.iter_unpack('<i', raw(13))]
    texinfo = list(struct.iter_unpack('<8fii', raw(6)))
    textures = raw(2)
    texture_count = struct.unpack_from('<i', textures)[0]
    texture_offsets = struct.unpack_from(f'<{texture_count}i', textures, 4)
    texture_names = [bytes(textures[n:n+16]).split(b'\0', 1)[0] if n >= 0 else b'' for n in texture_offsets]
    origins = {}
    for block in re.findall(r'\{[^{}]*\}', raw(0).decode('latin1')):
        entity = dict(re.findall(r'"([^"\n]+)" "([^"\n]*)"', block))
        model = entity.get('model', '')
        if model.startswith('*'):
            origins[int(model[1:])] = tuple(map(float, entity.get('origin', '0 0 0').split()))

    light_start, light_size = lumps[8]
    offsets = sorted({f[-1] for f in faces if f[-1] >= 0} | {light_size})
    end_offsets = dict(zip(offsets, offsets[1:]))
    use = defaultdict(list)
    for index, model in enumerate(models):
        world_origin = origins.get(index, (0, 0, 0))
        for f in faces[model[-2]:model[-2]+model[-1]]:
            plane, side, first, count, tex, style, *_, offset = f
            if offset < 0:
                continue
            plane_normal = planes[plane]
            direction = -1 if side else 1
            texture = texture_names[texinfo[tex][8]].upper()
            selected = False
            if style == 0 and texture in (b'CLASS_WALL', b'SCHOOL_CREAM'):
                corners = [vertices[edges[abs(e)][e < 0]] for e in surfedges[first:first+count]]
                x, y, z = [sum(v[axis] for v in corners) / count + world_origin[axis] for axis in range(3)]
                x, y = x / 40 - 28, y / 40 + 20
                # Only the exterior sides of the stair wing and gym wall.
                south_face = plane_normal[1] * direction < -.99
                selected = south_face and (
                    (abs(y - 4.5559) <= .08 and 31 <= x <= 55.6) or
                    (abs(y - 20.6377) <= .08 and 37.9 <= x <= 55.6)
                ) and 10 <= z <= 375
            use[offset].append(selected)

    changed_faces = raised_luxels = 0
    for offset, selection in use.items():
        if not all(selection):
            continue
        start, end = light_start+offset, light_start+end_offsets[offset]
        assert (end-start) % 3 == 0
        changed = False
        for i in range(start, end, 3):
            red, green, blue = data[i:i+3]
            luma = (red*54 + green*183 + blue*19) / 256
            if luma < 36:
                lift = round((36-luma)*.70)
                if lift:
                    data[i:i+3] = bytes((red+lift, green+lift, blue+lift))
                    raised_luxels += 1
                    changed = True
        changed_faces += len(selection) if changed else 0
    assert changed_faces > 0 and raised_luxels > 0
    temp = path.with_suffix('.bsp.facade')
    temp.write_bytes(data)
    temp.replace(path)
    return dict(changed_faces=changed_faces, raised_luxels=raised_luxels)


if __name__ == '__main__':
    print(json.dumps(fill_stair_facade(Path(sys.argv[1]))))
