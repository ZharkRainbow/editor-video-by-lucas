#!/usr/bin/env python3
"""Dit, fichier par fichier, si le debruitage DeepFilterNet a ete applique.

Indicateur : ecart entre le niveau de parole (p95) et le plancher (p10) dans la
bande 3-8 kHz, celle du brouhaha de salle. Mesure sur le rush Baptiste :
  brut 22 dB · debruite a 25 dB 35 dB · la musique a -40 LUFS ne la fausse pas.
Seuil retenu : 30 dB.

    python3 diagnostic-debruitage.py <dossier|fichier> [...]
"""
import array, math, subprocess, sys
from pathlib import Path

SEUIL = 30.0

def ecart(f):
    b = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-vn", "-ac", "1", "-ar", "16000",
                        "-af", "highpass=f=3000,highpass=f=3000,lowpass=f=8000",
                        "-f", "s16le", "-"], capture_output=True).stdout
    a = array.array("h"); a.frombytes(b[:len(b) // 2 * 2])
    n = 1600; v = []
    for i in range(0, len(a) - n, n):
        s = sum(float(x) * x for x in a[i:i + n]) / n
        v.append(10 * math.log10(s / (32768.0 ** 2) + 1e-20))
    if len(v) < 20:
        return None
    v.sort()
    return v[int(len(v) * .95)] - v[int(len(v) * .10)]

fichiers = []
for a in sys.argv[1:]:
    p = Path(a)
    fichiers += sorted(p.rglob("*.mp4")) if p.is_dir() else [p]

faits, absents = 0, []
for f in fichiers:
    e = ecart(f)
    if e is None:
        print(f"  ?      {f.name}  (trop court)"); continue
    ok = e >= SEUIL
    faits += ok
    if not ok:
        absents.append(f)
    print(f"  {'OUI' if ok else 'NON':4s} {e:5.1f} dB  {f.parent.parent.name}/{f.parent.name}/{f.name}",
          flush=True)
print(f"\n{faits}/{len(fichiers)} debruites, {len(absents)} a traiter")
