#!/usr/bin/env python3
"""Repere les faux departs : Valentin lance une phrase, s'arrete, recommence.

POURQUOI UN OUTIL
Lucas a signale trois fois le meme defaut, et trois fois je l'avais manque :
douze secondes de blanc au milieu de la 006, un "Un quelque chose ?" abandonne
avant la bonne prise sur la 005, une hesitation en tete de la 007 outdoor. Ni
le controle du debut ni le detecteur de begaiement ne les voyaient : un faux
depart n'est ni un silence de tete, ni une repetition de mots.

CE QU'ON CHERCHE
La signature est toujours la meme, dans la STRUCTURE de la parole :
  un bout de phrase court, puis un silence anormalement long, puis la reprise.
On ne se fie donc pas au texte mais au decoupage du son :
  - un segment de parole de moins de 1,8 s ;
  - suivi d'un silence d'au moins 0,7 s ;
  - alors que le segment suivant, lui, est long : c'est la vraie prise.
On signale aussi tout silence de plus de 1,5 s, meme sans faux depart : sur un
reel, un blanc pareil se voit.

usage : detecter-relance.py [dossier]
"""
import glob
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recaler

MODELE = os.path.expanduser("~/.cache/whisper-cpp/ggml-large-v3-turbo.bin")
COURT = 1.8        # un vrai debut de phrase dure plus longtemps que ca
PAUSE = 0.70       # en dessous, c'est une respiration
SUITE = 2.0        # la reprise, elle, est franche
BLANC = 1.5        # tout silence au-dela se voit a l'ecran


def dire(wav, a, b):
    bout = f"/tmp/_relance{os.getpid()}.wav"
    recaler.sh("ffmpeg", "-y", "-v", "error", "-i", wav, "-ss", f"{a:.2f}",
               "-to", f"{b:.2f}", "-ar", "16000", "-ac", "1", bout)
    if not os.path.exists(bout):
        return ""
    t = subprocess.run(["whisper-cli", "-m", MODELE, "-f", bout, "-l", "fr",
                        "-np", "-nt"], capture_output=True, text=True).stdout
    os.remove(bout)
    return " ".join(t.split())


def analyser(video):
    wav = f"/tmp/_rel{os.getpid()}.wav"
    recaler.sh("ffmpeg", "-y", "-v", "error", "-i", video,
               "-ar", "16000", "-ac", "1", wav)
    segs = recaler.segments_parole(wav)
    fin = len(recaler.enveloppe(wav)) * recaler.PAS
    faux, blancs = [], []
    t = 0.0
    for i, (a, z) in enumerate(segs):
        if a - t >= BLANC:
            blancs.append((t, a))
        duree = z - a
        suivant = segs[i + 1] if i + 1 < len(segs) else None
        if (suivant and duree <= COURT and suivant[0] - z >= PAUSE
                and suivant[1] - suivant[0] >= SUITE):
            faux.append((a, z, suivant[0], dire(wav, a, z),
                         dire(wav, suivant[0], min(suivant[0] + 3.5, suivant[1]))))
        t = z
    if fin - t >= BLANC:
        blancs.append((t, fin))
    os.remove(wav)
    return faux, blancs


def main(dossier):
    total = 0
    for f in sorted(glob.glob(os.path.join(dossier, "*.mp4"))):
        base = os.path.basename(f)[:-4]
        faux, blancs = analyser(f)
        if not faux and not blancs:
            print(f"{base[:46]:<48}  propre")
            continue
        print(f"{base[:46]:<48}  {len(faux)} relance(s), {len(blancs)} blanc(s)")
        for a, z, s, avant, apres in faux:
            print(f"    {a:7.2f}-{z:.2f}s  abandonne  « {avant[:44]} »")
            print(f"    {s:7.2f}s          reprend    « {apres[:44]} »")
            print(f"                       a couper : {a - 0.10:.2f}-{s - 0.15:.2f}")
        for a, z in blancs:
            print(f"    {a:7.2f}-{z:.2f}s  blanc de {z - a:.1f} s")
        total += len(faux) + len(blancs)
    print(f"\n{total} passage(s) a traiter")
    return 0


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
        "~/Downloads/VAL-Indoor-Propres/_racine")
    raise SystemExit(main(d))
