# Changelog — Issue #452

## Ajouté

- **Personnage Titeuf, le farceur aux mots de cour de récré (lot J, niveau
  Débutant).** Débutant n'avait jusqu'ici aucun personnage disponible à
  part Classique (Opportuniste et Chasseur de scrabbles l'excluent tous les
  deux), ce qui rendait aussi Aléatoire indisponible à ce niveau (règle du
  lot G : au moins deux personnages). Titeuf comble ce trou : un personnage
  comique, inspiré de Titeuf (Zep), qui place ses mots favoris de cour de
  récré dès qu'il le peut, même peu rémunérateurs.

  - **`data/personnages/titeuf_mots_favoris.txt`** (nouveau fichier,
    versionné avec le code) : liste de mots favoris, un mot par ligne,
    modifiable sans toucher au code. Liste de départ : caca, pipi, prout,
    crotte, popo, fesses, zizi, slip, beurk, sexe — mots courts,
    humoristiques, de cour de récré, sans injure ni terme haineux.

  - **`scrabble.moteur.ia`** : deux nouveaux champs facultatifs de
    `ProfilPersonnage`, tous deux neutres par défaut (`None`), généralisant
    les mécanismes du lot H ter (Chasseur de scrabbles) à un critère de
    LISTE plutôt que de LONGUEUR :
    - `mots_favoris: frozenset[str] | None`. Élargit l'ensemble des coups
      candidats (`_generer_coups_candidats`) aux coups dont le **mot
      principal** figure dans cette liste : générés via un petit Trie
      construit depuis la liste, et VALIDÉS (mot principal et mots croisés)
      avec `dictionnaire_complet` — pas avec ce petit Trie, qui rejetterait
      presque tous les mots croisés. `generer_coups` (`scrabble.moteur.
      generateur`) reçoit pour cela un nouveau paramètre optionnel
      `dictionnaire_validation` (`None` par défaut = retombe sur
      `dictionnaire`, comportement strictement inchangé) qui découple le
      Trie d'EXPLORATION (élagage par préfixe) de celui de VALIDATION. Un
      mot de la liste absent du lexique complet n'est filtré par aucun code
      dédié : la génération/validation ne produit alors simplement aucun
      coup pour lui — ignoré sans erreur. Sans doublon avec les coups du
      vocabulaire du niveau (même ensemble `vus` que `vocabulaire_long`, les
      deux élargissements se combinant sans conflit).
    - `poids_tirage_favori: float | None`. Généralise
      `poids_tirage_scrabble` (lot H ter) au critère de liste, avec une
      différence essentielle : les coups à mot favori sont ajoutés au pool
      de tirage même s'ils sont EXCLUS de la tranche des meilleurs coups
      (`_tirer_dans_tranche`, nouveau paramètre `coups_complets`) — un mot
      favori peu rémunérateur, plausible à Débutant, pourrait sinon en être
      écarté d'office. Si un coup cumule les deux critères (scrabble ET mot
      favori), le plus grand des deux poids s'applique. Neutralité stricte
      inchangée : sans profil, ou avec les deux poids à `None`, c'est
      exactement `rng.choice(tranche).coup` — même consommation du
      générateur aléatoire qu'avant l'introduction de ces champs.
    - `Partie.jouer_tour_ia` transmet `self.dictionnaire` comme lexique
      complet dès que `profil.vocabulaire_long` OU `profil.mots_favoris` est
      actif (auparavant : seulement `vocabulaire_long`).

  - **`scrabble.moteur.personnages`** : nouvelles constantes
    `CHEMIN_MOTS_FAVORIS_TITEUF`, `MOTS_FAVORIS_TITEUF` (chargée une fois au
    chargement du module via la nouvelle fonction `charger_mots_favoris`,
    qui réutilise `lire_liste_mots`/`desaccentuer` de
    `scrabble.dictionnaire.dictionnaire`), `POIDS_TIRAGE_FAVORI_TITEUF =
    50.0` (calcul détaillé dans le docstring du module et le rapport de
    l'issue), `PRENOM_TITEUF = "Titeuf"`, `NIVEAUX_TITEUF = {DEBUTANT}`,
    `NB_JOUEURS_TITEUF = {2}`. Nouvelle entrée `"titeuf"` dans le registre
    `PERSONNAGES`.

  - **Conséquence attendue (règle déjà en place, lot G) :** Débutant compte
    maintenant deux personnages réels (Classique + Titeuf) — Aléatoire y
    redevient donc disponible, sans aucune autre modification, et son
    tirage à ce niveau couvre bien les deux.

  - **`scripts/mesurer_force_niveaux.py`** : nouvel indicateur de style
    « Coups dont le mot principal est un mot favori » (colonne CSV
    `part_mot_favori`, préfixée `a_`/`b_`), alimenté par la liste de mots
    favoris résolue depuis le profil de CHAQUE camp — vaut 0 pour un
    personnage sans liste. Nouvel exemple de commande documenté (Titeuf
    contre Classique à Débutant, 100 parties, avec tableau de style).

  - **Tests** (`tests/test_moteur_generateur.py`,
    `tests/test_moteur_ia.py`, `tests/test_moteur_personnages.py`,
    `tests/test_mesurer_force_niveaux_style.py`) : neutralité des deux
    nouveaux champs (profil vide, consommation du générateur aléatoire
    inchangée), accessibilité d'un mot favori COURT hors du vocabulaire du
    niveau (contrairement à `vocabulaire_long`, aucune contrainte de
    longueur), mot absent du lexique ignoré sans erreur, absence de
    doublons, cohérence du journal de décision, fréquence de tirage proche
    de la théorie, ajout au pool même hors tranche, liste modifiable sans
    toucher au code (fichier temporaire), disponibilité de Titeuf
    (Débutant + deux joueurs seulement), Aléatoire redevenu disponible à
    Débutant, neutralité des autres personnages.

    Quelques tests existants, qui encodaient explicitement qu'Aléatoire
    était indisponible à Débutant (lot G, issue #447) ou que tout le
    registre était disponible à un niveau donné, sont mis à jour pour
    refléter la nouvelle disponibilité plutôt que laissés en échec :
    `tests/test_accueil.py`,
    `tests/test_moteur_partie.py`,
    `tests/test_moteur_personnages.py`.
