# -*- coding: utf-8 -*-
"""Programme une serie de stories Instagram depuis un dossier de la bibliotheque Publer.

L'ordre de publication vient du NOM du fichier, jamais de l'ordre renvoye par
l'API. Les medias ne sont pas renvoyes : on reutilise ceux deja ranges dans le
dossier, sinon la copie atterrit a la racine et le classement est perdu.

Piege : le type `story` documente est refuse. Il faut `type: video` plus
`details: {"type": "story"}`.
"""
import json, os, re, subprocess, sys, time

API = "https://app.publer.com/api/v1"
W = "6a7c9fd25eec0a3bd4859cb0"
COMPTE = "6a7ca51c2251ac1d8824f757"          # Instagram Valentin Thomy
CLE = next(l.split("=", 1)[1].strip().strip('"')
           for l in open(os.path.expanduser("~/.config/secrets/api-keys.env"))
           if l.startswith("PUBLER_API_KEY="))
H = ["-H", f"Authorization: Bearer-API {CLE}", "-H", f"Publer-Workspace-Id: {W}"]


def lire(u, *extra):
    """L'API rend parfois une reponse vide ou incomplete sous rafale. On reessaie."""
    for essai in range(5):
        r = subprocess.run(["curl", "-s", "-m", "60", "-G", *H, *extra, u],
                           capture_output=True, text=True)
        try:
            return json.loads(r.stdout)
        except Exception:
            time.sleep(3 * (essai + 1))
    raise SystemExit(f"lecture impossible : {u}")


def dossier(nom, parent=None):
    u = f"{API}/media/folders" + (f"?parent_folder_id={parent}" if parent else "")
    d = lire(u)
    def cle(x):
        return x.lower().replace(" ", "")
    fs = d.get("folders", [])
    for f in fs:                                   # nom exact
        if f["name"] == nom:
            return f["id"]
    for f in fs:                                   # a la casse et aux espaces pres
        if cle(f["name"]) == cle(nom):
            return f["id"]
    # les noms cote Publer divergent parfois de ceux du disque (Systeme/System,
    # Offound/Offbound), on retombe sur le prefixe le plus long
    cands = [f for f in fs if cle(f["name"])[:6] == cle(nom)[:6]]
    if len(cands) == 1:
        print(f"    (dossier Publer « {cands[0]['name']} » pour la serie « {nom} »)")
        return cands[0]["id"]
    raise SystemExit(f"dossier introuvable : {nom}")


def medias(folder_id):
    m = lire(f"{API}/media",
             "--data-urlencode", "types[]=video",
             "--data-urlencode", "used[]=true",
             "--data-urlencode", "used[]=false",
             "--data-urlencode", f"folder_id={folder_id}")["media"]
    # tri numerique sur le suffixe du nom, sinon Ambiance-10 passerait avant -2
    def rang(x):
        n = re.search(r"-(\d+)\.mp4$", x["name"])
        return int(n.group(1)) if n else 0
    return sorted(m, key=rang)


def programmer(media, quand):
    charge = {"bulk": {"state": "scheduled", "posts": [{
        "networks": {"instagram": {
            "type": "video",
            "details": {"type": "story"},
            "text": "",
            "media": [{"id": media["id"], "path": media["path"], "type": "video"}]}},
        "accounts": [{"id": COMPTE, "scheduled_at": quand}]}]}}
    r = subprocess.run(["curl", "-s", "-m", "120", *H,
                        "-H", "Content-Type: application/json",
                        "--data-binary", json.dumps(charge, ensure_ascii=False),
                        f"{API}/posts/schedule"], capture_output=True, text=True)
    job = json.loads(r.stdout).get("job_id")
    if not job:
        return {"status": "pas de job", "brut": r.stdout[:300]}
    for _ in range(25):
        time.sleep(2)
        d = json.loads(subprocess.run(["curl", "-s", "-m", "60", *H,
                                       f"{API}/job_status/{job}"],
                                      capture_output=True, text=True).stdout)
        if d.get("status") in ("complete", "failed"):
            return d
    return {"status": "timeout"}


if __name__ == "__main__":
    serie, jour, debut, ecart = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    racine = dossier("Story instagram")
    fid = dossier(serie, racine)
    ms = medias(fid)
    # rejouable : on releve les medias deja programmes ce jour-la pour ne pas
    # recreer un post par-dessus a chaque relance
    veille = lire(f"{API}/posts",
                  "--data-urlencode", "state=scheduled",
                  "--data-urlencode", "postType=story",
                  "--data-urlencode", f"from={jour}",
                  "--data-urlencode", f"to={jour}")
    deja = {(x.get("media") or [{}])[0].get("id") for x in veille.get("posts", [])}
    print(f"{serie} : {len(ms)} medias, {len(deja)} deja en file le {jour}")
    h, mn = map(int, debut.split(":"))
    for i, m in enumerate(ms):
        if m["id"] in deja:
            print(f"  --  {m['name']}  deja programme, ignore")
            continue
        v = (m.get("validity") or {}).get("instagram") or {}
        if not v.get("story"):
            print(f"  REFUS {m['name']} : Instagram n'accepte pas cette video en story")
            continue
        t = h * 60 + mn + i * ecart
        quand = f"{jour}T{t//60:02d}:{t%60:02d}:00+02:00"
        d = programmer(m, quand)
        ech = (d.get("payload") or {}).get("failures")
        etat = "OK " if d.get("status") == "complete" and not ech else "KO "
        print(f"  {etat} {quand[11:16]}  {m['name']}"
              + (f"  {json.dumps(ech, ensure_ascii=False)}" if ech else ""))
        time.sleep(3)
    print("=== termine ===")
