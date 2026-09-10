#!/usr/bin/env python3
"""Pose une carte d'accroche soulignee sur un reel, et sur sa miniature.

La carte est une seule forme blanche continue qui epouse le texte, comme un
soulignage, avec le texte en noir Offbound par dessus. Le trace est repris de
gen-reel.py : on releve les rectangles des lignes reellement affichees, on les
colle verticalement, puis on arrondit tous les sommets du contour en suivant le
sens du virage, ce qui creuse les angles rentrants au lieu de les bomber.

Deux choses sont calculees et non fixees a la main :

  la hauteur de la carte  Chrome rend la carte sur un fond transparent, on lit
      ensuite la boite englobante du canal alpha. Sans cela il faudrait deviner
      combien de lignes le texte occupe.

  la position verticale  On releve la position du visage de Valentin pendant
      toute la duree d'affichage, puis on pose la carte dans la bande libre la
      plus large, au-dessus ou en dessous de lui. Une carte posee sur son
      visage rend le plan inutilisable.

usage : carte-hook.py video.mp4 sortie.mp4 "La phrase, MOT en capitales"
          [--duree 5] [--miniature sortie.jpg] [--eviter 0.50 0.75]
"""
import os, re, subprocess, sys, tempfile
import base64, html
import cv2
import numpy as np

RACINE = os.path.expanduser("~/Documents/RAIZ-Claude/OFFBOUND/APPS/video-reels")
FONTS = os.path.expanduser(
    "~/Documents/RAIZ-Claude/OFFBOUND/CONTENU/reels-hyperframes/_charte-offbound/fonts")
CHROME = os.path.expanduser(
    "~/.cache/puppeteer/chrome-headless-shell/mac_arm-150.0.7871.24/"
    "chrome-headless-shell-mac-arm64/chrome-headless-shell")

# Zones mortes Instagram, relevees sur le gabarit de Lucas en 1080x1920 puis
# exprimees en fraction de hauteur, sinon un rendu horizontal en 2160 de haut
# les appliquerait deux fois trop haut
FRAC_HAUT, FRAC_BAS = 250 / 1920, 420 / 1920
PAD_X, PAD_Y, RAYON = 0.0333, 0.0194, 0.0259
FRAC_MARGE = 40 / 1920      # air minimal entre la carte et le visage
DUREE = 5.0
FONDU = 0.35


def taille(v):
    s = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height", "-of",
                        "csv=p=0:s=x", v], capture_output=True, text=True).stdout
    for ligne in s.splitlines():
        n = [int(x) for x in ligne.strip().split("x") if x.strip().isdigit()]
        if len(n) >= 2:
            return n[0], n[1]
    raise SystemExit("dimensions illisibles : " + v)


def b64(p):
    return base64.b64encode(open(p, "rb").read()).decode()


