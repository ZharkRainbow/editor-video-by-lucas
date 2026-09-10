"""Repere les bafouillages a l'oreille, pas sur le transcript.

POURQUOI LE TRANSCRIPT NE SUFFIT PAS
whisper decode par fenetres de 30 s. Sur une fenetre longue il "nettoie" : si
Valentin dit "je je je pense", il ecrit "je pense". Le transcript est donc muet
sur exactement ce qu'on cherche. Lucas : le probleme n'est pas le sous-titre,
c'est ce qu'on entend, et un reel ou l'on begaie fait fuir le spectateur.

LE SIGNAL QU'ON UTILISE
recaler.py retranscrit deja chaque segment de parole isolement pour caler les
sous-titres. Sur une fenetre de 2 a 5 s, whisper n'a plus la place de nettoyer :
il ecrit ce qu'il entend, repetitions comprises. Ce cache (.cal.json) est donc
un temoin fidele du son, et il est deja calcule.

CE QU'ON CHERCHE
  - une suite de 1 a 4 mots repetee immediatement ("je je", "c'est-a-dire
    c'est-a-dire") ;
  - les mots de remplissage isoles entre deux silences ("euh", "hein").

usage : detecter-begaiement.py [dossier_racine]
"""
import glob
import json
import os
import re
import subprocess
import sys
import unicodedata

W = os.path.expanduser("~/Documents/RAIZ-Claude/OFFBOUND/CONTENU/reels-hyperframes")
N_MAX = 4          # longueur maximale du groupe repete
ECART_MAX = 1.20   # au dela, ce n'est plus une reprise mais un rappel voulu
REMPLISSAGE = {"euh", "heu", "hein", "bah", "ben", "voila", "enfin"}
MODELE = os.path.expanduser("~/.cache/whisper-cpp/ggml-large-v3-turbo.bin")
# tournures ou la repetition est voulue : Valentin insiste, il ne bafouille pas
VOULU = {"plein", "ciao", "tchao", "non", "oui", "tres", "vite", "loin"}


def cle(mot):
    m = unicodedata.normalize("NFD", mot.lower())
    m = "".join(c for c in m if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9']", "", m)


def repetitions(mots):
    """Groupes de 1 a N_MAX mots repetes immediatement. Le plus long d'abord."""
    k = [cle(w) for _, _, w in mots]
    trouves, pris = [], set()
    for n in range(N_MAX, 0, -1):
        for i in range(len(mots) - 2 * n + 1):
            if any(j in pris for j in range(i, i + 2 * n)):
                continue
            if not all(k[i + j] for j in range(n)):
                continue
            if k[i:i + n] != k[i + n:i + 2 * n]:
                continue
            if mots[i + n][0] - mots[i + n - 1][1] > ECART_MAX:
                continue
            trouves.append((mots[i][0], mots[i + n - 1][1],
                            " ".join(w for _, _, w in mots[i:i + n]), n))
            pris.update(range(i, i + 2 * n))
    return sorted(trouves)


def remplissages(mots):
    out = []
    for i, (t0, t1, w) in enumerate(mots):
        if cle(w) not in REMPLISSAGE:
            continue
        avant = t0 - mots[i - 1][1] if i else 9
        apres = mots[i + 1][0] - t1 if i + 1 < len(mots) else 9
        if avant > 0.25 and apres > 0.25:      # isole entre deux silences
            out.append((t0, t1, w))
    return out


def confirme(video, t0, t1, texte):
    """Reecoute le passage pour trancher.

    Une repetition reperee dans le cache peut n'etre qu'une couture : le mot
    de fin d'un segment reapparait au debut du suivant. On reextrait donc une
    fenetre courte autour du passage et on verifie que le groupe y figure bien
    deux fois d'affilee. Verifie a la main sur six cas : quatre etaient des
    fausses alertes.
    """
    a, b = max(t0 - 1.2, 0), t1 + 1.6
    tmp = f"/tmp/_beg{os.getpid()}.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video, "-ss", f"{a:.2f}",
                    "-to", f"{b:.2f}", "-ar", "16000", "-ac", "1", tmp],
                   capture_output=True)
    if not os.path.exists(tmp):
        return None
    dit = subprocess.run(["whisper-cli", "-m", MODELE, "-f", tmp, "-l", "fr",
                          "-np", "-nt"], capture_output=True, text=True).stdout
    os.remove(tmp)
    suite = [cle(w) for w in dit.split() if cle(w)]
    groupe = [cle(w) for w in texte.split() if cle(w)]
    n = len(groupe)
    double = any(suite[i:i + n] == groupe and suite[i + n:i + 2 * n] == groupe
                 for i in range(len(suite) - 2 * n + 1))
    return (dit.strip(), double)


def main(racine):
    total = 0
    for f in sorted(glob.glob(os.path.join(racine, "*.mp4"))):
        base = os.path.basename(f)[:-4]
        ancre = os.path.join(W, ".mots-" + base + ".txt.cal.json")
        if not os.path.exists(ancre):
            print(f"{base[:44]:<46}  pas encore analyse")
            continue
        mots = [tuple(x) for x in json.load(open(ancre, encoding="utf-8"))]
        rep = repetitions(mots)
        rem = remplissages(mots)
        if not rep and not rem:
            print(f"{base[:44]:<46}  propre")
            continue
        confirmes = []
        for t0, t1, texte, n in rep:
            if cle(texte) in VOULU:
                continue
            v = confirme(f, t0, t1, texte)
            if v and v[1]:
                confirmes.append((t0, texte, v[0]))
        if not confirmes and not rem:
            print(f"{base[:44]:<46}  propre "
                  f"({len(rep)} fausse(s) alerte(s) ecartee(s))")
            continue
        print(f"{base[:44]:<46}  {len(confirmes)} begaiement(s) confirme(s)")
        for t0, texte, dit in confirmes:
            print(f"    {t0:7.2f}s  « {texte} » repete  ->  {dit[:78]}")
        for t0, _, w in rem:
            print(f"    {t0:7.2f}s  hesitation isolee : « {w} »")
        total += len(confirmes) + len(rem)
    print(f"\n{total} begaiement(s) confirme(s) a l'ecoute")
    return 0


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
        "~/Downloads/VAL-Outdoor-Propres/_racine")
    raise SystemExit(main(d))
