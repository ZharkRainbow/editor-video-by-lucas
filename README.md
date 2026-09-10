# offbound-montage-video

Chaine de montage video pilotee par script : transformer des rushes longs en
reels verticaux et horizontaux, sans passer par un logiciel de montage.

Depot volontairement separe de `RAIZ-Claude` pour pouvoir etre developpe seul.

## Ce que ca fait

1. **Transcrire** un long format (whisper.cpp)
2. **Retrouver un passage** a partir de son seul texte, sans timecodes
3. **Couper** le passage dans le rush 4K
4. **Composer** un split screen (camera + capture d'ecran, ou deux personnes)
5. **Cadrer** interactivement dans le navigateur, avec des points horodates
6. **Sous-titrer**, poser un titre, masteriser le son, poser un lit musical

## Demarrage

```bash
python3 outil-recadrage/serveur.py      # http://localhost:8765
```

Les proxys video ne sont pas versionnes (trop lourds). Les regenerer :

```bash
ffmpeg -i RUSH.mp4 -vf scale=640:360 -c:v libx264 -crf 28 -preset veryfast \
  -g 10 -keyint_min 10 -sc_threshold 0 -an outil-recadrage/proxy-camera.mp4
```

Le `-g 10` est **indispensable** : sans lui, une image-cle toutes les 8 s rend
tout deplacement dans la timeline insupportable.

## Arborescence

```
config.py              chemins et charte, seul fichier a adapter
outil-recadrage/       page de cadrage + serveur qui recoit les cadrages
  index.html           tout l'outil, sans dependance
  serveur.py           sert les fichiers et accepte POST /enregistrer
cadrages/              les JSON envoyes depuis l'outil
scripts/               la chaine de montage
docs/                  notes techniques
```

## Les scripts

| Script | Role |
|---|---|
| `retrouver-passage.py` | aligne un texte sur un SRT et rend les timecodes + le taux de couverture |
| `faire-captions.py` | re-transcrit chaque clip en captions courtes |
| `incruster-captions.py` | grave les captions et le bandeau titre (PNG + overlay) |
| `corriger-transcript.py` | dictionnaire du vocabulaire Offbound |
| `masteriser-audio.py` | debruitage + normalisation -14 LUFS |
| `ajouter-musique.py` | lit musical a gain fixe, marqueur anti-doublon |
| `rendre-depuis-points.py` | rend un extrait en appliquant les cadrages de l'outil |
| `monter-vertical-consulting.py` | split deux etages, un rush, deux personnes |
| `monter-vertical-masterclass.py` | 50/50 camera et ecran |
| `fusionner-split-screen.py` | recolle deux exports CapCut complementaires |

## Dependances

ffmpeg, ffprobe, ImageMagick (`magick`), whisper.cpp (`whisper-cli`),
DeepFilterNet (`deep-filter`), Python 3.

**Le ffmpeg de la machine n'a ni `drawtext` ni `subtitles`** : tout le texte
passe par ImageMagick. Voir `docs/notes-techniques.md`.

## A lire avant de toucher au code

`docs/notes-techniques.md` recense les pieges rencontres et leur cause. Chacun
a coute une iteration ratee.
