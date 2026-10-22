"""Synthetic scene generator.

Draws simple corridor scenes with Pillow so the demo, the tests and the evaluation harness have
photos to work with and the repository needs no binary files. These are SYNTHETIC ILLUSTRATIONS, not
real photographs. For a real submission, replace them with photos you take yourself (see docs).
"""
import io
import random
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFilter

from . import config

SIZE = (640, 480)
KINDS = ['broken_light', 'garbage_overflow', 'water_leak', 'blocked_path']
SAMPLE_REPORTS = {
    'broken_light': {'text': 'Stair light is not working in Hostel B and it is very dark at night. stairs pe andhera hai.',
                     'location': 'Hostel B', 'detail': 'main staircase'},
    'garbage_overflow': {'text': 'Garbage bin is overflowing near the mess and the smell is bad. kachra bahar tak aa gaya hai.',
                         'location': 'Mess Hall', 'detail': 'back door'},
    'water_leak': {'text': 'Water pipe is leaking in the bathroom block, floor is wet and slippery. paani leak ho raha hai.',
                   'location': 'Hostel A', 'detail': 'bathroom block'},
    'blocked_path': {'text': 'Corridor is blocked by chairs and boxes, students cannot walk through.',
                     'location': 'Block C', 'detail': '2nd floor corridor'},
}


def _local_exif_string(dt_utc: datetime) -> str:
    local = dt_utc.replace(tzinfo=timezone.utc).astimezone(config.campus_tz())
    return local.strftime('%Y:%m:%d %H:%M:%S')


def _background(rng, variant):
    """variant 'A' = the reported place, 'B' = a visibly different corridor."""
    img = Image.new('RGB', SIZE, (200, 196, 188) if variant == 'A' else (120, 150, 140))
    d = ImageDraw.Draw(img)
    vx = rng.randint(250, 390) if variant == 'A' else rng.randint(120, 200)
    wall = (205, 210, 220) if variant == 'A' else (95, 125, 120)
    d.polygon([(0, 0), (vx - 90, 120), (vx - 90, 330), (0, SIZE[1])], fill=wall)
    d.polygon([(SIZE[0], 0), (vx + 90, 120), (vx + 90, 330), (SIZE[0], SIZE[1])], fill=wall)
    d.polygon([(0, SIZE[1]), (vx - 90, 330), (vx + 90, 330), (SIZE[0], SIZE[1])], fill=(150, 140, 125))
    d.rectangle([vx - 90, 120, vx + 90, 330], fill=(170, 175, 185))
    for i in range(rng.randint(2, 4)):
        x = rng.randint(30, 560)
        d.rectangle([x, 60 + i * 5, x + rng.randint(25, 60), 150 + rng.randint(0, 60)], fill=(90, 70, 50))
    return img, d, vx


