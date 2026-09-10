#!/usr/bin/env python3
"""Version verticale des reels masterclass.

Valentin occupe le tiers haut, l'ecran animé les deux tiers du bas, et les
captions sont posees pile sur la ligne de jonction entre les deux.

L'ecran n'est pas etire dans une zone portrait : on cadre sur sa zone utile
(mesuree sur plusieurs frames, comme en horizontal), on l'affiche en 1080x900
et on comble avec le beige de la charte, qui se fond dans le fond du Canva.
Sinon un crop 9:16 dans un board paysage coupe la moitie du schema.

    python3 monter-vertical-masterclass.py [motif ...]
"""
import subprocess
import sys
import tempfile
from importlib import import_module
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
h = import_module("monter-split-masterclass")
val = import_module("monter-selection-valentin")

W, H = 1080, 1920
CAM_H = 960                                   # 50/50, demande de Valentin le 10/09
CAM_CROP = (2700, 1600, 250, 90)              # dezoome a la demande de Lucas le 09/09
SCR_H = 960                                   # hauteur d'affichage de l'ecran
SCR_RATIO = W / SCR_H
BEIGE = "0xD4CCBE"
CAP_Y = 0.4513                                # juste au-dessus de la jointure, comme le consulting
TITRE_Y2 = 0.4997                             # le bandeau a cheval sur la jointure

SRC_DIR = Path("/Users/lucasdo./Movies/CapCut/Valentin Masterclass")
SCRIPTS = Path(__file__).parent


def crop_ecran(debut, fin):
    """Meme mesure qu'en horizontal, mais au ratio de la vignette verticale."""
    garde = h.COL_SCR, h.HAUTEUR
    h.COL_SCR, h.HAUTEUR = W, SCR_H
    try:
        return h.crop_ecran(debut, fin)
    finally:
        h.COL_SCR, h.HAUTEUR = garde


def monter(nom_fichier, titre, debut, fin):
    dst_dir = SRC_DIR / "Vertical"
    dst_dir.mkdir(parents=True, exist_ok=True)
    final = dst_dir / f"{nom_fichier}.mp4"
    srt = SRC_DIR / "Horizontal" / "_captions" / f"{nom_fichier}.srt"

    cw, ch, cx, cy = CAM_CROP
    sw, sh, sx, sy = crop_ecran(debut, fin)
    pad_y = (H - CAM_H - SCR_H) // 2

    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        brut = tmp / "b.mp4"
        r = subprocess.run([
            "ffmpeg", "-y",
            "-ss", f"{debut:.3f}", "-i", str(h.CAM),
            "-ss", f"{debut:.3f}", "-i", str(h.SCR),
            "-t", f"{fin - debut:.3f}",
            "-filter_complex",
            f"[0:v]crop={cw}:{ch}:{cx}:{cy},scale={W}:{CAM_H}:flags=lanczos[cam];"
            f"[1:v]crop={sw}:{sh}:{sx}:{sy},scale={W}:{SCR_H}:flags=lanczos,"
            f"pad={W}:{H - CAM_H}:0:{pad_y}:{BEIGE}[scr];"
            f"[cam][scr]vstack=inputs=2[v]",
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(brut)],
            capture_output=True, text=True)
        if r.returncode:
            return "echec montage : " + r.stderr.strip()[-200:]
        if not srt.exists():
            brut.replace(final)
            return "monte SANS captions"
        r = subprocess.run([
            "python3", str(SCRIPTS / "incruster-captions.py"), str(brut),
            str(srt), str(final), "--y", str(CAP_Y), "--taille", "0.021",
            "--accroche", titre, "--accroche-y", str(TITRE_Y2)],
            capture_output=True, text=True)
        if r.returncode:
            return "echec captions : " + (r.stdout or r.stderr).strip()[-200:]
    return "ok"


if __name__ == "__main__":
    motifs = sys.argv[1:]
    lot = [(f"{i:02d} - Valentin {t}", t, d, f)
           for i, (d, f, t) in enumerate(h.LOT, 1)]
    lot += [(f"VAL {i} - Valentin {t}", t, d, f)
            for i, (d, f, t) in enumerate(val.LOT, 1)]
    for nom, titre, d, f in lot:
        if motifs and not any(m in nom for m in motifs):
            continue
        print(f"{nom[:56]:58s} -> {monter(nom, titre, d, f)}", flush=True)
    print("TERMINE")
