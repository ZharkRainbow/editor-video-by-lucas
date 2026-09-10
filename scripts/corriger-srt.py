#!/usr/bin/env python3
"""Applique le dictionnaire Offbound de corriger-transcript.py a un fichier SRT.

    python3 corriger-srt.py transcript-brut.srt   ->  transcript-brut-corrige.srt (+ .txt)
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from importlib import import_module
corriger = import_module("corriger-transcript").corriger


def main():
    src = Path(sys.argv[1])
    blocs = src.read_text(encoding="utf-8").strip().split("\n\n")
    sortie, plein, change = [], [], 0
    for b in blocs:
        L = b.strip().split("\n")
        if len(L) < 3:
            continue
        num, tc, texte = L[0], L[1], " ".join(L[2:]).strip()
        mots = texte.split()
        corr = [w for _, _, w in corriger([(0.0, 0.0, m) for m in mots])]
        if corr != mots:
            change += 1
        neuf = " ".join(corr)
        sortie.append(f"{num}\n{tc}\n{neuf}")
        plein.append(neuf)
    out = src.with_name(src.name.replace("-brut", "-corrige"))
    out.write_text("\n\n".join(sortie) + "\n", encoding="utf-8")
    out.with_suffix(".txt").write_text(" ".join(plein) + "\n", encoding="utf-8")
    print(f"{out.name} : {change} segment(s) corrige(s) sur {len(sortie)}")


if __name__ == "__main__":
    main()
