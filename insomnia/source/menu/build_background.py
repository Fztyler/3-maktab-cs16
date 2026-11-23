"""Convert the menu image into the existing GoldSrc background tile format."""
from argparse import ArgumentParser
from pathlib import Path

from PIL import Image, ImageOps


def build_background(source, resources):
    tile_size = 256
    width, height = 1024, 768
    with Image.open(source) as image:
        background = ImageOps.exif_transpose(image).convert('RGB').resize(
            (width, height), Image.Resampling.LANCZOS
        )

    tiles = resources / 'background'
    tiles.mkdir(parents=True, exist_ok=True)
    layout = [f'resolution\t{width}\t{height}', '']
    rebuilt = Image.new('RGB', background.size)
    for row, top in enumerate(range(0, height, tile_size)):
        for col, left in enumerate(range(0, width, tile_size)):
            name = f'insomnia_menu_{row}_{col}.tga'
            path = tiles / name
            background.crop((left, top, left + tile_size, top + tile_size)).save(path)
            layout.append(f'resource/background/{name}\tscaled\t{left}\t{top}')
            with Image.open(path) as tile:
                rebuilt.paste(tile, (left, top))

    if rebuilt.tobytes() != background.tobytes():
        raise ValueError('Tiles do not match the menu image')
    (resources / 'BackgroundLayout.txt').write_text('\n'.join(layout) + '\n', encoding='ascii')


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('resource_directory', type=Path)
    args = parser.parse_args()
    build_background(args.image, args.resource_directory)
