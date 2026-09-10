#!/usr/bin/env python3
"""Sert l'outil de recadrage et recoit les cadrages sans copier-coller.

Le bouton "Envoyer a Claude" fait un POST ici, le JSON atterrit dans
cadrages/<passage>.json, et Claude n'a plus qu'a le lire.
"""
import json
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).parent
DEPOT = RACINE / "cadrages"


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

    def log_message(self, *a):
        pass

    def handle_one_request(self):
        # le navigateur annule ses requetes video a chaque deplacement dans la
        # timeline : la connexion casse, c'est normal et sans consequence.
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True


if __name__ == "__main__":
    print(f"Outil de recadrage : http://localhost:8765")
    print(f"Les cadrages arrivent dans {DEPOT}/")
    ThreadingHTTPServer(("", 8765), H).serve_forever()
