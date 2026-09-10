#!/bin/zsh
S=/Users/lucasdo./Documents/RAIZ-Claude/OFFBOUND/APPS/video-reels/scripts
B="/Users/lucasdo./Movies/CapCut/Consulting by Lucas to 16,9"
cd $S
echo "===== verticaux regeneres (la musique etait mixee, on repart de la 4K) ====="
python3 monter-vertical-consulting.py Amory Jordy
echo "===== musique a gain fixe -36 LUFS ====="
python3 ajouter-musique.py "$B/Amory" "$B/Jordy"
echo "===== AMORY JORDY TERMINE ====="
