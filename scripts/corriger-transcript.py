#!/usr/bin/env python3
"""Corrige le vocabulaire propre a Offbound dans une transcription whisper.

Whisper ne connait ni la marque, ni le jargon, ni les titres de l'equipe. Il
remplace ce qu'il ne reconnait pas par le mot statistiquement le plus proche,
ce qui produit des sous-titres faux a l'ecran. Chaque correction listee ici a
ete verifiee a l'oreille sur une fenetre courte, la ou whisper est fiable.

Les corrections s'appliquent sur la SUITE DE MOTS, pas sur un texte recolle :
chaque mot porte son propre timecode et il faut les preserver.
"""
import re
import unicodedata

# Un mot pour un mot. Cle comparee sans accent ni casse ni ponctuation.
MOT_A_MOT = {
    "off-band": "Offbound", "offband": "Offbound", "off-bound": "Offbound",
    "l'off-band": "l'Offbound", "off-monde": "Offbound", "offbond": "Offbound",
    "loveband": "Offbound", "off-bande": "Offbound", "offbund": "Offbound",
    "hoffman": "Offbound", "hofband": "Offbound", "hoffband": "Offbound",
    "offband": "Offbound", "hoff": "Offbound", "ofband": "Offbound",
    "offbond": "Offbound", "ofbound": "Offbound", "obande": "Offbound",
    "sass": "SaaS", "saas": "SaaS", "sas": "SaaS", "sasse": "SaaS",
    "malt": "Malt", "malts": "Malt", "malte": "Malt",
    "propals": "propales", "propal": "propale", "propas": "propales",
    "propales": "propales", "propos": "propos",
    # mots courants ecorches, reperes par controle orthographique
    "ptege": "piège",
    # argot francais que whisper ne connait pas : keuss = etre tres mince
    "cuss": "keuss", "puckus": "keuss", "kuss": "keuss", "queuss": "keuss",
    "agencias": "agences", "agencia": "agence",
    "j'enviens": "j'envoie", "enviens": "envoie",
    "backsetting": "setting",
    # rushs indoor. On ecrit ce que Valentin DIT, pas ce qu'il aurait du dire :
    # il emploie l'anglicisme "extract", on ne le traduit pas en "extraire".
    "extracte": "extract", "extractes": "extract",
    "implimente": "implémente", "implimenter": "implémenter",
    "n'implimente": "n'implémente",
    # "cold call" : whisper le francise en "col-col" ou "call-call"
    "col-col": "cold call", "colcol": "cold call", "call-call": "cold call",
    # "delivery" : le service rendu au client, pas un mot francais
    "délivrerie": "delivery", "deliverie": "delivery", "delivrerie": "delivery",
}

