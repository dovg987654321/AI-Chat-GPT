# -*- coding: utf-8 -*-
"""
Akte 41 — 3D-сцена «Хутор ночью» (Hinterkaifeck, март 1922).
Blender (pip bpy) + Cycles, всё строится кодом. Туман считается прямо в материалах
(по расстоянию до камеры), поэтому рендер не дороже обычного.

python3 hk3d.py OUT_DIR --look film|diorama [--frames 0-191] [--samples 24] [--res 1920x1080]
Кадры: OUT_DIR/frames/f0000.png, плюс OUT_DIR/track.json (экранные точки трубы и окна для пост-обработки).
"""
import bpy, math, os, sys, random, json
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

args = sys.argv[1:]
OUT = args[0] if args else "out"
def opt(name, default):
    return args[args.index(name) + 1] if name in args else default
LOOK = opt("--look", "film")
SAMPLES = int(opt("--samples", "24"))
RES = [int(v) for v in opt("--res", "1920x1080").split("x")]
FPS = 24
DUR = float(opt("--dur", "8"))
NF = int(DUR * FPS)
fr = opt("--frames", f"0-{NF - 1}").split("-")
F0, F1 = int(fr[0]), int(fr[-1])
os.makedirs(os.path.join(OUT, "frames"), exist_ok=True)
rnd = random.Random(41)

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def seg(t, a, b): return clamp((t - a) / (b - a))
def ease(x): x = clamp(x); return x * x * (3 - 2 * x)
def lerp(a, b, t): return a + (b - a) * t

bpy.ops.wm.read_factory_settings(use_empty=True)
S = bpy.context.scene
COL = S.collection
def link(ob, parent=None):
    COL.objects.link(ob)
    if parent: ob.parent = parent
    return ob

def srgb(h):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c)

# ------------------------------------------------------------------ параметры подач
DIO = LOOK == "diorama"
DC, DR = (6.0, 20.0), 23.0          # центр и радиус макета
def inside(x, y, m=0.0):
    return (not DIO) or math.hypot(x - DC[0], y - DC[1]) < DR - m
if LOOK == "diorama":
    FOG_COL, FOG_D = srgb("#2b3550"), 0.0015
    MOON_E, MOON_C = 1.6, srgb("#b9c8ff")
    SKY_TOP, SKY_HOR = srgb("#0b1330"), srgb("#2a3658")
    WIN_E = 9.0
else:
    FOG_COL, FOG_D = srgb("#18223a"), 0.022
    MOON_E, MOON_C = 2.2, srgb("#9fb4ff")
    SKY_TOP, SKY_HOR = srgb("#03060f"), srgb("#1b2438")
    WIN_E = 7.0
WIN_L = 160 if LOOK == "film" else 220
SIL_T = (4.4, 6.4)

# ------------------------------------------------------------------ материалы
def add_fog(m):
    """Смешивает итоговый шейдер с цветом тумана по расстоянию до камеры."""
    nt = m.node_tree; N = nt.nodes; L = nt.links
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")
    src = out.inputs["Surface"].links[0].from_socket
    cam = N.new("ShaderNodeCameraData")
    mth = N.new("ShaderNodeMath"); mth.operation = "MULTIPLY"; mth.inputs[1].default_value = -FOG_D
    ex = N.new("ShaderNodeMath"); ex.operation = "EXPONENT"
    inv = N.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
    L.new(cam.outputs["View Distance"], mth.inputs[0]); L.new(mth.outputs[0], ex.inputs[0])
    L.new(ex.outputs[0], inv.inputs[1])
    em = N.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*FOG_COL, 1)
    em.inputs["Strength"].default_value = 1.0
    # туман не должен засвечиваться для лучей, отражённых от поверхностей — только для камеры
    lp = N.new("ShaderNodeLightPath")
    mul = N.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    L.new(inv.outputs[0], mul.inputs[0]); L.new(lp.outputs["Is Camera Ray"], mul.inputs[1])
    mix = N.new("ShaderNodeMixShader")
    L.new(mul.outputs[0], mix.inputs[0]); L.new(src, mix.inputs[1]); L.new(em.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs["Surface"])
    return m

