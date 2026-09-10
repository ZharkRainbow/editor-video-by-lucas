#!/usr/bin/env python3
"""Decoupe les extraits bruts de la selection Gauthier/Florian pour validation.
Sortie 1080p h264 (lecture facile). Le montage final repart du 4K via les memes bornes."""
import json, subprocess, sys
from pathlib import Path

SEULS = set(sys.argv[1:])  # codes a traiter, vide = tous

BASE = Path("/Users/lucasdo./Movies/CapCut/Consulting by Lucas to 16,9")
CFG  = Path(__file__).with_name("selection-gauthier-florian.json")
MARGE_AV, MARGE_AP = 0.0, 0.0  # les bornes du JSON portent deja leur marge (affiner-bornes.py)
RANG = {"prio": "1-prio", "option": "2-option", "reserve": "3-a-valider"}

d = json.load(open(CFG, encoding="utf-8"))
for client, src in d["_sources"].items():
    src = Path(src)
    if not src.exists():
        sys.exit(f"rush introuvable : {src}")
    for sous in ("Horizontal", "Vertical"):
        (BASE / client / sous).mkdir(parents=True, exist_ok=True)
    for clip in d[client]:
        code, titre, a, b, prio = clip[0], clip[1], clip[2], clip[3], clip[4]
        segments = clip[6] if len(clip) > 6 else None
        if SEULS and code not in SEULS:
            continue
        dst = BASE / client / "_extraits-bruts" / RANG[prio]
        dst.mkdir(parents=True, exist_ok=True)
        out = dst / f"{titre}.mp4"
        deb = max(0, a - MARGE_AV)
        dur = (b + MARGE_AP) - deb
        if segments:
            # mini-cuts : on garde plusieurs morceaux et on les recolle.
            # Fondu de 40 ms de chaque cote pour qu'aucune jointure ne claque.
            n = len(segments)
            fc = []
            for i, (x, y) in enumerate(segments):
                fc.append(f"[0:v]trim=start={x:.3f}:end={y:.3f},setpts=PTS-STARTPTS,"
                          f"scale=1920:-2[v{i}]")
                fc.append(f"[0:a]atrim=start={x:.3f}:end={y:.3f},asetpts=PTS-STARTPTS,"
                          f"afade=t=in:st=0:d=0.04,"
                          f"afade=t=out:st={max(0, y - x - 0.04):.3f}:d=0.04[a{i}]")
            fc.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]")
            garde = sum(y - x for x, y in segments)
            print(f"{code:4s} {n} segments, {garde:5.1f}s gardes  {out.name}", flush=True)
            subprocess.run([
                "ffmpeg", "-y", "-v", "error", "-i", str(src),
                "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
                "-c:v", "h264_videotoolbox", "-b:v", "8M",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", str(out),
            ], check=True)
            continue
        print(f"{code:4s} {deb:7.1f} +{dur:5.1f}s  {out.name}", flush=True)
        subprocess.run([
            "ffmpeg", "-y", "-v", "error",
            "-ss", f"{deb:.3f}", "-i", str(src), "-t", f"{dur:.3f}",
            "-vf", "scale=1920:-2",
            "-c:v", "h264_videotoolbox", "-b:v", "8M",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", str(out),
        ], check=True)
print("TERMINE")
