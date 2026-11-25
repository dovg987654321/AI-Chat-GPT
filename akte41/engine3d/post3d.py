# -*- coding: utf-8 -*-
"""
Пост-обработка 3D-кадров Akte 41: снег, дым из трубы, свечение окна, зерно, грейд, подписи.
Три подачи:
  film      — «Тёмное кино»: широкий кадр 2.39:1, холодная ночь, тёплое окно, зерно
  diorama   — «Макет следователя»: мягче, теплее, мелкий снег, подпись как в музее
  engraving — «Газетная гравюра 1922»: штриховка чернилами по бумаге, красное окно

python3 post3d.py IN_FRAMES_DIR TRACK.json LOOK OUT.mp4 [--fps-in 12] [--title "..."]
"""
import sys, os, json, glob, math, subprocess, tempfile, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy import ndimage as ndi

IN, TRACK, LOOK, OUT = sys.argv[1:5]
def opt(n, d):
    return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d
FPS_IN = int(opt("--fps-in", "12"))
TITLE = opt("--title", "Hinterkaifeck · März 1922")
FPS = 24
FONT_T = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_M = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
for f in ("/usr/share/fonts/opentype/inter/Inter-Medium.otf",):
    if os.path.exists(f): FONT_S = f
rng = np.random.default_rng(41)

# ---------------------------------------------------------------- 1) 12 → 24 к/с с компенсацией движения
tmp = tempfile.mkdtemp(prefix="p3d_")
src = sorted(glob.glob(os.path.join(IN, "f*.png")))
first = int(os.path.basename(src[0])[1:5])
for i, p in enumerate(src):
    os.symlink(os.path.abspath(p), os.path.join(tmp, f"s{i:04d}.png"))
if FPS_IN != FPS:
    subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS_IN), "-i", os.path.join(tmp, "s%04d.png"),
                           "-vf", f"minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1",
                           os.path.join(tmp, "i%04d.png")])
    frames = sorted(glob.glob(os.path.join(tmp, "i*.png")))
else:
    frames = sorted(glob.glob(os.path.join(tmp, "s*.png")))
track = {}
for tp in glob.glob(TRACK):
    track.update({int(k): v for k, v in json.load(open(tp)).items()})
tk = sorted(track)
def trk(fno, key):
    """экранная точка (0..1) для кадра 24 к/с — линейная интерполяция по отрендеренным"""
    f = first + fno if FPS_IN != FPS else int(os.path.basename(src[min(fno, len(src) - 1)])[1:5])
    lo = max([k for k in tk if k <= f] or [tk[0]]); hi = min([k for k in tk if k >= f] or [tk[-1]])
    a, b = np.array(track[lo][key][:2]), np.array(track[hi][key][:2])
    u = 0 if hi == lo else (f - lo) / (hi - lo)
    return a + (b - a) * u

W, H = Image.open(frames[0]).size
NF = len(frames)

# ---------------------------------------------------------------- частицы снега (3 слоя глубины)
def make_flakes(n, size, speed, blur):
    return dict(x=rng.uniform(0, W, n), y=rng.uniform(-H, H, n), ph=rng.uniform(0, 6.28, n),
                s=rng.uniform(size * 0.6, size * 1.3, n), v=rng.uniform(speed * 0.7, speed * 1.3, n), blur=blur)
LAYERS = {
    "film": [make_flakes(450, 1.3, 50, 0), make_flakes(110, 2.4, 110, 1.0), make_flakes(10, 6, 240, 4.0)],
    "diorama": [make_flakes(700, 1.4, 40, 0), make_flakes(160, 2.4, 70, 0.8)],
    "engraving": [make_flakes(500, 2.0, 60, 0), make_flakes(120, 4.0, 130, 0)],
}[LOOK]

def snow_layer(t):
    out = np.zeros((H, W), np.float32)
    for L in LAYERS:
        img = Image.new("L", (W, H), 0); d = ImageDraw.Draw(img)
        ys = (L["y"] + L["v"] * t) % (2 * H) - H * 0.5
        xs = (L["x"] + 18 * np.sin(L["ph"] + t * 0.9) + 25 * t) % W
        for x, y, s in zip(xs, ys, L["s"]):
            if -10 < y < H + 10:
                d.ellipse([x - s, y - s * 1.2, x + s, y + s * 1.2], fill=230)
        a = np.asarray(img, np.float32) / 255
        if L["blur"]: a = ndi.gaussian_filter(a, L["blur"])
        out = np.maximum(out, a)
    return out

