"""Transcrit les 4 premieres secondes de chaque clip pour reperer les
demarrages mous : accuse de reception, relance, phrase d'amorce plate."""
import json, subprocess, tempfile, sys
from pathlib import Path
MOD = Path.home()/".cache/whisper-cpp/ggml-large-v3-turbo.bin"
B = Path.home()/"Movies/CapCut/Consulting by Lucas to 16,9"
for client in sys.argv[1:]:
    print(f"\n===== {client}")
    for f in sorted((B/client/"Horizontal").glob("*.mp4")):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as t: w=t.name
        subprocess.run(["ffmpeg","-y","-v","error","-i",str(f),"-t","4.5","-ar","16000",
                        "-ac","1","-vn",w],check=True)
        r=subprocess.run(["whisper-cli","-m",str(MOD),"-l","fr","-nt",w],
                         capture_output=True,text=True)
        Path(w).unlink(missing_ok=True)
        print(f"  {f.stem[:44]:46s} | {' '.join(r.stdout.split())[:95]}", flush=True)
