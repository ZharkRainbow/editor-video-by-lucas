# Architecture

Ce document explique **comment la chaine est construite et pourquoi**. Les
pieges rencontres et leurs causes sont dans `notes-techniques.md` ; l'historique
des retours qui ont faconne les reglages est dans `journal-des-retours.md`.

---

## 1. Le probleme

On part de rushes longs : un consulting filme de 12 a 30 minutes, une
masterclass de 25 minutes en deux flux (camera + capture d'ecran). On doit en
sortir des reels de 15 a 130 secondes, en deux formats (9:16 et 16:9), avec
sous-titres, titre incruste, son masterise et lit musical.

Fait a la main dans un logiciel de montage, c'est une journee par lot de vingt.
Et surtout, **rien n'est reproductible** : un reglage change, il faut tout
refaire a la souris.

## 2. Le principe : le montage est une fonction, pas un geste

Chaque clip est entierement decrit par des donnees :

```
(rush, borne_debut, borne_fin, [segments], titre, accroche, cadrage)
```

Tout le reste est deterministe. On peut donc regenerer n'importe quel fichier a
l'identique, ou changer un reglage et repasser les 80 fichiers.

C'est ce qui a sauve la journee du 10/09 : quand on a decouvert que le
debruitage n'avait jamais tourne, il a suffi de relancer la chaine. Aucun
travail manuel n'a ete perdu, parce qu'il n'y en avait pas.

**Corollaire, et c'est la regle la plus importante du projet :** tout ce qui
n'est pas dans les donnees doit etre reproductible par le code. Un reglage
tape a la main dans une commande ponctuelle est un reglage perdu.

## 3. Les contraintes de l'environnement, qui structurent tout

Elles ne sont pas des details : elles expliquent des pans entiers du code.

**ffmpeg n'a ni `drawtext` ni `subtitles`.** Ce build est compile sans libass ni
freetype. Impossible d'incruster du texte avec ffmpeg. Tout le texte passe donc
par ImageMagick : chaque caption est rendue en PNG transparent, les PNG sont
assembles en un flux alpha, et un seul `overlay` les pose sur la video. C'est
plus lourd a ecrire, mais ca donne le controle exact de la typo, du contour et
du halo.

**Dans `crop`, ffmpeg n'evalue `w` et `h` qu'une seule fois.** Seuls `x` et `y`
peuvent dependre de `t`. Un zoom anime est donc impossible par ce chemin : le
cadrage peut se deplacer, pas changer de taille. L'outil de recadrage impose
pour cette raison un ratio verrouille.

**Le decodage 4K HEVC est lent.** Un `-ss` place **avant** `-i` fait un seek
rapide ; place apres, ffmpeg decode depuis la seconde zero. Sur un rush de 30
minutes, l'ecart est de quinze minutes a quelques secondes. Toute coupe doit
seek avant d'ouvrir le fichier.

**`SimpleHTTPRequestHandler` ne gere pas les requetes Range.** Sans elles, une
balise `<video>` ne peut pas se deplacer dans un fichier. C'est ce qui a casse
l'outil de recadrage pendant des heures, et aucun correctif cote client ne
pouvait y remedier.

## 4. La chaine, etape par etape

### 4.1 Transcrire

`whisper.cpp`, modele `ggml-large-v3-turbo`. Deux usages tres differents :

- **Le transcript du long format** sert a chercher et a decider. Segments longs.
- **Les captions d'un clip** sont produites en **re-transcrivant le clip**, pas
  en decoupant le SRT du long format. Un decoupage reintroduit une derive de
  calage ; whisper relance sur le clip donne des timecodes cales sur ce clip.

Deux calibrages : `-ml 19` pour le vertical (3 a 4 mots), `-ml 46` pour
l'horizontal (7 a 8 mots). Au-dela, la contrainte "une seule ligne" force une
reduction de taille qui rend le texte illisible.

Un troisieme usage, `-ml 1`, donne du mot-a-mot : c'est ce qui permet de caler
une borne au mot pres.

### 4.2 Retrouver un passage sans timecodes

`retrouver-passage.py`. Cas reel : Opus Clip fournit le texte d'un extrait, pas
sa position. On aligne les deux listes de mots normalisees avec
`difflib.SequenceMatcher`, on fusionne les blocs proches, et on rend les
segments **avec un taux de couverture**.

Le taux fait partie du livrable : **sous 85 %, les frontieres internes ne sont
pas fiables** et il vaut mieux livrer le bloc englobant que de fausses bornes.

### 4.3 Choisir et couper

`decouper-selection.py` produit des extraits de validation en 1080p, ranges par
priorite. Le montage final repart toujours de la 4K via les memes bornes.

Le format des bornes accepte une liste de **segments** : plusieurs morceaux a
recoller, pour retirer une hesitation ou une reprise. Chaque jointure recoit un
fondu audio de 40 ms, sans quoi elle claque.

### 4.4 Caler au mot pres

`affiner-bornes.py`. L'interpolation lineaire dans un segment SRT donne **1 a
2 secondes d'erreur** : assez pour demarrer sur la fin de la phrase precedente
ou couper un mot. On retranscrit une fenetre de +/- 8 s en mot-a-mot et on
recale sur le mot cible.

`auditer-debuts.py` transcrit les 4 premieres secondes de tout un lot : c'est ce
qui revele les clips qui ouvrent sur "Magnifique", sur une relance ou sur une
phrase plate. `recouper-debut.py` deplace la borne et **regenere toute la
chaine**, captions comprises, qui sinon resteraient calees sur l'ancienne duree.

### 4.5 Composer

**Vertical consulting** (`monter-vertical-consulting.py`) : split screen a deux
etages, 1080x1920. Le cadrage est cale a l'image et identique sur les cinq
consultings, le client etant toujours a gauche du cadre source et Valentin a
droite. On repart du 4K : recadrer une personne dans du 1080p donnerait un
500x960 upscale.

**Horizontal** (`refaire-horizontal-consulting.py`) : coupe, mise a l'echelle,
captions, en une seule passe. Une passe unique evite le defaut classique des
deux incrustations successives, invisibles a l'oeil mais qui empilent deux
encodages.

**Masterclass** (`rendre-depuis-points.py`) : la vue partagee camera + ecran
bouge en permanence, un crop fixe rend illisible la moitie des passages. D'ou
l'outil de recadrage.

### 4.6 Cadrer a la main

`outil-recadrage/` : un serveur Python et une page. Lucas pose des **points de
cadrage horodates** sur une timeline, l'outil ecrit un JSON, le rendu applique
les cadrages.

Deux decisions importantes :

- **Palier par defaut, glissement en option.** L'interpolation continue entre
  deux points produit une derive permanente que personne n'a demandee. Un
  cadrage tient jusqu'au point suivant, sauf si le point est explicitement
  marque "glisse".
- **Un seul proxy pour les deux flux.** Les deux rushes sont assembles cote a
  cote dans un proxy 1280x360 avec l'audio. Deux videos separees ne restent
  jamais synchrones dans un navigateur.

### 4.7 Traiter le son

Deux chaines, et **elles different par decision, pas par accident** :

| | Consulting | Masterclass |
|---|---|---|
| Debruitage | DeepFilterNet, -25 dB | **aucun** |
| Traitement de timbre | chaine voix v2 | **aucun** |
| Loudness | -14 LUFS | -14 LUFS |
| Musique | -34 LUFS gain fixe | -34 LUFS gain fixe |

La masterclass est filmee en interieur avec peu de bruit, et Valentin veut son
micro tel quel. Seule la normalisation de volume est gardee, parce que le rush
est a -23,3 LUFS et serait inpubliable a cote du reste.

La chaine voix v2 : coupe-bas 85 Hz, `adeclick` pour les claquements de langue,
creux de 2 dB a 250 Hz, `deesser`, creux de 2,5 dB a 6,5 kHz, compresseur
2.5:1 a -20 dB, limiteur a 0,93, puis loudnorm.

**Il n'y a pas de boost de presence a 4 kHz, et il ne faut jamais en remettre :**
cette bande est exactement celle des bruits de bouche.

### 4.8 Poser la musique

`ajouter-musique.py`. Le lit est pose a **gain fixe**, mesure une fois sur la
piste puis applique constant. Aucun traitement dynamique.

Un `sidechaincompress` ou un `loudnorm` a large plage fait remonter la musique
dans les silences : elle disparait sous la voix puis surgit entre deux phrases.
C'est le premier defaut que Lucas a entendu, et la raison de cette regle.

L'attribution est deterministe : `pistes[i % len(pistes)]` sur la liste triee
des clips. Elle se reproduit donc a l'identique, ce qui a permis de retrouver
quel morceau allait sur quel clip apres coup.

`monter-volume-musique.py` change le niveau **sans tout refaire** : le lit etant
deterministe, il suffit de reposer le meme lit au niveau qui complete la somme.
De -40 a -34, c'est exactement le meme lit une seconde fois. Verifie identique a
un rendu refait depuis la voix seule.

## 5. Les formats de donnees

**`clips-timecodes.json`** — la source de verite des bornes.
```json
{"Client": [["titre", debut, fin], ["titre", debut, fin, [[a,b],[c,d]]]]}
```
Le quatrieme element, optionnel, porte les segments a recoller.

**`accroches-consulting.json`** — le titre incruste, indexe par titre de clip.
Distinct du nom de fichier : le nom decrit, l'accroche accroche.

**`cadrages/<passage>.json`** — les points de cadrage horodates de l'outil.

**Les metadonnees du fichier lui-meme** portent l'historique du traitement, et
c'est ce qui rend la chaine auditable : `debruit25 + voix v2 + musique -34`.

## 6. Les invariants a ne jamais casser

1. **Un traitement qui echoue ne doit rien ecrire.** Le repli silencieux vers
   l'entree non traitee produit un fichier d'apparence normale, et le defaut ne
   se voit qu'a l'ecoute, des semaines plus tard.
2. **Tout script qui ecrit en place pose un marqueur, en l'empilant** sur les
   marqueurs existants. Ecraser le commentaire efface l'historique.
3. **La video n'est jamais reencodee pour une correction de son.** `-c:v copy`.
4. **Ne jamais passer DeepFilterNet sur un fichier ou la musique est deja
   mixee.** Il traite tout ce qui n'est pas de la parole comme du bruit.
5. **La musique se pose a gain fixe.** Jamais de ducking.
6. **Verifier sur le fichier produit, pas sur l'intention du code.** Chaque
   etape a son verificateur : transcription du debut et de la fin, mesure du
   plancher de bruit, position du texte dans l'image.

## 7. Comment on s'en sert, concretement

Le parcours reel d'un chantier, tel qu'il s'est deroule sur Gauthier et Florian :

1. Transcrire le rush.
2. Lire le transcript et **choisir les passages**. C'est le seul moment ou le
   jugement editorial compte : reperer un hook, un chiffre, un contre-pied.
3. Caler les bornes au mot pres, decouper des extraits de validation en 1080p,
   les ranger par priorite.
4. **Lucas regarde et tranche.** Il valide, retire, et demande des recadrages de
   debut. C'est la que se joue la qualite.
5. Generer les captions, corriger les fautes de transcription.
6. Monter les deux formats.
7. Traiter le son, poser la musique.
8. Verifier, mesurer, corriger.

Le temps se concentre sur les etapes 2 et 4. Tout le reste est de la mecanique.

## 8. Ce qu'il faut faire pour en faire une application

Par ordre de valeur :

**1. Sortir les chemins en dur.** `config.py` existe mais plusieurs scripts ne
l'utilisent pas encore. C'est le prerequis a tout le reste.

**2. Une interface pour le son.** Le besoin est demontre : trois allers-retours
pour trouver un niveau de musique qui se serait tranche en dix secondes avec un
curseur. Plan retenu : Web Audio API pour le reglage en direct sur un extrait,
puis rendu ffmpeg cote serveur une fois le reglage valide.

**3. Un etat de projet unique.** Aujourd'hui l'information est repartie entre
`clips-timecodes.json`, `accroches-consulting.json`, `cadrages/` et les
metadonnees des fichiers. Une application aurait besoin d'un seul etat.

**4. Un journal d'execution persistant.** Les journaux vivent dans la sortie des
commandes. Il a fallu fouiller un transcript de session pour retrouver quelle
musique allait sur quel clip.

**5. Rendre les verificateurs systematiques.** Ils existent tous mais se lancent
a la main. Une application les enchainerait apres chaque rendu.
