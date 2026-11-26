"""Люди 1920-х для «Тёмного кино»: лицо (глаза, брови, нос, рот, уши), причёска,
одежда со складками, руки с локтями и живые позы. Общий модуль для hk3d.py и sets3d.py.

person(x, y, z, face, kind, ...) -> root (Empty); все части — его потомки.
Лицо смотрит в -Y локально; face поворачивает фигуру вокруг Z.
"""
import bpy, math, random
from mathutils import Vector

_MATFN = None          # matfn(name, rgb_linear, rough, bump, bump_scale) -> Material
_M = {}

def setup(matfn):
    global _MATFN
    _MATFN = matfn

def _srgb(h):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c)

def _mk(name, hexc, rough, bump=0.0, bs=40.0, sss=0.0, emit=None, es=0.0):
    m = _MATFN(name, _srgb(hexc), rough, bump, bs)
    p = m.node_tree.nodes.get("Principled BSDF")
    if p:
        if sss:
            p.inputs["Subsurface Weight"].default_value = sss
            p.inputs["Subsurface Radius"].default_value = (0.9, 0.45, 0.3)
            p.inputs["Subsurface Scale"].default_value = 0.012
        if emit:
            p.inputs["Emission Color"].default_value = (*_srgb(emit), 1)
            p.inputs["Emission Strength"].default_value = es
    return m

def mats():
    if not _M:
        _M.update(
            skin=_mk("fg_skin", "#a37c64", 0.5, 0.04, 400, sss=0.15),
            skin_old=_mk("fg_skin_old", "#95705b", 0.55, 0.12, 300, sss=0.12),
            lip=_mk("fg_lip", "#7a4a40", 0.45, sss=0.12),
            mouth=_mk("fg_mouth", "#24120e", 0.7),
            ewhite=_mk("fg_ewhite", "#a99f90", 0.25),
            iris=_mk("fg_iris", "#120d0a", 0.08),
            hair=_mk("fg_hair", "#2b1d14", 0.6, 0.4, 260),
            hair_blond=_mk("fg_hair_bl", "#6b5132", 0.6, 0.4, 260),
            grey=_mk("fg_grey", "#77716a", 0.6, 0.4, 260),
            coat=_mk("fg_coat", "#1d1b1e", 0.85, 0.35, 60),
            coat2=_mk("fg_coat2", "#2c2520", 0.85, 0.35, 60),
            loden=_mk("fg_loden", "#2b3027", 0.9, 0.35, 70),
            trench=_mk("fg_trench", "#4f4638", 0.8, 0.3, 50),
            trouser=_mk("fg_trouser", "#232120", 0.85, 0.3, 60),
            skirt=_mk("fg_skirt", "#3b2523", 0.9, 0.35, 45),
            skirt2=_mk("fg_skirt2", "#262a34", 0.9, 0.35, 45),
            apron=_mk("fg_apron", "#6f685b", 0.9, 0.3, 70),
            apron2=_mk("fg_apron2", "#4a5260", 0.9, 0.3, 70),
            scarf=_mk("fg_scarf", "#2e2a33", 0.9, 0.35, 55),
            scarf2=_mk("fg_scarf2", "#4a2e2a", 0.9, 0.35, 55),
            shirt=_mk("fg_shirt", "#b8ae9c", 0.7, 0.2, 80),
            tie=_mk("fg_tie", "#2a1414", 0.6),
            boot=_mk("fg_boot", "#0f0d0c", 0.45),
            hat=_mk("fg_hat", "#1a1817", 0.8, 0.3, 90),
            hat2=_mk("fg_hat2", "#3a342c", 0.8, 0.3, 90),
            button=_mk("fg_button", "#0c0b0a", 0.3),
            metal=_mk("fg_metal", "#151515", 0.35),
            wood=_mk("fg_wood", "#3a2618", 0.6),
            case=_mk("fg_case", "#3d2a1c", 0.55, 0.3, 30),
            lamp=_mk("fg_lamp", "#ffc070", 0.3, emit="#ffa040", es=25.0),
        )
    return _M

# ---------------------------------------------------------------- примитивы (в локальных координатах фигуры)
def _smooth(o):
    for pg in o.data.polygons: pg.use_smooth = True
    return o

