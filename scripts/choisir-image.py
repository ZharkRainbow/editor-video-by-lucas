#!/usr/bin/env python3
"""Choisit la meilleure image d'un reel pour en faire une miniature.

Pourquoi une v2. La v1 notait la nettete sur l'image entiere, avec le poids le
plus fort. Or dans un plan parle, l'image la plus "nette" au sens du laplacien
est presque toujours celle ou la bouche est grande ouverte : les dents et
l'ombre de la cavite creent enormement de contraste local. Le selecteur
recompensait donc exactement ce qu'il fallait fuir. Le garde-fou "bouche
ouverte" reposait sur haarcascade_smile, qui ne se declenche quasiment jamais,
et rien ne regardait les yeux.

Ici on mesure la geometrie du visage avec FaceMesh (468 points) :

  EAR   ouverture des paupieres, rapportee a la largeur de l'oeil. Sous 0.24
        l'oeil est en train de se fermer. C'est le detecteur de clignement.
  MAR   ouverture des levres, rapportee a la largeur de la bouche. Au dessus
        de 0.22 la bouche est franchement ouverte, on est en pleine syllabe.
  sourire  commissures relevees par rapport au centre de la bouche. Un leger
        sourire fait une bien meilleure miniature qu'un visage neutre.
  frontalite  ecart entre le nez et le milieu des yeux, rapporte a la largeur
        du visage. Punit les trois-quarts et les visages de profil.
  regard  position de l iris entre les deux coins de l oeil. Un iris centre
        veut dire qu il regarde l objectif. Sur un vlog il regarde partout,
        et une miniature ou le sujet fixe le vide ne donne pas envie.

Deux criteres n'ont rien a voir avec le visage mais eliminent les images que
Lucas a signalees :

  main  une main devant le visage, ou un aliment porte a la bouche. Detectee
        avec Hands : on regarde le recouvrement des boites, mais aussi la
        distance entre le poing et la bouche, car une main au menton ne
        recouvre presque rien et gache pourtant l image.
  lunettes  les yeux nettement plus sombres que les joues. FaceMesh place des
        paupieres derriere des verres teintes et les declare grand ouvertes ;
        sans ce controle une miniature en lunettes de soleil passe pour un
        regard camera parfait.
  cadre  visage coupe par un bord, ou pose trop bas. Une tete a moitie sortie
        du cadre ne donne pas envie de cliquer.
  typo  la miniature porte un pave de texte en haut. Si la ligne des yeux
        tombe dedans, le texte se pose sur le regard.

usage : choisir-image.py video.mp4 sortie.jpg [--top N dossier] [--json]
"""
import json, os, sys
import cv2
import numpy as np
import mediapipe as mp

FM = mp.solutions.face_mesh.FaceMesh
MAINS = mp.solutions.hands.Hands
# FaceMesh embarque un detecteur courte portee : sur un plan de scene, ou le
# visage fait 10 a 15 % de la largeur, il ne trouve rien, et agrandir l'image
# n'y change rien puisque la taille RELATIVE ne bouge pas. On localise donc
# d'abord avec le detecteur longue portee, puis on recadre autour du visage et
# on repasse FaceMesh sur ce recadrage, ou le visage devient enfin grand.
DETECT = mp.solutions.face_detection.FaceDetection

# FaceMesh : paupieres haute/basse, coins de l'oeil
OEIL_G, LARG_G = [(159, 145), (158, 153)], (33, 133)
OEIL_D, LARG_D = [(386, 374), (385, 380)], (362, 263)
LEVRES, COMMIS = (13, 14), (61, 291)
NEZ = 1
# refine_landmarks ajoute les iris : 468-472 oeil gauche, 473-477 oeil droit
IRIS_G, IRIS_D = 468, 473

EAR_MIN = 0.24        # sous ce seuil l'oeil se ferme
MAR_MAX = 0.22        # au dessus la bouche est franchement ouverte
FRONTAL_MAX = 0.20    # au dela c'est un trois-quarts marque, voire un profil
LARG_MIN = 0.16       # visage trop petit : on ne le reconnait pas dans le fil
PAS = 0.40            # balayage grossier, en secondes
AFFINE = 12           # nombre de candidats repris image par image


def _d(p, a, b):
    return float(np.hypot(*(p[a] - p[b])[:2]))


