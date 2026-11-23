"""Prepare web-sized copies; keep original publication images unchanged.

Maintenance command: python3 scripts/optimize_images.py (requires Pillow).
The generated files are committed, so building Pages does not need Pillow.
"""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]


def main():
    covers = json.loads((ROOT / 'config/covers.json').read_text())
    sources = {r['src'] for r in covers.values() if r.get('src')}
    for path in (ROOT / 'content/issues').glob('*.json'):
        for record in json.loads(path.read_text())['records']:
            sources.update(im['src'] for im in record.get('images', []))
    manifest = {}
    for source in sorted(sources):
        path = ROOT / source
        if path.suffix.lower() not in ('.png', '.jpg', '.jpeg'):
            continue
        with Image.open(path) as original:
            image = ImageOps.exif_transpose(original).convert('RGB')
            variants = []
            for width in sorted({min(640, image.width), min(1100, image.width)}):
                resized = image.resize((width, round(image.height * width / image.width)), Image.Resampling.LANCZOS)
                output = path.with_name(f'{path.stem}-{width}w.webp')
                resized.save(output, 'WEBP', quality=84, method=6)
                variants.append({'src': output.relative_to(ROOT).as_posix(), 'width': width})
            manifest[source] = {'src': variants[-1]['src'], 'width': image.width, 'height': image.height, 'variants': variants}
    for name in ('cream-paper', 'mustard-paper'):
        source = ROOT / f'static/covers/{name}.png'
        with Image.open(source) as image:
            image.save(source.with_suffix('.webp'), 'WEBP', quality=84, method=6)
    target = ROOT / 'config/image-assets.json'
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(f'Prepared {len(manifest)} responsive images and 2 paper textures')


if __name__ == '__main__':
    main()
