# -*- coding: utf-8 -*-
"""Сцены первой серии Akte 41: Hinterkaifeck. Каждая сцена: fn(F, t, T)."""
import math
from riso import W, H, MONO, h, clamp, ease, eout, eback, lerp, seg, blob, poly, rect, line, textpath, circle
from props import (night_sky, day_sky, snow_ground, forest, snowfall, farm, footprints, figure, stamp,
                   card, typed, label, big_text, mattock, cross, red_wipe)

TRACK = [(330, 760), (520, 800), (760, 830), (980, 850), (1180, 850), (1330, 830), (1420, 812)]


def cam(F, t, T, z0=1.0, z1=1.07, cx=W / 2, cy=H / 2, dx=0, dy=0):
    k = ease(t / max(T, 0.1))
    z = lerp(z0, z1, k)
    F.translate(cx + dx * k, cy + dy * k)
    F.scale(z)
    F.translate(-cx, -cy)


def caption(F, txt, t, at=0.3, x=90, y=100, size=40):
    typed(F, [txt], x, y, size, prog=seg(t, at, at + len(txt) * 0.045), ink="navy", font=MONO)


def landscape(F, t, farm_kw=None, farm_x=1560, farm_y=820, farm_sc=0.75, snow=True, seed=0):
    night_sky(F, seed=seed)
    forest(F, -60, 700, 735, 260, seed=1)
    forest(F, 900, 1300, 715, 140, seed=2, tone=0.75)
    snow_ground(F, 720, seed=seed)
    farm(F, farm_x, farm_y, farm_sc, t=t, **(farm_kw or {}))
    if snow:
        snowfall(F, t, n=60)


# ------------------------------------------------------------ сцены
def s_tracks(F, t, T):
    F.push(); cam(F, t, T, 1.0, 1.08, dx=-60)
    landscape(F, t, farm_kw=dict(lit=1.0, smoke=0.5))
    footprints(F, TRACK, seg(t, 0.6, T * 0.85), size=1.2)
    F.pop()
    label(F, "OBERBAYERN · MÄRZ 1922", 90, 110, 38, "red", seg(t, 0.2, 0.9))


def s_tracks_back(F, t, T):
    F.push(); cam(F, t, T, 1.08, 1.16, dx=-80)
    landscape(F, t, farm_kw=dict(lit=1.0, smoke=0.5))
    footprints(F, TRACK, 1.0, size=1.2)
    back = [(p[0], p[1] - 70) for p in reversed(TRACK)]
    pr = seg(t, 0.6, T * 0.6)
    if pr > 0:
        n = max(2, int(len(back) * pr))
        F.stroke("red", poly(F, back[:n], False, amp=1.2), 6, dash=[18, 14])
    F.pop()
    stamp(F, "KEINE SPUR ZURÜCK", W / 2, 300, 74, -0.06, seg(t, T * 0.55, T * 0.55 + 0.35))


def s_farm_night(F, t, T):
    F.push(); cam(F, t, T, 1.15, 1.32, cx=1100, cy=640)
    landscape(F, t, farm_kw=dict(lit=1.0 - 0.6 * seg(t, 0.8, 2.5), smoke=seg(t, T * 0.45, T * 0.6)),
              farm_x=1100, farm_y=820, farm_sc=1.0)
    F.pop()
    p6 = seg(t, 1.0, 1.4)
    if p6 > 0:
        stamp(F, "6", 330, 330, 210, -0.05, p6)
        label(F, "TOTE", 330, 530, 48, "red", seg(t, 1.4, 1.8), "center")
    typed(F, ["Jemand bleibt.", "Tagelang."], 1250, 200, 58, prog=seg(t, T * 0.45, T * 0.75), knock=True)


def s_title(F, t, T):
    F.fill("navy", rect(F, -20, -20, W + 40, H + 40, amp=0))
    F.fill("grey", rect(F, -20, -20, W + 40, H + 40, amp=0), tone=0.3)
    snowfall(F, t, n=40)
    stamp(F, "AKTE 41", W / 2, 330, 150, -0.05, seg(t, 0.2, 0.55))
    if t > 0.9:
        big_text(F, "HINTERKAIFECK", W / 2, 640, 150, knock=True)
    typed(F, ["1922 · SECHS TOTE · UNGELÖST"], W / 2, 770, 46, prog=seg(t, 1.6, 3.0), knock=True, align="center")
    if t > T * 0.55:
        items = ["AKTEN", "GERÜCHTE", "VERDÄCHTIGE"]
        for i, s in enumerate(items):
            pp = seg(t, T * 0.55 + i * 0.9, T * 0.55 + i * 0.9 + 0.4)
            if pp > 0:
                label(F, s, 420 + i * 420, 920, 40, "red" if i == 2 else "grey", pp, "center")


BAVARIA = [(520, 180), (700, 140), (900, 170), (1060, 120), (1250, 210), (1320, 330), (1440, 420), (1400, 560),
           (1480, 700), (1420, 820), (1300, 860), (1160, 900), (980, 880), (820, 920), (650, 880), (560, 760),
           (470, 640), (430, 480), (480, 330)]


