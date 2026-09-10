#!/usr/bin/env python3
"""Sert l'outil de recadrage et recoit les cadrages.

POINT CRITIQUE : SimpleHTTPRequestHandler ne gere PAS les requetes Range HTTP.
Il repond 200 avec le fichier entier au lieu de 206 avec la plage demandee.
Pour une video de 146 Mo, le navigateur doit donc tout telecharger avant de
lire, et surtout il ne peut pas se deplacer dans la timeline : chaque seek
redemande le fichier depuis le debut, le decodeur repart de zero et l'image
reste figee sur les premieres frames.

C'etait la cause reelle des "bugs de synchronisation" de l'outil. On implemente
donc Range ici.
"""
import json
import os
import re
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).parent
DEPOT = RACINE / "cadrages"
TAILLE_BLOC = 1 << 20


class H(SimpleHTTPRequestHandler):

    def do_POST(self):
        if self.path != "/enregistrer":
            return self.send_error(404)
        n = int(self.headers.get("Content-Length", 0))
        try:
            d = json.loads(self.rfile.read(n))
        except Exception:
            return self.send_error(400)
        DEPOT.mkdir(exist_ok=True)
        nom = (d.get("passage") or "sans-passage").replace("/", "-")[:60]
        f = DEPOT / f"{nom}.json"
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{datetime.now():%H:%M:%S}] recu : {f.name} "
              f"({len(d.get('points', []))} point(s))", flush=True)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "fichier": f.name}).encode())

    def send_head(self):
        """Ajoute le support des requetes Range, indispensable pour le seek."""
        chemin = self.translate_path(self.path)
        if os.path.isdir(chemin):
            return super().send_head()
        plage = self.headers.get("Range")
        if not plage:
            self.send_header_accept_ranges = True
            f = super().send_head()
            return f
        m = re.match(r"bytes=(\d*)-(\d*)", plage)
        if not m or not os.path.isfile(chemin):
            return super().send_head()

        taille = os.path.getsize(chemin)
        debut = int(m.group(1)) if m.group(1) else 0
        fin = int(m.group(2)) if m.group(2) else taille - 1
        fin = min(fin, taille - 1)
        if debut > fin:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{taille}")
            self.end_headers()
            return None

        f = open(chemin, "rb")
        f.seek(debut)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(chemin))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {debut}-{fin}/{taille}")
        self.send_header("Content-Length", str(fin - debut + 1))
        self.end_headers()
        self._reste = fin - debut + 1
        return f

    def copyfile(self, source, sortie):
        """Ne copie que la plage demandee."""
        reste = getattr(self, "_reste", None)
        if reste is None:
            return super().copyfile(source, sortie)
        self._reste = None
        while reste > 0:
            bloc = source.read(min(TAILLE_BLOC, reste))
            if not bloc:
                break
            sortie.write(bloc)
            reste -= len(bloc)

    def end_headers(self):
        if not self.path.endswith(".json"):
            self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def log_message(self, *a):
        pass

    def handle_one_request(self):
        # le navigateur annule ses requetes video a chaque seek : c'est normal
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True


if __name__ == "__main__":
    print("Outil de recadrage : http://localhost:8765")
    print(f"Les cadrages arrivent dans {DEPOT}/")
    ThreadingHTTPServer(("", 8765), H).serve_forever()
