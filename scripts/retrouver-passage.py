#!/usr/bin/env python3
"""
Retrouve dans un SRT de long format le passage dont on donne le texte
(typiquement un extrait sorti d'Opus Clip, souvent deja recoupe).

Aligne mot a mot avec difflib et signale les TROUS : si Opus Clip a saute du
contenu, on le voit au lieu de couper un bloc qui contient des passages
non voulus.

    python3 retrouver-passage.py transcript.srt passage.txt
"""
import re
import sys
import unicodedata
from difflib import SequenceMatcher


def sec(t):
    h, m, r = t.split(":")
    s, ms = r.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def mmss(x):
    return f"{int(x)//60:02d}:{x - 60*(int(x)//60):06.3f}"


def cle(w):
    w = unicodedata.normalize("NFD", w.lower())
    w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", w)


def mots_du_srt(path):
    """Liste (t0, t1, mot). Timecodes interpoles dans chaque segment."""
    out = []
    for bloc in open(path, encoding="utf-8").read().strip().split("\n\n"):
        L = bloc.strip().split("\n")
        if len(L) < 3:
            continue
        a, b = L[1].split(" --> ")
        t0, t1 = sec(a), sec(b)
        mots = " ".join(L[2:]).split()
        if not mots:
            continue
        pas = (t1 - t0) / len(mots)
        for i, m in enumerate(mots):
            out.append((t0 + i * pas, t0 + (i + 1) * pas, m))
    return out


def main():
    srt, passage = sys.argv[1], sys.argv[2]
    src = mots_du_srt(srt)
    cible = open(passage, encoding="utf-8").read().split()

    a = [cle(w) for _, _, w in src]
    b = [cle(w) for w in cible]
    a = [x if x else "\x00" for x in a]
    b = [x if x else "\x00" for x in b]

    sm = SequenceMatcher(None, a, b, autojunk=False)
    blocs = [bl for bl in sm.get_matching_blocks() if bl.size >= 4]
    if not blocs:
        sys.exit("aucune correspondance trouvee")

    # on fusionne les blocs separes par moins de 2 s de source
    fus = []
    for bl in blocs:
        d, f = bl.a, bl.a + bl.size - 1
        if fus and src[d][0] - src[fus[-1][1]][1] < 2.0:
            fus[-1] = (fus[-1][0], f)
        else:
            fus.append((d, f))

    total = 0.0
    print(f"{len(fus)} segment(s) trouve(s) dans {srt.split('/')[-1]}\n")
    for i, (d, f) in enumerate(fus, 1):
        t0, t1 = src[d][0], src[f][1]
        total += t1 - t0
        extrait = " ".join(w for _, _, w in src[d:d + 9])
        fin = " ".join(w for _, _, w in src[max(d, f - 8):f + 1])
        print(f"[{i}] {mmss(t0)} -> {mmss(t1)}   ({t1-t0:.1f}s)")
        print(f"     debut : {extrait}...")
        print(f"     fin   : ...{fin}")
        if i < len(fus):
            saut = src[fus[i][0]][0] - t1
            print(f"     >>> TROU de {saut:.1f}s avant le segment suivant")
        print()
    print(f"total retenu : {total:.1f}s")
    couv = sum(bl.size for bl in blocs) / len(b) * 100
    print(f"couverture du texte fourni : {couv:.0f}%")
    print("\nffmpeg -ss / -to :")
    for d, f in fus:
        print(f"  -ss {src[d][0]:.3f} -to {src[f][1]:.3f}")


if __name__ == "__main__":
    main()
