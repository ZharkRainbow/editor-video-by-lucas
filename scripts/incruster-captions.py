#!/usr/bin/env python3
"""Incruste les captions d'un SRT dans une video.

Ce build de ffmpeg n'a ni drawtext ni subtitles (pas de libass, pas de
freetype). On rend donc chaque caption en PNG transparent avec ImageMagick,
qui sait charger ZT Nature par chemin de fichier, et on empile le tout en un
flux alpha unique passe a overlay. Une seule passe de filtrage, pas de chaine
de cent overlays.

    python3 incruster-captions.py clip.mp4 captions.srt sortie.mp4 [--y 0.86]
"""
import subprocess
import sys
import tempfile
from pathlib import Path

# Style releve au pixel sur le montage de reference de Lucas
# (~/Downloads/MONTAGE-Amory-LinkedIn-SANS-BLUR.mp4, mesure le 09/09) :
# captions jaunes #FAD400 en italique, casse de 33 px sur 1920, a y=0.4513 ;
# bandeau titre bleu charte a y=0.4997, visible seulement les 5 premieres s.
POLICE = Path.home() / "Library/Fonts/ZTNature-MediumItalic.otf"
POLICE_TITRE = Path.home() / "Library/Fonts/ZTNature-Bold.otf"
BLEU = "#2322E0"
JAUNE = "#FAD400"
TITRE_DUREE = 5.0
HALO = False   # active par --halo : ombre floue au lieu du contour net


def accroche_png(texte, W, H, y_rel, taille, tmp):
    """Bandeau titre : une seule ligne, fin, comme le montage de reference.

    Mesure sur MONTAGE-Amory-LinkedIn-SANS-BLUR.mp4 : hauteur totale 71 px sur
    1920, largeur ~81 % du cadre, texte blanc sur aplat bleu charte. Jamais deux
    lignes : si le texte est trop long, c'est la taille qui baisse.
    """
    largeur_max = int(W * 0.82)
    pt = taille
    for _ in range(16):
        r = subprocess.run(["magick", "-background", "none", "-font",
                            str(POLICE_TITRE), "-pointsize", str(pt),
                            f"label:{texte}", "-format", "%w", "info:"],
                           capture_output=True, text=True)
        try:
            if int(r.stdout) <= largeur_max - 2 * (pt // 2):
                break
        except ValueError:
            break
        pt = int(pt * 0.94)

    subprocess.run(["magick", "-background", BLEU, "-fill", "white",
                    "-colorspace", "sRGB", "-font", str(POLICE_TITRE),
                    "-pointsize", str(pt), f"label:{texte}",
                    "-bordercolor", BLEU, "-border", f"{pt // 2}x{int(pt * 0.20)}",
                    "PNG32:" + str(tmp / "acc.png")], capture_output=True)
    r = subprocess.run(["magick", "identify", "-format", "%w %h",
                        str(tmp / "acc.png")], capture_output=True, text=True)
    aw, ah = (int(x) for x in r.stdout.split())
    dst = tmp / "accroche_full.png"
    subprocess.run(["magick", "-size", f"{W}x{H}", "xc:none",
                    str(tmp / "acc.png"),
                    "-geometry", f"+{(W - aw)//2}+{int(H * y_rel - ah / 2)}",
                    "-composite", "-colorspace", "sRGB", "PNG32:" + str(dst)],
                   capture_output=True)
    return dst


def sec(t):
    h, m, r = t.split(":")
    s, ms = r.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def lire_srt(p: Path):
    out = []
    for b in Path(p).read_text(encoding="utf-8").strip().split("\n\n"):
        L = b.strip().split("\n")
        if len(L) < 3:
            continue
        a, bb = L[1].split(" --> ")
        txt = " ".join(x.strip() for x in L[2:]).strip()
        if txt:
            out.append((sec(a), sec(bb), txt))
    return out


def dim(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v",
                        "-show_entries", "stream=width,height",
                        "-of", "csv=p=0:nk=1", str(p)],
                       capture_output=True, text=True)
    w, h = r.stdout.strip().split("\n")[0].split(",")
    return int(w), int(h)


