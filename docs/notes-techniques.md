# Montage video automatise — notes techniques

Etat au 2026-09-10. Chantier : transformer des rushes longs (consultings clients
du mastermind, masterclass de Valentin) en reels verticaux et horizontaux, en
pilotant ffmpeg plutot qu'en montant a la main.

Ces notes sont ecrites pour etre lisibles par quelqu'un d'autre, ou par un autre
modele, sans le contexte de la session.

## Ce qui marche bien et qu'on garde

**Retrouver un passage a partir de son texte.** Opus Clip donne le texte d'un
extrait mais pas ses timecodes. On transcrit le long format avec whisper.cpp
(`large-v3-turbo`, `-osrt`), puis on aligne le texte fourni contre le transcript
avec `difflib.SequenceMatcher` sur des listes de mots normalises. On obtient les
timecodes, ET le taux de couverture, ET les trous. Sans le taux de couverture, on
sert des timecodes faux avec l'air d'etre sur. Script `retrouver-passage.py`.

**Le taux de couverture est un livrable, pas un detail.** En dessous de ~85 %,
les frontieres internes ne sont pas fiables : Opus Clip et whisper ne transcrivent
pas pareil, donc une partie des "trous" detectes sont des artefacts d'alignement
et non de vraies coupes. Dans ce cas on livre le bloc englobant et on le dit.

**Les captions.** On re-transcrit chaque clip coupe plutot que de decouper le SRT
du long format : les segments d'un long format font 2 a 5 s, illisibles en reel,
et un decoupage reintroduit une derive de calage. `-ml 19 -sow` donne 3 a 4 mots
par caption, `-ml 72` donne 10 a 15 mots pour les formats horizontaux.

**Le mastering audio.** DeepFilterNet bride a 25 dB d'attenuation (au-dela,
l'ambiance de salle disparait et les voix sonnent artificielles), puis `loudnorm`
en deux passes vers -14 LUFS / -1,5 dBTP. La video n'est jamais reencodee, seule
la piste audio est remplacee.

## Pieges rencontres, avec leur cause

**ffmpeg sans libass.** Le build Homebrew de la machine n'a ni `drawtext` ni
`subtitles`. Contournement : rendre chaque caption en PNG transparent avec
ImageMagick, empiler le tout en un flux alpha via le demuxer `concat`, et faire
un seul `overlay`. Une seule passe de filtrage, pas une chaine de cent overlays.

**ImageMagick optimise en niveaux de gris.** Un calque de texte ecrit sans
`PNG32:` ressort en `colorspace=Gray`. Le composite herite du colorspace du
premier calque, et un texte jaune devient blanc, silencieusement. Forcer `PNG32:`
sur CHAQUE calque et sur la fusion.

**`label:` contre `caption:`.** `caption:` renvoie a la ligne et produit une image
de la largeur demandee, donc le texte est centre par effet de bord. `label:` tient
sur une ligne mais produit une image a la largeur du texte : il faut centrer
explicitement, sinon tout se colle a gauche. Le passage de l'un a l'autre casse le
centrage sans prevenir.

**Un lot qui ecrit en place n'est pas reprenable.** Un lot interrompu puis relance
a double les incrustations sur 15 fichiers : deux couches de sous-titres
parfaitement superposees, donc invisibles, et deux encodages. Depuis, le script de
musique ecrit un marqueur dans les metadonnees et refuse de repasser.

**Un glob zsh sans correspondance interrompt le script.** Un dossier vide a suffi
a tuer un lot en cours. `setopt NULL_GLOB`.

**Le ducking fait pomper la musique.** `sidechaincompress` baisse la musique sous
la voix, mais la remonte dans chaque silence et chaque respiration : a l'ecoute,
elle est forte par moments et absente a d'autres. Un `loudnorm` sur la musique
aggrave le probleme en remontant aussi les passages calmes du morceau. La bonne
methode est un GAIN FIXE : mesurer la piste une fois, appliquer `volume=XdB`
constant. Cible -36 LUFS, soit ~21 dB sous la voix.

