"""Controle final : calage des sous-titres et silences trop longs.

Deux mesures independantes, comparees :
  - quand la voix commence reellement (detecteur d'enveloppe sur la voix
    nettoyee, le meme que recaler.py) ;
  - quand le premier sous-titre est programme (transcription recalee).

Un ecart de plus de 0,30 s se voit a l'oeil : soit le texte precede la voix,
soit il traine derriere. C'est ce controle qui aurait attrape du premier coup
le defaut de la 007, ou le texte partait 1,7 s avant la parole.

On signale aussi les SILENCES LONGS au milieu du reel. Le controle ne portait
d'abord que sur le debut, et la VAL-006 indoor est passee au travers avec
12,4 secondes de vide au milieu, reperees par Lucas et pas par moi. Sur un
reel, tout ce qui depasse une seconde et demie sans voix se voit.

usage : verifier-calage.py [dossier_racine]
"""
import glob
import importlib.util
import json
import os
import subprocess
import sys

SC = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SC)
import recaler

spec = importlib.util.spec_from_file_location("genreel", os.path.join(SC, "gen-reel.py"))
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

W = os.path.expanduser("~/Documents/RAIZ-Claude/OFFBOUND/CONTENU/reels-hyperframes")
TOLERANCE = 0.30
SILENCE_MAX = 1.5      # au-dela, un blanc au milieu du reel se voit


def mots_du_cache(cache):
    mots = []
    for l in open(cache, encoding="utf-8"):
        m = G.LIGNE.match(l.strip())
        if not m:
            continue
        w = m.group(7).strip()
        if not w or w in "«»:;":
            continue
        t0 = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        t1 = int(m.group(4)) * 3600 + int(m.group(5)) * 60 + float(m.group(6))
        if mots and mots[-1][2] == w and t0 - mots[-1][1] < 0.02:
            continue
        mots.append((t0, max(t1, t0 + 0.06), w))
    return G.CORR.corriger(mots)


def main(racine):
    tmp = os.path.join(os.path.dirname(racine), "_verif.wav")
    ecarts, alertes = [], []
    print(f"{'reel':<46}{'voix':>7}{'texte':>8}{'ecart':>8}   {'':<3}")
    for f in sorted(glob.glob(os.path.join(racine, "*.mp4"))):
        base = os.path.basename(f)[:-4]
        cache = os.path.join(W, ".mots-" + base + ".txt")
        if not os.path.exists(cache) or not os.path.exists(cache + ".cal.json"):
            print(f"{base[:44]:<46}   pas de transcription en cache")
            continue
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f,
                        "-ar", "16000", "-ac", "1", tmp], check=True)
        segs = recaler.segments_parole(tmp)
        env = recaler.enveloppe(tmp)
        fin = len(env) * recaler.PAS
        blancs, t = [], 0.0
        for a, z in segs:
            if a - t >= SILENCE_MAX:
                blancs.append((t, a))
            t = z
        if fin - t >= SILENCE_MAX:
            blancs.append((t, fin))
        # segments_parole rouvre chaque segment de MARGE : il faut la retirer
        # pour retrouver l'instant reel, sauf quand le segment part de zero,
        # ou il n'y a rien a retirer. Sans ce detail, tout reel qui demarre
        # pile sur la parole affichait un faux ecart de -0,12 s.
        voix = (segs[0][0] + recaler.MARGE if segs and segs[0][0] > 0.001
                else 0.0) if segs else 0.0
        ref = [tuple(x) for x in json.load(open(cache + ".cal.json", encoding="utf-8"))]
        texte = recaler.recaler(mots_du_cache(cache), ref)[0][0]
        e = texte - voix
        ecarts.append(abs(e))
        drapeau = "" if abs(e) <= TOLERANCE else ("  TEXTE EN AVANCE" if e < 0 else "  TEXTE EN RETARD")
        if drapeau:
            alertes.append(base)
        if blancs:
            drapeau += "  BLANC " + " ".join(f"{a:.0f}-{z:.0f}s" for a, z in blancs)
            if base not in alertes:
                alertes.append(base)
        print(f"{base[:44]:<46}{voix:7.2f}{texte:8.2f}{e:+8.2f}{drapeau}")
    if os.path.exists(tmp):
        os.remove(tmp)
    print()
    if alertes:
        print(f"{len(alertes)} reel(s) hors tolerance : " + ", ".join(a[:11] for a in alertes))
        return 1
    print(f"tous cales a moins de {TOLERANCE:.2f} s "
          f"(ecart moyen {sum(ecarts)/max(len(ecarts),1):.3f} s)")
    return 0


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
        "~/Downloads/VAL-Outdoor-Propres/_racine")
    raise SystemExit(main(d))
