"""Люди 1920-х для «Тёмного кино» (v2): общий модуль для hk3d.py и sets3d.py.

Что изменилось против v1:
  * пропорции: покатые плечи с трапецией, короткая шея, руки растут из плеча, а не висят рядом;
  * дети с детскими пропорциями (голова 1/4.5 у Йозефа, 1/5.7 у Цецилии), круглые лица;
  * лицо: крупнее глаза с цветной радужкой и бликом, тяжёлое верхнее веко, дуги бровей,
    тонкие губы, румянец/тени через цвет вершин, морщины и впалые щёки у стариков;
  * волосы — оболочка по черепу с линией роста (прямой пробор у женщин), пряди в материале;
    платок завязан под подбородком; борода — оболочка по нижней части лица, с проседью;
  * одежда: отвороты пиджака, жилет, рубашка и галстук; у женщин крест-накрест Brusttuch с вырезом;
    шляпа сидит на голове; у Йозефа — детский Kittel;
  * позы: перенос веса, сутулость у пожилых, кисти крупнее, большой палец.

person(x, y, z, face, kind, ...) -> root (Empty); все части — его потомки.
Лицо смотрит в -Y локально; face поворачивает фигуру вокруг Z.
"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix

_MATFN = None          # matfn(name, rgb_linear, rough, bump, bump_scale) -> Material
_M = {}

def setup(matfn):
    global _MATFN
    _MATFN = matfn

def _srgb(h):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c)

def _P(m):
    return m.node_tree.nodes.get("Principled BSDF")

def _mk(name, hexc, rough, bump=0.0, bs=40.0, sss=0.0, emit=None, es=0.0, mottle=0.0, spec=None):
    m = _MATFN(name, _srgb(hexc), rough, bump, bs)
    p = _P(m)
    if p:
        if sss:
            p.inputs["Subsurface Weight"].default_value = sss
            p.inputs["Subsurface Radius"].default_value = (1.0, 0.42, 0.25)
            p.inputs["Subsurface Scale"].default_value = 0.006
        if emit:
            p.inputs["Emission Color"].default_value = (*_srgb(emit), 1)
            p.inputs["Emission Strength"].default_value = es
        if spec is not None:
            p.inputs["Specular IOR Level"].default_value = spec
        if mottle:
            _mottle(m, mottle)
    return m

def _mottle(m, amt, scale=7.0):
    """Неровный цвет ткани: крупный шум затемняет/осветляет базовый цвет."""
    nt = m.node_tree; N = nt.nodes; L = nt.links; p = _P(m)
    src = p.inputs["Base Color"].links[0].from_socket if p.inputs["Base Color"].links else None
    base = tuple(p.inputs["Base Color"].default_value)
    tc = N.new("ShaderNodeTexCoord"); nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale; nz.inputs["Detail"].default_value = 3.0
    L.new(tc.outputs["Object"], nz.inputs["Vector"])
    mr = N.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = 1 - amt; mr.inputs["To Max"].default_value = 1 + amt * 0.6
    mr.inputs["From Min"].default_value = 0.3; mr.inputs["From Max"].default_value = 0.7
    L.new(nz.outputs["Fac"], mr.inputs["Value"])
    mx = N.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"
    mx.inputs["Factor"].default_value = 1.0
    if src is not None: L.new(src, mx.inputs[6])
    else: mx.inputs[6].default_value = base
    L.new(mr.outputs["Result"], mx.inputs[7])
    L.new(mx.outputs[2], p.inputs["Base Color"])

def _tinted(m, wrinkles=False, wscale=150.0):
    """Цвет вершин 'tint' умножает базовый цвет (румянец, тени глазниц, щетина);
    альфа того же атрибута — маска морщин (волнистый бамп)."""
    nt = m.node_tree; N = nt.nodes; L = nt.links; p = _P(m)
    base = tuple(p.inputs["Base Color"].default_value)
    at = N.new("ShaderNodeAttribute"); at.attribute_name = "tint"
    mx = N.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"
    mx.inputs["Factor"].default_value = 1.0
    if p.inputs["Base Color"].links: L.new(p.inputs["Base Color"].links[0].from_socket, mx.inputs[6])
    else: mx.inputs[6].default_value = base
    L.new(at.outputs["Color"], mx.inputs[7]); L.new(mx.outputs[2], p.inputs["Base Color"])
    if wrinkles:
        tc = N.new("ShaderNodeTexCoord"); wv = N.new("ShaderNodeTexWave")
        wv.wave_type = "BANDS"; wv.bands_direction = "Z"; wv.inputs["Scale"].default_value = wscale
        wv.inputs["Distortion"].default_value = 3.0; wv.inputs["Detail"].default_value = 1.5
        L.new(tc.outputs["Object"], wv.inputs["Vector"])
        mul = N.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
        L.new(wv.outputs["Fac"], mul.inputs[0]); L.new(at.outputs["Alpha"], mul.inputs[1])
        b = N.new("ShaderNodeBump"); b.inputs["Strength"].default_value = 0.6; b.inputs["Distance"].default_value = 0.002
        L.new(mul.outputs[0], b.inputs["Height"])
        if p.inputs["Normal"].links:
            L.new(p.inputs["Normal"].links[0].from_socket, b.inputs["Normal"])
        L.new(b.outputs["Normal"], p.inputs["Normal"])
    return m

def _strands(m, scale=220.0, direction="X", strength=0.25):
    """Пряди: полосы по направлению причёски."""
    nt = m.node_tree; N = nt.nodes; L = nt.links; p = _P(m)
    tc = N.new("ShaderNodeTexCoord"); wv = N.new("ShaderNodeTexWave")
    wv.wave_type = "BANDS"; wv.bands_direction = direction; wv.inputs["Scale"].default_value = scale
    wv.inputs["Distortion"].default_value = 6.0; wv.inputs["Detail"].default_value = 3.0
    wv.inputs["Detail Scale"].default_value = 2.0
    L.new(tc.outputs["Object"], wv.inputs["Vector"])
    b = N.new("ShaderNodeBump"); b.inputs["Strength"].default_value = strength; b.inputs["Distance"].default_value = 0.002
    L.new(wv.outputs["Fac"], b.inputs["Height"]); L.new(b.outputs["Normal"], p.inputs["Normal"])
    base = tuple(p.inputs["Base Color"].default_value)
    mr = N.new("ShaderNodeMapRange"); mr.inputs["To Min"].default_value = 0.88; mr.inputs["To Max"].default_value = 1.06
    L.new(wv.outputs["Fac"], mr.inputs["Value"])
    mx = N.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"; mx.inputs["Factor"].default_value = 1.0
    mx.inputs[6].default_value = base; L.new(mr.outputs["Result"], mx.inputs[7]); L.new(mx.outputs[2], p.inputs["Base Color"])
    return m

def _salt(m, grey_hex, amt):
    """Проседь: шум смешивает основной цвет волос с седым."""
    nt = m.node_tree; N = nt.nodes; L = nt.links; p = _P(m)
    src = p.inputs["Base Color"].links[0].from_socket if p.inputs["Base Color"].links else None
    tc = N.new("ShaderNodeTexCoord"); nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 900.0; nz.inputs["Detail"].default_value = 1.0
    L.new(tc.outputs["Object"], nz.inputs["Vector"])
    r = N.new("ShaderNodeMapRange"); r.inputs["From Min"].default_value = 0.62 - amt * 0.3; r.inputs["From Max"].default_value = 0.66 - amt * 0.3
    L.new(nz.outputs["Fac"], r.inputs["Value"])
    mx = N.new("ShaderNodeMix"); mx.data_type = "RGBA"
    if src is not None: L.new(src, mx.inputs[6])
    else: mx.inputs[6].default_value = tuple(p.inputs["Base Color"].default_value)
    mx.inputs[7].default_value = (*_srgb(grey_hex), 1)
    L.new(r.outputs["Result"], mx.inputs["Factor"]); L.new(mx.outputs[2], p.inputs["Base Color"])
    return m

def mats():
    if not _M:
        _M.update(
            skin=_mk("fg_skin", "#9c7a66", 0.62, 0.03, 500, sss=0.25, spec=0.35),
            face=_tinted(_mk("fg_face", "#9c7a66", 0.6, 0.03, 500, sss=0.25, spec=0.35)),
            face_old=_tinted(_mk("fg_face_old", "#9c7561", 0.66, 0.06, 420, sss=0.2, spec=0.3), wrinkles=True),
            skin_old=_mk("fg_skin_old", "#9c7561", 0.66, 0.06, 420, sss=0.2, spec=0.3),
            lip=_mk("fg_lip", "#8a5648", 0.5, sss=0.2),
            mouth=_mk("fg_mouth", "#2a1511", 0.8),
            ewhite=_mk("fg_ewhite", "#b9b2a6", 0.12, spec=0.6),
            iris_br=_mk("fg_iris_br", "#4a3020", 0.1, spec=0.6),
            iris_bl=_mk("fg_iris_bl", "#4d6070", 0.1, spec=0.6),
            iris_gr=_mk("fg_iris_gr", "#4f5540", 0.1, spec=0.6),
            pupil=_mk("fg_pupil", "#050404", 0.05, spec=0.7),
            hair=_strands(_mk("fg_hair", "#2e2018", 0.55, 0.0, 260)),
            hair_m=_strands(_salt(_mk("fg_hair_m", "#3a2a1f", 0.55), "#8d877f", 0.35)),
            hair_blond=_strands(_mk("fg_hair_bl", "#7a5c36", 0.55)),
            hair_toddler=_strands(_mk("fg_hair_td", "#8a6c44", 0.6), strength=0.15),
            grey=_strands(_salt(_mk("fg_grey", "#8e8a84", 0.6), "#c9c5be", 0.5)),
            beard=_strands(_salt(_mk("fg_beard", "#3b2b20", 0.8), "#8a857d", 0.3), scale=300, direction="Z", strength=0.35),
            coat=_mk("fg_coat", "#1e1c20", 0.88, 0.35, 60, mottle=0.12),
            coat2=_mk("fg_coat2", "#2e2621", 0.88, 0.35, 60, mottle=0.12),
            loden=_mk("fg_loden", "#2e3428", 0.92, 0.45, 70, mottle=0.15),
            jacket_br=_mk("fg_jacket_br", "#3a2c22", 0.9, 0.4, 65, mottle=0.15),
            trench=_mk("fg_trench", "#544a3b", 0.82, 0.3, 50, mottle=0.1),
            vest=_mk("fg_vest", "#26221f", 0.85, 0.3, 80, mottle=0.1),
            trouser=_mk("fg_trouser", "#24221f", 0.88, 0.3, 60, mottle=0.1),
            skirt=_mk("fg_skirt", "#3c2624", 0.92, 0.35, 45, mottle=0.12),
            skirt2=_mk("fg_skirt2", "#272b35", 0.92, 0.35, 45, mottle=0.12),
            skirt3=_mk("fg_skirt3", "#2b2a26", 0.92, 0.35, 45, mottle=0.12),
            apron=_mk("fg_apron", "#6e675a", 0.92, 0.3, 70, mottle=0.1),
            apron2=_mk("fg_apron2", "#4c5462", 0.92, 0.3, 70, mottle=0.1),
            apron3=_mk("fg_apron3", "#5e4a3e", 0.92, 0.3, 70, mottle=0.1),
            kittel=_mk("fg_kittel", "#5a5f52", 0.92, 0.3, 70, mottle=0.1),
            scarf=_mk("fg_scarf", "#2f2b34", 0.9, 0.35, 55, mottle=0.12),
            scarf2=_mk("fg_scarf2", "#4d302b", 0.9, 0.35, 55, mottle=0.12),
            scarf3=_mk("fg_scarf3", "#3d3a2f", 0.9, 0.35, 55, mottle=0.12),
            shirt=_mk("fg_shirt", "#a59c8c", 0.75, 0.2, 80),
            tie=_mk("fg_tie", "#2b1515", 0.6),
            stocking=_mk("fg_stock", "#1d1a19", 0.85, 0.2, 90),
            boot=_mk("fg_boot", "#100e0d", 0.42),
            hat=_mk("fg_hat", "#1b1918", 0.82, 0.3, 90, mottle=0.08),
            hat2=_mk("fg_hat2", "#3b352d", 0.82, 0.3, 90, mottle=0.08),
            button=_mk("fg_button", "#0c0b0a", 0.3),
            metal=_mk("fg_metal", "#151515", 0.35),
            wood=_mk("fg_wood", "#3a2618", 0.6),
            case=_mk("fg_case", "#3d2a1c", 0.55, 0.3, 30),
            lamp=_mk("fg_lamp", "#ffc070", 0.3, emit="#ffa040", es=25.0),
        )
    return _M

# ---------------------------------------------------------------- примитивы
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

def _mesh(n, verts, faces, m, smooth=True, subsurf=0):
    me = bpy.data.meshes.new(n); me.from_pydata(verts, [], faces); me.update()
    o = bpy.data.objects.new(n, me); bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(m)
    if smooth: _smooth(o)
    if subsurf:
        sd = o.modifiers.new("sub", "SUBSURF"); sd.levels = subsurf; sd.render_levels = subsurf
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

def _lathe(n, prof, m, nv=48, folds=None, cap=True, sub=1):
    """Токарный профиль: [(z, rx, ry, сдвиг y)]."""
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
    o = _mesh(n, verts, faces, m, subsurf=sub)
    if folds: _fold(o, *folds)
    return o

def _lathe_open(n, prof, m, delta, nv=64, sub=1):
    """Токарный профиль, разомкнутый спереди: на высоте z угол выреза delta(z, rx)."""
    verts, faces = [], []
    for (zz, rx, ry, yo) in prof:
        d = delta(zz, rx)
        for j in range(nv + 1):
            th = -math.pi / 2 + d + (2 * math.pi - 2 * d) * j / nv
            verts.append((rx * math.cos(th), ry * math.sin(th) + yo, zz))
    for i in range(len(prof) - 1):
        for j in range(nv):
            a0 = i * (nv + 1) + j
            faces.append((a0, a0 + 1, a0 + nv + 2, a0 + nv + 1))
    return _mesh(n, verts, faces, m, subsurf=sub)

def _prof_at(prof, zz):
    """(rx, ry, yo) профиля на высоте zz."""
    if zz <= prof[0][0]: return prof[0][1:]
    for a, b in zip(prof, prof[1:]):
        if a[0] <= zz <= b[0]:
            t = (zz - a[0]) / max(b[0] - a[0], 1e-9)
            return tuple(a[i] + (b[i] - a[i]) * t for i in (1, 2, 3))
    return prof[-1][1:]

def _front_y(prof, x, zz):
    rx, ry, yo = _prof_at(prof, zz)
    q = 1 - (x / rx) ** 2
    return yo - ry * math.sqrt(max(q, 0.0))

def _delete_verts(o, pred):
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if pred(v.co)], context="VERTS")
    bm.to_mesh(o.data); bm.free(); o.data.update()
    return o

def _solidify(o, t, off=1.0):
    s = o.modifiers.new("sol", "SOLIDIFY"); s.thickness = t; s.offset = off
    # subsurf после solidify
    for md in list(o.modifiers):
        if md.type == "SUBSURF":
            lv = md.levels; o.modifiers.remove(md)
            sd = o.modifiers.new("sub", "SUBSURF"); sd.levels = lv; sd.render_levels = lv
    return o

def _bake(o, S):
    """Перенести трансформ объекта в меш и сжать/растянуть (для детских пропорций)."""
    if o.type != "MESH": return
    o.data.transform(o.matrix_basis)
    o.matrix_basis = Matrix.Identity(4)
    o.data.transform(S)
    o.data.update()

# ---------------------------------------------------------------- лицо
def _g(x, z, cx, cz, sx, sz):
    return math.exp(-((x - cx) ** 2) / (2 * sx * sx) - ((z - cz) ** 2) / (2 * sz * sz))

def _sm(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a))); return t * t * (3 - 2 * t)

FACE = {   # индивидуальные черты
    "man": dict(jaw=1.04, nose=1.05, cheek=1.0, chin=1.0, brow=1.0, lips=0.9, eye=1.0),
    "old": dict(jaw=1.0, nose=1.15, cheek=1.15, chin=0.85, brow=1.2, lips=0.75, eye=0.95, sunk=1.0),
    "investigator": dict(jaw=1.08, nose=1.0, cheek=0.9, chin=1.2, brow=1.05, lips=0.85, eye=1.0),
    "woman": dict(jaw=0.9, nose=0.85, cheek=1.0, chin=0.75, brow=0.6, lips=1.0, eye=1.04),
    "maid": dict(jaw=0.94, nose=0.95, cheek=1.15, chin=0.8, brow=0.65, lips=0.9, eye=1.0),
    "old_woman": dict(jaw=0.92, nose=1.05, cheek=1.2, chin=0.65, brow=0.75, lips=0.6, eye=0.94, sunk=1.4),
    "girl": dict(jaw=1.0, nose=0.5, cheek=1.35, chin=0.45, brow=0.35, lips=0.8, eye=1.18, child=1),
    "boy": dict(jaw=1.05, nose=0.42, cheek=1.5, chin=0.35, brow=0.3, lips=0.75, eye=1.22, child=1),
}
RX, RY, RZ = 0.077, 0.098, 0.118

def _head_mesh(name, m, f, old, male, beard):
    """Цельная голова + цвет вершин tint (румянец, тени, щетина; альфа = морщины)."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0, 0, 0), segments=96, ring_count=72)
    o = bpy.context.active_object; o.name = name; o.data.materials.append(m)
    me = o.data
    ca = me.color_attributes.new("tint", "FLOAT_COLOR", "POINT")
    child = f.get("child", 0)
    fz = -0.012 if child else 0.0           # у детей черты лица ниже (большой лоб)
    sunk = f.get("sunk", 0.0) if old else 0.0
    for v in me.vertices:
        dx, dy, dz = v.co.x, v.co.y, v.co.z
        x, y, z = dx * RX, dy * RY, dz * RZ
        if child:
            x *= 1.04; y *= 0.98
        if dz < 0:
            z *= 0.86 if not child else 0.8
            x *= 1 - (0.2 / f["jaw"] - 0.02) * (-dz) ** 1.8 * (0.7 if child else 1.0)
            if dy > 0: y *= 1 - 0.45 * (-dz) ** 1.3
        if dy < 0: y *= 0.93
        w = max(0.0, min(1.0, (-dy - 0.25) / 0.35))
        r = g = b = 1.0; wr = 0.0
        if w > 0:
            d = 0.0
            zf = z - fz
            if -0.044 < zf < 0.02:
                t = (0.02 - zf) / 0.05
                A = (0.006 + 0.019 * t ** 1.4) * f["nose"]
                if zf < -0.03: A *= max(0.0, 1 - (-0.03 - zf) / 0.011)
                sxn = 0.008 + 0.007 * t
                d += A * math.exp(-x * x / (2 * sxn * sxn))
            for sx in (-1, 1):
                d += 0.0065 * f["nose"] * _g(x, zf, sx * 0.015, -0.034, 0.007, 0.006)
                d += 0.0065 * f["brow"] * _g(x, zf, sx * 0.031, 0.03, 0.022, 0.009)
                d -= 0.0095 * _g(x, zf, sx * 0.032, 0.011, 0.013, 0.010)
                d += 0.0055 * f["cheek"] * _g(x, zf, sx * 0.05, -0.016, 0.016, 0.016)
                if sunk:
                    d -= 0.004 * sunk * _g(x, zf, sx * 0.047, -0.045, 0.012, 0.012)    # впалые щёки
                    d -= 0.0028 * sunk * _g(x, zf, sx * 0.026, -0.047, 0.0028, 0.012)  # носогубные
                    d += 0.0018 * sunk * _g(x, zf, sx * 0.042, -0.075, 0.01, 0.008)    # брыли
                    d -= 0.0016 * sunk * _g(x, zf, sx * 0.03, -0.004, 0.012, 0.004)    # мешки под глазами (тень)
            lip = f.get("lips", 1.0)
            d += 0.004 * lip * _g(x, zf, 0, -0.05, 0.018, 0.0045)
            d += 0.0045 * lip * _g(x, zf, 0, -0.0615, 0.015, 0.005)
            d -= 0.0035 * _g(x, zf, 0, -0.0558, 0.02, 0.0015)
            d -= 0.0025 * _g(x, zf, 0, -0.071, 0.016, 0.0045)
            d += 0.0065 * f["chin"] * _g(x, zf, 0, -0.086, 0.017, 0.011)
            y -= d * w
            # ---- цвет: румянец, кончик носа, тени глазниц, губы
            red = 0.0
            for sx in (-1, 1):
                red += (0.55 if child else 0.32) * _g(x, zf, sx * 0.047, -0.025, 0.017, 0.016)
                sock = _g(x, zf, sx * 0.031, 0.008, 0.016, 0.012)
                r -= 0.16 * sock; g -= 0.2 * sock; b -= 0.16 * sock
                if old:
                    u = _g(x, zf, sx * 0.03, -0.006, 0.014, 0.006)
                    r -= 0.12 * u; g -= 0.16 * u; b -= 0.1 * u
            red += 0.3 * _g(x, zf, 0, -0.03, 0.009, 0.01)
            red += 0.45 * _g(x, zf, 0, -0.056, 0.016, 0.009)
            r += 0.08 * red * w; g -= 0.07 * red * w; b -= 0.07 * red * w
            if old: wr = max(wr, _sm(0.045, 0.06, zf) * (1 - _sm(0.085, 0.1, zf)) * (1 - _sm(0.04, 0.06, abs(x))))
        if male and not beard and z < -0.035:          # след бритья
            k = _sm(-0.035, -0.06, z) * (1 - _g(x, z - fz, 0, -0.056, 0.02, 0.012))
            r -= 0.07 * k; g -= 0.06 * k; b -= 0.03 * k
        v.co = (x, y, z)
        ca.data[v.index].color = (max(r, 0), max(g, 0), max(b, 0), wr)
    for pg in me.polygons: pg.use_smooth = True
    return o

