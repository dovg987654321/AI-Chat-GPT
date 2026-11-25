import sys, json, riso
from scenes import SCENES
from PIL import Image
names = sys.argv[2].split(",") if len(sys.argv) > 2 else list(SCENES)
frac = float(sys.argv[3]) if len(sys.argv) > 3 else 0.8
T = 12.0
ims = []
for i, n in enumerate(names):
    F = riso.Frame(i * 7 + 1)
    try:
        SCENES[n](F, T * frac, T)
    except Exception as e:
        import traceback; traceback.print_exc(); print("FAIL", n); continue
    ims.append((n, Image.fromarray(F.composite(i)).resize((480, 270))))
cols = 5
rows = (len(ims) + cols - 1) // cols
S = Image.new("RGB", (cols * 480, rows * 290), "white")
from PIL import ImageDraw
d = ImageDraw.Draw(S)
for k, (n, im) in enumerate(ims):
    x, y = (k % cols) * 480, (k // cols) * 290
    S.paste(im, (x, y)); d.text((x + 5, y + 272), n, fill="black")
S.save(sys.argv[1])
