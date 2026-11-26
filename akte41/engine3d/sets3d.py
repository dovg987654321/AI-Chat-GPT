# -*- coding: utf-8 -*-
"""
Akte 41 — интерьерные 3D-декорации для серии «Hinterkaifeck» (стиль «Тёмное кино»):
стол следователя (карта, фото, документы, улики), доска версий, кухня, чердак, амбар.
Каждый план — статичный кадр 2400x1350 + json с экранными точками для пост-камеры.

python3 sets3d.py OUT_DIR [--plates a,b,c] [--samples 20] [--res 2400x1350]
"""
import bpy, math, os, sys, json, random
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from PIL import Image, ImageDraw, ImageFont, ImageFilter

args = sys.argv[1:]
OUT = args[0] if args else "out"
def opt(n, d):
    return args[args.index(n) + 1] if n in args else d
SAMPLES = int(opt("--samples", "20"))
RES = [int(v) for v in opt("--res", "2400x1350").split("x")]
PLATES = [p for p in opt("--plates", "").split(",") if p]
TEX = os.path.join(OUT, "tex"); os.makedirs(TEX, exist_ok=True)
os.makedirs(os.path.join(OUT, "plates"), exist_ok=True)
rnd = random.Random(41)

FM = "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf"
FMB = "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf"
FS = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FSB = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
FX = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
FH = "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"
def F(p, s): return ImageFont.truetype(p, int(s))

bpy.ops.wm.read_factory_settings(use_empty=True)
S = bpy.context.scene; COL = S.collection
def link(ob):
    COL.objects.link(ob); return ob
def srgb(h):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c)

