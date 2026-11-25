# -*- coding: utf-8 -*-
"""Реквизит Akte 41: небо, снег, лес, хутор, фигуры, штампы, карточки."""
import math
from riso import (W, H, MONO, h, clamp, ease, eout, eback, lerp, seg,
                  blob, poly, rect, line, textpath, circle, text_extent, smooth)


# ------------------------------------------------------------ фон
def night_sky(F, tone=0.82, stars=True, moon=(1550, 190), seed=0):
    F.fill("navy", rect(F, -40, -40, W + 80, H + 80, amp=0), tone=tone)
    F.fill("grey", rect(F, -40, -40, W + 80, H + 80, amp=0), tone=0.25)
    if stars:
        for i in range(70):
            x = h(i, 1.1, seed) * W
            y = h(i, 2.7, seed) * 560
            r = 1.5 + 2.5 * h(i, 5.5, seed)
            tw = 0.5 + 0.5 * math.sin(F.seed * 0.15 + i)
            if tw > 0.25:
                F.knock(circle(F, x, y, r, amp=0.3))
    if moon:
        F.knock(circle(F, moon[0], moon[1], 62, amp=0.6))
        F.fill("grey", circle(F, moon[0] + 14, moon[1] - 8, 58), tone=0.18)


def day_sky(F, tone=0.18):
    F.fill("grey", rect(F, -40, -40, W + 80, H + 80, amp=0), tone=tone)


def snow_ground(F, horizon=700, seed=0, shade=0.14):
    pts = [(-40, horizon)]
    for i in range(13):
        x = -40 + i * (W + 80) / 12
        pts.append((x, horizon + 30 * math.sin(i * 1.3 + seed) + 14 * h(i, seed)))
    pts += [(W + 40, H + 40), (-40, H + 40)]
    p = poly(F, pts, True, amp=1.0, smooth_=False)
    F.knock(p)
    F.fill("grey", p, tone=shade)
    # лёгкие тени-сугробы
    for i in range(6):
        cx = h(i, 8.1, seed) * W
        cy = horizon + 120 + h(i, 4.4, seed) * 260
        F.fill("navy", blob(F, cx, cy, 220, 26, wob=.3, seed=i), tone=0.10)


def forest(F, x0, x1, base, height=230, seed=0, ink="navy", tone=None, n=None):
    n = n or int((x1 - x0) / 46)
    for i in range(n):
        x = x0 + (i + h(i, seed, 1.7) * 0.6) * (x1 - x0) / n
        hh = height * (0.65 + 0.5 * h(i, seed, 3.9))
        w = hh * 0.34
        b = base + 12 * h(i, seed, 6.1)
        pts = [(x, b - hh)]
        for k in range(4):
            yk = b - hh + (k + 1) * hh / 4.3
            wk = w * (k + 1) / 4
            pts.insert(0, (x - wk, yk))
            pts.append((x + wk, yk))
        pts = pts[:4] + [(x - w * 0.12, b)] + [(x + w * 0.12, b)] + pts[4:]
        pts = [pts[0], pts[1], pts[2], pts[3]] + [(x - w, b - 6), (x + w, b - 6)] + pts[5:]
        F.fill(ink, poly(F, [(x, b - hh), (x - w, b), (x + w, b)], True, amp=1.2), tone=tone)


def snowfall(F, t, n=90, seed=3, area=(0, 0, W, H), tone=None):
    x0, y0, w, hh = area
    for i in range(n):
        sp = 40 + 50 * h(i, seed)
        y = y0 + ((h(i, 2.2, seed) * hh + t * sp) % hh)
        x = x0 + (h(i, 7.7, seed) * w + 25 * math.sin(t * 0.8 + i)) % w
        r = 2 + 3 * h(i, 9.1, seed)
        F.knock(circle(F, x, y, r, amp=0.4))


