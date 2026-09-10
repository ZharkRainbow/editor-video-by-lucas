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
    # Sans -ss avant -i, ffmpeg decode le rush depuis le debut jusqu'au premier
    # segment : plusieurs minutes sur un 4K HEVC. On seek d'abord, puis on
    # ramene les segments dans le repere du flux ainsi ouvert.
    saut = max(0.0, segments[0][0] - 2.0)
    segments = [(x - saut, y - saut) for x, y in segments]
    n = len(segments)
    fc = []
    for i, (x, y) in enumerate(segments):
        chaine = ("," + filtre_video[1]) if len(filtre_video) > 1 else ""
        fc.append(f"[0:v]trim=start={x:.3f}:end={y:.3f},setpts=PTS-STARTPTS"
                  f"{chaine}[v{i}]")
        fc.append(f"[0:a]atrim=start={x:.3f}:end={y:.3f},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:st=0:d=0.04,"
                  f"afade=t=out:st={max(0, y - x - 0.04):.3f}:d=0.04[a{i}]")
    fc.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]")
    return subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{saut:.3f}", "-i", str(src),
         "-filter_complex", ";".join(fc),
         "-map", "[v]", "-map", "[a]"] + args_sortie + [str(sortie)],
        capture_output=True, text=True)


def monter(nom, titre, debut, fin, segments=None):
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
        # Avec des mini-cuts, on recolle d'abord les morceaux en 4K, puis on
        # applique le split screen : les labels du filtre ne peuvent pas etre
        # dupliques d'un segment a l'autre.
        entree = src
        d0, f0 = debut, fin
        if segments:
            recolle = tmp / "recolle.mp4"
            r = coupe_source(src, recolle, debut, fin, segments, [],
                             ["-c:v", "libx264", "-crf", "16", "-preset", "veryfast",
                              "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k"])
            if r.returncode or not recolle.exists():
                return "echec mini-cuts : " + r.stderr.strip()[-200:]
            entree, d0, f0 = recolle, 0.0, None

        cmd = ["ffmpeg", "-y"]
        if f0 is not None:
            cmd += ["-ss", f"{d0:.3f}", "-to", f"{f0:.3f}"]
        r = subprocess.run(cmd + [
            "-i", str(entree),
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
        for clip in clips:
            titre, d, f = clip[0], clip[1], clip[2]
            seg = clip[3] if len(clip) > 3 else None
            print(f"{nom:9s} {titre[:52]:54s} -> {monter(nom, titre, d, f, seg)}",
                  flush=True)
    print("TERMINE")
