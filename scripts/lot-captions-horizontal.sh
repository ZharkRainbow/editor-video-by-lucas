#!/bin/zsh
S=/Users/lucasdo./Documents/RAIZ-Claude/OFFBOUND/APPS/video-reels/scripts
setopt NULL_GLOB
for d in "/Users/lucasdo./Movies/CapCut/Consulting by Lucas to 16,9"/*/Horizontal; do
  for f in "$d"/*.mp4; do
    [[ -f "$f" ]] || continue
    srt="$d/_captions/${f:t:r}.srt"
    [[ -f "$srt" ]] || { echo "SRT manquant : ${f:t}"; continue; }
    python3 $S/incruster-captions.py "$f" "$srt" "/tmp/cap_out.mp4" --y 0.88 --taille 0.048 \
      && mv "/tmp/cap_out.mp4" "$f" && echo "OK  ${f:t}"
  done
done
echo LOT_TERMINE
