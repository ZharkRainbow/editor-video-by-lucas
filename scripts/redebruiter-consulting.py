#!/usr/bin/env python3
"""Refait l'audio des reels de consulting AVEC le debruitage, qui avait ete perdu.

Pourquoi repartir du rush : la musique est deja mixee dans les fichiers livres.
Passer DeepFilterNet par-dessus la detruirait, il traite tout ce qui n'est pas
de la parole comme du bruit. On reconstruit donc la chaine complete depuis le
rush 4K, et on remet la meme piste musicale qu'a l'origine.

  rush[a,b] -> deep-filter -a 25 -> chaine voix v2 -> musique -40 LUFS -> remux

La video n'est jamais reencodee (-c:v copy) : titres, captions et cadrage sont
preserves tels quels. Le decalage rush/fichier est mesure par correlation
d'enveloppe et compense clip par clip.

    python3 redebruiter-consulting.py Amory Baptiste Jordy
"""
import array, json, math, re, subprocess, sys, tempfile
from pathlib import Path

RUSHS = Path("/Users/lucasdo./Downloads/Consulting Client - Mastermind Valentin Montage vidéo")
BASE = Path("/Users/lucasdo./Movies/CapCut/Consulting by Lucas to 16,9")
MUSIQUES = Path("/Users/lucasdo./Documents/Musique pour OpusClip/*Musique calme pour montage")
TIMECODES = Path("/Users/lucasdo./Documents/RAIZ-Claude/OFFBOUND/CONTENU/"
                 "consulting-mastermind/clips-timecodes.json")
DF = Path.home() / ".local/bin/deep-filter"
ATTEN = 25
NIVEAU_MUSIQUE = -40
MARQUEUR = "debruit25 + voix v2"      # sans musique : elle sera reposee apres validation

# chaine voix v2, identique a affiner-voix.py. Pas de boost de presence a 4 kHz :
# il amplifiait exactement la bande des bruits de bouche.
CHAINE = ("highpass=f=85,"
          "adeclick,"
          "equalizer=f=250:t=q:w=1.2:g=-2,"
          "deesser=i=0.7:m=0.5:f=0.4,"
          "equalizer=f=6500:t=q:w=2:g=-2.5,"
          "acompressor=threshold=-20dB:ratio=2.5:attack=10:release=200:makeup=1.5,"
          "alimiter=limit=0.93,"
          "loudnorm=I=-14:TP=-1.5:LRA=11")

# Attribution d'origine, relevee dans le journal d'execution d'ajouter-musique.py.
# Rotation sur les 8 pistes calmes, par ordre alphabetique des clips.
ROTATION = ["Best insta", "Convergence", "IMPXSTR - GALAXY!", "Let it burn",
            "Monuments", "She Will Instrumental Slowed", "falling forwards",
            "ridgeclub - do i clench my fists_"]


def sh(c):
    return subprocess.run(c, capture_output=True, text=True)


def duree(f):
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "csv=p=0", str(f)])
    return float(r.stdout.strip())


