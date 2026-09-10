"""Verifie que les captions horizontales sont bien centrees.
On echantillonne plusieurs instants par fichier et on mesure la position du
texte jaune dans le bandeau bas."""
import subprocess, sys, tempfile
from pathlib import Path

B = Path.home() / "Movies/CapCut/Consulting by Lucas to 16,9"

def centre(png, W=1920, H=1080):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", png, "-f", "rawvideo",
                        "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    if len(r) < W * H * 3:
        return None
    xs = []
    for y in range(int(H * .82), int(H * .96), 2):
        b = y * W * 3
        for x in range(0, W, 2):
            i = b + x * 3
            if r[i] > 200 and r[i + 1] > 170 and r[i + 2] < 110:
                xs.append(x)
    return (min(xs) + max(xs)) / 2 if len(xs) >= 40 else None

for client in sys.argv[1:]:
    print(f"\n===== {client}")
    for f in sorted((B / client / "Horizontal").glob("*.mp4")):
        d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                  "-of", "csv=p=0", str(f)], capture_output=True,
                                 text=True).stdout.strip())
        ecarts = []
        with tempfile.TemporaryDirectory() as t:
            for frac in (.25, .45, .65, .85):
                p = Path(t) / f"{frac}.png"
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{d*frac:.2f}",
                                "-i", str(f), "-frames:v", "1", str(p)], capture_output=True)
                c = centre(str(p))
                if c is not None:
                    ecarts.append(c - 960)
        if not ecarts:
            print(f"  ?    {f.stem[:52]}"); continue
        pire = max(ecarts, key=abs)
        print(f"  {'OK ' if abs(pire) < 40 else 'GAUCHE':7s} ecart max {pire:+7.0f} px  "
              f"({len(ecarts)} mesures)  {f.stem[:46]}", flush=True)
