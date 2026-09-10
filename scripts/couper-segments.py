#!/usr/bin/env python3
"""
Retire des passages a l'interieur d'une video et recolle le reste.
usage : couper-segments.py entree.mp4 sortie.mp4 "12.4-18.9,45.0-47.2"
Les intervalles sont les passages A SUPPRIMER, en secondes.
"""
import subprocess, sys, os

def duree(p):
    return float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","csv=p=0",p], capture_output=True, text=True).stdout.strip())

def segments_gardes(dur, coupes):
    coupes = sorted(coupes)
    # fusionne les coupes qui se chevauchent
    fus = []
    for a,b in coupes:
        if fus and a <= fus[-1][1] + 0.05:
            fus[-1] = (fus[-1][0], max(fus[-1][1], b))
        else:
            fus.append((a,b))
    gardes, pos = [], 0.0
    for a,b in fus:
        if a - pos > 0.25:
            gardes.append((pos, a))
        pos = b
    if dur - pos > 0.25:
        gardes.append((pos, dur))
    return gardes

def main():
    src, dst, spec = sys.argv[1], sys.argv[2], sys.argv[3]
    coupes = []
    if spec.strip():
        for part in spec.split(","):
            a,b = part.split("-")
            coupes.append((float(a), float(b)))
    dur = duree(src)
    seg = segments_gardes(dur, coupes)
    if len(seg) == 1 and abs(seg[0][0]) < 0.01 and abs(seg[0][1]-dur) < 0.01:
        print("aucune coupe, copie simple"); subprocess.run(["cp", src, dst]); return
    # trim + concat en une passe, sans fichier intermediaire
    fc, vlab, alab = [], [], []
    for i,(a,b) in enumerate(seg):
        fc.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{i}]")
        fc.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS[a{i}]")
        vlab.append(f"[v{i}]"); alab.append(f"[a{i}]")
    inter = "".join(f"{v}{a}" for v,a in zip(vlab,alab))
    fc.append(f"{inter}concat=n={len(seg)}:v=1:a=1[vo][ao]")
    cmd = ["ffmpeg","-nostdin","-v","error","-y","-i",src,
           "-filter_complex",";".join(fc),"-map","[vo]","-map","[ao]",
           "-c:v","h264_videotoolbox","-b:v","16M","-profile:v","high",
           "-c:a","aac","-b:a","192k","-ar","48000","-movflags","+faststart",dst]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("ECHEC:", r.stderr[:400]); sys.exit(1)
    nd = duree(dst)
    print(f"{os.path.basename(src)} : {dur:.1f}s -> {nd:.1f}s  ({len(seg)} segments recolles, -{dur-nd:.1f}s)")

if __name__ == "__main__":
    main()
