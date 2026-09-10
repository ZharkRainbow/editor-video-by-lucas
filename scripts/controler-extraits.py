#!/usr/bin/env python3
"""Controle des extraits decoupes : transcrit 4 s au debut et 4 s a la fin de chaque
fichier pour verifier qu'aucun ne demarre ou ne finit au milieu d'un mot."""
import json, subprocess, sys, tempfile
from pathlib import Path

SEULS = set(sys.argv[1:])  # codes a traiter, vide = tous

BASE = Path("/Users/lucasdo./Movies/CapCut/Consulting by Lucas to 16,9")
MODELE = Path.home() / ".cache/whisper-cpp/ggml-large-v3-turbo.bin"
RANG = {"prio": "1-prio", "option": "2-option", "reserve": "3-a-valider"}

def txt(f, args):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as t:
        wav = t.name
    subprocess.run(["ffmpeg", "-y", "-v", "error"] + args + ["-i", str(f), "-ar", "16000",
                    "-ac", "1", "-vn", wav], check=True)
    r = subprocess.run(["whisper-cli", "-m", str(MODELE), "-l", "fr", "-nt", wav],
                       capture_output=True, text=True)
    Path(wav).unlink(missing_ok=True)
    return " ".join(r.stdout.split())

d = json.load(open(Path(__file__).with_name("selection-gauthier-florian.json"), encoding="utf-8"))
for client in ("Gauthier", "Florian"):
    for clip in d[client]:
        code, titre, a, b, prio = clip[0], clip[1], clip[2], clip[3], clip[4]
        if SEULS and code not in SEULS:
            continue
        f = BASE / client / "_extraits-bruts" / RANG[prio] / f"{titre}.mp4"
        print(f"\n{code}  {b-a:5.1f}s  {titre}")
        print("   DEBUT >", txt(f, ["-t", "4"]))
        print("   FIN   >", txt(f, ["-sseof", "-4"]), flush=True)
print("\nTERMINE")