def render_scene(kind: str, fixed: bool, seed: int = 0, variant: str = 'A') -> Image.Image:
    rng = random.Random(seed * 7919 + (1 if variant == 'B' else 0))
    img, d, vx = _background(rng, variant)
    if kind == 'broken_light':
        if fixed:
            img = Image.eval(img, lambda v: min(255, int(v * 1.25) + 18))
            d = ImageDraw.Draw(img)
            glow = Image.new('RGB', SIZE, (0, 0, 0))
            gd = ImageDraw.Draw(glow)
            gd.ellipse([vx - 140, 20, vx + 140, 220], fill=(255, 240, 170))
            glow = glow.filter(ImageFilter.GaussianBlur(40))
            img = Image.blend(img, Image.composite(glow, img, glow.convert('L')), 0.55)
            d = ImageDraw.Draw(img)
            d.rectangle([vx - 60, 40, vx + 60, 62], fill=(255, 250, 215))
        else:
            img = Image.eval(img, lambda v: int(v * 0.38))
            d = ImageDraw.Draw(img)
            d.rectangle([vx - 60, 40, vx + 60, 62], fill=(70, 70, 70))
    elif kind == 'garbage_overflow':
        d.rectangle([vx - 50, 300, vx + 50, 400], fill=(40, 90, 60))
        if not fixed:
            for _ in range(90):
                x, y = vx + rng.randint(-140, 140), rng.randint(300, 440)
                c = tuple(rng.randint(40, 255) for _ in range(3))
                d.polygon([(x, y), (x + rng.randint(6, 18), y + rng.randint(-6, 6)), (x + rng.randint(2, 12), y + rng.randint(8, 18))], fill=c)
    elif kind == 'water_leak':
        d.rectangle([vx - 6, 130, vx + 6, 330], fill=(120, 125, 135))
        if not fixed:
            d.ellipse([vx - 150, 360, vx + 150, 450], fill=(40, 90, 200))
            d.ellipse([vx - 90, 375, vx + 90, 435], fill=(70, 130, 235))
    elif kind == 'blocked_path':
        if not fixed:
            for _ in range(7):
                x, y = vx + rng.randint(-120, 100), rng.randint(300, 420)
                d.rectangle([x, y, x + rng.randint(40, 70), y + rng.randint(40, 60)], fill=tuple(rng.randint(60, 200) for _ in range(3)))
                d.line([x, y, x + 30, y + 50], fill=(30, 30, 30), width=3)
    return img


def scene_jpeg(kind: str, fixed: bool, seed: int = 0, variant: str = 'A', taken_utc: datetime | None = None) -> bytes:
    """JPEG bytes of a synthetic scene. taken_utc=None writes NO EXIF (like a screenshot)."""
    img = render_scene(kind, fixed, seed, variant)
    buf = io.BytesIO()
    if taken_utc is None:
        img.save(buf, 'JPEG', quality=88)
    else:
        exif = Image.Exif()
        exif[0x8769] = {36867: _local_exif_string(taken_utc), 36868: _local_exif_string(taken_utc)}
        img.save(buf, 'JPEG', quality=88, exif=exif)
    return buf.getvalue()


def sample_catalog():
    """Names the UI can request from GET /api/samples/{name}."""
    out = []
    for k in KINDS:
        rep = SAMPLE_REPORTS[k]
        out.append({'name': k + '__before', 'kind': k, 'role': 'report', 'label': 'Reported problem photo', **rep})
        out.append({'name': k + '__after_genuine', 'kind': k, 'role': 'evidence', 'label': 'Genuine repair photo'})
        out.append({'name': k + '__after_reused', 'kind': k, 'role': 'evidence', 'label': 'Reused original photo'})
        out.append({'name': k + '__after_other_place', 'kind': k, 'role': 'evidence', 'label': 'Photo of a different place'})
        out.append({'name': k + '__after_old', 'kind': k, 'role': 'evidence', 'label': 'Old photo (taken before the report)'})
        out.append({'name': k + '__after_screenshot', 'kind': k, 'role': 'evidence', 'label': 'Screenshot (no capture time)'})
    return out


def sample_image(name: str, seed: int) -> bytes:
    """Build one named sample. `seed` keeps the before/after of one demo run consistent."""
    kind, _, role = name.partition('__')
    if kind not in KINDS:
        raise KeyError(name)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if role == 'before':
        return scene_jpeg(kind, False, seed, 'A', now - timedelta(hours=2))
    if role == 'after_genuine':
        return scene_jpeg(kind, True, seed, 'A', now - timedelta(minutes=1))
    if role == 'after_reused':
        return scene_jpeg(kind, False, seed, 'A', now - timedelta(hours=2))   # byte-identical to 'before'
    if role == 'after_other_place':
        return scene_jpeg(kind, True, seed + 500, 'B', now - timedelta(minutes=1))
    if role == 'after_old':
        return scene_jpeg(kind, True, seed, 'A', now - timedelta(days=3))
    if role == 'after_screenshot':
        return scene_jpeg(kind, True, seed, 'A', None)
    raise KeyError(name)