# ================================================================ материалы
def mat(name, color, rough=0.6, bump=0.0, bs=40.0, ncol=None, emit=None, es=0.0, metal=0.0, coat=0.0, alpha=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    N = m.node_tree.nodes; L = m.node_tree.links; p = N["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1); p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if coat: p.inputs["Coat Weight"].default_value = coat
    if emit:
        p.inputs["Emission Color"].default_value = (*emit, 1); p.inputs["Emission Strength"].default_value = es
    if bump or ncol:
        tc = N.new("ShaderNodeTexCoord"); nz = N.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = bs; nz.inputs["Detail"].default_value = 8
        L.new(tc.outputs["Object"], nz.inputs["Vector"])
        if bump:
            b = N.new("ShaderNodeBump"); b.inputs["Strength"].default_value = bump; b.inputs["Distance"].default_value = 0.01
            L.new(nz.outputs["Fac"], b.inputs["Height"]); L.new(b.outputs["Normal"], p.inputs["Normal"])
        if ncol:
            r = N.new("ShaderNodeValToRGB")
            r.color_ramp.elements[0].color = (*ncol, 1); r.color_ramp.elements[1].color = (*color, 1)
            r.color_ramp.elements[0].position = 0.3; r.color_ramp.elements[1].position = 0.7
            L.new(nz.outputs["Fac"], r.inputs["Fac"]); L.new(r.outputs["Color"], p.inputs["Base Color"])
    if alpha is not None:
        p.inputs["Alpha"].default_value = alpha
    return m

def wood_mat(name, c1, c2, rough=0.55, scale=(1, 14, 1)):
    """дерево: вытянутый шум как волокна"""
    m = bpy.data.materials.new(name); m.use_nodes = True
    N = m.node_tree.nodes; L = m.node_tree.links; p = N["Principled BSDF"]
    p.inputs["Roughness"].default_value = rough
    tc = N.new("ShaderNodeTexCoord"); mp_ = N.new("ShaderNodeMapping"); mp_.inputs["Scale"].default_value = scale
    nz = N.new("ShaderNodeTexWave"); nz.wave_type = "BANDS"; nz.inputs["Scale"].default_value = 3.0
    nz.inputs["Distortion"].default_value = 1.6; nz.inputs["Detail"].default_value = 4; nz.inputs["Detail Scale"].default_value = 1.4
    L.new(tc.outputs["Object"], mp_.inputs["Vector"]); L.new(mp_.outputs["Vector"], nz.inputs["Vector"])
    r = N.new("ShaderNodeValToRGB")
    r.color_ramp.elements[0].color = (*c2, 1); r.color_ramp.elements[1].color = (*c1, 1)
    L.new(nz.outputs["Fac"], r.inputs["Fac"]); L.new(r.outputs["Color"], p.inputs["Base Color"])
    b = N.new("ShaderNodeBump"); b.inputs["Strength"].default_value = 0.15
    L.new(nz.outputs["Fac"], b.inputs["Height"]); L.new(b.outputs["Normal"], p.inputs["Normal"])
    return m

def tex_mat(name, path, rough=0.75, bump=0.12):
    m = bpy.data.materials.new(name); m.use_nodes = True
    N = m.node_tree.nodes; L = m.node_tree.links; p = N["Principled BSDF"]
    it = N.new("ShaderNodeTexImage"); it.image = bpy.data.images.load(path)
    L.new(it.outputs["Color"], p.inputs["Base Color"]); p.inputs["Roughness"].default_value = rough
    if bump:
        tc = N.new("ShaderNodeTexCoord"); nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 300
        L.new(tc.outputs["Object"], nz.inputs["Vector"])
        b = N.new("ShaderNodeBump"); b.inputs["Strength"].default_value = bump
        L.new(nz.outputs["Fac"], b.inputs["Height"]); L.new(b.outputs["Normal"], p.inputs["Normal"])
    return m

M = dict(
    desk=wood_mat("desk", srgb("#4a2c1a"), srgb("#2a170c"), 0.45),
    floor=wood_mat("floor", srgb("#5a4030"), srgb("#30221a"), 0.8, (1, 6, 1)),
    beam=wood_mat("beam", srgb("#4a3828"), srgb("#241a12"), 0.85, (1, 1, 8)),
    planks=wood_mat("planks", srgb("#5c4532"), srgb("#2c2016"), 0.85, (10, 1, 1)),
    wall=mat("wall", srgb("#2c3430"), 0.9, bump=0.2, bs=8, ncol=srgb("#1e2421")),
    plaster=mat("plasterk", srgb("#b8ad98"), 0.95, bump=0.3, bs=6, ncol=srgb("#8a806e")),
    cork=mat("cork", srgb("#8a6440"), 0.95, bump=0.6, bs=180, ncol=srgb("#5e4228")),
    red=mat("redp", srgb("#b0181c"), 0.5),
    redstr=mat("redstr", srgb("#9c1418"), 0.7),
    brass=mat("brass", srgb("#b08a40"), 0.3, metal=1.0),
    gold=mat("gold", srgb("#e0b040"), 0.22, metal=1.0, bump=0.1, bs=60),
    iron=mat("iron", srgb("#3a3a3c"), 0.55, metal=0.8, bump=0.4, bs=40, ncol=srgb("#4a3020")),
    black=mat("blackm", srgb("#121212"), 0.4),
    glass=mat("glassm", srgb("#ffffff"), 0.05, alpha=0.15),
    lampglow=mat("lampglow", srgb("#ffcf8a"), 0.2, emit=srgb("#ffb860"), es=30.0),
    ember=mat("ember", srgb("#ff6a20"), 0.5, emit=srgb("#ff5010"), es=6.0),
    stove=mat("stove", srgb("#3c5a4a"), 0.35, bump=0.3, bs=14, ncol=srgb("#2a4034"), coat=0.6),
    bread=mat("bread", srgb("#8a5428"), 0.7, bump=0.8, bs=30, ncol=srgb("#5a3418")),
    crumb=mat("crumb", srgb("#d8c090"), 0.9, bump=0.5, bs=120),
    plate=mat("plate", srgb("#e8e4da"), 0.25, coat=0.5),
    hay=mat("hay", srgb("#9a8040"), 0.95, bump=1.0, bs=60, ncol=srgb("#5a4a20")),
    coat=mat("coat", srgb("#1b1a1c"), 0.85, bump=0.3, bs=30),
    coat2=mat("coat2", srgb("#2a2420"), 0.85, bump=0.3, bs=30),
    skin=mat("skin", srgb("#6b5244"), 0.6),
    paper=mat("paperm", srgb("#ddd4c0"), 0.85),
    note=mat("notem", srgb("#c9b68e"), 0.8),
    win=mat("winm", srgb("#0d1626"), 0.1, emit=srgb("#3a5a90"), es=0.6),
)

def box(name, sx, sy, sz, loc, m, rot=(0, 0, 0), bevel=0.004):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object; o.name = name; o.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(m)
    if bevel:
        b = o.modifiers.new("bv", "BEVEL"); b.width = bevel; b.segments = 2
    return o

def cyl(name, r1, r2, h, loc, m, rot=(0, 0, 0), n=24):
    bpy.ops.mesh.primitive_cone_add(vertices=n, radius1=r1, radius2=r2, depth=h, location=loc, rotation=rot)
    o = bpy.context.active_object; o.name = name; o.data.materials.append(m)
    for p in o.data.polygons: p.use_smooth = True
    return o

def sph(name, r, loc, m, sc=(1, 1, 1), seg=24):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=seg, ring_count=seg // 2)
    o = bpy.context.active_object; o.name = name; o.scale = sc; o.data.materials.append(m)
    for p in o.data.polygons: p.use_smooth = True
    return o

def sheet(name, w, h, loc, m, rz=0.0, rx=0.0, thick=0.0006):
    """лист бумаги/картон: тонкая коробка с текстурой сверху (UV 0..1 на верхней грани)"""
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=(rx, 0, rz))
    o = bpy.context.active_object; o.name = name; o.scale = (w, h, 1)
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(m)
    if thick:
        so = o.modifiers.new("sol", "SOLIDIFY"); so.thickness = thick
    return o

def group(objs, name):
    for o in objs: o.hide_render = True
    GROUPS[name] = objs
GROUPS = {}

# ================================================================ текстуры (PIL)
PAPER_C = (226, 216, 192)
def paper_img(w, h, col=PAPER_C, age=1.0, seed=0):
    r = random.Random(seed)
    im = Image.new("RGB", (w, h), col)
    n = Image.effect_noise((w // 4, h // 4), 30).resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(2))
    stain = Image.new("L", (w, h), 0); d = ImageDraw.Draw(stain)
    for _ in range(int(6 * age)):
        x, y, rr = r.uniform(0, w), r.uniform(0, h), r.uniform(w * 0.05, w * 0.2)
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=r.randint(10, 35))
    stain = stain.filter(ImageFilter.GaussianBlur(w * 0.03))
    dark = Image.new("RGB", (w, h), (150, 120, 80))
    im = Image.composite(dark, im, stain)
    im = Image.blend(im, Image.merge("RGB", [n, n, n]), 0.06)
    # затемнённые края
    e = Image.new("L", (w, h), 0); ImageDraw.Draw(e).rectangle([w * 0.03, h * 0.03, w * 0.97, h * 0.97], fill=255)
    e = e.filter(ImageFilter.GaussianBlur(w * 0.03))
    im = Image.composite(im, Image.blend(im, dark, 0.35), e)
    return im

def save(im, name):
    p = os.path.join(TEX, name + ".png"); im.save(p); return p

def typed_lines(d, x, y, lines, f, fill=(40, 34, 30), lh=1.5, jitter=True, seed=1):
    r = random.Random(seed)
    for i, ln in enumerate(lines):
        xx = x
        for ch in ln:
            dy = r.uniform(-1.2, 1.2) if jitter else 0
            a = r.randint(170, 255)
            d.text((xx, y + i * f.size * lh + dy), ch, font=f, fill=(*fill, a))
            xx += f.getlength(ch)

BAVARIA = [(520, 180), (700, 140), (900, 170), (1060, 120), (1250, 210), (1320, 330), (1440, 420), (1400, 560),
           (1480, 700), (1420, 820), (1300, 860), (1160, 900), (980, 880), (820, 920), (650, 880), (560, 760),
           (470, 640), (430, 480), (480, 330)]

def tex_map():
    w, h = 2000, 1400
    im = paper_img(w, h, (222, 210, 180), 1.2, 3); d = ImageDraw.Draw(im, "RGBA")
    sx, sy, ox, oy = 1.25, 1.3, -380, -120
    P = [(x * sx + ox, y * sy + oy) for x, y in BAVARIA]
    d.polygon(P, fill=(196, 182, 150, 255))
    for k in range(3):
        d.line(P + [P[0]], fill=(90, 70, 50, 200), width=5 - k)
    # реки
    d.line([(P[18][0] + 60, 900), (560, 860), (860, 790), (1150, 720), (1380, 640)], fill=(80, 100, 120, 150), width=4)
    towns = {"München": (1010, 760), "Ingolstadt": (990, 470), "Schrobenhausen": (905, 590), "Augsburg": (760, 760),
             "Regensburg": (1160, 380), "Nürnberg": (930, 260)}
    for n, (x, y) in towns.items():
        X, Y = x * sx + ox, y * sy + oy
        d.ellipse([X - 9, Y - 9, X + 9, Y + 9], fill=(40, 34, 30, 255))
        d.text((X + 16, Y - 8), n, font=F(FS, 34), fill=(40, 34, 30, 255))
    hx, hy = 905 * sx + ox + 40, 590 * sy + oy - 40
    d.ellipse([hx - 40, hy - 40, hx + 40, hy + 40], outline=(170, 20, 24, 255), width=6)
    d.text((hx - 60, hy - 95), "Hinterkaifeck", font=F(FH, 44), fill=(170, 20, 24, 255))
    mx, my = 1010 * sx + ox, 760 * sy + oy
    d.line([(hx, hy), (mx, my)], fill=(170, 20, 24, 200), width=3)
    d.text(((hx + mx) / 2 + 20, (hy + my) / 2 - 10), "≈ 70 km", font=F(FH, 40), fill=(170, 20, 24, 255))
    d.text((80, 40), "FREISTAAT BAYERN · 1922", font=F(FSB, 56), fill=(50, 40, 32, 255))
    d.text((80, 110), "Oberbayern · Schwaben · Niederbayern", font=F(FS, 30), fill=(70, 60, 50, 255))
    return save(im, "map"), ((hx) / w, (hy) / h)

def portrait(name, age, sub=None, kind="man", blank=False, seed=0, cross=False):
    w, h = 700, 950
    im = Image.new("RGB", (w, h), (232, 224, 204)); d = ImageDraw.Draw(im)
    # фото сепия
    ph = Image.new("RGB", (w - 100, 620), (120, 100, 78))
    pd = ImageDraw.Draw(ph)
    for i in range(620):
        c = int(150 - i * 0.08); pd.line([(0, i), (w, i)], fill=(c, int(c * 0.85), int(c * 0.66)))
    if not blank:
        cx = (w - 100) / 2
        s = 1.0 if kind != "child" else 0.78
        col = (52, 40, 30)
        pd.ellipse([cx - 230 * s, 400 + 130 * (1 - s), cx + 230 * s, 820], fill=col)            # плечи
        pd.rectangle([cx - 45 * s, 300, cx + 45 * s, 440], fill=col)                             # шея
        pd.ellipse([cx - 95 * s, 170 + 80 * (1 - s), cx + 95 * s, 400], fill=col)               # голова
        if kind == "woman" or kind == "old":
            pd.ellipse([cx - 105 * s, 150, cx + 105 * s, 300], fill=(42, 32, 24))
            pd.rectangle([cx - 30, 145, cx + 30, 180], fill=(42, 32, 24))
        if kind == "man":
            pd.rectangle([cx - 85, 390, cx + 85, 420], fill=(60, 48, 36))
        if kind == "soldier":
            pd.rectangle([cx - 110, 150, cx + 110, 210], fill=(40, 34, 28))
            pd.rectangle([cx - 140, 200, cx + 140, 225], fill=(40, 34, 28))
    else:
        pd.text(((w - 100) / 2, 310), "?", font=F(FSB, 220), fill=(90, 74, 58), anchor="mm")
    ph = ph.filter(ImageFilter.GaussianBlur(2.2))
    n = Image.effect_noise(ph.size, 40).convert("RGB")
    ph = Image.blend(ph, n, 0.10)
    im.paste(ph, (50, 50))
    d.text((w / 2, 760), name, font=F(FH, 56), fill=(40, 30, 26), anchor="mm")
    if age: d.text((w / 2, 840), age, font=F(FSB, 60), fill=(150, 24, 28), anchor="mm")
    if sub: d.text((w / 2, 905), sub, font=F(FH, 38), fill=(100, 60, 50), anchor="mm")
    if cross:
        d.line([(60, 60), (w - 60, 670)], fill=(150, 24, 28), width=8)
    im = Image.composite(im, paper_img(w, h, (210, 196, 166), 0.8, seed), Image.new("L", (w, h), 230))
    return save(im, "por_" + name.split()[0].lower() + str(seed))

def tex_doc(name, title, lines, seed=1, w=1240, h=1754, head=None):
    im = paper_img(w, h, (230, 222, 200), 1.0, seed); d = ImageDraw.Draw(im, "RGBA")
    y = 140
    if head:
        d.text((w / 2, y), head, font=F(FSB, 52), fill=(40, 34, 30), anchor="mm"); y += 70
        d.line([(120, y), (w - 120, y)], fill=(40, 34, 30), width=3); y += 60
    d.text((w / 2, y), title, font=F(FMB, 46), fill=(40, 34, 30), anchor="mm"); y += 110
    typed_lines(d, 140, y, lines, F(FM, 36), seed=seed)
    return save(im, name)

def tex_newspaper():
    w, h = 1500, 2000
    im = paper_img(w, h, (214, 206, 186), 1.3, 9); d = ImageDraw.Draw(im, "RGBA")
    d.text((w / 2, 130), "Münchner Neueste Nachrichten", font=F(FSB, 92), fill=(30, 26, 24), anchor="mm")
    d.line([(60, 210), (w - 60, 210)], fill=(30, 26, 24), width=6)
    d.text((70, 250), "Nr. 87 · 75. Jahrgang", font=F(FS, 30), fill=(50, 44, 40))
    d.text((w - 70, 250), "März 1922", font=F(FS, 30), fill=(50, 44, 40), anchor="ra")
    d.line([(60, 300), (w - 60, 300)], fill=(30, 26, 24), width=2)
    d.text((w / 2, 380), "Die Lage im Reich", font=F(FSB, 70), fill=(30, 26, 24), anchor="mm")
    r = random.Random(5)
    for c in range(4):
        x0 = 70 + c * 345
        y = 470
        while y < h - 80:
            if r.random() < 0.06:
                d.text((x0, y), "Aus Stadt und Land", font=F(FSB, 30), fill=(30, 26, 24)); y += 50; continue
            ww = r.uniform(250, 315)
            d.rectangle([x0, y, x0 + ww, y + 10], fill=(90, 84, 78, 170)); y += 22
        if c: d.line([(x0 - 15, 460), (x0 - 15, h - 80)], fill=(60, 54, 50), width=2)
    return save(im, "newspaper")

def tex_calendar(day, num, month="MÄRZ 1922", red=False, seed=2):
    w, h = 800, 1000
    im = paper_img(w, h, (236, 230, 214), 0.6, seed); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w, 170], fill=(150, 24, 28) if red else (40, 34, 30))
    d.text((w / 2, 90), day, font=F(FSB, 76), fill=(236, 230, 214), anchor="mm")
    d.text((w / 2, 520), num, font=F(FSB, 420), fill=(40, 34, 30), anchor="mm")
    d.text((w / 2, 860), month, font=F(FSB, 70), fill=(40, 34, 30), anchor="mm")
    return save(im, "cal_" + num + day[:2])

