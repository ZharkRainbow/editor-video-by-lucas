#!/usr/bin/env python3
"""Genere un projet HyperFrames a partir d'un rush nettoye.

Style repris du reel de reference : sous-titres en majuscules, blancs, sans
cartouche, centres, 2 a 3 mots par ligne, animes a l'apparition. Pas de carton
titre. Le recadrage suit le visage, detecte avec OpenCV.

usage : gen-reel.py rush.mp4 musique.mp3 dossier_projet [9x16|1x1|16x9]
"""
import html, importlib.util, json, os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recaler

RACINE = os.path.expanduser("~/Documents/RAIZ-Claude/OFFBOUND/APPS/video-reels")
VENV = os.path.join(RACINE, ".venv", "bin", "python")
SUIVI = os.path.join(RACINE, "scripts", "suivre-visage.py")
CHARTE = os.path.expanduser(
    "~/Documents/RAIZ-Claude/OFFBOUND/CONTENU/reels-hyperframes/_charte-offbound")
MODELE = os.path.expanduser("~/.cache/whisper-cpp/ggml-large-v3-turbo.bin")

_sp = importlib.util.spec_from_file_location(
    "corr", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "corriger-transcript.py"))
CORR = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(CORR)

FORMATS = {"9x16": (1080, 1920), "1x1": (1080, 1080),
           "16x9": (1920, 1080), "4x5": (1080, 1350)}
# Formats obtenus en posant le paysage dans le cadre plutot qu'en recadrant.
# Le carre Instagram se lit ainsi : l'image 16:9 au milieu, bandes noires
# au-dessus et en dessous.
LETTERBOX = {"1x1"}
LIGNE = re.compile(r"\[(\d\d):(\d\d):(\d\d\.\d+)\s*-->\s*(\d\d):(\d\d):(\d\d\.\d+)\]\s*(.*)")
MAX_MOTS = 3          # Lucas : 2 a 3 mots par ligne, jamais plus
TAIL = 0.16           # temps de lecture ajoute apres le dernier mot


def sh(*a):
    return subprocess.run(a, check=True, capture_output=True, text=True).stdout