def mesures(img, fm, mains, det=None):
    """Renvoie None si aucun visage. Sinon un dict de mesures brutes."""
    h, w = img.shape[:2]
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    r = fm.process(rgb)
    if r.multi_face_landmarks:
        lm = r.multi_face_landmarks[0].landmark
        p = np.array([[l.x * w, l.y * h, l.z * w] for l in lm])
    elif det is not None:
        rd = det.process(rgb)
        if not rd.detections:
            return None
        b = rd.detections[0].location_data.relative_bounding_box
        cx, cy = (b.xmin + b.width / 2) * w, (b.ymin + b.height / 2) * h
        cote = max(b.width * w, b.height * h) * 2.4
        x0 = int(max(cx - cote / 2, 0)); x1 = int(min(cx + cote / 2, w))
        y0 = int(max(cy - cote / 2, 0)); y1 = int(min(cy + cote / 2, h))
        if x1 - x0 < 40 or y1 - y0 < 40:
            return None
        vign = rgb[y0:y1, x0:x1]
        rc = fm.process(cv2.resize(vign, None, fx=2.0, fy=2.0,
                                   interpolation=cv2.INTER_CUBIC))
        if not rc.multi_face_landmarks:
            return None
        cw, ch = x1 - x0, y1 - y0
        lm = rc.multi_face_landmarks[0].landmark
        p = np.array([[x0 + l.x * cw, y0 + l.y * ch, l.z * cw] for l in lm])
    else:
        return None

    ear = 0.0
    for paires, larg in ((OEIL_G, LARG_G), (OEIL_D, LARG_D)):
        L = _d(p, larg[0], larg[1]) or 1e-6
        ear += np.mean([_d(p, a, b) for a, b in paires]) / L
    ear /= 2.0

    lb = _d(p, COMMIS[0], COMMIS[1]) or 1e-6
    mar = _d(p, LEVRES[0], LEVRES[1]) / lb
    # commissures relevees : y plus petit que le centre des levres
    centre_y = (p[LEVRES[0]][1] + p[LEVRES[1]][1]) / 2
    sourire = float((centre_y - (p[COMMIS[0]][1] + p[COMMIS[1]][1]) / 2) / lb)

    x0, x1 = p[:, 0].min(), p[:, 0].max()
    y0, y1 = p[:, 1].min(), p[:, 1].max()
    larg_v = (x1 - x0) / w
    milieu_yeux = (p[LARG_G[0]][0] + p[LARG_D[1]][0]) / 2
    frontal = abs(p[NEZ][0] - milieu_yeux) / max(x1 - x0, 1e-6)

    # nettete et exposition mesurees SUR LE VISAGE, pas sur l'image entiere
    a, b = max(int(y0), 0), min(int(y1), h)
    c, e = max(int(x0), 0), min(int(x1), w)
    roi = cv2.cvtColor(img[a:b, c:e], cv2.COLOR_BGR2GRAY) if b > a and e > c else None
    nettete = float(cv2.Laplacian(roi, cv2.CV_64F).var()) if roi is not None else 0.0
    expo = float(roi.mean()) if roi is not None else 0.0

    # main devant le visage : recouvrement des boites, et proximite a la bouche
    main = 0.0
    bx = (p[COMMIS[0]][0] + p[COMMIS[1]][0]) / 2
    by = (p[LEVRES[0]][1] + p[LEVRES[1]][1]) / 2
    rm = mains.process(rgb)
    if rm.multi_hand_landmarks:
        for hlm in rm.multi_hand_landmarks:
            hx = [l.x * w for l in hlm.landmark]
            hy = [l.y * h for l in hlm.landmark]
            ix = max(0, min(x1, max(hx)) - max(x0, min(hx)))
            iy = max(0, min(y1, max(hy)) - max(y0, min(hy)))
            main = max(main, (ix * iy) / max((x1 - x0) * (y1 - y0), 1e-6))
            d = min(np.hypot(u - bx, v - by) for u, v in zip(hx, hy))
            # un point de la main a moins d une demi largeur de visage de la
            # bouche : il mange, il fume, ou il se tient le menton
            main = max(main, 1.0 - min(d / max((x1 - x0) * 0.55, 1e-6), 1.0))

    # lunettes de soleil : les yeux beaucoup plus sombres que les joues
    lunettes = 0.0
    if roi is not None and roi.size:
        def moy(cx, cy, rx, ry):
            u0, u1 = max(int(cx - rx), 0), min(int(cx + rx), w)
            v0, v1 = max(int(cy - ry), 0), min(int(cy + ry), h)
            z = img[v0:v1, u0:u1]
            return float(cv2.cvtColor(z, cv2.COLOR_BGR2GRAY).mean()) if z.size else 0.0
        ew = (x1 - x0) * 0.11
        oeil = (moy(p[LARG_G[0]][0] * .5 + p[LARG_G[1]][0] * .5, p[159][1], ew, ew * .5)
                + moy(p[LARG_D[0]][0] * .5 + p[LARG_D[1]][0] * .5, p[386][1], ew, ew * .5)) / 2
        joue = (moy(p[LARG_G[0]][0], p[LARG_G[0]][1] + (y1 - y0) * 0.22, ew, ew * .6)
                + moy(p[LARG_D[1]][0], p[LARG_D[1]][1] + (y1 - y0) * 0.22, ew, ew * .6)) / 2
        if joue > 1:
            lunettes = max(0.0, 1.0 - (oeil / joue) / 0.62)

    # cadrage : visage coupe par un bord, ou pose trop bas
    hv = max(y1 - y0, 1e-6)
    coupe = max(0.0, (y0 < 2) * 1.0, (y1 > h - 3) * 1.0,
                (x0 < 2) * 0.5, (x1 > w - 3) * 0.5)
    cy = (y0 + y1) / 2 / h
    place = min(max((0.32 - cy) / 0.18, 0.0), 1.0) + min(max((cy - 0.74) / 0.18, 0.0), 1.0)

    # regard : l iris doit tomber au milieu du segment forme par les deux coins
    regard = 0.0
    for iris, larg in ((IRIS_G, LARG_G), (IRIS_D, LARG_D)):
        c0, c1 = p[larg[0]][0], p[larg[1]][0]
        L = abs(c1 - c0) or 1e-6
        regard += abs((p[iris][0] - (c0 + c1) / 2) / L)
    regard /= 2.0

    yeux_y = (p[LARG_G[0]][1] + p[LARG_D[1]][1]) / 2
    return dict(ear=ear, mar=mar, sourire=sourire, larg=larg_v, frontal=frontal,
                nettete=nettete, expo=expo, main=main, regard=regard,
                lunettes=lunettes, coupe=coupe, place=place, yeux=yeux_y / h)


