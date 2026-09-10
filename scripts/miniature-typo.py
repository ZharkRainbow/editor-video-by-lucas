#!/usr/bin/env python3
"""Miniature typographiee : une phrase eclatee, le mot cle en enorme.

Structure de reference : une amorce en petit au-dessus, le mot ou le chiffre
qui accroche en tres gros, une chute en petit en dessous. Les deux petites
lignes font la largeur du gros mot, l'amorce calee a gauche et la chute a
droite.

L'amorce et la chute sont facultatives. Passer une amorce vide fait commencer
l'accroche par le gros mot, ce qui est souvent plus fort quand l'accroche est
un chiffre : le lecteur voit le montant avant de savoir de quoi on parle.

Par defaut le texte est en blanc avec mix-blend-mode difference : il s'inverse
sur le fond, donc il reste lisible partout sans ombre. L'option --blanc rend le
texte en blanc franc, sans inversion, avec une ombre portee douce pour tenir sur
les fonds clairs.

Le rendu passe par Chrome plutot que par ImageMagick : c'est la seule facon
d'avoir ZT Nature, le crenage et l'ombre portee exactement comme dans les
compositions video.

usage : miniature-typo.py video.mp4 sortie.jpg "amorce" "MOT CLE" "chute"
"""
import base64, html, os, subprocess, sys, tempfile

RACINE = os.path.expanduser("~/Documents/RAIZ-Claude/OFFBOUND/APPS/video-reels")
FONTS = os.path.expanduser(
    "~/Documents/RAIZ-Claude/OFFBOUND/CONTENU/reels-hyperframes/_charte-offbound/fonts")
CHROME = os.path.expanduser(
    "~/.cache/puppeteer/chrome-headless-shell/mac_arm-150.0.7871.24/"
    "chrome-headless-shell-mac-arm64/chrome-headless-shell")
MINI = os.path.join(RACINE, "scripts", "choisir-image.py")
# le selecteur v2 tourne sous mediapipe, qui n a pas de roue pour python 3.14
VENV = os.path.join(RACINE, ".venv-mp", "bin", "python")

# Zones sures Instagram relevees sur le gabarit de Lucas
SAFE_HAUT, SAFE_GAUCHE, SAFE_DROITE = 250, 70, 55


def fond(video, dst_png):
    """Meilleure image de la video, choisie par le selecteur existant."""
    r = subprocess.run([VENV, MINI, video, dst_png], capture_output=True, text=True)
    if not os.path.exists(dst_png):
        raise SystemExit(f"aucune image exploitable : {r.stdout} {r.stderr}")
    return dst_png


def b64(p):
    return base64.b64encode(open(p, "rb").read()).decode()


