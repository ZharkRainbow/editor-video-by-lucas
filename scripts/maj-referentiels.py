#!/usr/bin/env python3
"""Recopie les bornes validees de la selection Gauthier/Florian dans les deux
referentiels partages : clips-timecodes.json et Timecodes-shorts.md."""
import json
from pathlib import Path

sel = json.load(open(Path(__file__).with_name("selection-gauthier-florian.json"), encoding="utf-8"))
MARQUE = "\n\n---\n\n## Selection Claude"
DUREE = {"Gauthier": 829.013, "Florian": 1511.573}

# 1. clips-timecodes.json
p = Path("/Users/lucasdo./Documents/RAIZ-Claude/OFFBOUND/CONTENU/consulting-mastermind/clips-timecodes.json")
d = json.load(open(p, encoding="utf-8"))
for c in DUREE:
    # seuls les clips valides ; un 4e element porte les mini-cuts eventuels
    d[c] = [[cl[1], cl[2], cl[3]] + ([cl[6]] if len(cl) > 6 else [])
            for cl in sel[c] if cl[4] == "prio"]
d["_note_gauthier_florian"] = ("Selection editoriale Claude (pas d'Opus Clip sur ces deux consultings), "
                               "bornes recalees au mot pres. Priorites et accroches dans "
                               "OFFBOUND/APPS/video-reels/scripts/selection-gauthier-florian.json")
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# 2. Timecodes-shorts.md
doc = Path("/Users/lucasdo./Movies/CapCut/Consulting by Lucas to 16,9/Timecodes-shorts.md")
txt = doc.read_text(encoding="utf-8")
if MARQUE in txt:
    txt = txt[:txt.index(MARQUE)]

def smpte(s, fps=25):
    f = round(s * fps)
    return f"{f//(3600*fps):02d}:{f//(60*fps)%60:02d}:{f//fps%60:02d}:{f%fps:02d}"

bloc = [MARQUE + " (pas d'Opus Clip sur ces deux consultings)\n",
        "Valentin n'a pas fait passer Gauthier ni Florian dans Opus Clip. Les bornes viennent\n"
        "d'une lecture integrale des deux transcripts, puis d'un recalage au mot pres\n"
        "(whisper mot-a-mot sur +/-8 s autour de chaque borne, script `affiner-bornes.py`).\n"
        "Priorite et accroche de chaque clip :\n"
        "`OFFBOUND/APPS/video-reels/scripts/selection-gauthier-florian.json`\n"]
for client, duree in DUREE.items():
    bloc.append(f"\n## {client}\n")
    bloc.append(f"Rush : {int(duree)//60:02d}:{duree%60:06.3f} · 25 fps · {len(sel[client])} clips\n")
    bloc.append("| # | Clip | Debut | Fin | Duree | Debut (s) | Fin (s) | Prio |")
    bloc.append("|---|---|---|---|---|---|---|---|")
    for i, cl in enumerate(sel[client], 1):
        titre, a, b, prio = cl[1], cl[2], cl[3], cl[4]
        cuts = f" · {len(cl[6])} segments" if len(cl) > 6 else ""
        bloc.append(f"| {i} | {titre.split(' ', 1)[1]}{cuts} | `{smpte(a)}` | `{smpte(b)}` | "
                    f"{b-a:.2f}s | {a:.3f} | {b:.3f} | {prio} |")
    bloc.append("")
doc.write_text(txt.rstrip() + "\n".join(bloc) + "\n", encoding="utf-8")
print("clips-timecodes.json et Timecodes-shorts.md a jour")