def noter(m, court, lh, relache=0):
    """relache : 0 strict, puis 1 et 2 assouplissent les seuils si aucune image
    ne passe. Sur certains rushs Valentin parle sans arret et ne ferme jamais
    completement la bouche."""
    mar_max = MAR_MAX + 0.06 * relache
    ear_min = EAR_MIN - 0.03 * relache
    front_max = FRONTAL_MAX + 0.07 * relache
    larg_min = LARG_MIN - 0.05 * relache
    if (m["mar"] > mar_max or m["ear"] < ear_min
            or m["frontal"] > front_max or m["larg"] < larg_min):
        return None

    yeux = min(max((m["ear"] - ear_min) / 0.14, 0.0), 1.0)
    bouche = 1.0 - min(m["mar"] / mar_max, 1.0)
    # un sourire franc vaut mieux qu'un visage ferme, mais on plafonne
    sourire = min(max(m["sourire"] / 0.16, 0.0), 1.0)
    # un visage large accroche, mais le gros plan extreme est desagreable
    taille = min(m["larg"] / 0.45, 1.0) - max(m["larg"] - 0.80, 0.0) * 2.0
    frontal = 1.0 - min(m["frontal"] / front_max, 1.0)
    droit = 1.0 - min(m["regard"] / 0.16, 1.0)
    nettete = min(m["nettete"] / 260.0, 1.0)
    expo = 1.0 - min(abs(m["expo"] - 132) / 90.0, 1.0)

    # le pave de texte occupe environ 17 a 32 % de la hauteur
    dans_typo = 1.0 if 0.16 < m["yeux"] < 0.34 else 0.0

    return (bouche * 3.0 + yeux * 2.5 + frontal * 2.2 + droit * 2.0
            + nettete * 2.0 + sourire * 1.6 + taille * 1.5 + expo * 1.0
            - m["main"] * 4.5 - m["lunettes"] * 3.0 - m["coupe"] * 3.0
            - m["place"] * 2.5 - dans_typo * 0.9)


