#!/bin/bash
# usage : poser-titre.sh video_in.mp4 titre.png video_out.mp4 [duree_affichage]
export LC_ALL=C
V="$1"; T="$2"; O="$3"; D="${4:-3.5}"
ffmpeg -nostdin -v error -y -i "$V" -i "$T" \
  -filter_complex "[0:v][1:v]overlay=x=0:y=H*0.13:enable='lte(t,$D)':format=auto" \
  -c:v h264_videotoolbox -b:v 16M -profile:v high -c:a copy -movflags +faststart "$O"