def page(img_png, amorce, cle, chute, lw, lh, blanc=False):
    fam = []
    for nom, poids in (("Regular", 400), ("SemiBold", 600), ("Bold", 700),
                       ("Black", 900)):
        f = os.path.join(FONTS, f"ZTNature-{nom}.woff2")
        if os.path.exists(f):
            fam.append(f'@font-face{{font-family:"ZT Nature";font-weight:{poids};'
                       f'src:url(data:font/woff2;base64,{b64(f)}) format("woff2")}}')
    court = min(lw, lh)
    return f"""<!doctype html><meta charset="utf-8"><style>
{''.join(fam)}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{lw}px;height:{lh}px;overflow:hidden}}
/* isolation:isolate est obligatoire : sans elle le blend se calcule contre le
   fond de la page et l'inversion ne se produit pas */
.scene{{position:absolute;inset:0;isolation:isolate}}
.fond{{position:absolute;inset:0;background:url(data:image/png;base64,{b64(img_png)})
  center/cover no-repeat}}
.bloc{{position:absolute;top:{SAFE_HAUT + round(lh*0.045)}px;
  left:{SAFE_GAUCHE}px;right:{SAFE_DROITE}px;
  font-family:"ZT Nature",sans-serif;color:#fff;
  {'text-shadow:0 2px 20px rgba(0,0,0,.5),0 0 3px rgba(0,0,0,.3)'
   if blanc else 'mix-blend-mode:difference'};
  display:flex;flex-direction:column;align-items:center}}
.rangee{{width:100%;display:flex}}
.haut{{justify-content:flex-start}}
.bas{{justify-content:flex-end}}
/* casse naturelle sur les lignes d'appui, capitales sur le mot cle */
/* aucun rembourrage horizontal : les petites lignes doivent affleurer
   exactement les bords du mot cle, a gauche pour l'amorce, a droite pour la
   chute. Le moindre padding casse cet alignement. */
.petit{{font-weight:600;font-size:{round(court*0.042)}px;letter-spacing:0;
  line-height:1;padding:0;white-space:nowrap}}
.haut{{margin-bottom:-{round(court*0.004)}px}}
.bas{{margin-top:-{round(court*0.004)}px}}
.gros{{font-weight:900;font-size:{round(court*0.175)}px;letter-spacing:-.02em;
  line-height:.92;white-space:nowrap;text-transform:uppercase}}
</style>
<div class="scene">
  <div class="fond"></div>
  <div class="bloc">
    {f'<div class="rangee haut"><span class="petit">{html.escape(amorce)}</span></div>' if amorce.strip() else ''}
    <div class="gros">{html.escape(cle)}</div>
    {f'<div class="rangee bas"><span class="petit">{html.escape(chute)}</span></div>' if chute.strip() else ''}
  </div>
</div>
<script>
  // Aligner les boites de texte ne suffit pas : une police reserve une marge
  // laterale propre a chaque glyphe (l'approche), proportionnelle a la taille.
  // Le A d'une ligne a 45 px et le F d'une ligne a 180 px ne commencent donc
  // pas au meme endroit meme si leurs boites sont alignees. On mesure l'encre
  // reelle au canvas et on decale chaque ligne de sa propre approche.
  //
  // document.fonts.ready est indispensable : sans lui le canvas mesure avec
  // une police de repli et les approches obtenues n'ont rien a voir.
  document.fonts.ready.then(() => {{
    const gros = document.querySelector('.gros');
    const bloc = document.querySelector('.bloc');
    const haut = document.querySelector('.haut .petit');
    const bas  = document.querySelector('.bas .petit');

    let taille = parseFloat(getComputedStyle(gros).fontSize);
    const dispo = bloc.clientWidth;
    let garde = 0;
    while (gros.scrollWidth > dispo && taille > 24 && garde++ < 300) {{
      taille -= 2;
      gros.style.fontSize = taille + 'px';
    }}

    const ctx = document.createElement('canvas').getContext('2d');
    function encre(el) {{
      const st = getComputedStyle(el);
      ctx.font = st.fontWeight + ' ' + st.fontSize + ' "ZT Nature"';
      // measureText ignore letter-spacing du CSS. Sans cette ligne le mot cle
      // est mesure 33 px trop large et la chute deborde d'autant a droite.
      ctx.letterSpacing = st.letterSpacing === 'normal' ? '0px' : st.letterSpacing;
      const m = ctx.measureText(el.textContent);
      return {{ g: -m.actualBoundingBoxLeft, d: m.actualBoundingBoxRight }};
    }}

    const eg = encre(gros);
    const rg = gros.getBoundingClientRect();
    const bordG = rg.left + eg.g;
    const bordD = rg.left + eg.d;

    for (const r of document.querySelectorAll('.rangee')) {{
      r.style.width = '100%';
    }}
    // l amorce et la chute sont facultatives : une accroche peut demarrer
    // directement sur le gros mot
    if (haut) {{
      const eh = encre(haut);
      haut.style.position = 'relative';
      const rh = haut.getBoundingClientRect();
      haut.style.left = (bordG - (rh.left + eh.g)) + 'px';
    }}
    if (bas) {{
      const eb = encre(bas);
      bas.style.position = 'relative';
      const rb = bas.getBoundingClientRect();
      bas.style.left = (bordD - (rb.left + eb.d)) + 'px';
    }}

    document.documentElement.dataset.pret = '1';
  }});
</script>"""


def fabriquer(video, dst, amorce, cle, chute, fond_src=None, blanc=False):
    """fond_src : video servant d'image de fond. On lui passe le plan monte
    AVANT incrustation (plan.mp4), sinon la miniature herite d'un sous-titre
    fige au milieu de l'image, ce qui est laid et illisible hors contexte."""
    import json
    dims = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                           "-show_entries", "stream=width,height", "-of",
                           "csv=p=0:s=x", video], capture_output=True, text=True)
    lw, lh = [int(x) for x in dims.stdout.strip().split("x")]
    with tempfile.TemporaryDirectory() as td:
        img = fond(fond_src or video, os.path.join(td, "f.png"))
        htm = os.path.join(td, "m.html")
        open(htm, "w", encoding="utf-8").write(
            page(img, amorce, cle, chute, lw, lh, blanc))
        png = os.path.join(td, "out.png")
        subprocess.run([CHROME, "--headless", "--disable-gpu",
                        f"--window-size={lw},{lh}",
                        "--hide-scrollbars", "--force-device-scale-factor=1",
                        f"--screenshot={png}", "--virtual-time-budget=3000",
                        f"file://{htm}"], capture_output=True)
        if not os.path.exists(png):
            raise SystemExit("Chrome n'a pas produit d'image")
        subprocess.run(["magick", png, "-quality", "92", dst], check=True)
    print(f"{os.path.basename(dst)}  {lw}x{lh}")


if __name__ == "__main__":
    fond_src = None
    if "--fond" in sys.argv:
        fond_src = sys.argv[sys.argv.index("--fond") + 1]
    fabriquer(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5],
              fond_src, blanc="--blanc" in sys.argv)
