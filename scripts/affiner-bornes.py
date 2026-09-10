#!/usr/bin/env python3
"""Affine au mot pres les bornes de la selection Gauthier/Florian.

L'interpolation lineaire dans un segment SRT donne 1 a 2 s d'erreur : un extrait
peut demarrer sur la fin de la phrase precedente ou couper un mot. Ici on
retranscrit une fenetre de +/- 8 s autour de chaque borne en mot-a-mot et on
recale sur le mot cible.
"""
import difflib, json, re, subprocess, sys, unicodedata, tempfile
from pathlib import Path

MODELE = Path.home() / ".cache/whisper-cpp/ggml-large-v3-turbo.bin"
FENETRE = 8.0
CFG = Path(__file__).with_name("selection-gauthier-florian.json")

# (code, mots de depart, mots de fin) : 4 a 6 mots suffisent a lever l'ambiguite
CIBLES = {
 "G1": ("Ce que j'aimerais bien à ta place", "il peut te payer beaucoup plus"),
 "G2": ("De toute façon il faut la virer", "par mois, c'est trop compliqué"),
 "G3": ("je pense qu'on a surtout là le blocage mental", "c'est avoir des cas clients"),
 "G4": ("Et ton site est", "euros de marge par mois"),
 "G5": ("Ce qui est vraiment le cas", "tu le sens genre"),
 "G6": ("Il faut vraiment qu'elle ait un électrochoc", "on n'est pas rentable"),
 "G7": ("Mais le truc qui est bien", "22 000 euros en deux semaines"),
 "F1": ("c'est 4 500 et évidemment", "tout le monde est content"),
 "F2": ("Tes clients actuels, tu les as eu comment", "te ferait kiffer en acquisition"),
 "F3": ("j'avais testé de faire de l'emailing", "tu fais tout le temps pareil"),
 "F4": ("si jamais tu n'es pas excellent", "juste sur la partie présentiel"),
 "F5": ("soit extrême là-dessus", "ça peut aller très, très vite"),
 "F6": ("La seule contrainte qu'elle a", "ça peut être vraiment stylé"),
 "F7": ("beaucoup de gens, tu vois, ont trop peur", "ça peut être puissant"),
 "F8": ("tu peux être ultra agressif", "sur 10 ans pour payer l'encre"),
 "F9": ("si tu le fais gratuitement", "chez toi, il est habitué"),
 "F10": ("un truc typiquement, ce qui marche bien en SEO", "sur 5, 10 millions"),
 "F11": ("n'hésite pas à parler aussi à tous les fondateurs", "je le fais pour 500 euros"),
 "F12": ("les meilleures agences", "boum, boum, ça déroule"),
 "F13": ("quand tu m'as mis avec Maxence", "arrête"),
}

def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", " ", s).split()

def mots(src, debut, duree):
    """Retourne [(t_absolu, mot)] sur la fenetre demandee."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav = f.name
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{debut:.3f}", "-i", str(src),
                    "-t", f"{duree:.3f}", "-ar", "16000", "-ac", "1", "-vn", wav], check=True)
    r = subprocess.run(["whisper-cli", "-m", str(MODELE), "-l", "fr", "-ml", "1", wav],
                       capture_output=True, text=True)
    Path(wav).unlink(missing_ok=True)
    out = []
    for ligne in r.stdout.splitlines():
        m = re.match(r"\[(\d+):(\d+):([\d.]+) --> [\d:.]+\]\s+(.+)", ligne)
        if not m:
            continue
        t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        mot = m.group(4).strip()
        if mot:
            out.append((debut + t, mot))
    return out

def cale(liste, cible, fin=False):
    """Position (en s) du 1er mot de la cible, ou du dernier si fin=True.

    On aplatit en tokens : whisper decoupe "qu'il" en un seul mot, la cible en
    deux tokens. Chaque token garde le timestamp du mot dont il vient.
    """
    c = norm(cible)
    toks, tps = [], []
    for t, m in liste:
        for tok in norm(m):
            toks.append(tok)
            tps.append(t)
    for i in range(len(toks) - len(c) + 1):
        if toks[i:i + len(c)] == c:
            return tps[i + len(c) - 1] if fin else tps[i]
    # repli tolerant : whisper peut orthographier autrement sur une fenetre courte
    sm = difflib.SequenceMatcher(None, toks, c, autojunk=False)
    bl = [b for b in sm.get_matching_blocks() if b.size >= 2]
    if not bl:
        return None
    couvert = sum(b.size for b in bl)
    if couvert < max(2, len(c) - 2):
        return None
    return tps[bl[-1].a + bl[-1].size - 1] if fin else tps[bl[0].a]

def main():
    d = json.load(open(CFG, encoding="utf-8"))
    if not MODELE.exists():
        sys.exit(f"modele absent : {MODELE}")
    for client, src in d["_sources"].items():
        src = Path(src)
        for clip in d[client]:
            code, titre, a, b = clip[0], clip[1], clip[2], clip[3]
            dep, fin = CIBLES[code]
            ma = mots(src, max(0, a - FENETRE), 2 * FENETRE)
            mb = mots(src, max(0, b - FENETRE), 2 * FENETRE)
            na, nb = cale(ma, dep), cale(mb, fin, fin=True)
            print(f"{code:4s} {a:8.2f} -> {str(round(na,2)) if na else 'INTROUVABLE':>9s}   "
                  f"{b:8.2f} -> {str(round(nb,2)) if nb else 'INTROUVABLE':>9s}   {titre}", flush=True)
            if na is not None:
                clip[2] = round(na - 0.25, 2)
            if nb is not None:
                clip[3] = round(nb + 0.35, 2)
    d["_note_bornes"] = ("Bornes recalees au mot pres par affiner-bornes.py "
                         "(whisper mot-a-mot sur +/-8 s autour de chaque borne). "
                         "Marge : 0.25 s avant le premier mot, 0.35 s apres le dernier.")
    json.dump(d, open(CFG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("TERMINE")

main()
