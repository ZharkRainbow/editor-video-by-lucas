#!/usr/bin/env python3
"""Choisit la meilleure image d'une video et l'exporte en miniature.

Une miniature n'est pas la premiere image : c'est presque toujours un plan flou
ou les yeux fermes. On note donc chaque image candidate sur quatre criteres et
on garde la meilleure.

  nettete   variance du laplacien. Elimine le flou de bouge, qui est le
            defaut numero un quand le sujet parle en marchant.
  visage    taille du visage detecte. Un visage large accroche mieux dans le
            fil qu'un plan large.
  exposition penalise les images trop sombres ou cramees.
  bouche    penalise les images ou la bouche est grande ouverte, qui donnent
            toujours une expression ridicule fixee.

usage : faire-miniature.py video.mp4 sortie.jpg [--tous dossier]
"""
import os, sys
import cv2
import numpy as np

CASCADE = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
BOUCHE = cv2.data.haarcascades + "haarcascade_smile.xml"


def sous_titre_present(gris):
    """Densite de contours dans la bande des sous-titres.

    Une image ou un sous-titre est affiche fait une mauvaise miniature : on y
    lit un mot sorti de son contexte. La bande vaut 62 a 70 % de la hauteur,
    la ou le generateur pose le texte.
    """
    h, w = gris.shape[:2]
    bande = gris[int(h * 0.60):int(h * 0.72), int(w * 0.10):int(w * 0.90)]
    if bande.size == 0:
        return 0.0
    return float(cv2.Laplacian(bande, cv2.CV_64F).var())


def noter(img, face_cc, bouche_cc):
    h, w = img.shape[:2]
    p = cv2.resize(img, (640, int(h * 640 / w)))
    gris = cv2.cvtColor(p, cv2.COLOR_BGR2GRAY)

    nettete = float(cv2.Laplacian(gris, cv2.CV_64F).var())
    moy = float(gris.mean())
    exposition = 1.0 - abs(moy - 122) / 122.0

    # seuil bas : en 16:9 et en carre lettreboxe le visage occupe bien moins
    # de place qu'en vertical recadre
    vis = face_cc.detectMultiScale(cv2.equalizeHist(gris), 1.10, 5, minSize=(28, 28))
    if len(vis) == 0:
        # repli : pas de visage detecte, on note quand meme sur la nettete et
        # l'exposition plutot que de ne rien produire
        st = sous_titre_present(gris)
        return (min(nettete / 400.0, 1.0) * 3.0 + exposition * 1.5
                - min(st / 300.0, 1.0) * 2.5), dict(nettete=nettete, taille=0.0,
                                                    expo=moy, soustitre=st)
    x, y, bw, bh = max(vis, key=lambda v: v[2] * v[3])
    taille = bw / 640.0

    # bouche grande ouverte : on regarde le tiers bas du visage
    roi = gris[y + int(bh * 0.6):y + bh, x:x + bw]
    ouverte = 0.0
    if roi.size:
        s = bouche_cc.detectMultiScale(roi, 1.7, 12)
        ouverte = 1.0 if len(s) else 0.0

    st = sous_titre_present(gris)
    return (min(nettete / 400.0, 1.0) * 3.0
            + min(taille / 0.30, 1.0) * 2.0
            + exposition * 1.5
            - ouverte * 1.2
            - min(st / 300.0, 1.0) * 2.5), dict(nettete=nettete, taille=taille,
                                                expo=moy, soustitre=st)


def choisir(src, n=40, debut=0.10, fin=0.92):
    """debut et fin sont des fractions de la duree. Pour une video avec un
    cartouche d'accroche, on restreint a ses premieres secondes : la miniature
    doit montrer la carte, c'est elle qui accroche dans le fil."""
    cap = cv2.VideoCapture(src)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    face_cc = cv2.CascadeClassifier(CASCADE)
    bouche_cc = cv2.CascadeClassifier(BOUCHE)
    best, bimg, binfo, bpos = None, None, None, None
    for i in range(n):
        pos = int(total * (debut + (fin - debut) * i / max(n - 1, 1)))
        cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
        ok, img = cap.read()
        if not ok:
            continue
        r = noter(img, face_cc, bouche_cc)
        if r is None:
            continue
        s, info = r
        if best is None or s > best:
            best, bimg, binfo, bpos = s, img, info, pos / (cap.get(cv2.CAP_PROP_FPS) or 30)
    cap.release()
    return bimg, best, binfo, bpos


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    if "--carte" in sys.argv:
        # la carte tient 2.2 s : on cherche la meilleure image pendant qu'elle
        # est pleinement affichee, donc entre 0.6 s et 1.8 s
        import subprocess as sp
        d = float(sp.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration", "-of", "csv=p=0", src],
                         capture_output=True, text=True).stdout.strip())
        img, note, info, t = choisir(src, n=24, debut=0.6 / d, fin=1.8 / d)
    else:
        img, note, info, t = choisir(src)
    if img is None:
        print(f"aucun visage trouve dans {os.path.basename(src)}")
        sys.exit(1)
    cv2.imwrite(dst, img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f"{os.path.basename(dst)}  image a {t:.1f}s  note {note:.2f} "
          f"(nettete {info['nettete']:.0f}, visage {info['taille']*100:.0f}% "
          f"de la largeur, bande sous-titre {info['soustitre']:.0f})")
