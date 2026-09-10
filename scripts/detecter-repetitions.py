#!/usr/bin/env python3
"""Detecte les redites verbatim dans une transcription whisper mot a mot.

Entree : sortie de `whisper-cli -ml 1 -sow` (une ligne par mot).
Sortie : candidats de coupe au format JSON, regle Lucas = on garde la SECONDE prise.

Usage: detecter-repetitions.py mots.txt [--n-min 3] [--gap-max 14]
"""
import re, sys, json, unicodedata

LIGNE = re.compile(r"\[(\d\d):(\d\d):(\d\d\.\d+)\s*-->\s*(\d\d):(\d\d):(\d\d\.\d+)\]\s*(.*)")

def secondes(h, m, s):
    return int(h) * 3600 + int(m) * 60 + float(s)

def normaliser(mot):
    mot = unicodedata.normalize("NFD", mot.lower())
    mot = "".join(c for c in mot if unicodedata.category(c) != "Mn")
    mot = re.sub(r"[^a-z0-9' ]", " ", mot)
    return " ".join(mot.replace("'", " ").split())

def lire(chemin):
    mots = []
    for ligne in open(chemin, encoding="utf-8"):
        m = LIGNE.match(ligne.strip())
        if not m:
            continue
        brut = m.group(7).strip()
        cle = normaliser(brut)
        if not cle:
            continue
        t0 = secondes(*m.group(1, 2, 3))
        t1 = secondes(*m.group(4, 5, 6))
        for jeton in cle.split():
            mots.append({"t0": t0, "t1": t1, "brut": brut, "cle": jeton})
    return mots

def _txt(mots):
    out = []
    for w in mots:
        if not out or out[-1] != w["brut"]:
            out.append(w["brut"])
    return " ".join(out)


def detecter(mots, n_min=3, n_max=9, gap_max=14.0, fenetre=70):
    cles = [w["cle"] for w in mots]
    pris = set()
    trouves = []
    for n in range(n_max, n_min - 1, -1):
        for i in range(len(cles) - n):
            if any(k in pris for k in range(i, i + n)):
                continue
            motif = cles[i:i + n]
            for j in range(i + n, min(i + n + fenetre, len(cles) - n + 1)):
                if cles[j:j + n] != motif:
                    continue
                gap = mots[j]["t0"] - mots[i + n - 1]["t1"]
                if gap > gap_max:
                    break
                trouves.append({
                    "n": n,
                    "coupe_debut": round(mots[i]["t0"], 2),
                    "coupe_fin": round(mots[j]["t0"], 2),
                    "duree": round(mots[j]["t0"] - mots[i]["t0"], 2),
                    "motif": " ".join(motif),
                    "avant": _txt(mots[max(0, i - 10):i]),
                    "supprime": _txt(mots[i:j]),
                    "garde": _txt(mots[j:j + n + 10]),
                    "resultat": _txt(mots[max(0, i - 8):i])
                                + " >>> "
                                + _txt(mots[j:j + n + 8]),
                })
                for k in range(i, j + n):
                    pris.add(k)
                break
    return sorted(trouves, key=lambda c: c["coupe_debut"])

if __name__ == "__main__":
    chemin = sys.argv[1]
    args = sys.argv[2:]
    n_min = int(args[args.index("--n-min") + 1]) if "--n-min" in args else 3
    gap = float(args[args.index("--gap-max") + 1]) if "--gap-max" in args else 14.0
    print(json.dumps(detecter(lire(chemin), n_min=n_min, gap_max=gap), ensure_ascii=False, indent=1))
