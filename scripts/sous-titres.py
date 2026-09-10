# -*- coding: utf-8 -*-
"""Fabrique des sous-titres propres a partir d'une transcription whisper mot a mot.

Trois problemes que ce module resout, tous constates sur les consultings Offbound.

  le vocabulaire metier  Whisper ecrit systematiquement « call-call » pour
      « cold call », « Lincoln » pour « LinkedIn », et massacre les noms
      propres. Un dictionnaire les corrige avant toute chose.

  la ponctuation orpheline  quand on supprime un mot fantome, sa ponctuation
      reste et on obtient « en vrai, ? ». Toute ponctuation isolee se recolle
      au mot precedent, et une virgule collee a une fin de phrase disparait.

  la coupe des groupes  couper apres « les » ou « pour » casse la lecture. Un
      mot qui appelle la suite ne termine jamais un sous-titre, sauf si on est
      deja au plafond de cinq mots.
"""
import json, re, unicodedata

# vocabulaire que whisper rate a tous les coups sur nos rushes
CORRECTIONS = {
    "call-call": "cold call", "call call": "cold call", "callcall": "cold call",
    "col-col": "cold call", "colcol": "cold call", "cole call": "cold call",
    "linkedin": "LinkedIn", "lincoln": "LinkedIn", "linkdin": "LinkedIn",
    "clauser": "closer", "r1": "R1", "r2": "R2", "ltv": "LTV",
    "saas": "SaaS", "sas": "SaaS", "b2b": "B2B", "crm": "CRM", "cro": "CRO",
    "amoury": "Amory", "amaury": "Amory", "thaumier": "Thomy", "tommy": "Thomy",
    "off-band": "Offbound", "off-bound": "Offbound", "offband": "Offbound",
    "offbond": "Offbound", "youtube": "YouTube", "youtub": "YouTube",
}

# suites de mots a reecrire : la correction mot a mot ne suffit pas
SUITES = [
    ("est-ce qu'on puisse faire", "est-ce qu'on peut se faire"),
    ("le col col", "le cold call"),
    ("du col col", "du cold call"),
    # whisper entend « au lit » pour « aux leads », meme avec le vocabulaire en amorce
    ("gouté au lit de youtube", "goûté aux leads YouTube"),
    ("goûté au lit de youtube", "goûté aux leads YouTube"),
    ("gouté au lit youtube", "goûté aux leads YouTube"),
    ("goûté au lit youtube", "goûté aux leads YouTube"),
    ("au lit youtube", "aux leads YouTube"),
    ("au lit de youtube", "aux leads YouTube"),
    ("du 7 things", "du setting"),
    ("de 7 things", "du setting"),
    ("7 things", "setting"),
    ("les gars qui t'a fait", "les gars à qui t'as fait"),
    ("gars qui t'a fait", "gars à qui t'as fait"),
]

# mots fantomes : whisper les invente sur un souffle ou un tic de langage
FANTOMES = {"savons", "hum", "euh"}

PONCTUATION = {".", ",", "?", "!", ";", ":", "...", "?!", "!?"}

# un sous-titre ne se termine jamais sur un de ces mots : ils appellent la suite
ACCROCHE = set("""le la les un une des du de d au aux et ou a en pour par sur
dans que qui quoi ce ces cet cette mon ma mes ton ta tes son sa ses tout tous
je tu il on nous vous ils plus moins tres si quand comme avec sans juste ne
mais donc car
0 1 2 3 4 5 6 7 8 9 10 20 30 40 50 100 200 300 400 500 1000""".split())

MAX_MOTS = 5


def _norm(m):
    return m.strip(" ,.?!;:").lower()


def lire_mots(chemin_json):
    """Renvoie [(debut, fin, texte)] depuis la sortie -oj de whisper-cli."""
    d = json.load(open(chemin_json, encoding="utf-8"))
    out = []
    for s in d.get("transcription", []):
        t = s.get("text", "").strip()
        if not t:
            continue
        o = s.get("offsets", {})
        out.append((o.get("from", 0) / 1000.0, o.get("to", 0) / 1000.0, t))
    return out


def corriger(mots):
    # 1. mots fantomes
    mots = [(a, b, t) for a, b, t in mots if _norm(t) not in FANTOMES]

    # 2. corrections sur une et deux unites
    propre, i = [], 0
    while i < len(mots):
        a, b, t = mots[i]
        if i + 1 < len(mots):
            deux = _norm(t + " " + mots[i + 1][2])
            if deux in CORRECTIONS:
                propre.append((a, mots[i + 1][1], CORRECTIONS[deux]))
                i += 2
                continue
        k = _norm(t)
        if k in CORRECTIONS:
            queue = t[len(t.rstrip(" ,.?!;:")):]
            propre.append((a, b, CORRECTIONS[k] + queue))
        else:
            propre.append((a, b, t))
        i += 1

    # 3. suites : on redistribue les temps sur les nouveaux mots
    for avant, apres in SUITES:
        ma, mb = avant.split(), apres.split()
        for i in range(len(propre) - len(ma) + 1):
            if [_norm(propre[i + k][2]) for k in range(len(ma))] == ma:
                deb, fin = propre[i][0], propre[i + len(ma) - 1][1]
                pas = (fin - deb) / max(len(mb), 1)
                propre[i:i + len(ma)] = [
                    (deb + j * pas, deb + (j + 1) * pas, w) for j, w in enumerate(mb)]
                break

    # 4. ponctuation orpheline recollee au mot precedent
    recolle = []
    for a, b, t in propre:
        if recolle and t.strip() in PONCTUATION:
            pa, _, pt = recolle[-1]
            recolle[-1] = (pa, b, pt.rstrip(" ,;:") + t.strip())
        else:
            recolle.append((a, b, t))

    # 5. virgule collee a une fin de phrase, ponctuation en tete, espace francaise
    out = []
    for a, b, t in recolle:
        t = re.sub(r"[,;]\s*([?!.])", r"\1", t)
        t = t.lstrip(" ,;:")
        t = re.sub(r"\s*([?!;:])", r" \1", t)
        if t.strip():
            out.append((a, b, t))
    return out


def grouper(mots, max_mots=MAX_MOTS):
    """Groupes de 4 a 5 mots, coupes sur la ponctuation, jamais sur un mot lie."""
    groupes, cur = [], []
    for a, b, t in mots:
        cur.append((a, b, t))
        lie = _norm(t) in ACCROCHE
        fin_phrase = t.rstrip().endswith((".", "?", "!"))
        virgule = t.rstrip().endswith(",")
        if lie and len(cur) < max_mots:
            continue
        if len(cur) >= max_mots or (fin_phrase and len(cur) >= 3) or (virgule and len(cur) >= 4):
            groupes.append(cur)
            cur = []
    if cur:
        if groupes and len(cur) < 2:
            groupes[-1] += cur
        else:
            groupes.append(cur)

    subs = []
    for g in groupes:
        txt = re.sub(r"\s+", " ", " ".join(x[2] for x in g)).strip()
        subs.append((g[0][0], g[-1][1], txt))
    # chaque sous-titre tient jusqu'au suivant : pas de trou a l'ecran
    return [(a, subs[i + 1][0] if i + 1 < len(subs) else b + 0.4, t)
            for i, (a, b, t) in enumerate(subs)]


def sous_titres(chemin_json, max_mots=MAX_MOTS):
    return grouper(corriger(lire_mots(chemin_json)), max_mots)


if __name__ == "__main__":
    import sys
    for a, b, t in sous_titres(sys.argv[1]):
        print(f"{a:6.2f} -> {b:6.2f}  {t}")
