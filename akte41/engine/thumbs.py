import sys, os
import riso
from riso import W, H, rect, poly, circle, textpath, blob
from props import night_sky, forest, snow_ground, farm, footprints, stamp, label, figure
from scenes import TRACK
from PIL import Image
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)

def bigline(F, txt, x, y, size, box="red"):
    from riso import text_extent
    w = text_extent(txt, size) + size * 0.5
    F.paint(box, rect(F, x - 20, y - size * 0.95, w, size * 1.22))
    F.knock(textpath(F, txt, x + size * 0.12, y, size))

def base(F, fx=1300, sc=1.25, smoke=1.0, lit=1.0):
    night_sky(F, tone=0.9, moon=(1480, 200))
    forest(F, -60, 760, 760, 300, seed=1)
    snow_ground(F, 760)
    farm(F, fx, 900, sc, lit=lit, smoke=smoke, t=2.0)

# A: кто-то остался в доме
F = riso.Frame(5); base(F, 1350, 1.35, 1.0, 1.0)
F.push(); F.translate(1350, 900); F.scale(1.35)
F.paint("navy", rect(F, -232, -150, 54, 66)); F.knock(blob(F, -216, -118, 7, 4)); F.knock(blob(F, -194, -118, 7, 4))
F.pop()
bigline(F, "WER WAR", 70, 260, 150); bigline(F, "NOCH DA?", 70, 450, 150, "navy")
stamp(F, "AKTE 41", 1730, 110, 46, 0.05)
Image.fromarray(F.composite(1)).resize((1280, 720), Image.LANCZOS).save(f"{OUT}/thumb_A.png")

# B: следы туда, обратно нет
F = riso.Frame(9); base(F, 1450, 1.0, 0.4)
footprints(F, [(120, 1060), (420, 1000), (760, 960), (1060, 940), (1280, 925)], 1.0, size=2.0, tone=0.9)
bigline(F, "KEINE SPUR", 70, 230, 140); bigline(F, "ZURÜCK", 70, 410, 140, "navy")
stamp(F, "AKTE 41", 1730, 110, 46, 0.05)
Image.fromarray(F.composite(2)).resize((1280, 720), Image.LANCZOS).save(f"{OUT}/thumb_B.png")

# C: 6 и хутор, поисковый
F = riso.Frame(13); base(F, 1250, 1.3, 0.8)
stamp(F, "6", 330, 380, 300, -0.06)
bigline(F, "1922", 120, 820, 120, "navy")
stamp(F, "UNGELÖST", 1300, 330, 90, 0.05); stamp(F, "AKTE 41", 1730, 1000 - 900, 46, 0.05)
Image.fromarray(F.composite(3)).resize((1280, 720), Image.LANCZOS).save(f"{OUT}/thumb_C.png")

# превью-лист для проверки на телефоне
S = Image.new("RGB", (3 * 340, 200), "white")
for i, k in enumerate("ABC"):
    S.paste(Image.open(f"{OUT}/thumb_{k}.png").resize((320, 180), Image.LANCZOS), (10 + i * 340, 10))
S.save(f"{OUT}/thumbs_phone_preview.png")
