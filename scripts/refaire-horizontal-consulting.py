#!/usr/bin/env python3
"""Regenere un clip horizontal consulting en UNE seule passe depuis la 4K :
coupe, mastering audio, captions. Sert a reparer les clips qui ont recu deux
incrustations successives (donc deux encodages).

    python3 refaire-horizontal-consulting.py "Amory ..." "Baptiste ..."
    python3 refaire-horizontal-consulting.py --tous Amory
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path("/Users/lucasdo./Documents/RAIZ-Claude/OFFBOUND/CONTENU/consulting-mastermind")
SRC = Path("/Users/lucasdo./Downloads/Consulting Client - Mastermind Valentin Montage vidéo")
DST = Path("/Users/lucasdo./Movies/CapCut/Consulting by Lucas to 16,9")
SCRIPTS = Path(__file__).parent


def refaire(nom, titre, debut, fin):
    src = SRC / f"Consulting {nom}.mp4"
    final = DST / nom / "Horizontal" / f"{titre}.mp4"
    srt = DST / nom / "Horizontal" / "_captions-long" / f"{titre}.srt"
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        brut = tmp / "b.mp4"
        r = subprocess.run([
            "ffmpeg", "-y", "-ss", f"{debut:.3f}", "-to", f"{fin:.3f}", "-i", str(src),
            "-vf", "scale=1920:1080:flags=lanczos",
            "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(brut)],
            capture_output=True, text=True)
        if r.returncode:
            return "echec coupe"
        subprocess.run(["python3", str(SCRIPTS / "masteriser-audio.py"), str(brut)],
                       capture_output=True)
        if not srt.exists():
            brut.replace(final)
            return "refait SANS captions"
        r = subprocess.run(["python3", str(SCRIPTS / "incruster-captions.py"),
                            str(brut), str(srt), str(final),
                            "--y", "0.88", "--taille", "0.028"],
                           capture_output=True, text=True)
        if r.returncode:
            return "echec captions"
    return "ok"


if __name__ == "__main__":
    lots = json.loads((RACINE / "clips-timecodes.json").read_text("utf-8"))
    args = sys.argv[1:]
    tous = "--tous" in args
    cibles = [a for a in args if a != "--tous"]
    for nom, clips in lots.items():
        if nom.startswith("_"):
            continue
        for titre, d, f in clips:
            if (tous and nom in cibles) or titre in cibles:
                print(f"{titre[:56]:58s} -> {refaire(nom, titre, d, f)}", flush=True)
    print("TERMINE")
