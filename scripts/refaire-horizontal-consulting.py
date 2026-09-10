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


def coupe_source(src, sortie, debut, fin, segments, filtre_video, args_sortie):
    """Decoupe [debut, fin] du rush, ou recolle plusieurs segments (mini-cuts).

    Les mini-cuts servent a retirer les hesitations et les reprises. Chaque
    jointure recoit un fondu audio de 40 ms pour qu'elle ne claque pas.
    """
    import subprocess
    if not segments:
        return subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{debut:.3f}", "-to", f"{fin:.3f}", "-i", str(src)]
            + filtre_video + args_sortie + [str(sortie)],
            capture_output=True, text=True)
    n = len(segments)
    fc = []
    for i, (x, y) in enumerate(segments):
        fc.append(f"[0:v]trim=start={x:.3f}:end={y:.3f},setpts=PTS-STARTPTS[t{i}];"
                  f"[t{i}]" + filtre_video[1] + f"[v{i}]")
        fc.append(f"[0:a]atrim=start={x:.3f}:end={y:.3f},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:st=0:d=0.04,"
                  f"afade=t=out:st={max(0, y - x - 0.04):.3f}:d=0.04[a{i}]")
    fc.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]")
    return subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-filter_complex", ";".join(fc),
         "-map", "[v]", "-map", "[a]"] + args_sortie + [str(sortie)],
        capture_output=True, text=True)


def refaire(nom, titre, debut, fin, segments=None):
    src = SRC / f"Consulting {nom}.mp4"
    final = DST / nom / "Horizontal" / f"{titre}.mp4"
    srt = DST / nom / "Horizontal" / "_captions-long" / f"{titre}.srt"
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        brut = tmp / "b.mp4"
        r = coupe_source(
            src, brut, debut, fin, segments,
            ["-vf", "scale=1920:1080:flags=lanczos"],
            ["-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k"])
        if r.returncode:
            return "echec coupe"
        subprocess.run(["python3", str(SCRIPTS / "masteriser-audio.py"), str(brut)],
                       capture_output=True)
        if not srt.exists():
            brut.replace(final)
            return "refait SANS captions"
        r = subprocess.run(["python3", str(SCRIPTS / "incruster-captions.py"),
                            str(brut), str(srt), str(final),
                            "--y", "0.88", "--taille", "0.032", "--halo"],
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
        for clip in clips:
            titre, d, f = clip[0], clip[1], clip[2]
            seg = clip[3] if len(clip) > 3 else None
            if (tous and nom in cibles) or titre in cibles:
                print(f"{titre[:56]:58s} -> {refaire(nom, titre, d, f, seg)}", flush=True)
    print("TERMINE")
