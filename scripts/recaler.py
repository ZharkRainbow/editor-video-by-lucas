"""Recale les horodatages de whisper sur la parole reellement prononcee.

LE DEFAUT
whisper.cpp decode par fenetres de 30 s et repartit les mots a l'interieur de
la fenetre sans modeliser les silences. Quand un reel commence par un souffle
ou une respiration, whisper accroche les premiers mots au debut de la fenetre.
Mesure sur la 007 : whisper date "Je" a 0,00 s, "me" a 0,27 s, "suis" a 0,65 s,
alors qu'en decoupant l'audio on constate que rien n'est prononce avant 1,55 s
et que la phrase entiere "je me suis interdit de m'associer" tient entre
1,55 s et 2,95 s. Les trois premiers mots passaient donc a l'ecran une seconde
et demie avant la voix. C'est le "decalage au tout debut" signale par Lucas.

LA REPARATION
On ne touche pas au texte, seulement au minutage :
  1. on decoupe l'audio nettoye en segments de parole (detecteur d'enveloppe
     maison : silencedetect ne voit rien sur ces rushs sans un reglage fin) ;
  2. on retranscrit CHAQUE segment separement. Sur 1 a 5 s whisper ne peut plus
     deriver : ses horodatages sont bons par construction ;
  3. on apparie cette seconde liste avec la premiere (difflib) et on recopie
     les bons horodatages sur le texte deja relu et valide.

Le texte reste celui de la transcription complete, qui profite du contexte de
la phrase entiere. Seul le minutage vient des segments.
"""
import difflib
import math
import os
import re
import struct
import subprocess
import unicodedata
import wave

MODELE = os.path.expanduser("~/.cache/whisper-cpp/ggml-large-v3-turbo.bin")
LIGNE = re.compile(r"\[(\d+):(\d+):([\d.]+) --> (\d+):(\d+):([\d.]+)\]\s*(.*)")

PAS = 0.01            # resolution de l'enveloppe
MARGE_DB = 16.0       # au dessus du plancher de bruit = on considere que ca parle
PAUSE_MIN = 0.18      # en dessous, c'est une respiration : pas une coupure
FUSION = 0.10         # deux silences separes par moins que ca n'en font qu'un
MARGE = 0.12          # on rouvre le segment de part et d'autre, sans raboter
DERIVE_MAX = 0.45     # au dela, l'appariement est faux plutot que whisper
                      # (mesure sur la 008 outdoor : Valentin repete "la je
                      # suis en train d'inviter", la transcription complete
                      # n'en garde qu'une occurrence, et l'appariement se
                      # calait sur la seconde, 2,3 s plus loin. Ramene a 0,45
                      # apres la 016 indoor, ou la meme erreur decalait tout
                      # de 0,89 s en passant juste sous l'ancien seuil.)
BLOC_MIN = 2          # un mot isole qui coincide est une coincidence, pas une ancre
DUREE_MIN = 0.15      # un segment plus court ne porte pas de mot


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout


