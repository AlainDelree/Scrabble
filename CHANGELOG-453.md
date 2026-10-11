# Changelog — Issue #453

## Ajouté

- **Part réglable des mots courts connus du Chasseur de scrabbles, par
  niveau (lot H quater).** Les mesures du lot H ter (#451, vocabulaire long
  et tirage pondéré) montraient un style enfin visible (0,14 scrabble par
  partie à Intermédiaire contre 0,01 pour Classique, 0,4 contre 0,11 à
  Avancé) mais trop fort : environ +12 points par partie à Intermédiaire,
  +20 à Avancé contre Classique au même niveau — la règle « un personnage ne
  change pas la force du niveau » n'était plus respectée. Un scrabble
  rapportant beaucoup de points (de l'ordre de 80 en moyenne), ce surplus de
  scrabbles explique une large part du surplus de force ; les mesures du
  curseur `part_vocabulaire_long` à des valeurs intermédiaires (30 à 70 % à
  Intermédiaire, 20 à 50 % à Avancé) montrent qu'aux parts basses, le
  surplus de scrabbles devient à peine visible alors qu'un excédent de force
  de 6 à 9 points subsiste : réduire seulement le vocabulaire long dilue le
  style sans forcément retrouver la neutralité de force. Ce lot prend le
  problème à l'envers, sur proposition d'Alain : garder la connaissance des
  longs mots intacte (100 % aux deux niveaux, remis depuis 50 % à Avancé) et
  faire payer la force du personnage par une MOINS BONNE connaissance des
  mots COURTS — pour qu'il devienne un spécialiste des scrabbles qui joue
  moins bien le reste, un personnage plus marqué et plus cohérent.

  - **`scrabble.moteur.ia`** :
    - Nouveau champ facultatif de `ProfilPersonnage` :
      `part_vocabulaire_court: float | None`, neutre par défaut (`None`,
      traité comme `1.0`). Va dans le sens inverse de
      `part_vocabulaire_long` : au lieu d'ÉLARGIR les coups candidats, il
      RESTREINT l'ensemble déjà constitué (vocabulaire du niveau, plus
      l'éventuel élargissement `vocabulaire_long`/`mots_favoris`) aux coups
      dont le mot principal compte MOINS de 7 lettres
      (`_SEUIL_VOCABULAIRE_LONG`) — ceux-là ne restent candidats que si ce
      mot est « connu » selon la nouvelle fonction privée
      `_mot_connu_vocabulaire_court(mot, part_vocabulaire_court)`. Les mots
      de 7 lettres et plus — du vocabulaire du niveau ou ajoutés par
      `vocabulaire_long` — ne sont JAMAIS filtrés par ce champ.
    - `_mot_connu_vocabulaire_court` reprend EXACTEMENT le procédé de
      `_mot_connu_vocabulaire_long` (hachage SHA-256 stable du texte du mot,
      pas le `hash()` intégré de Python, randomisé d'un processus à l'autre)
      avec un **décalage de hachage distinct** : préfixe `b"court:"` ajouté
      avant hachage. Pour un même mot, le résultat de cette fonction et
      celui de `_mot_connu_vocabulaire_long` sont donc statistiquement
      indépendants — exigence explicite de l'issue, vérifiée par mesure du
      taux d'accord entre les deux sur un grand échantillon de mots
      fabriqués (proche de 50 % à `part = 0.5`, pas de 100 %).
    - `_generer_coups_candidats` applique ce filtre en DERNIER, après les
      deux élargissements `vocabulaire_long`/`mots_favoris` (eux-mêmes
      inchangés) : contrairement à ces deux champs, `part_vocabulaire_court`
      n'a besoin ni de `dictionnaire_complet` ni de `vocabulaire_long`/
      `mots_favoris` actifs pour s'appliquer — un profil qui ne renseigne
      QUE ce champ filtre déjà l'ensemble issu du seul vocabulaire du
      niveau. La fonction a été restructurée pour que ce filtre s'applique
      indépendamment du bloc d'élargissement (lequel reste conditionné à
      `dictionnaire_complet is not None and (vocabulaire_long or
      mots_favoris)`, comportement inchangé).
    - **Garde-fou** (point 2 de l'issue) : si le filtre ne laisse plus aucun
      coup candidat (début de partie, chevalet difficile), il est ignoré
      pour CE TOUR — la liste non filtrée est utilisée à la place plutôt que
      de forcer une passe, qui fausserait la mesure de force du personnage
      (un passage forcé coûte des points et change radicalement la
      dynamique de la partie, sans rapport avec le style réel du
      personnage). Implémenté simplement : la liste filtrée ne remplace la
      liste d'origine que si elle est non vide.
    - Journal de décision et évaluation (point 5) : `evaluer_coups` n'a reçu
      aucune modification — comme pour `part_vocabulaire_long`, le filtre
      est une fonction pure du texte du mot (pas de l'aléa de la partie) et
      vit entièrement dans `_generer_coups_candidats`, appelée par
      `choisir_coup` ET `evaluer_coups` : les deux restent automatiquement
      en phase sur le MÊME ensemble de coups candidats filtré, sans logique
      de cohérence supplémentaire à écrire.
  - **`scrabble.moteur.personnages`** :
    - `PART_VOCABULAIRE_COURT_CHASSEUR = {INTERMEDIAIRE: 0.7, AVANCE: 0.7}` :
      nouvelle constante en tête de module, table niveau → part (comme
      `PART_VOCABULAIRE_LONG_CHASSEUR`) — voir le calcul plus bas.
    - `PART_VOCABULAIRE_LONG_CHASSEUR` remis à `{INTERMEDIAIRE: 1.0, AVANCE:
      1.0}` (AVANCE valait 0.5 depuis le lot H ter) : le style du
      personnage reste donc entier sur le vocabulaire long, c'est le
      nouveau levier ci-dessus qui ajuste la force.
    - Nouveau champ optionnel `Personnage.part_vocabulaire_court_par_niveau`
      (`dict[Niveau, float] | None`, défaut `None`), résolu par
      `profil_pour_niveau` exactement comme `part_vocabulaire_long_par_niveau`
      — les deux tables sont indépendantes et se combinent sans conflit
      (chacune ne touche que le champ de `profil` qui lui correspond),
      c'est le cas du Chasseur de scrabbles qui renseigne les deux
      désormais. `.profil` (accès direct) reste la valeur PLATE, sans
      résolution de niveau, comme pour `part_vocabulaire_long`.
    - `PERSONNAGES["chasseur_de_scrabbles"]` renseigne la nouvelle table
      `part_vocabulaire_court_par_niveau=PART_VOCABULAIRE_COURT_CHASSEUR`.
      `poids_tirage_scrabble` et `poids_leave` du personnage restent
      inchangés (point 3 de l'issue).
  - Aucune modification de `scrabble.ui.jeu` ni de
    `scripts/mesurer_force_niveaux.py` : les deux résolvent déjà le profil
    via `profil_pour_niveau` (lot H ter) — le nouveau champ s'applique donc
    automatiquement, en jeu réel comme en mesure, sans aucun code
    supplémentaire à écrire (point 6 de l'issue : « le script de mesure
    doit suivre le même chemin que le jeu » — déjà vrai par construction).

### Calcul justifiant `PART_VOCABULAIRE_COURT_CHASSEUR = 0.7` (70 %, aux deux niveaux)

Point médian raisonné entre « tout » (comportement actuel du personnage,
trop fort d'après les mesures du lot H ter) et une restriction sévère qui
risquerait de ne plus trouver assez de coups courts pour varier le jeu —
même logique que le point médian 50 % choisi au lot H ter pour
`part_vocabulaire_long` à Avancé. Le dictionnaire réel n'étant pas
disponible dans ce worktree isolé, cette valeur n'a pas pu être mesurée par
parties jouées : point de départ explicitement provisoire, à ajuster par
Alain après mesure réelle (voir les commandes ci-dessous) — objectif de
l'issue : écart de points proche de zéro contre Classique au même niveau,
avec un surplus de scrabbles qui reste visible.

### Neutralité stricte

- Un profil sans `part_vocabulaire_court` (absent, ou `ProfilPersonnage()`
  vide), ou avec `part_vocabulaire_court=1.0`, reproduit bit à bit
  l'ensemble de coups candidats d'avant l'introduction du champ —
  `TestPartVocabulaireCourt.test_part_1_identique_au_comportement_actuel`.
  Le calcul du filtre étant purement déterministe (aucun aléa), la
  consommation du générateur aléatoire de `choisir_coup` est elle aussi
  identique, pour les six niveaux —
  `TestPartVocabulaireCourt.test_neutre_rng_choisir_coup`.
- `part_vocabulaire_court` reste `None` pour Classique, Opportuniste et
  Titeuf — strictement additif, aucun effet de bord
  (`TestPartVocabulaireCourtChasseur.test_profil_pour_niveau_personnage_sans_table_inchange`).
- `profil_pour_niveau` pour un personnage sans table de surcharge, ou pour
  un niveau absent de la table, renvoie exactement `.profil` — aucune
  mutation du profil de base du registre.
- Les réglages par niveau (`_MALUS_LONGUEUR`, `_BONUS_PREMIUM`,
  `_POIDS_LEAVE`), les autres personnages et le tirage Aléatoire ne sont pas
  touchés.

### Comportement du garde-fou (point 2 de l'issue, demandé dans le rapport)

Si, après filtrage, aucun coup candidat ne reste (chevalet qui ne permet
plus aucun mot court connu, et aucun mot long disponible pour compenser), la
liste FILTRÉE est simplement abandonnée et la liste D'ORIGINE (non filtrée)
est utilisée pour ce tour — comportement identique à l'absence du champ pour
ce seul tour, puis le filtre redevient actif au tour suivant si de nouveaux
coups candidats apparaissent. Choix simple délibéré, sans action corrective
plus élaborée (par exemple retenter avec une part relâchée) : l'objectif du
garde-fou est seulement d'éviter une passe forcée qui fausserait la mesure
de force, pas de maximiser le respect du style dans ce cas limite, rare par
construction (une part de 70 % laisse en moyenne 70 % des mots courts
accessibles). Testé explicitement avec un scénario à un seul coup court
candidat et `part_vocabulaire_court=0.0` —
`TestPartVocabulaireCourt.test_garde_fou_si_aucun_coup_candidat_apres_filtre`.

### Tests ajoutés

- `tests/test_moteur_ia.py` :
  - `TestMotConnuVocabulaireCourt` : déterminisme et indépendance de
    l'ordre, bornes à 0,0/1,0, proportion proche de la part sur une liste de
    mots fabriquée (5 valeurs), et indépendance statistique avec
    `_mot_connu_vocabulaire_long` (taux d'accord proche de 50 % à `part =
    0.5` sur 2000 mots, pas de 100 %).
  - `TestPartVocabulaireCourt` : part à 100 % identique au comportement
    actuel ; part à 0 % ne laissant que les mots de 7 lettres et plus (sans
    déclencher le garde-fou, un mot long restant disponible) ; garde-fou
    déclenché quand le seul candidat est un mot court filtré et qu'aucun mot
    long n'est disponible pour compenser ; mots longs (vocabulaire du niveau
    ET `vocabulaire_long`) jamais concernés, à 3 valeurs de part ; résultat
    stable entre 5 appels successifs ; neutralité des autres profils ;
    neutralité de la consommation du générateur aléatoire dans
    `choisir_coup`, sur les six niveaux.
- `tests/test_moteur_personnages.py` :
  - `TestPartVocabulaireLongChasseur` : `test_valeurs_de_depart` et
    `test_profil_pour_niveau_avance` mis à jour pour la nouvelle valeur
    100 % à Avancé (valaient 50 %, lot H ter) — seuls changements
    nécessaires dans les tests existants, conformément à la contrainte de
    l'issue.
  - `TestPartVocabulaireCourtChasseur` (nouvelle) : valeurs de la table,
    `.profil` qui ne porte jamais la résolution par niveau,
    `profil_pour_niveau` pour Intermédiaire/Avancé (avec vérification que la
    surcharge de `part_vocabulaire_long`, indépendante, reste appliquée en
    même temps)/niveau absent, non-mutation du profil de base, neutralité
    pour Classique/Opportuniste/Titeuf.
- **Tests verts** : 1229 avant ce lot (1222 passés + 7 échecs — 2
  spécifiques aux anciennes valeurs du lot H ter, modifiés ci-dessus, et 5
  préexistants sans rapport avec ce lot, reconfirmés préexistants via `git
  stash`) ; **1252 après** (1247 passés + les 5 mêmes échecs préexistants,
  inchangés). Aucune régression, 23 tests nets ajoutés.

## Commandes de mesure prêtes à l'emploi

À lancer par Alain avec le dictionnaire réel installé (absent de ce
worktree isolé). Même script, même chemin que le jeu réel
(`ConfigJoueur.profil()` passe par `profil_pour_niveau`, lot H ter) : le
nouveau filtre de mots courts s'y applique donc bien. 200 parties chacune
(pas 100) — le bruit observé sur 100 parties au lot H ter, de plusieurs
points d'écart, est trop grand pour un réglage fin de ce niveau. Le script
ne propose pas de surcharge en ligne de commande pour un champ de personnage
propre à un seul d'entre eux (mêmes conventions que pour
`POIDS_TIRAGE_SCRABBLE_CHASSEUR`/`PART_VOCABULAIRE_LONG_CHASSEUR`) : éditer
`PART_VOCABULAIRE_COURT_CHASSEUR` dans
`src/scrabble/moteur/personnages.py` entre chaque commande.

**Intermédiaire**, plusieurs valeurs de
`PART_VOCABULAIRE_COURT_CHASSEUR[Niveau.INTERMEDIAIRE]` :

```
# PART_VOCABULAIRE_COURT_CHASSEUR[Niveau.INTERMEDIAIRE] = 0.7 (valeur de départ)
python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 200 \
    --csv style_chasseur_vs_classique_intermediaire_court70.csv

# Puis éditer la table à 0.5, relancer :
python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 200 \
    --csv style_chasseur_vs_classique_intermediaire_court50.csv

# Puis à 0.3, relancer :
python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 200 \
    --csv style_chasseur_vs_classique_intermediaire_court30.csv
```

**Avancé**, plusieurs valeurs de
`PART_VOCABULAIRE_COURT_CHASSEUR[Niveau.AVANCE]` :

```
# PART_VOCABULAIRE_COURT_CHASSEUR[Niveau.AVANCE] = 0.7 (valeur de départ)
python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 200 \
    --csv style_chasseur_vs_classique_avance_court70.csv

# Puis éditer la table à 0.5, relancer :
python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 200 \
    --csv style_chasseur_vs_classique_avance_court50.csv

# Puis à 0.3, relancer :
python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 200 \
    --csv style_chasseur_vs_classique_avance_court30.csv
```

Pour chaque run, lire dans la sortie du script le tableau de style
(scrabbles par partie, points par coup) et l'écart de points moyen contre
Classique. Objectif (rappelé par l'issue) : écart de points proche de zéro
avec un surplus de scrabbles (scrabbles par partie du Chasseur contre celui
de Classique) qui reste visible. Si à 70 % l'écart de points reste
nettement positif, descendre vers 0,5 puis 0,3 ; si au contraire le surplus
de scrabbles s'efface avant que l'écart de points n'approche zéro, c'est le
signe que ce levier seul ne suffit pas non plus (comme pour
`part_vocabulaire_long` au lot H ter) et qu'il faudra le rapport complet
pour trancher. Valeurs à ajuster uniquement sur validation d'Alain, pas en
boucle automatique.
