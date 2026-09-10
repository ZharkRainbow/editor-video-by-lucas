#!/usr/bin/env python3
"""Detecte les faux departs : Valentin lance une phrase, l'abandonne, recommence.

Whisper lisse ces reprises sur une fenetre longue : il aligne sur la phrase
dominante et fait disparaitre la tentative avortee. Le seul moyen de la voir est
de transcrire la premiere seconde SEULE, puis de comparer au debut du transcript
complet. Si les deux ne disent pas la meme chose, il y a une reprise.

usage : detecter-faux-depart.py fichier.mp4 [...]
"""
import os, re, subprocess, sys, tempfile, unicodedata

MODELE = os.path.expanduser("~/.cache/whisper-cpp/ggml-large-v3-turbo.bin")


def norme(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return [m for m in re.findall(r"[a-z0-9']+", t)]


def transcrire(src, debut, duree):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav = f.name
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(debut), "-i", src,
                    "-t", str(duree), "-ar", "16000", "-ac", "1", wav],
                   capture_output=True)
    r = subprocess.run(["whisper-cli", "-m", MODELE, "-f", wav, "-l", "fr",
                        "-np", "-nt", "-t", "8"], capture_output=True, text=True)
    os.remove(wav)
    return " ".join(r.stdout.split())


def controler(src):
    # 1.0 s est trop court : whisper hallucine et le controle croule sous les
    # faux positifs. 2.5 s lui donne assez de contexte pour etre fiable, tout en
    # restant assez court pour ne pas lisser une reprise.
    courte = transcrire(src, 0, 2.5)
    longue = transcrire(src, 0, 8.0)
    a, b = norme(courte), norme(longue)
    if not a or not b:
        return None
    n = min(len(a), 4)
    # on tolere un mot de decalage : whisper varie sur les liaisons
    concorde = a[:n] == b[:n] or a[:n] == b[1:n + 1] or a[1:n] == b[:n - 1]
    return concorde, courte, longue


if __name__ == "__main__":
    for src in sys.argv[1:]:
        r = controler(src)
        nom = os.path.basename(src)[8:46]
        if r is None:
            print(f"  ?   {nom}")
            continue
        ok, c, l = r
        marque = "OK  " if ok else "REPRISE"
        print(f"{marque:8s} {nom}")
        if not ok:
            print(f"           1re seconde seule : {c[:70]}")
            print(f"           6 premieres sec.  : {l[:70]}")