def _surf_y(x, z, child=False):
    """Передняя поверхность базового эллипсоида (без рельефа) в точке (x, z)."""
    if z < 0: z = z / (0.8 if child else 0.86)
    rx = RX * (1.04 if child else 1.0)
    q = 1 - (x / rx) ** 2 - (z / RZ) ** 2
    return -RY * 0.93 * (0.98 if child else 1.0) * math.sqrt(max(q, 0.0))

# линия роста волос: таблица (|азимут|, z), азимут 0 = лицо, pi = затылок
HAIRLINE = {
    "man":  [(0.0, 0.064), (0.45, 0.06), (0.75, 0.05), (1.05, -0.03), (1.3, -0.02), (1.45, 0.032), (1.75, 0.032), (2.0, -0.07), (3.2, -0.075)],
    "fem":  [(0.0, 0.068), (0.35, 0.058), (0.7, 0.04), (1.05, 0.005), (1.35, -0.005), (1.75, -0.01), (2.1, -0.05), (3.2, -0.06)],
    "girl": [(0.0, 0.07), (0.35, 0.062), (0.7, 0.045), (1.05, 0.0), (1.35, -0.02), (1.75, -0.03), (2.1, -0.07), (3.2, -0.08)],
    "toddler": [(0.0, 0.074), (0.5, 0.066), (0.9, 0.04), (1.3, 0.02), (1.75, 0.02), (2.1, -0.04), (3.2, -0.05)],
    "tuch": [(0.0, 0.058), (0.5, 0.05), (0.85, 0.02), (1.0, -0.06), (1.15, -0.105), (3.2, -0.11)],
}

