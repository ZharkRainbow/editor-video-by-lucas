#!/usr/bin/env python3
"""Recoupe le debut d'un clip pour qu'il ouvre sur son hook, et refait tout.

Opus Clip coupe sur le silence, pas sur l'intention : ses bornes laissent
souvent une seconde de mou avant le vrai depart ("Magnifique.", une question
de relance, une phrase d'amorce plate). Ce script deplace la borne de debut
puis regenere la chaine entiere, sans quoi les captions resteraient calees sur
l'ancienne duree.

    coupe 4K -> captions -> voix (debruitage + v2) -> musique -34, H et V

    python3 recouper-debut.py <Client> <titre> <nouveau_debut>
"""
import json, re, subprocess, sys, tempfile
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

client, titre, nouveau = sys.argv[1], sys.argv[2], float(sys.argv[3])


def sh(c):
    return subprocess.run(c, capture_output=True, text=True)


def lufs(f):
    m = re.search(r"Input Integrated:\s*(-?[\d.]+)",
                  sh(["ffmpeg", "-i", str(f), "-af", "loudnorm=print_format=summary",
                      "-f", "null", "-"]).stderr)
    return float(m.group(1)) if m else None


# 1. nouvelle borne dans le referentiel
p = RACINE / "clips-timecodes.json"
tc = json.load(open(p, encoding="utf-8"))
ancien = None
for clip in tc[client]:
    if clip[0] == titre:
        ancien, clip[1] = clip[1], nouveau
if ancien is None:
    sys.exit(f"titre absent du referentiel : {titre}")
json.dump(tc, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
fin = [c[2] for c in tc[client] if c[0] == titre][0]
print(f"{titre}\n  debut {ancien:.2f} -> {nouveau:.2f}  ({nouveau-ancien:+.2f}s), duree {fin-nouveau:.1f}s")

# 2. les captions doivent etre refaites : elles sont calees sur l'ancienne duree
for d in ("_captions", "_captions-long"):
    srt = BASE / client / "Horizontal" / d / f"{titre}.srt"
    if srt.exists():
        sh(["osascript", "-e",
            f'tell application "Finder" to delete POSIX file "{srt}"'])
print("  captions mises a la corbeille")

# 3. horizontal brut, puis captions, puis horizontal final
sh(["python3", str(SCRIPTS / "refaire-horizontal-consulting.py"), titre])
sh(["python3", str(SCRIPTS / "faire-captions.py"), str(BASE / client / "Horizontal")])
sh(["python3", str(SCRIPTS / "faire-captions.py"), "--long", str(BASE / client / "Horizontal")])
r = sh(["python3", str(SCRIPTS / "refaire-horizontal-consulting.py"), titre])
print(f"  horizontal : {r.stdout.strip().splitlines()[0][-30:] if r.stdout.strip() else 'echec'}")

# 4. vertical
r = sh(["python3", str(SCRIPTS / "monter-vertical-consulting.py"), client, titre])
print(f"  vertical   : {r.stdout.strip().splitlines()[0][-30:] if r.stdout.strip() else 'echec'}")

# 5. son identique sur les deux formats
rush = RUSHS / f"Consulting {client}.mp4"
pistes = sorted(MUSIQUES.glob("*Musique calme pour montage/*.mp3"))
for fmt in ("Horizontal", "Vertical"):
    dst = BASE / client / fmt / f"{titre}.mp4"
    if not dst.exists():
        print(f"  {fmt} absent"); continue
    ordre = sorted((BASE / client / fmt).glob("*.mp4"))
    piste = pistes[ordre.index(dst) % len(pistes)]
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        brut = tmp / "b.wav"
        sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{nouveau:.3f}", "-i", str(rush),
            "-t", f"{fin-nouveau:.3f}", "-vn", "-ar", "48000", "-ac", "1",
            "-c:a", "pcm_s16le", str(brut)])
        sh([str(DF), "-a", "25", "-D", "-o", str(tmp / "df"), str(brut)])
        prop = tmp / "df" / "b.wav"
        if not prop.exists():
            print(f"  {fmt} ECHEC DEBRUITAGE, rien ecrit"); continue
        voix = tmp / "v.wav"
        sh(["ffmpeg", "-y", "-v", "error", "-i", str(prop), "-af", CHAINE, "-ar", "48000", str(voix)])
        d = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "csv=p=0", str(dst)]).stdout.strip())
        lit = tmp / "m.wav"
        sh(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", str(piste), "-t", f"{d:.3f}",
            "-af", f"volume={NIVEAU - lufs(piste):.2f}dB,afade=t=in:st=0:d=1.5,"
                   f"afade=t=out:st={max(0, d-2):.3f}:d=2", "-ar", "48000", "-ac", "2", str(lit)])
        out = tmp / dst.name
        sh(["ffmpeg", "-y", "-v", "error", "-i", str(dst), "-i", str(voix), "-i", str(lit),
            "-filter_complex",
            "[1:a]aformat=channel_layouts=stereo[v];[2:a]aformat=channel_layouts=stereo[m];"
            "[v][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[o]",
            "-map", "0:v:0", "-map", "[o]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-metadata", f"comment={MARQUEUR}",
            "-movflags", "+faststart", str(out)])
        if out.exists():
            out.replace(dst)
    print(f"  {fmt[0]} {piste.stem[:22]:24s} {d:5.1f}s -> {lufs(dst):.1f} LUFS")
print("TERMINE")