# ---------------------------------------------------------------- дым из трубы
SMOKE = rng.uniform(0, 1000, 3)
def smoke_layer(fno, t):
    cx, cy = trk(fno, "chimney"); cx *= W; cy *= H
    m = np.zeros((H, W), np.float32)
    if not (0 < cx < W and 0 < cy < H): return m
    img = Image.new("L", (W, H), 0); d = ImageDraw.Draw(img)
    scale = W / 1920
    for k in range(70):
        age = (k / 70 + t * 0.09) % 1.0
        r = (6 + 70 * age) * scale
        x = cx + (40 * age + 14 * math.sin(age * 9 + SMOKE[0] + t * 0.5)) * scale * (1 + age * 2)
        y = cy - 380 * age * scale
        a = int(110 * (1 - age) ** 1.5 * min(1, age * 8))
        d.ellipse([x - r, y - r, x + r, y + r], fill=a)
    return ndi.gaussian_filter(np.asarray(img, np.float32) / 255, 9 * scale)

# ---------------------------------------------------------------- общие штуки
def grain(a, s):
    return a + rng.normal(0, s, a.shape[:2])[..., None].astype(np.float32)

def bloom(a, thr=0.75, rad=18, k=0.6):
    lum = a.mean(axis=2)
    hi = np.clip((lum - thr) / (1 - thr), 0, 1)[..., None] * a
    small = hi[::4, ::4]
    bl = np.stack([ndi.gaussian_filter(small[..., c], rad / 4) for c in range(3)], -1)
    bl = np.asarray(Image.fromarray((np.clip(bl, 0, 1) * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR), np.float32) / 255
    return a + bl * k

VIG = None
def vignette(a, k=0.45):
    global VIG
    if VIG is None:
        yy, xx = np.mgrid[0:H, 0:W]
        r = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
        VIG = (1 - k * np.clip(r - 0.35, 0, 1) ** 1.6)[..., None].astype(np.float32)
    return a * VIG

def text_overlay(img, t):
    if LOOK == "engraving": return img
    d = ImageDraw.Draw(img)
    a = min(1, max(0, (t - 0.6) / 0.8))
    if a <= 0: return img
    sc = W / 1920
    if LOOK == "film":
        f = ImageFont.truetype(FONT_M, int(30 * sc))
        n = int(len(TITLE) * min(1, (t - 0.6) / 1.6))
        y = int(H * 0.86 - 46 * sc)
        d.text((int(150 * sc), y), TITLE[:n], font=f, fill=(235, 232, 225))
    else:
        f = ImageFont.truetype(FONT_T, int(26 * sc)); f2 = ImageFont.truetype(FONT_M, int(18 * sc))
        x, y = int(90 * sc), int(H - 150 * sc)
        d.rectangle([x, y, x + int(420 * sc), y + int(78 * sc)], fill=(236, 230, 214))
        d.rectangle([x, y, x + int(10 * sc), y + int(78 * sc)], fill=(200, 40, 40))
        d.text((x + int(30 * sc), y + int(10 * sc)), "Hinterkaifeck, Oberbayern", font=f, fill=(30, 26, 24))
        d.text((x + int(30 * sc), y + int(46 * sc)), "Tatort-Modell · 31.03.1922", font=f2, fill=(90, 80, 70))
    return img

# ---------------------------------------------------------------- гравюра
PAPER = None
def engraving(a, fno):
    global PAPER
    lum = (a[..., 0] * 0.3 + a[..., 1] * 0.55 + a[..., 2] * 0.15)
    lo, hi = np.percentile(lum[::8, ::8], [2, 99.7])
    lum = np.clip((lum - lo) / (hi - lo + 1e-6), 0, 1) ** 0.5
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    wob = 1.6 * np.sin(yy / 37.0 + xx / 91.0) + 1.1 * np.sin(xx / 23.0 - yy / 57.0)
    per = 7.0 * W / 1920
    def screen(ang, shift=0.0):
        c, s = math.cos(ang), math.sin(ang)
        ph = ((xx * c + yy * s + wob) / per + shift) % 1.0
        return np.abs(ph - 0.5) * 2          # 0 в центре линии, 1 между линиями
    dark = 1 - lum
    ink = (screen(math.radians(28)) < dark * 0.85).astype(np.float32)
    ink2 = (screen(math.radians(-38), 0.3) < np.clip((dark - 0.45) * 1.6, 0, 1)).astype(np.float32)
    ink3 = (screen(math.radians(80), 0.6) < np.clip((dark - 0.75) * 2.2, 0, 1)).astype(np.float32)
    ink = np.maximum(np.maximum(ink, ink2), ink3)
    # контуры
    g = ndi.gaussian_filter(lum, 1.2)
    ed = np.hypot(ndi.sobel(g, 0), ndi.sobel(g, 1))
    ink = np.maximum(ink, np.clip((ed - 0.12) * 5, 0, 1))
    ink = ndi.gaussian_filter(ink, 0.6)
    if PAPER is None:
        n = rng.normal(0, 1, (H // 4, W // 4)).astype(np.float32)
        n = ndi.gaussian_filter(n, 2)
        n = np.asarray(Image.fromarray(((n - n.min()) / (np.ptp(n) + 1e-6) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32) / 255
        PAPER = np.array([237, 229, 210], np.float32) / 255 * (0.94 + 0.06 * n[..., None])
    paper = PAPER
    inkc = np.array([30, 26, 26], np.float32) / 255
    out = paper * (1 - ink[..., None]) + inkc * ink[..., None]
    # красное окно: где исходник тёплый и яркий
    warm = np.clip((a[..., 0] - a[..., 2]) * 4.0, 0, 1) * np.clip(a[..., 0] * 2.0, 0, 1)
    warm = ndi.gaussian_filter(warm, 3)
    red = np.array([214, 48, 50], np.float32) / 255
    out = out * (1 - warm[..., None] * 0.85) + red * (1 - ink[..., None] * 0.7) * warm[..., None] * 0.85
    return out

# ---------------------------------------------------------------- рендер
ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                       "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "17",
                       "-pix_fmt", "yuv420p", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
for fno, p in enumerate(frames):
    t = fno / FPS
    a = np.asarray(Image.open(p).convert("RGB"), np.float32) / 255
    sm = smoke_layer(fno, t)
    sn = snow_layer(t)
    if LOOK == "film":
        a = a * (1 - sm[..., None] * 0.35) + np.array([0.55, 0.6, 0.72]) * sm[..., None] * 0.35
        a = bloom(a, 0.7, 26, 0.9)
        # грейд: холодные тени, тёплые света
        a = a * np.array([0.96, 1.0, 1.06]) + np.array([-0.005, 0.0, 0.012])
        a = a + sn[..., None] * 0.5
        a = vignette(a, 0.55)
        a = grain(a, 0.022)
        a = np.clip(a, 0, 1)
        bar = int((H - W / 2.39) / 2)
        a[:bar] = 0; a[H - bar:] = 0
    elif LOOK == "diorama":
        a = a * (1 - sm[..., None] * 0.3) + np.array([0.7, 0.72, 0.8]) * sm[..., None] * 0.3
        a = bloom(a, 0.65, 22, 0.7)
        lum = a.mean(axis=2, keepdims=True)
        a = lum + (a - lum) * 1.15
        a = a + sn[..., None] * 0.7
        a = vignette(a, 0.4)
        a = grain(a, 0.012)
    else:
        a = a + sm[..., None] * 0.25
        a = engraving(a, fno)
        a = a * (1 - sn[..., None] * 0.0) + sn[..., None] * 0.9 * (1 - a) * 0 + sn[..., None] * 0.0
        # снег в гравюре: белые точки с тонким контуром
        a = a * (1 - sn[..., None]) + np.array([0.96, 0.94, 0.88]) * sn[..., None]
        a = vignette(a, 0.25)
    img = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    img = text_overlay(img, t)
    ff.stdin.write(img.tobytes())
ff.stdin.close(); ff.wait()
shutil.rmtree(tmp, ignore_errors=True)
print("done", OUT, NF, "frames")
