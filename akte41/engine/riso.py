# -*- coding: utf-8 -*-
"""Akte 41: Ризограф, ночная палитра (синий, красный, серый). 1920x1080.

Основа взята из animation-style/render.py: три краски с умножением, точечный
растр, несовмещение листов, «кипящие» линии на двойках, бумага с волокном.
"""
import math
import numpy as np
import cairo

W, H = 1920, 1080
INKS = {
    "navy": (28, 42, 96),
    "red": (226, 52, 58),
    "grey": (138, 142, 150),
}
SCREEN_ANGLE = {"navy": 15, "red": 75, "grey": 45}
PAPER = np.array([241, 234, 219], dtype=np.float32) / 255.0
FONT = "Inter"
MONO = "Courier 10 Pitch"

rng = np.random.default_rng(41)


def h(*a):
    s = 0.0
    for v, k in zip(a, (12.9898, 78.233, 37.719, 4.581, 91.17)):
        s += v * k
    return (math.sin(s) * 43758.5453) % 1.0


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def eout(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def eback(x):
    x = clamp(x)
    c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def lerp(a, b, t):
    return a + (b - a) * t


def seg(t, a, b):
    if b <= a:
        return 1.0 if t >= a else 0.0
    return clamp((t - a) / (b - a))


# ------------------------------------------------------------ растр и бумага
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)


def make_screen(angle, cell):
    a = math.radians(angle)
    u = xx * math.cos(a) + yy * math.sin(a)
    v = -xx * math.sin(a) + yy * math.cos(a)
    s = 0.5 + 0.25 * (np.cos(2 * np.pi * u / cell) + np.cos(2 * np.pi * v / cell))
    return (1.0 - s).astype(np.float32)


SCREENS = {k: make_screen(SCREEN_ANGLE[k], 10.0) for k in INKS}