def tex_label(name, lines, w=900, h=360, col=(214, 200, 160), fonts=None, seed=4):
    im = paper_img(w, h, col, 0.5, seed); d = ImageDraw.Draw(im)
    y = h / 2 - (len(lines) - 1) * 40
    for i, ln in enumerate(lines):
        d.text((w / 2, y + i * 80), ln, font=F(fonts[i] if fonts else FMB, 60 if i == 0 else 44), fill=(40, 30, 26), anchor="mm")
    return save(im, name)

def tex_stencil(name, txt, w=1200, h=500):
    im = Image.new("RGB", (w, h), (120, 88, 56)); d = ImageDraw.Draw(im)
    n = Image.effect_noise((w, h), 50).convert("RGB"); im = Image.blend(im, n, 0.12)
    d = ImageDraw.Draw(im)
    for i in range(0, h, 100): d.line([(0, i), (w, i)], fill=(80, 58, 36), width=4)
    d.text((w / 2, h / 2), txt, font=F(FX, 150), fill=(30, 22, 18), anchor="mm")
    return save(im, name)

def tex_board_card(name, sub, kind, seed):
    w, h = 700, 820
    im = paper_img(w, h, (232, 226, 210), 0.5, seed); d = ImageDraw.Draw(im)
    p = Image.open(portrait(name, None, None, kind, seed=seed + 10)).crop((50, 50, 650, 670)).resize((560, 580))
    im.paste(p, (70, 50))
    d.text((w / 2, 690), sub, font=F(FS, 44), fill=(60, 50, 44), anchor="mm")
    d.text((w / 2, 760), name, font=F(FSB, 54), fill=(40, 30, 26), anchor="mm")
    return save(im, "bc_" + name.split()[0].lower())

