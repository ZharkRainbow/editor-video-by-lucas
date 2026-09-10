#!/usr/bin/env python3
"""Signale les mots qui n'existent pas en francais dans une transcription.

Whisper ne massacre pas seulement les noms propres et les anglicismes : il
ecorche aussi des mots courants ("piege" devenu "ptege" sur la 017). Aucune
liste de corrections ne peut anticiper ca. La seule parade est un dictionnaire :
tout mot inconnu est signale, on relit et on decide.

Le jargon d'Offbound et les noms propres sont evidemment inconnus du
dictionnaire : ils sont dans la liste blanche ci-dessous.

usage : verifier-orthographe.py transcript.txt [...]
"""
import os, re, sys
from spellchecker import SpellChecker

LIGNE = re.compile(r"\[(\d\d):(\d\d):(\d\d\.\d+)\s*-->.*?\]\s*(.*)")

# jargon, marques et anglicismes assumes : connus de nous, pas du dictionnaire
BLANCHE = {
    "offbound", "offgroup", "thomy", "budapest", "malt", "skool", "linkedin",
    "instagram", "tiktok", "youtube", "chatgpt", "saas", "mcp", "claude",
    "kifli", "tupperware", "osmo", "dji", "spacex", "yomi", "denzel",
    "closing", "closer", "setting", "setter", "branding", "networking",
    "scaling", "consulting", "coaching", "marketing", "upsell", "upsells",
    "lead", "leads", "hook", "hooks", "ads", "cash", "business", "cool",
    "mindset", "pitch", "pitches", "propales", "propale", "mastermind",
    "infopreneur", "infopreneurs", "lifestyle", "brand", "podcast",
    "podcasts", "csm", "ltv", "b2b", "b2c", "cta", "roi", "kpi", "smart",
    "chill", "clap", "team", "one", "to", "is", "key", "cold", "email",
    "emails", "personal", "focus", "insta", "reel", "reels", "story",
    "stories", "content", "growth", "sales", "delivery", "design", "dm",
    "dms", "lock", "in", "vas", "genre", "ouais", "bah", "hop", "boum",
    "trucs", "truc", "gars", "meuf", "taffe", "niaque", "dalle", "ok",
}


def mots_du_fichier(p):
    out = []
    for l in open(p, encoding="utf-8"):
        m = LIGNE.match(l.strip())
        if not m:
            continue
        w = m.group(4).strip()
        if w:
            out.append((float(m.group(1)) * 3600 + float(m.group(2)) * 60
                        + float(m.group(3)), w))
    return out


def controler(p, sp):
    inconnus = {}
    for t, brut in mots_du_fichier(p):
        for mot in re.findall(r"[A-Za-zÀ-ÿ'’-]+", brut):
            n = mot.lower().strip("'’-")
            # les elisions et les mots composes se verifient morceau par morceau
            morceaux = [x for x in re.split(r"['’-]", n) if len(x) > 1]
            for x in morceaux or ([n] if len(n) > 1 else []):
                if x in BLANCHE or len(x) < 3:
                    continue
                if x not in sp:
                    inconnus.setdefault(x, t)
    return inconnus


if __name__ == "__main__":
    sp = SpellChecker(language="fr")
    total = 0
    for p in sys.argv[1:]:
        inc = controler(p, sp)
        if not inc:
            continue
        nom = os.path.basename(p).replace(".mots-VAL-OUT-", "").replace(".txt", "")
        print(f"  {nom[:46]}")
        for mot, t in sorted(inc.items(), key=lambda kv: kv[1]):
            print(f"      {t:6.1f}s  {mot}")
            total += 1
    print(f"\n  {total} mots inconnus du dictionnaire francais")
