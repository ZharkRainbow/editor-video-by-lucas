#!/usr/bin/env python3
"""Monte la selection de 7 passages faite par Valentin lui-meme, au meme
format split screen que le lot principal. Les titres sont ceux qu'il a mis
en tete de chaque reel dans Opus Clip, repris tels quels."""
import sys
from importlib import import_module
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
m = import_module("monter-split-masterclass")

# (debut, fin, titre exact de Valentin)
LOT = [
    (   0.0,   63.5, "Mes systemes pour recruter des A-players"),
    ( 176.5,  259.3, "Les 5 premiers recrutements sont les + importants"),
    ( 442.0,  544.6, "La formule pour savoir combien payer son equipe"),
    ( 649.7,  739.5, "Les maths derriere un excellent (ou mauvais) recrutement"),
    ( 728.0,  808.1, "Funnel de recrutement = Funnel de vente"),
    ( 903.0,  974.5, "J'ai eu +100 candidatures sur mon dernier recrutement"),
    (1045.9, 1084.0, "J'ai envoye 450 messages pour un seul recrutement"),
]

if __name__ == "__main__":
    m.DST.mkdir(parents=True, exist_ok=True)
    voulus = [int(a) for a in sys.argv[1:]]
    for i, (d, f, t) in enumerate(LOT, 1):
        if not voulus or i in voulus:
            m.rendre(f"VAL {i}", d, f, t)
    print("TERMINE")