# ================================================================ люди
import figures
def person(x, y, z, face=0.0, kind="man", sc=1.0, lantern=False, gun=False, **kw):
    if figures._MATFN is None:
        figures.setup(lambda n, c, r, b, bs: mat(n, c, r, bump=b, bs=bs))
    root = figures.person(x, y, z, face, kind, sc, lantern, gun, **kw)
    return list(root.children_recursive) + [root]

# ================================================================ декорации
def build_desk():
    """Стол следователя у начала координат. Верх стола z=0.78."""
    objs = []
    Z = 0.78
    objs.append(box("desktop", 2.8, 1.7, 0.06, (0, 0, Z - 0.03), M["desk"], bevel=0.01))
    objs.append(box("deskfloor", 12, 12, 0.02, (0, 0, 0), M["floor"]))
    objs.append(box("deskwall", 12, 0.1, 4, (0, 2.6, 2), M["wall"]))
    # лампа
    objs.append(cyl("lampshade", 0.26, 0.08, 0.2, (-1.05, 0.65, Z + 0.62), mat("shade", srgb("#1e4a30"), 0.3, coat=0.8)))
    objs.append(cyl("lampstem", 0.015, 0.015, 0.55, (-1.05, 0.72, Z + 0.28), M["brass"]))
    objs.append(cyl("lampbase", 0.12, 0.1, 0.04, (-1.05, 0.72, Z + 0.02), M["brass"]))
    objs.append(sph("bulb", 0.05, (-1.05, 0.65, Z + 0.55), M["lampglow"]))
    L = bpy.data.lights.new("desklamp", "SPOT"); L.energy = 260; L.color = srgb("#ffc890")
    L.spot_size = math.radians(95); L.spot_blend = 0.7; L.shadow_soft_size = 0.06
    lo = link(bpy.data.objects.new("desklamp", L)); lo.location = (-1.05, 0.65, Z + 0.55)
    lo.rotation_euler = (math.radians(-25), math.radians(-30), 0); objs.append(lo)
    L2 = bpy.data.lights.new("deskfill", "AREA"); L2.energy = 30; L2.size = 2; L2.color = srgb("#6a86c0")
    lo2 = link(bpy.data.objects.new("deskfill", L2)); lo2.location = (1.8, -1.2, 2.2)
    lo2.rotation_euler = (math.radians(45), 0, math.radians(55)); objs.append(lo2)
    # лупа и перо
    objs.append(bpy_torus("magring", 0.075, 0.008, (0.95, -0.45, Z + 0.012), M["brass"]))
    objs.append(cyl("maglens", 0.072, 0.072, 0.004, (0.95, -0.45, Z + 0.012), M["glass"]))
    objs.append(cyl("maghandle", 0.012, 0.012, 0.16, (1.07, -0.55, Z + 0.012), M["black"], rot=(math.pi / 2, 0, 0.9)))
    objs.append(cyl("pen", 0.007, 0.007, 0.15, (-0.75, -0.55, Z + 0.008), M["black"], rot=(math.pi / 2, 0, 0.4)))
    GROUPS["desk_base"] = objs
    return Z

def bpy_torus(name, R, r, loc, m):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, location=loc)
    o = bpy.context.active_object; o.name = name; o.data.materials.append(m)
    for p in o.data.polygons: p.use_smooth = True
    return o

