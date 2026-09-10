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

CHAINE = (
    "highpass=f=80,"                      # sous 80 Hz il n'y a que du bruit
    "equalizer=f=250:t=q:w=1.2:g=-2,"     # degage le bas-medium
    "equalizer=f=4000:t=q:w=1.5:g=2.0,"   # presence
    "acompressor=threshold=-20dB:ratio=2.5:attack=8:release=180:makeup=1.5,"
    "alimiter=limit=0.93,"
    "loudnorm=I=-14:TP=-1.5:LRA=11"
)
MARQUEUR = "voix affinee"


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
