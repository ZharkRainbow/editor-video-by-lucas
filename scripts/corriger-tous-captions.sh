#!/bin/zsh
# corriger-srt.py ecrit en place quand le nom ne contient pas "-brut",
# ce qui est le cas des SRT de captions.
setopt NULL_GLOB
S=/Users/lucasdo./Documents/RAIZ-Claude/OFFBOUND/APPS/video-reels/scripts
n=0
for f in "/Users/lucasdo./Movies/CapCut/Consulting by Lucas to 16,9"/*/Horizontal/_captions*/*.srt \
         "/Users/lucasdo./Movies/CapCut/Valentin Masterclass/Horizontal"/_captions*/*.srt; do
  python3 $S/corriger-srt.py "$f" >/dev/null 2>&1 && n=$((n+1))
done
echo "$n SRT passes au dictionnaire Offbound"