def mat(name, color, rough=0.6, bump=0.0, bump_scale=40.0, noise_col=None, emit=None, emit_s=0.0,
        sss=0.0, snow_top=0.0, fog=True):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    p = N["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    if sss:
        p.inputs["Subsurface Weight"].default_value = sss
        p.inputs["Subsurface Radius"].default_value = (0.5, 0.6, 0.9)
        p.inputs["Subsurface Scale"].default_value = 0.03
    if emit:
        p.inputs["Emission Color"].default_value = (*emit, 1)
        p.inputs["Emission Strength"].default_value = emit_s
    col_sock = None
    if bump or noise_col or snow_top:
        tc = N.new("ShaderNodeTexCoord")
        nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = bump_scale
        nz.inputs["Detail"].default_value = 8.0; nz.inputs["Roughness"].default_value = 0.6
        L.new(tc.outputs["Object"], nz.inputs["Vector"])
        if bump:
            b = N.new("ShaderNodeBump"); b.inputs["Strength"].default_value = bump
            b.inputs["Distance"].default_value = 0.02
            L.new(nz.outputs["Fac"], b.inputs["Height"]); L.new(b.outputs["Normal"], p.inputs["Normal"])
        if noise_col:
            ramp = N.new("ShaderNodeValToRGB")
            ramp.color_ramp.elements[0].color = (*noise_col, 1)
            ramp.color_ramp.elements[1].color = (*color, 1)
            ramp.color_ramp.elements[0].position = 0.3; ramp.color_ramp.elements[1].position = 0.7
            L.new(nz.outputs["Fac"], ramp.inputs["Fac"])
            col_sock = ramp.outputs["Color"]
            L.new(col_sock, p.inputs["Base Color"])
        if snow_top:
            # снег там, где поверхность смотрит вверх
            geo = N.new("ShaderNodeNewGeometry")
            sep = N.new("ShaderNodeSeparateXYZ"); L.new(geo.outputs["Normal"], sep.inputs[0])
            add = N.new("ShaderNodeMath"); add.operation = "ADD"
            L.new(sep.outputs["Z"], add.inputs[0])
            nz2 = N.new("ShaderNodeTexNoise"); nz2.inputs["Scale"].default_value = 6.0
            L.new(tc.outputs["Object"], nz2.inputs["Vector"])
            sc = N.new("ShaderNodeMath"); sc.operation = "MULTIPLY"; sc.inputs[1].default_value = 0.5
            L.new(nz2.outputs["Fac"], sc.inputs[0]); L.new(sc.outputs[0], add.inputs[1])
            r2 = N.new("ShaderNodeValToRGB")
            r2.color_ramp.elements[0].position = 0.62 + (1 - snow_top) * 0.3
            r2.color_ramp.elements[1].position = 0.72 + (1 - snow_top) * 0.3
            L.new(add.outputs[0], r2.inputs["Fac"])
            mx = N.new("ShaderNodeMix"); mx.data_type = "RGBA"
            L.new(r2.outputs["Color"], mx.inputs["Factor"])
            if col_sock is not None: L.new(col_sock, mx.inputs[6])
            else: mx.inputs[6].default_value = (*color, 1)
            mx.inputs[7].default_value = (*srgb("#dfe6f2"), 1)
            L.new(mx.outputs[2], p.inputs["Base Color"])
    if fog: add_fog(m)
    return m

M = dict(
    snow=mat("snow", srgb("#e9eef7"), 0.55, bump=0.25, bump_scale=90, noise_col=srgb("#cdd6e6")),
    plaster=mat("plaster", srgb("#b9b3a6"), 0.9, bump=0.35, bump_scale=14, noise_col=srgb("#7d776b")),
    wood=mat("wood", srgb("#4a3a2c"), 0.85, bump=0.5, bump_scale=8, noise_col=srgb("#2a2018")),
    roof=mat("roof", srgb("#3a2f2a"), 0.8, bump=0.3, bump_scale=20, snow_top=0.95),
    roofsnow=mat("roofsnow", srgb("#e3e9f3"), 0.6, bump=0.2, bump_scale=30, noise_col=srgb("#c3cbd9")),
    frame=mat("frame", srgb("#2b2520"), 0.7),
    glassd=mat("glassd", srgb("#0a0c12"), 0.15),
    glassl=mat("glassl", srgb("#ffb35c"), 0.3, emit=srgb("#ffa040"), emit_s=WIN_E),
    tree=mat("tree", srgb("#132018"), 0.9, bump=0.6, bump_scale=10, noise_col=srgb("#0a120c"), snow_top=0.8),
    bark=mat("bark", srgb("#2a1f17"), 0.9),
    post=mat("post", srgb("#3a2e24"), 0.9, bump=0.4, bump_scale=12, snow_top=0.9),
    stone=mat("stone", srgb("#55565a"), 0.9, bump=0.5, bump_scale=6),
    shadow=mat("shadow", (0.003, 0.003, 0.004), 1.0, fog=False),
    earth=mat("earth", srgb("#3b2a1e"), 0.95, bump=0.8, bump_scale=6, noise_col=srgb("#1e140d")),
    table=mat("table", srgb("#2a1a10"), 0.45, bump=0.1, bump_scale=3, noise_col=srgb("#160d07"), fog=False),
)

# ------------------------------------------------------------------ рельеф
def h(x, y):
    return (0.25 * math.sin(x * 0.11 + 1.3) * math.cos(y * 0.07) + 0.12 * math.sin(x * 0.23 + y * 0.19)
            + 0.08 * math.sin(x * 0.9 + 0.5) * math.sin(y * 0.8 + 1.1) - 0.003 * max(0, y - 18) ** 2 * 0)

def path_pt(s):
    """Тропа следов: из леса слева, к двери хутора. s в метрах."""
    pts = [(-16, -14), (-9, -9), (-3, -3.5), (0.6, 3), (2.2, 10), (2.6, 17), (2.4, 22.5)]
    # кусочно-линейная с сглаживанием Catmull-Rom
    L_ = [0]
    for i in range(1, len(pts)):
        L_.append(L_[-1] + math.dist(pts[i - 1], pts[i]))
    s = clamp(s, 0, L_[-1] - 1e-3)
    i = max(k for k in range(len(L_) - 1) if L_[k] <= s)
    u = (s - L_[i]) / (L_[i + 1] - L_[i])
    p0 = pts[max(0, i - 1)]; p1 = pts[i]; p2 = pts[i + 1]; p3 = pts[min(len(pts) - 1, i + 2)]
    def cr(a, b, c, d, t):
        return 0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (-a + 3 * b - 3 * c + d) * t ** 3)
    return (cr(p0[0], p1[0], p2[0], p3[0], u), cr(p0[1], p1[1], p2[1], p3[1], u)), L_[-1]

