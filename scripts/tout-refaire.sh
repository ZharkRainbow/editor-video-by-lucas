#!/bin/zsh
setopt NULL_GLOB
S=/Users/lucasdo./Documents/RAIZ-Claude/OFFBOUND/APPS/video-reels/scripts
cd $S
echo "===== 1/4 horizontaux consulting ====="
python3 refaire-horizontal-consulting.py --tous Amory Baptiste Jordy
echo "===== 2/4 verticaux consulting ====="
python3 monter-vertical-consulting.py
echo "===== 3/4 verticaux masterclass ====="
python3 monter-vertical-masterclass.py
echo "===== 4/4 musique sur tous les verticaux ====="
python3 ajouter-musique.py "/Users/lucasdo./Movies/CapCut/Consulting by Lucas to 16,9" "/Users/lucasdo./Movies/CapCut/Valentin Masterclass"
echo "===== CHAINE TERMINEE ====="