HOT = {}       # именованные 3D-точки для пост-камеры
def build_desk_props(Z):
    # карта
    mp_, pin = tex_map()
    m = sheet("map", 1.0, 0.7, (0.0, 0.05, Z + 0.001), tex_mat("mapm", mp_), rz=0.04)
    px = (pin[0] - 0.5) * 1.0; py = (0.5 - pin[1]) * 0.7
    c, s = math.cos(0.04), math.sin(0.04)
    P = Vector((px * c - py * s, px * s + py * c + 0.05, Z + 0.002))
    pinb = sph("pinball", 0.012, P + Vector((0, 0, 0.05)), M["red"]); pinn = cyl("pinneedle", 0.0015, 0.0015, 0.05, P + Vector((0, 0, 0.025)), M["iron"])
    HOT["map_pin"] = P
    group([m, pinb, pinn], "map")
    # семья: карточки в два ряда
    fam = [("Andreas Gruber", "63", None, "man"), ("Cäzilia Gruber", "72", None, "old"), ("Viktoria Gabriel", "35", "Witwe", "woman"),
           ("Karl Gabriel", None, "gefallen 1914?", "soldier"), ("Cäzilia", "7", None, "child"), ("Josef", "2", None, "child"),
           ("Magd", None, "?", "blank")]
    objs = []
    for i, (n, a, sub, kd) in enumerate(fam):
        p = portrait(n, a, sub, kd, blank=(kd == "blank"), seed=i)
        row = 0 if i < 4 else 1
        col = i if i < 4 else i - 4
        x = -0.75 + col * 0.42 + (0.2 if row else 0); y = 0.32 - row * 0.62
        if i == 3: x += 0.12; y += 0.05
        rz = rnd.uniform(-0.08, 0.08)
        objs.append(sheet("card" + str(i), 0.34, 0.46, (x, y, Z + 0.001 + i * 0.0004), tex_mat("cm" + str(i), p), rz=rz, thick=0.0015))
        HOT["fam%d" % i] = Vector((x, y, Z))
    group(objs, "family")
    # приговор 1915
    doc = tex_doc("court", "URTEIL", ["", "In der Strafsache gegen", "", "  Andreas Gruber, Landwirt,", "  Hinterkaifeck,",
                                     "", "  Viktoria Gabriel, Witwe,", "  Hinterkaifeck,", "", "wegen Blutschande", "",
                                     "werden die Angeklagten", "für schuldig erkannt.", "", "Andreas Gruber: 1 Jahr Zuchthaus."],
                  seed=3, head="LANDGERICHT · 1915")
    o1 = sheet("court", 0.62, 0.87, (0.05, 0.0, Z + 0.001), tex_mat("courtm", doc), rz=-0.05)
    o2 = sheet("court2", 0.62, 0.87, (0.28, 0.12, Z + 0.0003), M["paper"], rz=0.12)
    HOT["court"] = Vector((0.05, 0.0, Z)); HOT["court_bottom"] = Vector((0.05, -0.3, Z))
    group([o1, o2], "court")
    # календарь
    c1 = tex_calendar("FREITAG", "31", red=True)
    blk = box("calblock", 0.42, 0.06, 0.5, (0.0, 0.25, Z + 0.25), M["paper"], rot=(math.radians(-12), 0, 0))
    front = sheet("calfront", 0.4, 0.5, (0.0, 0.215, Z + 0.26), tex_mat("calm", c1), rx=math.radians(78), thick=0)
    HOT["cal"] = Vector((0.0, 0.2, Z + 0.3))
    group([blk, front], "calendar")
    # дни: три листка
    objs = []
    for i, (dname, num) in enumerate([("SAMSTAG", "1"), ("SONNTAG", "2"), ("MONTAG", "3")]):
        p = tex_calendar(dname, num, "APRIL 1922", seed=20 + i)
        x = -0.5 + i * 0.5
        objs.append(sheet("day%d" % i, 0.4, 0.5, (x, 0.0 + (i % 2) * 0.06, Z + 0.001 + i * 0.0005), tex_mat("daym%d" % i, p), rz=rnd.uniform(-0.12, 0.12)))
        HOT["day%d" % i] = Vector((x, 0.0, Z))
    group(objs, "days")
    # Мюнхен: ящик с трафаретом и бирка
    st = tex_stencil("crate", "MÜNCHEN")
    cr = box("crate", 0.8, 0.5, 0.45, (0.1, 0.25, Z + 0.225), M["planks"], bevel=0.01)
    cf = sheet("cratefront", 0.76, 0.4, (0.1, -0.0015, Z + 0.225), tex_mat("crm", st, 0.9), rx=math.radians(90), thick=0)
    tag = tex_label("tag_munich", ["Pathologie München", "Hinterkaifeck · April 1922"], fonts=[FMB, FM])
    tg = sheet("tag", 0.3, 0.12, (-0.55, -0.3, Z + 0.001), tex_mat("tagm", tag), rz=0.2)
    HOT["crate"] = Vector((0.1, 0.0, Z + 0.25))
    group([cr, cf, tg], "munich")
    # Reuthaue
    objs = [cyl("handle", 0.022, 0.026, 0.9, (0.0, -0.05, Z + 0.03), M["beam"], rot=(0, math.pi / 2, 0.2))]
    hx, hy = 0.44 * math.cos(0.2), 0.44 * math.sin(0.2) - 0.05
    objs.append(box("eye", 0.07, 0.07, 0.06, (hx, hy, Z + 0.03), M["iron"], rot=(0, 0, 0.2)))
    objs.append(cyl("pick", 0.022, 0.003, 0.34, (hx + 0.02, hy + 0.17, Z + 0.03), M["iron"], rot=(math.pi / 2, 0, 0.2 + 0.0), n=6))
    objs.append(box("blade", 0.09, 0.26, 0.012, (hx - 0.03, hy - 0.16, Z + 0.025), M["iron"], rot=(0, 0, 0.2)))
    tg2 = tex_label("tag_weapon", ["Beweisstück", "Reuthaue · gef. 1923"], fonts=[FMB, FM])
    objs.append(sheet("wtag", 0.24, 0.1, (-0.2, -0.26, Z + 0.001), tex_mat("wtagm", tg2), rz=-0.15))
    HOT["weapon"] = Vector((hx, hy, Z))
    group(objs, "weapon")
    # 2007: папка и лист с зачёркнутым именем
    fold = tex_label("folder", ["FALLANALYSE", "Hinterkaifeck", "FH Fürstenfeldbruck · 2007"], 1000, 700, (180, 150, 100), [FX, FSB, FM])
    f1 = sheet("folder", 0.62, 0.44, (-0.35, 0.15, Z + 0.002), tex_mat("foldm", fold), rz=0.1, thick=0.003)
    d2 = tex_doc("redact", "ERGEBNIS", ["", "Nach Auswertung aller", "erhaltenen Akten gilt als", "Hauptverdächtiger:", "",
                                         "  ████████████████", "", "Der Name wird aus Rücksicht", "auf die Nachkommen", "nicht veröffentlicht."], seed=7)
    f2 = sheet("redactdoc", 0.5, 0.7, (0.35, -0.05, Z + 0.001), tex_mat("redm", d2), rz=-0.06)
    HOT["redact"] = Vector((0.35, -0.05, Z))
    group([f1, f2], "students")

def build_board(Z):
    """Доска версий на стене за столом."""
    objs = []
    objs.append(box("board", 2.0, 0.04, 1.2, (0, 2.5, 1.75), M["cork"], bevel=0.01))
    objs.append(box("bframe", 2.08, 0.05, 1.28, (0, 2.53, 1.75), M["beam"], bevel=0.01))
    cards = [("Lorenz Schlittenbauer", "Nachbar", "man", -0.62, 2.0), ("Karl Gabriel", "Ehemann", "soldier", 0.62, 2.0),
             ("Adolf & Anton Gump", "Brüder", "man", 0.0, 1.42)]
    center = Vector((0.0, 2.47, 1.98))
    hc = tex_label("bc_center", ["HINTERKAIFECK", "31.3./1.4.1922"], 900, 300, (232, 226, 210), [FX, FM])
    objs.append(sheet("bcenter", 0.36, 0.12, center + Vector((0, -0.005, 0)), tex_mat("bcm", hc), rx=math.radians(90), thick=0))
    HOT["board_center"] = center
    for i, (n, sub, kd, x, z) in enumerate(cards):
        p = tex_board_card(n, sub, kd, 30 + i)
        loc = Vector((x, 2.475, z))
        o = sheet("bcard%d" % i, 0.28, 0.33, loc, tex_mat("bcard%d" % i, p), rx=math.radians(90), thick=0)
        o.rotation_euler = (math.radians(90), rnd.uniform(-0.06, 0.06), 0)
        objs.append(o)
        objs.append(sph("bpin%d" % i, 0.012, loc + Vector((0, -0.02, 0.15)), M["red"]))
        # нить к центру
        a = loc + Vector((0, -0.02, 0.15)); b = center + Vector((0, -0.02, 0))
        mid = (a + b) / 2; dv = b - a
        s_ = cyl("str%d" % i, 0.002, 0.002, dv.length, mid, M["redstr"], n=6)
        s_.rotation_mode = "QUATERNION"; s_.rotation_quaternion = dv.to_track_quat("Z", "Y")
        objs.append(s_)
        HOT["bcard%d" % i] = loc
    # заметки
    for j in range(5):
        x = rnd.uniform(-0.9, 0.9); z = rnd.uniform(1.25, 2.25)
        if abs(x) < 0.25 and z > 1.8: continue
        objs.append(sheet("bnote%d" % j, 0.14, 0.1, (x, 2.476, z), M["note"], rx=math.radians(90), thick=0))
    GROUPS["board"] = objs

