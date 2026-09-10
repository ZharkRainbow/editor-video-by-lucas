#!/usr/bin/env python3
"""Repare les clips horizontaux dont les captions sont collees a gauche.

Ces fichiers ont ete incrustes avant que le centrage explicite soit ajoute a
incruster-captions.py : le texte est pose a 730 px du centre. On refait la
chaine complete pour eux seuls, sans toucher aux autres fichiers du client.

    coupe 4K -> captions centrees -> voix (debruitage + chaine v2) -> musique -34

    python3 reparer-horizontal.py Amory "Amory je cherche 5 agences pas plus" ...
"""
import json, math, re, subprocess, sys, tempfile
from pathlib import Path

RACINE = Path("/Users/lucasdo./Documents/RAIZ-Claude/OFFBOUND/CONTENU/consulting-mastermind")
RUSHS = Path("/Users/lucasdo./Downloads/Consulting Client - Mastermind Valentin Montage vidéo")
BASE = Path.home() / "Movies/CapCut/Consulting by Lucas to 16,9"
MUSIQUES = Path.home() / "Documents/Musique pour OpusClip"
SCRIPTS = Path(__file__).parent
DF = Path.home() / ".local/bin/deep-filter"
NIVEAU = -34
CHAINE = ("highpass=f=85,adeclick,equalizer=f=250:t=q:w=1.2:g=-2,"
          "deesser=i=0.7:m=0.5:f=0.4,equalizer=f=6500:t=q:w=2:g=-2.5,"
          "acompressor=threshold=-20dB:ratio=2.5:attack=10:release=200:makeup=1.5,"
          "alimiter=limit=0.93,loudnorm=I=-14:TP=-1.5:LRA=11")
MARQUEUR = f"debruit25 + voix v2 + musique {NIVEAU}"


def sh(c):
    return subprocess.run(c, capture_output=True, text=True)


def lufs(f):
    m = re.search(r"Input Integrated:\s*(-?[\d.]+)",
                  sh(["ffmpeg", "-i", str(f), "-af", "loudnorm=print_format=summary",
                      "-f", "null", "-"]).stderr)
    return float(m.group(1)) if m else None


client = sys.argv[1]
cibles = sys.argv[2:]
rush = RUSHS / f"Consulting {client}.mp4"
tc = {t: (a, b) for t, a, b, *_ in json.loads((RACINE / "clips-timecodes.json").read_text("utf-8"))[client]}
pistes = sorted(MUSIQUES.glob("*Musique calme pour montage/*.mp3"))
ordre = sorted((BASE / client / "Horizontal").glob("*.mp4"))

for titre in cibles:
    dst = BASE / client / "Horizontal" / f"{titre}.mp4"
    if titre not in tc or not dst.exists():
        print(f"  INCONNU {titre}"); continue
    a, b = tc[titre]
    piste = pistes[ordre.index(dst) % len(pistes)]

    # 1. coupe + captions centrees, en une passe depuis la 4K
    r = sh(["python3", str(SCRIPTS / "refaire-horizontal-consulting.py"), titre])
    if "-> ok" not in r.stdout:
        print(f"  ECHEC montage {titre} : {r.stdout.strip()[-120:]}"); continue

    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        # 2. voix : debruitage puis chaine v2, depuis le rush
        brut = tmp / "b.wav"
        sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-i", str(rush),
            "-t", f"{b-a:.3f}", "-vn", "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(brut)])
        sh([str(DF), "-a", "25", "-D", "-o", str(tmp / "df"), str(brut)])
        prop = tmp / "df" / "b.wav"
        if not prop.exists():
            print(f"  ECHEC DEBRUITAGE {titre}, rien ecrit"); continue
        voix = tmp / "v.wav"
        sh(["ffmpeg", "-y", "-v", "error", "-i", str(prop), "-af", CHAINE, "-ar", "48000", str(voix)])

        # 3. lit musical au gain fixe
        d = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "csv=p=0", str(dst)]).stdout.strip())
        gain = NIVEAU - lufs(piste)
        lit = tmp / "m.wav"
        sh(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", str(piste), "-t", f"{d:.3f}",
            "-af", f"volume={gain:.2f}dB,afade=t=in:st=0:d=1.5,"
                   f"afade=t=out:st={max(0, d-2):.3f}:d=2", "-ar", "48000", "-ac", "2", str(lit)])

        out = tmp / dst.name
        sh(["ffmpeg", "-y", "-v", "error", "-i", str(dst), "-i", str(voix), "-i", str(lit),
            "-filter_complex",
            "[1:a]aformat=channel_layouts=stereo[v];[2:a]aformat=channel_layouts=stereo[m];"
            "[v][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[o]",
            "-map", "0:v:0", "-map", "[o]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-metadata", f"comment={MARQUEUR}",
            "-movflags", "+faststart", str(out)])
        if not out.exists():
            print(f"  ECHEC remux {titre}"); continue
        out.replace(dst)
    print(f"  OK  {piste.stem[:24]:26s} -> {lufs(dst):.1f} LUFS   {titre[:44]}", flush=True)
print("TERMINE")