def s_map(F, t, T):
    day_sky(F, 0.10)
    F.push()
    z = lerp(1.0, 2.6, ease(seg(t, T * 0.55, T * 0.85)))
    cx, cy = 980, 560
    F.translate(cx, cy); F.scale(z); F.translate(-cx, -cy)
    F.fill("grey", poly(F, BAVARIA, True, amp=1.5, smooth_=True), tone=0.35)
    F.stroke("navy", poly(F, BAVARIA, True, amp=1.5, smooth_=True), 5 / z)
    pts = {"München": (1010, 760), "Ingolstadt": (990, 470), "Schrobenhausen": (905, 590)}
    for i, (n, (x, y)) in enumerate(pts.items()):
        pp = seg(t, 0.4 + i * 0.6, 0.8 + i * 0.6)
        if pp > 0:
            F.paint("navy", circle(F, x, y, 11 / z))
            F.fill("navy", textpath(F, n, x + 22 / z, y + 12 / z, 36 / z))
    hx, hy = 975, 545
    pp = seg(t, 2.2, 2.6)
    if pp > 0:
        F.stroke("red", line(F, hx, hy, 1010, 760), 4 / z, dash=[12 / z, 9 / z])
        F.paint("red", circle(F, hx, hy, 16 / z * eback(pp)))
        F.fill("red", textpath(F, "Hinterkaifeck", hx - 250 / z, hy - 30 / z, 40 / z))
        F.fill("navy", textpath(F, "≈ 70 km", 1010 + 20 / z, 660, 32 / z))
    zz = seg(t, T * 0.7, T * 0.85)
    if zz > 0:
        forest(F, hx + 15, hx + 60, hy - 4, 22, seed=5, n=6)
        F.paint("navy", circle(F, hx + 75, hy - 14, 6))
        F.fill("navy", textpath(F, "Gröbern", hx + 84, hy - 8, 14))
        F.fill("red", textpath(F, "Wald · ≈ 1 km", hx + 10, hy + 26, 12))
    F.pop()
    label(F, "EINÖDHOF", 90, 110, 38, "red", seg(t, T * 0.6, T * 0.7))


FAMILY = [("man", "Andreas Gruber", "63"), ("old", "Cäzilia Gruber", "72"), ("woman", "Viktoria Gabriel", "35"),
          ("girl", "Cäzilia", "7"), ("boy", "Josef", "2"), ("maid", "Maria Baumgartner", "44")]
XS = [260, 560, 860, 1120, 1330, 1620]


def family_row(F, t, upto, show_t, karl=0.0, maid_slot=0.0, maid=False, dim=None):
    day_sky(F, 0.16)
    F.fill("navy", rect(F, -20, 840, W + 40, 260, amp=0), tone=0.25)
    for i, (kind, name, age) in enumerate(FAMILY):
        if i >= upto:
            break
        if i == 5 and not maid:
            continue
        p = seg(t, show_t[i], show_t[i] + 0.4)
        if p <= 0:
            continue
        y = 840 + 40 * (1 - eout(p))
        tone = 0.35 if (dim and i in dim) else None
        figure(F, XS[i], y, 1.15, kind, tone=tone)
        F.fill("navy", textpath(F, name, XS[i], 920, 34, True, "center"))
        F.fill("red", textpath(F, age, XS[i], 975, 44, True, "center"))
    if karl > 0:
        figure(F, 1180, 840, 1.15, "soldier", outline=True, ink="grey")
        F.fill("grey", textpath(F, "Karl Gabriel", 1180, 920, 32, True, "center"))
        stamp(F, "GEFALLEN 1914?", 1180, 300, 46, -0.1, karl, ink="red")
    if maid_slot > 0:
        figure(F, XS[5], 840, 1.15, "maid", outline=True, ink="red")
        F.fill("red", textpath(F, "Magd: ?", XS[5], 920, 36, True, "center"))


def s_family(F, t, T):
    F.push(); cam(F, t, T, 1.0, 1.04)
    show = [0.3, T * 0.25, T * 0.45, 99, 99, 99]
    family_row(F, t, 3, show, karl=seg(t, T * 0.72, T * 0.8))
    F.pop()


def s_family_kids(F, t, T):
    F.push(); cam(F, t, T, 1.04, 1.08)
    family_row(F, t, 5, [-1, -1, -1, 0.4, 2.2, 99], maid_slot=seg(t, T * 0.55, T * 0.65))
    F.pop()


def s_maid_leaves(F, t, T):
    F.push(); cam(F, t, T, 1.0, 1.06)
    night_sky(F, tone=0.6)
    forest(F, -60, 1920, 700, 160, seed=4, tone=0.7)
    snow_ground(F, 700, seed=2)
    attic = 0.5 + 0.5 * math.sin(t * 7) if t > T * 0.5 else 0.0
    farm(F, 520, 820, 0.8, lit=0.3 + 0.6 * attic, t=t)
    x = lerp(900, 1500, seg(t, 0.2, T))
    figure(F, x, 900, 0.9, "maid", phase=t * 6, carry="case")
    F.pop()
    if t > 1.0:
        card(F, 1380, 330, 420, 150, 0.04)
        typed(F, ["„Es spukt.“"], 1380, 350, 62, prog=seg(t, 1.2, 2.0), align="center", font=MONO, ink="red")
    label(F, "HERBST 1921", 90, 110, 38, "navy", seg(t, 0.2, 0.8))


