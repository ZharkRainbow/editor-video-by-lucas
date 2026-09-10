#!/bin/zsh
# Debruite la voix d'un rush avec DeepFilterNet et la ramene a un niveau
# commun, en gardant la video intacte.
#
# La normalisation n'est pas cosmetique : sans elle, chaque rush a son propre
# niveau de voix (Valentin plus ou moins pres du micro, plus ou moins de vent),
# et comme la musique se cale par rapport a la voix, le rendu final semble plus
# ou moins habille d'un reel a l'autre. On vise -14 LUFS partout.
#
# On attenue de 6 dB avant le traitement : DeepFilterNet sature sur ces rushes
# et signale du clipping. On restaure le niveau apres, sinon tout le calage de
# musique en aval serait fausse de 6 dB.
#
# usage : nettoyer-voix.sh entree.mp4 sortie.mp4
set -e
IN="$1"; OUT="$2"
TMP=$(mktemp -d)
trap "rm -rf $TMP" EXIT
mkdir -p "$TMP/in" "$TMP/out"
ffmpeg -y -v error -i "$IN" -ar 48000 -ac 1 -af "volume=-6dB" "$TMP/in/a.wav"
~/.local/bin/deep-filter -D --pf -o "$TMP/out" "$TMP/in/a.wav" 2>/dev/null
[ -f "$TMP/out/a.wav" ] || { echo "ECHEC debruitage $IN"; exit 1; }
ffmpeg -y -v error -i "$IN" -i "$TMP/out/a.wav" \
  -map 0:v -map 1:a -af "volume=6dB,loudnorm=I=-14:TP=-1.5:LRA=11" \
  -c:v copy -c:a aac -b:a 192k -ar 48000 -movflags +faststart "$OUT"