# Suites de mots. Ordre : les plus longues d'abord.
SUITES = [
    (["tesicp"],                     ["de", "tes", "ICP"]),
    (["tesicps"],                    ["de", "tes", "ICP"]),
    (["icps"],                       ["ICP"]),
    (["call", "call"],               ["cold", "call"]),
    # Claude Code : whisper entend systematiquement "Cloud Code"
    (["cloud", "code"],              ["Claude", "Code"]),
    (["cloud", "codes"],             ["Claude", "Code"]),
    (["claude", "codes"],            ["Claude", "Code"]),
    # Opus Clip, l'outil de decoupe
    (["opus", "clipe"],              ["Opus", "Clip"]),
    (["opus", "clips"],              ["Opus", "Clip"]),
    # events cites en consulting
    (["viva", "tech"],               ["Vivatech"]),
    (["web", "sumite"],              ["Web", "Summit"]),
    (["web", "sumit"],               ["Web", "Summit"]),
    # SalesNavigator
    (["sales", "nav"],               ["SalesNav"]),
    (["salesnave"],                  ["SalesNav"]),
    # rushs indoor, verifies a l'ecoute passage par passage
    # FOMO, fear of missing out : whisper le francise en "faux mots"
    (["faux", "mots"],               ["FOMO"]),
    (["faux", "mot"],                ["FOMO"]),
    (["faut", "mots"],               ["FOMO"]),
    (["pho", "mo"],                  ["FOMO"]),
    (["fomo"],                       ["FOMO"]),
    # SEA, le search engine advertising : whisper entend "SIA", qui n'existe pas
    (["du", "sia"],                  ["du", "SEA"]),
    (["le", "sia"],                  ["le", "SEA"]),
    # Amandine Bart, referente SEO citee par Valentin (nom confirme par Lucas)
    (["avandine", "barthes"],        ["Amandine", "Bart"]),
    (["amandine", "barthes"],        ["Amandine", "Bart"]),
    (["avandine", "bart"],           ["Amandine", "Bart"]),
    # "un gars qui code" : whisper en fait un seul mot
    (["gakicode"],                   ["gars", "qui", "code"]),
    (["gaki", "code"],               ["gars", "qui", "code"]),
    # "remunere au pourcentage" : whisper bute sur la formule
    (["a", "remuner", "a", "la", "pourcentage"], ["rémunéré", "au", "pourcentage"]),
    (["a", "remuner", "au", "pourcentage"],      ["rémunéré", "au", "pourcentage"]),
    # "French bashing" : ecrit "batching" sur la 010, correct sur la 011
    (["francais", "batching"],       ["français", "bashing"]),
    # "repartir pour 2027" : whisper entend l'annee comme deux nombres
    (["2020", "cents"],              ["2027"]),
    (["2020", "sept"],               ["2027"]),
    (["call", "d'email"],            ["cold", "email"]),
    (["col", "d'email"],             ["cold", "email"]),
    (["call", "d'e-mail"],           ["cold", "email"]),
    (["hauts-de-parc", "en"],        ["autre", "part", "qu'en"]),
    (["haute", "park", "en"],        ["autre", "part", "qu'en"]),
    (["personal", "brain"],          ["personal", "brand"]),
    # "Focus is key" : whisper ne connait pas la formule et la francise
    (["focus", "il", "se", "quitte"],  ["Focus", "is", "key"]),
    (["focus", "ils", "skient"],       ["Focus", "is", "key"]),
    (["focus", "il", "skie"],          ["Focus", "is", "key"]),
    (["focus", "is", "quitte"],        ["Focus", "is", "key"]),
    (["focus", "il", "ski"],           ["Focus", "is", "key"]),
    # elision : whisper ecrit "de Hoffman", la correction donne "de Offbound"
    (["de", "offbound"],             ["d'Offbound"]),
    (["de", "hoffman"],              ["d'Offbound"]),
    (["de", "off-band"],             ["d'Offbound"]),
    # noms de produits que whisper francise
    (["chatdipity"],                 ["ChatGPT"]),
    (["chagipity"],                  ["ChatGPT"]),
    (["chat", "dipity"],             ["ChatGPT"]),
    (["chat", "gpt"],                ["ChatGPT"]),
    (["tchat", "gpt"],               ["ChatGPT"]),
    (["chatgpt"],                    ["ChatGPT"]),
    # MCP est le protocole d'Anthropic : "MCP Cloud" est un MCP Claude
    (["mcp", "cloud"],               ["MCP", "Claude"]),
    # expressions francaises que whisper anglicise. Contextualisees sur le
    # revenu : "en dancing" seul pourrait designer une vraie salle de danse.
    (["revenu", "vraiment", "en", "dancing"],
     ["revenu", "vraiment", "en", "dents", "de", "scie"]),
    (["revenu", "en", "dancing"],    ["revenu", "en", "dents", "de", "scie"]),
    (["revenus", "en", "dancing"],   ["revenus", "en", "dents", "de", "scie"]),
    (["chiffre", "en", "dancing"],   ["chiffre", "en", "dents", "de", "scie"]),
    # termes financiers que whisper ne connait pas
    # Le debruitage a fait halluciner whisper sur ce mot : sur l'audio brut il
    # entend "trucs", de facon stable et sur deux passes independantes.
    # Motifs complets d'abord : la correction se fait en une passe, un motif
    # court consommerait les jetons avant que le long soit teste.
    (["court-titres", "dans", "des", "specs"],
     ["comptes-titres", "dans", "des", "trucs"]),
    (["court-titres", "dans", "des", "snakes"],
     ["comptes-titres", "dans", "des", "trucs"]),
    (["court-titres", "dans", "des", "sneques"],
     ["comptes-titres", "dans", "des", "trucs"]),
    (["court-titres", "dans", "des", "smegs"],
     ["comptes-titres", "dans", "des", "trucs"]),
    (["court-titres", "dans", "des", "spectacles"],
     ["comptes-titres", "dans", "des", "trucs"]),
    (["court-titres", "dans", "des", "specks"],
     ["comptes-titres", "dans", "des", "trucs"]),
    (["co-titres", "dans", "des", "specs"],
     ["comptes-titres", "dans", "des", "trucs"]),
    (["co-titres", "dans", "des", "snakes"],
     ["comptes-titres", "dans", "des", "trucs"]),
    (["co-titres", "dans", "des", "sneques"],
     ["comptes-titres", "dans", "des", "trucs"]),
    (["co-titres", "dans", "des", "smegs"],
     ["comptes-titres", "dans", "des", "trucs"]),
    (["co-titres", "dans", "des", "spectacles"],
     ["comptes-titres", "dans", "des", "trucs"]),
    (["co-titres", "dans", "des", "specks"],
     ["comptes-titres", "dans", "des", "trucs"]),
    (["comptes-titres", "dans", "des", "specs"],
     ["comptes-titres", "dans", "des", "trucs"]),
    (["comptes-titres", "dans", "des", "snakes"],
     ["comptes-titres", "dans", "des", "trucs"]),
    (["comptes-titres", "dans", "des", "sneques"],
     ["comptes-titres", "dans", "des", "trucs"]),
    (["comptes-titres", "dans", "des", "smegs"],
     ["comptes-titres", "dans", "des", "trucs"]),
    (["comptes-titres", "dans", "des", "spectacles"],
     ["comptes-titres", "dans", "des", "trucs"]),
    (["comptes-titres", "dans", "des", "specks"],
     ["comptes-titres", "dans", "des", "trucs"]),
    (["co-titres"],                  ["comptes-titres"]),
    (["court-titres"],               ["comptes-titres"]),
    (["court", "titres"],            ["comptes-titres"]),
    (["co", "titres"],               ["comptes-titres"]),
    (["comptes", "titre"],           ["comptes-titres"]),

    (["plus", "du", "selection"],    ["plus", "de", "ce", "siècle"]),
    (["m'explotait"],                ["m'exploitait"]),
    # Lucas est COO, pas CEO. Les deux seules occurrences qui le designent :
    # verifiees a l'oreille, Valentin prononce bien C-O-O.
    (["le", "ceo", "que"],           ["le", "COO", "que"]),
    (["tant", "que", "ceo"],         ["tant", "que", "COO"]),
]