def page(texte, lw, lh):
    fam = []
    for nom, poids in (("Regular", 400), ("SemiBold", 600), ("Bold", 700),
                       ("Black", 900)):
        f = os.path.join(FONTS, f"ZTNature-{nom}.woff2")
        if os.path.exists(f):
            fam.append(f'@font-face{{font-family:"ZT Nature";font-weight:{poids};'
                       f'src:url(data:font/woff2;base64,{b64(f)}) format("woff2")}}')
    court = min(lw, lh)
    # une espace insecable dans les nombres et avant les unites, sinon « 10 000 »
    # se coupe en fin de ligne
    t = html.escape(texte)
    t = re.sub(r"(\d)\s+(\d)", "\\1\u202f\\2", t)
    t = re.sub(r"\s+([%€])", "\u202f\\1", t)
    t = re.sub(r"(\d)\s+(h|euros?|ans|K)\b", "\\1\u00a0\\2", t, flags=re.I)
    return f"""<!doctype html><meta charset="utf-8"><style>
{''.join(fam)}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{lw}px;height:{lh}px;overflow:hidden;background:transparent}}
.carte{{position:absolute;left:0;right:0;top:0;
  display:flex;justify-content:center}}
.boite{{position:relative;max-width:{round(lw * 0.80)}px}}
.boite svg{{position:absolute;inset:0;width:100%;height:100%;overflow:visible}}
/* text-wrap:balance est interdit : des que le navigateur egalise les lignes,
   la forme redevient un rectangle et le decrochement disparait */
.carte-in{{position:relative;display:block;text-align:center;
  color:#191919;font-family:"ZT Nature",sans-serif;font-weight:700;
  font-size:{round(court * 0.050)}px;line-height:1.50;letter-spacing:-.008em;
  padding:{round(court * PAD_Y)}px {round(court * PAD_X)}px}}
</style>
<div class="carte"><div class="boite">
  <svg><path id="soulignage" fill="#ffffff"></path></svg>
  <span class="carte-in">{t}</span>
</div></div>
<script>
function tracer() {{
  const txt = document.querySelector(".carte-in");
  const svg = document.querySelector(".boite svg");
  const hote = svg.parentNode.getBoundingClientRect();
  const plage = document.createRange();
  plage.selectNodeContents(txt);
  const lignes = [];
  for (const b of plage.getClientRects()) {{
    if (b.width < 1) continue;
    lignes.push({{x0: b.left - hote.left, x1: b.right - hote.left,
                 y0: b.top - hote.top, y1: b.bottom - hote.top}});
  }}
  if (!lignes.length) return;
  lignes.sort((a, b) => a.y0 - b.y0);
  const PX = {round(court * PAD_X)}, PY = {round(court * PAD_Y)},
        R = {round(court * RAYON)};
  const bo = lignes.map(l => ({{x0: l.x0 - PX, x1: l.x1 + PX,
                               y0: l.y0 - PY, y1: l.y1 + PY}}));
  for (let i = 1; i < bo.length; i++) {{
    const m = (bo[i - 1].y1 + bo[i].y0) / 2;
    bo[i - 1].y1 = m; bo[i].y0 = m;
  }}
  const pts = [];
  for (const b of bo) {{ pts.push([b.x1, b.y0]); pts.push([b.x1, b.y1]); }}
  for (let i = bo.length - 1; i >= 0; i--) {{
    pts.push([bo[i].x0, bo[i].y1]); pts.push([bo[i].x0, bo[i].y0]);
  }}
  const nets = pts.filter((p, i) => {{
    const q = pts[(i - 1 + pts.length) % pts.length];
    return Math.abs(p[0] - q[0]) > 0.5 || Math.abs(p[1] - q[1]) > 0.5;
  }});
  const n = nets.length, d = [];
  for (let i = 0; i < n; i++) {{
    const a = nets[(i - 1 + n) % n], b = nets[i], c = nets[(i + 1) % n];
    const v1 = [b[0] - a[0], b[1] - a[1]], v2 = [c[0] - b[0], c[1] - b[1]];
    const l1 = Math.hypot(v1[0], v1[1]), l2 = Math.hypot(v2[0], v2[1]);
    const k = Math.min(R, l1 / 2, l2 / 2);
    const e = [b[0] - v1[0] / l1 * k, b[1] - v1[1] / l1 * k];
    const t = [b[0] + v2[0] / l2 * k, b[1] + v2[1] / l2 * k];
    const croix = v1[0] * v2[1] - v1[1] * v2[0];
    d.push(i === 0 ? "M " + e[0] + " " + e[1] : "L " + e[0] + " " + e[1]);
    if (k > 0.5) d.push("A " + k + " " + k + " 0 0 " + (croix > 0 ? 1 : 0)
                        + " " + t[0] + " " + t[1]);
  }}
  svg.setAttribute("viewBox", "0 0 " + hote.width + " " + hote.height);
  document.getElementById("soulignage").setAttribute("d", d.join(" ") + " Z");
  document.documentElement.dataset.pret = "1";
}}
tracer();
if (document.fonts && document.fonts.ready) document.fonts.ready.then(tracer);
</script>"""