def s_family_secret(F, t, T):
    day_sky(F, 0.2)
    F.push(); cam(F, t, T, 1.0, 1.05)
    figure(F, 380, 900, 1.3, "man", tone=0.85)
    figure(F, 600, 900, 1.3, "woman", tone=0.85)
    card(F, 1250, 520, 760, 620, -0.03, fill_tone=0.05)
    typed(F, ["LANDGERICHT 1915", "", "Andreas Gruber", "Viktoria Gabriel", "", "wegen Blutschande", "verurteilt"],
          930, 330, 44, prog=seg(t, 0.8, T * 0.5))
    stamp(F, "VERURTEILT", 1300, 700, 70, -0.12, seg(t, T * 0.48, T * 0.55))
    F.pop()
    if t > T * 0.78:
        label(F, "Wer ist der Vater von Josef?", W / 2, 1000, 44, "red", seg(t, T * 0.78, T * 0.86), "center")


def s_attic(F, t, T):
    F.fill("grey", rect(F, -20, -20, W + 40, H + 40, amp=0), tone=0.55)
    F.fill("navy", rect(F, -20, -20, W + 40, H + 40, amp=0), tone=0.3)
    F.push(); cam(F, t, T, 1.0, 1.1)
    # стропила
    for i in range(7):
        x = 160 + i * 270
        F.fill("grey", poly(F, [(x, 1080), (x + 30, 1080), (W / 2 + (x - W / 2) * 0.1 + 15, 120), (W / 2 + (x - W / 2) * 0.1, 120)], True), tone=0.5)
    F.fill("grey", rect(F, 0, 840, W, 30), tone=0.6)
    # шаги на балке
    for k in range(8):
        p = seg(t, 0.4 + k * 0.35, 0.6 + k * 0.35)
        if p > 0 and k * 0.35 + 1.5 > t - 0.4:
            F.fill("red", blob(F, 300 + k * 170, 820 + (15 if k % 2 else -10), 30, 13, n=10), tone=0.8 * p)
    # Андреас с лампой и ружьём
    lx = lerp(-100, 700, ease(seg(t, T * 0.45, T * 0.85)))
    if lx > -100:
        figure(F, lx, 1080, 1.4, "man", lantern=1.0, gun=True, phase=t * 4)
    F.pop()
    if t > T * 0.85:
        big_text(F, "NIEMAND.", W / 2, 400, 110, ink="red")


def s_newspaper(F, t, T):
    F.fill("grey", rect(F, -20, -20, W + 40, H + 40, amp=0), tone=0.45)
    for i in range(9):
        F.stroke("navy", line(F, -20, 120 * i + 40, W + 20, 120 * i + 60), 3, tone=0.4)
    F.push(); cam(F, t, T, 1.0, 1.1, cx=900)
    card(F, 900, 560, 860, 640, -0.06, fill_tone=0.04)
    F.push(); F.translate(900, 560); F.rotate(-0.06)
    F.fill("navy", textpath(F, "Münchner Neueste", 0, -210, 64, True, "center"))
    F.fill("navy", rect(F, -380, -175, 760, 6))
    for c in range(3):
        for r in range(11):
            ww = 220 - 50 * h(c, r)
            F.fill("grey", rect(F, -370 + c * 255, -140 + r * 36, ww, 14), tone=0.75)
    F.pop()
    F.pop()
    pr = seg(t, T * 0.4, T * 0.6)
    if pr > 0:
        F.stroke("red", blob(F, 900, 560, 470 * pr, 360 * pr, n=18, wob=0.15), 9)
        label(F, "Wer hat sie gebracht?", 1420, 960, 44, "red", seg(t, T * 0.55, T * 0.65), "center")


def s_key(F, t, T):
    F.fill("grey", rect(F, -20, -20, W + 40, H + 40, amp=0), tone=0.3)
    F.push(); cam(F, t, T, 1.0, 1.06)
    F.paint("grey", rect(F, 260, 200, 620, 360), tone=0.6, outline="navy", ow=6)
    for i in range(3):
        x = 380 + i * 190
        F.paint("navy", circle(F, x, 260, 12))
        if i == 1:
            F.stroke("red", circle(F, x, 330, 34), 5, dash=[10, 8])
            F.stroke("red", rect(F, x - 8, 364, 16, 120), 5, dash=[10, 8])
        else:
            F.stroke("navy", circle(F, x, 330, 34), 9)
            F.fill("navy", rect(F, x - 8, 364, 16, 120))
            F.fill("navy", rect(F, x, 450, 28, 12))
    stamp(F, "WEG", 570, 640, 70, -0.08, seg(t, 0.8, 1.2))
    # замок с царапинами
    pl = seg(t, T * 0.45, T * 0.55)
    if pl > 0:
        F.paint("grey", rect(F, 1180, 380, 420, 380), tone=0.7, outline="navy", ow=6)
        F.stroke("navy", blob(F, 1390, 360, 110, 120, n=16), 22)
        F.knock(circle(F, 1390, 560, 30))
        F.knock(rect(F, 1380, 560, 20, 90))
        for k in range(6):
            pk = seg(t, T * 0.55 + k * 0.15, T * 0.55 + k * 0.15 + 0.12)
            if pk > 0:
                x0 = 1250 + 60 * k * 0.9
                F.stroke("red", line(F, x0, 450 + 30 * h(k), x0 + 70 * pk, 520 + 60 * h(k, 2) * pk), 5)
        label(F, "MASCHINENHAUS", 1390, 830, 36, "navy", seg(t, T * 0.6, T * 0.7), "center")
    F.pop()