# Whisper comble les silences avec des formules de generique apprises sur des
# sous-titres de television. Elles n'ont jamais ete prononcees et se retrouvent
# incrustees a l'ecran en fin de reel. On les supprime purement.
HALLUCINATIONS = [
    ["sous", "titrage"], ["sous-titrage"], ["societe", "radio", "canada"],
    ["radio-canada"], ["societe", "radio-canada"],
    ["amara", "org"], ["merci", "d'avoir", "regarde"],
    ["abonnez", "vous"], ["sous-titres", "realises", "par"],
    ["sous", "titres", "realises"], ["merci", "a", "tous"],
]


# Le nom de la marque, par regle plutot que par liste.
#
# Lister les graphies ne suffit pas : whisper en invente une nouvelle a chaque
# passe, et il lui arrive de couper le mot en deux ("of" puis "band"), ce qu'un
# dictionnaire a un mot ne voit jamais. On raisonne donc sur la forme : tout ce
# qui commence par of/off/hof et se termine par une de ces syllabes est la
# marque. Les vrais mots francais en "off" sont proteges par la liste blanche.
OFF_DEBUTS = ("off", "of", "hof", "hoff")
OFF_FINS_GROUPE = {"group", "groupe", "groupes", "grp"}
OFF_FINS_MARQUE = {"band", "bande", "bandes", "bond", "bonde", "bound", "bounds",
                   "vend", "vent", "vante", "monde", "man", "mane", "band's",
                   "banque", "bent", "vand", "bande's"}
OFF_MOTS_VRAIS = {"off", "office", "officiel", "officielle", "officiels",
                  "officielles", "offre", "offres", "offrir", "offert",
                  "offerte", "offerts", "offensive", "offshore", "offset",
                  "of", "often", "offense"}


def _decoupe_off(k):
    """Renvoie 'groupe', 'marque' ou None pour une cle donnee."""
    n = k.replace("-", "").replace("'", "").replace(" ", "")
    if k in OFF_MOTS_VRAIS or n in OFF_MOTS_VRAIS:
        return None
    for d in sorted(OFF_DEBUTS, key=len, reverse=True):
        if n.startswith(d):
            reste = n[len(d):]
            if reste in OFF_FINS_GROUPE:
                return "groupe"
            if reste in OFF_FINS_MARQUE:
                return "marque"
    return None


