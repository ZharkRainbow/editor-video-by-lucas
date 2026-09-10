#!/usr/bin/env python3
"""
Fusionne deux exports CapCut complementaires (un par piste, chacun avec du noir
la ou l'autre a l'image) en un seul split screen.

Detecte tout seul quel fichier est en haut, lequel est en bas, et lequel porte
le son. Aucun reglage a passer.

    python3 fusionner-split-screen.py "Test val -1.mp4" "Test val -2.mp4"
    python3 fusionner-split-screen.py dossier/            # prend les 2 mp4 dedans
"""
import json
import subprocess
import sys
from pathlib import Path

SEUIL_NOIR = 6          # une ligne au dessus de ca compte comme du contenu
INSTANT = 12            # seconde ou on sonde l'image


def sh(cmd, texte=True):
    return subprocess.run(cmd, capture_output=True, text=texte)


def sonde(path):
    """Renvoie (premiere_ligne, derniere_ligne, hauteur, largeur, a_du_son)."""
    p = sh(["ffprobe", "-v", "error", "-select_streams", "v",
            "-show_entries", "stream=width,height", "-of", "json", str(path)])
    st = json.loads(p.stdout)["streams"][0]
    w, h = st["width"], st["height"]

    # profil vertical : on ecrase l'image en une colonne de h pixels
    p = sh(["ffmpeg", "-v", "error", "-ss", str(INSTANT), "-i", str(path),
            "-frames:v", "1", "-vf", f"format=gray,scale=1:{h}",
            "-f", "rawvideo", "-"], texte=False)
    col = p.stdout
    if len(col) < h:
        sys.exit(f"lecture impossible : {path}")
    lignes = [y for y in range(h) if col[y] > SEUIL_NOIR]
    if not lignes:
        sys.exit(f"image entierement noire a {INSTANT}s : {path}")

    p = sh(["ffmpeg", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"])
    son = True
    for ligne in p.stderr.splitlines():
        if "mean_volume" in ligne:
            son = float(ligne.split(":")[-1].replace("dB", "").strip()) > -80
    return lignes[0], lignes[-1], h, w, son


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    if len(args) == 1 and Path(args[0]).is_dir():
        fichiers = sorted(Path(args[0]).glob("*.mp4"))
    else:
        fichiers = [Path(a) for a in args]
    fichiers = [f for f in fichiers if f.is_file()]
    if len(fichiers) != 2:
        sys.exit(f"il faut exactement 2 fichiers, {len(fichiers)} trouve(s)")

    infos = {}
    for f in fichiers:
        haut, bas, h, w, son = sonde(f)
        infos[f] = dict(haut=haut, bas=bas, h=h, w=w, son=son)
        print(f"{f.name}: contenu lignes {haut} a {bas} sur {h}, "
              f"son={'oui' if son else 'non'}")

    # celui dont le contenu commence le plus haut passe au dessus
    dessus, dessous = sorted(fichiers, key=lambda f: infos[f]["haut"])
    if infos[dessus]["h"] != infos[dessous]["h"] or infos[dessus]["w"] != infos[dessous]["w"]:
        sys.exit("les deux fichiers n'ont pas la meme definition")

    # audio : celui qui en a. Si les deux en ont, on prend celui du dessous.
    piste_son = dessous if infos[dessous]["son"] else dessus
    if not infos[piste_son]["son"]:
        sys.exit("aucun des deux fichiers n'a de son")

    coupe = infos[dessus]["bas"] + 1        # hauteur gardee du fichier du dessus
    w = infos[dessus]["w"]
    sortie = dessous.with_name(dessous.stem.rsplit("-", 1)[0].rstrip() + " - FUSION.mp4")

    print(f"\ndessus  : {dessus.name} (garde {coupe} px)")
    print(f"dessous : {dessous.name}")
    print(f"son     : {piste_son.name}")
    print(f"sortie  : {sortie.name}\n")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(dessous), "-i", str(dessus), "-i", str(piste_son),
        "-filter_complex",
        f"[1:v]crop={w}:{coupe}:0:0[cam];[0:v][cam]overlay=0:0[v]",
        "-map", "[v]", "-map", "2:a",
        "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "192k",
        str(sortie),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(r.stderr[-2000:])
    print(f"OK -> {sortie}")


if __name__ == "__main__":
    main()