KX = 40.0       # кухня
def build_kitchen():
    o = []
    x0 = KX
    o.append(box("kfloor", 5, 4.6, 0.05, (x0, 0, -0.025), M["floor"]))
    o.append(box("kwallb", 5, 0.15, 2.6, (x0, 2.3, 1.3), M["plaster"]))
    o.append(box("kwalll", 0.15, 4.6, 2.6, (x0 - 2.5, 0, 1.3), M["plaster"]))
    o.append(box("kwallr", 0.15, 4.6, 2.6, (x0 + 2.5, 0, 1.3), M["plaster"]))
    o.append(box("kceil", 5, 4.6, 0.08, (x0, 0, 2.62), M["planks"]))
    for i in range(5):
        o.append(box("kbeam", 0.16, 4.6, 0.18, (x0 - 2 + i, 0, 2.5), M["beam"]))
    # окно в левой стене
    o.append(box("kwin", 0.05, 0.8, 0.9, (x0 - 2.43, 0.6, 1.5), M["win"]))
    o.append(box("kwinf", 0.08, 0.06, 0.9, (x0 - 2.40, 0.6, 1.5), M["beam"]))
    o.append(box("kwinf2", 0.08, 0.8, 0.06, (x0 - 2.40, 0.6, 1.5), M["beam"]))
    L = bpy.data.lights.new("moonin", "AREA"); L.energy = 60; L.size = 0.8; L.color = srgb("#7090d0")
    lo = link(bpy.data.objects.new("moonin", L)); lo.location = (x0 - 2.3, 0.6, 1.5)
    lo.rotation_euler = (0, math.radians(-70), 0); o.append(lo)
    # стол, лавка
    TZ = 0.78
    o.append(box("ktable", 1.6, 0.9, 0.05, (x0, 0.2, TZ - 0.025), M["desk"], bevel=0.01))
    for sx in (-0.7, 0.7):
        for sy in (-0.3, 0.3):
            o.append(box("kleg", 0.07, 0.07, TZ - 0.05, (x0 + sx, 0.2 + sy, (TZ - 0.05) / 2), M["beam"]))
    o.append(box("kbench", 1.5, 0.3, 0.05, (x0, 0.95, 0.45), M["beam"]))
    o.append(box("kbench2", 1.5, 0.3, 0.05, (x0, -0.55, 0.45), M["beam"]))
    # лампа на столе
    o.append(cyl("kl_base", 0.06, 0.05, 0.08, (x0 - 0.45, 0.35, TZ + 0.04), M["brass"]))
    o.append(cyl("kl_glass", 0.035, 0.03, 0.18, (x0 - 0.45, 0.35, TZ + 0.17), M["lampglow"]))
    L = bpy.data.lights.new("klamp", "POINT"); L.energy = 45; L.color = srgb("#ffa850"); L.shadow_soft_size = 0.03
    lo = link(bpy.data.objects.new("klamp", L)); lo.location = (x0 - 0.45, 0.35, TZ + 0.2); o.append(lo)
    # газета
    np_ = tex_newspaper()
    o.append(sheet("knews", 0.42, 0.56, (x0 + 0.15, 0.15, TZ + 0.001), tex_mat("newsm", np_), rz=0.35))
    HOT["news"] = Vector((x0 + 0.15, 0.15, TZ))
    # хлеб, нож, тарелка
    o.append(cyl("kplate", 0.15, 0.13, 0.02, (x0 - 0.1, 0.45, TZ + 0.01), M["plate"]))
    o.append(sph("kbread", 0.13, (x0 - 0.12, 0.45, TZ + 0.092), M["bread"], (1.4, 0.95, 0.55)))
    o.append(cyl("kcut", 0.07, 0.07, 0.004, (x0 + 0.062, 0.45, TZ + 0.092), M["crumb"], rot=(0.0, math.pi / 2, 0)))
    o.append(cyl("kslice", 0.07, 0.07, 0.015, (x0 + 0.2, 0.36, TZ + 0.03), M["crumb"]))
    o.append(box("kknife", 0.22, 0.025, 0.004, (x0 + 0.05, 0.28, TZ + 0.025), M["iron"], rot=(0, 0, 0.5)))
    HOT["bread"] = Vector((x0 - 0.05, 0.45, TZ + 0.05))
    # кахельная печь
    o.append(box("kstove", 0.9, 0.7, 1.4, (x0 + 1.8, 1.8, 0.7), M["stove"], bevel=0.03))
    o.append(box("kstovetop", 1.0, 0.8, 0.08, (x0 + 1.8, 1.8, 1.44), M["iron"]))
    o.append(box("kember", 0.25, 0.02, 0.15, (x0 + 1.8, 1.44, 0.35), M["ember"]))
    L = bpy.data.lights.new("kember", "POINT"); L.energy = 8; L.color = srgb("#ff6020")
    lo = link(bpy.data.objects.new("kemberL", L)); lo.location = (x0 + 1.8, 1.3, 0.35); o.append(lo)
    # шкаф с открытым ящиком и деньгами
    cx_ = x0 - 1.4
    o.append(box("kcup", 1.2, 0.5, 1.9, (cx_, 2.0, 0.95), M["beam"], bevel=0.02))
    o.append(box("kdrawer_bottom", 0.9, 0.42, 0.02, (cx_, 1.55, 0.92), M["planks"]))
    for sx in (-0.45, 0.45):
        o.append(box("kdside", 0.02, 0.42, 0.14, (cx_ + sx, 1.55, 0.99), M["planks"]))
    o.append(box("kdfront", 0.94, 0.03, 0.18, (cx_, 1.33, 0.99), M["beam"]))
    for i in range(70):
        x = cx_ + rnd.uniform(-0.4, 0.4); y = 1.55 + rnd.uniform(-0.18, 0.18)
        o.append(cyl("coin", 0.012, 0.012, 0.003, (x, y, 0.935 + rnd.uniform(0, 0.02)), M["gold"],
                     rot=(rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), 0), n=16))
    for i in range(6):
        o.append(sheet("note", 0.16, 0.08, (cx_ + rnd.uniform(-0.3, 0.3), 1.55 + rnd.uniform(-0.1, 0.1), 0.94 + i * 0.002),
                       mat("bill%d" % i, srgb("#8a9a7a"), 0.8), rz=rnd.uniform(-0.6, 0.6)))
    HOT["money"] = Vector((cx_, 1.55, 0.95))
    # доска с ключами
    o.append(box("krack", 0.6, 0.03, 0.14, (x0 + 0.6, 2.21, 1.6), M["beam"]))
    for i in range(3):
        hx = x0 + 0.42 + i * 0.18
        o.append(cyl("khook", 0.006, 0.006, 0.06, (hx, 2.165, 1.62), M["brass"], rot=(math.pi / 2, 0, 0)))
        if i != 1:
            r_ = bpy_torus("kring", 0.026, 0.006, (hx, 2.15, 1.59), M["brass"]); r_.rotation_euler = (math.pi / 2, 0, 0); o.append(r_)
            o.append(box("kshaft", 0.012, 0.012, 0.12, (hx, 2.15, 1.505), M["brass"]))
            o.append(box("kbit", 0.03, 0.01, 0.025, (hx + 0.015, 2.15, 1.46), M["brass"]))
        else:
            o.append(box("kdust", 0.05, 0.004, 0.2, (hx, 2.192, 1.52), mat("dust", srgb("#cfc4ae"), 0.95)))
    HOT["keyhook"] = Vector((x0 + 0.6, 2.18, 1.6))
    GROUPS["kitchen"] = o

