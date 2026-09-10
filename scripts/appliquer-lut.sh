#!/bin/zsh
# Applique la LUT correctrice a un rush, sans toucher a l'audio.
#
# Les rushes propres portent l'ancienne chaine D-Log to Rec709 + Cinestyle.
# Valentin a valide Log M to Rec709. Plutot que de refaire les fichiers depuis
# les sources, ce qui obligerait a rejouer toutes les coupes, on applique une
# LUT calculee qui transforme le premier etalonnage en le second.
#
# usage : appliquer-lut.sh entree.mp4 sortie.mp4
set -e
LUT=~/Documents/RAIZ-Claude/OFFBOUND/APPS/video-reels/luts/"Correction vers Log M.cube"
[ -f "$LUT" ] || { echo "LUT correctrice introuvable"; exit 1; }
ffmpeg -y -v error -i "$1" \
  -vf "lut3d=file='$LUT'" \
  -c:v h264_videotoolbox -b:v 24M -profile:v high \
  -c:a copy -movflags +faststart "$2"