# ------------------------------------------------------------ хутор
def farm(F, cx, base, sc=1.0, lit=1.0, smoke=0.0, t=0.0, door=0.0, dark=False, windows_off=0):
    """Хинтеркайфек: жилой дом слева, сарай-конюшня под одной крышей справа."""
    F.push(); F.translate(cx, base); F.scale(sc)
    # стены
    house = rect(F, -330, -190, 300, 190)
    barn = rect(F, -30, -170, 380, 170)
    F.paint("grey", house, tone=0.42 if not dark else 0.7, outline="navy", ow=5)
    F.paint("grey", barn, tone=0.55 if not dark else 0.8, outline="navy", ow=5)
    # доски сарая
    for i in range(9):
        x = -10 + i * 40
        F.stroke("navy", line(F, x, -165, x, -4), 2.5, tone=0.6)
    # крыши
    F.paint("navy", poly(F, [(-360, -185), (-180, -330), (0, -185)], True, amp=1.4))
    F.paint("navy", poly(F, [(-40, -165), (-10, -290), (380, -290), (380, -165)], True, amp=1.4))
    # снег на крыше
    F.knock(poly(F, [(-345, -195), (-180, -318), (-15, -195), (-60, -200), (-180, -295), (-300, -200)], True, amp=1.2))
    F.knock(poly(F, [(-20, -282), (370, -282), (370, -270), (-15, -268)], True, amp=1.0))
    # труба и дым
    F.paint("navy", rect(F, -110, -300, 34, 80))
    if smoke > 0:
        for i in range(7):
            k = (t * 0.25 + i / 7) % 1.0
            r = (14 + 46 * k) * smoke
            F.fill("grey", circle(F, -93 + 40 * math.sin(k * 3 + i) * k, -310 - 260 * k, r),
                   tone=0.55 * (1 - k) * smoke)
    # окна
    wins = [(-300, -150), (-210, -150), (-120, -150)]
    for i, (x, y) in enumerate(wins):
        p = rect(F, x, y, 54, 66)
        on = lit > 0 and i >= windows_off
        if on:
            F.knock(p)
            F.fill("red", p, tone=0.55 * lit)
            F.fill("red", blob(F, x + 27, y + 33, 70, 60), tone=0.10 * lit)
        else:
            F.paint("navy", p)
        F.stroke("navy", line(F, x + 27, y, x + 27, y + 66), 3)
        F.stroke("navy", line(F, x, y + 33, x + 54, y + 33), 3)
        F.stroke("navy", p, 4)
    # дверь сарая
    dp = rect(F, 120, -130, 110, 130)
    if door > 0:
        F.knock(rect(F, 120, -130, 110 * door, 130))
        F.fill("red", rect(F, 120, -130, 110 * door, 130), tone=0.25)
        F.paint("navy", rect(F, 120 + 110 * door, -130, 110 * (1 - door) + 1, 130))
    else:
        F.paint("navy", dp, tone=None)
        F.stroke("grey", line(F, 124, -126, 226, -4), 3)
        F.stroke("grey", line(F, 226, -126, 124, -4), 3)
    # дверь дома
    F.paint("navy", rect(F, -50, -120, 0.1, 0.1))
    F.pop()


