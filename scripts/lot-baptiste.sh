#!/bin/zsh
S=/Users/lucasdo./Documents/RAIZ-Claude/OFFBOUND/APPS/video-reels/scripts
cd $S
echo "===== Baptiste : verticaux regeneres (la musique etait deja mixee, il faut repartir de la 4K) ====="
python3 monter-vertical-consulting.py Baptiste
echo "===== Baptiste : musique a gain fixe ====="
python3 ajouter-musique.py "/Users/lucasdo./Movies/CapCut/Consulting by Lucas to 16,9/Baptiste"
echo "===== BAPTISTE TERMINE ====="