def s_neighbors(F, t, T):
    F.push(); cam(F, t, T, 1.0, 1.05)
    day_sky(F, 0.25)
    forest(F, -60, 1920, 640, 180, seed=7, tone=0.6)
    snow_ground(F, 650, seed=4)
    figure(F, 640, 920, 1.3, "man", facing=1)
    figure(F, 1160, 920, 1.3, "man", facing=-1, tone=0.8)
    F.pop()
    if t > 0.5:
        card(F, 1330, 300, 640, 150, 0.03)
        typed(F, ["„Wir suchen den Wald ab.“"], 1330, 315, 40, prog=seg(t, 0.6, 2.2), align="center")
    if t > T * 0.35:
        card(F, 560, 470, 600, 150, -0.03)
        typed(F, ["„Nein. Ich hab ein Gewehr.“"], 560, 485, 38, prog=seg(t, T * 0.35, T * 0.6), align="center", ink="red")
    stamp(F, "KEINE POLIZEI", W / 2, 150, 70, -0.05, seg(t, T * 0.78, T * 0.86))


def s_calendar(F, t, T):
    F.fill("navy", rect(F, -20, -20, W + 40, H + 40, amp=0), tone=0.85)
    F.push(); cam(F, t, T, 1.0, 1.08)
    card(F, W / 2, 540, 620, 720, 0.02, shadow=True)
    F.paint("red", rect(F, W / 2 - 310, 180, 620, 130))
    F.knock(textpath(F, "FREITAG", W / 2, 270, 66, True, "center"))
    p = eback(seg(t, 0.2, 0.7))
    F.fill("navy", textpath(F, "31", W / 2, 640, 300 * max(.01, p), True, "center"))
    F.fill("navy", textpath(F, "MÄRZ 1922", W / 2, 790, 66, True, "center"))
    F.pop()


def s_maid_arrives(F, t, T):
    F.push(); cam(F, t, T, 1.0, 1.08, dx=40)
    night_sky(F, tone=0.45, moon=None)
    F.fill("red", rect(F, -20, 520, W + 40, 200, amp=0), tone=0.18)
    forest(F, -60, 900, 715, 200, seed=8)
    snow_ground(F, 720, seed=5)
    farm(F, 1480, 830, 0.8, lit=0.9, smoke=0.4, t=t)
    x = lerp(150, 1050, ease(seg(t, 0, T * 0.5)))
    figure(F, x, 920, 0.95, "maid", phase=t * 6 if t < T * 0.5 else None, carry="case")
    sis_back = seg(t, T * 0.6, T)
    sx = lerp(x - 120, -200, sis_back) if t > T * 0.6 else x - 120
    figure(F, sx, 925, 0.95, "woman", phase=t * 6 if (t < T * 0.5 or t > T * 0.6) else None,
           facing=-1 if t > T * 0.6 else 1, tone=0.7)
    F.pop()
    label(F, "Maria Baumgartner, 44", 90, 110, 40, "red", seg(t, 1.0, 1.6), sub="die neue Magd")
    if t > T * 0.62:
        label(F, "die Schwester: letzte Zeugin", 1830, 1000, 34, "navy", seg(t, T * 0.62, T * 0.7), "right")


def s_barn(F, t, T):
    F.fill("navy", rect(F, -20, -20, W + 40, H + 40, amp=0), tone=0.95)
    F.push(); cam(F, t, T, 1.0, 1.12, cy=600)
    # тёмный сарай, щель света
    F.fill("grey", rect(F, 460, 200, 1000, 760), tone=0.6)
    for i in range(12):
        F.stroke("navy", line(F, 480 + i * 82, 210, 480 + i * 82, 950), 5)
    gap = 18 + 10 * math.sin(t * 2)
    F.knock(rect(F, 955, 300, gap, 650))
    F.fill("red", rect(F, 955, 300, gap, 650), tone=0.35)
    F.fill("red", blob(F, 965, 960, 200, 30), tone=0.25)
    F.pop()
    names = ["Andreas", "Cäzilia", "Viktoria", "die kleine Cäzilia"]
    for i, n in enumerate(names):
        p = seg(t, T * 0.45 + i * 1.2, T * 0.45 + i * 1.2 + 0.4)
        if p > 0:
            label(F, n, 120, 260 + i * 120, 40, "grey", p)
    label(F, "NACHT AUF DEN 1. APRIL", 1800, 110, 36, "red", seg(t, 0.3, 0.9), "right")


