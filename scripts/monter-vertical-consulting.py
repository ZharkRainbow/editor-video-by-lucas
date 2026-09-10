#!/usr/bin/env python3
"""Version verticale des reels consulting : split screen a deux etages.

On repart du long format 4K, jamais du clip 1080p deja monte : recadrer une
personne dans du 1080p donnerait un 500x960 upscale. Les bornes viennent de
clips-timecodes.json.

Cadrage identique sur les cinq consultings, verifie a l'image : le client est
a gauche du cadre source, Valentin a droite.

    python3 monter-vertical-consulting.py [Nom ...]
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

W, H = 1080, 1920
ETAGE = H // 2
# crop 1300x1156 (ratio 1080:960), cales a l'image le 09/09
VALENTIN = (1300, 1156, 2110, 170)     # a droite du cadre source, recentre le 09/09
CLIENT = (1300, 1156, 530, 250)        # a gauche, recentre le 09/09
CAP_Y = 0.4513                         # captions juste au-dessus de la jointure
ACC_Y = 0.4997                          # accroche juste en dessous


def monter(nom, titre, debut, fin):
    src = SRC / f"Consulting {nom}.mp4"
    dossier = DST / nom / "Vertical"
    dossier.mkdir(parents=True, exist_ok=True)
    final = dossier / f"{titre}.mp4"
    srt = DST / nom / "Horizontal" / "_captions" / f"{titre}.srt"

    vw, vh, vx, vy = VALENTIN
    cw, ch, cx, cy = CLIENT
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        brut = tmp / "brut.mp4"
        r = subprocess.run([
            "ffmpeg", "-y", "-ss", f"{debut:.3f}", "-to", f"{fin:.3f}", "-i", str(src),
            "-filter_complex",
            f"[0:v]split=2[a][b];"
            f"[a]crop={vw}:{vh}:{vx}:{vy},scale={W}:{ETAGE}:flags=lanczos[val];"
            f"[b]crop={cw}:{ch}:{cx}:{cy},scale={W}:{ETAGE}:flags=lanczos[cli];"
            f"[val][cli]vstack=inputs=2[v]",
            "-map", "[v]", "-map", "0:a:0",
            "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(brut)],
            capture_output=True, text=True)
        if r.returncode:
            return "echec montage : " + r.stderr.strip()[-200:]

        subprocess.run(["python3", str(SCRIPTS / "masteriser-audio.py"), str(brut)],
                       capture_output=True)

        if not srt.exists():
            brut.replace(final)
            return "monte SANS captions (srt absent)"

        acc = ACCROCHES.get(titre)
        cmd = ["python3", str(SCRIPTS / "incruster-captions.py"), str(brut),
               str(srt), str(final), "--y", str(CAP_Y), "--taille", "0.023"]
        if acc:
            cmd += ["--accroche", acc, "--accroche-y", str(ACC_Y)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            return "echec captions : " + (r.stdout or r.stderr).strip()[-200:]
    return "ok" + ("" if acc else " (sans accroche)")


if __name__ == "__main__":
    ACCROCHES = json.loads((SCRIPTS / "accroches-consulting.json").read_text("utf-8"))
    lots = json.loads((RACINE / "clips-timecodes.json").read_text("utf-8"))
    voulus = sys.argv[1:]
    for nom, clips in lots.items():
        if nom.startswith("_") or (voulus and nom not in voulus):
            continue
        for titre, d, f in clips:
            print(f"{nom:9s} {titre[:52]:54s} -> {monter(nom, titre, d, f)}",
                  flush=True)
    print("TERMINE")