def duree(p):
    sortie = sh("ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "csv=p=0", p)
    for ligne in sortie.splitlines():
        ligne = ligne.strip()
        if ligne and ligne[0].isdigit():
            return float(ligne)
    raise ValueError(f"duree illisible pour {p}")


def taille(p):
    """Dimensions de la piste video.

    ffprobe est capricieux sur ces fichiers. Selon la source il renvoie une
    ligne propre, une ligne suivie d'une seconde ligne vide (rushs Osmo, qui
    portent une piste de donnees), ou une ligne terminee par un separateur en
    trop (rushs iPhone). On lit donc tous les nombres presents et on garde les
    deux premiers, plutot que de faire confiance au decoupage.
    """
    sortie = sh("ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", p)
    for ligne in sortie.splitlines():
        n = [int(v) for v in ligne.strip().split("x") if v.strip().isdigit()]
        if len(n) >= 2:
            return n[:2]
    raise ValueError(f"dimensions illisibles pour {p}")


# ---------------------------------------------------------------- transcription

def source_pour_transcrire(src):
    """Le debruitage ameliore l'ecoute mais degrade la transcription.

    Constate sur la 012 : whisper entend "trucs" de facon stable sur l'audio
    brut, et hallucine "specs", "sneques", "spectacles" sur le meme passage
    debruite. DeepFilterNet modifie le timbre des mots avales et whisper se met
    a deviner. On transcrit donc depuis le rush d'origine quand il existe, et on
    ne garde le fichier nettoye que pour le rendu.

    GARDE-FOU INDISPENSABLE : certains fichiers de _racine ont ete recoupes
    apres coup (redites retirees). Leur duree ne correspond alors plus a celle
    du brut, et transcrire le brut donnerait des sous-titres decales de plusieurs
    secondes. On ne bascule que si les deux durees concordent.
    """
    d = os.path.dirname(os.path.abspath(src))
    if os.path.basename(d) not in ("_racine", "_voix-nettoyee"):
        return src
    brut = os.path.join(os.path.dirname(d), os.path.basename(src))
    if not os.path.exists(brut):
        return src
    try:
        if abs(duree(brut) - duree(src)) > 0.15:
            return src          # le fichier a ete recoupe : on garde le sien
    except Exception:
        return src
    return brut


def transcrire(src, cache):
    if not os.path.exists(cache):
        texte_src = source_pour_transcrire(src)
        wav = cache + ".wav"
        sh("ffmpeg", "-y", "-v", "error", "-i", texte_src, "-ar", "16000", "-ac", "1", wav)
        open(cache, "w", encoding="utf-8").write(subprocess.run(
            ["whisper-cli", "-m", MODELE, "-f", wav, "-l", "fr", "-ml", "1", "-sow",
             "-np", "-t", "8"], capture_output=True, text=True).stdout)
        os.remove(wav)
    mots = []
    for l in open(cache, encoding="utf-8"):
        m = LIGNE.match(l.strip())
        if not m:
            continue
        w = m.group(7).strip()
        if not w or w in "«»:;":
            continue
        t0 = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        t1 = int(m.group(4)) * 3600 + int(m.group(5)) * 60 + float(m.group(6))
        if mots and mots[-1][2] == w and t0 - mots[-1][1] < 0.02:
            continue
        mots.append((t0, max(t1, t0 + 0.06), w))
    # whisper ne connait ni la marque ni le jargon : on corrige avant de
    # decouper en lignes, sinon les fautes partent a l'ecran
    mots = CORR.corriger(mots)

    # whisper accroche les premiers mots au debut de sa fenetre de 30 s meme
    # quand le reel commence par un souffle. Sur la 007 les trois premiers mots
    # passaient 1,7 s avant la voix. On remet le minutage d'aplomb en
    # retranscrivant chaque segment de parole isolement (le texte, lui, ne
    # bouge pas). Voir recaler.py.
    ancre = cache + ".cal.json"
    if os.path.exists(ancre):
        ref = [tuple(x) for x in json.load(open(ancre, encoding="utf-8"))]
    else:
        voix = cache + ".voix.wav"
        sh("ffmpeg", "-y", "-v", "error", "-i", src, "-ar", "16000", "-ac", "1", voix)
        ref = recaler.horodatages_reels(voix, os.path.dirname(os.path.abspath(cache)))
        os.remove(voix)
        json.dump(ref, open(ancre, "w", encoding="utf-8"))
    return recaler.recaler(mots, ref)


def nettoyer(w):
    """Retire la ponctuation, garde la casse telle que whisper l'a ecrite.

    Pas de majuscules forcees : la casse naturelle suit la phrase, donc une
    ligne qui commence au milieu d'une phrase reste en minuscules.
    """
    return w.strip(" ,.;:!?»«…\"'")


def lignes(mots):
    """Decoupe en lignes de 2 a 3 mots, sans jamais chevaucher deux phrases.

    On isole d'abord les phrases : une ligne qui melange la fin d'une phrase et
    le debut de la suivante se lit mal. On tranche ensuite a l'interieur, en
    privilegiant les virgules et les respirations.
    """
    phrases, cur = [], []
    for t0, t1, w in mots:
        if not nettoyer(w):
            continue
        cur.append((t0, t1, w))
        if w.endswith((".", "!", "?", "…")):
            phrases.append(cur)
            cur = []
    if cur:
        phrases.append(cur)

    out = []
    for ph in phrases:
        bloc = []
        for i, mot in enumerate(ph):
            bloc.append(mot)
            suivant = ph[i + 1] if i + 1 < len(ph) else None
            coupe = (len(bloc) >= MAX_MOTS
                     or mot[2].endswith(",") and len(bloc) >= 2
                     or (suivant and suivant[0] - mot[1] >= 0.30 and len(bloc) >= 2))
            if coupe:
                out.append(bloc)
                bloc = []
        if bloc:
            out.append(bloc)
    # un mot isole se lit mal et passe trop vite : on le recolle au voisin
    fus = []
    for g in out:
        if len(g) == 1 and fus and len(fus[-1]) < MAX_MOTS + 1:
            fus[-1] = fus[-1] + g
        else:
            fus.append(g)
    for i, g in enumerate(fus):
        if len(g) == 1 and i + 1 < len(fus) and len(fus[i + 1]) < MAX_MOTS + 1:
            fus[i + 1] = g + fus[i + 1]
            fus[i] = []
    return [g for g in fus if g]


# ------------------------------------------------------------------- recadrage

def serie_visage(src):
    """Trajectoire horizontale du visage, pour un recadrage qui le suit."""
    if not os.path.exists(VENV):
        return None
    r = subprocess.run([VENV, SUIVI, src, "--serie"], capture_output=True, text=True)
    t = r.stdout.strip()
    if not t or t == "aucun":
        return None
    pts = []
    for p in t.split():
        a, b = p.split(",")
        pts.append((float(a), float(b)))
    return pts


MAX_POINTS = 26   # au-dela, les if() imbriques depassent le parseur d'ffmpeg


def expr_suivi(pts, sw, cw):
    """Expression ffmpeg : x du recadrage interpole entre les points mesures.

    On echantillonne dense pour bien detecter, puis on decime avant de
    construire l'expression : la courbe est deja lissee, elle bouge lentement,
    et une trentaine de points suffit a la decrire. Sans cette decimation un
    reel d'une minute produit 139 if() imbriques et ffmpeg refuse de parser.
    """
    if len(pts) > MAX_POINTS:
        pas = (len(pts) - 1) / (MAX_POINTS - 1)
        pts = [pts[min(int(round(i * pas)), len(pts) - 1)] for i in range(MAX_POINTS)]
    xs = [max(0, min(sw - cw, x * sw - cw / 2)) for _, x in pts]
    ts = [t for t, _ in pts]
    expr = f"{xs[-1]:.1f}"
    for i in range(len(ts) - 2, -1, -1):
        dt = max(ts[i + 1] - ts[i], 1e-3)
        seg = (f"({xs[i]:.1f}+({xs[i+1]-xs[i]:.1f})*"
               f"(t-{ts[i]:.3f})/{dt:.3f})")
        expr = f"if(lt(t,{ts[i+1]:.3f}),{seg},{expr})"
    return expr


def visage(src):
    if not os.path.exists(VENV):
        return None
    r = subprocess.run([VENV, SUIVI, src], capture_output=True, text=True)
    p = r.stdout.strip().split()
    if len(p) != 5:
        return None
    return float(p[0]), float(p[1]), float(p[2]), int(p[3]), int(p[4])


def filtre_video(fmt, sw, sh_, cx, cy, pts=None):
    lw, lh = FORMATS[fmt]
    # Le letterbox suppose une source plus large que haute : on la pose en
    # entier et il reste une bande noire en haut et en bas. Sur un rush filme
    # en vertical, la meme regle demanderait une image de 1920 de haut dans un
    # carre de 1080, donc un decalage negatif, et ffmpeg refuse. Ces rushs-la
    # sont donc recadres comme les autres formats.
    if fmt in LETTERBOX and sw >= sh_:
        hv = int(round(lw * sh_ / sw))
        hv -= hv % 2
        haut = (lh - hv) // 2
        return (f"scale={lw}:{hv}:flags=lanczos,"
                f"pad={lw}:{lh}:0:{haut}:black")
    ratio = lw / lh
    if sw / sh_ > ratio:
        cw, ch = int(sh_ * ratio), sh_
    else:
        cw, ch = sw, int(sw / ratio)
    cw -= cw % 2
    ch -= ch % 2
    # on vise le visage au tiers haut plutot qu'au centre geometrique
    y = (sh_ - ch) // 2 if cy is None else int(cy * sh_ - ch * 0.38)
    y = max(0, min(sh_ - ch, y)) & ~1
    if pts and cw < sw:
        x = f"'{expr_suivi(pts, sw, cw)}'"
    else:
        xi = (sw - cw) // 2 if cx is None else int(cx * sw - cw / 2)
        x = str(max(0, min(sw - cw, xi)) & ~1)
    return f"crop={cw}:{ch}:{x}:{y},scale={lw}:{lh}:flags=lanczos"


def caler_musique(src, musique, ecart=16.0):
    """Choisit le bon extrait du morceau et le bon gain, mesures a l'appui."""
    r = subprocess.run([sys.executable,
                        os.path.join(RACINE, "scripts", "caler-musique.py"),
                        src, musique, str(ecart)], capture_output=True, text=True)
    p = r.stdout.strip().split()
    if len(p) != 2:
        return 0.0, 0.10
    return float(p[0]), float(p[1])


def preparer_plan(src, musique, dst, fmt, vol, vignette=False):
    sw, sh_ = taille(src)
    v = visage(src)
    if v:
        cx, cy, t, n, tot = v
        print(f"  visage detecte sur {n}/{tot} images : x={cx*100:.0f}% y={cy*100:.0f}%")
    else:
        cx = cy = None
        print("  aucun visage detecte, recadrage au centre")
    sans_suivi = LETTERBOX | {"16x9"}
    pts = None if fmt in sans_suivi else serie_visage(src)
    if pts:
        mini, maxi = min(x for _, x in pts), max(x for _, x in pts)
        print(f"  suivi du visage sur {len(pts)} points, amplitude "
              f"{(maxi-mini)*100:.1f}% de la largeur")
    vf = filtre_video(fmt, sw, sh_, cx, cy, pts)
    if vignette:
        vf += "," + VIGNETTE
    d = duree(src)
    # un pourcentage de volume ne veut rien dire d'un morceau a l'autre : on
    # mesure la voix et la musique, et on vise un ecart fixe en LU
    debut_mus, vol = caler_musique(src, musique)
    print(f"  musique : extrait a {debut_mus:.0f}s, gain {vol:.3f} "
          f"(16 LU sous la voix)")
    sh("ffmpeg", "-y", "-v", "error", "-i", src,
       "-ss", f"{debut_mus:.3f}", "-stream_loop", "-1", "-i", musique,
       "-filter_complex",
       f"[0:v]{vf}[v];"
       f"[1:a]volume={vol},atrim=0:{d:.3f},asetpts=PTS-STARTPTS,"
       f"afade=t=in:st=0:d=0.8,afade=t=out:st={max(0, d-1.6):.3f}:d=1.6[m];"
       # Limiteur de securite. level=false est obligatoire : par defaut alimiter
       # fait de l'auto-level, c'est-a-dire qu'il REMONTE le signal jusqu'a sa
       # limite. Sans ce reglage on obtient l'inverse d'un limiteur et le pic
       # vrai passe au-dessus de zero.
       f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
       f"alimiter=limit=0.84:level=false:latency=true[a]",
       "-map", "[v]", "-map", "[a]", "-c:v", "h264_videotoolbox", "-b:v", "14M",
       "-c:a", "aac", "-b:a", "192k", "-r", "30", dst)
    return d


# ------------------------------------------------------------------------ HTML

# Zones sures Instagram Reels, relevees sur le gabarit fourni par Lucas
# (1080x1920) : haut 250, bas 420, gauche 70, droite 55 au-dessus de y=1110,
# droite 193 en dessous (colonne des boutons). On place donc le sous-titre
# au-dessus de 1110 : c'est la seule facon d'etre a la fois centre sur 540 et
# hors des zones mortes.
SAFE = {"haut": 250, "bas": 420, "gauche": 70, "droite_haut": 55,
        "droite_bas": 193, "bascule": 1110}


# Motifs declenches par un mot du discours. Dessines en SVG plutot qu'en image :
# net a n'importe quelle taille, et le trace peut s'animer.
MOTIFS = {
    "hook": """<svg viewBox="0 0 200 420" fill="none" stroke="#fff"
        stroke-width="11" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="100" cy="26" r="17"/>
      <path d="M100 44 L100 258 C100 336 26 336 26 258 L26 228"/>
      <path d="M26 228 L52 262"/>
    </svg>""",
}
MOTIFS["hooks"] = MOTIFS["hook"]


def css_motif(lw, lh):
    # le motif doit tenir derriere le texte sans toucher la zone morte du bas
    haut = round(lh * 0.355)
    haut_dispo = round(lh * 0.76) - haut
    cote = round(haut_dispo / 2.1)
    return f"""
      .motif{{position:absolute;left:50%;top:{haut}px;
        width:{cote}px;height:{haut_dispo}px;margin-left:-{cote//2}px;
        display:flex;align-items:center;justify-content:center;opacity:0;
        pointer-events:none}}
      .motif svg{{width:100%;height:100%;
        filter:drop-shadow(0 0 26px rgba(0,0,0,.45))}}
      .motif path,.motif circle{{stroke-dasharray:1200;stroke-dashoffset:1200}}
"""


CARTE_DUREE = 2.2
# Soulignage de la carte, reglage choisi par Lucas sur maquette (variante G).
# Pas de text-wrap:balance : tant que le navigateur egalise les deux lignes,
# la forme redevient un rectangle et le decrochement ne se voit plus.
PAD_X = 0.0333
PAD_Y = 0.0194
RAYON = 0.0259
# Longueur au-dela de laquelle une phrase ne tient plus sur une ligne de
# carte, mesuree sur les rendus : 864 px utiles, corps 54 px.
LIGNE_MAX = 30
# Vignettage : assombrissement des coins pour ramener l'oeil au centre.
# Mesure sur un plan interieur, part de lumiere retiree dans les coins :
# PI/16 -> 5,8 %   PI/13 -> 8,7 %   PI/11 -> 11,9 %   PI/9 -> 17,4 %
# PI/7 -> 27,3 %. Lucas a retenu PI/7 : un vrai vignettage, assume.
VIGNETTE = "vignette=angle=PI/7"


def titre_html(t):
    """Prepare le texte de la carte pour l'affichage.

    Deux corrections que le navigateur ne fait pas tout seul :

      - la coupure de ligne tombe apres un point plutot qu'au milieu d'une
        phrase. Sans cela on obtenait « Ton studio ne sert a RIEN. 500 » puis
        « euros suffisent. », ce qui casse la lecture du hook. Mais on ne force
        la coupure que si CHAQUE phrase tient sur une ligne : sinon on cree une
        ligne orpheline, comme sur la 016 ou « Ils suivaient un SUJET, pas une
        personne. Ils sont partis. » donnait « pas une » / « personne. » /
        « Ils sont partis. ». La mesure se fait sur le texte brut, avant
        echappement : une apostrophe devient &#x27; et fausserait le comptage ;

      - un nombre ne se separe jamais de son unite ni de ses milliers. On pose
        une espace insecable dans « 10 000 », « 12 h », « 50 % », « 500 euros ».
    """
    morceaux = re.split(r"(?<=[.!?])\s+(?=[A-ZÀÉÈÊÎÔÙ«\d])", t)
    couper = len(morceaux) > 1 and all(len(m) <= LIGNE_MAX for m in morceaux)

    def souder(m):
        m = html.escape(m)
        m = re.sub(r"(\d)\s+(\d)", "\\1\u202f\\2", m)
        m = re.sub(r"\s+([%€])", "\u202f\\1", m)
        m = re.sub(r"(\d)\s+(h|euros?|centimes?|ans|K)\b", "\\1\u00a0\\2", m,
                   flags=re.IGNORECASE)
        return m

    return ("<br>" if couper else " ").join(souder(m) for m in morceaux)


def css_carte(lw, lh, fmt, bande=True):
    """Cartouche d'accroche, reserve au format carre.

    Le carre est le seul format lettreboxe, donc le seul ou une bande noire est
    libre. Ailleurs la carte se poserait sur le visage de Valentin.

    Le fond blanc n'est PAS un fond CSS. Un fond pose sur du texte en ligne
    donne un rectangle par ligne, et on voit deux blocs distincts. Lucas veut
    une seule forme continue qui epouse le texte, comme un soulignage : elle est
    donc tracee en SVG a partir des lignes reellement affichees, angles
    rentrants arrondis compris. Voir soulignage() plus bas.
    """
    # hauteur de la bande noire du haut, ou zone sure quand il n'y en a pas
    # (rush filme en vertical : l'image occupe tout le carre, la carte se pose
    # dessus, comme sur la reference fournie par Lucas)
    # Bande noire du haut quand la source est horizontale. Quand elle est
    # verticale, l'image occupe tout le carre : la carte se pose dessus, mais
    # sous la zone morte du haut d'Instagram (250 px sur 1920, soit 13 % de la
    # hauteur), sinon l'interface la recouvre.
    if bande:
        haut_y, haut_h = 0, (lh - round(lw * 9 / 16)) // 2
    else:
        haut_y, haut_h = round(lh * 0.135), round(lh * 0.24)
    court = min(lw, lh)
    return f"""
      .carte{{position:absolute;left:0;right:0;top:{haut_y}px;height:{haut_h}px;
        display:flex;justify-content:center;align-items:center;opacity:0}}
      .boite{{position:relative;max-width:{round(lw * 0.80)}px}}
      .boite svg{{position:absolute;inset:0;width:100%;height:100%;
        overflow:visible}}
      .carte-in{{position:relative;display:block;text-align:center;
        color:var(--ob-noir,#191919);font-weight:700;
        font-size:{round(court * 0.050)}px;line-height:1.50;
        letter-spacing:-.008em;
        padding:{round(court * PAD_Y)}px {round(court * PAD_X)}px}}
"""


def soulignage_js(court):
    """Trace le fond de la carte comme UNE seule forme.

    On releve les rectangles des lignes reellement affichees, on les colle
    verticalement pour que l'union soit d'un seul tenant, puis on arrondit tous
    les sommets du contour. Le sens de l'arc suit le sens du virage, ce qui
    creuse les angles rentrants au lieu de les bomber : c'est ce detail qui fait
    lire la forme comme un soulignage et non comme deux pavés empiles.
    """
    return f"""
      function tracerSoulignage() {{
        const txt = document.querySelector(".carte-in");
        const svg = document.querySelector(".boite svg");
        if (!txt || !svg) return;
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
          if (k > 0.5) d.push("A " + k + " " + k + " 0 0 " +
                              (croix > 0 ? 1 : 0) + " " + t[0] + " " + t[1]);
        }}
        svg.setAttribute("viewBox", "0 0 " + hote.width + " " + hote.height);
        document.getElementById("soulignage").setAttribute("d", d.join(" ") + " Z");
      }}
      tracerSoulignage();
      if (document.fonts && document.fonts.ready) {{
        document.fonts.ready.then(tracerSoulignage);
      }}
"""


def css_blend():
    """Blend Difference (catalogue HyperFrames) : le texte s'inverse pixel par
    pixel contre l'image. Il reste lisible sur clair comme sur sombre, sans
    ombre portee. Exige isolation:isolate sur la racine et la classe posee sur
    le conteneur, pas sur chaque mot."""
    return """
      .sub-in.blend{mix-blend-mode:difference;color:#fff;
        text-shadow:0 0 22px rgba(255,255,255,.16)}
"""


def css(lw, lh, fmt="9x16", bande=True):
    court = min(lw, lh)
    if (lw, lh) == (1080, 1920):
        bas = lh - SAFE["bascule"] + 20          # le bloc reste au-dessus de 1110
        large = lw - 2 * SAFE["droite_haut"] - 40
    elif fmt in LETTERBOX and bande:
        # le texte doit rester sur l'image, pas sur la bande noire : on le cale
        # a 62 % de la hauteur de la VIDEO, pas du cadre
        hv = round(lw * 9 / 16)
        haut = (lh - hv) // 2
        bas = lh - (haut + round(hv * 0.74))
        large = round(lw * 0.80)
    else:
        # meme regle qu'en portrait : le texte assis vers 63 % de la hauteur,
        # et des lignes qui restent compactes plutot qu'etalees sur la largeur
        bas = round(lh * 0.37)
        large = round(lw * (0.72 if lh >= lw else 0.55))
    return f"""
      *{{margin:0;padding:0;box-sizing:border-box}}
      html,body{{width:{lw}px;height:{lh}px;overflow:hidden;background:#000;
        font-family:var(--ob-font),system-ui,sans-serif}}
      .sub{{position:absolute;left:0;right:0;bottom:{bas}px;
        display:flex;justify-content:center;align-items:flex-end}}
      .sub-in{{max-width:{large}px;text-align:center;font-weight:600;
        font-size:{round(court*0.048)}px;line-height:1.16;letter-spacing:0;
        color:#fff;
        /* halo blanc tres discret, pose sur l'ombre portee qui assure la lisibilite */
        text-shadow:0 0 26px rgba(255,255,255,.30),0 0 10px rgba(255,255,255,.22),
                    0 2px 14px rgba(0,0,0,.55),0 1px 3px rgba(0,0,0,.70)}}
      /* Focus Blur Resolve (catalogue HyperFrames) : GSAP ne sait pas animer
         filter, mais il sait animer une variable CSS. Le CSS la consomme ici. */
      .w{{display:inline-block;opacity:0;will-change:transform,filter,opacity;
        transform:translateY(var(--hf-word-y,0px)) scale(var(--hf-word-scale,1));
        filter:blur(var(--hf-word-blur,0px))}}
"""


def generer(src, musique, projet, fmt, vol=0.17, blend=False, motifs=False,
            titre=None, vignette=False):
    lw, lh = FORMATS[fmt]
    os.makedirs(os.path.join(projet, "assets", "media"), exist_ok=True)
    cible = os.path.join(projet, "assets", "charte-offbound")
    if not os.path.isdir(cible):
        shutil.copytree(CHARTE, cible)

    sw0, sh0 = taille(src)
    bande = fmt in LETTERBOX and sw0 >= sh0
    plan = os.path.join(projet, "assets", "media", "plan.mp4")
    d = preparer_plan(src, musique, plan, fmt, vol, vignette)

    cache = os.path.join(os.path.dirname(os.path.abspath(projet)),
                         ".mots-" + os.path.basename(src).replace(".mp4", ".txt"))
    ls = lignes(transcrire(src, cache))

    divs, blocs = [], []
    for i, g in enumerate(ls):
        deb = max(g[0][0] - 0.14, 0)
        suivante = ls[i + 1][0][0] if i + 1 < len(ls) else d + 1
        fin = min(g[-1][1] + TAIL, suivante - 0.01, d)
        # une ligne trop breve s'allonge, elle ne se jette pas : sinon des mots
        # se retrouvent sans sous-titre a l'ecran
        if fin - deb < 0.28:
            fin = min(deb + 0.28, suivante - 0.01, d)
        if fin - deb < 0.08:
            continue
        spans = " ".join(
            f'<span class="w" id="w{i}_{j}">{html.escape(nettoyer(w))}</span>'
            for j, (a, b, w) in enumerate(g))
        divs.append(f'      <div id="s{i}" class="clip sub" data-start="{deb:.2f}" '
                    f'data-duration="{fin-deb:.2f}" data-track-index="1">'
                    f'<div class="sub-in{" blend" if blend else ""}">'
                    f'{spans}</div></div>')
        # Le mot doit etre LISIBLE quand il est prononce, pas commencer a
        # apparaitre a cet instant. L'animation dure 0.26 s : on l'anticipe pour
        # que le mot soit deja en place. Sans cela le tout premier mot du reel
        # semble en retard, les suivants etant masques par l'enchainement.
        avance = 0.14
        blocs.append({"i": i, "d": round(deb, 3), "f": round(fin, 3),
                      "at": [round(max(a - deb - avance, 0), 3) for a, b, w in g]})

    # un motif s'accroche au premier mot declencheur rencontre, une seule fois
    mdivs, mjs = [], []
    if motifs:
        vus = set()
        for i, g in enumerate(ls):
            for (a, b, w) in g:
                cle = nettoyer(w).lower()
                if cle in MOTIFS and cle not in vus:
                    vus.add(cle)
                    deb = max(a - 0.35, 0)
                    mdivs.append(
                        f'      <div id="m{len(mdivs)}" class="clip motif" '
                        f'data-start="{deb:.2f}" data-duration="2.60" '
                        f'data-track-index="2">{MOTIFS[cle]}</div>')
                    mjs.append({"id": f"m{len(mdivs)-1}", "d": round(deb, 2)})
                    break

    # Lucas : le cartouche est reserve au carre. Ailleurs il masquerait le sujet.
    if titre and fmt not in LETTERBOX:
        titre = None
    carte_html = ""
    if titre:
        carte_html = (f'      <div id="carte" class="clip carte" data-start="0" '
                      f'data-duration="{CARTE_DUREE}" data-track-index="3">'
                      f'<div class="boite"><svg><path id="soulignage" '
                      f'fill="var(--ob-blanc,#fff)"></path></svg>'
                      f'<span class="carte-in">{titre_html(titre)}</span>'
                      f'</div></div>')

    doc = f"""<!doctype html>
<html lang="fr" data-resolution="{'portrait' if lh>lw else ('square' if lw==lh else 'landscape')}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={lw}, height={lh}" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <link rel="stylesheet" href="./assets/charte-offbound/offbound.css" />
    <style>{css(lw, lh, fmt, bande)}{css_blend() if blend else ""}{css_motif(lw, lh) if motifs else ""}{css_carte(lw, lh, fmt, bande) if titre else ""}</style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{d:.2f}"
         data-width="{lw}" data-height="{lh}" data-fps="30"
         style="isolation:isolate">

      <video id="plan" class="clip" data-start="0" data-duration="{d:.2f}"
             data-track-index="0" src="./assets/media/plan.mp4"
             data-volume="1" data-has-audio="true"
             style="width:{lw}px;height:{lh}px;object-fit:cover"></video>

{carte_html}
{chr(10).join(mdivs)}
{chr(10).join(divs)}
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const B = {json.dumps(blocs, ensure_ascii=False)};
      const tl = gsap.timeline({{paused:true}});
      for (const b of B) {{
        b.at.forEach((at, j) => {{
          const w = document.getElementById("w" + b.i + "_" + j);
          if (!w) return;
          tl.fromTo(w,
            {{opacity:0, "--hf-word-blur":"14px", "--hf-word-scale":1.09,
              "--hf-word-y":"{round(lh*0.009)}px"}},
            {{opacity:1, "--hf-word-blur":"0px", "--hf-word-scale":1,
              "--hf-word-y":"0px", duration:0.34, ease:"power3.out"}},
            b.d + at);
        }});
        const sortie = Math.max(b.d + 0.16, b.f - 0.11);
        b.at.forEach((at, j) => {{
          const w = document.getElementById("w" + b.i + "_" + j);
          if (w) tl.to(w, {{opacity:0, "--hf-word-blur":"9px",
                            "--hf-word-scale":0.97,
                            "--hf-word-y":"-{round(lh*0.006)}px",
                            duration:0.17, ease:"power2.in"}}, sortie);
        }});
      }}
      // cartouche d'accroche : entree douce, sortie qui s'efface vers le haut
{soulignage_js(min(lw, lh)) if titre else ""}
      const carte = document.getElementById("carte");
      if (carte) {{
        tl.fromTo(carte, {{opacity:0, y:{round(lh*0.016)}, scale:0.96}},
                         {{opacity:1, y:0, scale:1,
                           duration:0.42, ease:"power3.out"}}, 0.10);
        tl.to(carte, {{opacity:0, y:-{round(lh*0.012)}, scale:0.98,
                       duration:0.32, ease:"power2.in"}}, {CARTE_DUREE} - 0.34);
      }}

      // motifs : trace qui se dessine, derive lente, sortie en fondu
      const M = {json.dumps(mjs, ensure_ascii=False)};
      for (const m of M) {{
        const el = document.getElementById(m.id);
        if (!el) continue;
        const traits = el.querySelectorAll("path, circle");
        tl.fromTo(el, {{opacity:0, scale:0.86, rotation:-9}},
                      {{opacity:0.17, scale:1, rotation:3,
                        duration:1.5, ease:"power2.out"}}, m.d);
        traits.forEach((t, k) => tl.fromTo(t,
          {{strokeDashoffset:1200}},
          {{strokeDashoffset:0, duration:0.95, ease:"power2.inOut"}},
          m.d + 0.10 + k * 0.16));
        tl.to(el, {{opacity:0, scale:1.10, rotation:7,
                    duration:0.55, ease:"power2.in"}}, m.d + 2.05);
      }}
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""
    open(os.path.join(projet, "index.html"), "w", encoding="utf-8").write(doc)
    json.dump({"name": os.path.basename(projet), "fps": 30, "width": lw, "height": lh},
              open(os.path.join(projet, "meta.json"), "w"), indent=2)
    moy = sum(len(g) for g in ls) / max(len(ls), 1)
    print(f"  {lw}x{lh}  {d:.1f}s  {len(divs)} lignes  ({moy:.1f} mots/ligne)")


if __name__ == "__main__":
    generer(sys.argv[1], sys.argv[2], sys.argv[3],
            sys.argv[4] if len(sys.argv) > 4 else "9x16",
            blend="--blend" in sys.argv, motifs="--motifs" in sys.argv,
            titre=(sys.argv[sys.argv.index("--titre") + 1]
                   if "--titre" in sys.argv else None),
            vignette="--vignette" in sys.argv)