**Un crop fixe ne tient pas sur un enregistrement d'ecran.** L'orateur deplace et
zoome sa vue en permanence. Un cadrage valide sur un passage rend les autres
illisibles. Il faut mesurer la zone occupee par frame echantillonnee et cadrer
dessus, ou laisser un humain poser des points de cadrage horodates.

**Le seek dans un proxy depend de l'intervalle entre images-cles.** Un proxy
encode par defaut a une image-cle toutes les 250 frames, soit 8 s : chaque
deplacement dans la timeline force le navigateur a decoder jusqu'a 250 images, et
l'interface parait buguee. `-g 10 -keyint_min 10 -sc_threshold 0` donne une
image-cle tous les tiers de seconde et rend le seek instantane. Le fichier grossit,
c'est sans importance en local.

## L'outil de recadrage

`OFFBOUND/APPS/video-reels/outil-recadrage/`, servi par `python3 -m http.server 8765`.

Page HTML autonome. Charge deux proxys 640x360 synchrones, affiche un cadre
redimensionnable par source au ratio impose par le format de sortie, et rend
l'apercu du montage final dans un canvas en temps reel. Les cadrages se posent
sur une timeline sous forme de points horodates, editables, avec interpolation
lineaire entre deux points. L'export est un JSON en coordonnees du 4K source.

Le navigateur ne lit pas le HEVC 4K, d'ou les proxys. Les valeurs restent en
coordonnees source, donc le rendu final se fait en pleine resolution.

## Ce qui n'a pas marche

**HyperFrames n'est pas un editeur.** `hyperframes preview` lance un studio de
previsualisation d'une composition HTML/CSS/GSAP, pas une timeline ou l'on
recadre a la souris. Utile pour rendre une composition ecrite, inutile pour du
montage interactif.

## Reglages valides par Lucas

| Element | Valeur |
|---|---|
| Captions | #FAD400, ZT Nature MediumItalic, une seule ligne, centrees |
| Taille | 0.023 de la hauteur en vertical, 0.028 en horizontal |
| Bandeau titre | bleu #2322E0, une ligne, fin, visible 5 s puis disparait |
| Position | captions a y=0.4513, bandeau a y=0.4997 |
| Vertical masterclass | **50/50** camera en haut, ecran en bas |
| Vertical consulting | deux etages, Valentin en haut, client en bas |
| Musique | -36 LUFS gain fixe, sans ducking |
| Voix | -14 LUFS / -1,5 dBTP |

Reference de style : `~/Downloads/MONTAGE-Amory-LinkedIn-SANS-BLUR.mp4`.

---

# Annexe : l'outil de recadrage, code et pieges

Ajoute le 2026-09-10. Cette annexe est ecrite pour qu'un autre modele puisse
reprendre le code sans le contexte des echanges.

## Le probleme que l'outil resout

Un reel split screen assemble deux sources : la camera de l'orateur et sa
capture d'ecran. La camera se cadre une fois pour toutes, mais **la capture
d'ecran non** : l'orateur deplace et zoome sa vue en permanence. Un cadrage
fixe rend illisible la moitie des passages.

Il faut donc des cadrages horodates, poses par un humain qui voit l'image, et
un moteur qui les applique au rendu. C'est ce que fait cet outil.

## Architecture

Une page HTML sans dependance, servie par un `ThreadingHTTPServer` Python qui
accepte en plus un `POST /enregistrer` pour recevoir les cadrages sans
copier-coller. Trois elements media : deux `<video>` (les proxys) et un
`<audio>`. Un `<canvas>` redessine le montage final a chaque frame via
`drawImage(video, sx,sy,sw,sh, dx,dy,dw,dh)`.

Les cadrages sont stockes en coordonnees du 4K source, pas du proxy. L'outil
convertit a l'affichage. Le rendu final se fait donc en pleine resolution.

## Les quatre pieges de synchronisation, dans l'ordre ou ils sont apparus