def s_house_dark(F, t, T):
    F.push(); cam(F, t, T, 1.2, 1.35, cx=1000, cy=650)
    landscape(F, t, farm_kw=dict(lit=1.0, windows_off=int(3 * seg(t, 0.5, T * 0.4))), farm_x=1000, farm_y=830, farm_sc=1.1, snow=True)
    F.pop()
    pc = seg(t, T * 0.62, T * 0.72)
    if pc > 0:
        card(F, 1500, 520, 560, 520, 0.05, fill_tone=0.05)
        mattock(F, 1500, 420, 1.2 * eout(pc), 0.5)
        F.fill("navy", textpath(F, "Reuthaue", 1500, 730, 52, True, "center", font=MONO))
    stamp(F, "6", 320, 300, 200, -0.05, seg(t, T * 0.45, T * 0.52), ink="red")


def s_quiet(F, t, T):
    landscape(F, t, farm_kw=dict(lit=0.0), farm_x=W / 2 + 200, farm_y=830, farm_sc=0.9)
    F.fill("navy", rect(F, -20, -20, W + 40, H + 40, amp=0), tone=0.25)


def s_days(F, t, T):
    F.fill("navy", rect(F, -20, -20, W + 40, H + 40, amp=0), tone=0.8)
    days = [("SA 1.4.", "Schule: Cäzilia fehlt"), ("SO 2.4.", "keiner in der Messe"), ("MO 3.4.", "Post bleibt liegen")]
    for i, (d, s) in enumerate(days):
        p = seg(t, 0.3 + i * T * 0.22, 0.7 + i * T * 0.22)
        if p <= 0:
            continue
        x = 380 + i * 580
        y = 500 + 60 * (1 - eout(p))
        card(F, x, y, 460, 520, (-0.04, 0.02, 0.05)[i])
        F.paint("red", rect(F, x - 230, y - 260, 460, 110))
        F.knock(textpath(F, d, x, y - 185, 60, True, "center"))
        # иконки
        if i == 0:
            F.stroke("navy", rect(F, x - 120, y - 40, 240, 30), 6)
            F.stroke("navy", line(F, x - 100, y - 10, x - 100, y + 90), 6)
            F.stroke("navy", line(F, x + 100, y - 10, x + 100, y + 90), 6)
            F.stroke("red", circle(F, x, y - 90, 30), 5, dash=[8, 8])
        elif i == 1:
            F.stroke("navy", poly(F, [(x - 90, y + 90), (x - 90, y - 30), (x, y - 110), (x + 90, y - 30), (x + 90, y + 90)], False), 6)
            F.stroke("navy", line(F, x, y - 110, x, y - 170), 6)
            F.stroke("navy", line(F, x - 25, y - 145, x + 25, y - 145), 6)
        else:
            F.stroke("navy", rect(F, x - 110, y - 60, 220, 140), 6)
            F.stroke("navy", poly(F, [(x - 110, y - 60), (x, y + 20), (x + 110, y - 60)], False), 6)
        F.fill("navy", textpath(F, s, x, y + 180, 34, True, "center"))
    if t > T * 0.8:
        label(F, "„Die Grubers waren halt komisch.“", W / 2, 960, 40, "grey", seg(t, T * 0.8, T * 0.88), "center")


def s_chimney(F, t, T):
    F.push(); cam(F, t, T, 1.0, 1.12, cx=700, cy=500)
    landscape(F, t, farm_kw=dict(lit=0.25, smoke=1.0), farm_x=700, farm_y=840, farm_sc=1.1)
    F.pop()
    checks = ["Rauch aus dem Kamin", "Vieh gefüttert", "Brot angeschnitten", "Fleisch fehlt"]
    card(F, 1460, 520, 640, 520, 0.03)
    for i, s in enumerate(checks):
        p = seg(t, 0.8 + i * T * 0.17, 1.2 + i * T * 0.17)
        if p > 0:
            y = 360 + i * 105
            F.stroke("red", poly(F, [(1180, y - 10), (1200, y + 12), (1240, y - 30)], False), 8)
            typed(F, [s], 1270, y + 10, 36, prog=p * 2)
    if t > T * 0.85:
        stamp(F, "JEMAND HAT HIER GELEBT", W / 2, 140, 60, -0.04, seg(t, T * 0.85, T * 0.9))


