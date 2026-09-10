#!/usr/bin/env python3
"""Finition de la voix : un coup de propre sur le micro, rien de spectaculaire.

Le debruitage et la normalisation sont deja faits au rendu. Ici on ajoute
seulement ce qui manque a une voix de micro-cravate ou de Shure enregistree
en piece calme :
  - coupe des infrabasses (bruits de bureau, souffle de clim, plosives)
  - creux leger dans le bas-medium, qui degage la voix de la boue
  - presence discrete vers 4 kHz, pour l'intelligibilite en telephone
  - compression douce, pour que les fins de phrases ne decrochent pas
  - limiteur de securite, puis re-normalisation

Volontairement leger : une voix sur-traitee s'entend tout de suite.

    python3 affiner-voix.py <dossier|fichier> [...]
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Mesure sur 25 s de voix de Valentin, bande 3-9 kHz ou vivent les bruits de
# bouche : la chaine precedente les laissait a -29,2 dB avec des pics a -2,9.
# Celle-ci descend a -32,5 et -6,3, soit ~3,4 dB de gagne.
# Le boost de presence a 4 kHz a ete RETIRE : il amplifiait precisement ces
# bruits. On lui prefere un creux a 6,5 kHz.
CHAINE = (
    "highpass=f=85,"                      # sous 85 Hz il n'y a que du bruit de piece
    "adeclick,"                           # claquements de langue et clics de bouche
    "equalizer=f=250:t=q:w=1.2:g=-2,"     # degage le bas-medium
    "deesser=i=0.7:m=0.5:f=0.4,"          # sifflantes et salive
    "equalizer=f=6500:t=q:w=2:g=-2.5,"    # adoucit la zone la plus agressive
    "acompressor=threshold=-20dB:ratio=2.5:attack=10:release=200:makeup=1.5,"
    "alimiter=limit=0.93,"
    "loudnorm=I=-14:TP=-1.5:LRA=11"
)
MARQUEUR = "voix affinee v2"


def sh(c):
    return subprocess.run(c, capture_output=True, text=True)


def affiner(f: Path):
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format_tags=comment",
            "-of", "default=nk=1:nw=1", str(f)])
    if MARQUEUR in r.stdout:
        return "deja fait"
    with tempfile.TemporaryDirectory() as t:
        out = Path(t) / ("a" + f.suffix)
        r = sh(["ffmpeg", "-y", "-i", str(f), "-af", CHAINE,
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-metadata", f"comment={MARQUEUR}",
                "-movflags", "+faststart", str(out)])
        if not out.exists():
            return "echec : " + r.stderr.strip()[-140:]
        shutil.move(str(out), str(f))
    r = sh(["ffmpeg", "-i", str(f), "-af", "loudnorm=print_format=summary",
            "-f", "null", "-"])
    m = re.search(r"Input Integrated:\s*(-?[\d.]+)", r.stderr)
    return f"{m.group(1)} LUFS" if m else "ok"


if __name__ == "__main__":
    cibles = []
    for a in sys.argv[1:]:
        p = Path(a)
        cibles += sorted(p.rglob("*.mp4")) if p.is_dir() else [p]
    for f in cibles:
        print(f"{f.name[:52]:54s} -> {affiner(f)}", flush=True)
    print("TERMINE")
