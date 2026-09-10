#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Programme en reels d'essai Instagram tout ce qui est dans Programmation/.

Reprend les deux pieges documentes dans publer-programmer.py :
  - curl doit declarer le type MIME, sinon Publer repond "File is not supported"
  - le post doit etre type "video" avec details type "reel", feed false et
    trial_reel MANUAL ; le type "reel" seul echoue en silence

Reprenable : chaque succes est journalise, une relance repart ou elle s'est
arretee. Utile parce que l'envoi represente une dizaine de gigaoctets.
"""
import json, os, re, subprocess, sys, time

D = os.path.expanduser("~/Downloads/S du 24 aout")
API = "https://app.publer.com/api/v1"
W = "6a7c9fd25eec0a3bd4859cb0"
COMPTE = "6a7ca51c2251ac1d8824f757"           # Instagram Valentin Thomy
TEXTE = "Follow @valentin.thomy si t'es un fondateur en B2B"
JOURNAL = os.path.join(D, "Programmation", "_publer-faits.txt")
HEURES = ["08:10", "10:05", "12:15", "14:20", "16:10", "18:05", "19:40", "21:15"]

CLE = next(l.split("=", 1)[1].strip().strip('"')
           for l in open(os.path.expanduser("~/.config/secrets/api-keys.env"))
           if l.startswith("PUBLER_API_KEY="))
H = ["-H", f"Authorization: Bearer-API {CLE}", "-H", f"Publer-Workspace-Id: {W}"]

MOIS = {"aout": 8, "septembre": 9, "octobre": 10}


def deja_faits():
    if not os.path.exists(JOURNAL):
        return set()
    return {l.split("\t")[0] for l in open(JOURNAL, encoding="utf-8") if l.strip()}


def noter(cle, quand):
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(f"{cle}\t{quand}\n")


def envoyer(chemin, mime):
    for essai in range(3):
        r = subprocess.run(["curl", "-s", "-X", "POST", *H,
                            "-F", f"file=@{chemin};type={mime}",
                            "-F", "direct_upload=true", f"{API}/media"],
                           capture_output=True, text=True)
        try:
            d = json.loads(r.stdout)
        except Exception:
            time.sleep(3); continue
        if "id" in d:
            return d
        time.sleep(3)
    raise RuntimeError(f"envoi refuse : {os.path.basename(chemin)} {r.stdout[:150]}")


def programmer(video, couverture, quand):
    vign = list(video.get("thumbnails") or [])
    vign.append({"id": couverture["id"],
                 "small": couverture.get("thumbnail") or couverture["path"],
                 "real": couverture["path"]})
    charge = {"bulk": {"state": "scheduled", "posts": [{
        "networks": {"instagram": {
            "type": "video",
            "details": {"type": "reel", "feed": False, "trial_reel": "MANUAL"},
            "text": TEXTE,
            "media": [{"id": video["id"], "path": video["path"], "type": "video",
                       "thumbnails": vign, "default_thumbnail": len(vign) - 1}]}},
        "accounts": [{"id": COMPTE, "scheduled_at": quand}]}]}}
    r = subprocess.run(["curl", "-s", "-X", "POST", *H,
                        "-H", "Content-Type: application/json",
                        "--data-binary", json.dumps(charge, ensure_ascii=False),
                        f"{API}/posts/schedule"], capture_output=True, text=True)
    job = json.loads(r.stdout).get("job_id")
    for _ in range(30):
        time.sleep(2)
        s = subprocess.run(["curl", "-s", *H, f"{API}/job_status/{job}"],
                           capture_output=True, text=True)
        d = json.loads(s.stdout)
        if d.get("status") in ("complete", "failed"):
            return d
    return {"status": "timeout"}


def lot():
    prog = os.path.join(D, "Programmation")
    for jour in sorted(d for d in os.listdir(prog) if d.startswith("J")):
        m = re.match(r"J(\d+) - (\d+) (\w+)", jour)
        j, mois = int(m.group(2)), MOIS[m.group(3)]
        fichiers = sorted(f for f in os.listdir(os.path.join(prog, jour))
                          if f.endswith(".mp4"))
        for i, f in enumerate(fichiers):
            quand = f"2026-{mois:02d}-{j:02d}T{HEURES[i % len(HEURES)]}:00+02:00"
            yield jour, os.path.realpath(os.path.join(prog, jour, f)), quand


if __name__ == "__main__":
    faits = deja_faits()
    total = ok = saute = ko = 0
    for jour, video, quand in lot():
        total += 1
        base = os.path.basename(video)
        cle = f"{base}|{quand}"
        if cle in faits:
            saute += 1; continue
        sujet = re.sub(r"_(9x16|4x5|1x1|16x9)\.mp4$", "", base)
        couv = os.path.join(D, "Couvertures", sujet + ".jpg")
        if not os.path.exists(couv):
            print(f"  KO  {base} : couverture absente", flush=True); ko += 1; continue
        try:
            mv = envoyer(video, "video/mp4")
            ig = (mv.get("validity") or {}).get("instagram") or {}
            if not ig.get("reel"):
                print(f"  KO  {base} : refuse en reel {ig}", flush=True); ko += 1; continue
            mc = envoyer(couv, "image/jpeg")
            d = programmer(mv, mc, quand)
            ech = (d.get("payload") or {}).get("failures")
            if d.get("status") == "complete" and not ech:
                noter(cle, quand); ok += 1
                print(f"  OK  {quand[:16]}  {base}", flush=True)
            else:
                ko += 1
                print(f"  KO  {quand[:16]}  {base}  {ech or d.get('status')}", flush=True)
        except Exception as e:
            ko += 1
            print(f"  KO  {base} : {e}", flush=True)
    print(f"=== PUBLER TERMINE : {ok} programmes, {saute} deja faits, {ko} echecs, "
          f"{total} au total ===", flush=True)