def rendre_carte(texte, lw, lh, dst):
    """Rend la carte sur fond transparent et la recadre sur son alpha."""
    with tempfile.TemporaryDirectory() as td:
        htm = os.path.join(td, "c.html")
        open(htm, "w", encoding="utf-8").write(page(texte, lw, lh))
        brut = os.path.join(td, "c.png")
        subprocess.run([CHROME, "--headless", "--disable-gpu",
                        f"--window-size={lw},{lh}", "--hide-scrollbars",
                        "--force-device-scale-factor=1",
                        "--default-background-color=00000000",
                        f"--screenshot={brut}", "--virtual-time-budget=3000",
                        f"file://{htm}"], capture_output=True)
        if not os.path.exists(brut):
            raise SystemExit("Chrome n'a pas produit la carte")
        img = cv2.imread(brut, cv2.IMREAD_UNCHANGED)
        if img is None or img.shape[2] < 4:
            raise SystemExit("la carte n'a pas de canal alpha")
        ys, xs = np.where(img[:, :, 3] > 8)
        if not len(ys):
            raise SystemExit("carte vide")
        crop = img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        cv2.imwrite(dst, crop)
        return crop.shape[1], crop.shape[0]


def bande_visage(video, t0, t1, lw, lh):
    """Union des boites du visage entre t0 et t1. None si aucun visage."""
    import mediapipe as mp
    FM = mp.solutions.face_mesh.FaceMesh
    DET = mp.solutions.face_detection.FaceDetection
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    y0, y1 = lh, 0
    with FM(static_image_mode=True, max_num_faces=1,
            min_detection_confidence=0.4) as fm, \
         DET(model_selection=1, min_detection_confidence=0.3) as det:
        t = t0
        while t < t1:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, img = cap.read()
            if ok:
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                r = fm.process(rgb)
                if r.multi_face_landmarks:
                    ys = [l.y * lh for l in r.multi_face_landmarks[0].landmark]
                    y0, y1 = min(y0, min(ys)), max(y1, max(ys))
                else:
                    rd = det.process(rgb)
                    if rd.detections:
                        b = rd.detections[0].location_data.relative_bounding_box
                        y0 = min(y0, b.ymin * lh)
                        y1 = max(y1, (b.ymin + b.height) * lh)
            t += 0.25
    cap.release()
    return (y0, y1) if y1 > y0 else None


def poser(lh, hauteur_carte, obstacles):
    """Choisit le haut de la carte dans la zone sure Instagram.

    obstacles : liste de (y0, y1, poids). Le visage pese dix fois un
    sous-titre deja incruste : quand rien ne rentre, mieux vaut recouvrir du
    texte que la figure de Valentin. On balaie donc toutes les positions
    possibles et on garde celle qui minimise le recouvrement pondere, ce qui
    donne aussi le bon resultat quand une bande libre existe puisque son cout
    est nul.
    """
    haut, bas = round(lh * FRAC_HAUT), lh - round(lh * FRAC_BAS)
    marge = round(lh * FRAC_MARGE)
    if bas - haut < hauteur_carte:
        return int(haut)
    obs = [(max(o[0] - marge, 0), min(o[1] + marge, lh), o[2])
           for o in obstacles if o]

    def cout(y):
        c = 0.0
        for a, b, w in obs:
            c += max(0, min(y + hauteur_carte, b) - max(y, a)) * w
        # a cout egal, on prefere le haut du cadre : c'est la que l'oeil arrive
        return c + (y - haut) * 0.001

    return int(min(range(haut, bas - hauteur_carte + 1, 2), key=cout))


