import json, re, sys
NUM = [("neunzehnhundertzweiundzwanzig","1922"),("neunzehnhundertfünfzehn","1915"),("neunzehnhundertvierzehn","1914"),
("Zweitausendsieben","2007"),("dreiundsechzig","63"),("zweiundsiebzig","72"),("fünfunddreißig","35"),("vierundvierzig","44"),
("siebzig Kilometer","70 Kilometer"),("der einunddreißigste März","der 31. März"),("zweitausendsieben","2007"),("dem vierten April","dem 4. April"),
("sieben Jahre alt","7 Jahre alt"),("Josef, zwei.","Josef, 2."),("Fünfzigerjahren","1950er-Jahren")]
segs = {s["id"]: s for s in json.load(open(sys.argv[1]))}
tl = json.load(open(sys.argv[2]))
def ts(x):
    ms = int(round(x * 1000)); return f"{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}"
out, n = [], 1
for s in tl:
    text = segs[s["id"]]["text"]
    sents = re.split(r"(?<=[.?!:])\s+", text)
    for a, b in NUM: sents = [x.replace(a, b) for x in sents]
    # длинные куски режем по запятым до ~84 символов
    parts = []
    for se in sents:
        k = max(1, -(-len(se) // 84))
        words = se.split(); per = len(se) / k; cur = ""
        for w in words:
            if cur and len(cur) + len(w) + 1 > per * 1.1 and len(parts) < 999:
                parts.append(cur); cur = w
            else:
                cur = (cur + " " + w).strip()
        parts.append(cur)
    tot = sum(len(p) for p in parts)
    t = s["voice"]
    for p in parts:
        d = s["vdur"] * len(p) / tot
        out.append(f"{n}\n{ts(t)} --> {ts(t + d - 0.05)}\n{p}\n"); n += 1; t += d
open(sys.argv[3], "w").write("\n".join(out))
print(n - 1, "cues")
