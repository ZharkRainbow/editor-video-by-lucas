#!/usr/bin/env python3
"""Rend aux reels de la masterclass le son d'origine du micro.

Valentin ne veut aucune correction de voix sur la masterclass recrutement :
ni de-esser, ni egaliseur, ni compresseur, ni debruitage. On reprend donc
l'audio tel quel dans le rush et on le remuxe sur la video montee, qui n'est
jamais reencodee (-c:v copy). La musique disparait avec l'ancienne piste.

Seule exception assumee : une normalisation de loudness a -14 LUFS. Le rush
est a -23,3 LUFS, inpubliable tel quel a cote du reste du lot. C'est un
reglage de volume, pas un traitement de timbre. Passer --brut pour s'en
priver aussi.

    python3 restaurer-audio-masterclass.py [--brut]
"""
import array, math, subprocess, sys, tempfile
from pathlib import Path

RUSH = Path.home() / "Downloads/Ecran-1.mp4"   # l'audio du montage vient de ce flux
BASE = Path.home() / "Movies/CapCut/Valentin Masterclass"
DOSSIER = "Selection Valentin (Opus Clip)"
BRUT = "--brut" in sys.argv
MARQUEUR = "micro d'origine" + ("" if BRUT else " + loudnorm")

# Bornes relevees dans TIMECODES-selection-Valentin.txt, verifiees contre la
# duree de chaque fichier livre : les 7 sont des extraits continus.
VAL = {
    "VAL 1": (0.000, 63.500),
    "VAL 2": (176.500, 259.300),
    "VAL 3": (442.028, 544.523),
    "VAL 4": (649.700, 739.440),
    "VAL 5": (728.000, 808.100),
    "VAL 6": (903.000, 974.500),
    "VAL 7": (1045.900, 1084.000),
}


def sh(c):
    return subprocess.run(c, capture_output=True, text=True)


def enveloppe(src, ss=None, t=None):
    cmd = ["ffmpeg", "-v", "error"]
    if ss is not None:
        cmd += ["-ss", f"{ss:.3f}"]
    cmd += ["-i", str(src)]
    if t is not None:
        cmd += ["-t", f"{t:.3f}"]
    cmd += ["-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"]
    b = subprocess.run(cmd, capture_output=True).stdout
    a = array.array("h"); a.frombytes(b[:len(b) // 2 * 2])
    n, e = 80, []
    for i in range(0, len(a) - n, n):
        e.append(math.sqrt(sum(float(x) * x for x in a[i:i + n]) / n))
    m = sum(e) / max(1, len(e))
    return [x - m for x in e]


def decalage(clip, debut, duree):
    a, b = enveloppe(RUSH, debut, duree), enveloppe(clip)
    L = min(len(a), len(b)) - 120
    if L <= 0:
        return 0.0
    best = (0, -1e18)
    for k in range(-50, 51):
        s = sum(a[i + 50] * b[i + 50 + k] for i in range(0, L, 3))
        if s > best[1]:
            best = (k, s)
    return best[0] / 100.0


def duree(f):
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "csv=p=0", str(f)])
    return float(r.stdout.strip())


def restaurer(f: Path, debut: float):
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format_tags=comment",
            "-of", "csv=p=0", str(f)])
    if MARQUEUR in r.stdout:
        return "deja fait"
    d = duree(f)
    dec = decalage(f, debut, d)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        son = tmp / "a.wav"
        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{debut - dec:.3f}", "-i", str(RUSH),
               "-t", f"{d:.3f}", "-vn", "-ar", "48000", "-ac", "2"]
        if not BRUT:
            cmd += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]
        cmd += [str(son)]
        sh(cmd)
        if not son.exists():
            return "ECHEC extraction, rien ecrit"
        out = tmp / f.name
        sh(["ffmpeg", "-y", "-v", "error", "-i", str(f), "-i", str(son),
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-shortest",
            "-metadata", f"comment={MARQUEUR}",
            "-movflags", "+faststart", str(out)])
        if not out.exists():
            return "ECHEC remux"
        out.replace(f)
    r = sh(["ffmpeg", "-i", str(f), "-af", "loudnorm=print_format=summary", "-f", "null", "-"])
    import re
    m = re.search(r"Input Integrated:\s*(-?[\d.]+)", r.stderr)
    return f"decalage {dec*1000:+5.0f} ms -> {m.group(1) if m else '?'} LUFS"


for fmt in ("Horizontal", "Vertical"):
    print(f"\n===== {fmt}")
    for f in sorted((BASE / fmt / DOSSIER).glob("*.mp4")):
        cle = f.name[:5]
        if cle not in VAL:
            print(f"  ? borne inconnue : {f.name}")
            continue
        print(f"  {f.stem[:52]:54s} {restaurer(f, VAL[cle][0])}", flush=True)
print("\nTERMINE")