def _sph(n, r, loc, m, sc=(1, 1, 1), rot=(0, 0, 0), seg=28, ring=16):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, rotation=rot, segments=seg, ring_count=ring)
    o = bpy.context.active_object; o.name = n; o.scale = sc; o.data.materials.append(m)
    return _smooth(o)

def _cone(n, r1, r2, d, loc, m, rot=(0, 0, 0), nv=32, sc=(1, 1, 1), fill="NGON"):
    bpy.ops.mesh.primitive_cone_add(vertices=nv, radius1=r1, radius2=r2, depth=d, location=loc, rotation=rot, end_fill_type=fill)
    o = bpy.context.active_object; o.name = n; o.scale = sc; o.data.materials.append(m)
    return _smooth(o)

def _seg(n, a, b, r1, r2, m, nv=18):
    a, b = Vector(a), Vector(b); d = b - a
    q = d.to_track_quat("Z", "Y").to_euler()
    return _cone(n, r1, r2, d.length, (a + b) / 2, m, rot=q, nv=nv, fill="NOTHING")

def _box(n, sx, sy, sz, loc, m, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object; o.name = n; o.scale = (sx, sy, sz); o.data.materials.append(m)
    return o

def _fold(o, n, amp, phase=0.0, top_amp=0.15):
    """Складки: радиальная волна, сильнее внизу (подол)."""
    vs = o.data.vertices
    zs = [v.co.z for v in vs]; z0, z1 = min(zs), max(zs)
    for v in vs:
        x, y = v.co.x, v.co.y; r = math.hypot(x, y)
        if r < 1e-5: continue
        t = (v.co.z - z0) / max(z1 - z0, 1e-6)
        a = amp * ((1 - t) + top_amp * t)
        th = math.atan2(y, x)
        w = math.sin(n * th + phase) + 0.35 * math.sin(2.3 * n * th + 1.7 * phase)
        f = (r + a * w) / r
        v.co.x *= f; v.co.y *= f
    return o

# ---------------------------------------------------------------- лицо
def _g(x, z, cx, cz, sx, sz):
    return math.exp(-((x - cx) ** 2) / (2 * sx * sx) - ((z - cz) ** 2) / (2 * sz * sz))

FACE = {   # индивидуальные черты: ширина челюсти, нос, скулы, подбородок
    "man": dict(jaw=1.0, nose=1.05, cheek=1.0, chin=1.0, brow=1.0),
    "old": dict(jaw=0.95, nose=1.15, cheek=1.2, chin=0.8, brow=1.15),
    "investigator": dict(jaw=1.05, nose=1.0, cheek=0.9, chin=1.2, brow=1.1),
    "woman": dict(jaw=0.86, nose=0.85, cheek=1.0, chin=0.7, brow=0.6),
    "maid": dict(jaw=0.88, nose=0.8, cheek=1.1, chin=0.7, brow=0.55),
    "old_woman": dict(jaw=0.9, nose=1.0, cheek=1.2, chin=0.6, brow=0.8),
    "girl": dict(jaw=0.82, nose=0.6, cheek=1.2, chin=0.5, brow=0.4),
    "boy": dict(jaw=0.85, nose=0.6, cheek=1.2, chin=0.5, brow=0.4),
}
RX, RY, RZ = 0.077, 0.098, 0.118

def _head_mesh(name, m, f, old):
    """Цельная голова: эллипсоид + сужение челюсти + рельеф лица (нос, надбровья, глазницы, скулы, губы, подбородок)."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0, 0, 0), segments=72, ring_count=54)
    o = bpy.context.active_object; o.name = name; o.data.materials.append(m)
    for v in o.data.vertices:
        dx, dy, dz = v.co.x, v.co.y, v.co.z
        x, y, z = dx * RX, dy * RY, dz * RZ
        if dz < 0:
            z *= 0.86
            x *= 1 - (0.2 / f["jaw"] - 0.02) * (-dz) ** 1.8
            if dy > 0: y *= 1 - 0.45 * (-dz) ** 1.3
        if dy < 0: y *= 0.93
        w = max(0.0, min(1.0, (-dy - 0.25) / 0.35))
        if w > 0:
            d = 0.0
            # нос: спинка + кончик + крылья
            if -0.044 < z < 0.02:
                t = (0.02 - z) / 0.05
                A = (0.006 + 0.019 * t ** 1.4) * f["nose"]
                if z < -0.03: A *= max(0.0, 1 - (-0.03 - z) / 0.011)
                sxn = 0.008 + 0.007 * t
                d += A * math.exp(-x * x / (2 * sxn * sxn))
            for sx in (-1, 1):
                d += 0.0065 * f["nose"] * _g(x, z, sx * 0.015, -0.034, 0.007, 0.006)
                d += 0.0065 * f["brow"] * _g(x, z, sx * 0.031, 0.03, 0.022, 0.009)      # надбровья
                d -= 0.0115 * _g(x, z, sx * 0.032, 0.011, 0.013, 0.011)                # глазницы
                d += 0.0055 * f["cheek"] * _g(x, z, sx * 0.05, -0.016, 0.016, 0.016)  # скулы
                if old: d -= 0.002 * _g(x, z, sx * 0.027, -0.045, 0.003, 0.011)        # носогубные складки
            d += 0.0055 * _g(x, z, 0, -0.05, 0.019, 0.005)       # верхняя губа
            d += 0.0055 * _g(x, z, 0, -0.0625, 0.016, 0.0055)        # нижняя губа
            d -= 0.0045 * _g(x, z, 0, -0.0565, 0.021, 0.0017)      # линия рта
            d -= 0.0025 * _g(x, z, 0, -0.072, 0.016, 0.0045)        # ямка под губой
            d += 0.0065 * f["chin"] * _g(x, z, 0, -0.086, 0.017, 0.011)  # подбородок
            y -= d * w
        v.co = (x, y, z)
    for pg in o.data.polygons: pg.use_smooth = True
    return o

def _surf_y(x, z):
    """Передняя поверхность базового эллипсоида (без рельефа) в точке (x, z)."""
    if z < 0: z = z / 0.86
    q = 1 - (x / RX) ** 2 - (z / RZ) ** 2
    return -RY * 0.93 * math.sqrt(max(q, 0.0))

def _head(P, M, kind, fem, old, child, beard, hair_m, rng):
    """Голова с центром (0,0,1.6). Части в локальных координатах фигуры."""
    sk = M["skin_old"] if old else M["skin"]
    f = FACE.get(kind, FACE["man"])
    A = P.append
    H = 1.585
    hm = _head_mesh("head", sk, f, old); hm.location = (0, 0, H); A(hm)
    if fem: hm.scale = (1, 1, 0.95)
    for sx in (-1, 1):
        ex, ez = sx * 0.032, 0.011
        ey = _surf_y(ex, ez) + 0.0115 * 0.93 + 0.0035
        A(_sph("eye", 0.0112, (ex, ey, H + ez), M["ewhite"], seg=24, ring=16))
        A(_sph("iris", 0.0068, (ex, ey - 0.0085, H + ez), M["iris"], (1, 0.55, 1), seg=20, ring=12))
        A(_sph("lid", 0.0122, (ex, ey + 0.0005, H + ez + 0.0042), sk, (1.06, 1.0, 0.72), seg=24, ring=14))
        A(_sph("lowlid", 0.0118, (ex, ey + 0.001, H + ez - 0.005), sk, (1.04, 1.0, 0.45), seg=20, ring=10))
        by = _surf_y(sx * 0.032, 0.034) - 0.0065 * f["brow"] - 0.001
        A(_sph("brow", 0.017, (sx * 0.033, by, H + 0.035), hair_m, (1.5, 0.35, 0.22 if fem else 0.3),
               rot=(0, sx * -0.07, 0), seg=16, ring=8))
        pass
    uy = _surf_y(0, -0.05) - 0.0055 * f.get("lips", 1.0)
    ly = _surf_y(0, -0.0625) - 0.0055 * f.get("lips", 1.0)
    A(_sph("ulip", 0.016, (0, uy + 0.0042, H - 0.0505), M["lip"], (1.2 if not fem else 1.15, 0.3, 0.3), seg=24, ring=12))
    A(_sph("llip", 0.015, (0, ly + 0.0042, H - 0.0625), M["lip"], (1.05, 0.32, 0.36), seg=24, ring=12))
    A(_sph("mouth", 0.019, (0, _surf_y(0, -0.0565) - 0.0012, H - 0.0565), M["mouth"], (1.18, 0.16, 0.055), seg=24, ring=10))
    for sx in (-1, 1):
        A(_sph("ear", 0.027, (sx * 0.077, 0.012, H - 0.005), sk, (0.32, 0.68, 1.1), rot=(0, 0, sx * 0.25), seg=16, ring=10))
    # волосы
    if kind not in ("maid", "old_woman"):
        A(_sph("hair", 0.1, (0, 0.018, H + 0.018), hair_m, (0.84 if not fem else 0.86, 1.0, 1.1), seg=40, ring=24))
    if kind == "woman":
        A(_sph("bun", 0.042, (0, 0.105, H - 0.01), hair_m, (1.0, 0.85, 0.9)))
        A(_sph("part", 0.05, (0, -0.02, H + 0.09), hair_m, (1.35, 1.0, 0.45)))
    if kind == "girl":
        for sx in (-1, 1):
            A(_seg("braid", (sx * 0.062, 0.04, H - 0.03), (sx * 0.07, 0.03, H - 0.21), 0.02, 0.013, hair_m, nv=10))
            A(_sph("ribbon", 0.015, (sx * 0.07, 0.03, H - 0.215), M["scarf2"], (1.4, 0.6, 0.8), seg=12, ring=8))
    if kind in ("maid", "old_woman"):   # Kopftuch: макушка и затылок, лоб открыт
        sc_m = M["scarf2"] if kind == "maid" else M["scarf"]
        A(_sph("hairline", 0.098, (0, 0.022, H + 0.02), hair_m if kind == "maid" else M["grey"], (0.86, 1.0, 1.1), seg=40, ring=24))
        A(_sph("kopftuch", 0.104, (0, 0.045, H + 0.04), sc_m, (0.92, 0.98, 1.06), seg=40, ring=24))
        A(_sph("knot", 0.026, (0, 0.118, H - 0.07), sc_m, (1.3, 0.8, 0.9)))
        A(_seg("tail", (0.01, 0.12, H - 0.075), (0.03, 0.126, H - 0.17), 0.022, 0.01, sc_m, nv=10))
    if kind in ("man", "old", "investigator") and not child:
        if beard:
            A(_sph("beard", 0.058, (0, -0.048, H - 0.078), hair_m, (1.12, 0.78, 0.82), seg=32, ring=20))
            for sx in (-1, 1):
                A(_sph("sideb", 0.03, (sx * 0.06, -0.025, H - 0.045), hair_m, (0.7, 1.2, 1.5)))
        if beard or kind in ("man", "old"):
            A(_sph("moustache", 0.02, (0, _surf_y(0, -0.042) - 0.013, H - 0.043), hair_m,
                   (1.6 if kind != "investigator" else 1.2, 0.5, 0.38), seg=20, ring=10))
        hat_m = M["hat"] if kind != "investigator" else M["hat2"]
        bz = H + 0.088
        A(_cone("brim", 0.16 if kind != "investigator" else 0.17, 0.15, 0.012, (0, 0.008, bz), hat_m, rot=(-0.08, 0, 0), nv=48))
        A(_cone("crown", 0.088, 0.078, 0.1, (0, 0.012, bz + 0.054), hat_m, rot=(-0.08, 0, 0), nv=40))
        A(_cone("band", 0.0895, 0.088, 0.022, (0, 0.009, bz + 0.016), M["boot"], rot=(-0.08, 0, 0), nv=40))

# ---------------------------------------------------------------- фигура
def person(x, y, z, face=0.0, kind="man", sc=1.0, lantern=False, gun=False, case=False, arm_up=0.0,
           beard=False, seed=None, head=None, pose=None):
    M = mats()
    rng = random.Random(seed if seed is not None else int(abs(x * 131 + y * 17) * 10))
    root = bpy.data.objects.new("person", None); bpy.context.scene.collection.objects.link(root)
    P = []
    child = kind in ("girl", "boy", "child")
    k = (1.15 if kind != "boy" else 0.92) / 1.75 if child else 1.0
    fem = kind in ("woman", "maid", "old_woman", "girl")
    old = kind in ("old", "old_woman")
    hair_m = M["grey"] if old else (M["hair_blond"] if kind in ("girl", "boy") else M["hair"])
    coat = {"investigator": M["trench"], "woman": M["coat2"], "maid": M["coat2"], "old_woman": M["coat"],
            "old": M["loden"], "girl": M["coat2"], "boy": M["loden"]}.get(kind, M["coat"])
    if pose is None:
        pose = "fold" if (fem and not case and rng.random() < 0.6) else ("pocket" if rng.random() < 0.5 else "hang")
    # ---- тело (токарные профили: z, rx, ry, сдвиг y)
    def lathe(n, prof, m, nv=48, folds=None, cap=True):
        verts, faces = [], []
        for (zz, rx, ry, yo) in prof:
            for j in range(nv):
                th = 2 * math.pi * j / nv
                verts.append((rx * math.cos(th), ry * math.sin(th) + yo, zz))
        for i in range(len(prof) - 1):
            for j in range(nv):
                a0 = i * nv + j; a1 = i * nv + (j + 1) % nv
                faces.append((a0, a1, a1 + nv, a0 + nv))
        if cap:
            faces.append(tuple(range(nv))[::-1]); faces.append(tuple(range((len(prof) - 1) * nv, len(prof) * nv)))
        me = bpy.data.meshes.new(n); me.from_pydata(verts, [], faces); me.update()
        o = bpy.data.objects.new(n, me); bpy.context.scene.collection.objects.link(o)
        o.data.materials.append(m); _smooth(o)
        if folds: _fold(o, *folds)
        sd = o.modifiers.new("sub", "SUBSURF"); sd.levels = 1; sd.render_levels = 1
        return o
    skin = M["skin_old"] if old else M["skin"]
    if fem:
        sk_m = M["skirt2"] if kind == "maid" else M["skirt"]
        P.append(lathe("skirt", [(0.02, 0.325, 0.275, 0), (0.035, 0.33, 0.28, 0), (0.06, 0.328, 0.278, 0), (0.3, 0.29, 0.245, 0), (0.6, 0.23, 0.19, 0), (0.85, 0.165, 0.13, 0),
                                 (0.95, 0.15, 0.115, 0)], sk_m, 64, folds=(9, 0.018, rng.uniform(0, 6))))
        P.append(lathe("bodice", [(0.93, 0.15, 0.115, 0), (1.05, 0.16, 0.12, 0), (1.18, 0.18, 0.13, 0), (1.3, 0.19, 0.13, 0),
                                  (1.37, 0.17, 0.115, 0), (1.42, 0.1, 0.085, 0.005), (1.45, 0.05, 0.048, 0.005)], coat, 40))
        ap_m = M["apron2"] if kind == "maid" else M["apron"]
        ap = lathe("apron", [(0.08, 0.25, 0.335, -0.005), (0.4, 0.21, 0.29, -0.005), (0.75, 0.16, 0.225, -0.004), (0.94, 0.115, 0.15, -0.003)],
                   ap_m, 48, folds=(7, 0.01, rng.uniform(0, 6)))
        P.append(ap)
        # передник только спереди: убрать заднюю половину
        import bmesh
        bm = bmesh.new(); bm.from_mesh(ap.data)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > 0.02], context="VERTS"); bm.to_mesh(ap.data); bm.free()
        P.append(lathe("waistband", [(0.92, 0.157, 0.122, 0), (0.955, 0.155, 0.12, 0)], ap_m, 40))
        shm = M["scarf"] if kind != "old_woman" else M["scarf2"]
        P.append(lathe("shawl", [(1.455, 0.06, 0.055, 0.005), (1.42, 0.13, 0.1, 0.005), (1.38, 0.2, 0.14, 0.004), (1.32, 0.215, 0.15, 0.006),
                                 (1.22, 0.215, 0.152, 0.008)], shm, 48, folds=(5, 0.006, rng.uniform(0, 6)), cap=False))
        P.append(lathe("collar", [(1.44, 0.056, 0.052, 0.002), (1.47, 0.054, 0.05, 0.002)], M["shirt"], 24))
        for sx in (-1, 1):
            P.append(_sph("shoe", 0.045, (sx * 0.075, -0.07, 0.03), M["boot"], (0.85, 1.6, 0.65)))
        SH = 0.175
    else:
        for sx in (-1, 1):
            P.append(_seg("leg", (sx * 0.095, 0, 0.72), (sx * 0.1, -0.005, 0.09), 0.072, 0.058, M["trouser"]))
            P.append(lathe("boot", [(0.0, 0.05, 0.06, 0), (0.06, 0.055, 0.065, -0.005), (0.13, 0.05, 0.05, 0)], M["boot"], 24))
            P[-1].location = (sx * 0.1, -0.01, 0)
            P.append(_sph("toe", 0.045, (sx * 0.1, -0.075, 0.03), M["boot"], (0.95, 1.4, 0.65)))
        hem = 0.38 if kind == "investigator" else 0.58
        P.append(lathe("coat", [(hem, 0.245, 0.195, 0), (hem + 0.012, 0.25, 0.2, 0), (hem + 0.04, 0.248, 0.198, 0), (0.8, 0.215, 0.165, 0), (1.0, 0.2, 0.14, 0), (1.2, 0.215, 0.14, 0),
                                (1.32, 0.225, 0.14, 0), (1.38, 0.2, 0.125, 0), (1.425, 0.12, 0.09, 0.005), (1.455, 0.062, 0.058, 0.005)],
                       coat, 48, folds=(6, 0.01, rng.uniform(0, 6))))
        def front(zz):
            pr = [(hem, 0.2), (0.8, 0.165), (1.0, 0.14), (1.2, 0.14), (1.32, 0.14), (1.38, 0.125)]
            for (z0, r0), (z1, r1) in zip(pr, pr[1:]):
                if z0 <= zz <= z1: return r0 + (r1 - r0) * (zz - z0) / (z1 - z0)
            return 0.14
        for zz in (0.98, 1.08, 1.18):
            P.append(_sph("button", 0.01, (0.03, -front(zz) - 0.002, zz), M["button"], seg=12, ring=8))
        P.append(lathe("shirtcol", [(1.45, 0.054, 0.05, 0.002), (1.49, 0.05, 0.047, 0.002)], M["shirt"], 24))
        P.append(lathe("collar", [(1.43, 0.075, 0.07, 0.004), (1.475, 0.06, 0.056, 0.004)], coat, 32, cap=False))
        if kind == "investigator":
            P.append(lathe("belt", [(0.975, 0.208, 0.148, 0), (1.025, 0.206, 0.146, 0)], M["trench"], 40))
            P.append(_box("buckle", 0.045, 0.01, 0.035, (0, -0.15, 1.0), M["metal"]))
            for sx in (-1, 1):
                P.append(_box("epaul", 0.09, 0.045, 0.01, (sx * 0.16, 0, 1.4), M["trench"], rot=(0, sx * 0.35, 0)))
        SH = 0.2
    P.append(_cone("neck", 0.049, 0.052, 0.11, (0, 0.006, 1.485), skin, nv=24))
    # ---- руки (плечо — локоть — кисть)
    for sx in (-1, 1):
        S_ = Vector((sx * SH, 0.0, 1.34))
        if sx > 0 and arm_up > 0:
            E = S_ + Vector((sx * 0.03, -0.27 * math.sin(arm_up), -0.27 * math.cos(arm_up)))
            H = E + Vector((0, -0.25 * math.sin(arm_up + 0.35), -0.25 * math.cos(arm_up + 0.35)))
        elif sx > 0 and lantern:
            E = Vector((SH + 0.04, -0.02, 1.07)); H = Vector((0.27, -0.07, 0.82))
        elif sx < 0 and case:
            E = Vector((-SH - 0.05, 0.0, 1.06)); H = Vector((-0.31, -0.02, 0.78))
        elif gun:
            E = Vector((sx * (SH + 0.01), -0.12, 1.1)); H = Vector((0.1, -0.24, 1.05)) if sx > 0 else Vector((-0.1, -0.3, 1.3))
        elif pose == "fold":
            E = Vector((sx * (SH + 0.02), -0.04, 1.08)); H = Vector((sx * 0.03, -0.17, 0.99))
        elif pose == "pocket":
            E = Vector((sx * (SH + 0.05), 0.02, 1.09)); H = Vector((sx * 0.17, -0.1, 0.93))
        else:
            E = Vector((sx * (SH + 0.035), -0.01, 1.07)); H = Vector((sx * (SH + 0.035), -0.06, 0.82))
        P.append(_sph("shoulder", 0.056, S_ + Vector((0, 0, 0.005)), coat, seg=20, ring=12))
        P.append(_seg("uarm", S_, E, 0.056, 0.047, coat, nv=24))
        P.append(_sph("elbow", 0.047, E, coat, seg=20, ring=12))
        P.append(_seg("farm", E, H, 0.047, 0.04, coat, nv=24))
        hid = pose == "pocket" and not ((sx > 0 and (lantern or arm_up)) or (sx < 0 and case) or gun)
        if not hid:
            dr = (H - E).normalized()
            P.append(_cone("cuff", 0.041, 0.041, 0.018, H, M["shirt"], rot=dr.to_track_quat("Z", "Y").to_euler(), nv=16))
            P.append(_sph("hand", 0.038, H + dr * 0.04, skin, (0.75, 0.55, 1.2), rot=dr.to_track_quat("Z", "Y").to_euler(), seg=20, ring=12))
            P.append(_sph("thumb", 0.014, H + dr * 0.03 + Vector((-sx * 0.0, -0.025, 0)), skin, (0.8, 0.8, 1.6),
                          rot=dr.to_track_quat("Z", "Y").to_euler(), seg=12, ring=8))
    # ---- голова (на шарнире шеи)
    hd = bpy.data.objects.new("headpivot", None); bpy.context.scene.collection.objects.link(hd)
    hd.location = (0, 0, 1.47)
    HP = []
    _head(HP, M, kind, fem, old, child, beard, hair_m, rng)
    for o in HP:
        o.location = o.location - Vector((0, 0, 1.47)); o.parent = hd
    hs = 1.18 if child else 1.0
    hd.scale = (hs, hs, hs)
    pitch, yaw = head if head is not None else (rng.uniform(-0.06, 0.1), rng.uniform(-0.25, 0.25))
    hd.rotation_euler = (pitch, rng.uniform(-0.04, 0.04), yaw)
    P.append(hd)
    # ---- предметы
    if lantern:
        P.append(_cone("lantern", 0.06, 0.055, 0.17, (0.3, -0.07, 0.64), M["lamp"]))
        P.append(_cone("lanterncap", 0.07, 0.02, 0.06, (0.3, -0.07, 0.75), M["metal"]))
        P.append(_seg("handle", (0.27, -0.07, 0.78), (0.33, -0.07, 0.78), 0.005, 0.005, M["metal"], nv=6))
        L = bpy.data.lights.new("lan", "POINT"); L.energy = 35; L.color = _srgb("#ffa850"); L.shadow_soft_size = 0.05
        lo = bpy.data.objects.new("lan", L); bpy.context.scene.collection.objects.link(lo)
        lo.location = (0.3, -0.17, 0.66); P.append(lo)
    if gun:
        P.append(_seg("gun", (0.2, -0.2, 0.86), (-0.2, -0.32, 1.52), 0.02, 0.014, M["wood"], nv=10))
        P.append(_seg("barrel", (-0.05, -0.28, 1.27), (-0.26, -0.33, 1.62), 0.011, 0.011, M["metal"], nv=8))
    if case:
        P.append(_box("case", 0.1, 0.4, 0.29, (-0.37, -0.02, 0.58), M["case"]))
        P.append(_seg("caseh", (-0.37, -0.08, 0.745), (-0.37, 0.04, 0.745), 0.008, 0.008, M["boot"], nv=6))
    for o in P:
        o.location = Vector(o.location) * k
        if o.type != "LIGHT": o.scale = Vector(o.scale) * k
        o.parent = root
    root.location = (x, y, z); root.rotation_euler = (0, 0, face); root.scale = (sc, sc, sc)
    root["head_z"] = 1.6 * k * sc
    return root
