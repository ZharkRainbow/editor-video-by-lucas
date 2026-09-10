#!/usr/bin/env python3
"""Cale une musique sous une voix : bon extrait, bon niveau.

Deux problemes que resout ce script.

1. Un pourcentage de volume ne veut rien dire. 17 % d'un morceau masterise a
   -18 LUFS et 17 % d'un morceau masterise a -8 LUFS ne donnent pas du tout le
   meme resultat sous la voix. Le bon reglage est un ECART en LU par rapport a
   la voix, pas un pourcentage. On mesure les deux et on calcule le gain.

2. Le debut d'un morceau est rarement le bon passage : intro clairsemee,
   montee. On balaie le morceau par fenetres de la longueur de la video et on
   garde celle dont l'energie est la plus forte et la plus reguliere.

usage : caler-musique.py rush.mp4 musique.mp3 [ecart_LU]
sortie : "debut_extrait gain_lineaire" en secondes et en facteur
"""
import re, subprocess, sys


def lufs(src, debut=None, duree=None, filtre="anull"):
    cmd = ["ffmpeg", "-v", "info"]
    if debut is not None:
        cmd += ["-ss", str(debut)]
    if duree is not None:
        cmd += ["-t", str(duree)]
    cmd += ["-i", src, "-af", f"{filtre},loudnorm=print_format=summary", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, env={"LC_ALL": "C", "PATH": "/opt/homebrew/bin:/usr/bin:/bin"})
    m = re.search(r"Input Integrated:\s*(-?[\d.]+)", r.stderr)
    return float(m.group(1)) if m else None


def duree(p):
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
        capture_output=True, text=True).stdout.strip())


def profil(src, fenetre=40):
    """Energie RMS du morceau. Retourne [(t, dB)].

    astats remet ses compteurs a zero tous les N FRAMES, pas toutes les N
    secondes : il faut lire le pts_time pour savoir ou l'on est.
    """
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", src, "-af",
         f"astats=metadata=1:reset={fenetre},ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
         "-f", "null", "-"], capture_output=True, text=True,
        env={"LC_ALL": "C", "PATH": "/opt/homebrew/bin:/usr/bin:/bin"})
    pts, out = None, []
    for l in r.stdout.splitlines():
        m = re.match(r"frame:\d+\s+pts:\d+\s+pts_time:([\d.]+)", l)
        if m:
            pts = float(m.group(1))
            continue
        m = re.match(r"lavfi\.astats\.Overall\.RMS_level=(-?[\d.]+|-inf)", l)
        if m and pts is not None:
            out.append((pts, -90.0 if m.group(1) == "-inf" else float(m.group(1))))
    return out


def meilleur_extrait(mus, besoin, marge_intro=8.0):
    """Fenetre la plus energique et la plus reguliere, intro ecartee."""
    pts = profil(mus)
    if len(pts) < 8:
        return 0.0
    total = pts[-1][0]
    if total <= besoin + marge_intro:
        return 0.0
    meilleur, score_max = marge_intro, None
    i = 0
    while i < len(pts):
        t0 = pts[i][0]
        if t0 < marge_intro:
            i += 1
            continue
        if t0 + besoin > total:
            break
        f = [v for t, v in pts if t0 <= t <= t0 + besoin]
        if len(f) < 4:
            i += 1
            continue
        moy = sum(f) / len(f)
        ecart = (sum((x - moy) ** 2 for x in f) / len(f)) ** 0.5
        score = moy - 0.6 * ecart          # fort ET regulier
        if score_max is None or score > score_max:
            score_max, meilleur = score, t0
        i += 1
    return float(meilleur)


def caler(rush, mus, ecart=16.0):
    d = duree(rush)
    voix = lufs(rush)
    debut = meilleur_extrait(mus, d)
    niveau = lufs(mus, debut, d)
    if voix is None or niveau is None:
        return debut, 0.17
    gain_db = (voix - ecart) - niveau
    return debut, round(10 ** (gain_db / 20.0), 4)


if __name__ == "__main__":
    e = float(sys.argv[3]) if len(sys.argv) > 3 else 16.0
    debut, gain = caler(sys.argv[1], sys.argv[2], e)
    print(f"{debut:.2f} {gain:.4f}")