def cle(mot):
    m = unicodedata.normalize("NFD", mot.lower())
    m = "".join(c for c in m if unicodedata.category(c) != "Mn")
    return m.strip(" ,.;:!?»«…\"")


def _ponctuation(origine):
    """Recupere la ponctuation finale du mot remplace."""
    m = re.search(r"[,.;:!?…»]+$", origine)
    return m.group(0) if m else ""


# Whisper invente une graphie differente a chaque passe pour le nom de
# Valentin : Thaumy, Tommy, Tomy, Taumier... Lister les variantes ne suffit pas,
# il en sort toujours une nouvelle. On prend donc la regle inverse : apres le
# prenom, tout mot commençant par un t qui n'est pas un mot courant est son nom.
APRES_VALENTIN_OK = {
    "ta", "te", "tes", "toi", "ton", "tous", "tout", "toute", "toutes",
    "toujours", "trop", "tres", "travaille", "tu", "type", "tellement",
    "tellement", "tel", "telle", "tenir", "temps", "termine", "trouve",
}


def corriger(mots):
    """mots = [(t0, t1, texte)] -> meme forme, vocabulaire corrige."""
    out = list(mots)

    # suites d'abord : elles peuvent changer le nombre de mots
    i = 0
    res = []
    while i < len(out):
        remplace = None
        for source, cible in SUITES:
            n = len(source)
            if i + n > len(out):
                continue
            if [cle(out[i + k][2]) for k in range(n)] == source:
                remplace = (n, cible)
                break
        if remplace:
            n, cible = remplace
            t0 = out[i][0]
            t1 = out[i + n - 1][1]
            fin = _ponctuation(out[i + n - 1][2])
            pas = (t1 - t0) / max(len(cible), 1)
            for j, mot in enumerate(cible):
                a = t0 + j * pas
                b = t0 + (j + 1) * pas
                res.append((a, b, mot + (fin if j == len(cible) - 1 else "")))
            i += n
        else:
            res.append(out[i])
            i += 1

    # marque : d'abord les paires, car whisper coupe parfois le mot en deux
    fus = []
    i = 0
    while i < len(res):
        if i + 1 < len(res):
            k1, k2 = cle(res[i][2]), cle(res[i + 1][2])
            if k1 in OFF_DEBUTS and k1 not in OFF_MOTS_VRAIS - {"off", "of"} or \
               (k1 in ("off", "of", "hof", "hoff")):
                genre = _decoupe_off(k1 + k2)
                if genre:
                    nom = "Offgroup" if genre == "groupe" else "Offbound"
                    fus.append((res[i][0], res[i + 1][1],
                                nom + _ponctuation(res[i + 1][2])))
                    i += 2
                    continue
        res_i = res[i]
        genre = _decoupe_off(cle(res_i[2]))
        if genre:
            nom = "Offgroup" if genre == "groupe" else "Offbound"
            fus.append((res_i[0], res_i[1], nom + _ponctuation(res_i[2])))
        else:
            fus.append(res_i)
        i += 1
    res = fus

    # hallucinations : on retire les suites entieres
    net = []
    i = 0
    while i < len(res):
        saute = 0
        for h in HALLUCINATIONS:
            n = len(h)
            if i + n <= len(res) and [cle(res[i + k][2]) for k in range(n)] == h:
                saute = n
                break
        if saute:
            i += saute
        else:
            net.append(res[i])
            i += 1
    res = net

    # nom de famille de Valentin : regle par position, pas par liste
    for i in range(len(res) - 1):
        if cle(res[i][2]) != "valentin":
            continue
        t0, t1, w = res[i + 1]
        k = cle(w)
        if k.startswith("t") and k not in APRES_VALENTIN_OK and len(k) >= 4:
            res[i + 1] = (t0, t1, "Thomy" + _ponctuation(w))

    # puis mot a mot
    final = []
    for t0, t1, w in res:
        k = cle(w)
        if k in MOT_A_MOT:
            final.append((t0, t1, MOT_A_MOT[k] + _ponctuation(w)))
        else:
            final.append((t0, t1, w))
    return final


if __name__ == "__main__":
    import sys
    for a in sys.argv[1:]:
        print(a, "->", corriger([(0.0, 1.0, a)])[0][2])
