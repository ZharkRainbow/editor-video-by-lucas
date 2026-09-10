#!/bin/zsh
# Version HORIZONTALE. Le cadrage doit avoir ete fait dans l'outil en mode
# Horizontal : les ratios de cadre ne sont pas les memes qu'en vertical.
#   ./rendre-val.sh 2
# Le fichier atterrit dans Vertical/Selection Valentin (Opus Clip)/.
setopt NULL_GLOB
N=$1
[[ -z "$N" ]] && { echo "usage : rendre-val.sh <numero de 1 a 7>"; exit 1 }

S=/Users/lucasdo./Documents/RAIZ-Claude/OFFBOUND/APPS/video-reels/scripts
C=/Users/lucasdo./Documents/RAIZ-Claude/OFFBOUND/APPS/video-reels/outil-recadrage/cadrages
M="/Users/lucasdo./Movies/CapCut/Valentin Masterclass"

# titres exacts de Valentin et bornes dans le long format
titres=("Mes systemes pour recruter des A-players"
        "Les 5 premiers recrutements sont les + importants"
        "La formule pour savoir combien payer son equipe"
        "Les maths derriere un excellent (ou mauvais) recrutement"
        "Funnel de recrutement = Funnel de vente"
        "J'ai eu +100 candidatures sur mon dernier recrutement"
        "J'ai envoye 450 messages pour un seul recrutement")
debuts=(0 176.5 442.0 649.7 728.0 903.0 1045.9)
fins=(63.5 259.3 544.6 739.5 808.1 974.5 1084.0)

T="${titres[$N]}"; D="${debuts[$N]}"; F="${fins[$N]}"
json=("$C"/"VAL $N —"*.json)
# on refuse un cadrage vertical, il donnerait un cadre au mauvais ratio
if ! grep -q '"format": *"hmc"' "$json[1]" 2>/dev/null; then
  echo "Ce cadrage n'est pas au format Horizontal. Dans l'outil, clique le bouton"
  echo "Horizontal AVANT de poser les cadrages, puis renvoie."; exit 1
fi
[[ -z "$json" ]] && { echo "aucun cadrage envoye pour VAL $N"; exit 1 }
nom="VAL $N - Valentin $T"

python3 $S/rendre-depuis-points.py "$json[1]" --in $D --out $F \
  --srt "$M/Horizontal/Selection Valentin (Opus Clip)/_captions-long/$nom.srt" \
  --titre "$T" \
  --sortie "$M/Horizontal/Selection Valentin (Opus Clip)/$nom.mp4"
