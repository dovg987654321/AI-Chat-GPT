# -*- coding: utf-8 -*-
"""
Akte 41 — сборка серии в стиле «Тёмное кино» из 3D-планов (Blender/Cycles).
Тайминг и звук — как в engine/render_ep.py (по озвучке). Кадры: план из 3D + медленная камера,
снег, дым, свет в окне, зерно, кашетирование 2.39:1, надписи.

python3 ep3d.py EP_DIR PLATES_DIR OUT_DIR [--from S] [--to S] [--subs SRT] [--procs 4]
"""
import sys, os, json, math, subprocess, re, glob
import multiprocessing as mp
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
EP, PLATES, OUT = (os.path.abspath(x) for x in sys.argv[1:4])
def opt(n, d):
    return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d
T_FROM, T_TO = float(opt("--from", "0")), opt("--to", None)
SUBS = opt("--subs", None)
NPROC = int(opt("--procs", "4"))
os.makedirs(OUT, exist_ok=True)

# тайминг, голос и музыка — из старого движка (тот же звук, те же таймкоды)
_argv = sys.argv; sys.argv = [_argv[0], EP, OUT]
sys.path.insert(0, os.path.join(HERE, "..", "engine"))
import render_ep as RE
sys.argv = _argv

W, H, FPS = 1920, 1080, 24
BAR = int(round((H - W / 2.0) / 2))           # 60 px — узкое кашетирование 2:1 (было 2.39:1, 138 px)
PIC_T, PIC_B = BAR, H - BAR
F_MONO = "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf"
F_MONO_B = "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf"
F_SANS = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"
F_SANS_B = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
F_X = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
F_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
RED = (214, 40, 46)
PAPER = (236, 231, 220)

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def seg(t, a, b): return clamp((t - a) / (b - a)) if b > a else float(t >= a)
def ease(x): x = clamp(x); return x * x * (3 - 2 * x)
def lerp(a, b, t): return a + (b - a) * t
_fonts = {}
def font(p, s):
    k = (p, int(s))
    if k not in _fonts: _fonts[k] = ImageFont.truetype(p, int(s))
    return _fonts[k]

