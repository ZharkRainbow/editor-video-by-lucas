#!/bin/zsh
S=/Users/lucasdo./Documents/RAIZ-Claude/OFFBOUND/APPS/video-reels/scripts
B="/Users/lucasdo./Movies/CapCut/Consulting by Lucas to 16,9"
cd $S
echo "===== 20 verticaux, titres definitifs ====="
python3 monter-vertical-consulting.py
echo "===== musique -36 LUFS gain fixe ====="
python3 ajouter-musique.py "$B"
echo "===== LOT FINAL TERMINE ====="
