#!/usr/bin/env python3
"""Mastering audio d'un lot de clips : debruitage DeepFilterNet puis
normalisation de loudness en deux passes. La video n'est jamais reencodee.

Cible Instagram / TikTok : -14 LUFS, true peak -1,5 dBTP.
Le debruitage est volontairement limite a 25 dB : au-dela, l'ambiance de la
salle disparait et les voix sonnent artificielles.

    python3 masteriser-audio.py <dossier> [<dossier> ...]
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DF = Path.home() / ".local/bin/deep-filter"
CIBLE = dict(I=-14, TP=-1.5, LRA=11)
ATTEN = 25


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def masteriser(src: Path):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        brut = tmp / "brut.wav"
        sh(["ffmpeg", "-y", "-i", str(src), "-vn", "-ar", "48000", "-ac", "1",
            "-c:a", "pcm_s16le", str(brut)])
        if not brut.exists():
            return "pas d'audio"
        sh([str(DF), "-a", str(ATTEN), "-D", "-o", str(tmp / "df"), str(brut)])
        prop = tmp / "df" / "brut.wav"
        if not prop.exists():
            prop = brut

        # passe 1 : mesure
        f = (f"loudnorm=I={CIBLE['I']}:TP={CIBLE['TP']}:LRA={CIBLE['LRA']}"
             ":print_format=json")
        r = sh(["ffmpeg", "-i", str(prop), "-af", f, "-f", "null", "-"])
        m = re.search(r"\{[^{}]*input_i[^{}]*\}", r.stderr, re.S)
        if m:
            d = json.loads(m.group(0))
            f2 = (f"loudnorm=I={CIBLE['I']}:TP={CIBLE['TP']}:LRA={CIBLE['LRA']}"
                  f":measured_I={d['input_i']}:measured_TP={d['input_tp']}"
                  f":measured_LRA={d['input_lra']}:measured_thresh={d['input_thresh']}"
                  f":offset={d['target_offset']}:linear=true")
        else:
            f2 = f.replace(":print_format=json", "")

        fini = tmp / "fini.wav"
        sh(["ffmpeg", "-y", "-i", str(prop), "-af", f2, "-ar", "48000", str(fini)])
        if not fini.exists():
            return "echec loudnorm"

        out = tmp / ("m" + src.suffix)
        r = sh(["ffmpeg", "-y", "-i", str(src), "-i", str(fini),
                "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-shortest",
                "-movflags", "+faststart", str(out)])
        if not out.exists():
            return "echec remux"
        shutil.move(str(out), str(src))

    r = sh(["ffmpeg", "-i", str(src), "-af", "loudnorm=print_format=summary",
            "-f", "null", "-"])
    i = re.search(r"Input Integrated:\s*(-?[\d.]+)", r.stderr)
    t = re.search(r"Input True Peak:\s*(-?[\d.]+)", r.stderr)
    return f"{i.group(1)} LUFS / {t.group(1)} dBTP" if i and t else "ok"


if __name__ == "__main__":
    fichiers = []
    for a in sys.argv[1:]:
        p = Path(a)
        fichiers += sorted(p.rglob("*.mp4")) if p.is_dir() else [p]
    for f in fichiers:
        print(f"{f.parent.parent.name:10s} {f.name[:52]:54s} -> {masteriser(f)}",
              flush=True)
    print("TERMINE")
