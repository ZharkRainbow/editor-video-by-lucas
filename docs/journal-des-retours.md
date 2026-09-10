# Journal des retours

Chaque reglage de cette chaine vient d'un retour precis, pas d'une preference.
Ce document garde la trace de qui a demande quoi et pourquoi, pour qu'un
reglage ne soit pas defait par ignorance six mois plus tard.

Les retours sont de Lucas sauf mention contraire.

---

## Typographie et habillage

**« La typo je t'avais dit c'etait jaune en italique. »**
ZT Nature MediumItalic, jaune `#FAD400`. Le titre incruste est en ZT Nature Bold
sur bandeau bleu `#2322E0`, affiche 5 secondes.

**« 4 mots maximum, pas de retour a la ligne. »**
Vertical : `-ml 19`, soit 3 a 4 mots. Une caption tient toujours sur une seule
ligne. Un retour a la ligne casse la lecture en scroll.

**« Les captions sur les formats horizontaux doivent etre mises bien au
centre. »**
A l'origine 72 caracteres par ligne, ce qui forcait une reduction de taille
extreme. Ramene a 46 caracteres et la taille remontee de 0,028 a 0,032.

**« L'encadre en haut, il doit pas etre la, il doit etre mis en dessous des
captions. »**
Le bandeau titre est passe au-dessus de la jointure du split screen, juste sous
les captions. `cap_y = 0.4513`, `titre_y = 0.4997`.

**« Je ne sais pas pourquoi tu mets ca centre a gauche. »**
Bug reel, pas une preference. Le passage de `caption:` a `label:` dans
ImageMagick (pour forcer une seule ligne) produit une image a la largeur du
texte ; le `-geometry +marge` la collait au bord. `caption:` centrait par effet
de bord. Corrige par un centrage explicite. **Neuf fichiers ont survecu avec
l'ancien defaut jusqu'au 10/09**, detectes par `controle-centrage.py`.

**« Si tu pouvais mettre du blur derriere, donc un blur un peu noir. »**
Halo flou derriere les captions horizontales, pour tenir sur les fonds clairs.

**« Le blur est beaucoup trop fort, faudrait qu'il se plus diffuse. »**
Apres comparaison de cinq reglages : rayon multiplie par 2,3, densite divisee
par 2. Un halo diffus se voit moins qu'une ombre dense et protege autant.

## Son

**« Il y a de la musique des fois qui est in-forte, apres on n'entend plus. »**
Le `sidechaincompress` faisait remonter la musique dans les silences.
Remplace par un **gain fixe**, mesure une fois puis applique constant. Jamais de
traitement dynamique sur le lit musical.

**« On entend un peu ces bruits de bouche. »**
Le boost de presence a 4 kHz amplifiait exactement cette bande. **Retire.**
Remplace par `adeclick`, un `deesser` et un creux de 2,5 dB a 6,5 kHz.
Mesure apres correction : bande 3-9 kHz de -29,2 a -32,5 dB, pics de -2,9 a
-6,3 dB. **Ne jamais remettre ce boost.**

**« T'es sur que t'as fait la reduction de bruit ? On entend absolument tout ce
qu'il dit derriere. »**
Il avait raison, et sur les 80 fichiers. Le debruitage n'avait jamais tourne.
Voir `notes-techniques.md`. Corrige a la racine : le script echoue plutot que
d'ecrire, et pose un marqueur.

**« Les musiques elles sont un peu faibles, j'aurais ete chaud que tu montes
encore un peu. »**
De -40 a **-34 LUFS**. Trois variantes ont ete produites (-38, -36, -34) pour
trancher en une ecoute plutot qu'en trois allers-retours.

**Valentin, via Lucas : « Sur la masterclass recrutement, on enleve la
correction de voix. On laisse le micro d'origine sans rien toucher. »**
Les 14 VAL sont repartis du rush, sans debruitage ni traitement de timbre. Seule
la normalisation de volume est gardee : le rush est a -23,3 LUFS. Verifie apres
coup, le timbre est identique au rush a 0,1 dB pres.

## Choix editorial

**« Faut vraiment commencer sur le hook et pas laisser des creux comme ca ou
c'est tres plat, l'intonation n'est pas bonne, c'est pas un hook. »**
Opus Clip coupe sur le silence, pas sur l'intention. Ses bornes laissent
souvent une amorce plate. `auditer-debuts.py` transcrit les 4 premieres secondes
de tout un lot pour les reperer : **5 clips sur 20** ouvraient mal.

**« Les moments ou ils hesitent un peu, si tu peux faire des mini-cuts, ce
serait mieux que ce soit legerement plus dynamique. »**
Sur un temoignage de 25 secondes, retirer une reprise, un aparte et une
repetition l'a ramene a 15 secondes sans rien perdre du fond. D'ou le format
multi-segments dans `clips-timecodes.json`.

**« Il y a une sorte de glissement qui se fait tout seul sur la droite alors que
sur le cadrage que j'ai fait il n'y a pas de glissement. »**
Ce n'etait pas un bug mais un defaut de conception : l'interpolation continue
entre deux points de cadrage. Devenu **palier par defaut**, glissement en option
cochee par point.

**« Reprendre ce que Val a mis »** pour les titres incrustes.
Les titres de Valentin sont repris verbatim depuis ses cartes Opus Clip, apparies
par duree et par contenu. Quand il n'y en a pas, on ecrit dans sa formulation.
Un piege identifie : sur Jordy, un clip de 1:43 semblait correspondre au titre de
1:44, mais le contenu prouvait qu'il fallait celui de 2:24. **Apparier par le
contenu, pas seulement par la duree.**

**« Si tu corriges les fautes d'orthographe comme ca, t'as meme pas besoin de me
demander. »**
Autorisation permanente de corriger silencieusement les fautes dans les titres.

**« C'etait voulu de la part de Valentin. »**
Le « putain de brute » de VAL 7 reste. Ne pas prendre l'initiative de nettoyer
le langage de quelqu'un.

## Methode de travail

**« Si tu as besoin de ces informations la, n'invente rien, tu me les
demandes. »**
Pose des le premier message du chantier. Aucun chiffre, aucun timecode, aucun
lien inventes.

**« Fais une note aussi complete sur ce sujet-la. »** (revenu plusieurs fois)
Chaque piege resolu est documente avec sa cause, pas seulement son correctif.

**« Je te laisse me faire le derush, on voit ca ensemble apres, on passera au
montage que quand j'aurai valide. »**
Le montage ne demarre jamais avant validation de la selection. Les extraits de
validation sont produits en 1080p, rapides a regarder, et le montage final
repart de la 4K.

**Suppressions : toujours par la Corbeille**, jamais `rm`. Reformuler ce qui va
etre supprime avant tout lot destructif.