# ================================================================ планы
_plates = {}
def plate(name):
    """Возвращает (PIL-картинка с предрасчитанным свечением, meta)."""
    if name not in _plates:
        im = Image.open(os.path.join(PLATES, name + ".png")).convert("RGB")
        a = np.asarray(im, np.float32) / 255
        lum = a.mean(axis=2)
        warm = np.clip((a[..., 0] - a[..., 2]) * 3 + 0.15, 0, 1)
        hi = (np.clip((lum - 0.72) / 0.28, 0, 1) * warm)[..., None] * a
        sm = Image.fromarray((hi * 255).astype(np.uint8)).resize((im.width // 4, im.height // 4), Image.BILINEAR)
        g1 = np.asarray(sm.filter(ImageFilter.GaussianBlur(5)), np.float32) / 255
        g2 = np.asarray(sm.filter(ImageFilter.GaussianBlur(16)), np.float32) / 255
        g = Image.fromarray((np.clip(g1 * 0.7 + g2 * 0.9, 0, 1) * 255).astype(np.uint8)).resize(im.size, Image.BILINEAR)
        a = a + np.asarray(g, np.float32) / 255 * 0.8
        # грейд: холодные тени, тёплые света
        a = a * np.array([0.97, 1.0, 1.05]) + np.array([-0.004, 0.0, 0.010])
        im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
        mp_ = os.path.join(PLATES, name + ".json")
        meta = json.load(open(mp_)) if os.path.exists(mp_) else {}
        _plates[name] = (im, meta)
    return _plates[name]

class View:
    """Камера по плану: центр (cx, cy) в долях плана и зум (1 = кадр 2.39 по ширине плана)."""
    def __init__(self, name, cx, cy, z):
        self.im, self.meta = plate(name)
        pw, ph = self.im.size
        self.cw = pw / z; self.ch = self.cw * H / W
        self.x0 = cx * pw - self.cw / 2; self.y0 = cy * ph - self.ch / 2
        self.x0 = min(max(self.x0, 0), pw - self.cw); self.y0 = min(max(self.y0, 0), ph - self.ch)
        self.pw, self.ph = pw, ph
    def render(self):
        return self.im.transform((W, H), Image.EXTENT, (self.x0, self.y0, self.x0 + self.cw, self.y0 + self.ch),
                                 Image.BILINEAR)
    def to_screen(self, fx, fy):
        return ((fx * self.pw - self.x0) / self.cw * W, (fy * self.ph - self.y0) / self.ch * H)

def kb(name, t, T, a=(0.5, 0.5, 1.0), b=(0.5, 0.5, 1.08), k=None):
    """медленная камера между двумя позициями"""
    u = ease(t / max(T, 0.1)) if k is None else k
    return View(name, lerp(a[0], b[0], u), lerp(a[1], b[1], u), lerp(a[2], b[2], u))

# ================================================================ атмосфера
rng = np.random.default_rng(41)
def _flake_tile(n, rmin, rmax, blur, seed):
    r = np.random.default_rng(seed)
    im = Image.new("L", (W, 2 * H), 0); d = ImageDraw.Draw(im)
    for _ in range(n):
        x, y, s = r.uniform(0, W), r.uniform(0, 2 * H), r.uniform(rmin, rmax)
        d.ellipse([x - s, y - s * 1.15, x + s, y + s * 1.15], fill=int(r.uniform(150, 235)))
    if blur: im = im.filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(im, np.float32) / 255
SNOW = None
def snow(t, amt=1.0):
    global SNOW
    if SNOW is None:
        SNOW = [(_flake_tile(420, 0.9, 1.7, 0, 1), 46, 9), (_flake_tile(110, 1.8, 2.8, 0.9, 2), 105, 22),
                (_flake_tile(9, 4.5, 6.5, 3.5, 3), 230, 40)]
    out = np.zeros((H, W), np.float32)
    for tile, v, sway in SNOW:
        oy = int(v * t) % (2 * H); ox = int(sway * math.sin(t * 0.5) + 20 * t) % W
        a = np.roll(np.roll(tile, oy, axis=0), ox, axis=1)[:H]
        out = np.maximum(out, a)
    return out * amt

GRAIN = None
def grain(fno):
    global GRAIN
    if GRAIN is None:
        GRAIN = [rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32) for _ in range(6)]
    g = GRAIN[fno % 6]
    return np.repeat(np.repeat(g, 2, 0), 2, 1)[..., None]

VIG = None
def vignette():
    global VIG
    if VIG is None:
        yy, xx = np.mgrid[0:H, 0:W]
        r = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
        VIG = (1 - 0.5 * np.clip(r - 0.4, 0, 1) ** 1.5)[..., None].astype(np.float32)
    return VIG

_smoke = {}
def smoke_sprite(t):
    """Дым: маска 360x700, низ по центру = устье трубы."""
    k = int(t * 12) % 240
    if k not in _smoke:
        im = Image.new("L", (360, 700), 0); d = ImageDraw.Draw(im)
        tt = k / 12
        for i in range(60):
            age = (i / 60 + tt * 0.08) % 1.0
            r = 6 + 60 * age
            x = 180 + 60 * age + 16 * math.sin(age * 8 + tt * 0.6)
            y = 690 - 600 * age
            d.ellipse([x - r, y - r, x + r, y + r], fill=int(90 * (1 - age) ** 1.4 * min(1, age * 10)))
        _smoke[k] = im.filter(ImageFilter.GaussianBlur(10))
    return _smoke[k]

def add_smoke(img, v, t, scale=1.0, alpha=0.5):
    if "chimney" not in v.meta: return img
    x, y = v.to_screen(*v.meta["chimney"])
    sp = smoke_sprite(t)
    s = scale * v.pw / v.cw * 0.6
    sp = sp.resize((max(1, int(360 * s)), max(1, int(700 * s))), Image.BILINEAR)
    col = Image.new("RGB", sp.size, (120, 130, 155))
    m = sp.point(lambda q: int(q * alpha))
    img.paste(col, (int(x - sp.width / 2), int(y - sp.height + 4 * s)), m)
    return img

def window_figure(img, v, u, dim=0.0):
    """Тень человека проходит за светящимся окном. u — 0..1 проход слева направо."""
    if "window" not in v.meta or not (0 < u < 1): return img
    q = [v.to_screen(*p) for p in v.meta["window"]]
    x0, x1 = min(p[0] for p in q), max(p[0] for p in q)
    y0, y1 = min(p[1] for p in q), max(p[1] for p in q)
    wh = y1 - y0; ww = x1 - x0
    cx = x0 - ww * 0.35 + (ww * 1.7) * ease(u)
    mask = Image.new("L", img.size, 0); d = ImageDraw.Draw(mask)
    hr = wh * 0.16; hy = y0 + wh * 0.42
    d.ellipse([cx - hr * 0.85, hy - hr, cx + hr * 0.85, hy + hr], fill=255)
    d.rectangle([cx - hr * 0.4, hy, cx + hr * 0.4, hy + hr * 1.3], fill=255)
    d.rounded_rectangle([cx - hr * 2.0, hy + hr * 1.1, cx + hr * 2.0, y1 + wh], radius=hr * 1.2, fill=255)
    clip = Image.new("L", img.size, 0); ImageDraw.Draw(clip).polygon(q, fill=255)
    from PIL import ImageChops
    m = ImageChops.multiply(mask, clip).filter(ImageFilter.GaussianBlur(max(1, wh * 0.025)))
    img.paste((26, 14, 8), (0, 0), m.point(lambda p: int(p * 0.9)))
    return img

# ================================================================ надписи
def text_w(txt, f, sp=0):
    return sum(f.getlength(ch) for ch in txt) + sp * max(0, len(txt) - 1)

def draw_spaced(d, xy, txt, f, fill, sp=0, anchor="ls"):
    x, y = xy
    if anchor[0] == "m": x -= text_w(txt, f, sp) / 2
    elif anchor[0] == "r": x -= text_w(txt, f, sp)
    for ch in txt:
        d.text((x, y), ch, font=f, fill=fill, anchor="l" + anchor[1]); x += f.getlength(ch) + sp

def caption(img, lines, t, at, x=150, y=None, size=34, col=(236, 232, 224), cps=26, hold=None):
    """Машинописная подпись: печатается по буквам, с курсором."""
    if t < at: return img
    if hold is not None and t > at + hold:
        a = 1 - seg(t, at + hold, at + hold + 0.5)
        if a <= 0: return img
    else:
        a = 1.0
    d = ImageDraw.Draw(img, "RGBA"); f = font(F_MONO, size)
    y = PIC_B - 60 - (len(lines) - 1) * size * 1.4 if y is None else y
    n = int((t - at) * cps)
    for i, ln in enumerate(lines):
        k = clamp(n / max(1, len(ln))); show = ln[:max(0, min(len(ln), n))]
        n -= len(ln) + 4
        c = col if not isinstance(col, list) else col[i]
        d.text((x, y + i * size * 1.4), show, font=f, fill=(*c, int(255 * a)), anchor="ls")
        if 0 < k < 1 and int(t * 4) % 2 == 0:
            cx = x + f.getlength(show) + 3
            d.rectangle([cx, y + i * size * 1.4 - size * 0.8, cx + size * 0.5, y + i * size * 1.4 + 4], fill=(*c, int(200 * a)))
    return img

def tag(img, txt, t, at, x=150, y=None, size=26, col=RED, align="l", hold=None):
    """Красная плашка-метка (капс, разрядка), всплывает."""
    a = seg(t, at, at + 0.35)
    if hold is not None: a *= 1 - seg(t, at + hold, at + hold + 0.4)
    if a <= 0: return img
    y = PIC_T + 70 if y is None else y
    d = ImageDraw.Draw(img, "RGBA"); f = font(F_SANS_B, size); sp = size * 0.18
    w = text_w(txt, f, sp)
    x0 = x - (w if align == "r" else (w / 2 if align == "m" else 0))
    dy = (1 - ease(a)) * 10
    d.rectangle([x0 - 16, y - size - 10 + dy, x0 - 10, y + 10 + dy], fill=(*col, int(255 * a)))
    draw_spaced(d, (x0, y + dy), txt, f, (*PAPER, int(255 * a)), sp)
    return img

def stamp(img, txt, t, at, cx, cy, size=64, rot=-6, col=RED):
    """Штамп: рамка + капс, с ударом (скейл 1.3→1) и неровной краской."""
    a = seg(t, at, at + 0.18)
    if a <= 0: return img
    f = font(F_X, size); sp = size * 0.08
    w = int(text_w(txt, f, sp) + size * 0.9); h = int(size * 1.6)
    st = Image.new("L", (w, h), 0); d = ImageDraw.Draw(st)
    lw = max(3, size // 12)
    d.rectangle([lw, lw, w - lw - 1, h - lw - 1], outline=255, width=lw)
    draw_spaced(d, (w / 2, h / 2 + size * 0.36), txt, f, 255, sp, anchor="ms")
    noise = np.asarray(Image.effect_noise((w, h), 90).filter(ImageFilter.GaussianBlur(1.2)), np.float32)
    m = np.asarray(st, np.float32) * np.clip((noise - 40) / 120, 0.35, 1)
    st = Image.fromarray(m.astype(np.uint8))
    sc = 1.3 - 0.3 * ease(a)
    st = st.resize((int(w * sc), int(h * sc)), Image.BILINEAR).rotate(rot, expand=True, resample=Image.BILINEAR)
    img.paste(Image.new("RGB", st.size, col), (int(cx - st.width / 2), int(cy - st.height / 2)),
              st.point(lambda p: int(p * 0.92 * a)))
    return img

def big_title(img, txt, t, at, cy, size=150, sp=None, col=PAPER):
    a = seg(t, at, at + 0.9)
    if a <= 0: return img
    d = ImageDraw.Draw(img, "RGBA"); f = font(F_X, size)
    sp = size * (0.35 - 0.2 * ease(a)) if sp is None else sp
    draw_spaced(d, (W / 2, cy), txt, f, (*col, int(255 * ease(a))), sp, anchor="ms")
    return img

# ================================================================ субтитры (только для превью)
def load_srt(p):
    cues = []
    for blk in open(p, encoding="utf-8").read().strip().split("\n\n"):
        ls = blk.strip().split("\n")
        if len(ls) < 3: continue
        def s2t(s):
            h_, m_, r = s.split(":"); s_, ms = r.split(","); return int(h_) * 3600 + int(m_) * 60 + int(s_) + int(ms) / 1000
        a, b = ls[1].split(" --> ")
        cues.append((s2t(a), s2t(b), " ".join(ls[2:])))
    return cues
CUES = load_srt(SUBS) if SUBS else []
def subtitles(img, tt):
    for a, b, txt in CUES:
        if a <= tt < b:
            d = ImageDraw.Draw(img); f = font(F_SANS, 34)
            words = txt.split(); lines = [""]
            for w_ in words:
                if f.getlength(lines[-1] + " " + w_) > 1500: lines.append(w_)
                else: lines[-1] = (lines[-1] + " " + w_).strip()
            y = PIC_B + 52 if len(lines) == 1 else PIC_B + 36
            for i, ln in enumerate(lines):
                d.text((W / 2, y + i * 44), ln, font=f, fill=(240, 238, 232), anchor="mm")
            break
    return img

# ================================================================ сцены
# каждая сцена: fn(t, T, sid, tt) -> (PIL.Image кадр, dict опций атмосферы)
SC = {}
def scene(name):
    def deco(fn): SC[name] = fn; return fn
    return deco

MOVE_DIR = os.path.join(PLATES, "move_tracks")
_move = None
@scene("tracks")
def s_tracks(t, T, sid, tt):
    global _move
    if sid == "s01" and os.path.isdir(MOVE_DIR):
        if _move is None: _move = sorted(glob.glob(os.path.join(MOVE_DIR, "*.png")))
        i = min(len(_move) - 1, int(t / T * len(_move)))
        im = Image.open(_move[i]).convert("RGB")
        if im.size != (W, H): im = im.resize((W, H), Image.BICUBIC)
        img = im
        img = tag(img, "OBERBAYERN · MÄRZ 1922", t, 1.2, hold=6.0)
        return img, dict(snow=0.8)
    v = kb("tracks_low", t, T, (0.5, 0.55, 1.0), (0.5, 0.5, 1.12))
    img = v.render()
    img = caption(img, ["vom Wald zum Hof.", "keine zurück."], t, 0.8, cps=20)
    img = tag(img, "VOR DER TAT", t, 0.4, hold=T - 1)
    return img, dict(snow=0.8, view=v)

@scene("tracks_back")
def s_tracks_back(t, T, sid, tt):
    v = kb("tracks_back", t, T, (0.5, 0.5, 1.0), (0.5, 0.48, 1.12))
    img = v.render()
    img = caption(img, ["Spuren zurück: keine."], t, T * 0.58, col=RED, size=40, cps=22)
    return img, dict(snow=0.8, view=v)

@scene("farm_night")
def s_farm_night(t, T, sid, tt):
    cut = T * 0.42
    if t < cut:
        v = kb("farm_wide", t, cut + 2, (0.5, 0.52, 1.0), (0.46, 0.52, 1.14))
        img = v.render()
        img = add_smoke(img, v, tt)
        img = tag(img, "6 TOTE", t, 1.4, hold=cut - 2.2)
    else:
        u = t - cut
        v = kb("farm_window", u, T - cut, (0.5, 0.5, 1.0), (0.5, 0.48, 1.18))
        img = v.render()
        img = window_figure(img, v, seg(u, 1.0, 5.5))
        img = caption(img, ["Jemand bleibt dort.", "Tagelang."], u, 2.2, cps=18)
    return img, dict(snow=0.7)

@scene("title")
def s_title(t, T, sid, tt):
    v = kb("farm_far", t, T, (0.5, 0.5, 1.0), (0.5, 0.5, 1.1))
    img = v.render()
    img = Image.eval(img, lambda p: int(p * 0.6))
    img = add_smoke(img, v, tt, 1.0, 0.25)
    img = stamp(img, "AKTE 41", t, 0.3, W / 2, 380, 54, -4)
    img = big_title(img, "HINTERKAIFECK", t, 0.9, 590, 140)
    img = caption(img, ["1922 · sechs Tote · ein Name, der nie genannt wird"], t, 2.2, x=W / 2 - 520, y=690, size=32)
    k = seg(t, T * 0.62, T * 0.66)
    if k > 0:
        d = ImageDraw.Draw(img, "RGBA")
        for i, (s_, c) in enumerate([("AKTEN", PAPER), ("GERÜCHTE", PAPER), ("VERDÄCHTIGE", RED)]):
            a = seg(t, T * 0.62 + i * 0.9, T * 0.62 + i * 0.9 + 0.4)
            if a > 0:
                draw_spaced(d, (W / 2 + (i - 1) * 420, 830), s_, font(F_SANS_B, 34), (*c, int(255 * a)), 6, anchor="ms")
    return img, dict(snow=0.5)

# ---------------------------------------------------------------- помощники для остальных сцен
def path(name, t, keys):
    """keys: [(t, cx, cy, z)] — камера едет между ключами с плавностью; cx/cy могут быть именем хот-спота"""
    im, meta = plate(name)
    def res(k):
        tk, cx, cy, z = k
        if isinstance(cx, str):
            hx, hy = meta.get(cx, [0.5, 0.5]); return tk, hx + (cy or 0), hy, z
        return k
    K = [res(k) for k in keys]
    if t <= K[0][0]: _, cx, cy, z = K[0]
    elif t >= K[-1][0]: _, cx, cy, z = K[-1]
    else:
        for a, b in zip(K, K[1:]):
            if a[0] <= t <= b[0]:
                u = ease((t - a[0]) / (b[0] - a[0]))
                cx, cy, z = lerp(a[1], b[1], u), lerp(a[2], b[2], u), lerp(a[3], b[3], u); break
    return View(name, cx, cy, z)

def darken(img, k):
    return Image.eval(img, lambda p: int(p * k))

def xfade(a, b, k):
    return Image.blend(a, b, clamp(k)) if k > 0 else a

def notes(img, lines, t, at, x=1080, y=PIC_T + 120, size=32, red_last=None):
    """тёмная панель с машинописными заметками справа"""
    a = seg(t, at - 0.4, at)
    if a <= 0: return img
    d = ImageDraw.Draw(img, "RGBA")
    h_ = int(len(lines) * size * 1.5 + 60)
    d.rectangle([x - 40, y - 50, W - 90, y + h_ - 30], fill=(8, 10, 14, int(200 * a)))
    d.rectangle([x - 40, y - 50, x - 34, y + h_ - 30], fill=(*RED, int(255 * a)))
    cols = [PAPER] * len(lines)
    cols[0] = RED
    return caption(img, lines, t, at, x=x, y=y, size=size, col=cols, cps=34)

@scene("map")
def s_map(t, T, sid, tt):
    v = path("desk_map", t, [(0, 0.5, 0.5, 1.0), (T * 0.45, "map_pin", 0.0, 1.5), (T, "map_pin", 0.0, 2.2)])
    img = v.render()
    img = tag(img, "EINÖDHOF BEI SCHROBENHAUSEN", t, 1.0, hold=T * 0.5)
    img = caption(img, ["Gröbern: ca. 1 km entfernt.", "Dazwischen: Wald."], t, T * 0.6, cps=24)
    return img, {}

FAM_T = {"s06": [(0, 0.5, 0.48, 1.0), (2.2, "fam0", 0.02, 1.9), (5.8, "fam1", 0.02, 1.9), (9.0, "fam2", 0.02, 1.9),
                 (13.5, "fam3", 0.02, 1.9), (21.5, "fam3", 0.02, 2.1)],
         "s07": [(0, "fam3", 0.0, 1.6), (1.5, "fam4", 0.02, 1.9), (4.5, "fam5", 0.02, 1.9), (7.5, "fam6", 0.02, 1.9),
                 (11.2, "fam6", 0.02, 2.05)]}
@scene("family")
def s_family(t, T, sid, tt):
    v = path("desk_family", t, FAM_T["s06"]); img = v.render()
    img = caption(img, ["Karl Gabriel, Viktorias Mann:", "gefallen 1914 – laut Papieren."], t, 14.5, cps=24)
    return img, {}

@scene("family_kids")
def s_family_kids(t, T, sid, tt):
    v = path("desk_family", t, FAM_T["s07"]); img = v.render()
    img = tag(img, "MAGD: KEINE", t, 8.0)
    return img, {}

@scene("maid_leaves")
def s_maid_leaves(t, T, sid, tt):
    v = kb("attic_empty", t, T, (0.5, 0.5, 1.0), (0.5, 0.47, 1.25)); img = v.render()
    img = tag(img, "HERBST 1921", t, 0.6, hold=T * 0.5)
    img = caption(img, ["Aussage der letzten Magd:", "Schritte auf dem Dachboden."], t, T * 0.45, cps=22)
    return img, {}

@scene("family_secret")
def s_family_secret(t, T, sid, tt):
    cut = T * 0.22
    if t < cut:
        v = kb("farm_far", t, cut, (0.5, 0.5, 1.05), (0.52, 0.5, 1.15)); img = v.render()
        img = caption(img, ["Im Dorf: nicht beliebt.", "„geizig und hart“"], t, 1.0, cps=22)
        return img, dict(snow=0.4)
    u = t - cut
    v = path("desk_court", u, [(0, "court", 0.0, 1.15), (T - cut, "court_bottom", 0.0, 1.6)]); img = v.render()
    img = stamp(img, "VERURTEILT", u, (T - cut) * 0.42, W * 0.62, H * 0.6, 70, -8)
    img = caption(img, ["Wer ist der Vater von Josef?"], u, (T - cut) * 0.8, col=RED, size=38, cps=24)
    return img, {}

@scene("attic")
def s_attic(t, T, sid, tt):
    v = kb("attic_gruber", t, T, (0.5, 0.5, 1.0), (0.48, 0.5, 1.22)); img = v.render()
    img = caption(img, ["Er geht mit dem Gewehr hinauf.", "Niemand."], t, T * 0.45, cps=22)
    return img, {}

@scene("newspaper")
def s_newspaper(t, T, sid, tt):
    v = path("kitchen_news", t, [(0, 0.5, 0.5, 1.0), (T, "news", 0.0, 1.45)]); img = v.render()
    img = caption(img, ["Niemand hat sie gekauft.", "Wer hat sie gebracht?"], t, T * 0.45, col=[PAPER, RED], cps=22)
    return img, {}

@scene("key")
def s_key(t, T, sid, tt):
    v = kb("kitchen_keys", t, T, (0.5, 0.5, 1.0), (0.5, 0.5, 1.35)); img = v.render()
    img = stamp(img, "WEG", t, 1.6, W * 0.5, H * 0.66, 64, -6)
    img = caption(img, ["Am Maschinenhaus:", "Kratzspuren am Schloss."], t, T * 0.5, cps=24)
    return img, {}

@scene("neighbors")
def s_neighbors(t, T, sid, tt):
    v = kb("neighbors", t, T, (0.5, 0.5, 1.0), (0.48, 0.5, 1.18)); img = v.render()
    img = caption(img, ["Angebot: den Wald absuchen.", "Gruber: abgelehnt."], t, 0.8, col=[PAPER, RED], cps=22)
    img = stamp(img, "KEINE POLIZEI", t, T * 0.8, W * 0.68, PIC_T + 140, 54, -5)
    return img, dict(snow=0.5)

@scene("calendar")
def s_calendar(t, T, sid, tt):
    v = kb("desk_calendar", t, T, (0.5, 0.5, 1.0), (0.5, 0.48, 1.3)); img = v.render()
    return img, {}

@scene("maid_arrives")
def s_maid_arrives(t, T, sid, tt):
    v = kb("maid_arrives", t, T, (0.63, 0.5, 1.3), (0.72, 0.54, 1.65)); img = v.render()
    img = tag(img, "MARIA BAUMGARTNER, 44", t, 2.0, hold=T * 0.45)
    img = caption(img, ["Die neue Magd. Ihre Schwester bringt sie hin."], t, 3.0, cps=26, hold=7)
    img = caption(img, ["Die Schwester gehört zu den Letzten,", "die die Familie lebend sehen."], t, T * 0.55, cps=26)
    return img, dict(snow=0.5)

@scene("barn")
def s_barn(t, T, sid, tt):
    v = kb("barn_in", t, T, (0.5, 0.5, 1.0), (0.53, 0.5, 1.25)); img = v.render()
    img = tag(img, "NACHT AUF DEN 1. APRIL 1922", t, 0.8, hold=T * 0.4)
    img = caption(img, ["Andreas · Cäzilia · Viktoria", "die kleine Cäzilia"], t, T * 0.62, cps=20)
    return img, {}

@scene("house_dark")
def s_house_dark(t, T, sid, tt):
    v = kb("farm_wide", t, T, (0.48, 0.52, 1.1), (0.44, 0.52, 1.3)); a = v.render()
    v2 = kb("house_dark", t, T, (0.48, 0.52, 1.1), (0.44, 0.52, 1.3)); b = v2.render()
    img = xfade(a, b, seg(t, T * 0.3, T * 0.36))
    img = caption(img, ["Sechs Menschen in einer Nacht."], t, T * 0.4, cps=24, hold=4.5)
    img = caption(img, ["Tatwaffe: sehr wahrscheinlich", "eine Reuthaue."], t, T * 0.68, cps=24)
    return img, dict(snow=0.7)

@scene("quiet")
def s_quiet(t, T, sid, tt):
    v = kb("farm_far", t, T, (0.5, 0.5, 1.2), (0.5, 0.5, 1.28)); img = darken(v.render(), 0.75)
    return img, dict(snow=0.6)

@scene("days")
def s_days(t, T, sid, tt):
    cut = T * 0.78
    if t < cut:
        v = path("desk_days", t, [(0, 0.5, 0.5, 1.0), (1.2, "day0", 0.0, 1.6), (6.5, "day1", 0.0, 1.6), (11.5, "day2", 0.0, 1.6), (cut, "day2", 0.0, 1.7)])
        img = v.render()
        img = caption(img, ["Sa: Cäzilia fehlt in der Schule."], t, 1.4, cps=26, hold=4.6)
        img = caption(img, ["So: niemand in der Messe."], t, 6.7, cps=26, hold=4.6)
        img = caption(img, ["Mo: der Briefträger klopft. Keiner öffnet."], t, 11.7, cps=26)
        return img, {}
    v = kb("days", t - cut, T - cut, (0.5, 0.5, 1.0), (0.5, 0.5, 1.08)); img = v.render()
    img = caption(img, ["„Die Grubers waren halt komisch.“"], t - cut, 0.6, cps=24)
    return img, dict(snow=0.4)

@scene("chimney")
def s_chimney(t, T, sid, tt):
    cut = T * 0.3
    if t < cut:
        v = kb("chimney", t, cut, (0.5, 0.5, 1.0), (0.5, 0.48, 1.1)); img = v.render()
        img = add_smoke(img, v, tt, 1.3, 0.75)
        img = tag(img, "RAUCH AUS DEM KAMIN", t, 1.0)
        return img, dict(snow=0.6)
    u = t - cut
    v = kb("kitchen_bread", u, T - cut, (0.5, 0.5, 1.0), (0.5, 0.5, 1.22)); img = v.render()
    lines = ["Vieh gefüttert", "Brot angeschnitten", "vom Fleisch fehlt etwas"]
    shown = [ln for i, ln in enumerate(lines) if u > 1.0 + i * 2.2]
    if shown:
        img = caption(img, ["✓ " + s for s in shown], u, 1.0, cps=200)
    img = stamp(img, "JEMAND HAT HIER GELEBT", u, (T - cut) * 0.8, W * 0.5, PIC_T + 150, 50, -4)
    return img, {}

@scene("mechanic")
def s_mechanic(t, T, sid, tt):
    v = kb("mechanic", t, T, (0.5, 0.5, 1.0), (0.55, 0.52, 1.3)); img = v.render()
    img = tag(img, "DIENSTAG, 4. APRIL 1922", t, 0.6, hold=T * 0.35)
    img = caption(img, ["Albert Hofner, Monteur.", "Keiner öffnet. Nur der Hund bellt."], t, 2.5, cps=24, hold=9)
    img = caption(img, ["Mehrere Stunden allein auf dem Hof."], t, T * 0.55, cps=24, hold=5)
    img = caption(img, ["Wer hat ihn beobachtet?"], t, T * 0.8, col=RED, size=38, cps=22)
    return img, dict(snow=0.4)

@scene("discovery")
def s_discovery(t, T, sid, tt):
    v = kb("discovery", t, T, (0.5, 0.5, 1.0), (0.55, 0.5, 1.3)); img = v.render()
    img = tag(img, "LORENZ SCHLITTENBAUER, NACHBAR", t, 0.8, hold=T * 0.5)
    img = stamp(img, "4. APRIL 1922", t, T * 0.7, W * 0.72, PIC_T + 140, 52, -6)
    return img, dict(snow=0.4)

@scene("money")
def s_money(t, T, sid, tt):
    v = kb("kitchen_money", t, T, (0.5, 0.5, 1.0), (0.5, 0.52, 1.3)); img = v.render()
    img = tag(img, "POLIZEI AUS MÜNCHEN · 5. APRIL", t, 0.6, hold=T * 0.4)
    img = caption(img, ["Bargeld und Goldmünzen,", "offen in Schränken und Schubladen."], t, T * 0.4, cps=26, hold=5)
    img = stamp(img, "RAUBMORD? NEIN.", t, T * 0.78, W * 0.66, H * 0.62, 60, -7)
    return img, {}

@scene("crime_scene")
def s_crime_scene(t, T, sid, tt):
    v = kb("crime_scene", t, T, (0.5, 0.5, 1.0), (0.52, 0.52, 1.22)); img = v.render()
    img = caption(img, ["Die Toten wurden bewegt.", "Dutzende Neugierige auf dem Hof."], t, T * 0.3, cps=24, hold=8)
    img = stamp(img, "SPUREN: ZERSTÖRT", t, T * 0.78, W * 0.5, PIC_T + 140, 58, -4)
    return img, dict(snow=0.3)

@scene("munich")
def s_munich(t, T, sid, tt):
    v = kb("desk_munich", t, T, (0.5, 0.5, 1.0), (0.5, 0.5, 1.3)); img = v.render()
    img = caption(img, ["Hoffnung: Hellseher in München."], t, T * 0.3, cps=24, hold=7)
    img = caption(img, ["Was sie gesehen haben: in keiner Akte."], t, T * 0.55, cps=24, hold=4.5)
    img = stamp(img, "SCHÄDEL: VERSCHOLLEN", t, T * 0.8, W * 0.5, PIC_T + 140, 56, -5)
    return img, {}

@scene("board")
def s_board(t, T, sid, tt):
    v = kb("board", t, T, (0.5, 0.5, 1.0), (0.5, 0.5, 1.1)); img = v.render()
    img = tag(img, "MEHR ALS 100 BEFRAGTE", t, 0.6)
    img = stamp(img, "KEINE SPUR BEWIESEN", t, T * 0.72, W * 0.5, PIC_B - 120, 50, -4)
    return img, {}

def board_zoom(t, T, card, lines, stamp_txt=None, at=0.85):
    im, meta = plate("board")
    hx, hy = meta.get(card, [0.5, 0.5])
    v = path("board", t, [(0, 0.5, 0.5, 1.0), (1.4, hx + 0.16, hy, 2.0), (T, hx + 0.16, hy, 2.15)])
    img = v.render()
    img = notes(img, lines, t, 1.6)
    if stamp_txt: img = stamp(img, stamp_txt, t, T * at, 1460, PIC_B - 110, 48, -6)
    return img, {}

@scene("suspect1")
def s_suspect1(t, T, sid, tt):
    return board_zoom(t, T, "bcard0", ["SPUR 1: DER NACHBAR", "Witwer, Beziehung mit Viktoria", "galt als Vater von Josef",
                                       "– hat das später bestritten", "kennt sich im dunklen Haus aus", "geht direkt zu den Toten"])

@scene("suspect1b")
def s_suspect1b(t, T, sid, tt):
    return board_zoom(t, T, "bcard0", ["SPUR 1: DER NACHBAR", "verklagt Leute, die ihn", "„Mörder“ nennen"], "RECHT BEKOMMEN", 0.7)

@scene("suspect2")
def s_suspect2(t, T, sid, tt):
    return board_zoom(t, T, "bcard1", ["SPUR 2: DER EHEMANN", "gefallen 12/1914 (Kameraden)", "kein eigenes Grab",
                                       "nach 1945: „in Russland gesehen“"], "KEINE BEWEISE", 0.86)

@scene("suspect3")
def s_suspect3(t, T, sid, tt):
    return board_zoom(t, T, "bcard2", ["SPUR 3: DIE BRÜDER GUMP", "1950er: die Schwester sagt,", "Adolf habe gestanden",
                                       "Anton: fest- und freigelassen"], "HÖRENSAGEN", 0.85)

@scene("weapon")
def s_weapon(t, T, sid, tt):
    v = path("desk_weapon", t, [(0, 0.5, 0.5, 1.0), (T, "weapon", 0.0, 1.4)]); img = v.render()
    img = stamp(img, "1923", t, 0.5, W * 0.2, PIC_T + 150, 80, -6)
    img = caption(img, ["Gefunden im Zwischenboden.", "Der Täter hat sie im Haus versteckt."], t, T * 0.45, cps=26)
    return img, {}

@scene("students")
def s_students(t, T, sid, tt):
    v = path("desk_students", t, [(0, 0.5, 0.5, 1.0), (T * 0.55, "redact", 0.0, 1.35), (T, "redact", 0.0, 1.6)]); img = v.render()
    img = tag(img, "2007 · FH FÜRSTENFELDBRUCK", t, 0.8, hold=T * 0.45)
    img = caption(img, ["Ein Hauptverdächtiger.", "Name: nicht öffentlich."], t, T * 0.6, col=[PAPER, RED], cps=24)
    return img, {}

@scene("memorial")
def s_memorial(t, T, sid, tt):
    v = kb("memorial", t, T, (0.5, 0.5, 1.0), (0.5, 0.48, 1.2)); img = v.render()
    img = caption(img, ["Gräber: Friedhof Waidhofen."], t, T * 0.5, cps=24)
    return img, dict(snow=0.35)

@scene("ending")
def s_ending(t, T, sid, tt):
    cut = T * 0.62
    if t < cut:
        v = kb("kitchen_wide", t, cut, (0.5, 0.5, 1.0), (0.48, 0.52, 1.18)); img = v.render()
        return img, {}
    u = t - cut
    v = kb("farm_window", u, T - cut, (0.5, 0.5, 1.05), (0.5, 0.48, 1.3)); img = v.render()
    img = window_figure(img, v, seg(u, 0.5, 5.0))
    img = caption(img, ["Wir wissen es nicht."], u, (T - cut) * 0.6, cps=20)
    return img, dict(snow=0.6)

@scene("outro")
def s_outro(t, T, sid, tt):
    v = kb("farm_far", t, T, (0.5, 0.5, 1.1), (0.5, 0.5, 1.2)); img = darken(v.render(), 0.35)
    d = ImageDraw.Draw(img, "RGBA")
    a = seg(t, 0.5, 1.3)
    if a > 0:
        draw_spaced(d, (W / 2, 430), "Wer war in diesen Tagen auf Hinterkaifeck?", font(F_SANS_B, 52), (*PAPER, int(255 * a)), 1, anchor="ms")
    img = caption(img, ["Schreib deine Version in die Kommentare."], t, 3.0, x=W / 2 - 400, y=520, size=34)
    b = seg(t, T * 0.5, T * 0.5 + 0.6)
    if b > 0:
        draw_spaced(d, (W / 2, 720), "NÄCHSTE AKTE", font(F_SANS_B, 30), (*RED, int(255 * b)), 8, anchor="ms")
        draw_spaced(d, (W / 2, 800), "Die Frau, die es nie gab", font(F_X, 64), (*PAPER, int(255 * b)), 2, anchor="ms")
    return img, dict(snow=0.4)


def s_missing(t, T, sid, tt):
    img = Image.new("RGB", (W, H), (8, 10, 16))
    d = ImageDraw.Draw(img); d.text((W / 2, H / 2), f"[{sid}]", font=font(F_MONO, 40), fill=(90, 90, 90), anchor="mm")
    return img, {}

# ================================================================ рендер
def frame(tl, tt, fno):
    seg_ = next((s for s in tl if s["start"] <= tt < s["end"]), tl[-1])
    idx = tl.index(seg_); j = idx
    while j > 0 and tl[j - 1]["scene"] == seg_["scene"] and seg_["scene"] not in ("tracks",):
        j -= 1
    s0 = tl[j]; T = seg_["end"] - s0["start"]; t = tt - s0["start"]
    fn = SC.get(seg_["scene"], s_missing)
    img, o = fn(t, T, seg_["id"], tt)
    a = np.asarray(img, np.float32) / 255
    sn = o.get("snow", 0)
    if sn: a = a + snow(tt, sn)[..., None] * 0.55
    a = a * vignette()
    a = a + grain(fno) * 0.018
    # затемнение на входе в сцену
    if t < 0.3 and j > 0: a *= 0.25 + 0.75 * ease(t / 0.3)
    if tt < 1.0: a *= ease(tt / 1.0)
    a[:PIC_T] = 0; a[PIC_B:] = 0
    img = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    if CUES: img = subtitles(img, tt)
    return img

def render_chunk(args):
    k, f0, f1, tl, path = args
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                           "-maxrate", "10M", "-bufsize", "20M", "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)
    for fno in range(f0, f1):
        ff.stdin.write(frame(tl, fno / FPS, fno).tobytes())
    ff.stdin.close(); ff.wait()
    return path

def main():
    tl = RE.timeline(); total = tl[-1]["end"]
    json.dump(tl, open(os.path.join(OUT, "timeline.json"), "w"), indent=1)
    t0 = T_FROM; t1 = float(T_TO) if T_TO else total
    f0, f1 = int(t0 * FPS), int(min(t1, total) * FPS)
    step = math.ceil((f1 - f0) / NPROC)
    jobs = [(k, f0 + k * step, min(f1, f0 + (k + 1) * step), tl, os.path.join(OUT, f"chunk{k:02d}.mp4"))
            for k in range(NPROC) if f0 + k * step < f1]
    with mp.Pool(len(jobs)) as pool:
        paths = pool.map(render_chunk, jobs)
    with open(os.path.join(OUT, "chunks.txt"), "w") as f:
        for p in paths: f.write(f"file '{p}'\n")
    vid = os.path.join(OUT, "video.mp4")
    subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", os.path.join(OUT, "chunks.txt"), "-c", "copy", vid])
    vpath, mpath = os.path.join(OUT, "voice.wav"), os.path.join(OUT, "music.wav")
    RE.voice_track(tl, total, vpath); RE.music(total, tl, mpath)
    final = os.path.join(OUT, "final.mp4")
    flt = ("[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,asplit[v][vv];[2:a]volume=0.11,highpass=f=30[m];"
           "[m][v]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=400[md];"
           "[vv][md]amix=inputs=2:normalize=0,alimiter=limit=0.95,apad[a]")
    subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-i", vid, "-ss", f"{t0:.3f}", "-i", vpath, "-ss", f"{t0:.3f}", "-i", mpath,
                           "-filter_complex", flt, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                           "-t", f"{(f1 - f0) / FPS:.3f}", "-movflags", "+faststart", final])
    print("done", final, round(total, 1))

if __name__ == "__main__":
    main()
