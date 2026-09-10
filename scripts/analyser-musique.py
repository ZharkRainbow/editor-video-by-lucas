#!/usr/bin/env python3
"""Caracterise un morceau : tempo, niveau, nervosite.

Le tempo vient d'une autocorrelation de l'enveloppe d'attaques : on mesure a
quel intervalle les impacts se repetent. La nervosite est l'ecart-type de
l'energie : un morceau qui varie beaucoup se remarque, un morceau plat s'oublie
et c'est exactement ce qu'on veut derriere une voix.

usage : analyser-musique.py fichier.mp3 [...]
"""
import os, subprocess, sys
import numpy as np

TAUX = 22050


def charger(src, secondes=90):
    r = subprocess.run(["ffmpeg", "-v", "error", "-t", str(secondes), "-i", src,
                        "-ac", "1", "-ar", str(TAUX), "-f", "f32le", "-"],
                       capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32)


def tempo(x, saut=256):
    # enveloppe d'energie, puis flux positif = attaques
    n = len(x) // saut
    env = np.sqrt(np.array([np.mean(x[i*saut:(i+1)*saut]**2) for i in range(n)]) + 1e-12)
    flux = np.diff(env)
    flux[flux < 0] = 0
    flux -= flux.mean()
    ac = np.correlate(flux, flux, mode="full")[len(flux) - 1:]
    fps = TAUX / saut
    lo, hi = int(fps * 60 / 180), int(fps * 60 / 60)      # 60 a 180 BPM
    if hi >= len(ac):
        return 0.0
    pic = lo + int(np.argmax(ac[lo:hi]))
    return round(60.0 * fps / pic, 1)


def nervosite(x, fen=None):
    fen = fen or TAUX // 2
    n = len(x) // fen
    e = np.array([np.sqrt(np.mean(x[i*fen:(i+1)*fen]**2) + 1e-12) for i in range(n)])
    db = 20 * np.log10(e + 1e-9)
    return round(float(np.std(db)), 2)


if __name__ == "__main__":
    print(f"{'morceau':38s} {'BPM':>6s} {'nervosite':>10s}")
    for f in sys.argv[1:]:
        x = charger(f)
        if x.size < TAUX:
            print(f"{os.path.basename(f)[:38]:38s}      -          -")
            continue
        print(f"{os.path.basename(f)[:38]:38s} {tempo(x):6.1f} {nervosite(x):10.2f}")
