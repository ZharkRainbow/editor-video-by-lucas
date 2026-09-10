#!/usr/bin/env python3
"""Fabrique la LUT qui transforme un etalonnage deja applique en un autre.

Le probleme : les rushes propres portent la chaine A (D-Log to Rec709 puis
Cinestyle), on veut la chaine B (Log M to Rec709). Refaire les fichiers depuis
les sources obligerait a rejouer toutes les coupes. On calcule donc la LUT C
telle que C(A(x)) = B(x) pour toute couleur x.

Methode : on passe une mire HALD identite dans A et dans B. Pour chaque case de
la mire on connait alors la couleur actuelle et la couleur voulue. On disperse
ces couples dans un cube 3D, puis on comble les trous par diffusion, parce que
A n'atteint pas toutes les cases du cube.

usage : lut-correctrice.py chaineA.cube[,chaineA2.cube] chaineB.cube sortie.cube
"""
import subprocess, sys, os
import numpy as np

N = 64          # 64 niveaux par canal, comme les .cube du dossier
TAILLE = 512    # mire HALD 8 -> 512x512


def mire(chemin):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "haldclutsrc=8", "-frames:v", "1",
                    "-pix_fmt", "rgb24", chemin], check=True)


def passer(entree, luts, sortie):
    chaine = ",".join(f"lut3d=file='{l}'" for l in luts)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", entree,
                    "-vf", chaine, "-pix_fmt", "rgb24", sortie], check=True)


def lire(p):
    from PIL import Image
    return np.asarray(Image.open(p).convert("RGB"), dtype=np.uint8).reshape(-1, 3)


def construire(a, b):
    """a = couleurs actuelles, b = couleurs voulues, meme ordre."""
    cube = np.zeros((N, N, N, 3), dtype=np.float64)
    poids = np.zeros((N, N, N), dtype=np.float64)
    idx = np.rint(a.astype(np.float64) / 255.0 * (N - 1)).astype(int)
    for canal in range(3):
        np.add.at(cube[..., canal], (idx[:, 0], idx[:, 1], idx[:, 2]),
                  b[:, canal].astype(np.float64))
    np.add.at(poids, (idx[:, 0], idx[:, 1], idx[:, 2]), 1.0)
    rempli = poids > 0
    cube[rempli] /= poids[rempli][:, None]
    print(f"  cases renseignees : {rempli.sum()} sur {N**3} "
          f"({rempli.sum()/N**3*100:.1f} %)")

    # diffusion : chaque case vide prend la moyenne de ses voisines remplies,
    # on repete jusqu'a ce que tout le cube soit couvert
    tours = 0
    while not rempli.all() and tours < 200:
        somme = np.zeros_like(cube)
        compte = np.zeros_like(poids)
        for axe in range(3):
            for sens in (1, -1):
                somme += np.roll(np.where(rempli[..., None], cube, 0), sens, axis=axe)
                compte += np.roll(rempli.astype(float), sens, axis=axe)
        neuf = (~rempli) & (compte > 0)
        cube[neuf] = somme[neuf] / compte[neuf][:, None]
        rempli |= neuf
        tours += 1
    print(f"  diffusion : {tours} tours")
    return np.clip(cube / 255.0, 0, 1)


def ecrire(cube, dst, titre):
    with open(dst, "w") as f:
        f.write(f'TITLE "{titre}"\nLUT_3D_SIZE {N}\nDOMAIN_MIN 0 0 0\n'
                f'DOMAIN_MAX 1 1 1\n\n')
        # ordre .cube : le rouge varie le plus vite
        for b in range(N):
            for g in range(N):
                for r in range(N):
                    v = cube[r, g, b]
                    f.write(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")


if __name__ == "__main__":
    lutsA = sys.argv[1].split(",")
    lutB = sys.argv[2]
    dst = sys.argv[3]
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        h = os.path.join(td, "h.png")
        pa = os.path.join(td, "a.png")
        pb = os.path.join(td, "b.png")
        mire(h)
        passer(h, lutsA, pa)
        passer(h, [lutB], pb)
        cube = construire(lire(pa), lire(pb))
    ecrire(cube, dst, os.path.basename(dst))
    print(f"  ecrit : {dst}")
