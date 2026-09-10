#!/usr/bin/env python3
"""Position du visage sur un rush face camera (necessite le venv OpenCV).

Echantillonne des images, detecte les visages, renvoie la mediane des centres
en fraction de la largeur et de la hauteur, plus la taille mediane du visage.
La mediane resiste a une detection isolee sur un passant a l'arriere-plan.

usage : suivre-visage.py rush.mp4   ->  "cx cy taille n total"  ou "aucun"
"""
import sys, cv2, numpy as np

def suivre(src, n=24):
    cap = cv2.VideoCapture(src)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    face = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    profil = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_profileface.xml")
    xs, ys, ts = [], [], []
    for i in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * (i + 0.5) / n))
        ok, img = cap.read()
        if not ok:
            continue
        h, w = img.shape[:2]
        L = 640
        petit = cv2.resize(img, (L, int(h * L / w)))
        H = petit.shape[0]
        gris = cv2.equalizeHist(cv2.cvtColor(petit, cv2.COLOR_BGR2GRAY))
        vis = face.detectMultiScale(gris, 1.12, 6, minSize=(46, 46))
        if len(vis) == 0:
            vis = profil.detectMultiScale(gris, 1.12, 6, minSize=(46, 46))
        if len(vis) == 0:
            v2 = profil.detectMultiScale(cv2.flip(gris, 1), 1.12, 6, minSize=(46, 46))
            vis = [(L - x - bw, y, bw, bh) for (x, y, bw, bh) in v2]
        if len(vis) == 0:
            continue
        x, y, bw, bh = max(vis, key=lambda v: v[2] * v[3])   # le sujet = le plus grand
        xs.append((x + bw / 2) / L)
        ys.append((y + bh / 2) / H)
        ts.append(bw / L)
    cap.release()
    if len(xs) < 3:
        return None
    return float(np.median(xs)), float(np.median(ys)), float(np.median(ts)), len(xs), n




def serie(src, hz=2.0, lissage=2.5):
    """Suit le visage dans le temps : renvoie [(t, cx)] lisse.

    Le lissage est volontairement long : un recadrage qui colle a chaque
    micro-mouvement de tete donne une image qui tremble. On veut un panoramique
    lent, pas un asservissement.
    """
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    dur = total / fps
    face = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    profil = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_profileface.xml")
    pts = []
    n = max(int(dur * hz), 4)
    for i in range(n):
        t = dur * i / (n - 1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(int(t * fps), total - 1))
        ok, img = cap.read()
        if not ok:
            continue
        h, w = img.shape[:2]
        L = 480
        petit = cv2.resize(img, (L, int(h * L / w)))
        gris = cv2.equalizeHist(cv2.cvtColor(petit, cv2.COLOR_BGR2GRAY))
        vis = face.detectMultiScale(gris, 1.14, 5, minSize=(34, 34))
        if len(vis) == 0:
            vis = profil.detectMultiScale(gris, 1.14, 5, minSize=(34, 34))
        if len(vis) == 0:
            v2 = profil.detectMultiScale(cv2.flip(gris, 1), 1.14, 5, minSize=(34, 34))
            vis = [(L - x - bw, y, bw, bh) for (x, y, bw, bh) in v2]
        if len(vis) == 0:
            continue
        x, y, bw, bh = max(vis, key=lambda v: v[2] * v[3])
        pts.append((t, (x + bw / 2) / L))
    cap.release()
    if len(pts) < 4:
        return None
    # trous combles par la valeur voisine, puis moyenne glissante
    ts = [t for t, _ in pts]
    xs = [x for _, x in pts]
    med = float(np.median(xs))
    xs = [x if abs(x - med) < 0.22 else med for x in xs]   # rejette les aberrants
    demi = max(int(lissage * hz / 2), 1)
    liss = []
    for i in range(len(xs)):
        a, b = max(0, i - demi), min(len(xs), i + demi + 1)
        liss.append(sum(xs[a:b]) / (b - a))
    return list(zip(ts, liss))


if __name__ == "__main__":
    if "--serie" in sys.argv:
        r = serie(sys.argv[1])
        print("aucun" if r is None else
              " ".join(f"{t:.3f},{x:.4f}" for t, x in r))
    else:
        r = suivre(sys.argv[1])
        print("aucun" if r is None else
              f"{r[0]:.4f} {r[1]:.4f} {r[2]:.4f} {r[3]} {r[4]}")
