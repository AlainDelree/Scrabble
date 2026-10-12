# Changelog — Issue #461

## Modifié

- **Personnages IA : désactivation d'Opportuniste et Titeuf, et masquage
  complet de l'interface liée aux personnages tant que moins de deux
  personnages sont actifs.** Après l'issue #459 (Chasseur de scrabbles et
  Lettré déjà désactivés), Alain décide de ne proposer AUCUN personnage dans
  la première version diffusée : leur effet reste jugé trop discret pour
  être remarqué en jeu. Opportuniste et Titeuf déclarent à leur tour
  `actif=False` — rien n'est supprimé (code, réglages, listes de mots,
  tests de comportement) — et Classique redevient, pour cette première
  diffusion, le seul personnage actif du registre.

  - **`scrabble/moteur/personnages.py`** : `"opportuniste"` et `"titeuf"`
    déclarent désormais `actif=False`, avec un commentaire donnant la raison
    (décision d'Alain) et la procédure de réactivation (repasser à `True`).
    Nouvelles fonctions `nombre_personnages_actifs()` et
    `interface_personnages_visible()` (vrai dès que deux personnages ou plus
    sont actifs) calculées depuis le registre — jamais codées en dur, pour
    que la réapparition de l'interface soit automatique dès qu'un second
    personnage est réactivé. `libelle_choix_accueil`, `libelle_personnage_partie`
    et `lister_personnages` renvoient désormais respectivement chaîne vide,
    chaîne vide et liste vide dès que l'interface est masquée — y compris
    pour une partie sauvegardée qui mentionne un personnage (son profil reste
    résolu normalement, seul l'affichage entre parenthèses disparaît).
    L'accès direct par clé (`obtenir_personnage`, `profil_pour_niveau`,
    `PERSONNAGES[cle]`) reste inchangé, et `scripts/mesurer_force_niveaux.py`
    continue de pouvoir forcer n'importe quel personnage, actif ou non,
    puisqu'il accède au registre directement. Docstring du module mise à
    jour (nouvelle section « Désactivation d'Opportuniste et Titeuf,
    masquage de l'interface »).

  - **`scrabble/ui/accueil.py`** : `ApiAccueil.obtenir_personnages` renvoie
    la liste vide dès que l'interface est masquée. Nouvelle méthode
    `ApiAccueil.interface_personnages_visible()`, exposée au JS pour que
    `accueil.js` masque dès le chargement tout le bloc personnage (sélecteur,
    textes d'explication, lien « Les personnages ») — `accueil.html` donne un
    `id` à ce bloc (`zone-personnage`) sans `hidden` statique, pour que la
    réapparition reste automatique. `ApiAccueil.ajouter_ordinateur` refuse
    toujours un personnage inactif avec un message dédié, inchangé par ce
    lot ; un appel sans `personnage_cle` (Classique par défaut) continue de
    fonctionner normalement.

  - **`scrabble/ui/jeu.py`** : même mécanisme côté écran de jeu — nouvelle
    méthode `ApiJeu.interface_personnages_visible()`, `jeu.js` masque le
    bouton « 🎭 Personnages » dès l'initialisation si moins de deux
    personnages sont actifs.

  - **Comportement de l'ordinateur inchangé** : pour toute nouvelle partie,
    tous les ordinateurs jouent désormais comme Classique à tous les niveaux
    (plus aucun autre personnage n'étant tirable qu'à la réactivation d'un
    second), strictement comme avant l'introduction des personnages (même
    sélection de coup à graine égale, même consommation du générateur
    aléatoire — test explicite sur les six niveaux, déjà présent et
    inchangé par ce lot).

  - **Parties sauvegardées** : une partie sauvegardée avec Opportuniste,
    Titeuf, Chasseur de scrabbles ou Lettré continue de se charger et de se
    jouer avec son profil complet, sans aucune erreur — seul l'affichage
    entre parenthèses après le prénom disparaît, puisque l'interface qui
    l'afficherait est elle-même masquée.

  - **Tests adaptés** (`tests/test_accueil.py`, `tests/test_jeu_personnages.py`,
    `tests/test_moteur_partie.py`, `tests/test_moteur_personnages.py`,
    `tests/test_persistance.py`) : les tests qui supposaient Opportuniste ou
    Titeuf actifs (proposés au sélecteur, tirables par Aléatoire, affichés
    entre parenthèses) sont séparés en deux — un test par défaut (interface
    masquée, plus rien proposé/affiché) et une variante qui réactive
    localement le personnage via `monkeypatch.setitem` (procédure de
    réactivation documentée par le module, jamais de modification de code)
    pour continuer à couvrir le mécanisme générique sous-jacent (restriction
    de niveau/taille de table, tirage, repérage « dans la partie »...).
    Nouveaux tests explicites : interface masquée avec zéro ou un
    personnage actif, visible dès que deux le sont (réactivation simulée) ;
    `obtenir_personnages()` vide côté accueil et jeu par défaut ; parties
    sauvegardées avec Opportuniste et Titeuf rejouables sans erreur
    (`test_reprise_partie_avec_personnage_desactive_se_joue_normalement`
    étendu, nouveau `test_reprise_partie_avec_titeuf_desactive_se_joue_normalement`).
    Aucun test de comportement d'Opportuniste ou de Titeuf n'est supprimé.

  Moteur d'IA, réglages par niveau et personnages eux-mêmes inchangés —
  seule leur activité et l'affichage qui en dépend. 1370 tests avant ce lot :
  1365 verts (5 échecs préexistants, sans rapport, confirmés par
  `git stash` : `test_accueil::test_infos_tirage_memorisees`, deux dans
  `test_application.py`, deux dans `test_journal_integration.py`) ; après ce
  lot, 1400 tests (30 nouveaux), 1395 verts, mêmes 5 échecs préexistants
  seuls restants (voir le rapport de clôture pour le détail).