def s_mechanic(F, t, T):
    F.push(); cam(F, t, T, 1.0, 1.08, cx=900)
    day_sky(F, 0.22)
    forest(F, -60, 1920, 620, 150, seed=9, tone=0.55)
    snow_ground(F, 640, seed=6, shade=0.08)
    farm(F, 600, 860, 1.0, lit=0.0, t=t, dark=False)
    # машина и шестерня
    gx, gy = 1250, 720
    F.paint("grey", rect(F, 1100, 680, 320, 220), tone=0.65, outline="navy", ow=6)
    F.push(); F.translate(gx, gy); F.rotate(t * 2.0)
    teeth = []
    for k in range(24):
        r = 90 if k % 2 else 70
        a = k * math.pi / 12
        teeth.append((r * math.cos(a), r * math.sin(a)))
    F.paint("navy", poly(F, teeth, True))
    F.knock(circle(F, 0, 0, 22))
    F.pop()
    figure(F, 1520, 920, 1.2, "man", facing=-1, phase=None)
    if int(t * 2) % 3 == 0 and t > 1.0:
        F.fill("red", textpath(F, "WAU!", 820, 640, 54, True))
    # глаза в тёмном окне
    if t > T * 0.75:
        e = 1.0 if int(t * 3) % 5 else 0.0
        F.paint("navy", rect(F, 330, 690, 60, 70))
        if e:
            F.knock(circle(F, 349, 720, 5)); F.knock(circle(F, 371, 720, 5))
    F.pop()
    label(F, "DIENSTAG, 4. APRIL · Albert Hofner", 90, 110, 38, "red", seg(t, 0.3, 1.0))


def s_discovery(F, t, T):
    F.push(); cam(F, t, T, 1.0, 1.15, cx=1300, cy=700)
    night_sky(F, tone=0.55, moon=None)
    F.fill("red", rect(F, -20, 450, W + 40, 260, amp=0), tone=0.12)
    forest(F, -60, 800, 715, 200, seed=10)
    snow_ground(F, 720, seed=7)
    farm(F, 1450, 840, 1.0, lit=0.0, t=t, door=seg(t, T * 0.62, T * 0.75))
    for i in range(3):
        x = lerp(200 + i * 130, 1180 + i * 120, ease(seg(t, 0.2, T * 0.6)))
        figure(F, x, 910 + i * 8, 0.95, "man", phase=t * 6 + i if t < T * 0.6 else None, lantern=1.0 if i == 0 else 0.0)
    F.pop()
    stamp(F, "4. APRIL 1922", 520, 220, 74, -0.07, seg(t, T * 0.75, T * 0.82))
    label(F, "Lorenz Schlittenbauer, Nachbar", 90, 110, 38, "navy", seg(t, 0.4, 1.0))


def s_money(F, t, T):
    F.fill("grey", rect(F, -20, -20, W + 40, H + 40, amp=0), tone=0.5)
    F.push(); cam(F, t, T, 1.0, 1.08)
    card(F, 760, 600, 900, 520, -0.03, fill_tone=0.1)
    for k in range(26):
        p = seg(t, 1.0 + k * 0.06, 1.3 + k * 0.06)
        if p > 0:
            x = 520 + 480 * h(k, 1) ; y = 520 + 180 * h(k, 2) - 20 * (1 - p)
            F.paint("grey", circle(F, x, y, 38), tone=0.35, outline="red", ow=5)
            F.stroke("red", circle(F, x, y, 22), 3)
    for k in range(3):
        F.paint("grey", rect(F, 380 + k * 40, 380 - k * 18, 300, 150), tone=0.5, outline="navy", ow=4)
    F.pop()
    label(F, "Polizei aus München · 5. April", 90, 110, 38, "navy", seg(t, 0.2, 0.8))
    stamp(F, "RAUB? NEIN.", 1450, 520, 90, -0.1, seg(t, T * 0.7, T * 0.78))


def s_crime_scene(F, t, T):
    F.push(); cam(F, t, T, 1.0, 1.06)
    day_sky(F, 0.2)
    forest(F, -60, 1920, 600, 140, seed=11, tone=0.5)
    snow_ground(F, 620, seed=8, shade=0.1)
    farm(F, 960, 800, 0.85, lit=0.0, t=t)
    n = int(18 * seg(t, T * 0.35, T * 0.8))
    for i in range(n):
        x = 160 + 1600 * h(i, 3.1)
        y = 870 + 170 * h(i, 5.2)
        figure(F, x, y, 0.45 + 0.2 * (y - 870) / 170, "man" if i % 3 else "woman", tone=0.85,
               phase=t * 4 + i, facing=1 if i % 2 else -1)
    for i in range(14):
        a = (TRACK[0][0] + 1500 * h(i, 8)), 860 + 180 * h(i, 9)
        footprints(F, [a, (a[0] + 200 * (h(i, 4) - .5), a[1] + 60 * (h(i, 6) - .5))], seg(t, T * 0.4, T * 0.9), 0.9, 0.6)
    F.pop()
    stamp(F, "SPUREN: ZERSTÖRT", W / 2, 230, 74, -0.05, seg(t, T * 0.8, T * 0.88))