_, PATH_LEN = path_pt(0)

def mesh_from(name, verts, faces, m, smooth=True):
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.update()
    if smooth:
        for p in me.polygons: p.use_smooth = True
    ob = link(bpy.data.objects.new(name, me)); ob.data.materials.append(m)
    return ob

def build_ground():
    # общий снег: сетка 160x160 м
    n, size = 460, 160.0
    verts, faces = [], []
    for j in range(n + 1):
        for i in range(n + 1):
            x = -size / 2 + size * i / n; y = -40 + size * j / n
            if DIO:
                dd = math.hypot(x - DC[0], y - DC[1])
                if dd > DR:
                    x, y = DC[0] + (x - DC[0]) * DR / dd, DC[1] + (y - DC[1]) * DR / dd
            verts.append((x, y, h(x, y) - 0.004))
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            if DIO and not any(inside(*verts[k][:2], 0.01) for k in (a, a + 1, a + n + 2, a + n + 1)):
                continue
            faces.append((a, a + 1, a + n + 2, a + n + 1))
    mesh_from("ground", verts, faces, M["snow"])
    if DIO: build_base()
    # полоса со следами — плотная сетка с настоящими вмятинами
    stride, half = 0.78, 0.65
    steps = []
    s = 0.4; k = 0
    while s < PATH_LEN - 0.6:
        (x0, y0), _ = path_pt(s); (x1, y1), _ = path_pt(s + 0.05)
        d = Vector((x1 - x0, y1 - y0, 0)).normalized(); nrm = Vector((-d.y, d.x, 0))
        side = 0.13 if k % 2 == 0 else -0.13
        jit = rnd.uniform(-0.03, 0.03)
        steps.append((x0 + nrm.x * (side + jit), y0 + nrm.y * (side + jit), d.x, d.y, rnd.uniform(-0.15, 0.15)))
        s += stride + rnd.uniform(-0.05, 0.05); k += 1
    rows = int(PATH_LEN / 0.022); cols = 60
    verts, faces = [], []
    for r in range(rows + 1):
        sp = PATH_LEN * r / rows
        (x0, y0), _ = path_pt(sp); (x1, y1), _ = path_pt(sp + 0.05)
        d = Vector((x1 - x0, y1 - y0, 0)).normalized(); nrm = Vector((-d.y, d.x, 0))
        near = [st for st in steps if abs(st[0] - x0) < 1.0 and abs(st[1] - y0) < 1.0]
        for c in range(cols + 1):
            o = -half + 2 * half * c / cols
            if DIO and not inside(x0, y0, 0.8): o = 0.0
            x, y = x0 + nrm.x * o, y0 + nrm.y * o
            z = h(x, y)
            edge = clamp(1 - abs(o) / half)
            dz = 0.0
            for (fx, fy, dx, dy, rot) in near:
                lx, ly = x - fx, y - fy
                u = lx * dx + ly * dy; v = -lx * dy + ly * dx
                # ботинок: вытянутый эллипс с более широким носком
                a, b = 0.15, 0.055 + 0.015 * clamp((u + 0.15) / 0.3)
                q = (u / a) ** 2 + (v / b) ** 2
                if q < 1.5:
                    k_ = clamp((1.3 - q) / 0.5)
                    dz -= 0.075 * k_ * k_ * (3 - 2 * k_)
                # волочение ноги в снегу: мелкая борозда вперёд от носка
                if 0.1 < u < 0.55 and abs(v) < 0.05:
                    dz -= 0.018 * (1 - abs(v) / 0.05) * (1 - (u - 0.1) / 0.45)
            dz = max(dz, -0.08)
            z += dz * edge - 0.012 * ease(clamp((abs(o) / half - 0.45) / 0.55))
            verts.append((x, y, z))
    for r in range(rows):
        for c in range(cols):
            a = r * (cols + 1) + c
            faces.append((a, a + 1, a + cols + 2, a + cols + 1))
    mesh_from("tracks", verts, faces, M["snow"])
    return steps