**1. Le seek etait lent et l'interface paraissait figee.**
Cause : les proxys avaient une image-cle toutes les 250 frames (8 s). Chaque
deplacement forcait le decodage de centaines d'images.
Correctif : reencoder avec `-g 10 -keyint_min 10 -sc_threshold 0`, soit une
image-cle tous les tiers de seconde. Le fichier grossit de 50 %, sans
importance en local.

**2. Le seek pendant la lecture desynchronisait l'image et le son.**
Cause : repositionner trois elements qui jouent ne les remet pas d'accord, et
l'audio repart immediatement pendant que les videos decodent encore.
Correctif : mettre les trois en pause, repositionner, **attendre l'evenement
`seeked` des trois**, puis relancer.

**3. Les trois elements derivaient en lecture.**
Cause : trois lecteurs independants ne restent jamais alignes.
Correctif : l'audio devient la reference, les images se recalent sur lui.
Recaler l'image sur le son et jamais l'inverse : un saut d'image ne s'entend
pas, un saut de son s'entend immediatement.

**4. L'image restait figee sur les premieres frames, en boucle.**
Cause, et c'est le piege le plus subtil : le correctif du point 3 forcait
`video.currentTime = t` toutes les 300 ms. Or **un seek prend souvent plus de
300 ms**. On relancait donc un seek avant la fin du precedent, indefiniment.
La video passait son temps a chercher et n'affichait jamais rien de nouveau.
Correctif en trois parties :
  - ne rien faire tant que `video.seeking` est vrai ou `readyState < 3` ;
  - ne seeker que sur un ecart franc (> 0,6 s) ;
  - rattraper les petites derives par **`playbackRate`** (entre 0,90 et 1,10),
    ce qui n'interrompt jamais le decodage.

Regle generale : sur un media, corriger une derive par la vitesse, pas par la
position. La position ne sert qu'aux grands sauts.

## L'interpolation entre points : palier par defaut

Premiere version : le cadrage glissait lineairement d'un point au suivant.
Rejete a l'usage : poser "tout a gauche" a 8 s puis autre chose a 47 s
produisait une derive continue de 39 secondes que personne n'avait demandee.

Regle retenue : **le cadrage TIENT jusqu'au point suivant, puis saute**. Le
glissement existe toujours mais devient une option cochee point par point
(`"glisse": true` dans le JSON).

Lecon transposable : dans un editeur de keyframes, le defaut doit etre le
maintien. L'interpolation est un effet, pas un comportement de base.

## Format d'echange

```json
{
  "format": "vmc",
  "passage": "VAL 1 — ...",
  "source": {"w": 3840, "h": 2160},
  "points": [
    {"t": 2.74, "glisse": false,
     "camera": {"x": 311, "y": 0, "w": 2430, "h": 2160},
     "ecran":  {"x": 1325, "y": 0, "w": 2430, "h": 2160}}
  ]
}
```

`format` : `vmc` (vertical 50/50), `hmc` (horizontal), `vcons` (consulting,
deux etages depuis un seul rush).

## Le rendu : contrainte ffmpeg a connaitre

Dans le filtre `crop`, **`w` et `h` sont evalues une seule fois**, seuls `x` et
`y` peuvent dependre de `t`. On ne peut donc pas animer un zoom via `crop`.
`rendre-depuis-points.py` le detecte, prend la plus grande taille et le signale.
Pour un vrai zoom anime il faudrait `zoompan` ou `scale` + `overlay` animes.

Les expressions produites sont des `if(lt(t,T),valeur,...)` imbriques, avec le
temps relatif au debut de l'extrait puisque `-ss` remet l'horloge a zero.

## Pistes non explorees

- Detection automatique de la zone utile de l'ecran (mesure des pixels non
  uniformes sur des frames echantillonnees) pour pre-remplir les points.
- Zoom anime, qui demanderait de sortir de `crop`.
- Rendu de previsualisation basse resolution pour valider avant le rendu final.