def s_munich(F, t, T):
    F.fill("navy", rect(F, -20, -20, W + 40, H + 40, amp=0), tone=0.75)
    F.push(); cam(F, t, T, 1.0, 1.08)
    for i in range(6):
        p = seg(t, 0.4 + i * 0.25, 0.8 + i * 0.25)
        if p > 0:
            x = 330 + i * 250
            y = 600
            F.paint("grey", rect(F, x - 100, y - 90, 200, 180), tone=0.4, outline="navy", ow=5)
            F.stroke("navy", line(F, x - 100, y - 20, x + 100, y - 20), 4)
            F.fill("red", textpath(F, "MÜNCHEN", x, y + 50, 30, True, "center", font=MONO))
    F.pop()
    if t > T * 0.35:
        label(F, "Hoffnung: Hellseher", W / 2, 260, 46, "grey", seg(t, T * 0.35, T * 0.45), "center")
    stamp(F, "VERSCHOLLEN SEIT DEM KRIEG", W / 2, 900, 58, -0.04, seg(t, T * 0.72, T * 0.8))


BOARD = [("Lorenz", "Schlittenbauer", 430, 330), ("Karl", "Gabriel", 1490, 330), ("Adolf & Anton", "Gump", 960, 830)]


def board_bg(F, t):
    F.fill("grey", rect(F, -20, -20, W + 40, H + 40, amp=0), tone=0.55)
    F.fill("red", rect(F, -20, -20, W + 40, H + 40, amp=0), tone=0.08)
    for i in range(40):
        F.fill("navy", circle(F, h(i, 1) * W, h(i, 2) * H, 3), tone=0.5)


def board(F, t, T, focus=None, reveal=1.0):
    board_bg(F, t)
    cx, cy = 960, 500
    for i, (a, b, x, y) in enumerate(BOARD):
        p = seg(t, 0.5 + i * 0.6, 0.9 + i * 0.6) if reveal < 1 else 1.0
        if p > 0:
            F.stroke("red", line(F, cx, cy, lerp(cx, x, eout(p)), lerp(cy, y, eout(p))), 5)
    card(F, cx, cy, 420, 150, 0.02, pin=True, fill_tone=0.0)
    F.fill("navy", textpath(F, "HINTERKAIFECK", cx, cy + 18, 48, True, "center"))
    for i, (a, b, x, y) in enumerate(BOARD):
        p = seg(t, 0.5 + i * 0.6, 0.9 + i * 0.6) if reveal < 1 else 1.0
        if p <= 0:
            continue
        dim = focus is not None and focus != i
        card(F, x, y, 360, 300, (-0.05, 0.04, -0.02)[i], pin=True, fill_tone=0.3 if dim else 0.0)
        figure(F, x, y + 70, 0.42, "soldier" if i == 1 else "man", tone=0.5 if dim else None)
        F.fill("navy", textpath(F, a, x, y + 105, 28, False, "center"))
        F.fill("navy", textpath(F, b, x, y + 140, 34, True, "center"))


def s_board(F, t, T):
    F.push(); cam(F, t, T, 1.0, 1.04)
    board(F, t, T, reveal=0.0)
    F.pop()
    label(F, "> 100 BEFRAGTE", 90, 110, 40, "red", seg(t, 0.2, 0.8))
    stamp(F, "NICHTS BEWIESEN", 1500, 980, 50, -0.05, seg(t, T * 0.75, T * 0.82), ink="navy")


def zoom_card(F, t, T, i, notes, stamp_txt=None, stamp_at=0.75):
    a, b, x, y = BOARD[i]
    F.push()
    z = lerp(1.0, 1.9, ease(seg(t, 0, 1.2)))
    F.translate(W * 0.33, H / 2); F.scale(z); F.translate(-x, -y)
    board(F, 99, T, focus=i)
    F.pop()
    card(F, 1400, 540, 760, 620, 0.02, fill_tone=0.0)
    lines_ = []
    for s in notes:
        lines_.append(s)
    typed(F, lines_, 1060, 330, 38, prog=seg(t, 1.2, T * 0.8), lh=1.45)
    if stamp_txt:
        stamp(F, stamp_txt, 1420, 900, 54, -0.07, seg(t, T * stamp_at, T * stamp_at + 0.08))


def s_suspect1(F, t, T):
    zoom_card(F, t, T, 0, ["SPUR 1: DER NACHBAR", "", "Witwer", "Beziehung mit Viktoria", "Vater von Josef?", "→ später bestritten",
                          "kennt das dunkle Haus", "geht direkt zu den Toten"])


def s_suspect1b(F, t, T):
    zoom_card(F, t, T, 0, ["SPUR 1: DER NACHBAR", "", "Klagen wegen Verleumdung:", "„Mörder“ genannt", "", "Ergebnis:"],
              "RECHT BEKOMMEN", 0.7)


def s_suspect2(F, t, T):
    zoom_card(F, t, T, 1, ["SPUR 2: DER EHEMANN", "", "gilt als gefallen, 1914", "Leiche nie gefunden", "",
                          "Jahre später:", "„in Russland gesehen“"], "NICHT BEWIESEN", 0.85)


def s_suspect3(F, t, T):
    zoom_card(F, t, T, 2, ["SPUR 3: DIE BRÜDER", "", "1950er: Schwester sagt,", "Adolf habe gestanden", "(Sterbebett)", "",
                          "Anton: fest-, dann", "freigelassen"], "HÖRENSAGEN", 0.85)


