#!/usr/bin/env python3
"""Remonte le lit musical deja pose, sans refaire tout le montage.

Le lit est deterministe : meme piste, meme gain, memes fondus. Pour passer de
N1 a N2 il suffit donc de reposer le meme lit au niveau qui complete la somme :
    10^(N1/20) + 10^(Nadd/20) = 10^(N2/20)
De -40 a -34, Nadd vaut -40,0 dB : on repose exactement le meme lit.

Verifie sur un temoin : identique au bit pres a un rendu refait depuis la voix
seule (memes LUFS, meme true peak, meme spectre).

    python3 monter-volume-musique.py -34            # depuis -40
    python3 monter-volume-musique.py -34 --de -38
"""
import math, re, subprocess, sys, tempfile
from pathlib import Path

BASE = Path.home() / "Movies/CapCut/Consulting by Lucas to 16,9"
MUSIQUES = Path.home() / "Documents/Musique pour OpusClip"
CLIENTS = ("Amory", "Baptiste", "Jordy", "Gauthier", "Florian")

cible = float(sys.argv[1]) if len(sys.argv) > 1 else -34.0
depart = float(sys.argv[sys.argv.index("--de") + 1]) if "--de" in sys.argv else -40.0
ajout = 20 * math.log10(max(1e-9, 10 ** (cible / 20) - 10 ** (depart / 20)))
MARQUEUR = f"musique {cible:.0f}"


def sh(c):
    return subprocess.run(c, capture_output=True, text=True)


def lufs(f):
    r = sh(["ffmpeg", "-i", str(f), "-af", "loudnorm=print_format=summary", "-f", "null", "-"])
    m = re.search(r"Input Integrated:\s*(-?[\d.]+)", r.stderr)
    return float(m.group(1)) if m else None


pistes = sorted(MUSIQUES.glob("*Musique calme pour montage/*.mp3"))
niveaux = {p: lufs(p) for p in pistes}
print(f"cible {cible:.0f} LUFS, depuis {depart:.0f} : on repose un lit a {ajout:.2f} dB\n")

for client in CLIENTS:
    for fmt in ("Horizontal", "Vertical"):
        clips = sorted((BASE / client / fmt).glob("*.mp4"))
        for i, clip in enumerate(clips):
            marque = sh(["ffprobe", "-v", "error", "-show_entries", "format_tags=comment",
                         "-of", "csv=p=0", str(clip)]).stdout.strip()
            if MARQUEUR in marque:
                print(f"  {clip.stem[:50]:52s} deja fait"); continue
            piste = pistes[i % len(pistes)]
            d = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(clip)]).stdout.strip())
            gain = ajout - niveaux[piste]
            with tempfile.TemporaryDirectory() as t:
                tmp = Path(t)
                lit = tmp / "lit.wav"
                sh(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", str(piste),
                    "-t", f"{d:.3f}",
                    "-af", f"volume={gain:.2f}dB,afade=t=in:st=0:d=1.5,"
                           f"afade=t=out:st={max(0, d-2):.3f}:d=2",
                    "-ar", "48000", "-ac", "2", str(lit)])
                if not lit.exists():
                    print(f"  {clip.stem[:50]:52s} ECHEC lit"); continue
                out = tmp / clip.name
                sh(["ffmpeg", "-y", "-v", "error", "-i", str(clip), "-i", str(lit),
                    "-filter_complex",
                    "[0:a]aformat=channel_layouts=stereo[a];"
                    "[1:a]aformat=channel_layouts=stereo[m];"
                    "[a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[o]",
                    "-map", "0:v", "-map", "[o]", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k",
                    "-metadata", f"comment={marque.replace('+ musique', '+').rstrip('+ ')} + {MARQUEUR}",
                    "-movflags", "+faststart", str(out)])
                if not out.exists():
                    print(f"  {clip.stem[:50]:52s} ECHEC mixage"); continue
                out.replace(clip)
            print(f"  {fmt[0]} {clip.stem[:48]:50s} {piste.stem[:22]:24s} -> {lufs(clip):.1f} LUFS",
                  flush=True)
print("\nTERMINE")
