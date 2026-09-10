#!/usr/bin/env python3
"""Pose un lit musical tres discret sous la voix d'un lot de reels.

Les 8 titres du dossier "Musique calme pour montage" vont de -6,8 a -17,2 LUFS,
soit plus de 10 dB d'ecart : ils sont donc tous ramenes au meme niveau avant
d'etre poses, sinon l'un couvre la voix la ou l'autre est inaudible.

Le niveau est pose par un GAIN FIXE, jamais par une compression dynamique.
Un ducking ou un loudnorm a large plage fait remonter la musique des que
personne ne parle : a l'ecoute, elle "pompe", forte dans les silences et
absente sous la voix. Ici elle reste au meme volume du debut a la fin.
La video n'est jamais reencodee, seule la piste audio est remplacee.

    python3 ajouter-musique.py <dossier|fichier> [...] [--niveau -34]
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

MUSIQUES = Path("/Users/lucasdo./Documents/Musique pour OpusClip/*Musique calme pour montage")
NIVEAU = -36          # LUFS du lit musical, gain FIXE
MARQUEUR = "musique"  # ecrit dans les metadonnees pour ne jamais repasser deux fois


def sh(c, **k):
    return subprocess.run(c, capture_output=True, text=True, **k)


def deja_fait(f):
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format_tags=comment",
            "-of", "default=nk=1:nw=1", str(f)])
    return MARQUEUR in r.stdout


def duree(f):
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "csv=p=0:nk=1", str(f)])
    return float(r.stdout.strip())


def poser(clip: Path, piste: Path, niveau: int):
    if deja_fait(clip):
        return "deja fait, saute"
    d = duree(clip)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        lit = tmp / "lit.wav"
        # on mesure la piste une fois, puis on applique un gain constant.
        r = sh(["ffmpeg", "-i", str(piste), "-af",
                "loudnorm=print_format=summary", "-f", "null", "-"])
        m = re.search(r"Input Integrated:\s*(-?[\d.]+)", r.stderr)
        gain = niveau - float(m.group(1)) if m else -20.0
        # boucle + coupe a la duree du clip + fondus + gain fixe
        r = sh(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(piste),
                "-t", f"{d:.3f}",
                "-af", f"volume={gain:.2f}dB,"
                       f"afade=t=in:st=0:d=1.5,afade=t=out:st={max(0, d-2):.3f}:d=2",
                "-ar", "48000", "-ac", "2", str(lit)])
        if not lit.exists():
            return "echec preparation musique"

        out = tmp / ("m" + clip.suffix)
        r = sh(["ffmpeg", "-y", "-i", str(clip), "-i", str(lit),
                "-filter_complex",
                "[0:a]aformat=channel_layouts=stereo[voix];"
                "[1:a]aformat=channel_layouts=stereo[lit];"
                "[voix][lit]amix=inputs=2:duration=first:dropout_transition=0:"
                "normalize=0[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-metadata", f"comment={MARQUEUR}",
                "-movflags", "+faststart", str(out)])
        if not out.exists():
            return "echec mixage : " + r.stderr.strip()[-160:]
        out.replace(clip)

    r = sh(["ffmpeg", "-i", str(clip), "-af", "loudnorm=print_format=summary",
            "-f", "null", "-"])
    m = re.search(r"Input Integrated:\s*(-?[\d.]+)", r.stderr)
    return f"{piste.stem[:26]:28s} -> {m.group(1) if m else '?'} LUFS"


if __name__ == "__main__":
    args = sys.argv[1:]
    niveau = NIVEAU
    if "--niveau" in args:
        i = args.index("--niveau")
        niveau = int(args[i + 1])
        args = args[:i] + args[i + 2:]

    pistes = sorted(MUSIQUES.glob("*.mp3"))
    if not pistes:
        sys.exit(f"aucune musique dans {MUSIQUES}")
    clips = []
    for a in args:
        p = Path(a)
        clips += sorted(p.rglob("*.mp4")) if p.is_dir() else [p]
    clips = [c for c in clips if "/Vertical/" in str(c)]

    for i, c in enumerate(clips):
        print(f"{c.name[:46]:48s} {poser(c, pistes[i % len(pistes)], niveau)}",
              flush=True)
    print("TERMINE")
