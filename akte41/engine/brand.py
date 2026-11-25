import os, sys, riso
from riso import W, H, rect, textpath, circle
from props import night_sky, forest, snow_ground, farm, footprints, stamp, snowfall
from PIL import Image
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
# баннер: 16:9, всё важное в центральной полосе (безопасная зона 1546x423 из 2560x1440)
F = riso.Frame(3)
night_sky(F, tone=0.88, moon=(1560, 330))
forest(F, -60, 760, 700, 170, seed=1)
forest(F, 1250, 1980, 690, 150, seed=3)
snow_ground(F, 700)
farm(F, 1450, 722, 0.45, lit=1.0, smoke=0.8, t=2.0)
footprints(F, [(820, 745), (1050, 760), (1250, 745), (1330, 722)], 1.0, size=0.8)
stamp(F, "AKTE 41", 960, 460, 120, -0.04)
F.knock(textpath(F, "Ungelöste Fälle aus Deutschland · animiert", 960, 615, 36, True, "center"))
Image.fromarray(F.composite(1)).resize((2560, 1440), Image.LANCZOS).save(f"{OUT}/banner_2560x1440.png")
# аватар
F = riso.Frame(7)
F.fill("navy", rect(F, -20, -20, W + 40, H + 40, amp=0), tone=0.95)
F.knock(circle(F, 960, 540, 400))
F.fill("grey", circle(F, 960, 540, 400), tone=0.08)
stamp(F, "41", 960, 470, 260, -0.07)
F.fill("navy", textpath(F, "AKTE", 960, 800, 100, True, "center"))
im = Image.fromarray(F.composite(2)).crop((960 - 470, 540 - 470, 960 + 470, 540 + 470)).resize((800, 800), Image.LANCZOS)
im.save(f"{OUT}/avatar_800.png")
