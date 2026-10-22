"""DEMO MODE stand-ins.

These are small deterministic rules used ONLY when no Nebius API key / model IDs are configured.
They let you run and test the whole workflow offline and for free. They are NOT AI and NOT NVIDIA
model output: every result they produce is tagged source='demo' and the UI says so.
"""
import io
import re

import imagehash
from PIL import Image, ImageFilter, ImageStat

from . import config

KEYWORDS = {
    'broken_light': ['light', 'lights', 'lamp', 'bulb', 'tubelight', 'tube light', 'bijli', 'andhera', 'dark', 'flicker', 'flickering', 'led'],
    'garbage_overflow': ['garbage', 'trash', 'waste', 'dustbin', 'bin', 'kachra', 'kooda', 'dump', 'overflowing', 'overflow'],
    'water_leak': ['leak', 'leaking', 'leakage', 'pipe', 'tap', 'nal', 'paani', 'pani', 'drip', 'dripping', 'seepage', 'puddle', 'water', 'flooded'],
    'blocked_path': ['blocked', 'blocking', 'obstructed', 'obstruction', 'rasta', 'passage', 'pathway', 'corridor blocked', 'cannot walk', 'boxes', 'parked'],
    'wifi_down': ['wifi', 'wi-fi', 'internet', 'network', 'router', 'lan', 'broadband', 'signal'],
    'broken_furniture': ['bench', 'desk', 'table', 'cupboard', 'almirah', 'furniture', 'cot', 'bed', 'chair', 'stool'],
    'pest': ['pest', 'cockroach', 'cockroaches', 'rat', 'rats', 'mice', 'mosquito', 'mosquitoes', 'insect', 'insects', 'ant', 'ants', 'termite', 'bedbug', 'keeda', 'chuha', 'machhar', 'snake'],
}
HINGLISH_MARKERS = {'hai', 'nahi', 'nhi', 'kharab', 'pe', 'mein', 'me', 'ka', 'ki', 'ko', 'toota', 'bahut', 'paani', 'bijli', 'andhera', 'kachra',
                    'aa', 'gaya', 'raha', 'rahi', 'hua', 'band', 'chal', 'karo', 'abhi', 'kuch'}
INJECTION_PATTERNS = [
    r'ignore (all |any |your |the )?(previous |prior |above )?(instructions|rules|prompt)',
    r'disregard (all |any |your |the )?(previous |prior )?(instructions|rules)',
    r'(mark|set|close|change)\b.{0,25}\b(closed|resolved|urgent|verified)',
    r'system prompt', r'you are now', r'override', r'act as',
]


def words(text):
    return re.findall(r'[a-z0-9\-]+', (text or '').lower())


def detect_injection(text: str) -> bool:
    t = (text or '').lower()
    return any(re.search(p, t) for p in INJECTION_PATTERNS)


def detect_language(text: str) -> str:
    if re.search(r'[\u0900-\u097F]', text or ''):
        return 'hi'
    ws = set(words(text))
    return 'hinglish' if len(ws & HINGLISH_MARKERS) >= 2 else 'en'


def match_building(text: str):
    """Find a campus location name mentioned in free text."""
    t = (text or '').lower()
    for name in config.DOMAIN['locations']:
        if name.lower() in t:
            return name
    return None


def demo_intake(text: str, building: str | None, category: str | None = None):
    """Keyword rules -> dict shaped like the live Intake model."""
    ws = set(words(text))
    low = (text or '').lower()
    scores = {}
    for issue, kws in KEYWORDS.items():
        scores[issue] = sum(1 for k in kws if (k in ws) or (' ' in k and k in low))
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    best, best_n = ranked[0]
    second_n = ranked[1][1]
    if best_n == 0:
        issue, conf = 'other', 0.30
    else:
        issue = best
        conf = min(0.95, 0.60 + 0.15 * best_n) if best_n > second_n else 0.50
    if category in config.ISSUE_TYPES and category != 'other':     # the student's own category choice is a hint, not an order
        if best_n == 0:
            issue, conf = category, 0.80
        elif category == best:
            conf = min(0.95, conf + 0.10)
    urgent = any(k in low for k in config.DOMAIN['urgent_keywords'])
    if issue == 'broken_light' and any(k in low for k in ('stair', 'night', 'corridor', 'andhera')):
        urgent = True
    building = building or match_building(text)
    missing = [] if building else ['location']
    summary = re.sub(r'\s+', ' ', (text or '').strip())[:160]
    return {'issue_type': issue, 'urgency': 'high' if urgent else 'medium', 'location_text': building,
            'summary': summary, 'safety_hazard': urgent, 'missing_info': missing,
            'language': detect_language(text), 'confidence': conf}


# ---------- photo heuristics (only for the synthetic demo scenes; not computer vision) ----------

def _stats(jpeg: bytes):
    im = Image.open(io.BytesIO(jpeg)).convert('RGB')
    im.thumbnail((256, 256))
    gray = im.convert('L')
    brightness = ImageStat.Stat(gray).mean[0]
    edges = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0]
    px = list(im.get_flattened_data()) if hasattr(im, 'get_flattened_data') else list(im.getdata())
    blue = sum(1 for r, g, b in px if b > 140 and b > r + 40 and b > g + 10) / len(px)
    return brightness, edges, blue


def demo_visual_check(issue_type: str, before_jpeg: bytes, after_jpeg: bytes):
    """Returns (answer, confidence, evidence). Answers the YAML question for this issue type."""
    b0, e0, w0 = _stats(before_jpeg)
    b1, e1, w1 = _stats(after_jpeg)
    if issue_type == 'broken_light':       # question: is the light lit?  yes == brighter
        if b1 > b0 * 1.15:
            return 'yes', 0.80, 'demo heuristic: the scene is much brighter than the original photo'
        if b1 < b0 * 1.03:
            return 'no', 0.78, 'demo heuristic: the scene is not brighter than the original photo'
    elif issue_type in ('garbage_overflow', 'blocked_path'):    # question: is it clear?  yes == less clutter
        if e1 < e0 * 0.80:
            return 'yes', 0.80, 'demo heuristic: visibly less clutter than the original photo'
        if e1 > e0 * 0.95:
            return 'no', 0.76, 'demo heuristic: clutter level is unchanged from the original photo'
    elif issue_type == 'water_leak':       # question: is water visible?  yes == puddle present
        if w1 < w0 * 0.4:
            return 'no', 0.80, 'demo heuristic: the wet/blue area has disappeared'
        if w1 > w0 * 0.8:
            return 'yes', 0.76, 'demo heuristic: the wet/blue area is still present'
    return 'unsure', 0.40, 'demo heuristic: change is too small to judge'


def demo_same_place(before_jpeg: bytes, after_jpeg: bytes):
    a = imagehash.phash(Image.open(io.BytesIO(before_jpeg)))
    b = imagehash.phash(Image.open(io.BytesIO(after_jpeg)))
    d = a - b
    if d <= 16:
        return 'same', 0.80, 'demo heuristic: overall layout matches (hash distance ' + str(d) + ')'
    if d >= 20:
        return 'different', 0.80, 'demo heuristic: overall layout differs (hash distance ' + str(d) + ')'
    return 'unsure', 0.40, 'demo heuristic: layout similarity is borderline (hash distance ' + str(d) + ')'
