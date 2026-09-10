#!/bin/bash
# usage : faire-titre.sh "Le texte du titre" sortie.png
# genere une carte titre transparente 1080 de large, police ZTNature Bold
export LC_ALL=C
TXT="$1"; OUTP="${2:-titre.png}"
TMP=$(mktemp -d)
cat > "$TMP/t.html" <<HTML
<html><head><meta charset="utf-8"><style>
@font-face{font-family:ZTN;src:url("file:///Users/lucasdo./Library/Fonts/ZTNature-Bold.otf") format("opentype");font-weight:700;}
html,body{margin:0;padding:0;background:transparent;}
.wrap{width:1080px;padding:0 64px;box-sizing:border-box;}
.card{background:#fff;border-radius:16px;padding:30px 36px;
      font-family:ZTN,"Helvetica Neue",sans-serif;font-weight:700;
      font-size:54px;line-height:1.16;color:#191919;letter-spacing:-.015em;
      box-shadow:0 12px 44px rgba(0,0,0,.22);}
</style></head><body><div class="wrap"><div class="card">$TXT</div></div></body></html>
HTML
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu \
  --screenshot="$OUTP" --window-size=1080,340 --default-background-color=00000000 \
  --hide-scrollbars "$TMP/t.html" 2>/dev/null
rm -rf "$TMP"
echo "$OUTP"