def incruster(video, carte, x, y, duree, dst):
    cw, ch = cv2.imread(carte, cv2.IMREAD_UNCHANGED).shape[1::-1]
    f = (f"[1:v]format=rgba,fade=in:st=0:d={FONDU}:alpha=1,"
         f"fade=out:st={duree - FONDU:.2f}:d={FONDU}:alpha=1[c];"
         f"[0:v][c]overlay={x}:{y}:enable='between(t,0,{duree})'[v]")
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y",
                    "-i", video, "-loop", "1", "-t", f"{duree}", "-i", carte,
                    "-filter_complex", f, "-map", "[v]", "-map", "0:a?",
                    "-c:v", "h264_videotoolbox", "-b:v", "16M",
                    "-profile:v", "high", "-c:a", "copy",
                    "-movflags", "+faststart", dst], check=True)


if __name__ == "__main__":
    src, dst, texte = sys.argv[1], sys.argv[2], sys.argv[3]
    duree = float(sys.argv[sys.argv.index("--duree") + 1]) \
        if "--duree" in sys.argv else DUREE
    mini = sys.argv[sys.argv.index("--miniature") + 1] \
        if "--miniature" in sys.argv else None
    # bande a eviter, en fraction de hauteur : les reels du Mastermind portent
    # deja les sous-titres du monteur entre 0,50 et 0,75
    eviter = None
    if "--eviter" in sys.argv:
        i = sys.argv.index("--eviter")
        eviter = (float(sys.argv[i + 1]), float(sys.argv[i + 2]))

    lw, lh = taille(src)
    with tempfile.TemporaryDirectory() as td:
        carte = os.path.join(td, "carte.png")
        cw, ch = rendre_carte(texte, lw, lh, carte)
        vis = bande_visage(src, 0.2, duree, lw, lh)
        obs = [(vis[0], vis[1], 10.0)] if vis else []
        if eviter:
            obs.append((eviter[0] * lh, eviter[1] * lh, 1.0))
        y = poser(lh, ch, obs)
        x = (lw - cw) // 2
        incruster(src, carte, x, y, duree, dst)
        ou = ("aucun visage" if vis is None else f"visage {vis[0]:.0f}-{vis[1]:.0f}")
        if eviter:
            ou += f", bande evitee {eviter[0]*lh:.0f}-{eviter[1]*lh:.0f}"
        print(f"{os.path.basename(dst)}  carte {cw}x{ch} a y={y}  ({ou})")

        if mini:
            # le selecteur d'image tourne en sous-processus : son nom de
            # fichier porte un tiret, il n'est pas importable tel quel
            fond = os.path.join(td, "fond.png")
            subprocess.run([sys.executable,
                            os.path.join(RACINE, "scripts", "choisir-image.py"),
                            src, fond], capture_output=True)
            if not os.path.exists(fond):
                raise SystemExit("pas d'image de fond pour la miniature")
            img = cv2.imread(fond)
            # la miniature est une image fixe : on relit le visage dessus
            vm = None
            import mediapipe as mp
            with mp.solutions.face_mesh.FaceMesh(
                    static_image_mode=True, max_num_faces=1,
                    min_detection_confidence=0.4) as fm, \
                 mp.solutions.face_detection.FaceDetection(
                    model_selection=1, min_detection_confidence=0.3) as det:
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                r = fm.process(rgb)
                if r.multi_face_landmarks:
                    ys = [l.y * lh for l in r.multi_face_landmarks[0].landmark]
                    vm = (min(ys), max(ys))
                else:
                    rd = det.process(rgb)
                    if rd.detections:
                        b = rd.detections[0].location_data.relative_bounding_box
                        vm = (b.ymin * lh, (b.ymin + b.height) * lh)
            obm = [(vm[0], vm[1], 10.0)] if vm else []
            if eviter:
                obm.append((eviter[0] * lh, eviter[1] * lh, 1.0))
            ym = poser(lh, ch, obm)
            c = cv2.imread(carte, cv2.IMREAD_UNCHANGED)
            a = c[:, :, 3:4].astype(float) / 255.0
            zone = img[ym:ym + ch, x:x + cw].astype(float)
            img[ym:ym + ch, x:x + cw] = (zone * (1 - a) +
                                         c[:, :, :3].astype(float) * a)
            cv2.imwrite(mini, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            print(f"  miniature -> {os.path.basename(mini)}  carte a y={ym}")
