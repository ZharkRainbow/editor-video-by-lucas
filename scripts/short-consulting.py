# -*- coding: utf-8 -*-
"""Monte les shorts d'un consulting client : split screen, titre, sous-titres, musique.

Chaine complete pour un dossier de rushes deja decoupes en 16:9.

  1. transcription mot a mot (whisper-cli), corrigee par `sous-titres.py`
  2. detection des deux visages pour caler le recadrage du split screen
  3. composition HyperFrames rendue en vertical 1080x1920 et en horizontal 1920x1080
  4. musique calee 16 LU sous la voix, uniquement sur le vertical

Deux choix qui ne sont pas negociables et qui viennent de mesures, pas de gout.

  le titre n'a aucune animation  et les sous-titres non plus. Un `filter: blur`
      laisse actif apres son animation maintient un calque de composition, et le
      texte vibre alors d'un pixel entre les images. Mesure : 1,88 px d'amplitude
      avec, 0,01 px sans.

  le recadrage vient de la detection de visage  et pas d'une valeur en dur. Le
      classifieur frontal ne voit pas le client, qui est de profil ; il faut le
      classifieur de profil, plus l'image miroir, plus un filtre par taille pour
      ne pas se faire piloter par le public en arriere-plan.

usage : short-consulting.py <dossier_rushes> <nom_personne> <dossier_sortie> [titres.json]
"""
import json, os, re, shutil, subprocess, sys

RACINE = os.path.expanduser("~/Documents/RAIZ-Claude/OFFBOUND/APPS/video-reels")
sys.path.insert(0, os.path.join(RACINE, "scripts"))
import importlib.util
_spec = importlib.util.spec_from_file_location("st", os.path.join(RACINE, "scripts", "sous-titres.py"))
st = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(st)

