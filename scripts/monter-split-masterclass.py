#!/usr/bin/env python3
"""
Monte un split screen "Matis Clouet" a partir de deux rushs synchrones :
la camera a gauche (colonne fixe), l'ecran a droite.

Le zoom du Canva bouge en permanence pendant la masterclass. Un crop ecran
fixe rend la moitie des passages illisibles. Ce script echantillonne donc
l'ecran sur toute la duree du passage, mesure la zone reellement occupee
(tout ce qui n'est pas le fond beige) et cadre dessus.

    python3 monter-split-masterclass.py            # rend tout le lot
    python3 monter-split-masterclass.py 3 7        # rend les clips 3 et 7
"""
import subprocess
import sys
from pathlib import Path

CAM = Path.home() / "Downloads/Camera.-1.mp4"
SCR = Path.home() / "Downloads/Ecran-1.mp4"
DST = Path.home() / "Movies/CapCut/Valentin Masterclass/Horizontal"

LARGEUR = 1920
HAUTEUR = 1080
COL_CAM = 720                      # validee par Lucas le 09/09
COL_SCR = LARGEUR - COL_CAM
CAM_CX = 1600                      # centre du visage dans le rush 4K
SRC_W, SRC_H = 3840, 2160
MARGE = 0.06                       # air autour du contenu detecte
ECHANT = 7                         # frames sondees par passage

# (debut, fin, titre)
LOT = [
    (   0.0,   28.3, "900'000 euros a 22 ans grace au recrutement"),
    (  70.5,   94.1, "ce n'est pas l'IA c'est le recrutement"),
    ( 176.5,  210.8, "les 5 premiers recrutements decident de tout"),
    ( 223.6,  256.0, "l'ordre exact de ses 6 premiers recrutements"),
    ( 289.8,  319.3, "l'exercice du calendrier en 3 couleurs"),
    ( 517.8,  554.5, "un employe doit rapporter 4 a 8 fois ce qu'il coute"),
    ( 587.8,  642.3, "recruter et vendre c'est le meme funnel"),
    ( 676.9,  720.4, "le top 5 pourcent n'est pas excellent"),
    ( 776.3,  808.1, "tu n'es pas en position de force face aux candidats"),
    ( 838.0,  886.0, "une VSL pour vendre le job"),
    ( 980.6, 1022.5, "70 pourcent de son equipe n'etait pas en recherche d'emploi"),
    (1065.5, 1084.0, "si tu n'as pas eu 30 candidats en appel"),
    (1127.2, 1169.4, "ne pitche jamais le job au debut de l'appel"),
    (1173.3, 1195.3, "les meilleurs candidats sont des entrepreneurs caches"),
    (1238.9, 1263.0, "si ce n'est pas un grand oui c'est un non"),
    (1295.4, 1315.8, "le suivi hebdo en 3 colonnes"),
    (1332.1, 1378.0, "un jour entier par semaine avec chaque head of"),
    (1394.0, 1434.1, "a 22 ans des gens vivent grace a lui"),
]


def pair(n):
    return int(n) // 2 * 2


def bbox_contenu(t, taille=192):
    """Zone occupee a l'instant t, en fraction du cadre. None si vide."""
    h = taille * SRC_H // SRC_W
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(SCR),
         "-frames:v", "1", "-vf", f"scale={taille}:{h},format=gray",
         "-f", "rawvideo", "-"], capture_output=True)
    d = p.stdout
    if len(d) < taille * h:
        return None
    # le fond Canva est un beige clair et uniforme : on garde ce qui s'en ecarte
    fond = sorted(d)[len(d) // 2]
    seuil = 26
    xs, ys = [], []
    for y in range(h):
        base = y * taille
        for x in range(taille):
            if abs(d[base + x] - fond) > seuil:
                xs.append(x)
                ys.append(y)
    if len(xs) < 40:
        return None
    xs.sort(); ys.sort()
    k = max(1, len(xs) // 100)          # on ignore 1% de bruit de chaque cote
    return (xs[k] / taille, ys[k] / h, xs[-k] / taille, ys[-k] / h)


def crop_ecran(debut, fin):
    """Crop (w, h, x, y) au ratio de la colonne ecran, cadre sur le contenu."""
    ratio = COL_SCR / HAUTEUR
    boites = [b for b in
              (bbox_contenu(debut + i * (fin - debut) / (ECHANT - 1))
               for i in range(ECHANT)) if b]
    if not boites:
        h = SRC_H
        w = pair(h * ratio)
        return w, h, pair((SRC_W - w) / 2), 0
    x0 = min(b[0] for b in boites) * SRC_W
    y0 = min(b[1] for b in boites) * SRC_H
    x1 = max(b[2] for b in boites) * SRC_W
    y1 = max(b[3] for b in boites) * SRC_H
    w, h = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w *= 1 + MARGE
    h *= 1 + MARGE
    if w / h < ratio:                    # on elargit ou on rehausse au ratio
        w = h * ratio
    else:
        h = w / ratio
    if h > SRC_H:                        # la hauteur borne tout
        h = SRC_H
        w = h * ratio
    if w > SRC_W:
        w = SRC_W
        h = w / ratio
    x = min(max(cx - w / 2, 0), SRC_W - w)
    y = min(max(cy - h / 2, 0), SRC_H - h)
    return pair(w), pair(h), pair(x), pair(y)


def rendre(i, debut, fin, titre):
    cw = pair(COL_CAM * SRC_H / HAUTEUR)
    cx = pair(CAM_CX - cw / 2)
    sw, sh, sx, sy = crop_ecran(debut, fin)
    nom = f"{i:02d}" if isinstance(i, int) else str(i)
    dst = DST / f"{nom} - Valentin {titre}.mp4"
    zoom = SRC_H / sh
    print(f"[{nom}] {debut:7.1f} -> {fin:7.1f} ({fin-debut:5.1f}s) "
          f"ecran {sw}x{sh}@{sx},{sy} zoom x{zoom:.2f}  {titre}")
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{debut:.3f}", "-i", str(CAM),
        "-ss", f"{debut:.3f}", "-i", str(SCR),
        "-t", f"{fin - debut:.3f}",
        "-filter_complex",
        f"[0:v]crop={cw}:{SRC_H}:{cx}:0,scale={COL_CAM}:{HAUTEUR}:flags=lanczos[cam];"
        f"[1:v]crop={sw}:{sh}:{sx}:{sy},scale={COL_SCR}:{HAUTEUR}:flags=lanczos[scr];"
        f"[cam][scr]hstack=inputs=2[v]",
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "192k", str(dst),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print("   ECHEC :", r.stderr.strip()[-400:])


if __name__ == "__main__":
    DST.mkdir(parents=True, exist_ok=True)
    voulus = [int(a) for a in sys.argv[1:]]
    for i, (d, f, t) in enumerate(LOT, 1):
        if not voulus or i in voulus:
            rendre(i, d, f, t)
    print("TERMINE")