def balayer(src, verbeux=False):
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    tot = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    lh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1920
    lw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1080
    court = min(lw, lh)
    deb, fin = int(tot * 0.05), int(tot * 0.95)
    pas = max(int(fps * PAS), 1)

    with FM(static_image_mode=True, max_num_faces=1, refine_landmarks=True,
            min_detection_confidence=0.4) as fm, \
         MAINS(static_image_mode=True, max_num_hands=2,
               min_detection_confidence=0.5) as mains, \
         DETECT(model_selection=1, min_detection_confidence=0.3) as det:

        brut = {}
        for i in range(deb, fin, pas):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ok, img = cap.read()
            if ok:
                m = mesures(img, fm, mains, det)
                if m:
                    brut[i] = m

        for relache in (0, 1, 2):
            notes = [(noter(m, court, lh, relache), i) for i, m in brut.items()]
            notes = [(s, i) for s, i in notes if s is not None]
            if notes:
                break
        if not notes:
            # dernier recours : aucun visage de toute la video. On garde
            # l'image la plus nette et la mieux exposee plutot que de ne rien
            # rendre, sinon le reel se retrouve sans couverture.
            repli = None
            for i in range(deb, fin, pas * 2):
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ok, img = cap.read()
                if not ok:
                    continue
                g = cv2.cvtColor(cv2.resize(img, (480, 854)), cv2.COLOR_BGR2GRAY)
                n = (min(float(cv2.Laplacian(g, cv2.CV_64F).var()) / 300.0, 1.0)
                     - abs(float(g.mean()) - 128) / 128.0)
                if repli is None or n > repli[0]:
                    repli = (n, i, img)
            cap.release()
            if repli is None:
                return None, None, None, None, 3
            vide = dict(ear=0, mar=0, sourire=0, larg=0, frontal=0, nettete=0,
                        expo=0, main=0, regard=0, lunettes=0, coupe=0,
                        place=0, yeux=0)
            return repli[2], repli[0], vide, repli[1] / fps, 3

        notes.sort(reverse=True)
        # affinage : autour de chaque bon candidat, on regarde image par image
        vus, best = set(), []
        for s, i in notes[:AFFINE]:
            for j in range(i - pas // 2, i + pas // 2 + 1, 2):
                if j in vus or j < deb or j >= fin:
                    continue
                vus.add(j)
                cap.set(cv2.CAP_PROP_POS_FRAMES, j)
                ok, img = cap.read()
                if not ok:
                    continue
                m = mesures(img, fm, mains, det)
                if not m:
                    continue
                n = noter(m, court, lh, relache)
                if n is not None:
                    best.append((n, j, m))
        if not best:
            best = [(s, i, brut[i]) for s, i in notes]

    best.sort(key=lambda t: -t[0])
    n, j, m = best[0]
    cap.set(cv2.CAP_PROP_POS_FRAMES, j)
    ok, img = cap.read()
    cap.release()
    return (img if ok else None), n, m, j / fps, relache


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    img, note, m, t, relache = balayer(src)
    if img is None:
        print(f"aucune image exploitable dans {os.path.basename(src)}")
        sys.exit(1)
    ext = os.path.splitext(dst)[1].lower()
    par = [cv2.IMWRITE_JPEG_QUALITY, 95] if ext in (".jpg", ".jpeg") else []
    cv2.imwrite(dst, img, par)
    print(f"{os.path.basename(dst)}  image a {t:.2f}s  note {note:.2f}"
          f"  (bouche {m['mar']:.2f}, yeux {m['ear']:.2f}, sourire {m['sourire']:+.2f},"
          f" face {m['frontal']:.2f}, regard {m['regard']:.2f},"
          f" visage {m['larg']*100:.0f}%, main {m['main']*100:.0f}%,"
          f" lunettes {m['lunettes']:.2f}, cadre {m['coupe']:.1f}/{m['place']:.1f}"
          f"{', seuils relaches x%d' % relache if relache else ''})")
