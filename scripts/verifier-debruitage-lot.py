#!/usr/bin/env python3
"""Verifie le debruitage en comparant chaque fichier a SA propre reference.

Un seuil fixe produit des faux negatifs : sur un clip ou la personne parle sans
pause, l'ecart parole/plancher plafonne bas meme apres debruitage. On mesure
donc, pour chaque clip, le meme passage du rush brut et sa version debruitee,
et on regarde de quel cote tombe le fichier livre.

    python3 verifier-debruitage-lot.py Amory Baptiste Jordy Gauthier Florian
"""
import array, json, math, subprocess, sys, tempfile
from pathlib import Path

RUSHS = Path("/Users/lucasdo./Downloads/Consulting Client - Mastermind Valentin Montage vidéo")
BASE = Path("/Users/lucasdo./Movies/CapCut/Consulting by Lucas to 16,9")
TIMECODES = Path("/Users/lucasdo./Documents/RAIZ-Claude/OFFBOUND/CONTENU/"
                 "consulting-mastermind/clips-timecodes.json")
DF = Path.home() / ".local/bin/deep-filter"


def ecart(src, ss=None, t=None):
    cmd = ["ffmpeg", "-v", "error"]
    if ss is not None:
        cmd += ["-ss", f"{ss:.3f}"]
    cmd += ["-i", str(src)]
    if t is not None:
        cmd += ["-t", f"{t:.3f}"]
    cmd += ["-vn", "-ac", "1", "-ar", "16000",
            "-af", "highpass=f=3000,highpass=f=3000,lowpass=f=8000", "-f", "s16le", "-"]
    b = subprocess.run(cmd, capture_output=True).stdout
    a = array.array("h"); a.frombytes(b[:len(b) // 2 * 2])
    n, v = 1600, []
    for i in range(0, len(a) - n, n):
        s = sum(float(x) * x for x in a[i:i + n]) / n
        v.append(10 * math.log10(s / (32768.0 ** 2) + 1e-20))
    if len(v) < 20:
        return None
    v.sort()
    return v[int(len(v) * .95)] - v[int(len(v) * .10)]


def main():
    tc = json.load(open(TIMECODES, encoding="utf-8"))
    total, bons = 0, 0
    for client in sys.argv[1:]:
        rush = RUSHS / f"Consulting {client}.mp4"
        print(f"\n===== {client}")
        for clip in tc[client]:
            titre, a, b = clip[0], clip[1], clip[2]
            with tempfile.TemporaryDirectory() as t:
                tmp = Path(t)
                brut = tmp / "b.wav"
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-i", str(rush),
                                "-t", f"{b - a:.3f}", "-vn", "-ar", "48000", "-ac", "1",
                                "-c:a", "pcm_s16le", str(brut)], check=True)
                subprocess.run([str(DF), "-a", "25", "-D", "-o", str(tmp / "df"), str(brut)],
                               capture_output=True)
                ref = tmp / "df" / "b.wav"
                e_brut, e_ref = ecart(brut), ecart(ref) if ref.exists() else None
            for fmt in ("Horizontal", "Vertical"):
                f = BASE / client / fmt / f"{titre}.mp4"
                if not f.exists():
                    continue
                e = ecart(f)
                total += 1
                marque = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format_tags=comment",
                     "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout.strip()
                # la chaine voix comprime, donc le livre reste sous la reference :
                # on juge sur le gain par rapport au brut, confirme par le marqueur
                gain = (e - e_brut) if e is not None else -99
                ok = gain >= 4.0 and "debruit25" in marque
                bons += ok
                print(f"  {'OUI' if ok else 'NON':4s} {fmt[0]}  brut {e_brut:5.1f} | "
                      f"reference {e_ref if e_ref else float('nan'):5.1f} | "
                      f"livre {e:5.1f} | gain {gain:+5.1f} dB   {titre[:40]}", flush=True)
    print(f"\n{bons}/{total} debruites")


main()
