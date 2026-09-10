# montage-video

Chaine de montage video pilotee par script : transformer des rushes longs en
reels verticaux et horizontaux, sans ouvrir de logiciel de montage.

Tout se fait en ligne de commande, sauf le cadrage, qui passe par une petite
interface web locale. Rien ne sort de la machine.

## Ce que ca fait, dans l'ordre d'un chantier reel

| Etape | Script | Ce qu'il resout |
|---|---|---|
| 1. Transcrire | whisper.cpp (`ggml-large-v3-turbo`) | rendre le rush cherchable |
| 2. Retrouver un passage | `retrouver-passage.py` | localiser un extrait dont on n'a que le texte |
| 3. Choisir les extraits | `decouper-selection.py` | couper des extraits de validation, avec mini-cuts |
| 4. Caler au mot pres | `affiner-bornes.py` | supprimer les 1 a 2 s d'erreur de l'interpolation |
| 5. Verifier | `controler-extraits.py` | transcrire debut et fin de chaque extrait |
| 6. Sous-titrer | `faire-captions.py` | un SRT par clip, calibre vertical ou horizontal |
| 7. Composer | `monter-vertical-*.py`, `refaire-horizontal-*.py` | split screen, recadrage, incrustation |
| 8. Cadrer a la main | `outil-recadrage/` | points de cadrage horodates, dans le navigateur |
| 9. Traiter le son | `masteriser-audio.py`, `affiner-voix.py` | debruitage, de-esser, loudness |
| 10. Verifier le son | `diagnostic-debruitage.py` | dire si le debruitage a reellement ete applique |
| 11. Poser la musique | `ajouter-musique.py` | lit musical a gain fixe, jamais de ducking |

## Demarrage

```bash
python3 outil-recadrage/serveur.py      # http://localhost:8765
```

Les proxys video ne sont pas versionnes (trop lourds). Les regenerer :

```bash
ffmpeg -i RUSH.mp4 -vf scale=640:360 -c:v libx264 -crf 28 -preset veryfast \
  -g 10 -keyint_min 10 -sc_threshold 0 -an outil-recadrage/proxy.mp4
```

Le `-g 10` est **indispensable** : sans lui, une image-cle toutes les 8 s rend
le deplacement dans la timeline inutilisable.

## Dependances

- `ffmpeg` et `ffprobe`
- `whisper-cli` (whisper.cpp) + le modele `ggml-large-v3-turbo`
- `deep-filter` (DeepFilterNet 0.5) pour le debruitage vocal
- ImageMagick (`magick`) pour le rendu du texte

Ce build de ffmpeg n'a **ni `drawtext` ni `subtitles`** (compile sans libass ni
freetype). Tout le texte passe donc par ImageMagick, en PNG, puis par un seul
`overlay`. C'est une contrainte structurante du projet, pas un detour.

## Configuration

`config.py` centralise les chemins et la charte. C'est le seul fichier a
adapter sur une autre machine. Plusieurs scripts portent encore leurs chemins
en dur : les faire tous passer par `config.py` est le premier chantier a mener
avant d'en faire une application.

## Documentation

| Fichier | Ce qu'il contient |
|---|---|
| `docs/architecture.md` | comment la chaine est construite et **pourquoi**, les contraintes de l'environnement, les formats de donnees, les invariants, la feuille de route |
| `docs/journal-des-retours.md` | chaque reglage avec le retour qui l'a produit : ne pas defaire un reglage par ignorance |
| `docs/notes-techniques.md` | les pieges rencontres avec leur cause, et l'annexe sur l'outil de recadrage |

Lire `architecture.md` en premier si vous reprenez le projet.

## Regles apprises a la dure

Elles sont detaillees dans `docs/notes-techniques.md`, avec leur cause. Les
plus couteuses :

- Dans `crop`, ffmpeg n'evalue `w` et `h` qu'une fois. Seuls `x` et `y` peuvent
  dependre de `t`. Un zoom anime est donc impossible par ce chemin.
- `SimpleHTTPRequestHandler` ne gere pas les requetes Range. Sans elles, une
  balise `<video>` ne peut pas se deplacer dans le fichier.
- Un script qui traite du son doit **echouer bruyamment**. Un debruitage
  silencieusement saute produit un fichier d'apparence normale, et le defaut ne
  se voit qu'a l'ecoute, des semaines plus tard.
- Tout script qui ecrit en place doit poser un marqueur dans les metadonnees,
  sans quoi rien ne prouve son passage.
- Le lit musical se pose a **gain fixe**. Un `sidechaincompress` ou un
  `loudnorm` a large plage le fait remonter dans les silences.