MODELE = os.path.expanduser("~/.cache/whisper-cpp/ggml-large-v3-turbo.bin")
POLICES = os.path.expanduser("~/Library/Fonts")
MUSIQUES = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/Documents/Musique pour OpusClip/*Musique calme pour montage")
PROJET = "/tmp/hf-short"
CW, CH = 756, 672            # fenetre de recadrage, ratio d'une demi-image 9:16
TITRE_FIN = 4.5
BLEU, JAUNE = "#2322E0", "#FFD600"


# ---------------------------------------------------------------- transcription
def transcrire(video, cache):
    os.makedirs(cache, exist_ok=True)
    base = os.path.join(cache, os.path.splitext(os.path.basename(video))[0])
    if not os.path.exists(base + ".json"):
        wav = base + ".wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-ar", "16000",
                        "-ac", "1", "-c:a", "pcm_s16le", wav], check=True)
        subprocess.run(["whisper-cli", "-m", MODELE, "-f", wav, "-l", "fr", "-np",
                        "-ml", "1", "-sow", "-oj", "-of", base],
                       check=True, capture_output=True)
        os.remove(wav)
    return base + ".json"


# ---------------------------------------------------------------- cadrage
def cadrage(video):
    """Position des deux visages -> fenetres de recadrage haut (Valentin) et bas (client)."""
    import cv2, statistics as stat
    front = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    profil = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
    cap = cv2.VideoCapture(video)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); W = int(cap.get(3)); H = int(cap.get(4))
    gauche, droite = [], []
    for k in range(20):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * (k + 0.5) / 20))
        ok, img = cap.read()
        if not ok:
            continue
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        vus = []
        for (x, y, w, h) in front.detectMultiScale(g, 1.10, 6, minSize=(110, 110)):
            vus.append((x + w // 2, y + h // 2, w))
        for (x, y, w, h) in profil.detectMultiScale(g, 1.08, 5, minSize=(110, 110)):
            vus.append((x + w // 2, y + h // 2, w))
        for (x, y, w, h) in profil.detectMultiScale(cv2.flip(g, 1), 1.08, 5, minSize=(110, 110)):
            vus.append((W - (x + w // 2), y + h // 2, w))
        # les deux interlocuteurs sont au premier plan : leur visage est le plus
        # grand de leur moitie. Le public du fond est plus petit.
        for cote, seau in ((0, gauche), (1, droite)):
            cand = [v for v in vus if (v[0] < W / 2) == (cote == 0)]
            if cand:
                gros = max(cand, key=lambda v: v[2])
                if gros[2] >= 130:
                    seau.append((gros[0], gros[1]))
    cap.release()

    def med(pts, dx, dy):
        return ((int(stat.median(p[0] for p in pts)), int(stat.median(p[1] for p in pts)))
                if len(pts) >= 3 else (dx, dy))

    gx, gy = med(gauche, 675, 297)
    dx, dy = med(droite, 1355, 350)

    def fenetre(cx, cy):
        # le visage se place au tiers haut de la fenetre
        return (max(0, min(W - CW, cx - CW // 2)), max(0, min(H - CH, cy - CH // 3)))

    return dict(haut=fenetre(dx, dy), bas=fenetre(gx, gy), taille=(W, H))


# ---------------------------------------------------------------- composition
def corps_titre(titre, large_max):
    """Le titre tient toujours sur une ligne et n'occupe jamais toute la largeur."""
    from PIL import ImageFont, ImageDraw, Image
    d = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    for taille in range(56, 23, -1):
        f = ImageFont.truetype(os.path.join(POLICES, "ZTNature-Black.otf"), taille)
        if d.textlength(titre, font=f) + 40 <= large_max:
            return taille
    return 24


def corps_sub(subs, large_max, depart=50):
    from PIL import ImageFont, ImageDraw, Image
    d = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    plus_long = max((t for _, _, t in subs), key=len)
    for taille in range(depart, 23, -1):
        f = ImageFont.truetype(os.path.join(POLICES, "ZTNature-MediumItalic.otf"), taille)
        if d.textlength(plus_long, font=f) + 60 <= large_max:
            return taille
    return 24


def composition(video_fond, subs, titre, W, H, joint, duree):
    """Ecrit index.html. Aucune animation : ni sur le titre, ni sur les sous-titres."""
    import html as H_
    t_titre = corps_titre(titre, int(W * 0.83))
    t_sub = corps_sub(subs, int(W * 0.90), depart=int(W / 24))
    clips = [f'  <div id="titre" class="clip zone-titre" data-start="0" data-duration="{TITRE_FIN}">'
             f'<div class="surlignage"><div class="mots-titre">{H_.escape(titre)}</div></div></div>']
    for i, (a, b, t) in enumerate(subs):
        clips.append(f'  <div class="clip zone-sub" data-start="{a:.2f}" '
                     f'data-duration="{max(b - a, 0.25):.2f}"><div class="mots-sub">'
                     f'{H_.escape(t)}</div></div>')
    return f'''<!doctype html>
<html lang="fr"><head><meta charset="UTF-8" />
<meta name="viewport" content="width={W}, height={H}" />
<title>Short consulting</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
@font-face {{ font-family:"ZT Nature"; font-weight:900; src:url("assets/ZTNature-Black.otf") format("opentype"); }}
@font-face {{ font-family:"ZT Nature"; font-weight:500; font-style:italic; src:url("assets/ZTNature-MediumItalic.otf") format("opentype"); }}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;overflow:hidden;background:#000}}
#root{{position:relative;width:{W}px;height:{H}px;overflow:hidden}}
#fond{{position:absolute;inset:0;width:{W}px;height:{H}px;object-fit:cover}}
.zone-sub{{position:absolute;left:0;right:0;top:{joint - 170}px;height:100px;display:flex;align-items:flex-end;justify-content:center}}
.mots-sub{{font-family:"ZT Nature",sans-serif;font-weight:500;font-style:italic;font-size:{t_sub}px;
  color:{JAUNE};white-space:nowrap;letter-spacing:-0.005em;
  text-shadow:0 3px 10px rgba(0,0,0,.75), 0 0 3px rgba(0,0,0,.9)}}
.zone-titre{{position:absolute;left:0;right:0;top:{joint - 100}px;height:200px;display:flex;align-items:center;justify-content:center}}
.surlignage{{background:{BLEU};border-radius:9px;padding:12px 20px 16px;display:flex;align-items:center;justify-content:center}}
.mots-titre{{font-family:"ZT Nature",sans-serif;font-weight:900;font-size:{t_titre}px;color:#fff;white-space:nowrap;letter-spacing:-0.015em;line-height:1.05}}
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-width="{W}" data-height="{H}" data-duration="{duree:.2f}">
  <video id="fond" src="assets/{os.path.basename(video_fond)}" data-start="0" data-duration="{duree:.2f}" muted playsinline></video>
  <audio id="son" src="assets/{os.path.basename(video_fond)}" data-start="0" data-duration="{duree:.2f}"></audio>
{chr(10).join(clips)}
</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
tl.to({{}}, {{ duration: {duree:.2f} }});
window.__timelines["main"] = tl;
</script></body></html>
'''


def rendre(video_fond, subs, titre, W, H, joint, duree, sortie):
    shutil.rmtree(PROJET, ignore_errors=True)
    subprocess.run(["npx", "--yes", "hyperframes", "init", os.path.basename(PROJET),
                    "--non-interactive", "--example=blank"],
                   cwd=os.path.dirname(PROJET), check=True, capture_output=True)
    os.makedirs(os.path.join(PROJET, "assets"), exist_ok=True)
    shutil.copy(video_fond, os.path.join(PROJET, "assets"))
    for p in ("ZTNature-Black.otf", "ZTNature-MediumItalic.otf"):
        shutil.copy(os.path.join(POLICES, p), os.path.join(PROJET, "assets"))
    open(os.path.join(PROJET, "index.html"), "w", encoding="utf-8").write(
        composition(video_fond, subs, titre, W, H, joint, duree))
    r = subprocess.run(["npx", "--yes", "hyperframes", "render", "--quality", "high",
                        "--output", sortie], cwd=PROJET, capture_output=True, text=True)
    if not (os.path.exists(sortie) and os.path.getsize(sortie) > 100000):
        raise SystemExit(f"rendu echoue pour {sortie}\n{r.stdout[-800:]}{r.stderr[-800:]}")


# ---------------------------------------------------------------- musique
def poser_musique(video, sortie, ecart=16.0):
    import glob, random
    pistes = sorted(glob.glob(os.path.join(MUSIQUES, "*.mp3")))
    if not pistes:
        shutil.copy(video, sortie); return None
    # choix stable : la meme video recevra toujours la meme piste
    piste = pistes[abs(hash(os.path.basename(video))) % len(pistes)]
    r = subprocess.run([sys.executable, os.path.join(RACINE, "scripts", "caler-musique.py"),
                        video, piste, str(ecart)], capture_output=True, text=True)
    try:
        debut, gain = r.stdout.split()[:2]
        debut, gain = float(debut), float(gain)
    except Exception:
        debut, gain = 0.0, 0.06
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-ss", str(debut), "-i", piste,
                    "-filter_complex",
                    f"[1:a]volume={gain},afade=t=in:st=0:d=1.2,"
                    f"afade=t=out:st={max(duree_de(video) - 1.6, 0):.2f}:d=1.6[m];"
                    f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
                    f"alimiter=limit=0.89:level=false:latency=true[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    sortie], check=True)
    return os.path.basename(piste)


def duree_de(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", p], capture_output=True, text=True
                                ).stdout.strip().split("\n")[0])


# ---------------------------------------------------------------- chaine
def main():
    rushes, personne, sortie_racine = sys.argv[1], sys.argv[2], sys.argv[3]
    titres = json.load(open(sys.argv[4], encoding="utf-8")) if len(sys.argv) > 4 else {}
    vert = os.path.join(sortie_racine, personne, "Vertical")
    horiz = os.path.join(sortie_racine, personne, "Horizontal")
    for d in (vert, horiz):
        os.makedirs(d, exist_ok=True)
    cache = "/tmp/montage/mots"

    for f in sorted(os.listdir(rushes)):
        if not f.endswith(".mp4"):
            continue
        src = os.path.join(rushes, f)
        base = os.path.splitext(f)[0]
        titre = titres.get(base) or titres.get(f) or base
        print(f"\n=== {base}\n    titre : {titre}", flush=True)

        subs = st.sous_titres(transcrire(src, cache))
        with open(os.path.join(vert, base + " - sous-titres.txt"), "w", encoding="utf-8") as fh:
            fh.write(f"{titre}\n\n")
            for a, b, t in subs:
                fh.write(f"{a:6.2f} -> {b:6.2f}   {t}\n")

        d = duree_de(src)
        c = cadrage(src)
        (hx, hy), (bx, by) = c["haut"], c["bas"]

        # --- vertical : split screen
        split = f"/tmp/montage/split-{base}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex",
                        f"[0:v]crop={CW}:{CH}:{hx}:{hy},scale=1080:960,setsar=1[h];"
                        f"[0:v]crop={CW}:{CH}:{bx}:{by},scale=1080:960,setsar=1[b];"
                        f"[h][b]vstack=2[v];"
                        f"[v]drawbox=x=0:y=956:w=1080:h=8:color=0x191919@1:t=fill[out]",
                        "-map", "[out]", "-map", "0:a", "-c:v", "libx264", "-preset", "medium",
                        "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                        split], check=True)
        brut = f"/tmp/montage/vert-{base}.mp4"
        rendre(split, subs, titre, 1080, 1920, 960, d, brut)
        piste = poser_musique(brut, os.path.join(vert, base + ".mp4"))
        print(f"    vertical ok, musique : {piste}", flush=True)

        # --- horizontal : image d'origine, meme habillage, sans musique
        plat = f"/tmp/montage/plat-{base}.mp4"
        shutil.copy(src, plat)
        rendre(plat, subs, titre, 1920, 1080, 900, d, os.path.join(horiz, base + ".mp4"))
        print("    horizontal ok", flush=True)

    print("\n=== TERMINE ===")


if __name__ == "__main__":
    main()