def png(texte, W, H, y_rel, taille, tmp, i):
    """Caption blanche a contour noir, centree, posee a y_rel de la hauteur."""
    dst = tmp / f"c{i:05d}.png"
    marge = int(W * 0.08)
    largeur = W - 2 * marge
    # label: ne renvoie jamais a la ligne. Si la ligne deborde, on reduit la
    # taille plutot que de casser la regle "tout sur une seule ligne".
    pt = taille
    for _ in range(12):
        r = subprocess.run(["magick", "-background", "none", "-font", str(POLICE),
                            "-pointsize", str(pt), f"label:{texte}",
                            "-format", "%w", "info:"], capture_output=True, text=True)
        try:
            if int(r.stdout) <= largeur:
                break
        except ValueError:
            break
        pt = int(pt * 0.93)
    base = ["-background", "none", "-colorspace", "sRGB",
            "-font", str(POLICE), "-pointsize", str(pt), "-gravity", "center"]
    trait = max(3, pt // 10)   # contour epaissi : le texte passe souvent sur le beige clair du Canva
    if HALO:
        # ombre noire floue plutot qu'un contour net : plus doux a l'oeil, et
        # ca detache le texte aussi bien sur le beige clair du Canva.
        # rayon large et densite faible : l'ombre se diffuse au lieu de former
        # un liseré. Comparaison faite le 10/09 sur cinq reglages.
        rayon = max(10, int(pt / 2.2))
        marge_halo = rayon * 3
        subprocess.run(["magick", *base, "-fill", "black", f"label:{texte}",
                        "-bordercolor", "none", "-border", str(marge_halo),
                        "-blur", f"0x{rayon}",
                        "-channel", "A", "-evaluate", "multiply", "1.3", "+channel",
                        "PNG32:" + str(tmp / "b.png")], capture_output=True)
        subprocess.run(["magick", *base, "-fill", JAUNE, f"label:{texte}",
                        "-bordercolor", "none", "-border", str(marge_halo),
                        "PNG32:" + str(tmp / "h.png")], capture_output=True)
    else:
        subprocess.run(["magick", *base, "-stroke", "black", "-strokewidth",
                        str(trait), "-fill", "black", f"label:{texte}",
                        "PNG32:" + str(tmp / "b.png")], capture_output=True)
        subprocess.run(["magick", *base, "-stroke", "none", "-fill", JAUNE,
                        f"label:{texte}", "PNG32:" + str(tmp / "h.png")], capture_output=True)
    subprocess.run(["magick", str(tmp / "b.png"), str(tmp / "h.png"),
                    "-gravity", "center", "-composite",
                    "-colorspace", "sRGB", "PNG32:" + str(tmp / "t.png")],
                   capture_output=True)
    r = subprocess.run(["magick", "identify", "-format", "%w %h",
                        str(tmp / "t.png")], capture_output=True, text=True)
    try:
        lt, ht = (int(v) for v in r.stdout.split())
    except ValueError:
        lt, ht = largeur, taille
    x = max(0, (W - lt) // 2)
    y = int(H * y_rel - ht / 2)
    subprocess.run(["magick", "-size", f"{W}x{H}", "xc:none",
                    str(tmp / "t.png"), "-geometry", f"+{x}+{y}",
                    "-composite", "PNG32:" + str(dst)], capture_output=True)
    return dst


def vide(W, H, tmp):
    d = tmp / "vide.png"
    if not d.exists():
        subprocess.run(["magick", "-size", f"{W}x{H}", "xc:none",
                        "PNG32:" + str(d)], capture_output=True)
    return d


def main():
    src, srt, dst = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    y_rel = 0.86
    taille_rel = 0.052
    acc_txt, acc_y = None, 0.50
    for i, a in enumerate(sys.argv):
        if a == "--y":
            y_rel = float(sys.argv[i + 1])
        if a == "--taille":
            taille_rel = float(sys.argv[i + 1])
        if a == "--accroche":
            acc_txt = sys.argv[i + 1]
        if a == "--accroche-y":
            acc_y = float(sys.argv[i + 1])
        if a == "--halo":
            globals()["HALO"] = True

    W, H = dim(src)
    taille = int(H * taille_rel)
    subs = lire_srt(srt)
    if not subs:
        sys.exit("srt vide")

    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        v = vide(W, H, tmp)
        lignes, prec = [], 0.0
        for i, (a, b, txt) in enumerate(subs):
            if a - prec > 0.04:
                lignes.append((v, a - prec))
            lignes.append((png(txt, W, H, y_rel, taille, tmp, i), b - a))
            prec = b
        liste = tmp / "l.txt"
        liste.write_text("".join(
            f"file '{p}'\nduration {d:.3f}\n" for p, d in lignes)
            + f"file '{lignes[-1][0]}'\n", encoding="utf-8")

        entrees = ["-i", str(src),
                   "-f", "concat", "-safe", "0", "-i", str(liste)]
        chaine = "[1:v]format=rgba,setsar=1[t];[0:v][t]overlay=0:0[v]"
        if acc_txt:
            ap = accroche_png(acc_txt, W, H, acc_y, taille, tmp)
            entrees += ["-loop", "1", "-t", str(TITRE_DUREE), "-i", str(ap)]
            chaine = ("[1:v]format=rgba,setsar=1[t];[2:v]format=rgba,setsar=1[a];"
                      "[0:v][t]overlay=0:0[x];"
                      f"[x][a]overlay=0:0:enable='lt(t,{TITRE_DUREE})'[v]")
        r = subprocess.run([
            "ffmpeg", "-y", *entrees,
            "-filter_complex", chaine,
            "-map", "[v]", "-map", "0:a?",
            "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-c:a", "copy", "-shortest", str(dst)], capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stderr[-1500:])
    print(f"{dst.name} : {len(subs)} captions")


if __name__ == "__main__":
    main()