# ------------------------------------------------------------------ постройки
def box(name, sx, sy, sz, loc, m, rot_z=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = bpy.context.active_object; ob.name = name
    ob.scale = (sx, sy, sz); ob.rotation_euler = (0, 0, rot_z)
    bpy.ops.object.transform_apply(scale=True)
    ob.data.materials.append(m)
    bv = ob.modifiers.new("bv", "BEVEL"); bv.width = 0.03; bv.segments = 2
    return ob

def gable(name, w, d, wall_h, ridge_h, over, loc, m, msnow, rot_z=0.0):
    """Двускатная крыша вдоль оси Y шириной w (по X), длиной d, с толщиной и снежной шапкой."""
    x0, y0, z0 = loc
    hw, hd = w / 2 + over, d / 2 + over
    t = 0.18
    vs = [(-hw, -hd, wall_h - 0.25), (0, -hd, wall_h + ridge_h), (hw, -hd, wall_h - 0.25),
          (-hw, hd, wall_h - 0.25), (0, hd, wall_h + ridge_h), (hw, hd, wall_h - 0.25)]
    vs2 = [(x, y, z + t) for (x, y, z) in vs]
    V = vs + vs2
    Fc = [(0, 1, 4, 3), (1, 2, 5, 4), (6, 9, 10, 7), (7, 10, 11, 8), (0, 3, 9, 6), (2, 8, 11, 5),
          (0, 6, 7, 1), (1, 7, 8, 2), (3, 4, 10, 9), (4, 5, 11, 10)]
    ob = mesh_from(name, V, Fc, m, smooth=False)
    # снежная шапка: чуть выше, с неровным краем
    sv, sf = [], []
    nx, ny = 24, 40
    for side in (-1, 1):
        base = len(sv)
        for j in range(ny + 1):
            yy = -hd + 2 * hd * j / ny
            for i in range(nx + 1):
                u = i / nx
                xx = side * hw * (1 - u) * 0.985
                zz = wall_h - 0.25 + (ridge_h + 0.25) * u + t + 0.02
                thick = 0.10 + 0.05 * math.sin(yy * 3.1 + side) * math.sin(u * 7) + 0.03 * math.sin(yy * 11.0)
                if i == 0: thick *= 0.3
                sv.append((xx, yy, zz + thick))
        for j in range(ny):
            for i in range(nx):
                a = base + j * (nx + 1) + i
                f = (a, a + 1, a + nx + 2, a + nx + 1)
                sf.append(f if side > 0 else f[::-1])
    sn = mesh_from(name + "_snow", sv, sf, msnow)
    for o in (ob, sn):
        o.location = (x0, y0, z0); o.rotation_euler = (0, 0, rot_z)
    return ob

def window(x, y, z, facing, lit=False, w=0.9, hgt=1.0):
    """Окно в стене. facing — угол нормали стены (рад)."""
    nx, ny = math.cos(facing), math.sin(facing)
    rz = facing + math.pi / 2
    g = box("win", w, 0.06, hgt, (x + nx * 0.02, y + ny * 0.02, z), M["glassl"] if lit else M["glassd"], rz)
    fr_ = M["frame"]
    box("wf_t", w + 0.16, 0.14, 0.08, (x, y, z + hgt / 2 + 0.04), fr_, rz)
    box("wf_b", w + 0.22, 0.2, 0.08, (x + nx * 0.05, y + ny * 0.05, z - hgt / 2 - 0.04), fr_, rz)
    for sx in (-1, 1):
        ox, oy = math.cos(rz) * sx * (w / 2 + 0.04), math.sin(rz) * sx * (w / 2 + 0.04)
        box("wf_s", 0.08, 0.14, hgt + 0.1, (x + ox, y + oy, z), fr_, rz)
    box("wf_m", 0.05, 0.1, hgt, (x + nx * 0.05, y + ny * 0.05, z), fr_, rz)
    box("wf_c", w, 0.1, 0.05, (x + nx * 0.05, y + ny * 0.05, z + 0.1), fr_, rz)
    # ставни
    for sx in (-1, 1):
        ox, oy = math.cos(rz) * sx * (w / 2 + 0.32), math.sin(rz) * sx * (w / 2 + 0.32)
        box("shut", 0.45, 0.05, hgt + 0.05, (x + ox + nx * 0.06, y + oy + ny * 0.06, z), M["wood"], rz)
    return g

HOUSE = dict(x=2.5, y=27.0, w=8.5, d=11.0, wall=3.0)
def build_farm():
    hx, hy = HOUSE["x"], HOUSE["y"]
    gz = h(hx, hy) - 0.3
    # жилой дом: фасад смотрит на камеру (-Y)
    box("house", 8.5, 11.0, 3.6, (hx, hy, gz + 1.8), M["plaster"])
    gable("house_roof", 8.5, 11.0, 3.6, 3.4, 0.55, (hx, hy, gz), M["roof"], M["roofsnow"])
    # цоколь
    box("plinth", 8.7, 11.2, 0.5, (hx, hy, gz + 0.25), M["stone"])
    # фронтон досками
    fz = gz + 3.6
    vs = [(-4.25, -5.52, 0), (4.25, -5.52, 0), (0, -5.52, 3.2)]
    fron = mesh_from("gable_front", [(hx + a, hy + b, fz + c) for a, b, c in vs], [(0, 1, 2)], M["wood"], smooth=False)
    # амбар/хлев под одной крышей, вбок
    bx, by = hx + 12.0, hy + 2.0
    box("barn", 15.5, 10.0, 4.6, (bx, by, gz + 2.3), M["wood"])
    gable("barn_roof", 10.0, 15.5, 4.6, 3.6, 0.6, (bx, by, gz), M["roof"], M["roofsnow"], rot_z=math.pi / 2)
    vs = [(-5.0, -5.02, 0), (5.0, -5.02, 0), (0, -5.02, 3.4)]
    # ворота амбара
    box("barn_door", 3.2, 0.12, 3.4, (bx - 2.0, by - 5.02, gz + 1.7), M["frame"])
    box("barn_door2", 3.0, 0.14, 0.15, (bx - 2.0, by - 5.06, gz + 2.0), M["wood"])
    # окна дома: одно светится
    fy = hy - 5.5
    WZ = gz + 1.9
    lit = window(hx - 2.3, fy, WZ, -math.pi / 2, lit=True)
    window(hx + 2.3, fy, WZ, -math.pi / 2)
    window(hx, fy, gz + 4.8, -math.pi / 2, w=0.6, hgt=0.7)
    # боковые окна
    window(hx - 4.25, hy - 2.0, WZ, math.pi, w=0.8)
    window(hx - 4.25, hy + 2.5, WZ, math.pi, w=0.8)
    # дверь
    box("door", 1.1, 0.12, 2.1, (hx + 0.2, fy - 0.02, gz + 1.35), M["wood"])
    box("step", 1.6, 0.6, 0.3, (hx + 0.2, fy - 0.35, gz + 0.3), M["stone"])
    # труба
    ch = box("chimney", 0.7, 0.7, 2.0, (hx + 1.4, hy + 1.0, gz + 3.6 + 3.4 * 0.62 + 0.4), M["stone"])
    # тёплый свет внутри: тянется на снег
    L1 = bpy.data.lights.new("winlight", "AREA"); L1.energy = WIN_L
    L1.color = srgb("#ffa24a"); L1.size = 0.8
    lo = link(bpy.data.objects.new("winlight", L1))
    lo.location = (hx - 2.3, fy - 0.25, WZ + 0.2)
    lo.rotation_euler = (math.radians(-70), 0, 0)
    L1.size = 1.0
    # силуэт за окном: проходит в момент «кто-то остался»
    sil = link(bpy.data.objects.new("silo", None))
    sil.location = (hx - 2.3, fy, WZ - 0.25)
    silhouette_mask(M["glassl"], sil)
    return dict(lit=lit, chimney_top=Vector((hx + 1.4, hy + 1.0, gz + 3.6 + 3.4 * 0.62 + 1.45)),
                window=Vector((hx - 2.3, fy, WZ)), sil=sil, gz=gz, L1=L1)

def silhouette_mask(m, empty):
    """Тень человека за освещённым стеклом: маска из голой математики в координатах пустышки."""
    nt = m.node_tree; N = nt.nodes; L = nt.links
    p = N["Principled BSDF"]
    tc = N.new("ShaderNodeTexCoord"); tc.object = empty
    sep = N.new("ShaderNodeSeparateXYZ"); L.new(tc.outputs["Object"], sep.inputs[0])
    def M_(op, a, b=None, v=None):
        n = N.new("ShaderNodeMath"); n.operation = op
        for i, x in enumerate((a, b)):
            if x is None: continue
            if isinstance(x, (int, float)): n.inputs[i].default_value = x
            else: L.new(x, n.inputs[i])
        return n.outputs[0]
    X, Z = sep.outputs["X"], sep.outputs["Z"]
    # голова
    hz = M_("SUBTRACT", Z, 0.42)
    hd = M_("SQRT", M_("ADD", M_("MULTIPLY", X, X), M_("MULTIPLY", hz, hz)))
    head = M_("LESS_THAN", hd, 0.12)
    # плечи и тело: скруглённый прямоугольник
    ax = M_("MAXIMUM", M_("SUBTRACT", M_("ABSOLUTE", X), 0.12), 0.0)
    az = M_("MAXIMUM", M_("SUBTRACT", Z, 0.12), 0.0)
    bd = M_("SQRT", M_("ADD", M_("MULTIPLY", ax, ax), M_("MULTIPLY", az, az)))
    body = M_("LESS_THAN", bd, 0.14)
    neck = M_("MULTIPLY", M_("LESS_THAN", M_("ABSOLUTE", X), 0.06), M_("LESS_THAN", Z, 0.36))
    mask = M_("MAXIMUM", M_("MAXIMUM", head, body), neck)
    inv = M_("SUBTRACT", 1.0, M_("MULTIPLY", mask, 0.93))
    st = M_("MULTIPLY", inv, p.inputs["Emission Strength"].default_value)
    L.new(st, p.inputs["Emission Strength"])

def build_silhouette():
    """Плоский силуэт человека в шляпе (чёрный, без тумана)."""
    pts = []
    prof = [(0.0, 0.0), (0.26, 0.0), (0.28, 0.7), (0.30, 1.25), (0.24, 1.42), (0.12, 1.5), (0.11, 1.56),
            (0.13, 1.62), (0.13, 1.72), (0.23, 1.74), (0.23, 1.77), (0.12, 1.79), (0.10, 1.9), (0.0, 1.92)]
    right = prof; left = [(-x, z) for (x, z) in reversed(prof)]
    outline = right + left[1:-1]
    V = [(x, 0, z) for (x, z) in outline]
    me = bpy.data.meshes.new("sil"); me.from_pydata(V, [], [list(range(len(V)))]); me.update()
    ob = link(bpy.data.objects.new("sil", me)); ob.data.materials.append(M["shadow"])
    return ob

def build_base():
    """Срез макета: земля, камень, тонкий слой снега; под ним стол."""
    n = 160; V, Fc = [], []
    for i in range(n):
        a = 2 * math.pi * i / n
        x, y = DC[0] + math.cos(a) * DR, DC[1] + math.sin(a) * DR
        V += [(x, y, h(x, y) - 0.004), (x, y, -3.2)]
    for i in range(n):
        j = (i + 1) % n
        Fc.append((2 * i, 2 * i + 1, 2 * j + 1, 2 * j))
    ob = mesh_from("base", V, Fc, M["earth"])
    tb = bpy.data.meshes.new("table")
    tb.from_pydata([(-400, -400, -3.2), (400, -400, -3.2), (400, 400, -3.2), (-400, 400, -3.2)], [], [(0, 1, 2, 3)])
    t = link(bpy.data.objects.new("table", tb)); t.data.materials.append(M["table"])
    # тёплая настольная лампа сбоку: «макет на столе следователя»
    L2 = bpy.data.lights.new("desk", "AREA"); L2.energy = 15000; L2.size = 18; L2.color = srgb("#ffcf9a")
    lo = link(bpy.data.objects.new("desk", L2)); lo.location = (DC[0] + 55, DC[1] - 70, 45)
    d = Vector(DC + (0,)) - lo.location; lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

def build_trees():
    # одна модель ели, много копий
    def tree_mesh():
        V, Fc = [], []
        tiers = [(0.6, 2.2, 1.3), (1.4, 1.8, 1.25), (2.2, 1.45, 1.15), (2.9, 1.1, 1.0), (3.5, 0.75, 0.9), (4.0, 0.4, 0.8)]
        seg_n = 14
        for (z, r, hh) in tiers:
            base = len(V)
            for i in range(seg_n):
                a = 2 * math.pi * i / seg_n
                rr = r * (0.85 + 0.25 * ((i * 7) % 3) / 2)
                V.append((math.cos(a) * rr, math.sin(a) * rr, z - 0.15 * ((i % 2))))
            V.append((0, 0, z + hh)); tip = len(V) - 1
            V.append((0, 0, z + 0.1)); bot = len(V) - 1
            for i in range(seg_n):
                j = (i + 1) % seg_n
                Fc.append((base + i, base + j, tip)); Fc.append((base + j, base + i, bot))
        me = bpy.data.meshes.new("tree"); me.from_pydata(V, [], Fc); me.update()
        for p in me.polygons: p.use_smooth = True
        me.materials.append(M["tree"])
        return me
    me = tree_mesh()
    trunk = bpy.data.meshes.new("trunk")
    tv = [(math.cos(a) * 0.14, math.sin(a) * 0.14, z) for z in (0, 1.0) for a in [2 * math.pi * i / 8 for i in range(8)]]
    tf = [(i, (i + 1) % 8, 8 + (i + 1) % 8, 8 + i) for i in range(8)]
    trunk.from_pydata(tv, [], tf); trunk.update(); trunk.materials.append(M["bark"])
    def place(x, y, sc):
        z = h(x, y) - 0.1
        o = link(bpy.data.objects.new("tree", me)); o.location = (x, y, z)
        o.scale = (sc, sc, sc * rnd.uniform(0.95, 1.3)); o.rotation_euler = (0, 0, rnd.uniform(0, 6.3))
        t = link(bpy.data.objects.new("trunk", trunk)); t.location = (x, y, z); t.scale = (sc, sc, sc)
    if DIO:
        k = 0
        while k < 46:
            x = rnd.uniform(DC[0] - DR, DC[0] + DR); y = rnd.uniform(DC[1] - DR, DC[1] + DR)
            if not inside(x, y, 1.6): continue
            if -4 < x < 23 and 13 < y < 35: continue        # двор и постройки
            if math.hypot(x - DC[0], y - DC[1]) < 15 and y < 24: continue
            # близко к тропе — нет
            if any(math.hypot(x - path_pt(ss)[0][0], y - path_pt(ss)[0][1]) < 2.2 for ss in range(0, int(PATH_LEN), 2)):
                continue
            place(x, y, rnd.uniform(0.9, 1.5)); k += 1
        return
    # лес слева (откуда пришли следы) и за хутором
    for _ in range(170):
        x = rnd.uniform(-60, -15); y = rnd.uniform(-25, 70)
        if x > -22 and y < 0: continue
        place(x, y, rnd.uniform(1.6, 2.8))
    for _ in range(170):
        x = rnd.uniform(-20, 60); y = rnd.uniform(48, 85)
        place(x, y, rnd.uniform(1.8, 3.0))
    for _ in range(40):
        x = rnd.uniform(28, 60); y = rnd.uniform(-10, 50)
        place(x, y, rnd.uniform(1.6, 2.6))

def build_fence():
    for i in range(14):
        x = -6.5 + i * 1.9; y = 19.0 + 0.15 * math.sin(i)
        if 1.0 < x < 4.0: continue
        z = h(x, y)
        box("post", 0.12, 0.12, 1.2, (x, y, z + 0.45), M["post"], rnd.uniform(-0.1, 0.1))
    for zz in (0.55, 0.95):
        box("rail", 7.6, 0.06, 0.08, (-6.5 + 3.8, 19.0, h(-3, 19) + zz), M["post"])
        box("rail", 13.4, 0.06, 0.08, (4.4 + 6.7, 19.0, h(11, 19) + zz), M["post"])

# ------------------------------------------------------------------ свет, мир
def build_world():
    w = bpy.data.worlds.new("world"); S.world = w; w.use_nodes = True
    N = w.node_tree.nodes; L = w.node_tree.links
    bg = N["Background"]
    tc = N.new("ShaderNodeTexCoord"); sep = N.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Generated"], sep.inputs[0])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.5; ramp.color_ramp.elements[0].color = (*SKY_HOR, 1)
    ramp.color_ramp.elements[1].position = 0.75; ramp.color_ramp.elements[1].color = (*SKY_TOP, 1)
    L.new(sep.outputs["Z"], ramp.inputs["Fac"])
    # для камеры — небо с туманом у горизонта; для освещения — слабый синий
    lp = N.new("ShaderNodeLightPath")
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"
    L.new(lp.outputs["Is Camera Ray"], mix.inputs["Factor"])
    mix.inputs[6].default_value = (*srgb("#1c2640"), 1)
    if DIO:
        ramp.color_ramp.elements[0].color = (*srgb("#0d0b0a"), 1); ramp.color_ramp.elements[1].color = (*srgb("#050404"), 1)
    L.new(ramp.outputs["Color"], mix.inputs[7])
    L.new(mix.outputs[2], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.55 if LOOK == "film" else 0.8
    moon = bpy.data.lights.new("moon", "SUN"); moon.energy = MOON_E; moon.color = MOON_C
    moon.angle = math.radians(1.2)
    mo = link(bpy.data.objects.new("moon", moon))
    mo.rotation_euler = (math.radians(62), 0, math.radians(150))

# ------------------------------------------------------------------ камера
def build_camera():
    cd = bpy.data.cameras.new("cam"); cam = link(bpy.data.objects.new("cam", cd)); S.camera = cam
    cd.sensor_width = 36; cd.dof.use_dof = True; cd.dof.aperture_blades = 6
    foc = link(bpy.data.objects.new("focus", None)); cd.dof.focus_object = foc
    tgt = link(bpy.data.objects.new("target", None))
    c = cam.constraints.new("TRACK_TO"); c.target = tgt; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
    return cam, cd, foc, tgt

def shot(t, cam, cd, foc, tgt, farm):
    if LOOK == "diorama":
        # высоко и издалека, медленный облёт: игрушечный макет
        u = ease(t / DUR)
        a = math.radians(-112 + 14 * u)
        R = 92.0 - 8.0 * u
        cam.location = (DC[0] + math.cos(a) * R, DC[1] + math.sin(a) * R, 66.0 - 5.0 * u)
        tgt.location = (DC[0] - 0.5, DC[1] + 1.0, -1.5)
        cd.lens = 58; cd.dof.aperture_fstop = 0.4
        foc.location = (HOUSE["x"], HOUSE["y"] - 5.0, 1.5)
    else:
        # низко над следами, наезд вдоль тропы, перевод фокуса со следа на окно
        u = ease(t / DUR)
        s = lerp(9.5, 12.5, u)
        (px, py), _ = path_pt(s)
        cam.location = (px + 0.45, py - 0.2, h(px, py) + lerp(0.75, 1.15, u))
        (qx, qy), _ = path_pt(s + 6)
        tgt.location = (lerp(qx, HOUSE["x"] - 0.8, ease(seg(t, 0.0, DUR))), lerp(qy, HOUSE["y"] - 5.5, u),
                        lerp(h(qx, qy) + 0.1, farm["gz"] + 2.3, u))
        cd.lens = 32
        cd.dof.aperture_fstop = 2.0
        (fx, fy), _ = path_pt(s + 1.8)
        f_near = Vector((fx, fy, h(fx, fy)))
        foc.location = f_near.lerp(farm["window"], ease(seg(t, 2.4, 4.6)))
    # силуэт проходит за светящимся окном
    k = seg(t, SIL_T[0], SIL_T[1])
    sx = HOUSE["x"] - 3.3 + 2.0 * ease(k)
    farm["sil"].location.x = sx
    farm["L1"].energy = WIN_L * (1 - 0.55 * clamp(1 - abs(sx - (HOUSE["x"] - 2.3)) / 0.35))

def setup_render():
    S.render.engine = "CYCLES"; S.cycles.device = "CPU"
    S.cycles.samples = SAMPLES
    S.cycles.use_adaptive_sampling = True; S.cycles.adaptive_threshold = 0.06
    S.cycles.use_denoising = True
    try: S.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception: pass
    S.cycles.max_bounces = 3; S.cycles.diffuse_bounces = 1; S.cycles.glossy_bounces = 1
    S.cycles.transmission_bounces = 1; S.cycles.transparent_max_bounces = 2
    S.cycles.caustics_reflective = False; S.cycles.caustics_refractive = False
    S.render.use_persistent_data = True
    S.render.resolution_x, S.render.resolution_y = RES; S.render.resolution_percentage = 100
    S.view_settings.view_transform = "AgX"
    try: S.view_settings.look = "AgX - Medium High Contrast"
    except Exception: pass
    S.view_settings.exposure = 0.6 if LOOK == "film" else 0.9
    S.render.image_settings.file_format = "PNG"

def main():
    setup_render(); build_world()
    build_ground(); farm = build_farm(); build_trees(); build_fence()
    cam, cd, foc, tgt = build_camera()
    track = {}
    for f in range(F0, F1 + 1, int(opt("--step", "1"))):
        t = f / FPS
        shot(t, cam, cd, foc, tgt, farm)
        bpy.context.view_layer.update()
        def scr(v):
            p = world_to_camera_view(S, cam, v); return [p.x, 1 - p.y, p.z]
        track[f] = dict(chimney=scr(farm["chimney_top"]), window=scr(farm["window"]))
        S.render.filepath = os.path.join(OUT, "frames", f"f{f:04d}.png")
        if not os.path.exists(S.render.filepath):
            bpy.ops.render.render(write_still=True)
    old = {}
    tp = os.path.join(OUT, f"track_{F0}_{F1}.json")
    json.dump(track, open(tp, "w"))

if __name__ == "__main__":
    main()