AX = 80.0       # чердак
def build_attic():
    o = []; x0 = AX
    Lh = 9.0
    o.append(box("afloor1", 6, Lh - 1.4, 0.06, (x0, 0.7, 0), M["planks"]))
    o.append(box("afloor2", 6 - 1.2, 1.4, 0.06, (x0 + 0.6, -Lh / 2 + 0.7, 0), M["planks"]))      # с люком слева
    for i in range(12):
        y = -Lh / 2 + i * 0.8
        for sx in (-1, 1):
            o.append(box("rafter", 0.12, 0.16, 4.3, (x0 + sx * 1.5, y, 1.55), M["beam"], rot=(0, sx * math.radians(-44), 0)))
    for sx in (-1, 1):
        o.append(box("roofb", 0.03, Lh, 4.4, (x0 + sx * 1.62, 0, 1.62), M["planks"], rot=(0, sx * math.radians(-44), 0)))
    o.append(box("ridge", 0.14, Lh, 0.16, (x0, 0, 3.0), M["beam"]))
    o.append(box("tie", 4.2, 0.12, 0.14, (x0, 1.0, 1.4), M["beam"]))
    o.append(box("tie2", 4.2, 0.12, 0.14, (x0, -2.2, 1.4), M["beam"]))
    o.append(box("gable", 6, 0.1, 3.2, (x0, Lh / 2, 1.5), M["planks"]))
    o.append(box("gwin", 0.4, 0.05, 0.4, (x0, Lh / 2 - 0.06, 1.7), M["win"]))
    L = bpy.data.lights.new("amoon", "SPOT"); L.energy = 400; L.color = srgb("#7a98e0"); L.spot_size = math.radians(30)
    L.shadow_soft_size = 0.02
    lo = link(bpy.data.objects.new("amoon", L)); lo.location = (x0, Lh / 2 - 0.15, 1.75)
    lo.rotation_euler = (math.radians(-110), 0, 0); o.append(lo)
    L = bpy.data.lights.new("afill", "AREA"); L.energy = 90; L.size = 4; L.color = srgb("#5a70a8")
    lo = link(bpy.data.objects.new("afill", L)); lo.location = (x0, 0, 2.7); o.append(lo)
    for i in range(5):
        o.append(sph("hay", 0.8, (x0 + rnd.uniform(-1.2, 1.2), rnd.uniform(0, 4), 0.1), M["hay"], (1.2, 1.0, 0.45), seg=16))
    o.append(box("chest", 0.9, 0.5, 0.5, (x0 + 1.3, -1.5, 0.25), M["beam"]))
    # свет снизу через люк
    L = bpy.data.lights.new("hatch", "AREA"); L.energy = 0; L.size = 0.9; L.color = srgb("#ffa040")
    lo = link(bpy.data.objects.new("hatch", L)); lo.location = (x0 - 2.4, -Lh / 2 + 0.7, -0.3)
    lo.rotation_euler = (0, 0, 0); o.append(lo)
    GROUPS["attic"] = o
    HOT["attic_dark"] = Vector((x0, 2.0, 1.2))

BX = 120.0      # амбар
def build_barn():
    o = []; x0 = BX
    o.append(box("bfloor", 8, 12, 0.05, (x0, 0, 0), M["floor"]))
    for sx in (-1, 1):
        o.append(box("bwall", 0.12, 12, 4.5, (x0 + sx * 4, 0, 2.25), M["planks"]))
    o.append(box("bback", 8, 0.12, 4.5, (x0, 6, 2.25), M["planks"]))
    # передняя стена с открытой дверью
    o.append(box("bfront1", 4.6, 0.12, 4.5, (x0 - 1.7, -6, 2.25), M["planks"]))
    o.append(box("bfront2", 1.6, 0.12, 4.5, (x0 + 3.2, -6, 2.25), M["planks"]))
    o.append(box("bfront3", 1.8, 0.12, 1.3, (x0 + 1.5, -6, 3.85), M["planks"]))
    o.append(box("bdoor", 0.08, 1.7, 3.1, (x0 + 0.62, -6.85, 1.55), M["planks"], rot=(0, 0, 0.1)))
    o.append(box("bceil", 8, 12, 0.1, (x0, 0, 4.5), M["planks"]))
    for i in range(6):
        o.append(box("bbeam", 8, 0.2, 0.25, (x0, -5 + i * 2, 3.6), M["beam"]))
        o.append(box("bpost", 0.22, 0.22, 3.6, (x0 - 1.8, -5 + i * 2, 1.8), M["beam"]))
    for i in range(6):
        o.append(sph("bhay", 1.2, (x0 + rnd.uniform(0.5, 3.0), rnd.uniform(-2, 5), 0.2), M["hay"], (1.1, 1.3, 0.55), seg=16))
    # лунный свет через дверь
    L = bpy.data.lights.new("bmoon", "SPOT"); L.energy = 7000; L.color = srgb("#7a98e0"); L.spot_size = math.radians(40)
    L.shadow_soft_size = 0.05
    lo = link(bpy.data.objects.new("bmoon", L)); lo.location = (x0 + 1.8, -10, 3.5)
    lo.rotation_euler = (math.radians(62), 0, math.radians(8)); o.append(lo)
    # фонарь на балке
    o.append(cyl("blantern", 0.07, 0.07, 0.18, (x0 - 1.5, 1.0, 3.2), M["lampglow"]))
    L = bpy.data.lights.new("blan", "POINT"); L.energy = 70; L.color = srgb("#ff9840"); L.shadow_soft_size = 0.04
    lo = link(bpy.data.objects.new("blan", L)); lo.location = (x0 - 1.5, 1.0, 3.05); o.append(lo)
    GROUPS["barn"] = o

