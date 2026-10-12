"""Registre des personnages IA : profils de personnalité par-dessus les niveaux (issue #439, lot B).

Rôle : un seul endroit où déclarer un personnage — prénom, description de
caractère (affichable au joueur plus tard) et le
:class:`~scrabble.moteur.ia.ProfilPersonnage` de surcharges stratégiques qu'il
applique (issue #438, lot A). Ajouter un personnage revient à ajouter une
entrée à :data:`PERSONNAGES` ci-dessous ; rien d'autre à toucher dans ce
module.

Portée (issue #439) : ce registre n'est consulté ni par ``ui/`` (aucun
sélecteur de personnage n'existe encore — contrainte explicite de l'issue)
ni par :meth:`scrabble.moteur.partie.Partie.jouer_tour_ia` (qui continue de
recevoir un ``ProfilPersonnage`` explicite, jamais résolu automatiquement
depuis :attr:`~scrabble.moteur.partie.Joueur.personnage`) — uniquement par les
tests et par le script de mesure de force
(``scripts/mesurer_force_niveaux.py``).

Règle absolue : le joueur humain a accès à tout le dictionnaire (issue #457)
-----------------------------------------------------------------------------
Aucun des réglages de ce module (vocabulaire par palier, ``vocabulaire_long``,
``mots_favoris``) ne restreint ni n'élargit jamais ce que le joueur **humain**
peut jouer. Un personnage ou un niveau ne modifie QUE la **génération** des
coups candidats de l'ordinateur (:func:`scrabble.moteur.ia.choisir_coup`,
via le Trie restreint transmis par :attr:`~scrabble.moteur.partie.
Partie.dictionnaires_ia`) ; la **validation** d'un coup — humain comme IA —
reste toujours sur :attr:`~scrabble.moteur.partie.Partie.dictionnaire`, le
Trie complet de la partie (voir sa docstring). Si l'humain apprend un mot
rare joué par un personnage (le Lettré, par exemple), il peut toujours le
rejouer ensuite contre n'importe quel autre adversaire, à n'importe quel
niveau. Voir aussi ``data/dictionnaire/README.md``.

Personnage Classique
---------------------
Absence de biais : :class:`~scrabble.moteur.ia.ProfilPersonnage` vide,
comportement bit à bit identique à l'absence de profil (garanti par
construction, voir la docstring de ``ProfilPersonnage``). Présent dans le
registre pour que les comparaisons (tests, script de mesure) le nomment comme
les autres plutôt que de traiter « pas de personnage » comme un cas à part.

Personnage Opportuniste
------------------------
Se précipite sur les cases bonus, néglige ce qu'il garde sur son
chevalet. D'après le rapport d'investigation (issue #437), ce style s'exprime
entièrement avec deux réglages déjà existants de ``ProfilPersonnage`` —
aucun nouveau calcul :

* ``poids_leave=0.0`` : indifférence totale à la qualité du reliquat. Reprend
  tel quel la valeur de production de DEBUTANT/FACILE
  (:data:`scrabble.moteur.ia._POIDS_LEAVE`), pas une valeur inédite.
* ``bonus_premium`` fortement renforcé : :data:`BONUS_PREMIUM_OPPORTUNISTE`
  = 100, valeur choisie par mesure avec ``scripts/mesurer_force_niveaux.py``.
  Les réglages de production de :data:`scrabble.moteur.ia._BONUS_PREMIUM`
  vont de 3 (DEBUTANT) à 20 (EXPERT/CHAMPION_DU_MONDE) ; une première
  valeur de 28, déduite de cette échelle, ne se voyait presque pas en jeu.
  À 100, Opportuniste joue nettement plus de coups sur cases mot
  double/triple que Classique, pour une force comparable à niveau égal
  (44 à 50 % de victoires sur les six niveaux, 100 parties chacun) ;
  au-delà de 100, plus rien ne change.

  Cette surcharge est **plate** (une constante, pas une table indexée par
  niveau) : par construction de ``ProfilPersonnage`` (issue #438, lot A),
  Opportuniste applique le même ``bonus_premium=100`` quel que soit le niveau
  du joueur — le trait de caractère ne varie pas avec sa force. ``malus_longueur``
  n'est volontairement pas surchargé : seuls les deux réglages évoqués par
  l'intention du personnage (issue #439) sont touchés.

Voir le rapport de l'issue #439 pour les résultats de mesure (taux de
victoire, écart de score) de ce calibrage face à Classique, au même niveau,
et une éventuelle proposition d'ajustement si la mesure le justifie — la
valeur ne doit pas être retouchée en boucle pour « faire passer » une mesure,
seulement sur validation explicite d'Alain.

Personnage Chasseur de scrabbles
----------------------------------
Guette les coups posant les 7 lettres du chevalet d'un coup (un
« scrabble ») et garde ses meilleures lettres pour y arriver. D'après le
rapport d'investigation (issue #437), ce style est « réalisable en
partie » : le bonus direct sur la pose de 7 lettres relève de la même
famille de calcul que le bonus premium (une constante ajoutée au score
stratégique selon un critère sur le coup, voir
:data:`scrabble.moteur.ia._SEUIL_BONUS_SCRABBLE`) ; l'anticipation fine du
reliquat (deviner par avance qu'on approche d'un scrabble jouable) reste
hors périmètre — on s'appuie sur trois réglages :

* ``bonus_scrabble`` = :data:`BONUS_SEPT_LETTRES_CHASSEUR` = 150 : champ de
  :class:`~scrabble.moteur.ia.ProfilPersonnage` (issue #448, lot H), neutre
  (0) en l'absence de personnage, quel que soit le niveau. Valeur de départ
  déduite par analogie avec :data:`BONUS_PREMIUM_OPPORTUNISTE` (100) :
  l'événement déclencheur (poser les 7 lettres) est bien plus rare que
  « toucher une case premium », donc le bonus doit être encore plus
  déterminant pour l'emporter sur un coup concurrent mieux payé en score
  brut — 150 reprend l'échelle d'Opportuniste en l'augmentant d'un facteur
  comparable à celui qui sépare déjà ce dernier (x5) du bonus premium de
  production (20 à EXPERT/CHAMPION_DU_MONDE). Inchangé par le lot H bis.
* ``vocabulaire_long`` = ``True`` (issue #450, lot H bis) : nouveau champ de
  :class:`~scrabble.moteur.ia.ProfilPersonnage`, neutre (``None``) en
  l'absence de personnage. L'ensemble des coups candidats de l'ordinateur
  devient l'union de ceux du vocabulaire de son niveau et des coups dont le
  mot principal compte 7 lettres ou plus, générés et validés (mot principal
  et mots croisés) avec le lexique complet — voir
  :func:`scrabble.moteur.ia._generer_coups_candidats`. C'est ce réglage, pas
  le bonus de pose, qui porte le caractère du personnage : la mesure du lot H
  (contre Classique au même niveau) montrait un style qui ne se voyait pas
  (écarts de scrabbles par partie dans la marge d'erreur, à tous les niveaux
  où le vocabulaire du niveau est déjà le lexique complet) — le rapport
  d'investigation de l'issue #437 avait sous-estimé à quel point le
  vocabulaire restreint des niveaux, pas le bonus sur le score, est le vrai
  frein aux scrabbles.
* ``poids_leave`` = :data:`POIDS_LEAVE_CHASSEUR_SCRABBLES` = ``None`` (issue
  #450, lot H bis ; valait 2.0 au lot H) : **aucune surcharge** — le poids de
  leave du niveau du joueur s'applique tel quel
  (:data:`scrabble.moteur.ia._POIDS_LEAVE`, de 0.3 à Intermédiaire à 0.6 à
  Avancé). La mesure du lot H montrait Chasseur plus faible que Classique de
  8 à 20 points par partie : un poids de 2.0 (le double du plafond de
  production) le faisait privilégier un reliquat soigné à un score immédiat,
  sans que le vocabulaire restreint des niveaux disponibles ne lui donne
  assez d'occasions de scrabble pour compenser. Avec ``vocabulaire_long``
  comme seul trait de caractère, retirer la surcharge isole proprement son
  effet dans la prochaine mesure — :data:`POIDS_LEAVE_CHASSEUR_SCRABBLES`
  reste une constante nommée, à remonter à une valeur légèrement supérieure
  à ``None`` si la mesure montre que Chasseur garde encore trop facilement un
  petit coup plutôt qu'un reliquat prometteur.

  Ces trois réglages sont **plats** (une constante chacun, pas une table
  indexée par niveau), par construction de ``ProfilPersonnage`` — le trait de
  caractère ne varie pas avec la force du joueur.

Deux réglages supplémentaires (issue #451, lot H ter) répondent à deux
constats distincts de la mesure du lot H bis : à Intermédiaire, le style ne
se voit pas assez ; à Avancé, il rend le personnage trop fort.

* ``poids_tirage_scrabble`` = :data:`POIDS_TIRAGE_SCRABBLE_CHASSEUR` = 5.0 :
  nouveau champ de :class:`~scrabble.moteur.ia.ProfilPersonnage`, neutre
  (``None``, tirage uniforme) en l'absence de personnage. S'applique
  uniquement aux niveaux qui tirent au hasard dans une tranche de meilleurs
  coups (DEBUTANT, FACILE, INTERMEDIAIRE, EXPERT — voir
  :func:`scrabble.moteur.ia._tirer_dans_tranche`) : sans effet à Avancé, qui
  joue toujours son meilleur coup. Répond au premier constat : à
  Intermédiaire, le tirage uniforme dans la tranche des 15 % meilleurs coups
  dilue l'effet d'un scrabble qui n'y figure qu'une fois sur 10 à 15 coups —
  ce réglage lui donne plus de poids dans ce tirage, sans changer la
  composition de la tranche. Reste **plat** comme les trois réglages
  précédents : voir :data:`POIDS_TIRAGE_SCRABBLE_CHASSEUR` pour le calcul
  justifiant la valeur 5.0.
* ``part_vocabulaire_long`` : pas un champ plat pour ce personnage — table
  :data:`PART_VOCABULAIRE_LONG_CHASSEUR` (niveau → part), transmise via
  :attr:`Personnage.part_vocabulaire_long_par_niveau` et résolue par
  :func:`profil_pour_niveau` (pas directement accessible depuis ``profil``
  ci-dessus, qui reste la valeur plate sans résolution de niveau). Répondait au
  second constat : à Avancé, réduire la part de mots longs accessibles hors
  du vocabulaire du niveau rapprochait la force du personnage de celle de
  Classique sans toucher au vocabulaire du niveau lui-même ni aux mots
  courts — remis à 100 % aux deux niveaux par le lot H quater ci-dessous, qui
  reprend ce levier autrement.

Les mesures du lot H ter (100 parties, bruitées de plusieurs points) ont
confirmé que le style se voit enfin (0,14 scrabble par partie à Intermédiaire
contre 0,01 pour Classique, 0,4 contre 0,11 à Avancé) mais à un prix trop
élevé : environ +12 points par partie à Intermédiaire, +20 à Avancé contre
Classique au même niveau — la règle « un personnage ne change pas la force du
niveau » n'est plus respectée. Un scrabble rapportant beaucoup de points (de
l'ordre de 80 en moyenne), le surplus de scrabbles explique une large part de
ce surplus de force ; les mesures du curseur ``part_vocabulaire_long`` à des
valeurs intermédiaires (30 à 70 % à Intermédiaire, 20 à 50 % à Avancé)
montrent qu'aux parts basses, le surplus de scrabbles devient à peine visible
alors qu'un excédent de force de 6 à 9 points subsiste — réduire SEULEMENT le
vocabulaire long ne suffit pas à retrouver la neutralité de force, et dilue le
style en même temps qu'il la réduit.

Un réglage supplémentaire (issue #453, lot H quater) prend le problème à
l'envers : garder la connaissance des longs mots intacte (100 % aux deux
niveaux, pour que le style reste entier) et faire payer la force du
personnage par une MOINS BONNE connaissance des mots courts — pour qu'il
devienne un spécialiste des scrabbles qui joue moins bien le reste, un
personnage plus marqué et plus cohérent que la réduction symétrique du lot H
ter.

* ``part_vocabulaire_court`` = :data:`PART_VOCABULAIRE_COURT_CHASSEUR`
  (niveau → part, transmise comme ``part_vocabulaire_long`` via
  :attr:`Personnage.part_vocabulaire_court_par_niveau` et résolue par
  :func:`profil_pour_niveau`) : les coups dont le mot principal compte moins
  de 7 lettres (:data:`~scrabble.moteur.ia._SEUIL_VOCABULAIRE_LONG`) ne
  restent candidats que si ce mot fait partie de la fraction « connue »
  (:func:`scrabble.moteur.ia._mot_connu_vocabulaire_court`, même procédé
  déterministe que les mots longs, décalage de hachage distinct pour une
  sélection indépendante). Les mots de 7 lettres et plus — du vocabulaire du
  niveau ou ajoutés par ``vocabulaire_long`` — ne sont jamais concernés.
  Garde-fou : si le filtre ne laisse plus aucun coup candidat (début de
  partie, chevalet difficile), il est ignoré pour ce tour plutôt que de
  forcer une passe qui fausserait la mesure (voir
  :func:`scrabble.moteur.ia._generer_coups_candidats`).

  Valeur de départ, aux deux niveaux : 70 % — point médian raisonné entre
  « tout » (comportement actuel, trop fort) et une restriction sévère qui
  risquerait de ne plus trouver assez de coups courts pour varier le jeu,
  dans le même esprit que le point médian 50 % choisi au lot H ter pour
  ``part_vocabulaire_long`` à Avancé ; à ajuster par Alain après mesure avec
  ``scripts/mesurer_force_niveaux.py`` — objectif : écart de points proche de
  zéro contre Classique au même niveau, avec un surplus de scrabbles qui
  reste visible.

Les valeurs ci-dessus sont des points de départ raisonnés (le dictionnaire
réel n'est pas disponible dans ce worktree isolé pour les mesurer par
parties jouées, voir le rapport des issues #448, #450, #451 et #453) —
provisoires, destinées à être ajustées par Alain après mesure avec
``scripts/mesurer_force_niveaux.py``, comme pour Opportuniste.

Personnage Titeuf
------------------
Face à sa mamy, ne trouve jamais que des mots de cour de récré — caca, prout
et compagnie — même quand ça ne rapporte presque rien. Généralise à une
LISTE de mots les deux mécanismes du Chasseur de scrabbles (issues #450/#451,
lots H bis/H ter), qui, eux, portaient sur un critère de LONGUEUR :

* :attr:`~scrabble.moteur.ia.ProfilPersonnage.mots_favoris` (issue #452, lot
  J) : liste de mots, chargée depuis :data:`CHEMIN_MOTS_FAVORIS_TITEUF`
  (:func:`charger_mots_favoris`) — un fichier texte simple, un mot par ligne,
  modifiable sans toucher au code. Liste de départ (choix d'Alain à relire
  avant le build) : des mots courts et humoristiques de cour de récré, sans
  injure ni terme haineux — caca, pipi, prout, crotte, popo, fesses, zizi,
  slip, beurk, sexe. Un mot absent du lexique complet installé n'est filtré
  par AUCUN code dédié : la génération/validation
  (:func:`scrabble.moteur.ia._generer_coups_candidats`) ne produit alors tout
  simplement aucun coup valide pour lui.
* :attr:`~scrabble.moteur.ia.ProfilPersonnage.poids_tirage_favori` =
  :data:`POIDS_TIRAGE_FAVORI_TITEUF` = 50.0 : poids de tirage des coups dont
  le mot principal est un mot favori (voir
  :func:`scrabble.moteur.ia._tirer_dans_tranche`), AJOUTÉS au tirage même
  s'ils sont exclus de la tranche des meilleurs coups — différence
  essentielle avec ``poids_tirage_scrabble`` du Chasseur, nécessaire ici
  puisque les mots de la liste (courts, peu de cases premium visées) sont
  plausiblement souvent hors du haut du tri par score stratégique.

  Calcul justifiant 50 : à DEBUTANT (seul niveau où Titeuf est disponible),
  la tranche est le TOP 70 % des coups candidats — une tranche bien plus
  large que celles du Chasseur (top 5/15 %), donc un nombre de coups ``n``
  en jeu typiquement bien plus grand (le dictionnaire réel n'étant pas
  disponible dans ce worktree isolé pour le mesurer, on l'estime par
  analogie : si le nombre total de coups candidats est d'un ordre de
  grandeur comparable à celui observé pour le Chasseur, le TOP 70 % couvre
  alors de l'ordre de ``50`` coups, contre ``10`` à ``20`` pour un TOP 15 %).
  Avec un poids ``w`` sur le seul coup à mot favori parmi ``n`` coups de
  poids 1 chacun, la probabilité de le tirer est ``w / (n - 1 + w)`` : pour
  retrouver l'objectif de comportement (joué dans environ la moitié des cas
  ou plus, quand il est jouable), il faut ``w ≥ n - 1`` ; à ``n = 50``,
  ``w = 50`` redonne très exactement 50 % — et, pour un ``n`` plus petit (cas
  fréquent : la tranche à 70 % exclut seulement le pire tiers des coups, un
  mot court raisonnable y figure souvent déjà), la même valeur donne une
  probabilité supérieure à 50 % (ex. 71 % à ``n = 20``). Point de départ,
  comme les réglages du Chasseur, à ajuster par Alain après mesure réelle
  avec ``scripts/mesurer_force_niveaux.py`` (voir le rapport de l'issue
  #452) — l'indicateur de style « coups dont le mot principal est un mot
  favori » permet de vérifier si l'objectif de ~50 % est atteint.

Disponibilité (issue #452, lot J) : :data:`NIVEAUX_TITEUF` (Débutant
seulement — c'est le seul niveau sans aucun personnage disponible
aujourd'hui, d'où ce lot) et :data:`NB_JOUEURS_TITEUF` (deux joueurs
seulement, même prudence que les autres personnages). Avec Titeuf, Débutant
compte maintenant deux personnages réels (Classique + Titeuf) : la règle déjà
en place (:func:`aleatoire_disponible_a_niveau`) rend Aléatoire de nouveau
disponible à ce niveau, sans aucune autre modification.

Personnage Lettré
------------------
Connaît des mots que presque personne n'utilise et les place avec fierté,
même quand un mot plus simple rapporterait autant. Reprend EXACTEMENT le
mécanisme de Titeuf (issue #452, lot J) avec sa propre liste — une LISTE de
mots différente, choisie pour son caractère rare/littéraire plutôt que
cour de récré, rien à généraliser dans le code puisque Titeuf l'avait déjà
fait au bon niveau de généralité (liste quelconque, pas « liste de mots de
cour de récré ») :

* :attr:`~scrabble.moteur.ia.ProfilPersonnage.mots_favoris` chargée depuis
  :data:`CHEMIN_MOTS_FAVORIS_LETTRE` (:func:`charger_mots_favoris`, même
  fonction que Titeuf). Liste de départ (fournie par Alain, voir
  ``data/personnages/lettre_mots_favoris.txt``) : des mots rares/littéraires
  croisés depuis Lexique 3 (``Lexique383.tsv``) avec l'ODS8, sans filtrage
  mécanique d'un critère de rareté — c'est la liste elle-même, choisie à la
  main, qui définit ce qu'est un « mot rare » pour ce personnage. Un mot
  absent du lexique complet installé n'est filtré par AUCUN code dédié,
  exactement comme pour Titeuf.

Différence essentielle avec Titeuf (issue #454, lot K) : le tirage pondéré
de Titeuf (:attr:`~scrabble.moteur.ia.ProfilPersonnage.poids_tirage_favori`)
n'a aucun effet sur AVANCE et CHAMPION_DU_MONDE, qui jouent toujours leur
meilleur coup — un mot favori n'y serait donc joué que s'il l'est déjà par
hasard, sans aucun style perceptible. Lettré a donc besoin d'un second
levier, nouveau (issue #454, lot K), qui agit lui AVANT le tri par score
plutôt qu'après, donc à tous les niveaux :

* :attr:`~scrabble.moteur.ia.ProfilPersonnage.bonus_favori` =
  :data:`BONUS_FAVORI_LETTRE` = 40 : ajoute cette constante au score
  stratégique (:func:`scrabble.moteur.ia._score_strategique`) des coups dont
  le mot principal est un mot favori — voir la docstring du module
  ``scrabble.moteur.ia`` pour le détail du calcul. Neutre par défaut
  (``None``, traité comme 0), sans effet sur aucun autre personnage ni sur
  Titeuf (qui ne renseigne pas ce champ).

  Calcul justifiant 40 (valeur demandée par l'issue #454, le dictionnaire
  réel n'étant pas disponible dans ce worktree isolé pour la mesurer par
  parties jouées comme Alain le fera avec
  ``scripts/mesurer_force_niveaux.py``) : par analogie avec l'échelle déjà en
  production de :data:`scrabble.moteur.ia._BONUS_PREMIUM` (3 à DEBUTANT,
  jusqu'à 20 à EXPERT/CHAMPION_DU_MONDE) et de
  :data:`scrabble.moteur.ia._MALUS_LONGUEUR` (jusqu'à -25) — les deux plus
  gros écarts que le score stratégique absorbe déjà en production à ces
  niveaux. 40, environ le double du plus haut bonus premium de production
  (20), suffit à faire gagner un mot favori à score brut comparable ou
  légèrement inférieur à celui d'un concurrent sans être pour autant
  écrasant : un coup nettement meilleur (par exemple posant une case
  MOT_TRIPLE, bonus 20, cumulé à un score brut supérieur de plus de 40
  points) continue de l'emporter, pour que Lettré reste reconnaissable sans
  cesser d'être un joueur de son niveau. À ajuster par Alain après mesure
  réelle (part de coups sur mot favori et écart de score contre Classique au
  même niveau), comme les autres valeurs de départ de ce module.

Le tirage pondéré (``poids_tirage_favori``) n'est volontairement PAS
renseigné pour Lettré : seul EXPERT, parmi ses niveaux de disponibilité,
tire au hasard dans une tranche (top 5 %) — AVANCE et CHAMPION_DU_MONDE n'en
tireraient aucun bénéfice — et ``bonus_favori`` suffit déjà, à ce niveau, à
faire remonter un mot favori suffisamment bien noté dans cette tranche
étroite ; à ajouter si une mesure réelle montre que ça ne suffit pas à
EXPERT.

Disponibilité (issue #454, lot K, provisoire) : :data:`NIVEAUX_LETTRE`
(Avancé, Expert et Champion du monde — les niveaux qui jouent déjà sur un
vocabulaire suffisamment riche pour que des mots rares y apparaissent
naturellement, et où ``bonus_favori`` a un effet direct puisqu'ils trient
par score) et :data:`NB_JOUEURS_LETTRE` (deux joueurs seulement, même
prudence que les autres personnages). Alain ajustera ces niveaux après
mesure. Avec Lettré, Avancé, Expert et Champion du monde comptent chacun
trois personnages réels ou plus (au moins Classique + Chasseur de
scrabbles/Opportuniste selon le niveau + Lettré) : Aléatoire y reste
disponible, sans aucune autre modification (règle déjà en place).

Désactivation de Chasseur de scrabbles et Lettré (issue #459)
----------------------------------------------------------------
Mesures du 12 octobre 2026 (``scripts/mesurer_force_niveaux.py``, partie
réellement jouées) : l'effet des deux personnages est trop discret pour être
remarqué en jeu — environ 0,45 scrabble supplémentaire par partie à Avancé et
0,2 à Intermédiaire pour Chasseur de scrabbles ; environ deux mots de sa
liste par partie pour Lettré. Alain abandonne les deux, mais rien n'est
supprimé : code, constantes de réglage (``BONUS_SEPT_LETTRES_CHASSEUR``,
``PART_VOCABULAIRE_COURT_CHASSEUR``, ``BONUS_FAVORI_LETTRE``, etc.), listes de
mots (``lettre_mots_favoris.txt``) et tests de comportement restent en place
pour une réactivation éventuelle si une meilleure idée de calibrage apparaît.

Le registre porte désormais un indicateur :attr:`Personnage.actif` (vrai par
défaut) : les deux entrées ``"chasseur_de_scrabbles"`` et ``"lettre"`` le
déclarent à ``False`` ci-dessous. Un personnage inactif reste une entrée
normale de :data:`PERSONNAGES` — :func:`obtenir_personnage`,
:func:`profil_pour_niveau`, une partie sauvegardée qui le mentionne
(:func:`~scrabble.moteur.partie.creer_partie` ne vérifie elle-même aucune
disponibilité) et le script de mesure continuent de le résoudre normalement.
Seules les fonctions qui PROPOSENT un personnage au joueur ou au tirage
``aleatoire`` l'excluent : :func:`tirer_personnage`,
:func:`personnages_disponibles_a_niveau`,
:func:`personnages_disponibles_a_nb_joueurs`, :func:`lister_personnages`
(fenêtre « Les personnages ») et :meth:`~scrabble.ui.accueil.ApiAccueil.
obtenir_personnages` (sélecteur de l'accueil) — donc aussi
:func:`aleatoire_disponible_a_niveau`/:func:`aleatoire_disponible_a_nb_joueurs`,
qui ne comptent plus que les personnages actifs. L'ajout d'un ordinateur sur
un personnage inactif est refusé côté serveur
(:meth:`~scrabble.ui.accueil.ApiAccueil.ajouter_ordinateur`) avec un message
dédié, avant même le contrôle de niveau/taille de table.

Réactivation : repasser ``actif=True`` sur l'entrée du registre (ci-dessous)
suffit à tout remettre en place, sans aucune autre modification — c'est
exactement l'inverse de cette désactivation.

Liste complémentaire locale, hors dépôt (issue #455)
------------------------------------------------------
En plus de ``data/personnages/lettre_mots_favoris.txt`` (suivi par git),
:data:`MOTS_FAVORIS_LETTRE` est l'union avec un second fichier facultatif,
:data:`CHEMIN_MOTS_FAVORIS_LETTRE_MERAL`
(``data/personnages/lettre_mots_meral.txt``), JAMAIS suivi par git (voir
``.gitignore``) : Alain peut y ajouter des mots tirés d'une source qu'il ne
veut pas publier dans le dépôt. Absent — cas de tout autre poste de travail,
de la CI et de tout worktree isolé — le comportement est exactement celui
d'avant ce lot. Le chargement réutilise :func:`charger_mots_favoris_avec_complement`,
qui réutilise elle-même :func:`charger_mots_favoris` deux fois (même règles
de normalisation pour les deux fichiers) plutôt que d'introduire un nouveau
mécanisme de lecture — Titeuf ou un futur personnage à liste pourrait s'en
servir de la même façon, sans qu'il n'en profite aujourd'hui.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from scrabble.config import RACINE_PROJET
from scrabble.dictionnaire.dictionnaire import desaccentuer, lire_liste_mots
from scrabble.moteur.ia import Niveau, ProfilPersonnage

#: Renforcement du bonus premium d'Opportuniste (voir docstring du module) :
#: valeur la plus haute déjà en production (20, EXPERT/CHAMPION_DU_MONDE) +
#: le plus grand palier observé entre deux niveaux adjacents (+8, AVANCE ->
#: EXPERT).
BONUS_PREMIUM_OPPORTUNISTE = 100

#: Bonus de pose de 7 lettres du personnage Chasseur de scrabbles (voir
#: docstring du module, issue #448, lot H) : valeur de départ, à ajuster par
#: mesure.
BONUS_SEPT_LETTRES_CHASSEUR = 150

#: Poids du leave du personnage Chasseur de scrabbles (voir docstring du
#: module, issue #450, lot H bis — valait 2.0 au lot H, issue #448) :
#: ``None`` = aucune surcharge, le poids de leave du niveau du joueur
#: s'applique tel quel. Constante nommée pour être ajustée par mesure : une
#: valeur légèrement supérieure à celle du niveau (p. ex. un petit flottant
#: positif) remplacerait ``None`` si la mesure montre que Chasseur garde
#: encore trop facilement un petit coup plutôt qu'un reliquat prometteur.
#: Inchangé par le lot H ter (issue #451, voir ci-dessous).
POIDS_LEAVE_CHASSEUR_SCRABBLES: float | None = None

#: Poids de tirage des scrabbles du personnage Chasseur de scrabbles (issue
#: #451, lot H ter, champ :attr:`~scrabble.moteur.ia.ProfilPersonnage.poids_tirage_scrabble`) :
#: valeur de départ, à ajuster par mesure.
#:
#: Calcul justifiant 5 : aux niveaux qui tirent au hasard dans une tranche
#: de meilleurs coups (seul cas où ce champ a un effet — voir
#: :func:`scrabble.moteur.ia._tirer_dans_tranche`), la tranche compte, en
#: pratique, de l'ordre de 10 à 20 coups. Sans ce champ (tirage uniforme), la
#: probabilité de tirer un scrabble présent dans la tranche n'est que
#: ``1/n`` (5 % à 10 %). Avec un poids ``w`` sur ce seul coup parmi les
#: ``n`` de la tranche (chaque autre coup gardant le poids 1), cette
#: probabilité devient ``w / (n - 1 + w)``. Pour ``w = 5`` :
#: ``5 / (10 - 1 + 5) = 5/14 ≈ 36 %`` à ``n = 10``, et
#: ``5 / (20 - 1 + 5) = 5/24 ≈ 21 %`` à ``n = 20`` — une hausse nette (de
#: l'ordre d'un facteur 3 à 4) tout en laissant encore la majorité des tirages
#: aux autres coups de la tranche : ni un tirage toujours gagnant pour le
#: scrabble (qui romprait la règle « même tranche, probabilités seulement
#: modifiées »), ni un effet trop dilué pour être visible en mesure (constat
#: de départ de l'issue #451, à Intermédiaire où le lot H bis ne se voyait
#: pas).
POIDS_TIRAGE_SCRABBLE_CHASSEUR: float | None = 5.0

#: Bonus de mot favori du personnage Lettré (issue #454, lot K, champ
#: :attr:`~scrabble.moteur.ia.ProfilPersonnage.bonus_favori`) : valeur de
#: départ demandée par l'issue, voir la docstring du module pour le calcul
#: complet la justifiant par analogie avec l'échelle de
#: :data:`scrabble.moteur.ia._BONUS_PREMIUM` — à ajuster par Alain après
#: mesure réelle avec ``scripts/mesurer_force_niveaux.py``.
BONUS_FAVORI_LETTRE = 20

#: Part des mots de 7 lettres et plus du lexique complet (hors vocabulaire
#: du niveau) connue du personnage Chasseur de scrabbles, par niveau (issue
#: #451, lot H ter, champ :attr:`~scrabble.moteur.ia.ProfilPersonnage.part_vocabulaire_long`) :
#: table niveau → part, un niveau absent de la table (ou avec ``vocabulaire_long``
#: inactif, voir :data:`NIVEAUX_CHASSEUR_SCRABBLES`) n'a aucun sens à régler
#: ici.
#:
#: Remise à 1.0 (100 %) aux deux niveaux par le lot H quater (issue #453) :
#: le lot H ter avait réduit AVANCE à 0.5 pour contrer l'excès de force du
#: personnage, mais les mesures à parts intermédiaires ont montré que ce
#: levier dilue le style (le surplus de scrabbles devient à peine visible
#: aux parts basses) sans forcément retrouver la neutralité de force — voir
#: la docstring du module. Le lot H quater reprend ce problème avec
#: :data:`PART_VOCABULAIRE_COURT_CHASSEUR` à la place : la connaissance des
#: longs mots reste donc entière, c'est la connaissance des mots COURTS qui
#: ajuste la force.
PART_VOCABULAIRE_LONG_CHASSEUR: dict[Niveau, float] = {
    Niveau.INTERMEDIAIRE: 1.0,
    Niveau.AVANCE: 1.0,
}

#: Part des mots de MOINS de 7 lettres du vocabulaire du niveau connue du
#: personnage Chasseur de scrabbles, par niveau (issue #453, lot H quater,
#: champ :attr:`~scrabble.moteur.ia.ProfilPersonnage.part_vocabulaire_court`) :
#: table niveau → part, résolue comme :data:`PART_VOCABULAIRE_LONG_CHASSEUR`
#: par :func:`profil_pour_niveau` via :attr:`Personnage.part_vocabulaire_court_par_niveau`.
#:
#: Valeur de départ, aux deux niveaux : 0.7 (70 %) — voir la docstring du
#: module pour le raisonnement complet (point médian entre comportement
#: actuel et restriction sévère, à ajuster par mesure réelle avec
#: ``scripts/mesurer_force_niveaux.py``, objectif : écart de points proche
#: de zéro contre Classique avec un surplus de scrabbles qui reste visible).
PART_VOCABULAIRE_COURT_CHASSEUR: dict[Niveau, float] = {
    Niveau.INTERMEDIAIRE: 0.7,
    Niveau.AVANCE: 0.55,
}

#: Dossier des petites listes de personnalisation par personnage (issue
#: #452, lot J) — distinct de ``data/dictionnaire`` (dictionnaires tiers,
#: gitignorés, déposés manuellement) : ces fichiers sont de petites listes
#: éditoriales, versionnées avec le code.
DOSSIER_PERSONNAGES = RACINE_PROJET / "data" / "personnages"

#: Chemin de la liste de mots favoris de Titeuf (issue #452, lot J) : un mot
#: par ligne, modifiable sans toucher au code (voir le docstring du module).
CHEMIN_MOTS_FAVORIS_TITEUF: Path = DOSSIER_PERSONNAGES / "titeuf_mots_favoris.txt"


def charger_mots_favoris(chemin: Path) -> frozenset[str]:
    """Charge une liste « un mot par ligne » de mots favoris (issue #452, lot J).

    Reprend :func:`~scrabble.dictionnaire.dictionnaire.lire_liste_mots` (même
    tolérance : fichier absent -> ensemble vide, sans erreur — convient à une
    liste facultative) puis désaccentue chaque mot
    (:func:`~scrabble.dictionnaire.dictionnaire.desaccentuer`) pour rester
    comparable aux lettres posées sur le plateau (toujours désaccentuées) et
    aux entrées du Trie de validation (issue #281). Les mots absents du
    lexique complet ne sont PAS filtrés ici : ils le sont naturellement lors
    de la génération/validation des coups candidats
    (:func:`scrabble.moteur.ia._generer_coups_candidats`), sans code dédié.
    """
    return frozenset(desaccentuer(mot) for mot in lire_liste_mots(chemin))


def charger_mots_favoris_avec_complement(
    chemin: Path, chemin_complement: Path
) -> frozenset[str]:
    """Union de :func:`charger_mots_favoris` sur ``chemin`` et sur
    ``chemin_complement`` (issue #455).

    ``chemin_complement`` est facultatif au même titre que ``chemin`` :
    absent ou vide, le résultat est identique à ``charger_mots_favoris(chemin)``
    seul. Généralise le chargement d'une liste de personnage à un second
    fichier complémentaire SANS créer de mécanisme nouveau — pour que Titeuf
    ou un futur personnage à liste puisse en bénéficier plus tard sans
    modification de cette fonction ; aujourd'hui, seul le Lettré l'appelle
    (voir :data:`CHEMIN_MOTS_FAVORIS_LETTRE_MERAL`).
    """
    return charger_mots_favoris(chemin) | charger_mots_favoris(chemin_complement)


#: Mots favoris de Titeuf, chargés une fois au chargement de ce module (issue
#: #452, lot J) — modifier le fichier suppose de relancer l'application, pas
#: de modifier le code (voir :data:`CHEMIN_MOTS_FAVORIS_TITEUF`).
MOTS_FAVORIS_TITEUF: frozenset[str] = charger_mots_favoris(CHEMIN_MOTS_FAVORIS_TITEUF)

#: Poids de tirage des coups à mot favori du personnage Titeuf (issue #452,
#: lot J, champ :attr:`~scrabble.moteur.ia.ProfilPersonnage.poids_tirage_favori`) :
#: valeur de départ, à ajuster par mesure — voir le docstring du module pour
#: le calcul détaillé.
POIDS_TIRAGE_FAVORI_TITEUF: float | None = 50.0

#: Prénom affiché de Titeuf (issue #452, lot J) — un seul endroit à modifier
#: pour en changer l'affichage.
PRENOM_TITEUF = "Titeuf"

#: Niveaux où Titeuf est disponible (issue #452, lot J) : Débutant
#: uniquement — le seul niveau sans aucun personnage disponible avant ce lot
#: (Opportuniste et Chasseur de scrabbles l'excluent tous les deux, voir
#: :data:`NIVEAUX_OPPORTUNISTE`/:data:`NIVEAUX_CHASSEUR_SCRABBLES`).
NIVEAUX_TITEUF: frozenset[Niveau] = frozenset({Niveau.DEBUTANT})

#: Tailles de table où Titeuf est disponible (issue #452, lot J) : deux
#: joueurs seulement, même prudence que les autres personnages (voir
#: :data:`NB_JOUEURS_OPPORTUNISTE`).
NB_JOUEURS_TITEUF: frozenset[int] = frozenset({2})

#: Chemin de la liste de mots favoris du Lettré (issue #454, lot K) : même
#: principe que :data:`CHEMIN_MOTS_FAVORIS_TITEUF`, fichier distinct, fourni
#: par Alain (voir la docstring du module).
CHEMIN_MOTS_FAVORIS_LETTRE: Path = DOSSIER_PERSONNAGES / "lettre_mots_favoris.txt"

#: Chemin de la liste complémentaire, locale et facultative, de mots favoris
#: du Lettré (issue #455) : mots qu'Alain veut ajouter sans les publier dans
#: le dépôt (source dont il ne souhaite pas que la liste soit visible sur
#: git) — jamais suivie par git (voir ``.gitignore``), absente par défaut sur
#: toute autre machine, y compris en CI et dans les worktrees isolés. Fichier
#: absent ou vide : aucune différence avec le comportement d'avant ce lot.
CHEMIN_MOTS_FAVORIS_LETTRE_MERAL: Path = DOSSIER_PERSONNAGES / "lettre_mots_meral.txt"

#: Mots favoris du Lettré, chargés une fois au chargement de ce module
#: (issue #454, lot K ; étendu issue #455 à l'union avec le fichier
#: complémentaire local ci-dessus) — liste indépendante de
#: :data:`MOTS_FAVORIS_TITEUF`, modifier l'un des deux fichiers n'affecte
#: jamais l'autre personnage.
MOTS_FAVORIS_LETTRE: frozenset[str] = charger_mots_favoris_avec_complement(
    CHEMIN_MOTS_FAVORIS_LETTRE, CHEMIN_MOTS_FAVORIS_LETTRE_MERAL
)

#: Prénom affiché du Lettré (issue #454, lot K).
PRENOM_LETTRE = "Lettré"

#: Niveaux où le Lettré est disponible (issue #454, lot K, provisoire) :
#: Avancé, Expert et Champion du monde — voir la docstring du module pour la
#: justification, à ajuster par Alain après mesure.
NIVEAUX_LETTRE: frozenset[Niveau] = frozenset(
    {Niveau.AVANCE, Niveau.EXPERT, Niveau.CHAMPION_DU_MONDE}
)

#: Tailles de table où le Lettré est disponible (issue #454, lot K) : deux
#: joueurs seulement, même prudence que les autres personnages.
NB_JOUEURS_LETTRE: frozenset[int] = frozenset({2})

#: Clé pseudo-personnage exposée à l'UI (issue #440, lot D) : « Aléatoire »
#: n'est **jamais** une entrée de :data:`PERSONNAGES` — elle désigne le choix
#: « tire un personnage réel au lancement de la partie et cache-le ». Le
#: moteur ne connaît que des personnages réels : cette clé n'apparaît donc
#: jamais dans :attr:`~scrabble.moteur.partie.Joueur.personnage`, seulement
#: dans la configuration de l'écran d'accueil, avant résolution.
CLE_ALEATOIRE = "aleatoire"

#: Texte de mystère affiché à l'accueil quand « Aléatoire » est sélectionné
#: (issue #440, lot D) : ne doit rien révéler de l'identité qui sera tirée.
DESCRIPTION_ALEATOIRE = (
    "Un caractère sera tiré au sort au lancement de la partie et restera "
    "secret jusqu'à l'écran de résultat."
)


#: Tous les niveaux de difficulté — valeur par défaut de
#: :attr:`Personnage.niveaux_disponibles` (issue #447, lot G) : un personnage
#: qui ne déclare rien reste disponible partout, comme Classique.
TOUS_NIVEAUX: frozenset[Niveau] = frozenset(Niveau)

#: Niveaux où Opportuniste est disponible (issue #447, lot G) : de Facile à
#: Champion du monde, **pas** Débutant. D'après les mesures de l'issue #437,
#: à Débutant l'ordinateur joue tiré au hasard parmi 70 % des meilleurs coups
#: et Opportuniste y utilise les cases bonus à peine plus souvent que
#: Classique (20,5 % contre 20,1 %) : son caractère n'y est pas perceptible.
NIVEAUX_OPPORTUNISTE: frozenset[Niveau] = TOUS_NIVEAUX - {Niveau.DEBUTANT}

#: Niveaux où Chasseur de scrabbles est disponible (issue #450, lot H bis,
#: provisoire — remplace la plage « Avancé à Champion du monde » du lot H,
#: issue #448) : Intermédiaire et Avancé.
#:
#: Le caractère du personnage (lot H bis) vient du vocabulaire, pas du bonus
#: de score : il n'existe que là où le vocabulaire du niveau est RESTREINT
#: par rapport au lexique complet (``vocabulaire_long`` élargit alors
#: réellement les coups candidats). D'après
#: :data:`scrabble.moteur.ia._PALIERS_PAR_NIVEAU` et la configuration des
#: paliers (``scrabble.dictionnaire.dictionnaire.FICHIERS_VOCABULAIRE_PALIER``,
#: quatre entrées : debutant/facile/intermediaire/avance), seuls DEBUTANT,
#: FACILE, INTERMEDIAIRE et AVANCE ont un vocabulaire restreint — EXPERT et
#: CHAMPION_DU_MONDE n'ont volontairement aucune entrée de palier
#: (:func:`scrabble.moteur.ia.resoudre_palier` y renvoie ``None``) : ces deux
#: niveaux jouent déjà sur le lexique complet, donc ``vocabulaire_long`` n'y
#: changerait rigoureusement rien (même raisonnement que l'exclusion de
#: Champion du monde proposée par l'issue #450 — étendu ici à Expert, pour la
#: même raison). Parmi les niveaux à vocabulaire restreint, DEBUTANT et
#: FACILE restent exclus (scrabbles peu réalistes à ces niveaux, même
#: critère qu'au lot H) : restent INTERMEDIAIRE et AVANCE. Plage provisoire,
#: à élargir ou réduire par Alain après mesure réelle, **en un seul endroit**
#: (cette constante).
NIVEAUX_CHASSEUR_SCRABBLES: frozenset[Niveau] = frozenset(
    {Niveau.INTERMEDIAIRE, Niveau.AVANCE}
)

#: Toutes les tailles de table (nombre total de joueurs) — valeur par défaut
#: de :attr:`Personnage.nb_joueurs_disponibles` (issue #449, lot I) : un
#: personnage qui ne déclare rien reste disponible à toutes les tailles,
#: comme Classique. Une table ne compte jamais moins de deux joueurs (il
#: faut au moins un adversaire) ni plus de quatre
#: (:data:`scrabble.moteur.partie.MAX_JOUEURS`).
TOUTES_TAILLES: frozenset[int] = frozenset({2, 3, 4})

#: Tailles de table où Opportuniste est disponible (issue #449, lot I) :
#: deux joueurs seulement. Tous les réglages et mesures des personnages ont
#: été faits en parties à deux (rapport d'investigation #437) ; rien n'a été
#: vérifié à trois ou quatre joueurs (plateau qui se remplit plus vite, moins
#: de coups par joueur) — réservé par prudence pour cette première diffusion,
#: à élargir par Alain après mesure, **en un seul endroit** (cette constante).
NB_JOUEURS_OPPORTUNISTE: frozenset[int] = frozenset({2})

#: Tailles de table où Chasseur de scrabbles est disponible (issue #449, lot
#: I) : deux joueurs seulement, même raison qu'Opportuniste ci-dessus.
NB_JOUEURS_CHASSEUR_SCRABBLES: frozenset[int] = frozenset({2})


@dataclass(frozen=True)
class Personnage:
    """Un personnage : prénom, description de caractère (FR), profil stratégique.

    ``niveaux_disponibles`` (issue #447, lot G) : l'ensemble des niveaux où ce
    personnage peut être choisi — facultatif, vaut :data:`TOUS_NIVEAUX` par
    défaut (cas de Classique), pour qu'un futur personnage sans déclaration
    explicite reste disponible partout.

    ``nb_joueurs_disponibles`` (issue #449, lot I) : l'ensemble des tailles de
    table (nombre total de joueurs) où ce personnage peut être choisi —
    facultatif lui aussi, vaut :data:`TOUTES_TAILLES` par défaut (cas de
    Classique), indépendamment de ``niveaux_disponibles``. Les deux
    restrictions se combinent (ET logique) : un personnage doit être
    disponible à la fois au niveau et à la taille de table concernés.

    ``part_vocabulaire_long_par_niveau`` (issue #451, lot H ter) : surcharge
    optionnelle, par niveau, du champ
    :attr:`~scrabble.moteur.ia.ProfilPersonnage.part_vocabulaire_long` de
    ``profil`` — ``None`` par défaut (aucune surcharge, cas de Classique et
    Opportuniste : ``profil.part_vocabulaire_long`` s'applique tel quel,
    identique quel que soit le niveau). Un niveau absent de la table se
    comporte comme si la table elle-même était absente. Résolu par
    :func:`profil_pour_niveau`, jamais directement par :attr:`profil` (qui
    reste la valeur « plate », sans résolution de niveau — voir les tests
    qui y accèdent directement pour les niveaux sans surcharge, p. ex.
    AVANCE n'y est câblé que dans la table, pas dans ``profil`` lui-même).

    ``part_vocabulaire_court_par_niveau`` (issue #453, lot H quater) : même
    principe de surcharge, pour le champ
    :attr:`~scrabble.moteur.ia.ProfilPersonnage.part_vocabulaire_court` —
    table indépendante de ``part_vocabulaire_long_par_niveau``, les deux
    pouvant être renseignées simultanément (cas de Chasseur de scrabbles)
    sans interférence : chacune ne touche que le champ de ``profil`` qui lui
    correspond.

    ``actif`` (issue #459) : facultatif, vrai par défaut — un personnage qui
    ne déclare rien reste proposé partout, comme avant ce champ. Un
    personnage inactif (``actif=False``, cas de Chasseur de scrabbles et de
    Lettré depuis cette issue) n'est plus proposé par
    :func:`tirer_personnage`, :func:`personnages_disponibles_a_niveau`,
    :func:`personnages_disponibles_a_nb_joueurs` ni :func:`lister_personnages`
    — mais reste une entrée normale de :data:`PERSONNAGES`, résolue comme
    n'importe quel autre personnage par :func:`obtenir_personnage` et
    :func:`profil_pour_niveau` (une partie sauvegardée qui le mentionne
    continue de se jouer sans changement). Voir la docstring du module pour
    la procédure de réactivation.
    """

    cle: str
    prenom: str
    description: str
    profil: ProfilPersonnage
    niveaux_disponibles: frozenset[Niveau] = field(
        default_factory=lambda: TOUS_NIVEAUX
    )
    nb_joueurs_disponibles: frozenset[int] = field(
        default_factory=lambda: TOUTES_TAILLES
    )
    part_vocabulaire_long_par_niveau: dict[Niveau, float] | None = None
    part_vocabulaire_court_par_niveau: dict[Niveau, float] | None = None
    actif: bool = True


def profil_pour_niveau(cle: str, niveau: Niveau | None) -> ProfilPersonnage:
    """Résout le :class:`~scrabble.moteur.ia.ProfilPersonnage` de ``cle`` pour ``niveau``
    (issue #451, lot H ter ; étendu issue #453, lot H quater).

    Reprend :attr:`Personnage.profil` tel quel, sauf si
    :attr:`Personnage.part_vocabulaire_long_par_niveau` et/ou
    :attr:`Personnage.part_vocabulaire_court_par_niveau` sont renseignés ET
    contiennent une entrée pour ``niveau`` : dans ce cas, le champ
    :attr:`~scrabble.moteur.ia.ProfilPersonnage.part_vocabulaire_long` et/ou
    :attr:`~scrabble.moteur.ia.ProfilPersonnage.part_vocabulaire_court`
    correspondant est remplacé par cette valeur, tous les autres champs du
    profil restant inchangés — les deux surcharges sont indépendantes,
    chacune ne s'applique que si SA table contient une entrée pour
    ``niveau``. ``niveau=None`` (joueur humain, ou appelant qui ne connaît
    encore aucun niveau) ne trouve jamais d'entrée et renvoie donc
    ``profil`` sans modification — même résultat que :attr:`Personnage.profil`
    lu directement, ce qui garde ce dernier valide pour tout appelant qui ne
    se préoccupe pas de la résolution par niveau (cas de tous les
    personnages déclarés avant ce lot).

    :raises KeyError: si ``cle`` ne correspond à aucune entrée de
        :data:`PERSONNAGES` (même condition que :func:`obtenir_personnage`).
    """
    personnage = PERSONNAGES[cle]
    profil = personnage.profil
    table_long = personnage.part_vocabulaire_long_par_niveau
    if table_long is not None and niveau is not None and niveau in table_long:
        profil = replace(profil, part_vocabulaire_long=table_long[niveau])
    table_court = personnage.part_vocabulaire_court_par_niveau
    if table_court is not None and niveau is not None and niveau in table_court:
        profil = replace(profil, part_vocabulaire_court=table_court[niveau])
    return profil


#: Registre unique des personnages (issue #439, lot B). Ajouter un
#: personnage = ajouter une entrée ici.
PERSONNAGES: dict[str, Personnage] = {
    "classique": Personnage(
        cle="classique",
        prenom="Classique",
        description="Joue normalement selon son niveau.",
        profil=ProfilPersonnage(),
    ),
    "opportuniste": Personnage(
        cle="opportuniste",
        prenom="Opportuniste",
        description=(
            "Se précipite sur les cases bonus dès qu'elles sont à "
            "sa portée, quitte à négliger la qualité des lettres qu'il garde "
            "sur son chevalet."
        ),
        profil=ProfilPersonnage(
            bonus_premium=BONUS_PREMIUM_OPPORTUNISTE,
            poids_leave=0.0,
        ),
        niveaux_disponibles=NIVEAUX_OPPORTUNISTE,
        nb_joueurs_disponibles=NB_JOUEURS_OPPORTUNISTE,
    ),
    "chasseur_de_scrabbles": Personnage(
        cle="chasseur_de_scrabbles",
        prenom="Chasseur de scrabbles",
        description=(
            "Guette les occasions de poser ses 7 lettres d'un coup et garde "
            "ses meilleures lettres en réserve pour y arriver."
        ),
        profil=ProfilPersonnage(
            bonus_scrabble=BONUS_SEPT_LETTRES_CHASSEUR,
            poids_leave=POIDS_LEAVE_CHASSEUR_SCRABBLES,
            vocabulaire_long=True,
            poids_tirage_scrabble=POIDS_TIRAGE_SCRABBLE_CHASSEUR,
        ),
        niveaux_disponibles=NIVEAUX_CHASSEUR_SCRABBLES,
        nb_joueurs_disponibles=NB_JOUEURS_CHASSEUR_SCRABBLES,
        part_vocabulaire_long_par_niveau=PART_VOCABULAIRE_LONG_CHASSEUR,
        part_vocabulaire_court_par_niveau=PART_VOCABULAIRE_COURT_CHASSEUR,
        # Désactivé (issue #459) : effet trop discret pour être remarqué en
        # jeu (~0,45 scrabble/partie à Avancé, ~0,2 à Intermédiaire, mesures
        # du 12 octobre 2026). Code et réglages conservés tels quels pour une
        # réactivation éventuelle — repasser à True suffit.
        actif=False,
    ),
    "titeuf": Personnage(
        cle="titeuf",
        prenom=PRENOM_TITEUF,
        description=(
            "Devant sa mamy, il ne trouve jamais que des mots de cour de "
            "récré — un peu de pipi, beaucoup de caca — même quand ça ne "
            "rapporte presque rien."
        ),
        profil=ProfilPersonnage(
            mots_favoris=MOTS_FAVORIS_TITEUF,
            poids_tirage_favori=POIDS_TIRAGE_FAVORI_TITEUF,
        ),
        niveaux_disponibles=NIVEAUX_TITEUF,
        nb_joueurs_disponibles=NB_JOUEURS_TITEUF,
    ),
    "lettre": Personnage(
        cle="lettre",
        prenom=PRENOM_LETTRE,
        description=(
            "Connaît des mots que presque personne n'utilise et les place "
            "avec une fierté non dissimulée, même quand un mot plus simple "
            "aurait rapporté autant."
        ),
        profil=ProfilPersonnage(
            mots_favoris=MOTS_FAVORIS_LETTRE,
            bonus_favori=BONUS_FAVORI_LETTRE,
        ),
        niveaux_disponibles=NIVEAUX_LETTRE,
        nb_joueurs_disponibles=NB_JOUEURS_LETTRE,
        # Désactivé (issue #459) : effet trop discret pour être remarqué en
        # jeu (~deux mots de sa liste par partie, mesures du 12 octobre
        # 2026). Code et réglages conservés tels quels pour une réactivation
        # éventuelle — repasser à True suffit.
        actif=False,
    ),
}


def obtenir_personnage(cle: str) -> Personnage:
    """Renvoie le personnage enregistré sous ``cle``.

    Fonctionne à l'identique pour un personnage inactif (issue #459, voir
    :attr:`Personnage.actif`) : seules les fonctions qui PROPOSENT un
    personnage au joueur ou au tirage ``aleatoire`` l'excluent, jamais
    l'accès direct par clé — une partie sauvegardée qui le mentionne
    continue de se résoudre normalement.

    :raises KeyError: si ``cle`` ne correspond à aucune entrée de
        :data:`PERSONNAGES`.
    """
    return PERSONNAGES[cle]


def personnage_actif(personnage_cle: str) -> bool:
    """Vrai si ``personnage_cle`` (réel, ou :data:`CLE_ALEATOIRE`) désigne un
    personnage proposable (issue #459).

    « Aléatoire » est toujours actif lui-même : il ne tire de toute façon
    jamais qu'un personnage réel actif (voir :func:`tirer_personnage`). Une
    clé inconnue du registre (et différente de :data:`CLE_ALEATOIRE`) renvoie
    ``False``, comme les autres fonctions de disponibilité de ce module.
    """
    if personnage_cle == CLE_ALEATOIRE:
        return True
    personnage = PERSONNAGES.get(personnage_cle)
    return personnage is not None and personnage.actif


def tirer_personnage(
    generateur: random.Random | None = None,
    niveau: Niveau | None = None,
    nb_joueurs: int | None = None,
) -> Personnage:
    """Tire un personnage parmi ceux du registre disponibles à ``niveau`` et
    ``nb_joueurs``.

    Classique compris (issue #440, lot D, point 3) : le tirage « Aléatoire »
    ne favorise ni n'exclut le personnage neutre. ``generateur`` est
    injectable pour un tirage déterministe en test ; à défaut, utilise le
    module :mod:`random` global (``random.choice`` s'appelle de la même façon
    sur le module que sur une instance de :class:`random.Random`).

    ``niveau`` (issue #447, lot G) restreint le tirage aux personnages
    disponibles à ce niveau (:func:`personnages_disponibles_a_niveau`) — à
    appeler uniquement là où :func:`aleatoire_disponible_a_niveau` est vrai
    (au moins deux personnages y figurent), ce que le contrôle côté serveur
    garantit déjà avant tout tirage.

    ``nb_joueurs`` (issue #449, lot I) restreint pareillement le tirage aux
    personnages disponibles à cette taille de table
    (:func:`personnages_disponibles_a_nb_joueurs`). Les deux restrictions se
    combinent (ET logique) quand elles sont fournies ensemble — c'est
    ``creer_partie`` qui les transmet toutes les deux pour une IA donnée.

    ``None`` (défaut pour chacun des deux) conserve l'ancien comportement :
    tirage sur tout le registre, sans la restriction correspondante — utilisé
    par les appelants qui ne connaissent pas encore de niveau ou de taille de
    table particuliers.

    Un personnage inactif (:attr:`Personnage.actif` à ``False`` — Chasseur de
    scrabbles et Lettré depuis l'issue #459) n'est jamais tiré, quels que
    soient ``niveau`` et ``nb_joueurs`` — y compris les deux ``None``.
    """
    rng = generateur if generateur is not None else random
    reserve = [p for p in PERSONNAGES.values() if p.actif]
    if niveau is not None:
        reserve = [p for p in reserve if niveau in p.niveaux_disponibles]
    if nb_joueurs is not None:
        reserve = [p for p in reserve if nb_joueurs in p.nb_joueurs_disponibles]
    return rng.choice(reserve)


def personnages_disponibles_a_niveau(niveau: Niveau) -> list[Personnage]:
    """Personnages réels du registre disponibles à ``niveau`` (issue #447, lot G).

    Dans l'ordre d'insertion de :data:`PERSONNAGES` (Classique en tête).
    N'inclut jamais l'entrée pseudo-personnage « Aléatoire » : voir
    :func:`aleatoire_disponible_a_niveau` pour sa propre règle de
    disponibilité, déduite de celle-ci. N'inclut jamais non plus un
    personnage inactif (:attr:`Personnage.actif` à ``False``, issue #459).
    """
    return [
        p
        for p in PERSONNAGES.values()
        if p.actif and niveau in p.niveaux_disponibles
    ]


def aleatoire_disponible_a_niveau(niveau: Niveau) -> bool:
    """Vrai si « Aléatoire » a un sens à ``niveau`` (issue #447, lot G).

    Règle déduite automatiquement des déclarations des personnages réels,
    sans qu'Aléatoire ait lui-même à déclarer quoi que ce soit : il lui faut
    au moins **deux** personnages disponibles à ce niveau (hors lui-même),
    tirer au hasard parmi un seul personnage n'ayant aucun sens. Un futur
    personnage ajouté au registre et compatible avec un niveau aujourd'hui à
    un seul personnage disponible rend donc Aléatoire à nouveau disponible à
    ce niveau, sans aucune autre modification.
    """
    return len(personnages_disponibles_a_niveau(niveau)) >= 2


def personnage_disponible_a_niveau(personnage_cle: str, niveau: Niveau) -> bool:
    """Vrai si ``personnage_cle`` (réel, ou :data:`CLE_ALEATOIRE`) peut être
    choisi à ``niveau`` (issue #447, lot G).

    Une clé inconnue du registre (et différente de :data:`CLE_ALEATOIRE`)
    renvoie ``False`` plutôt que de lever : à l'appelant (contrôle côté
    serveur) de distinguer « personnage inconnu » de « indisponible à ce
    niveau » s'il le souhaite.
    """
    if personnage_cle == CLE_ALEATOIRE:
        return aleatoire_disponible_a_niveau(niveau)
    personnage = PERSONNAGES.get(personnage_cle)
    return personnage is not None and niveau in personnage.niveaux_disponibles


def personnages_disponibles_a_nb_joueurs(nb_joueurs: int) -> list[Personnage]:
    """Personnages réels du registre disponibles à ``nb_joueurs`` (issue #449, lot I).

    Dans l'ordre d'insertion de :data:`PERSONNAGES` (Classique en tête).
    N'inclut jamais l'entrée pseudo-personnage « Aléatoire » : voir
    :func:`aleatoire_disponible_a_nb_joueurs` pour sa propre règle de
    disponibilité, déduite de celle-ci. Indépendant de
    :func:`personnages_disponibles_a_niveau` (deux dimensions distinctes qui
    se combinent chez l'appelant). N'inclut jamais non plus un personnage
    inactif (:attr:`Personnage.actif` à ``False``, issue #459).
    """
    return [
        p
        for p in PERSONNAGES.values()
        if p.actif and nb_joueurs in p.nb_joueurs_disponibles
    ]


def aleatoire_disponible_a_nb_joueurs(nb_joueurs: int) -> bool:
    """Vrai si « Aléatoire » a un sens à ``nb_joueurs`` (issue #449, lot I).

    Règle déduite automatiquement des déclarations des personnages réels,
    sans qu'Aléatoire ait lui-même à déclarer quoi que ce soit : il lui faut
    au moins **deux** personnages disponibles à cette taille de table (hors
    lui-même), tirer au hasard parmi un seul personnage n'ayant aucun sens.
    Un futur personnage ajouté au registre et compatible avec une taille
    aujourd'hui à un seul personnage disponible rend donc Aléatoire à nouveau
    disponible à cette taille, sans aucune autre modification. Seuls les
    personnages actifs comptent (issue #459 — Chasseur de scrabbles et
    Lettré, inactifs, n'y sont plus comptés bien que tous deux réservés à
    deux joueurs). Aujourd'hui : disponible à deux joueurs (Classique +
    Opportuniste + Titeuf), indisponible à trois ou quatre (seul Classique y
    figure).
    """
    return len(personnages_disponibles_a_nb_joueurs(nb_joueurs)) >= 2


def personnage_disponible_a_nb_joueurs(personnage_cle: str, nb_joueurs: int) -> bool:
    """Vrai si ``personnage_cle`` (réel, ou :data:`CLE_ALEATOIRE`) peut être
    choisi pour une table de ``nb_joueurs`` (issue #449, lot I).

    Une clé inconnue du registre (et différente de :data:`CLE_ALEATOIRE`)
    renvoie ``False`` plutôt que de lever : à l'appelant (contrôle côté
    serveur) de distinguer « personnage inconnu » de « indisponible à cette
    taille de table » s'il le souhaite.
    """
    if personnage_cle == CLE_ALEATOIRE:
        return aleatoire_disponible_a_nb_joueurs(nb_joueurs)
    personnage = PERSONNAGES.get(personnage_cle)
    return personnage is not None and nb_joueurs in personnage.nb_joueurs_disponibles


#: Message affiché quand les personnages sont réservés aux parties à deux
#: joueurs (issue #449, lot I, points 2, 3 et 4) : explication du sélecteur
#: désactivé à l'accueil (point 2), remise à Classique d'un adversaire déjà
#: configuré (point 3) et refus côté serveur (point 4) partagent le même
#: texte.
MESSAGE_PERSONNAGES_RESERVES_DEUX_JOUEURS = (
    "Les personnages sont réservés aux parties à deux joueurs."
)

#: Libellés français des nombres de joueurs (issue #449, lot I), réservés à
#: l'affichage des tailles de table de disponibilité d'un personnage
#: (:func:`libelle_tailles`, :func:`libelle_tailles_aleatoire`).
_MOTS_NB_JOUEURS: dict[int, str] = {2: "deux", 3: "trois", 4: "quatre"}

#: Message affiché pour une taille de table où « Aléatoire » est
#: indisponible (issue #449, lot I) — le même quelle que soit la taille
#: concernée, puisque la raison ne dépend jamais de la taille elle-même,
#: seulement du nombre de personnages réels qui y sont disponibles.
MESSAGE_ALEATOIRE_NB_JOUEURS_INSUFFISANT = (
    "Aléatoire demande au moins deux personnages disponibles à cette taille "
    "de table."
)


def _libelle_tailles(tailles: frozenset[int]) -> str:
    """Texte des tailles de table d'un ensemble, pour affichage (issue #449, lot I).

    « Toutes les parties » si ``tailles`` couvre :data:`TOUTES_TAILLES` ;
    « Parties à <nombre> joueurs » pour une taille unique ; « Parties de
    <premier> à <dernier> joueurs » pour un intervalle contigu de plusieurs
    tailles ; sinon (motif non contigu, hypothétique) « Parties à <nombre> ou
    <nombre> joueurs ».
    """
    if tailles == TOUTES_TAILLES:
        return "Toutes les parties"
    ordre = sorted(TOUTES_TAILLES)
    presentes = [n for n in ordre if n in tailles]
    mots = [_MOTS_NB_JOUEURS[n] for n in presentes]
    if len(mots) == 1:
        return f"Parties à {mots[0]} joueurs"
    if presentes == list(range(presentes[0], presentes[-1] + 1)):
        return f"Parties de {mots[0]} à {mots[-1]} joueurs"
    return "Parties à " + " ou ".join(mots) + " joueurs"


def libelle_tailles(personnage: Personnage) -> str:
    """Texte des tailles de table où ``personnage`` est disponible (issue
    #449, lot I, point 5) : « Toutes les parties » ou « Parties à deux
    joueurs »."""
    return _libelle_tailles(personnage.nb_joueurs_disponibles)


def tailles_disponibles_aleatoire() -> frozenset[int]:
    """Tailles de table où « Aléatoire » est disponible (issue #449, lot I, point 5)."""
    return frozenset(n for n in TOUTES_TAILLES if aleatoire_disponible_a_nb_joueurs(n))


def libelle_tailles_aleatoire() -> str:
    """Texte des tailles de table où « Aléatoire » est disponible, même
    présentation que :func:`libelle_tailles` (issue #449, lot I, point 5)."""
    return _libelle_tailles(tailles_disponibles_aleatoire())


def explication_disponibilite_tailles(personnage_cle: str) -> str:
    """Courte explication de la restriction de tailles de table de
    ``personnage_cle`` (issue #449, lot I), à afficher au même titre que
    :func:`explication_disponibilite_niveaux`.

    Chaîne vide quand le personnage est disponible à toutes les tailles (cas
    de Classique, et de tout personnage sans déclaration) : rien à expliquer.
    Pour Aléatoire, :data:`MESSAGE_ALEATOIRE_NB_JOUEURS_INSUFFISANT` dès
    qu'au moins une taille lui est fermée. Pour un personnage réel restreint
    à deux joueurs (motif observé à ce jour, Opportuniste, Chasseur de
    scrabbles et Titeuf compris) : :data:`MESSAGE_PERSONNAGES_RESERVES_DEUX_JOUEURS`.
    Motif différent (hypothétique) : repli sur :func:`libelle_tailles`.
    """
    if personnage_cle == CLE_ALEATOIRE:
        if tailles_disponibles_aleatoire() == TOUTES_TAILLES:
            return ""
        return MESSAGE_ALEATOIRE_NB_JOUEURS_INSUFFISANT
    personnage = PERSONNAGES.get(personnage_cle)
    if personnage is None:
        return ""
    tailles = personnage.nb_joueurs_disponibles
    if tailles == TOUTES_TAILLES:
        return ""
    if tailles == frozenset({2}):
        return MESSAGE_PERSONNAGES_RESERVES_DEUX_JOUEURS
    return f"Disponible : {_libelle_tailles(tailles)}"


#: Libellés français des niveaux (issue #447, lot G), dans l'ordre de
#: :class:`~scrabble.moteur.ia.Niveau` — réservés à l'affichage des niveaux de
#: disponibilité d'un personnage (:func:`libelle_niveaux`,
#: :func:`explication_disponibilite_niveaux`). Dupliqués à dessein de
#: ``scrabble.ui.accueil._LIBELLES_NIVEAUX`` plutôt que partagés : ce module
#: (``moteur``) ne doit pas dépendre de ``ui``, et l'inverse est déjà le cas.
_LIBELLES_NIVEAU: dict[Niveau, str] = {
    Niveau.DEBUTANT: "Débutant",
    Niveau.FACILE: "Facile",
    Niveau.INTERMEDIAIRE: "Intermédiaire",
    Niveau.AVANCE: "Avancé",
    Niveau.EXPERT: "Expert",
    Niveau.CHAMPION_DU_MONDE: "Champion du monde",
}

#: Message affiché pour un niveau où « Aléatoire » est indisponible (issue
#: #447, lot G, point 2) — le même quel que soit le niveau concerné, puisque
#: la raison ne dépend jamais du niveau lui-même, seulement du nombre de
#: personnages réels qui y sont disponibles.
MESSAGE_ALEATOIRE_NIVEAU_INSUFFISANT = (
    "Aléatoire demande au moins deux personnages disponibles à ce niveau."
)


def _libelle_niveaux(niveaux: frozenset[Niveau]) -> str:
    """Texte des niveaux d'un ensemble, pour affichage (issue #447, lot G).

    « Tous les niveaux » si ``niveaux`` couvre :data:`TOUS_NIVEAUX` ; sinon
    « <premier> à <dernier> » (ou le niveau seul s'il n'y en a qu'un), dans
    l'ordre de :class:`~scrabble.moteur.ia.Niveau` — suffisant pour les motifs
    observés à ce jour (un intervalle contigu de niveaux).
    """
    if niveaux == TOUS_NIVEAUX:
        return "Tous les niveaux"
    ordonnes = [n for n in Niveau if n in niveaux]
    labels = [_LIBELLES_NIVEAU[n] for n in ordonnes]
    if len(labels) == 1:
        return labels[0]
    return f"{labels[0]} à {labels[-1]}"


def libelle_niveaux(personnage: Personnage) -> str:
    """Texte des niveaux où ``personnage`` est disponible (issue #447, lot G,
    point 5) : « Tous les niveaux » ou « <premier> à <dernier> »."""
    return _libelle_niveaux(personnage.niveaux_disponibles)


def niveaux_disponibles_aleatoire() -> frozenset[Niveau]:
    """Niveaux où « Aléatoire » est disponible (issue #447, lot G, point 5)."""
    return frozenset(n for n in Niveau if aleatoire_disponible_a_niveau(n))


def libelle_niveaux_aleatoire() -> str:
    """Texte des niveaux où « Aléatoire » est disponible, même présentation
    que :func:`libelle_niveaux` (issue #447, lot G, point 5)."""
    return _libelle_niveaux(niveaux_disponibles_aleatoire())


def explication_disponibilite_niveaux(personnage_cle: str) -> str:
    """Courte explication de la restriction de niveaux de ``personnage_cle``
    (issue #447, lot G, point 2), à afficher sous le sélecteur de personnage.

    Chaîne vide quand le personnage est disponible à tous les niveaux (cas de
    Classique, et de tout personnage sans déclaration) : rien à expliquer.
    Pour Aléatoire, :data:`MESSAGE_ALEATOIRE_NIVEAU_INSUFFISANT` dès qu'au
    moins un niveau lui est fermé. Pour un personnage réel indisponible sur un
    préfixe de niveaux les plus faibles (motif observé à ce jour, Opportuniste
    compris) : « Disponible à partir de <premier niveau disponible> ». Motif
    différent (hypothétique) : repli sur :func:`libelle_niveaux`.
    """
    if personnage_cle == CLE_ALEATOIRE:
        if niveaux_disponibles_aleatoire() == TOUS_NIVEAUX:
            return ""
        return MESSAGE_ALEATOIRE_NIVEAU_INSUFFISANT
    personnage = PERSONNAGES.get(personnage_cle)
    if personnage is None:
        return ""
    niveaux = personnage.niveaux_disponibles
    if niveaux == TOUS_NIVEAUX:
        return ""
    ordre = list(Niveau)
    manquants = [n for n in ordre if n not in niveaux]
    presents = [n for n in ordre if n in niveaux]
    if presents and ordre.index(presents[0]) == len(manquants):
        return f"Disponible à partir de {_LIBELLES_NIVEAU[presents[0]]}"
    return f"Disponible : {_libelle_niveaux(niveaux)}"


def _prenom_affichable(cle: str) -> str:
    """Prénom affichable d'un personnage réel du registre, Classique compris.

    Défense en profondeur : une clé devenue inconnue (le registre n'est
    jamais réduit en pratique) retombe sur la clé elle-même plutôt que de
    faire planter l'affichage.
    """
    personnage = PERSONNAGES.get(cle)
    return personnage.prenom if personnage is not None else cle


def libelle_choix_accueil(personnage_cle: str) -> str:
    """Texte à afficher entre parenthèses pour un choix fait à l'accueil (issue #441).

    ``personnage_cle`` est ici la clé **encore non résolue** mémorisée par
    :class:`~scrabble.ui.accueil.JoueurConfig` : soit une clé de
    :data:`PERSONNAGES`, soit :data:`CLE_ALEATOIRE` (le tirage réel n'a lieu
    qu'au lancement de la partie, voir
    :func:`~scrabble.moteur.partie.creer_partie`). Chaîne vide pour Classique
    (ou l'absence de personnage) : l'accueil affiche alors le prénom seul,
    comme avant l'introduction du sélecteur.
    """
    if personnage_cle == CLE_ALEATOIRE:
        return "Aléatoire"
    if not personnage_cle or personnage_cle == "classique":
        return ""
    return _prenom_affichable(personnage_cle)


def libelle_personnage_partie(
    personnage_cle: str, personnage_aleatoire: bool, reveler: bool = False
) -> str:
    """Texte à afficher entre parenthèses pour un ``Joueur`` en partie (issue #441).

    ``personnage_cle``/``personnage_aleatoire`` reprennent les champs de
    :class:`~scrabble.moteur.partie.Joueur` — ``personnage_cle`` porte ici
    toujours l'identité **réelle** (jamais le libellé « Aléatoire »).

    Pour un personnage tiré au hasard (``personnage_aleatoire`` vrai), le
    libellé reste « Aléatoire » tant que ``reveler`` est faux (pendant toute
    la partie — l'identité ne doit pas fuiter), puis devient « Aléatoire :
    <Personnage> » une fois révélé, Classique compris : jamais le prénom seul,
    pour que le joueur ne croie pas à un défaut d'affichage.

    Pour un personnage choisi explicitement, chaîne vide pour Classique (ou
    l'absence de personnage, sauvegarde antérieure à l'issue #438) : seul un
    personnage tiré au hasard doit être annoncé pour Classique.
    """
    if personnage_aleatoire:
        if reveler:
            return f"Aléatoire : {_prenom_affichable(personnage_cle)}"
        return "Aléatoire"
    if not personnage_cle or personnage_cle == "classique":
        return ""
    return _prenom_affichable(personnage_cle)


def lister_personnages(
    cles_dans_partie: frozenset[str] = frozenset(),
    aleatoire_dans_partie: bool = False,
) -> list[dict[str, Any]]:
    """Liste présentable pour la fenêtre « Les personnages » (issue #442, lot F).

    Une entrée par personnage ACTIF de :data:`PERSONNAGES` (dans l'ordre
    d'insertion, donc Classique en tête — un personnage inactif,
    :attr:`Personnage.actif` à ``False``, en est exclu, issue #459), puis
    « Aléatoire » toujours en dernier — construite dynamiquement depuis le
    registre comme :func:`~scrabble.ui.accueil.ApiAccueil.obtenir_personnages`,
    pour qu'un personnage ajouté plus tard au registre y apparaisse sans
    autre modification. Chaque entrée est ``{"cle", "prenom", "description",
    "dans_la_partie", "niveaux_label", "tailles_label"}`` — ``niveaux_label``
    (issue #447, lot G, point 5) est le texte des niveaux où le personnage
    est disponible (:func:`libelle_niveaux`/:func:`libelle_niveaux_aleatoire`)
    et ``tailles_label`` (issue #449, lot I, point 5) le texte des tailles de
    table où il est disponible (:func:`libelle_tailles`/
    :func:`libelle_tailles_aleatoire`), même présentation à l'accueil et en
    jeu puisque les deux fenêtres consomment cette même fonction (directement
    ici, ou via :meth:`~scrabble.ui.accueil.ApiAccueil.obtenir_personnages`
    qui reprend la même logique).

    ``cles_dans_partie`` (vide par défaut — cas de l'accueil, où il n'y a pas
    encore de partie) marque les personnages choisis À L'AVANCE par un
    adversaire de la partie en cours (``dans_la_partie``). Ne jamais y
    inclure la clé d'un personnage tiré au hasard : ce paramètre ne pilote
    donc jamais le marquage de l'entrée « Aléatoire » elle-même (voir
    ``aleatoire_dans_partie`` ci-dessous), afin que la fenêtre ne laisse
    jamais deviner le résultat d'un tirage avant la révélation finale.

    ``aleatoire_dans_partie`` (issue #443, lot F bis) marque l'entrée
    « Aléatoire » dès qu'au moins un adversaire a été RÉGLÉ sur Aléatoire
    (:attr:`~scrabble.moteur.partie.Joueur.personnage_aleatoire`), quel que
    soit le personnage réellement tiré. Cela ne révèle rien : le libellé
    « (Aléatoire) » est déjà affiché à côté du prénom de cet adversaire
    pendant toute la partie (voir
    :func:`libelle_personnage_partie`) — seule l'identité tirée reste
    secrète, jamais le fait d'avoir réglé un adversaire sur Aléatoire.
    """
    resultat = [
        {
            "cle": personnage.cle,
            "prenom": personnage.prenom,
            "description": personnage.description,
            "dans_la_partie": personnage.cle in cles_dans_partie,
            "niveaux_label": libelle_niveaux(personnage),
            "tailles_label": libelle_tailles(personnage),
        }
        for personnage in PERSONNAGES.values()
        if personnage.actif
    ]
    resultat.append(
        {
            "cle": CLE_ALEATOIRE,
            "prenom": "Aléatoire",
            "description": DESCRIPTION_ALEATOIRE,
            "dans_la_partie": aleatoire_dans_partie,
            "niveaux_label": libelle_niveaux_aleatoire(),
            "tailles_label": libelle_tailles_aleatoire(),
        }
    )
    return resultat
