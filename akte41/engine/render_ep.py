# -*- coding: utf-8 -*-
"""Сборка серии: тайминг по озвучке, рендер кадров в 4 процесса, музыка, сведение.

python3 render_ep.py ../ep01 out_dir [--preview SECONDS] [--start S]
"""
import json, os, subprocess, sys, math, wave
import multiprocessing as mp
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

EP = os.path.abspath(sys.argv[1])
OUT = os.path.abspath(sys.argv[2])
PREVIEW = None
START = 0.0
if "--preview" in sys.argv:
    PREVIEW = float(sys.argv[sys.argv.index("--preview") + 1])
if "--start" in sys.argv:
    START = float(sys.argv[sys.argv.index("--start") + 1])
os.makedirs(OUT, exist_ok=True)
DRAW_FPS = 12
SR = 48000
LEAD = 0.6       # тишина перед первой фразой
GAP = 0.45
SCENE_GAP = 0.75
TAIL = 2.5
WIPE_SCENES = {"title", "map", "family", "calendar", "days", "money", "board", "weapon", "students", "outro"}


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", p]).decode().strip())


def timeline():
    segs = json.load(open(os.path.join(EP, "segments.json")))
    tl = []
    t = LEAD
    for i, s in enumerate(segs):
        d = dur(os.path.join(EP, "audio", s["id"] + ".mp3"))
        nxt = segs[i + 1]["scene"] if i + 1 < len(segs) else None
        gap = SCENE_GAP if nxt != s["scene"] else GAP
        start = 0.0 if i == 0 else t
        end = t + d + gap if nxt else t + d + TAIL
        tl.append(dict(id=s["id"], scene=s["scene"], start=start, voice=t, vdur=d, end=end))
        t = t + d + gap
    return tl


def render_chunk(args):
    k, f0, f1, tl, path = args
    import riso
    from scenes import SCENES
    from props import red_wipe
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{riso.W}x{riso.H}", "-r", str(DRAW_FPS), "-i", "-",
                           "-vf", "fps=24", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-maxrate", "12M", "-bufsize", "24M",
                           "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)
    prev = None
    for fno in range(f0, f1):
        tt = fno / DRAW_FPS
        seg = next((s for s in tl if s["start"] <= tt < s["end"]), tl[-1])
        idx = tl.index(seg)
        # сцена может длиться несколько сегментов подряд с одним именем — время считаем от первого
        j = idx
        while j > 0 and tl[j - 1]["scene"] == seg["scene"] and seg["scene"] not in ("tracks",):
            j -= 1
        s0 = tl[j]
        T = seg["end"] - s0["start"]
        t = tt - s0["start"]
        F = riso.Frame(fno * 3 + 11)
        SCENES[seg["scene"]](F, t, T)
        if seg["scene"] in WIPE_SCENES and t < 0.5:
            red_wipe(F, t / 0.5)
        fade = min(1.0, tt / 0.8) if tt < 0.8 else 1.0
        ff.stdin.write(F.composite(fno, fade).tobytes())
    ff.stdin.close()
    ff.wait()
    return path


# ------------------------------------------------------------ звук
def music(total, tl, path):
    n = int(total * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(4)
    out = np.zeros(n, np.float32)
    # гул: ре минор, медленные волны
    for f, a in [(36.71, .30), (73.42, .22), (110.0, .12), (146.83, .07), (174.61, .05), (220.0, .03)]:
        lfo = 0.6 + 0.4 * np.sin(2 * np.pi * t / (17 + f % 7) + f)
        out += a * lfo * np.sin(2 * np.pi * f * t + 0.3 * np.sin(2 * np.pi * 0.07 * t))
    # ветер: фильтрованный шум
    noise = rng.standard_normal(n).astype(np.float32)
    k = int(SR / 400)
    wind = np.convolve(noise, np.ones(k) / k, "same")
    wind *= 0.5 + 0.5 * np.sin(2 * np.pi * t / 11.0) ** 2
    out += 0.35 * wind
    # удары на сменах сцен
    for i, s in enumerate(tl):
        if i and s["scene"] != tl[i - 1]["scene"] and s["scene"] in WIPE_SCENES | {"farm_night", "barn", "discovery", "munich", "memorial"}:
            st = int(s["start"] * SR)
            L = int(2.2 * SR)
            if st + L < n:
                tt = np.arange(L) / SR
                boom = np.sin(2 * np.pi * (55 - 20 * tt) * tt) * np.exp(-tt * 2.2)
                out[st:st + L] += 0.55 * boom
    # тиканье в «днях»
    for s in tl:
        if s["scene"] in ("days", "quiet", "calendar"):
            for x in np.arange(s["start"], s["end"], 1.0):
                st = int(x * SR)
                L = int(0.03 * SR)
                if st + L < n:
                    out[st:st + L] += 0.25 * rng.standard_normal(L) * np.exp(-np.arange(L) / (0.004 * SR))
    fade = np.minimum(1, np.minimum(t / 2.0, (total - t) / 3.0))
    out *= fade
    out /= np.max(np.abs(out)) + 1e-6
    pcm = (out * 0.8 * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def voice_track(tl, total, path):
    inputs, filt = [], []
    for i, s in enumerate(tl):
        inputs += ["-i", os.path.join(EP, "audio", s["id"] + ".mp3")]
        ms = int(s["voice"] * 1000)
        filt.append(f"[{i}:a]aresample={SR},adelay={ms}|{ms}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(tl)))
    filt.append(f"{mix}amix=inputs={len(tl)}:normalize=0,apad,atrim=0:{total:.3f}[v]")
    subprocess.check_call(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt),
                           "-map", "[v]", "-ac", "1", "-ar", str(SR), path])


def main():
    tl = timeline()
    total = tl[-1]["end"]
    json.dump(tl, open(os.path.join(OUT, "timeline.json"), "w"), indent=1)
    t0, t1 = START, (START + PREVIEW if PREVIEW else total)
    f0, f1 = int(t0 * DRAW_FPS), int(min(t1, total) * DRAW_FPS)
    nproc = os.cpu_count() or 4
    step = math.ceil((f1 - f0) / nproc)
    jobs = [(k, f0 + k * step, min(f1, f0 + (k + 1) * step), tl, os.path.join(OUT, f"chunk{k:02d}.mp4"))
            for k in range(nproc) if f0 + k * step < f1]
    with mp.Pool(len(jobs)) as pool:
        paths = pool.map(render_chunk, jobs)
    with open(os.path.join(OUT, "chunks.txt"), "w") as f:
        for p in paths:
            f.write(f"file '{p}'\n")
    subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i",
                           os.path.join(OUT, "chunks.txt"), "-c", "copy", os.path.join(OUT, "video.mp4")])
    vpath, mpath = os.path.join(OUT, "voice.wav"), os.path.join(OUT, "music.wav")
    voice_track(tl, total, vpath)
    music(total, tl, mpath)
    final = os.path.join(OUT, "final.mp4")
    flt = ("[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[v];"
           "[2:a]volume=0.11,highpass=f=30[m];"
           "[m][v]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=400[md];"
           "[v][md]amix=inputs=2:normalize=0,alimiter=limit=0.95[a]")
    # для превью обрезаем звук
    subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(OUT, "video.mp4"),
                           "-ss", f"{t0:.3f}", "-i", vpath, "-ss", f"{t0:.3f}", "-i", mpath,
                           "-filter_complex", flt.replace("[v][md]", "[vv][md]").replace("[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[v];", "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,asplit[v][vv];"),
                           "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                           "-shortest", "-movflags", "+faststart", final])
    print("done", final, "total", round(total, 1))


if __name__ == "__main__":
    main()