def enveloppe(src, ss=None, t=None, pas=0.01):
    cmd = ["ffmpeg", "-v", "error"]
    if ss is not None:
        cmd += ["-ss", f"{ss:.3f}"]
    cmd += ["-i", str(src)]
    if t is not None:
        cmd += ["-t", f"{t:.3f}"]
    cmd += ["-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"]
    b = subprocess.run(cmd, capture_output=True).stdout
    a = array.array("h"); a.frombytes(b[:len(b) // 2 * 2])
    n = int(8000 * pas); e = []
    for i in range(0, len(a) - n, n):
        e.append(math.sqrt(sum(float(x) * x for x in a[i:i + n]) / n))
    m = sum(e) / max(1, len(e))
    return [x - m for x in e]


def decalage(rush, debut, clip, d):
    """Decalage en secondes entre le rush a `debut` et l'audio du clip."""
    a, b = enveloppe(rush, debut, d), enveloppe(clip)
    L = min(len(a), len(b)) - 120
    if L <= 0:
        return 0.0
    best = (0, -1e18)
    for k in range(-50, 51):
        s = sum(a[i + 50] * b[i + 50 + k] for i in range(0, L, 3))
        if s > best[1]:
            best = (k, s)
    return best[0] / 100.0


def traiter(clip: Path, rush: Path, a: float, piste: Path):
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format_tags=comment",
            "-of", "csv=p=0", str(clip)])
    marque = r.stdout.strip()
    # "debruit25 + voix v2" est un prefixe de l'ancien marqueur avec musique :
    # un simple 'in' laissait passer les fichiers qui portent encore un lit musical.
    if marque == MARQUEUR or (MARQUEUR in marque and "musique" not in marque):
        return "deja fait"
    d = duree(clip)
    dec = decalage(rush, a, clip, d)
    debut = a - dec

    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        brut = tmp / "brut.wav"
        sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{debut:.3f}", "-i", str(rush),
            "-t", f"{d:.3f}", "-vn", "-ar", "48000", "-ac", "1",
            "-c:a", "pcm_s16le", str(brut)])
        if not brut.exists():
            return "echec extraction"

        sh([str(DF), "-a", str(ATTEN), "-D", "-o", str(tmp / "df"), str(brut)])
        prop = tmp / "df" / "brut.wav"
        if not prop.exists():
            return "ECHEC DEBRUITAGE, rien ecrit"   # jamais en silence

        voix = tmp / "voix.wav"
        sh(["ffmpeg", "-y", "-v", "error", "-i", str(prop), "-af", CHAINE,
            "-ar", "48000", str(voix)])
        if not voix.exists():
            return "echec chaine voix"

        if piste is None:
            # pas de lit musical : on remuxe la voix seule
            out = tmp / ("n" + clip.suffix)
            sh(["ffmpeg", "-y", "-v", "error", "-i", str(clip), "-i", str(voix),
                "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-shortest",
                "-metadata", f"comment={MARQUEUR}",
                "-movflags", "+faststart", str(out)])
            if not out.exists():
                return "echec remux"
            out.replace(clip)
            r = sh(["ffmpeg", "-i", str(clip), "-af", "loudnorm=print_format=summary",
                    "-f", "null", "-"])
            m = re.search(r"Input Integrated:\s*(-?[\d.]+)", r.stderr)
            return f"decalage {dec*1000:+5.0f} ms · sans musique -> {m.group(1) if m else '?'} LUFS"

        r = sh(["ffmpeg", "-i", str(piste), "-af", "loudnorm=print_format=summary",
                "-f", "null", "-"])
        m = re.search(r"Input Integrated:\s*(-?[\d.]+)", r.stderr)
        gain = NIVEAU_MUSIQUE - float(m.group(1)) if m else -20.0
        lit = tmp / "lit.wav"
        sh(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", str(piste),
            "-t", f"{d:.3f}",
            "-af", f"volume={gain:.2f}dB,afade=t=in:st=0:d=1.5,"
                   f"afade=t=out:st={max(0, d-2):.3f}:d=2",
            "-ar", "48000", "-ac", "2", str(lit)])
        if not lit.exists():
            return "echec musique"

        out = tmp / ("n" + clip.suffix)
        sh(["ffmpeg", "-y", "-v", "error", "-i", str(clip), "-i", str(voix), "-i", str(lit),
            "-filter_complex",
            "[1:a]aformat=channel_layouts=stereo[v];"
            "[2:a]aformat=channel_layouts=stereo[m];"
            "[v][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]",
            "-map", "0:v:0", "-map", "[a]", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-shortest",
            "-metadata", f"comment={MARQUEUR}",
            "-movflags", "+faststart", str(out)])
        if not out.exists():
            return "echec remux"
        out.replace(clip)

    r = sh(["ffmpeg", "-i", str(clip), "-af", "loudnorm=print_format=summary",
            "-f", "null", "-"])
    m = re.search(r"Input Integrated:\s*(-?[\d.]+)", r.stderr)
    return f"decalage {dec*1000:+5.0f} ms · {piste.stem[:24]:26s} -> {m.group(1) if m else '?'} LUFS"


def main():
    tc = json.load(open(TIMECODES, encoding="utf-8"))
    pistes = {p.stem: p for p in MUSIQUES.parent.glob(MUSIQUES.name + "/*.mp3")}
    manquantes = [n for n in ROTATION if n not in pistes]
    if manquantes:
        sys.exit(f"pistes introuvables : {manquantes}")

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    avec_musique = "--avec-musique" in sys.argv
    for client in args:
        rush = RUSHS / f"Consulting {client}.mp4"
        if not rush.exists():
            sys.exit(f"rush absent : {rush}")
        clips = sorted(tc[client], key=lambda x: x[0])   # meme tri que sorted() sur les .mp4
        print(f"\n===== {client}")
        for i, (titre, a, _b) in enumerate(clips):
            for fmt in ("Horizontal", "Vertical"):
                f = BASE / client / fmt / f"{titre}.mp4"
                if not f.exists():
                    print(f"  ABSENT {fmt}/{titre}")
                    continue
                piste = pistes[ROTATION[i % len(ROTATION)]] if avec_musique else None
                print(f"  {fmt[0]} {titre[:44]:46s} {traiter(f, rush, a, piste)}", flush=True)
    print("\nTERMINE")


main()
