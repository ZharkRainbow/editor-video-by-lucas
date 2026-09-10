#!/usr/bin/env python3
"""Detecte les phrases dites deux fois, meme quand whisper en efface une.

Le probleme central de tout ce chantier : sur une fenetre longue, whisper
s'aligne sur la phrase dominante et supprime purement la tentative avortee.
La 002 disait deux fois "evidemment faut pas faire que ca" et le transcript
complet ne la contenait qu'une fois. Aucun detecteur travaillant sur ce
transcript ne pouvait la voir.

La parade : transcrire le fichier par fenetres courtes, ou whisper est fiable,
et chercher les phrases qui reviennent dans deux fenetres non contigues. Une
phrase de 4 mots ou plus repetee a moins de 12 secondes d'intervalle est une
reprise, pas une figure de style.

usage : detecter-reprises.py fichier.mp4 [--fenetre 3.0] [--recouvrement 1.0]
"""
import os, re, subprocess, sys, tempfile, unicodedata

MODELE = os.path.expanduser("~/.cache/whisper-cpp/ggml-large-v3-turbo.bin")
MOTS_MIN = 4          # en dessous, on attrape des tournures banales
# LIMITE CONNUE : la 018 disait "le probleme c'est que ton probleme c'est que".
# La reprise ne partage que trois mots, elle passe donc sous ce seuil. Descendre
# a 3 attrape ce cas mais fait exploser les faux positifs sur les anaphores de
# Valentin, qui en abuse. Ce type de reprise reste a reperer a l'ecoute.
ECART_MAX = 12.0      # au-dela, c'est un rappel volontaire, pas un begaiement


def norme(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z0-9']+", t)


def duree(p):
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", p], capture_output=True, text=True).stdout.strip())


def fenetres(src, largeur, recouvrement):
    """[(debut, mots)] transcrit fenetre par fenetre."""
    d = duree(src)
    pas = largeur - recouvrement
    out = []
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, "f.wav")
        t = 0.0
        while t < d:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}",
                            "-i", src, "-t", f"{largeur:.2f}", "-ar", "16000",
                            "-ac", "1", wav], capture_output=True)
            r = subprocess.run(["whisper-cli", "-m", MODELE, "-f", wav, "-l", "fr",
                                "-np", "-nt", "-t", "8"], capture_output=True, text=True)
            m = norme(r.stdout)
            if m:
                out.append((t, m))
            t += pas
    return out


def reprises(fen, largeur):
    """Phrases presentes dans deux fenetres qui ne se chevauchent pas."""
    vues = {}
    trouve = []
    for debut, mots in fen:
        for i in range(len(mots) - MOTS_MIN + 1):
            for n in range(MOTS_MIN, min(MOTS_MIN + 4, len(mots) - i + 1)):
                cle = " ".join(mots[i:i + n])
                if cle in vues:
                    prec = vues[cle]
                    ecart = debut - prec
                    # les fenetres se recouvrent : un ecart inferieur a la
                    # largeur signifie qu'on relit le meme passage, pas une redite
                    if largeur < ecart <= ECART_MAX:
                        trouve.append((prec, debut, ecart, cle))
                        vues[cle] = debut
                else:
                    vues[cle] = debut
    # on garde la formule la plus longue par couple d'instants
    best = {}
    for a, b, e, c in trouve:
        k = (round(a, 1), round(b, 1))
        if k not in best or len(c) > len(best[k][3]):
            best[k] = (a, b, e, c)
    return sorted(best.values())


if __name__ == "__main__":
    src = sys.argv[1]
    larg = float(sys.argv[sys.argv.index("--fenetre") + 1]) if "--fenetre" in sys.argv else 3.0
    rec = float(sys.argv[sys.argv.index("--recouvrement") + 1]) if "--recouvrement" in sys.argv else 1.0
    f = fenetres(src, larg, rec)
    r = reprises(f, larg)
    nom = os.path.basename(src)
    if not r:
        print(f"OK       {nom[8:52]}")
    else:
        print(f"REPRISES {nom[8:52]}  ({len(r)})")
        for a, b, e, c in r:
            print(f"           {a:6.1f}s puis {b:6.1f}s  (+{e:.1f}s)  \"{c}\"")
