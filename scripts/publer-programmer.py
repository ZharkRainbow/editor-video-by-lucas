# -*- coding: utf-8 -*-
"""Programme des reels d'essai Instagram sur Publer.

Deux pieges qui ne sont pas dans la documentation :

  l'envoi de media  curl doit declarer explicitement le type MIME de la piece
      jointe. Sans ca Publer repond 400 "File is not supported", quelle que
      soit la taille et le codec.

  le type de post   la doc dit type "reel". Publer refuse et le job repond
      "complete" sans rien creer ; l'erreur reelle n'apparait que dans
      payload.failures du job. Il faut type "video" et details
      {"type": "reel", "feed": false, "trial_reel": "MANUAL"} pour un reel
      d'essai, qui n'est pas montre aux abonnes et n'apparait pas sur le profil.
"""
import json, os, subprocess, sys, time, urllib.request

D = "/Users/lucasdo./Downloads/S du 24 aout"
API = "https://app.publer.com/api/v1"
W = "6a7c9fd25eec0a3bd4859cb0"
COMPTE = "6a7ca51c2251ac1d8824f757"          # Instagram Valentin Thomy
TEXTE = "Follow @valentin.thomy si t'es un fondateur en B2B"

with open(os.path.expanduser("~/.config/secrets/api-keys.env")) as f:
    CLE = next(l.split("=", 1)[1].strip().strip('"')
               for l in f if l.startswith("PUBLER_API_KEY="))
H = ["-H", f"Authorization: Bearer-API {CLE}", "-H", f"Publer-Workspace-Id: {W}"]

LOT = [
 ("Reels-carte-hook", "VAL-OUT-012_Holding-ouverte-a-22-ans",              "15:20"),
 ("VAL-Indoor",       "VAL-004_Cold-call-trois-oui-d-affilee-avant-le-RDV", "15:50"),
 ("Reels-carte-hook", "VAL-OUT-008_Clients-viennent-dans-mon-salon",        "16:30"),
 ("VAL-Indoor",       "VAL-009_Le-vision-board-du-bureau-vue-sur-la-foret", "17:35"),
 ("VAL-Outdoor",      "VAL-OUT-029_Suis-ton-intuition",                     "18:10"),
 ("VAL-Indoor",       "VAL-010_Deux-ans-a-Budapest-est-ce-que-je-regrette", "19:20"),
 ("VAL-Outdoor",      "VAL-OUT-019_Les-moments-les-plus-durs",              "20:10"),
 ("VAL-Indoor",       "VAL-017_L-agence-2027-fondateur-CTO-account-manager","21:00"),
]


def envoyer(chemin, mime):
    r = subprocess.run(["curl", "-s", "-X", "POST", *H,
                        "-F", f"file=@{chemin};type={mime}",
                        "-F", "direct_upload=true", f"{API}/media"],
                       capture_output=True, text=True)
    d = json.loads(r.stdout)
    if "id" not in d:
        raise SystemExit(f"envoi refuse pour {chemin} : {d}")
    return d


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
    for _ in range(20):
        time.sleep(2)
        s = subprocess.run(["curl", "-s", *H, f"{API}/job_status/{job}"],
                           capture_output=True, text=True)
        d = json.loads(s.stdout)
        if d.get("status") in ("complete", "failed"):
            return d
    return {"status": "timeout"}


for dossier, base, heure in LOT:
    v = os.path.join(D, dossier, base + "_9x16.mp4")
    c = os.path.join(D, "Couvertures", base + ".jpg")
    mv = envoyer(v, "video/mp4")
    mc = envoyer(c, "image/jpeg")
    ig = (mv.get("validity") or {}).get("instagram") or {}
    if not ig.get("reel"):
        print(f"REFUS  {base} : Instagram n'accepte pas cette video en reel {ig}")
        continue
    d = programmer(mv, mc, f"2026-08-28T{heure}:00+02:00")
    ech = (d.get("payload") or {}).get("failures")
    print(f"{'OK ' if d.get('status') == 'complete' and not ech else 'KO '} "
          f"{heure}  {base}" + (f"  {ech}" if ech else ""))
print("=== PROGRAMMATION PUBLER TERMINEE ===")
