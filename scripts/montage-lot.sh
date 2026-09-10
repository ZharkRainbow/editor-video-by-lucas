#!/bin/bash
export LC_ALL=C
SRC="/Users/lucasdo./Downloads/Reels - Outdoor."
OUT="/Users/lucasdo./Downloads/VAL-Outdoor-Propres"
mkdir -p "$OUT"
DJI="/Users/lucasdo./Downloads/DJI OSMO Pocket 4 D-Log to Rec.709 V1.0.cube"
CINE="/Users/lucasdo./Downloads/Apple - Cinestyle (sans LOG).cube"
VF="lut3d=file='$DJI',lut3d=file='$CINE'"

# nom source | start | end (vide = jusqu'a la fin)
DATA="
5 profils avec expertises differentes|0|102.0
Arrete les videos en studio|2.7|
Avoir une personne a tes cotes|4.3|
Catering et logistique (long BTS)|0|362.0
Ce n est jamais trop cher|0|
Ce qu il y a dans le salariat|11.38|91.6
Ce que je me suis interdit (coupe)|8.8|92.5
Clients viennent dans mon salon|2.6|
Commande Course IA|11.5|134.0
Comment je gere mon contenu|23.5|
Comment s expatrier|0|
Holding ouverte a 22 ans|5.6|73.8
J ai annule toutes mes vacances|0|16.9
La canicule a Budapest|10.9|
La vraie ambition|15.0|201.0
Le piege du branding lifestyle|0|
Le piege quand tu reussis|0|76.0
Le vrai probleme des clients|5.5|
Les moments les plus durs|2.5|64.0
Ne pas s associer avant 1 million|2.8|
Organiser Mastermind|22.56|
Pourquoi le setting marche|0|63.6
Quand commencer a recruter|0|
Quel business lancer|0|87.8
Recette poulet cacahuetes (long)|11.5|139.5
Recette poulet oignons magnets (long)|1.02|210.0
Setup tournage 2 cameras (BTS)|0|
Stresse c est du presentiel|0|
Suis ton intuition|0|
Suis-je vraiment heureux|2.8|
Tout le monde veut plus de clients|13.5|
Travaille ton hook|11.8|63.6
Upsell mastermind 20 a 50|2.6|
"
echo "src;start;end;duree_source;duree_finale;fichier_sortie" > "$OUT/_correspondance.csv"
n=0
echo "$DATA" | grep -v '^$' | while IFS='|' read -r name st en; do
  n=$((n+1))
  id=$(printf "VAL-OUT-%03d" $n)
  clean=$(echo "$name" | tr ' ' '-' | tr -d "()")
  outf="${id}_${clean}.mp4"
  src_dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$SRC/$name.mp4")
  args=(-hwaccel videotoolbox -ss "$st")
  [ -n "$en" ] && args+=(-to "$en")
  ffmpeg -nostdin -v error -y "${args[@]}" -i "$SRC/$name.mp4" \
    -map 0:v:0 -map 0:a:0 -vf "$VF" \
    -c:v h264_videotoolbox -b:v 16M -profile:v high \
    -c:a aac -b:a 192k -ar 48000 -movflags +faststart \
    "$OUT/$outf" || { echo "[$n/33] ECHEC $name"; continue; }
  fin_dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/$outf")
  printf "[%2d/33] %-40s %6.1fs -> %6.1fs\n" "$n" "${name:0:39}" "$src_dur" "$fin_dur"
  echo "$name;$st;$en;$src_dur;$fin_dur;$outf" >> "$OUT/_correspondance.csv"
done
echo "=== PASSE FINALE TERMINEE ==="