def lowfreq(scale, seed):
    from PIL import Image
    r = np.random.default_rng(seed)
    small = r.random((H // scale + 2, W // scale + 2)).astype(np.float32)
    im = Image.fromarray((small * 255).astype(np.uint8)).resize(
        ((W // scale + 2) * scale, (H // scale + 2) * scale), Image.BICUBIC)
    return np.asarray(im, dtype=np.float32)[:H, :W] / 255.0


fiber = 0.6 * lowfreq(3, 1) + 0.4 * rng.random((H, W)).astype(np.float32)
PAPER_TEX = (0.93 + 0.07 * fiber)[..., None]
GRAIN = []
for i in range(3):
    g = 0.5 * lowfreq(60, 10 + i) + 0.3 * lowfreq(8, 20 + i) + 0.2 * rng.random((H, W)).astype(np.float32)
    GRAIN.append((0.80 + 0.20 * g).astype(np.float32))
VIGNETTE = (1.0 - 0.22 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / 2)[..., None]
INK_MUL = {k: (1.0 - np.array(c, np.float32) / 255.0) for k, c in INKS.items()}


class Frame:
    def __init__(self, seed, boil=1.6):
        self.seed = seed
        self.boil = boil
        self.surf, self.ctx = {}, {}
        for ink in INKS:
            for kind in ("solid", "tone"):
                sf = cairo.ImageSurface(cairo.FORMAT_A8, W, H)
                self.surf[(ink, kind)] = sf
                self.ctx[(ink, kind)] = cairo.Context(sf)
        self.m = cairo.Matrix()
        self.stack = []
        self.pid = 0

    def push(self): self.stack.append(cairo.Matrix(*self.m))
    def pop(self): self.m = self.stack.pop()
    def translate(self, x, y): self.m = cairo.Matrix(x0=x, y0=y).multiply(self.m)

    def rotate(self, a):
        c, s = math.cos(a), math.sin(a)
        self.m = cairo.Matrix(c, s, -s, c, 0, 0).multiply(self.m)

    def scale(self, sx, sy=None):
        self.m = cairo.Matrix(sx, 0, 0, sx if sy is None else sy, 0, 0).multiply(self.m)

    def j(self, x, y, amp=None):
        self.pid += 1
        a = self.boil if amp is None else amp
        return (x + (h(self.pid, self.seed, 1.3) - .5) * 2 * a,
                y + (h(self.pid, self.seed, 7.1) - .5) * 2 * a)

    def _apply(self, targets, pathfn, op):
        pid0 = self.pid
        for c in targets:
            self.pid = pid0
            c.save()
            c.set_matrix(self.m)
            c.new_path()
            pathfn(c)
            op(c)
            c.restore()

    def fill(self, ink, pathfn, tone=None):
        kind = "solid" if tone is None else "tone"
        a = 1.0 if tone is None else clamp(tone)

        def op(c):
            c.set_source_rgba(0, 0, 0, a)
            c.fill()
        self._apply([self.ctx[(ink, kind)]], pathfn, op)

    def stroke(self, ink, pathfn, w, tone=None, dash=None):
        kind = "solid" if tone is None else "tone"
        a = 1.0 if tone is None else clamp(tone)

        def op(c):
            c.set_source_rgba(0, 0, 0, a)
            c.set_line_width(w)
            c.set_line_cap(cairo.LINE_CAP_ROUND)
            c.set_line_join(cairo.LINE_JOIN_ROUND)
            if dash:
                c.set_dash(dash)
            c.stroke()
        self._apply([self.ctx[(ink, kind)]], pathfn, op)

    def knock(self, pathfn):
        def op(c):
            c.set_operator(cairo.OPERATOR_CLEAR)
            c.fill()
        self._apply(list(self.ctx.values()), pathfn, op)

    def paint(self, ink, pathfn, tone=None, outline=None, ow=4):
        self.knock(pathfn)
        if ink:
            self.fill(ink, pathfn, tone)
        if outline:
            self.stroke(outline, pathfn, ow)

    def arr(self, ink, kind):
        sf = self.surf[(ink, kind)]
        sf.flush()
        a = np.ndarray((H, sf.get_stride()), dtype=np.uint8, buffer=sf.get_data())
        return a[:, :W].astype(np.float32) * (1.0 / 255.0)

    def composite(self, frame_no, fade=1.0):
        out = np.empty((H, W, 3), np.float32)
        out[:] = PAPER
        for i, ink in enumerate(INKS):
            solid = self.arr(ink, "solid")
            tone = self.arr(ink, "tone")
            ht = np.clip((tone - SCREENS[ink]) * 10.0 + 0.5, 0, 1)
            ht *= (tone > 0.02)
            cov = np.maximum(solid, ht) * GRAIN[(frame_no + i) % 3]
            dx = int(round(1.6 * math.sin(frame_no * 0.7 + i * 2.1))) + (2, -1, 0)[i]
            dy = int(round(1.6 * math.cos(frame_no * 0.9 + i * 1.3))) + (1, 2, -1)[i]
            cov = np.roll(cov, (dy, dx), (0, 1))
            out *= 1.0 - cov[..., None] * INK_MUL[ink]
        out *= PAPER_TEX
        out *= VIGNETTE
        if fade < 1.0:
            out *= fade
        return (np.clip(out, 0, 1) * 255).astype(np.uint8)


# ------------------------------------------------------------ пути
def smooth(c, pts, closed=True):
    n = len(pts)
    if n < 2:
        return
    c.move_to(*pts[0])
    rng_ = range(n) if closed else range(n - 1)
    for i in rng_:
        p0 = pts[i - 1] if (closed or i > 0) else pts[0]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if (closed or i + 2 < n) else pts[-1]
        c.curve_to(p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6,
                   p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6, p2[0], p2[1])
    if closed:
        c.close_path()


def blob(F, cx, cy, rx, ry, n=14, rot=0.0, amp=None, wob=0.0, seed=0):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        k = 1 + wob * (h(i, 3.3, seed) - .5)
        x = math.cos(a) * rx * k
        y = math.sin(a) * ry * k
        xr = cx + x * math.cos(rot) - y * math.sin(rot)
        yr = cy + x * math.sin(rot) + y * math.cos(rot)
        pts.append(F.j(xr, yr, amp))
    return lambda c: smooth(c, pts)


def poly(F, pts, closed=True, amp=None, smooth_=False):
    jp = [F.j(x, y, amp) for x, y in pts]
    if smooth_:
        return lambda c: smooth(c, jp, closed)

    def p(c):
        c.move_to(*jp[0])
        for q in jp[1:]:
            c.line_to(*q)
        if closed:
            c.close_path()
    return p


def rect(F, x, y, w, hh, amp=None):
    return poly(F, [(x, y), (x + w, y), (x + w, y + hh), (x, y + hh)], True, amp)


def line(F, x1, y1, x2, y2, amp=None):
    return poly(F, [(x1, y1), (x2, y2)], False, amp)


def text_extent(s, size, bold=True, font=None):
    sf = cairo.ImageSurface(cairo.FORMAT_A8, 8, 8)
    c = cairo.Context(sf)
    c.select_font_face(font or FONT, cairo.FONT_SLANT_NORMAL,
                       cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(size)
    return c.text_extents(s).x_advance


def textpath(F, s, x, y, size, bold=True, align="left", rot=0.0, font=None, amp=0.8):
    jx, jy = F.j(x, y, amp)
    jr = rot + (h(F.seed, len(s), 2.2) - .5) * 0.012

    def p(c):
        c.select_font_face(font or FONT, cairo.FONT_SLANT_NORMAL,
                           cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
        c.set_font_size(size)
        ext = c.text_extents(s)
        ox = {"left": 0, "center": -ext.x_advance / 2, "right": -ext.x_advance}[align]
        c.translate(jx, jy)
        c.rotate(jr)
        c.move_to(ox, 0)
        c.text_path(s)
    return p


def circle(F, cx, cy, r, amp=None):
    return blob(F, cx, cy, r, r, n=max(10, int(r / 4)), amp=amp)