# ================================================================ мир, камера, рендер
def build_world():
    w = bpy.data.worlds.new("w"); S.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (*srgb("#0a0d14"), 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.3

def setup_render():
    S.render.engine = "CYCLES"; S.cycles.device = "CPU"; S.cycles.samples = SAMPLES
    S.cycles.use_adaptive_sampling = True; S.cycles.adaptive_threshold = 0.05
    S.cycles.use_denoising = True
    try: S.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception: pass
    S.cycles.max_bounces = 4; S.cycles.diffuse_bounces = 2; S.cycles.glossy_bounces = 2
    S.cycles.transmission_bounces = 2; S.cycles.transparent_max_bounces = 4
    S.render.resolution_x, S.render.resolution_y = RES; S.render.resolution_percentage = 100
    S.view_settings.view_transform = "AgX"
    try: S.view_settings.look = "AgX - Medium High Contrast"
    except Exception: pass
    S.view_settings.exposure = 0.3
    S.render.image_settings.file_format = "PNG"

def build_camera():
    cd = bpy.data.cameras.new("cam"); cam = link(bpy.data.objects.new("cam", cd)); S.camera = cam
    cd.sensor_width = 36; cd.dof.use_dof = True; cd.dof.aperture_blades = 7
    foc = link(bpy.data.objects.new("focus", None)); cd.dof.focus_object = foc
    tgt = link(bpy.data.objects.new("target", None))
    c = cam.constraints.new("TRACK_TO"); c.target = tgt; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
    return cam, cd, foc, tgt

def V(*a): return Vector(a)

def plate_defs(Z):
    D = lambda x, y: V(x, y, Z)
    return {
        "desk_map": dict(g=["desk_base", "map"], cam=V(0.15, -0.95, Z + 0.95), tgt=D(0.0, 0.08), lens=40, f=2.8, focus=HOT["map_pin"],
                         hot=["map_pin"]),
        "desk_family": dict(g=["desk_base", "family"], cam=V(0.0, -1.05, Z + 1.2), tgt=D(-0.05, 0.0), lens=36, f=3.5, focus=D(0, 0),
                            hot=["fam%d" % i for i in range(7)]),
        "desk_court": dict(g=["desk_base", "court"], cam=V(-0.2, -0.75, Z + 0.7), tgt=D(0.05, 0.0), lens=40, f=2.2, focus=HOT["court"],
                           hot=["court", "court_bottom"]),
        "desk_calendar": dict(g=["desk_base", "calendar"], cam=V(0.0, -0.85, Z + 0.45), tgt=HOT["cal"], lens=45, f=2.0, focus=HOT["cal"]),
        "desk_days": dict(g=["desk_base", "days"], cam=V(0.0, -0.95, Z + 0.95), tgt=D(0.0, 0.03), lens=38, f=3.2, focus=D(0, 0),
                          hot=["day0", "day1", "day2"]),
        "desk_munich": dict(g=["desk_base", "munich"], cam=V(-0.6, -1.3, Z + 0.55), tgt=HOT["crate"], lens=42, f=2.4, focus=HOT["crate"]),
        "desk_weapon": dict(g=["desk_base", "weapon"], cam=V(0.05, -0.85, Z + 0.75), tgt=D(0.12, 0.0), lens=36, f=3.2, focus=D(0.15, 0.0),
                            hot=["weapon"], key=(V(0.6, -0.6, Z + 1.2), D(0.15, 0.0), 60)),
        "desk_students": dict(g=["desk_base", "students"], cam=V(0.0, -0.85, Z + 0.85), tgt=D(0.05, 0.05), lens=40, f=2.8,
                              focus=HOT["redact"], hot=["redact"]),
        "board": dict(g=["desk_base", "board"], cam=V(0.0, -0.2, 1.75), tgt=V(0.0, 2.5, 1.75), lens=32, f=4.0, focus=V(0, 2.5, 1.75),
                      hot=["board_center", "bcard0", "bcard1", "bcard2"], key=(V(-0.6, 0.6, 3.0), V(0.0, 2.5, 1.75), 220)),
        "kitchen_news": dict(g=["kitchen"], cam=V(KX + 0.75, -0.55, 1.35), tgt=HOT["news"], lens=40, f=2.0, focus=HOT["news"], hot=["news"]),
        "kitchen_bread": dict(g=["kitchen"], cam=V(KX + 0.55, -0.15, 1.05), tgt=HOT["bread"], lens=50, f=1.8, focus=HOT["bread"]),
        "kitchen_wide": dict(ev=0.9, g=["kitchen"], cam=V(KX + 2.1, -2.1, 1.6), tgt=V(KX - 0.6, 0.8, 0.9), lens=24, f=4.0, focus=V(KX, 0.2, 0.8)),
        "kitchen_money": dict(ev=0.7, g=["kitchen"], cam=V(KX - 1.25, 0.85, 1.6), tgt=HOT["money"], lens=40, f=2.8, focus=HOT["money"],
                              key=(V(KX - 1.0, 0.9, 2.2), HOT["money"], 40)),
        "kitchen_keys": dict(ev=0.8, g=["kitchen"], cam=V(KX + 0.35, 1.2, 1.45), tgt=HOT["keyhook"] + V(0, 0, -0.06), lens=55, f=2.8, focus=HOT["keyhook"],
                             key=(V(KX - 0.2, 1.3, 2.1), HOT["keyhook"], 25)),
        "attic_empty": dict(ev=1.4, key=(V(AX - 1.6, -2.6, 0.4), V(AX + 0.2, 1.5, 1.3), 90), g=["attic"], cam=V(AX - 0.6, -4.0, 1.4), tgt=V(AX, 3.0, 1.2), lens=28, f=3.2, focus=V(AX, 1.0, 1.0)),
        "attic_gruber": dict(ev=0.8, g=["attic"], cam=V(AX + 1.1, -3.9, 1.0), tgt=V(AX - 0.4, 1.0, 1.4), lens=28, f=3.2, focus=V(AX - 0.5, -0.5, 1.2),
                             people=[dict(x=AX - 0.5, y=-0.5, z=0.03, face=math.pi + 0.25, gun=True, lantern=True)], hatch=60),
        "barn_in": dict(ev=1.4, key=(V(BX - 1.2, 2.5, 2.6), V(BX + 1.0, -4.0, 0.8), 260), g=["barn"], cam=V(BX - 2.6, 4.5, 1.7), tgt=V(BX + 1.2, -6, 1.2), lens=26, f=4.0, focus=V(BX + 1.2, -4, 1.0)),
    }

def main():
    setup_render(); build_world()
    Z = build_desk(); build_desk_props(Z); build_board(Z)
    build_kitchen(); build_attic(); build_barn()
    for g in GROUPS.values():
        for o in g: o.hide_render = True
    cam, cd, foc, tgt = build_camera()
    defs = plate_defs(Z)
    for n in (PLATES or list(defs)):
        d = defs[n]
        for g in GROUPS.values():
            for o in g: o.hide_render = True
        for g in d["g"]:
            for o in GROUPS[g]: o.hide_render = False
        extra = []
        for pp in d.get("people", []): extra += person(**pp)
        if "key" in d:
            kl = bpy.data.objects.get("keylight")
            if kl is None:
                L = bpy.data.lights.new("keylight", "AREA"); L.size = 1.2; L.color = srgb("#ffd0a0")
                kl = link(bpy.data.objects.new("keylight", L))
            kl.location = d["key"][0]; kl.data.energy = d["key"][2]
            kl.rotation_euler = (d["key"][1] - d["key"][0]).to_track_quat("-Z", "Y").to_euler()
        elif bpy.data.objects.get("keylight"):
            bpy.data.objects["keylight"].data.energy = 0
        S.view_settings.exposure = d.get("ev", 0.3)
        hatch = bpy.data.objects.get("hatch")
        if hatch: hatch.data.energy = d.get("hatch", 0)
        cam.location = d["cam"]; tgt.location = d["tgt"]; cd.lens = d["lens"]; cd.dof.aperture_fstop = d["f"]
        foc.location = d["focus"]
        bpy.context.view_layer.update()
        meta = {}
        for k in d.get("hot", []):
            p = world_to_camera_view(S, cam, HOT[k]); meta[k] = [p.x, 1 - p.y]
        S.render.filepath = os.path.join(OUT, "plates", n + ".png")
        bpy.ops.render.render(write_still=True)
        json.dump(meta, open(os.path.join(OUT, "plates", n + ".json"), "w"))
        for e in extra: bpy.data.objects.remove(e, do_unlink=True)
        print("PLATE", n, flush=True)

if __name__ == "__main__":
    main()