def cle(mot):
    """Forme comparable : sans accent, sans ponctuation, en minuscules."""
    m = unicodedata.normalize("NFD", mot.lower())
    m = "".join(c for c in m if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9']", "", m)


def mots_de(sortie, decalage=0.0):
    out = []
    for l in sortie.splitlines():
        m = LIGNE.match(l.strip())
        if not m:
            continue
        w = m.group(7).strip()
        if not w or w in "«»:;":
            continue
        t0 = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        t1 = int(m.group(4)) * 3600 + int(m.group(5)) * 60 + float(m.group(6))
        out.append((t0 + decalage, max(t1, t0 + 0.06) + decalage, w))
    return out


def enveloppe(wav):
    """Niveau RMS en dB par tranche de 10 ms, lu directement sur les echantillons."""
    w = wave.open(wav)
    sr = w.getframerate()
    brut = w.readframes(w.getnframes())
    ech = struct.unpack(f"<{len(brut) // 2}h", brut)
    h = int(sr * PAS)
    return [10 * math.log10(sum(v * v for v in ech[i:i + h]) / h / (32768.0 ** 2) + 1e-12)
            for i in range(0, len(ech) - h, h)]


def segments_parole(wav):
    """Intervalles ou quelqu'un parle. Complementaire des vraies pauses."""
    e = enveloppe(wav)
    if not e:
        return []
    ordre = sorted(e)
    seuil = max(ordre[len(ordre) // 10] + MARGE_DB, -45.0)
    muet = [v < seuil for v in e]

    trous, i = [], 0
    while i < len(muet):
        if not muet[i]:
            i += 1
            continue
        j = i
        while j < len(muet) and muet[j]:
            j += 1
        trous.append([i * PAS, j * PAS])
        i = j
    fus = []
    for t in trous:
        if fus and t[0] - fus[-1][1] < FUSION:
            fus[-1][1] = t[1]
        else:
            fus.append(t)
    trous = [t for t in fus if t[1] - t[0] >= PAUSE_MIN]

    total = len(e) * PAS
    segs, t = [], 0.0
    for a, b in trous:
        if a - t >= DUREE_MIN:
            segs.append((max(t - MARGE, 0), min(a + MARGE, total)))
        t = b
    if total - t >= DUREE_MIN:
        segs.append((max(t - MARGE, 0), total))
    return segs


def horodatages_reels(wav_voix, tmp):
    """Retranscrit chaque segment isolement : aucune derive possible.

    Le nom des fichiers temporaires porte le PID : plusieurs montages tournent
    parfois en parallele dans le meme dossier de travail, et sans cela ils se
    marchent dessus (un process efface le segment qu'un autre vient d'ecrire).
    """
    mots = []
    for i, (a, b) in enumerate(segments_parole(wav_voix)):
        bout = os.path.join(tmp, f"_seg{os.getpid()}_{i:03d}.wav")
        try:
            sh("ffmpeg", "-y", "-v", "error", "-i", wav_voix,
               "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-ar", "16000", "-ac", "1", bout)
            if not os.path.exists(bout):
                continue          # segment vide : rien a en tirer
            mots += mots_de(sh("whisper-cli", "-m", MODELE, "-f", bout, "-l", "fr",
                               "-ml", "1", "-sow", "-np", "-t", "8"), a)
        finally:
            if os.path.exists(bout):
                os.remove(bout)
    return mots


def recaler(texte, reference):
    """Recopie les horodatages de `reference` sur les mots de `texte`.

    Les deux listes disent la meme chose mais pas toujours avec les memes mots :
    privee du contexte de la phrase, la transcription par segments se trompe
    parfois. difflib apparie ce qui est commun ; les mots restes seuls sont
    repartis entre leurs deux voisins apparies, ce qui les garde dans le bon
    intervalle de parole.
    """
    if not reference or not texte:
        return texte
    a = [cle(w) for _, _, w in texte]
    b = [cle(w) for _, _, w in reference]
    cales = [None] * len(texte)

    # Deux garde-fous, appris sur la 018 et la 025 :
    #  - un mot isole qui coincide ne prouve rien (les articles se repetent) ;
    #    on n'ancre que sur des suites d'au moins deux mots identiques ;
    #  - si l'appariement pretend deplacer un mot de plusieurs secondes, c'est
    #    qu'il s'est trompe de passage, pas que whisper etait a ce point faux.
    #    Sur la 025, ou le bruit de cuisine fabrique 21 mots parasites, un tel
    #    appariement decalait une phrase entiere de 11 secondes.
    for i, j, n in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        if n < BLOC_MIN:
            continue
        for k in range(n):
            if abs(reference[j + k][0] - texte[i + k][0]) <= DERIVE_MAX:
                cales[i + k] = (reference[j + k][0], reference[j + k][1])

    # les ancres retenues doivent rester dans l'ordre : on garde la plus longue
    # suite croissante et on jette le reste
    brut = [i for i, v in enumerate(cales) if v is not None]
    if brut:
        garde = [brut[0]]
        for i in brut[1:]:
            if cales[i][0] >= cales[garde[-1]][0]:
                garde.append(i)
        for i in brut:
            if i not in set(garde):
                cales[i] = None

    ancres = [i for i, v in enumerate(cales) if v is not None]
    if not ancres:
        return texte
    for i in range(len(texte)):
        if cales[i] is not None:
            continue
        avant = [p for p in ancres if p < i]
        apres = [p for p in ancres if p > i]
        if avant and apres:
            g, d = avant[-1], apres[0]
            pas = (cales[d][0] - cales[g][1]) / (d - g)
            t0 = cales[g][1] + pas * (i - g)
            t1 = t0 + pas
        elif apres:                       # avant la premiere ancre
            # rien pour interpoler : on garde le rythme de whisper et on lui
            # applique la correction constatee sur l'ancre la plus proche.
            # Reinventer un rythme fixe envoyait les mots n'importe ou (18 s
            # d'erreur sur la fin de la 018).
            d = apres[0]
            ecart = cales[d][0] - texte[d][0]
            t0, t1 = texte[i][0] + ecart, texte[i][1] + ecart
        else:                             # apres la derniere ancre
            g = avant[-1]
            ecart = cales[g][0] - texte[g][0]
            t0, t1 = texte[i][0] + ecart, texte[i][1] + ecart
        cales[i] = (max(t0, 0), max(t1, t0 + 0.06))

    out, plancher = [], 0.0
    for (t0, t1), (_, _, w) in zip(cales, texte):
        t0 = max(t0, plancher)
        t1 = max(t1, t0 + 0.06)
        plancher = t0
        out.append((round(t0, 3), round(t1, 3), w))
    return out