def footprints(F, pts, prog, size=1.0, tone=0.75, ink="navy"):
    """следы вдоль ломаной, prog 0..1 — сколько уже появилось"""
    # длина пути
    L = [0.0]
    for a, b in zip(pts, pts[1:]):
        L.append(L[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = L[-1]
    step = 34 * size
    n = int(total / step)
    shown = int(n * clamp(prog))
    for k in range(shown):
        d = k * step
        i = 1
        while i < len(L) - 1 and L[i] < d:
            i += 1
        a, b = pts[i - 1], pts[i]
        u = (d - L[i - 1]) / max(1e-3, L[i] - L[i - 1])
        x, y = lerp(a[0], b[0], u), lerp(a[1], b[1], u)
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        side = 1 if k % 2 else -1
        nx, ny = -math.sin(ang) * 9 * size * side, math.cos(ang) * 9 * size * side
        persp = 0.55 + 0.45 * clamp((y - 650) / 400)
        F.fill(ink, blob(F, x + nx, y + ny, 11 * size * persp, 5.5 * size * persp, n=10, rot=ang, amp=0.6),
               tone=tone)


# ------------------------------------------------------------ фигуры
def figure(F, x, y, sc=1.0, kind="man", phase=None, ink="navy", tone=None, facing=1,
           lantern=0.0, carry=None, gun=False, outline=False):
    """силуэт без лица. y — уровень ступней."""
    F.push(); F.translate(x, y); F.scale(sc * facing, sc)
    small = kind in ("girl", "boy")
    k = 0.62 if kind == "girl" else 0.42 if kind == "boy" else 1.0
    F.scale(k)
    sw = math.sin(phase) if phase is not None else 0.0
    bob = abs(math.cos(phase)) * 6 if phase is not None else 0.0
    F.translate(0, -bob)
    def P(p):
        if outline:
            F.stroke(ink, p, 5 / max(.3, sc * k), dash=[14, 10])
        else:
            F.fill(ink, p, tone=tone)
    # ноги
    P(poly(F, [(-14, -120), (-4, -120), (-6 + 22 * sw, 0), (-22 + 22 * sw, 0)], True))
    P(poly(F, [(4, -120), (14, -120), (22 - 22 * sw, 0), (6 - 22 * sw, 0)], True))
    # корпус
    if kind in ("woman", "maid", "girl", "old"):
        P(poly(F, [(-30, -250), (30, -250), (52, -60), (-52, -60)], True))
    else:
        P(poly(F, [(-34, -255), (34, -255), (30, -110), (-30, -110)], True))
    # руки
    a1 = 0.25 * sw
    P(poly(F, [(-34, -245), (-24, -240), (-30 - 60 * math.sin(.25 + a1), -150), (-44 - 60 * math.sin(.25 + a1), -155)], True))
    P(poly(F, [(34, -245), (24, -240), (30 + 60 * math.sin(.25 - a1), -150), (44 + 60 * math.sin(.25 - a1), -155)], True))
    # голова
    P(circle(F, 0, -292, 34))
    if kind in ("man", "old_man"):
        P(poly(F, [(-50, -312), (50, -312), (30, -322), (24, -348), (-24, -348), (-30, -322)], True))
    if kind in ("woman", "old", "maid"):
        P(poly(F, [(-38, -300), (-30, -334), (0, -344), (30, -334), (38, -300), (30, -280), (-30, -280)], True))
    if kind == "soldier":
        P(blob(F, 0, -318, 46, 22))
    if carry == "case":
        P(rect(F, 46, -150, 56, 40))
    if gun:
        F.fill(ink, poly(F, [(40, -170), (150, -250), (156, -242), (48, -160)], True))
    if lantern > 0:
        lx, ly = 62, -150
        F.fill("red", circle(F, lx, ly, 90), tone=0.14 * lantern)
        F.fill("red", circle(F, lx, ly, 40), tone=0.45 * lantern)
        F.paint("red", circle(F, lx, ly, 14))
        F.stroke(ink, line(F, lx, ly - 14, lx, ly - 30), 3)
    F.pop()


# ------------------------------------------------------------ графика «дела»
def stamp(F, txt, x, y, size=80, rot=-0.08, p=1.0, ink="red", box=True, font=None):
    if p <= 0:
        return
    s = lerp(1.7, 1.0, eback(p))
    F.push(); F.translate(x, y); F.rotate(rot); F.scale(s)
    w = text_extent(txt, size, True, font) + size * 0.7
    hh = size * 1.35
    if box:
        F.knock(rect(F, -w / 2, -hh / 2, w, hh, amp=1.5))
        F.fill("grey", rect(F, -w / 2, -hh / 2, w, hh, amp=1.5), tone=0.06)
        F.stroke(ink, rect(F, -w / 2, -hh / 2, w, hh, amp=1.5), size * 0.09)
        F.stroke(ink, rect(F, -w / 2 + size * .16, -hh / 2 + size * .16, w - size * .32, hh - size * .32, amp=1.5),
                 size * 0.035)
    F.fill(ink, textpath(F, txt, 0, size * 0.36, size, True, "center", font=font))
    F.pop()


def card(F, x, y, w, hh, rot=0.0, shadow=True, ink="navy", fill_tone=None, pin=False):
    F.push(); F.translate(x, y); F.rotate(rot)
    if shadow:
        F.fill("navy", rect(F, -w / 2 + 12, -hh / 2 + 14, w, hh), tone=0.45)
    p = rect(F, -w / 2, -hh / 2, w, hh)
    F.knock(p)
    if fill_tone:
        F.fill("grey", p, tone=fill_tone)
    F.stroke(ink, p, 4)
    if pin:
        F.paint("red", circle(F, 0, -hh / 2 + 18, 12))
    F.pop()


def typed(F, lines_, x, y, size=40, prog=1.0, ink="navy", font=MONO, lh=1.35, bold=True, align="left", knock=False):
    total = sum(len(s) for s in lines_)
    left = int(total * clamp(prog) + 0.5)
    for i, s in enumerate(lines_):
        if left <= 0:
            break
        part = s[:left]
        left -= len(s)
        if part.strip():
            tp = textpath(F, part, x, y + i * size * lh, size, bold, align, font=font)
            F.knock(tp) if knock else F.fill(ink, tp)


def label(F, txt, x, y, size=42, ink="red", p=1.0, align="left", sub=None):
    """плашка-подпись: цветной блок с вывороткой текста"""
    if p <= 0:
        return
    w = text_extent(txt, size, True) + size * 0.9
    hh = size * 1.5
    ox = {"left": 0, "center": -w / 2, "right": -w}[align]
    ww = w * eout(p)
    F.paint(ink, rect(F, x + ox, y - hh / 2, ww, hh))
    if p > 0.6:
        F.knock(textpath(F, txt, x + ox + size * 0.45, y + size * 0.36, size, True))
    if sub and p > 0.8:
        F.fill("navy", textpath(F, sub, x + ox + size * 0.45, y + hh / 2 + size * 0.95, size * 0.72, False))


def big_text(F, txt, x, y, size, ink="navy", align="center", knock=False, bold=True, font=None):
    p = textpath(F, txt, x, y, size, bold, align, font=font)
    if knock:
        F.knock(p)
    else:
        F.fill(ink, p)


def mattock(F, x, y, sc=1.0, rot=0.0, ink="red", outline=True):
    F.push(); F.translate(x, y); F.rotate(rot); F.scale(sc)
    handle = rect(F, -8, -10, 16, 300)
    head = poly(F, [(-150, -30), (0, -46), (130, -30), (140, -16), (0, -4), (-140, -10)], True)
    if outline:
        F.stroke(ink, handle, 5); F.stroke(ink, head, 5)
    else:
        F.fill(ink, handle); F.fill(ink, head)
    F.pop()


def cross(F, x, y, sc=1.0, ink="navy", tone=None):
    F.push(); F.translate(x, y); F.scale(sc)
    F.fill(ink, rect(F, -9, -150, 18, 150), tone=tone)
    F.fill(ink, rect(F, -50, -120, 100, 16), tone=tone)
    F.fill(ink, poly(F, [(-30, -150), (0, -175), (30, -150)], True), tone=tone)
    F.pop()


def red_wipe(F, p):
    """смена сцены листом красной краски"""
    if p <= 0 or p >= 1:
        return
    x = lerp(-W * 1.2, W * 1.2, ease(p))
    F.fill("red", poly(F, [(x, -50), (x + W, -50), (x + W - 200, H + 50), (x - 200, H + 50)], True, amp=3))
