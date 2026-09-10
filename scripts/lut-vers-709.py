#!/usr/bin/env python3
"""Convertit une LUT de conversion log -> Rec709 en une LUT Rec709 -> Rec709.

LE PROBLEME
Une LUT « Log M to Rec709 » attend une image encodee en log. Elle fait deux
choses a la fois : elle redresse la courbe logarithmique, et elle rend les
couleurs (saturation, teinte des peaux, comportement des hautes lumieres).
Sur un rush iPhone, deja en Rec709, la courbe est deja redressee. Appliquer la
LUT telle quelle revient a decoder deux fois : le contraste part, les peaux
rougissent. Lucas l'a dit : ce n'est pas la meme chose.

LA SEPARATION
On lit la reponse de la LUT sur son axe neutre : n(x) = L(x,x,x). C'est la
partie « redressement de courbe », et sur cette LUT elle n'est meme pas neutre
(un gris 0,50 en ressort bleute). On la retire en post-corrigeant :

    T(r,v,b) = n⁻¹( L(r,v,b) )   canal par canal

Un gris redonne alors exactement le meme gris, par construction. Ce qui
subsiste est le rendu couleur seul : saturation, teinte des peaux, separation
des primaires. C'est cette partie-la qui est transposable a une image deja en
Rec709. Corriger AVANT application ne marche pas, la LUT n'etant pas separable
par canal.

usage : lut-vers-709.py entree.cube sortie.cube "Titre" [force]
        force : 1.0 = rendu couleur entier, 0.5 = a moitie (defaut 1.0)
"""
import sys


def lire(p):
    taille, table = None, []
    for l in open(p, encoding="utf-8", errors="ignore"):
        l = l.strip()
        if not l or l.startswith("#"):
            continue
        if l.upper().startswith("LUT_3D_SIZE"):
            taille = int(l.split()[-1])
            continue
        m = l.split()
        if len(m) == 3:
            try:
                table.append([float(v) for v in m])
            except ValueError:
                continue
    if taille is None or len(table) != taille ** 3:
        raise SystemExit(f"{p} : table de {len(table)} entrees pour une taille {taille}")
    return taille, table


def echantillon(taille, table, r, g, b):
    """Lecture trilineaire. L'index cube varie d'abord en rouge."""
    def bornes(v):
        x = min(max(v, 0.0), 1.0) * (taille - 1)
        i = min(int(x), taille - 2)
        return i, x - i
    ir, fr = bornes(r)
    ig, fg = bornes(g)
    ib, fb = bornes(b)
    out = [0.0, 0.0, 0.0]
    for dr in (0, 1):
        for dg in (0, 1):
            for db in (0, 1):
                p = ((ir + dr) + (ig + dg) * taille + (ib + db) * taille * taille)
                w = ((fr if dr else 1 - fr) * (fg if dg else 1 - fg)
                     * (fb if db else 1 - fb))
                if w:
                    c = table[p]
                    for k in range(3):
                        out[k] += w * c[k]
    return out


def inverse(courbe):
    """Inverse une courbe croissante donnee par ses N points, sur [0,1]."""
    n = len(courbe)

    def f(y):
        if y <= courbe[0]:
            return 0.0
        if y >= courbe[-1]:
            return 1.0
        lo, hi = 0, n - 1
        while hi - lo > 1:
            mi = (lo + hi) // 2
            if courbe[mi] <= y:
                lo = mi
            else:
                hi = mi
        d = courbe[hi] - courbe[lo]
        t = 0.0 if d < 1e-9 else (y - courbe[lo]) / d
        return (lo + t) / (n - 1)
    return f


def main(src, dst, titre, force=1.0):
    taille, table = lire(src)
    # reponse de la LUT sur son axe neutre, canal par canal
    neutre = [[table[(i + i * taille + i * taille * taille)][k] for i in range(taille)]
              for k in range(3)]
    inv = [inverse(c) for c in neutre]

    sortie = [f'TITLE "{titre}"', f"LUT_3D_SIZE {taille}",
              "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0", ""]
    for ib in range(taille):
        for ig in range(taille):
            for ir in range(taille):
                e = [ir / (taille - 1), ig / (taille - 1), ib / (taille - 1)]
                brut = echantillon(taille, table, e[0], e[1], e[2])
                v = [inv[k](brut[k]) for k in range(3)]
                v = [e[k] + (v[k] - e[k]) * force for k in range(3)]
                sortie.append(" ".join(f"{min(max(x, 0.0), 1.0):.6f}" for x in v))
    open(dst, "w", encoding="utf-8").write("\n".join(sortie) + "\n")
    print(f"{dst} ecrit : {taille}^3 entrees, force {force}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3],
         float(sys.argv[4]) if len(sys.argv) > 4 else 1.0)
