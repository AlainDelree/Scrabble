# Changelog — Issue #446

## Ajouté

- **Indicateurs de style comparés A/B dans le script de mesure de force
  (`scripts/mesurer_force_niveaux.py`).** Le script oppose déjà deux
  configurations IA sur de nombreuses parties et mesure qui gagne et de
  combien (lot B, issue #439), mais ne disait rien de leur *style* de jeu :
  on savait qu'Opportuniste est aussi fort que Classique, pas s'il joue
  vraiment différemment — une seule partie à la main n'avait pas permis de
  trancher, le style y étant noyé dans le hasard du tirage.
  - Nouvelle dataclass **`IndicateursPartieJoueur`** (par joueur, par
    partie) et champs `indicateurs_a`/`indicateurs_b` ajoutés à
    `ResultatPartie`, remplis par la nouvelle `_calculer_indicateurs_joueur()`
    — appelée **après** la fin de la boucle de jeu dans `jouer_une_partie()`,
    en relecture pure de `Partie.historique` et des chevalets finaux (aucun
    appel supplémentaire à `ia.choisir_coup`, aucune consommation d'aléa) :
    `score_a`/`score_b`/`commence`/`tours` restent calculés exactement comme
    avant. Vérifié par comparaison directe avant/après la modification, même
    graines, 30 parties déterministes : résultats strictement identiques.
  - Indicateurs retenus, cumulés sur toutes les parties (définitions exactes
    dans le docstring de `IndicateursPartieJoueur`) :
    - part des coups touchant au moins une case à multiplicateur (toute case
      **neuve** du coup dont `TypeCase != NORMALE`, reflet direct de
      `DetailMot.cases_bonus`) ;
    - part des coups touchant un mot double ou triple — la case **centrale**
      y est comptée (elle fonctionne comme un mot double), sinon le tout
      premier coup de chaque partie, qui la couvre toujours, aurait été
      systématiquement exclu de ce sous-total ;
    - lettres posées par coup (`len(positions_posees)`, pas la longueur du
      mot formé) et part des coups de une ou deux lettres ;
    - points par coup, longueur du mot principal (premier mot de
      `detail.mots`, celui porté par la direction du coup) ;
    - scrabbles (7 lettres posées) par partie ;
    - jokers joués : nombre par partie, points du coup où le joker est posé,
      et tour de sa pose (rang 1-indexé de l'action dans l'historique
      **complet** de la partie, les deux joueurs confondus — même convention
      que `tours`/`MAX_TOURS` ailleurs dans le script) ; une tuile joker déjà
      posée un tour précédent et seulement retraversée par un coup ultérieur
      ne recompte pas ;
    - passes par partie ;
    - pénalité des lettres restantes en fin de partie
      (`Joueur.valeur_chevalet()` — le chevalet n'est pas vidé par
      `Partie._terminer`, seul le score l'intègre déjà en soustraction).
  - Écart-type d'échantillon (points/coup, longueur de mot, lettres posées)
    ou IC95 (proportions, via l'`_ic_95` existant ; nouvelle
    `_ic_95_moyenne` pour la moyenne des continus) selon le cas, pour juger
    si un écart A-B est significatif.
  - **Affichage** : nouveau tableau comparatif A vs B
    (`_afficher_tableau_style`), ajouté à la fin du résumé existant
    (`_afficher_resume`, lui-même **inchangé**) — colonnes valeur A, valeur
    B, écart A-B. Absent du mode `--comparer` (relit un CSV sans le détail
    par coup nécessaire à ces indicateurs).
  - **Export CSV** : 13 colonnes par joueur (préfixe `a_`/`b_`) ajoutées
    **après** les six colonnes historiques du CSV — `_lire_csv` (mode
    `--comparer`) les lit par position et ignore le reste, donc reste
    compatible avec les CSV produits avant et après cet ajout. Les moyennes
    sur zéro coup (ex. aucun joker joué cette partie) sont exportées en
    chaîne vide, pas en `0`, pour ne pas confondre « jamais » et « zéro
    point ».
  - **`tests/test_mesurer_force_niveaux_style.py`** (nouveau, 3 tests) :
    calcul des indicateurs sur une petite partie fabriquée à la main (CHAT
    au centre, CH sur lettre double, AS au joker sur une autre lettre
    double, puis une passe — valeurs attendues connues par avance : cases
    bonus, longueurs, joker et son tour, pénalité) ; export CSV complet
    (vérifie aussi la colonne vide du joker non joué) ; intégration
    `jouer_une_partie()` de bout en bout (dictionnaire vide à dessein, sans
    dépendre d'un vrai dictionnaire — absent de ce worktree isolé, comme au
    lot B) vérifiant le déterminisme du résultat de force entre deux appels
    identiques.
  - **Aucune modification** du moteur d'IA, des réglages par niveau, des
    personnages ni du tirage aléatoire (`moteur/ia.py`, `moteur/personnages.py`
    non touchés).
  - Suite pytest : 1023 verts / 5 échecs préexistants (inchangés, hors
    périmètre — `test_accueil.py`, `test_application.py` ×2,
    `test_journal_integration.py` ×2, confirmés préexistants avant toute
    modification) avant ce lot ; **1026 verts / mêmes 5 échecs** après (3
    nouveaux tests, aucune régression).
  - **Mesure réelle non lancée** : le dictionnaire ODS8 n'est pas présent
    dans ce worktree isolé (gitignoré, déposé manuellement — voir lot B,
    issue #439) ; conformément à la consigne, il n'a pas été recherché
    ailleurs. Deux commandes prêtes à lancer par Alain (vocabulaire par
    palier, comme le jeu réel, avec export CSV pour réanalyse ultérieure) :

    ```
    python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
        --personnage-a opportuniste --personnage-b classique --vocab palier \
        --parties 200 --csv style_opportuniste_vs_classique_avance.csv

    python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
        --personnage-a opportuniste --personnage-b classique --vocab palier \
        --parties 200 --csv style_opportuniste_vs_classique_intermediaire.csv
    ```

  - Exemple de tableau obtenu sur une mesure courte (30 parties, FACILE vs
    DEBUTANT, lexique de démonstration minimaliste — valeurs indicatives, pas
    une mesure réelle) :

    ```
    ============================================================
    STYLE DE JEU — FACILE (A) vs DEBUTANT (B)
    ============================================================
    Indicateur                                       FACILE    DEBUTANT     Écart (A-B)
    Coups touchant une case à multiplicateur     57.1% ± 10.2%  53.8% ± 11.1%           +3.3%
      dont mot double/triple (ou centre)         23.1% ± 8.7%  20.5% ± 9.0%           +2.6%
    Lettres posées par coup                      1.91 ± 0.18  1.58 ± 0.16           +0.34
    Coups de une ou deux lettres                 79.1% ± 8.4%  87.2% ± 7.4%           -8.1%
    Points par coup                              4.80 ± 0.43  4.23 ± 0.46           +0.57
    Longueur du mot principal                    2.67 ± 0.16  2.50 ± 0.15           +0.17
    Scrabbles (7 lettres) par partie             0.00 ± 0.00  0.00 ± 0.00           +0.00
    Jokers joués par partie                      0.43 ± 0.22  0.13 ± 0.12           +0.30
      points du coup où un joker est posé        3.69 ± 1.03  3.25 ± 1.47           +0.44
      tour de pose du joker                      3.85 ± 2.21  4.00 ± 2.53           -0.15
    Passes par partie                            1.40 ± 0.35  1.83 ± 0.46           -0.43
    Pénalité lettres restantes en fin de partie  19.37 ± 2.85  17.03 ± 2.31           +2.33
    ============================================================
    ```

  Fichiers touchés : `scripts/mesurer_force_niveaux.py` (modifié),
  `tests/test_mesurer_force_niveaux_style.py` (nouveau). Aucune modification
  de l'interface du jeu.