def s_weapon(F, t, T):
    day_sky(F, 0.3)
    snow_ground(F, 860, seed=9, shade=0.2)
    F.push(); cam(F, t, T, 1.0, 1.1)
    # разобранный дом: стены без крыши, доски летят
    F.paint("grey", rect(F, 360, 560, 1200, 300), tone=0.5, outline="navy", ow=6)
    for k in range(10):
        p = (t * 0.4 + k / 10) % 1.0
        x = 400 + k * 115
        y = 540 - 300 * p
        F.push(); F.translate(x, y); F.rotate(p * 3 + k)
        F.paint("navy", rect(F, -70, -10, 140, 20))
        F.pop()
    # пол и топор
    F.fill("navy", rect(F, 360, 700, 1200, 26), tone=0.8)
    pm = seg(t, T * 0.35, T * 0.5)
    if pm > 0:
        F.knock(rect(F, 760, 690, 520, 60))
        mattock(F, 1020, 660 + 30 * (1 - pm), 0.9, 1.5708, "red", outline=False)
    F.pop()
    stamp(F, "1923", 330, 200, 120, -0.06, seg(t, 0.3, 0.7))
    label(F, "versteckt im Zwischenboden", 1600, 980, 38, "red", seg(t, T * 0.5, T * 0.6), "right")


def s_students(F, t, T):
    F.fill("navy", rect(F, -20, -20, W + 40, H + 40, amp=0), tone=0.7)
    F.push(); cam(F, t, T, 1.0, 1.06)
    for k in range(5):
        F.paint("grey", rect(F, 520 + k * 8, 260 - k * 10, 880, 620), tone=0.15 + 0.05 * k, outline="navy", ow=4)
    card(F, 960, 560, 880, 620, 0.0, fill_tone=0.0)
    typed(F, ["POLIZEIHOCHSCHULE FÜRSTENFELDBRUCK", "Neubewertung, 2007", "", "Hauptverdächtiger:"], 560, 340, 36,
          prog=seg(t, 0.6, T * 0.6))
    pb = seg(t, T * 0.62, T * 0.72)
    if pb > 0:
        F.paint("navy", rect(F, 560, 590, 760 * eout(pb), 70))
    F.pop()
    stamp(F, "NAME NICHT VERÖFFENTLICHT", W / 2, 940, 50, -0.04, seg(t, T * 0.78, T * 0.85))


def s_memorial(F, t, T):
    F.fill("grey", rect(F, -20, -20, W + 40, H + 40, amp=0), tone=0.22)
    F.fill("red", rect(F, -20, 300, W + 40, 300, amp=0), tone=0.1)
    F.push(); cam(F, t, T, 1.0, 1.1, cx=1100, cy=700)
    forest(F, -60, 1920, 640, 150, seed=12, tone=0.5)
    snow_ground(F, 650, seed=10, shade=0.08)
    for r in range(9):
        F.stroke("grey", line(F, -20, 700 + r * 45, W + 20, 690 + r * 45), 3, tone=0.6)
    cross(F, 1100, 900, 2.0)
    F.pop()
    label(F, "Marterl bei Gröbern", 90, 110, 38, "navy", seg(t, 0.5, 1.2))
    if t > T * 0.6:
        label(F, "Friedhof Waidhofen", 90, 210, 38, "grey", seg(t, T * 0.6, T * 0.7))


def s_ending(F, t, T):
    F.push(); cam(F, t, T, 1.1, 1.25, cx=1100, cy=700)
    door = seg(t, T * 0.75, T * 0.82) * (1 - seg(t, T * 0.9, T * 0.97))
    landscape(F, t, farm_kw=dict(lit=0.8, smoke=0.8, door=door), farm_x=1100, farm_y=830, farm_sc=1.0)
    F.pop()
    if t > T * 0.3:
        typed(F, ["Vieh versorgt.", "Brot geschnitten.", "Feuer gemacht."], 90, 200, 54, prog=seg(t, T * 0.3, T * 0.7), knock=True)


def s_outro(F, t, T):
    F.fill("navy", rect(F, -20, -20, W + 40, H + 40, amp=0), tone=0.9)
    snowfall(F, t, n=40)
    big_text(F, "Wer war in diesen Tagen", W / 2, 330, 80, knock=True)
    big_text(F, "auf Hinterkaifeck?", W / 2, 440, 80, knock=True)
    label(F, "Deine Version → Kommentare", W / 2, 560, 40, "red", seg(t, 1.5, 2.2), "center")
    if t > T * 0.55:
        card(F, W / 2, 830, 780, 260, -0.02, fill_tone=0.0)
        F.fill("navy", textpath(F, "Das Phantom von Heilbronn", W / 2, 830, 52, True, "center"))
        stamp(F, "NÄCHSTE AKTE", W / 2 + 260, 720, 40, 0.08, seg(t, T * 0.6, T * 0.68))
    if t > T - 1.2:
        F.fill("navy", rect(F, -20, -20, W + 40, H + 40, amp=0), tone=clamp((t - (T - 1.2)) / 1.2))


SCENES = {k[2:]: v for k, v in globals().items() if k.startswith("s_") and callable(v)}
