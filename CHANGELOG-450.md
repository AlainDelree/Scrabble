# Changelog — Issue #450

## Ajouté

- **Chasseur de scrabbles connaît les mots de 7 lettres et plus du lexique
  complet (lot H bis).** La mesure du lot H (issue #448) montrait un style
  indiscernable de Classique (écarts de scrabbles par partie dans la marge
  d'erreur, à Avancé/Expert/Champion du monde) et une perte de force de 8 à
  20 points par partie : le poids de leave renforcé (2,0) faisait jouer de
  petits coups sans que le vocabulaire disponible ne lui donne plus
  d'occasions réelles de scrabble. Le personnage joue désormais avec le
  vocabulaire de son niveau pour les mots courts, mais peut en plus poser
  tout mot de 7 lettres ou plus du lexique complet — un spécialiste des longs
  mots, dont le caractère vient maintenant du vocabulaire plutôt que d'un
  réglage de score.
  - **`scrabble.moteur.ia`** : nouveau champ facultatif
    `ProfilPersonnage.vocabulaire_long` (`bool | None`, défaut `None`,
    neutre). Nouvelle fonction `_generer_coups_candidats(plateau, chevalet,
    dictionnaire, profil, dictionnaire_complet)` : sans le champ actif (ou
    sans `dictionnaire_complet`), renvoie exactement `generer_coups(...)`
    comme avant son introduction ; avec les deux, renvoie l'UNION, sans
    doublon (clé `(ligne, colonne, direction, mot)`), des coups habituels
    (vocabulaire du niveau) et des coups générés avec `dictionnaire_complet`
    dont le **mot principal** compte au moins 7 lettres (nouvelle constante
    `_SEUIL_VOCABULAIRE_LONG`). **Mot principal** = toutes les tuiles du coup
    dans sa direction, lettres déjà posées comprises (`len(coup.tuiles)`,
    PAS `nb_nouvelles`, qui ne compte que les lettres neuves) — définition
    déjà utilisée ailleurs dans le module (`AlternativeCoup.mot`). **Mots
    croisés** : aucune logique de validation ajoutée — la seconde génération
    (avec `dictionnaire_complet`) élague ET valide (`coup_valide`) avec ce
    même Trie, donc le mot principal et tous les mots croisés d'un coup long
    sont automatiquement validés avec le lexique complet, par construction
    de `generer_coups`. `choisir_coup` et `evaluer_coups` reçoivent un
    nouveau paramètre optionnel `dictionnaire_complet` (`None` par défaut,
    ignoré si le profil ne demande pas `vocabulaire_long`) et appellent tous
    les deux `_generer_coups_candidats` — le journal de décision
    (`evaluer_coups`) porte donc sur le même ensemble de coups candidats
    élargi que la sélection réelle (`choisir_coup`), jamais un ensemble
    différent.
  - **`scrabble.moteur.partie`** : `Partie.jouer_tour_ia` calcule
    `dictionnaire_complet = self.dictionnaire` **uniquement** si
    `profil.vocabulaire_long` est actif, sinon `None` (rien transmis,
    strictement identique à avant). **Aucun nouveau chargement** : contrairement
    au vocabulaire par palier, `self.dictionnaire` est déjà, pour TOUTE
    partie, le Trie complet qui valide chaque coup posé (humain ou IA,
    voir la docstring de `Partie`) — construit par l'appelant UI à la
    création *et* à la reprise d'une partie, que la table compte un Chasseur
    de scrabbles ou non. Il ne restait donc qu'à le **brancher** vers l'IA
    en plus de la validation ; les parties sans Chasseur (ou avec un profil
    qui ne demande pas `vocabulaire_long`) ne chargent rien de plus et
    n'appellent `choisir_coup`/`evaluer_coups` sans ce paramètre, à
    l'identique d'avant. Une partie sauvegardée avec un Chasseur se reprend
    donc normalement sans aucune modification de
    `scrabble.persistance.stockage` ni `scrabble.ui.accueil` : le mécanisme
    de chargement du Trie complet à la reprise (`ApiAccueil.reprendre` →
    `obtenir_trie` → `reprendre_partie(..., dictionnaire=trie)`) existait
    déjà et n'est pas spécifique au Chasseur.
  - **Temps de réflexion supplémentaire** : `vocabulaire_long` fait tourner
    `generer_coups` une seconde fois (sur le lexique complet, le double de la
    génération normale) à chaque tour du Chasseur. Mesuré sur un Trie
    synthétique (le dictionnaire réel est absent de ce worktree isolé) —
    vocabulaire de niveau à 3 000 mots contre lexique complet à 18 000 mots,
    plateau à mi-partie, dix tirages de chevalet : **23 ms/tour en Classique
    contre 103 ms/tour en Chasseur, soit ×4,4**. Le ratio réel dépendra de la
    taille relative ODS8 / palier du niveau (probablement plus grande que
    dans ce test synthétique) ; mesure réelle à faire par Alain avec le
    dictionnaire installé (voir commandes de mesure plus bas) — reste de
    l'ordre de quelques dizaines à centaines de millisecondes par tour, sans
    impact perceptible en jeu (le tour d'un ordinateur n'est jamais instantané
    à l'écran).
  - **`scrabble.moteur.personnages`** : `NIVEAUX_CHASSEUR_SCRABBLES` resserré
    à **Intermédiaire et Avancé** (remplace « Avancé à Champion du monde » du
    lot H). Déterminé par le code et la configuration des paliers plutôt que
    par la proposition par défaut de l'issue (« Avancé à Expert ») : d'après
    `scrabble.moteur.ia._PALIERS_PAR_NIVEAU`/`resoudre_palier` et
    `scrabble.dictionnaire.dictionnaire.FICHIERS_VOCABULAIRE_PALIER` (quatre
    entrées : debutant/facile/intermediaire/avance), **seuls ces quatre
    niveaux ont un vocabulaire restreint** — Expert et Champion du monde
    jouent déjà, tous les deux, sur le lexique complet (aucune entrée de
    palier pour eux, refonte de l'échelle issue #401). `vocabulaire_long` n'y
    changerait donc rigoureusement rien : l'union avec le lexique complet
    serait un no-op puisque le vocabulaire du niveau EST déjà le lexique
    complet. Exclure Expert suit donc exactement la même logique que
    l'exclusion de Champion du monde proposée par l'issue. Parmi les niveaux
    à vocabulaire restreint, Débutant et Facile restent exclus (scrabbles peu
    réalistes à ces niveaux, même critère qu'au lot H) : restent
    Intermédiaire et Avancé. Plage provisoire, à ajuster par Alain après
    mesure.
  - **`scrabble.moteur.personnages`** : poids de leave du Chasseur
    (`POIDS_LEAVE_CHASSEUR_SCRABBLES`) remplacé par `None` (**aucune
    surcharge** — le poids de leave du niveau du joueur s'applique tel quel,
    de 0,3 à Intermédiaire à 0,6 à Avancé), au lieu de 2,0 au lot H. Choix de
    la première des deux valeurs de départ proposées par l'issue (« celle du
    niveau, sans surcharge ») plutôt qu'une valeur légèrement supérieure :
    puisque `vocabulaire_long` devient l'unique trait de caractère du
    personnage, retirer la surcharge de leave isole proprement son effet
    pour la prochaine mesure, sans compounder deux changements à la fois —
    c'est justement le poids à 2,0 que la mesure du lot H incriminait pour la
    perte de force. La constante reste nommée en tête de module, à remonter
    à une valeur légèrement supérieure à `None` si la mesure montre que
    Chasseur garde encore trop facilement un petit coup plutôt qu'un reliquat
    prometteur. Le bonus de pose de 7 lettres (`bonus_scrabble` =
    `BONUS_SEPT_LETTRES_CHASSEUR` = 150) est inchangé.
  - **`scripts/mesurer_force_niveaux.py`** : `jouer_une_partie` transmet
    désormais `dictionnaire_complet=dictionnaire` (le Trie complet déjà
    chargé pour la validation) à `ia.choisir_coup` — même chemin que le jeu
    réel (`Partie.jouer_tour_ia`), pour que le Chasseur y dispose du lexique
    complet pendant la mesure. Ignoré par tout profil qui ne demande pas
    `vocabulaire_long` : aucun effet sur les mesures existantes (Opportuniste,
    Classique, niveaux bruts).
  - **Neutralité** : un profil vide, ou sans `vocabulaire_long`, reproduit
    bit à bit le comportement d'avant son introduction, à graine égale, pour
    tous les niveaux et personnages (testé explicitement, comme aux lots A et
    H) — y compris quand un `dictionnaire_complet` est malgré tout fourni à
    `choisir_coup`/`evaluer_coups` (défense en profondeur : c'est le profil,
    jamais l'appelant, qui décide).
  - Tests ajoutés : `tests/test_moteur_ia.py` (nouvelle classe
    `TestVocabulaireLong` — neutralité sans profil/profil vide, mot de 7
    lettres absent du vocabulaire du niveau trouvé et joué avec le lexique
    complet, mot croisé validé avec le lexique complet, mots courts non
    empruntés au lexique complet, journal de décision sur l'ensemble
    élargi) ; `tests/test_moteur_partie.py` (intégration `Partie.jouer_tour_ia`
    de bout en bout : Chasseur trouve le mot long via `self.dictionnaire`,
    Classique sur le même scénario ne le voit pas) ; `tests/test_moteur_personnages.py`
    (profil du Chasseur — `vocabulaire_long=True`, `poids_leave=None` ;
    neutralité de Classique/Opportuniste ; disponibilité resserrée à
    Intermédiaire/Avancé, libellés et messages associés mis à jour). Tests
    existants ajustés pour la nouvelle plage de disponibilité (sans changer
    ce qu'ils vérifient) : `test_ajouter_ordinateur_refuse_chasseur_a_quatre_joueurs`
    (niveau Avancé + `paliers_disponibles` monkeypatché, au lieu d'Expert,
    pour continuer à isoler le refus sur la taille de table) ;
    `test_creer_partie_aleatoire_peut_tirer_classique` et
    `test_creer_partie_aleatoire_peut_tirer_opportuniste_a_deux_joueurs`
    (niveau Avancé, où le registre complet reste disponible, au lieu de
    Champion du monde).
  - **Tests verts** : 1133 avant ce lot (1128 passés + 5 échecs préexistants,
    sans rapport avec ce lot — confirmés préexistants via `git stash`,
    `tests/test_accueil.py::TestApiAccueilInfosTirage::test_infos_tirage_memorisees`
    et 4 autres liés à l'environnement pywebview/GTK absent de ce worktree) ;
    **1143 après** (1138 passés + les 5 mêmes échecs préexistants, inchangés).
    Aucune régression, 10 tests nets ajoutés.

## Commandes de mesure prêtes à l'emploi

À lancer par Alain avec le dictionnaire réel installé (absent de ce worktree
isolé). Même script que pour Opportuniste (issue #439/#446), même format de
sortie (tableau de style — scrabbles par partie, points par coup — et taux de
victoire). Chasseur de scrabbles contre Classique, 100 parties, aux quatre
niveaux déjà mesurés au lot H (Intermédiaire, Avancé, Expert, Champion du
monde) — vocabulaire long attendu pour faire une différence à Intermédiaire et
Avancé (vocabulaire du niveau restreint), et pour n'en faire AUCUNE à Expert
et Champion du monde (vocabulaire déjà complet à ces deux niveaux, confirmant
ou infirmant l'hypothèse de ce lot) :

```
python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_intermediaire.csv

python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_avance.csv

python scripts/mesurer_force_niveaux.py EXPERT EXPERT \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_expert.csv

python scripts/mesurer_force_niveaux.py CHAMPION_DU_MONDE CHAMPION_DU_MONDE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_champion.csv
```

Ces commandes fonctionnent même si Chasseur de scrabbles n'est plus
« disponible » (au sens UI) à Expert/Champion du monde : le script, comme pour
Opportuniste, n'applique aucun garde-fou de disponibilité — c'est précisément
ce qui permet de mesurer l'absence d'effet attendue à ces deux niveaux.