def _hl(tab, a):
    a = abs(a)
    for (a0, z0), (a1, z1) in zip(tab, tab[1:]):
        if a0 <= a <= a1:
            t = _sm(0, 1, (a - a0) / (a1 - a0)); return z0 + (z1 - z0) * t
    return tab[-1][1]

def _shell(name, m, tab, off, thick, sx=1.0, sy=1.0, sz=1.0, yo=0.0, zo=0.0, part=0.0, child=False, bulk=None):
    """Оболочка по черепу (волосы, платок) с вырезом по линии роста."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0, 0, 0), segments=120, ring_count=80)
    o = bpy.context.active_object; o.name = name; o.data.materials.append(m)
    cx = 1.04 if child else 1.0
    for v in o.data.vertices:
        dx, dy, dz = v.co.x, v.co.y, v.co.z
        x, y, z = dx * (RX * cx + off) * sx, dy * (RY + off) * sy, dz * (RZ + off) * sz
        if dz < 0: z *= 0.86
        if dy < 0: y *= 0.93
        if part and dy < 0.4 and dz > 0.6:      # пробор: ложбинка по центру
            y += 0; z -= part * math.exp(-(dx * dx) / (2 * 0.05 ** 2)) * _sm(0.6, 0.9, dz)
        if bulk:
            x, y, z = bulk(x, y, z, dx, dy, dz)
        v.co = (x, y + yo, z + zo)
    def cut(co):
        az = math.atan2(co.x, -(co.y - yo))
        return co.z - zo < _hl(tab, az)
    _delete_verts(o, cut)
    _smooth(o)
    _solidify(o, thick, 1.0)
    sd = o.modifiers.new("sub", "SUBSURF"); sd.levels = 1; sd.render_levels = 1
    return o

def _head(P, M, kind, fem, old, child, beard, hair_m, rng, eye_m, opts):
    """Голова с центром (0,0,H). Части в локальных координатах фигуры."""
    f = dict(FACE.get(kind, FACE["man"])); f.update(opts.get("face", {}))
    male = not fem and not child
    fm = M["face_old"] if old else M["face"]
    sk = M["skin_old"] if old else M["skin"]
    A = P.append
    H = 1.585
    hm = _head_mesh("head", fm, f, old, male, beard); hm.location = (0, 0, H); A(hm)
    if fem and not child: hm.scale = (1, 1, 0.96)
    fz = -0.012 if child else 0.0
    es = f.get("eye", 1.0)
    for sx in (-1, 1):
        ex, ez = sx * (0.031 if not child else 0.03), 0.011 + fz
        re = 0.0118 * es
        ey = _surf_y(ex, ez, child) + 0.0098 * 0.93 + 0.0022
        A(_sph("eye", re, (ex, ey, H + ez), M["ewhite"], seg=32, ring=20))
        A(_sph("iris", re * 0.62, (ex, ey - re * 0.8, H + ez - 0.0006), eye_m, (1, 0.42, 1), seg=24, ring=14))
        A(_sph("pupil", re * 0.3, (ex, ey - re * 0.99, H + ez - 0.0006), M["pupil"], (1, 0.3, 1), seg=16, ring=10))
        drop = 0.0012 if old else 0.0
        A(_sph("lid", re * 1.09, (ex, ey + 0.0006, H + ez + re * (0.5 if child else 0.36) - drop), sk, (1.08, 1.0, 0.62), rot=(-0.12, sx * 0.08, 0), seg=28, ring=16))
        A(_sph("lowlid", re * 1.05, (ex, ey + 0.0012, H + ez - re * 0.52), sk, (1.05, 1.0, 0.38), seg=24, ring=12))
        # брови: три сплющенных капли по дуге надбровья
        bw = (0.85 if fem else 1.15) * (0.6 if child else 1.0)
        for i, (bx, bz, br) in enumerate([(0.017, 0.029, 0.0068), (0.031, 0.031, 0.0064), (0.044, 0.028, 0.0048)]):
            zz = bz + fz + (0.002 if fem else 0.0) - (0.002 if old and i == 2 else 0.0)
            yy = _surf_y(sx * bx, zz, child) - 0.0065 * f["brow"] * math.exp(-((bx - 0.031) ** 2) / (2 * 0.022 ** 2)) + 0.0012
            A(_sph("brow", br * 1.35, (sx * bx, yy, H + zz), hair_m if not old else M["grey"],
                   (1.6, 0.4, 0.42 * bw), rot=(0, sx * (0.06 - 0.12 * i), 0), seg=14, ring=8))
    lip = f.get("lips", 1.0)
    uy = _surf_y(0, -0.05 + fz, child) - 0.004 * lip
    ly = _surf_y(0, -0.0615 + fz, child) - 0.0045 * lip
    A(_sph("ulip", 0.0155, (0, uy + 0.0036, H - 0.0505 + fz), M["lip"], (1.15, 0.28, 0.24 * lip + 0.05), seg=24, ring=12))
    A(_sph("llip", 0.0145, (0, ly + 0.0038, H - 0.0615 + fz), M["lip"], (1.0, 0.3, 0.3 * lip + 0.05), seg=24, ring=12))
    A(_sph("mouth", 0.0185, (0, _surf_y(0, -0.0558 + fz, child) - 0.0008, H - 0.0558 + fz), M["mouth"], (1.12, 0.14, 0.04), seg=24, ring=10))
    for sx in (-1, 1):
        ear = _sph("ear", 0.026, (sx * 0.076, 0.012, H - 0.006), sk, (0.3, 0.66, 1.05), rot=(0, 0, sx * 0.3), seg=20, ring=12)
        A(ear)
        A(_sph("earin", 0.016, (sx * 0.0795, 0.009, H - 0.006), M["mouth"], (0.12, 0.55, 0.8), rot=(0, 0, sx * 0.3), seg=12, ring=8))
    # ---- волосы
    hat = opts.get("hat", male)
    if kind in ("maid", "old_woman"):
        sc_m = opts.get("scarf_m") or (M["scarf2"] if kind == "maid" else M["scarf"])
        hl_m = hair_m if kind == "maid" else M["grey"]
        A(_shell("hairline", hl_m, HAIRLINE["fem"], 0.002, 0.006, part=0.004))
        def puff(x, y, z, dx, dy, dz):     # платок свободнее на затылке
            k = max(0.0, dy) * 0.006 + max(0.0, dz) * 0.002
            return x * (1 + k * 4), y + k, z + k * 0.5
        A(_shell("kopftuch", sc_m, HAIRLINE["tuch"], 0.012, 0.004, zo=0.004, bulk=puff))
        # узел под подбородком и концы
        A(_sph("knot", 0.016, (0, -0.045, H - 0.112), sc_m, (1.3, 0.9, 0.8)))
        for s in (-1, 1):
            A(_seg("tail", (s * 0.008, -0.05, H - 0.118), (s * 0.03, -0.075, H - 0.2), 0.012, 0.006, sc_m, nv=10))
    elif fem or kind == "girl":
        tab = HAIRLINE["girl" if child else "fem"]
        A(_shell("hair", hair_m, tab, 0.003, 0.006, part=0.005, child=child))
        if kind == "woman":
            A(_sph("bun", 0.04, (0, 0.108, H - 0.005), hair_m, (1.05, 0.8, 0.85)))
            for s in (-1, 1):
                A(_sph("roll", 0.03, (s * 0.06, 0.03, H + 0.04), hair_m, (0.5, 1.3, 0.7), rot=(0.3, 0, s * 0.2)))
        if kind == "girl":
            for s in (-1, 1):
                A(_seg("braid", (s * 0.05, 0.06, H - 0.04), (s * 0.06, 0.04, H - 0.25), 0.017, 0.011, hair_m, nv=10))
                for i in range(5):
                    t = (i + 0.5) / 5
                    A(_sph("braidk", 0.016 - 0.004 * t, (s * (0.05 + 0.01 * t), 0.06 - 0.02 * t, H - 0.04 - 0.21 * t), hair_m, (1, 1, 1.4), seg=10, ring=6))
                A(_sph("ribbon", 0.014, (s * 0.06, 0.04, H - 0.255), M["scarf2"], (1.5, 0.6, 0.7), seg=12, ring=8))
    elif kind == "boy":
        A(_shell("hair", hair_m, HAIRLINE["toddler"], 0.003, 0.006, child=True))
    else:
        A(_shell("hair", hair_m, HAIRLINE["man"], 0.002, 0.005))
    if male:
        bm_ = M["beard"] if (old or beard) else hair_m
        if beard:
            def full(x, y, z, dx, dy, dz):
                k = _sm(-0.02, -0.1, z)
                return x * (1 + 0.08 * k), y - 0.012 * k * max(0, -dy), z - 0.03 * k * k
            bd = _shell("beard", M["beard"], [(0.0, -1.0), (3.2, -1.0)], 0.003, 0.008, bulk=full)
            def bcut(co):
                az = abs(math.atan2(co.x, -co.y))
                top = -0.038 if az < 0.7 else (-0.038 + 0.05 * _sm(0.7, 1.35, az))
                mouth = False
                return co.z > top or az > 1.7 or mouth
            # оболочка уже с solidify: вырезаем по базовой сетке
            for md in list(bd.modifiers): bd.modifiers.remove(md)
            _delete_verts(bd, bcut)
            _solidify(bd, 0.009, 1.0)
            sd = bd.modifiers.new("sub", "SUBSURF"); sd.levels = 1; sd.render_levels = 1
            bd.location = (0, 0, H); A(bd)
        if beard or opts.get("moustache", kind in ("man", "old")):
            for s in (-1, 1):
                A(_sph("moustache", 0.016, (s * 0.011, _surf_y(0.01, -0.045) - 0.006, H - 0.046), bm_,
                       (1.25, 0.55, 0.42), rot=(0, s * 0.35, 0), seg=16, ring=10))
        if hat:
            hat_m = M["hat"] if kind != "investigator" else M["hat2"]
            bz = H + 0.062
            tilt = (-0.06, 0, 0)
            A(_cone("brim", 0.152 if kind != "investigator" else 0.162, 0.143, 0.01, (0, 0.012, bz), hat_m, rot=tilt, nv=56, sc=(0.94, 1.1, 1)))
            # тулья с вмятиной сверху (федора / баварская шляпа)
            cr = _cone("crown", 0.088, 0.08, 0.1, (0, 0.012, bz + 0.052), hat_m, rot=tilt, nv=48, sc=(0.93, 1.12, 1))
            bv = cr.modifiers.new("bev", "BEVEL"); bv.width = 0.008; bv.segments = 3
            A(cr)
            A(_cone("band", 0.0895, 0.088, 0.02, (0, 0.012, bz + 0.016), M["boot"], rot=tilt, nv=48, sc=(0.93, 1.12, 1)))
    # хвост объектов: голова мужчины без шляпы — ничего; у шляпы волосы под ней видны по бокам
    for o in P:
        if o.name.startswith(("hair", "kopftuch", "beard")) and o.location.z == 0:
            o.location = (0, 0, H)

# ---------------------------------------------------------------- фигура
CHILD = {   # (высота, ширина тела, масштаб головы) — пропорции детей
    "girl": (0.67, 0.72, 0.9),
    "boy": (0.455, 0.62, 0.86),
}

def person(x, y, z, face=0.0, kind="man", sc=1.0, lantern=False, gun=False, case=False, arm_up=0.0,
           beard=False, seed=None, head=None, pose=None, **opts):
    """opts: coat='loden'|..., hair='hair'|..., eyes='br'|'bl'|'gr', build=1.0, stoop=0.0, lean=0.0,
    skirt=..., apron=..., scarf=..., hat=True/False, moustache=True/False."""
    M = mats()
    rng = random.Random(seed if seed is not None else int(abs(x * 131 + y * 17) * 10))
    root = bpy.data.objects.new("person", None); bpy.context.scene.collection.objects.link(root)
    P = []
    child = kind in ("girl", "boy")
    toddler = kind == "boy"
    fem = kind in ("woman", "maid", "old_woman", "girl")
    old = kind in ("old", "old_woman")
    hair_m = M[opts["hair"]] if "hair" in opts else (
        M["grey"] if kind == "old_woman" else M["hair_m"] if kind == "old" else
        M["hair_toddler"] if toddler else M["hair_blond"] if kind == "girl" else M["hair"])
    eye_m = M["iris_" + opts.get("eyes", rng.choice(["br", "br", "bl", "gr"]))]
    coat = M[opts["coat"]] if "coat" in opts else {
        "investigator": M["trench"], "woman": M["coat2"], "maid": M["coat2"], "old_woman": M["coat"],
        "old": M["loden"], "girl": M["coat2"], "boy": M["kittel"]}.get(kind, M["coat"])
    build = opts.get("build", 1.0)
    if pose is None:
        pose = "fold" if (fem and not case and not toddler and rng.random() < 0.6) else ("pocket" if (not fem and rng.random() < 0.5) else "hang")
    if toddler: pose = "toddler"
    skin = M["skin_old"] if old else M["skin"]
    # ---- тело
    if fem or toddler:
        sk_m = M[opts["skirt"]] if "skirt" in opts else (M["kittel"] if toddler else M["skirt2"] if kind == "maid" else M["skirt"])
        hem = 0.02 if not child else (0.32 if kind == "girl" else 0.42)
        if child:
            for sx in (-1, 1):
                P.append(_seg("leg", (sx * 0.07, 0, hem + 0.12), (sx * 0.075, -0.005, 0.09), 0.05, 0.042, M["stocking"]))
                P.append(_sph("shoe", 0.045, (sx * 0.075, -0.05, 0.035), M["boot"], (0.9, 1.5, 0.75)))
        else:
            for sx in (-1, 1):
                P.append(_sph("shoe", 0.045, (sx * 0.075, -0.07, 0.03), M["boot"], (0.85, 1.6, 0.65)))
        r0 = 0.325 if not child else 0.3
        prof = [(hem, r0, r0 * 0.85, 0), (hem + 0.015, r0 + 0.005, r0 * 0.86, 0), (hem + 0.04, r0 + 0.003, r0 * 0.855, 0)]
        for zz, rx, ry in [(0.3, 0.29, 0.245), (0.6, 0.23, 0.19), (0.85, 0.165, 0.13), (0.95, 0.15, 0.115)]:
            if zz > hem + 0.05: prof.append((zz, rx, ry, 0))
        if toddler:   # Kittel: свободный, без талии
            prof = [(hem, 0.26, 0.22, 0), (hem + 0.015, 0.265, 0.225, 0), (0.7, 0.22, 0.18, 0), (0.95, 0.19, 0.15, 0)]
        P.append(_lathe("skirt", prof, sk_m, 64, folds=(9, 0.018, rng.uniform(0, 6))))
        BOD = [(0.93, 0.14, 0.112, 0), (1.05, 0.148, 0.118, 0), (1.18, 0.162, 0.126, 0), (1.28, 0.172, 0.126, 0),
               (1.345, 0.182, 0.118, 0), (1.39, 0.15, 0.104, 0.004), (1.435, 0.095, 0.075, 0.006), (1.465, 0.06, 0.055, 0.006)]
        if toddler:
            BOD = [(0.93, 0.19, 0.15, 0), (1.1, 0.2, 0.15, 0), (1.28, 0.2, 0.14, 0), (1.36, 0.185, 0.128, 0),
                   (1.41, 0.15, 0.108, 0.004), (1.44, 0.1, 0.078, 0.006), (1.465, 0.058, 0.052, 0.006)]
        P.append(_lathe("bodice", BOD, coat, 40))
        if not toddler:
            ap_m = M[opts["apron"]] if "apron" in opts else (M["apron2"] if kind == "maid" else M["apron"])
            ap = _lathe("apron", [(max(hem, 0.08) + 0.06, 0.25, 0.335, -0.005), (0.4, 0.21, 0.29, -0.005), (0.75, 0.16, 0.225, -0.004), (0.94, 0.115, 0.15, -0.003)],
                        ap_m, 48, folds=(7, 0.01, rng.uniform(0, 6)))
            _delete_verts(ap, lambda co: co.y > 0.02)
            P.append(ap)
            P.append(_lathe("waistband", [(0.92, 0.157, 0.122, 0), (0.955, 0.155, 0.12, 0)], ap_m, 40))
            # Brusttuch: накидка по плечам, крест-накрест спереди с V-вырезом
            shm = M[opts["shawl"]] if "shawl" in opts else (M["scarf"] if kind != "old_woman" else M["scarf2"])
            SHW = [(1.47, 0.068, 0.062, 0.006), (1.44, 0.112, 0.09, 0.006), (1.405, 0.162, 0.116, 0.004), (1.36, 0.196, 0.132, 0.002),
                   (1.29, 0.198, 0.14, 0), (1.2, 0.19, 0.136, 0)]
            SHW = [(1.47 - 0.27 * i / 8, *_prof_at(sorted(SHW), 1.47 - 0.27 * i / 8)) for i in range(9)]
            sw = _lathe_open("shawl", SHW, shm, lambda zz, rx: math.asin(min(0.95, (0.045 + 0.1 * (1.47 - zz)) / rx)), 72)
            for v in sw.data.vertices:
                t = (1.47 - v.co.z) / 0.27
                bk = max(0.0, 1 - abs(v.co.x) / 0.2) if v.co.y > 0 else 0.0
                fr = max(0.0, 1 - abs(v.co.x) / 0.2) if v.co.y < 0 else 0.0
                v.co.z -= t * (0.1 * fr + 0.05 * bk)
            _fold(sw, 6, 0.003, rng.uniform(0, 6))
            _solidify(sw, 0.006, 1.0)
            for zz in (1.38, 1.31, 1.24, 1.17):
                P.append(_sph("button", 0.0075, (0, _front_y(BOD, 0, zz) - 0.002, zz), M["button"], (1, 0.6, 1), seg=12, ring=8))
            P.append(sw)
        P.append(_lathe("collar", [(1.455, 0.061, 0.057, 0.006), (1.495, 0.057, 0.053, 0.006)], M["shirt"], 32, cap=False, sub=0))
        SH = 0.178 if not toddler else 0.175
        BODY = BOD
    else:
        for sx in (-1, 1):
            P.append(_seg("leg", (sx * 0.095, 0, 0.74), (sx * 0.1, -0.005, 0.1), 0.074, 0.058, M["trouser"]))
            P.append(_lathe("boot", [(0.0, 0.05, 0.06, 0), (0.06, 0.055, 0.065, -0.005), (0.15, 0.05, 0.05, 0)], M["boot"], 24))
            P[-1].location = (sx * 0.1, -0.01, 0)
            P.append(_sph("toe", 0.046, (sx * 0.1, -0.078, 0.03), M["boot"], (0.95, 1.45, 0.65)))
        hem = 0.38 if kind == "investigator" else 0.6
        COAT = [(hem, 0.235, 0.19, 0), (hem + 0.012, 0.24, 0.195, 0), (hem + 0.04, 0.238, 0.193, 0), (0.8, 0.205, 0.16, 0),
                (1.0, 0.182, 0.142, 0), (1.2, 0.19, 0.145, 0), (1.29, 0.198, 0.14, 0), (1.345, 0.205, 0.132, 0),
                (1.385, 0.17, 0.116, 0.003), (1.425, 0.115, 0.09, 0.005), (1.462, 0.068, 0.062, 0.005)]
        P.append(_lathe("coat", COAT, coat, 48, folds=(6, 0.008, rng.uniform(0, 6))))
        BODY = COAT
        # V-вырез: жилет, рубашка, галстук, отвороты
        def fy(xx, zz, d=0.0): return _front_y(COAT, xx, zz) - d
        def tri(n, top_w, z_top, z_bot, m, d):
            nseg = 6; vs = []; fs = []
            for i in range(nseg + 1):
                zz = z_top + (z_bot - z_top) * i / nseg; hw = top_w * (1 - i / nseg) + 0.002
                for xx in (-hw, 0.0, hw):
                    vs.append((xx, fy(xx, zz, d + 0.003 * (1 - abs(xx) / max(hw, 1e-6))), zz))
            for i in range(nseg):
                a = i * 3
                fs += [(a, a + 1, a + 4, a + 3), (a + 1, a + 2, a + 5, a + 4)]
            return _mesh(n, vs, fs, m)
        P.append(tri("vest", 0.075, 1.445, 1.16, M["vest"] if kind != "investigator" else M["coat"], 0.002))
        P.append(tri("shirtv", 0.04, 1.452, 1.3, M["shirt"], 0.004))
        if kind != "old" or rng.random() < 0.5:
            P.append(tri("tie", 0.017, 1.445, 1.28, M["tie"], 0.006))
        for sx in (-1, 1):
            # отворот: полоска вдоль края выреза, приподнята над пальто
            vs = []; fs = []
            for i in range(7):
                t = i / 6; zz = 1.45 + (1.16 - 1.45) * t; xe = sx * (0.078 * (1 - t) + 0.004)
                xo = xe + sx * (0.04 + 0.03 * math.sin(math.pi * min(t * 1.4, 1)))
                vs += [(xe, fy(xe, zz, 0.008), zz), (xo, fy(xo, zz, 0.006), zz)]
            for i in range(6):
                a = i * 2; fs.append((a, a + 1, a + 3, a + 2) if sx > 0 else (a, a + 2, a + 3, a + 1))
            lp = _mesh("lapel", vs, fs, coat); _solidify(lp, 0.004, 0.0); P.append(lp)
        for zz in (1.12, 1.03, 0.94):
            P.append(_sph("button", 0.0095, (0.022, fy(0.022, zz, 0.004), zz), M["button"], seg=12, ring=8))
        P.append(_lathe("shirtcol", [(1.45, 0.066, 0.062, 0.003), (1.493, 0.064, 0.06, 0.003)], M["shirt"], 32, cap=False, sub=0))
        if kind == "investigator":
            P.append(_lathe("belt", [(0.975, 0.206, 0.152, 0), (1.025, 0.204, 0.15, 0)], M["trench"], 40))
            P.append(_box("buckle", 0.045, 0.01, 0.035, (0, -0.155, 1.0), M["metal"]))
        if kind == "old":   # уголок платка в нагрудном кармане / часы на цепочке
            P.append(_seg("chain", (-0.02, fy(-0.02, 1.08, 0.004), 1.08), (-0.09, fy(-0.09, 1.06, 0.004), 1.06), 0.0025, 0.0025, M["metal"], nv=6))
        SH = 0.19
    P.append(_cone("neck", 0.06 if not fem else 0.052, 0.055 if not fem else 0.048, 0.13, (0, 0.01, 1.52), skin, nv=28))
    # ---- руки: плечо — локоть — кисть
    for sx in (-1, 1):
        S_ = Vector((sx * SH, 0.0, 1.345))
        if sx > 0 and arm_up > 0:
            E = S_ + Vector((sx * 0.03, -0.27 * math.sin(arm_up), -0.27 * math.cos(arm_up)))
            Hh = E + Vector((0, -0.25 * math.sin(arm_up + 0.35), -0.25 * math.cos(arm_up + 0.35)))
        elif sx > 0 and lantern:
            E = Vector((SH + 0.035, 0.0, 1.07)); Hh = Vector((0.25, -0.08, 0.84))
        elif sx < 0 and case:
            E = Vector((-SH - 0.045, 0.01, 1.06)); Hh = Vector((-0.29, -0.01, 0.79))
        elif gun:
            E = Vector((sx * (SH + 0.01), -0.12, 1.1)); Hh = Vector((0.1, -0.24, 1.05)) if sx > 0 else Vector((-0.1, -0.3, 1.3))
        elif pose == "fold":
            E = Vector((sx * (SH + 0.015), 0.0, 1.08)); Hh = Vector((sx * 0.035, -0.165, 0.97))
        elif pose == "pocket":
            E = Vector((sx * (SH + 0.03), 0.035, 1.09)); Hh = Vector((sx * 0.17, -0.09, 0.93))
        elif pose == "behind":
            E = Vector((sx * (SH + 0.015), 0.07, 1.08)); Hh = Vector((sx * 0.06, 0.2, 0.95))
        elif pose == "toddler":
            E = Vector((sx * (SH + 0.05), -0.02, 1.08)); Hh = Vector((sx * (SH + 0.08), -0.08, 0.86))
        else:
            E = Vector((sx * (SH + 0.008), 0.01, 1.07)); Hh = Vector((sx * (SH + 0.012), -0.035, 0.82))
        ra = 0.05 if not fem else 0.044
        P.append(_sph("shtop", ra * 0.98, S_ + Vector((-sx * 0.022, 0, -0.004)), coat, (1, 1.1, 1), seg=24, ring=14))
        P.append(_seg("uarm", S_ + Vector((-sx * 0.022, 0, -0.004)), E, ra * 0.98, ra * 0.84, coat, nv=24))
        P.append(_sph("elbow", ra * 0.84, E, coat, seg=20, ring=12))
        P.append(_seg("farm", E, Hh, ra * 0.84, ra * 0.78, coat, nv=24))
        hid = pose in ("pocket", "behind") and not ((sx > 0 and (lantern or arm_up)) or (sx < 0 and case) or gun)
        if not hid:
            dr = (Hh - E).normalized()
            q = dr.to_track_quat("Z", "Y")
            # ладонь смотрит к бедру (внутрь) у опущенной руки
            rq = (q @ Vector((1, 0, 0)))
            P.append(_cone("cuff", ra * 0.8, ra * 0.8, 0.02, Hh, M["shirt"], rot=q.to_euler(), nv=18))
            hs = 1.0 if not fem else 0.9
            hc = Hh + dr * 0.052 * hs
            hand = _sph("hand", 0.043 * hs, hc, skin, (0.42, 0.85, 1.25), rot=q.to_euler(), seg=24, ring=14)
            P.append(hand)
            side = q @ Vector((0, -1, 0))
            P.append(_sph("fingers", 0.034 * hs, hc + dr * 0.04 * hs, skin, (0.38, 0.8, 0.9),
                          rot=q.to_euler(), seg=20, ring=12))
            P.append(_sph("thumb", 0.013 * hs, Hh + dr * 0.035 * hs + side * 0.028 * hs, skin, (0.85, 0.85, 1.9),
                          rot=q.to_euler(), seg=12, ring=8))
    # ---- голова (на шарнире шеи)
    hd = bpy.data.objects.new("headpivot", None); bpy.context.scene.collection.objects.link(hd)
    HP = []
    _head(HP, M, kind, fem, old, child, beard, hair_m, rng, eye_m, opts)
    # ---- пропорции: дети — короче и уже тело, крупнее голова; взрослые — телосложение
    if child:
        kz, kxy, hs = CHILD[kind]
    else:
        kz, kxy, hs = 1.0, build, 1.0
    Sm = Matrix.Diagonal((kxy, kxy, kz, 1.0))
    for o in P:
        if o.type == "MESH": _bake(o, Sm)
    neck_top = 1.47 * kz - ({"girl": 0.012, "boy": 0.03}.get(kind, 0.0))
    hd.location = (0, 0, neck_top)
    for o in HP:
        o.location = o.location - Vector((0, 0, 1.47)); o.parent = hd
    hd.scale = (hs, hs, hs)
    pitch, yaw = head if head is not None else (rng.uniform(-0.06, 0.1), rng.uniform(-0.25, 0.25))
    stoop = opts.get("stoop", 0.1 if old else 0.0)
    hd.rotation_euler = (pitch - stoop * 0.6, rng.uniform(-0.05, 0.05) + opts.get("tilt", 0.0), yaw)
    P.append(hd)
    # ---- предметы
    if lantern:
        lx = 0.27 * kxy; lz = 0.62 * kz
        P.append(_cone("lantern", 0.06, 0.055, 0.17, (lx, -0.08, lz), M["lamp"]))
        P.append(_cone("lanterncap", 0.07, 0.02, 0.06, (lx, -0.08, lz + 0.11), M["metal"]))
        P.append(_seg("handle", (lx - 0.02, -0.08, lz + 0.18), (lx + 0.02, -0.08, lz + 0.18), 0.005, 0.005, M["metal"], nv=6))
        P.append(_seg("bail", (lx, -0.08, lz + 0.14), (0.25 * kxy, -0.08 - 0.0, 0.84 * kz - 0.02), 0.003, 0.003, M["metal"], nv=6))
        L = bpy.data.lights.new("lan", "POINT"); L.energy = 35; L.color = _srgb("#ffa850"); L.shadow_soft_size = 0.05
        lo = bpy.data.objects.new("lan", L); bpy.context.scene.collection.objects.link(lo)
        lo.location = (lx, -0.18, lz + 0.02); P.append(lo)
    if gun:
        P.append(_seg("gun", (0.2, -0.2, 0.86), (-0.2, -0.32, 1.52), 0.02, 0.014, M["wood"], nv=10))
        P.append(_seg("barrel", (-0.05, -0.28, 1.27), (-0.26, -0.33, 1.62), 0.011, 0.011, M["metal"], nv=8))
    if case:
        P.append(_box("case", 0.1, 0.4, 0.29, (-0.35 * kxy, -0.01, 0.6 * kz), M["case"]))
        P.append(_seg("caseh", (-0.35 * kxy, -0.07, 0.76 * kz), (-0.35 * kxy, 0.05, 0.76 * kz), 0.008, 0.008, M["boot"], nv=6))
    # ---- осанка: сутулость и перенос веса — наклон всего верха вокруг бедра
    lean = opts.get("lean", rng.uniform(-0.035, 0.035))
    upper = bpy.data.objects.new("upper", None); bpy.context.scene.collection.objects.link(upper)
    upper.location = (0, 0, 0.95 * kz)
    upper.rotation_euler = (stoop, lean, 0)
    for o in P:
        top = o.location.z if o.type != "MESH" else max((v.co.z for v in o.data.vertices), default=0)
        if o.name.startswith(("leg", "boot", "toe", "shoe", "skirt", "apron")) or (o.type == "MESH" and top < 0.9 * kz):
            o.parent = root
        else:
            o.location = Vector(o.location) - upper.location
            o.parent = upper
    upper.parent = root
    root.location = (x, y, z); root.rotation_euler = (0, 0, face); root.scale = (sc, sc, sc)
    root["head_z"] = (neck_top + 0.115 * hs) * sc
    return root
