# Changelog — Issue #445

## Ajouté

- **Journal de décision de l'ordinateur : chevalet et meilleures alternatives
  à chaque tour, avec script de relecture.** Pour juger le style d'un
  personnage (Opportuniste, et d'autres plus tard), il fallait voir ce
  qu'un ordinateur avait comme lettres et quels coups il aurait pu jouer, pas
  seulement le coup joué (la base ne conservait que les coups réellement
  posés).
  - **`moteur/ia.py`** : nouvelles `AlternativeCoup` (mot, position,
    direction, score réel, score stratégique) et `EvaluationCoupsIA`
    (nb de coups possibles, 5 meilleurs, rang et fiche du coup choisi),
    produites par la nouvelle fonction **pure et sans aléa**
    `evaluer_coups()`. Le tri par score stratégique (deux passes, leave
    value) a été factorisé hors de `choisir_coup()` dans
    `_trier_par_score_strategique()`, réutilisé par les deux fonctions — elles
    restent ainsi trivialement en phase sans dupliquer la logique de tri.
    `choisir_coup()` n'a **ni nouveau paramètre ni changement de
    comportement** : `evaluer_coups()` est un second appel, indépendant,
    toujours fait **après** `choisir_coup()`, jamais à sa place.
  - **`moteur/partie.py`** : nouvelle `JournalDecisionIA` (chevalet avant
    action, meilleurs coups, rang, coup choisi) et champ optionnel
    `EntreeHistorique.journal_ia` (`None` par défaut). `Partie.jouer_tour_ia`
    capture le chevalet avant l'action puis appelle `ia.evaluer_coups()` en
    plus de `ia.choisir_coup()`, et transmet le journal à `jouer_coup()`/
    `passer()` (nouveau paramètre mot-clé `journal_ia=None` sur les trois
    méthodes d'action, jamais utilisé par un appelant humain). Garde-fou
    (`hasattr(dictionnaire_ia, "racine")`) : certains tests substituent au
    dictionnaire un double minimal n'exposant que `contient()`, prévu pour
    fonctionner tant que `choisir_coup` reste lui-même monkeypatché — le
    journal est alors simplement absent plutôt qu'en erreur.
  - **`persistance/stockage.py`** : colonne facultative `actions.journal_ia`
    (TEXT, migration idempotente comme `mode_belgicisme`) — **aucune
    migration manuelle** : une base antérieure à cette issue se recharge et
    se rejoue sans erreur, `journal_ia` valant `None`. Nouvelles fonctions de
    lecture **seule** `lire_configuration_partie()` et
    `lire_actions_journalisees()` (ouverture SQLite `mode=ro`, jamais
    d'écriture ni de migration — fonctionnent même sur une base jamais
    rouverte en écriture depuis l'ajout de la colonne, via une vérification
    `PRAGMA table_info`).
  - **`scripts/relire_journal_ia.py`** (nouveau) : affiche, tour par tour,
    joueur (personnage et niveau), chevalet avant action, coup joué, 5
    meilleures alternatives (le coup réellement joué signalé même hors top 5)
    et son rang — puis un résumé par joueur (part de coups sur case bonus,
    part sur mot double/triple, lettres posées par coup en moyenne, jokers
    joués et leur score, passes, échanges). Option `--joueur` pour filtrer un
    seul joueur. Base ouverte en lecture seule. Les parties sans journal
    (anciennes) affichent les coups seuls avec la mention « chevalet non
    enregistré ».

## Stockage : choix retenu

Colonne facultative plutôt que champ dans le JSON `detail` existant : aucun
test ne fige la structure de `actions.detail` ni de `EntreeHistorique`, donc
les deux options étaient ouvertes ; la colonne séparée garde `detail` (déjà
consulté à chaque tour pour l'affichage) inchangé et indépendant d'une
fonctionnalité d'analyse jamais lue pendant une partie.

## Poids ajouté par partie

Sur un petit dictionnaire de test, chaque entrée `journal_ia` pèse entre 139
et 741 octets (moyenne ~450 octets) selon le nombre d'alternatives
disponibles — toujours borné par le top 5, **indépendant** du nombre total de
coups possibles (qui peut se chiffrer en milliers avec le dictionnaire ODS8
complet : seul l'entier `nb_coups_possibles` en rend compte). Pour une partie
à 2 joueurs (1 humain + 1 IA) d'une trentaine de tours, l'ajout total est de
l'ordre de 5 à 10 Ko — négligeable comparé au reste de la table `actions`.

## Confidentialité

Le chevalet et les alternatives de l'IA ne sont lus que par
`lire_actions_journalisees()` (lecture seule, hors jeu) : aucune des fonctions
de sérialisation vers l'UI (`etat_public`, `serialiser_entree_historique`,
`serialiser_historique`, `serialiser_dernier_coup`) ne les mentionne —
vérifié par 4 nouveaux tests cherchant les clés `journal_ia`/
`chevalet_avant`/`score_strategique` dans le JSON envoyé au JS.

## Tests

Nouveau fichier `tests/test_journal_decision_ia.py` (28 tests) : présence/
absence du journal (ordinateur vs humain), cohérence du contenu (coup choisi
retrouvable, alternatives triées, 5 au plus), absence d'influence sur la
sélection (même coup à graine figée avec/sans journal, même état du
générateur aléatoire après `choisir_coup`, pour les 6 niveaux), aller-retour
de sauvegarde, chargement d'une ancienne base sans la colonne `journal_ia`
(écriture **et** lecture seule), poids d'une entrée, confidentialité (4
tests), et le script de relecture sur des parties fabriquées dans le test
(dont une ancienne sauvegarde sans journal et un filtre `--joueur`).

Suite complète : **995 tests verts avant** ce lot (+ 5 échecs préexistants,
confirmés avec `git stash`, sans rapport avec cette issue — `test_accueil.py`,
`test_application.py` ×2, `test_journal_integration.py` ×2) → **1023 tests
verts après** (995 + 28 nouveaux), mêmes 5 échecs préexistants inchangés.

## Exemple de sortie du script de relecture

```
=== Partie #1 (graine 2) ===
  Joueur 0 : Alice (humain)
  Joueur 1 : IA 1 (Opportuniste, INTERMEDIAIRE)

--- Tour 1 — IA 1 (Opportuniste, INTERMEDIAIRE) ---
  Chevalet avant : A E E D E U C
  Coup joué      : 'DA' en (7,7) H — score 6
  Rang du coup choisi : 1 / 4
  Meilleurs coups (score stratégique) :
    - 'DA' (7,7) H réel=6 stratégique=9 <- choisi
    - 'DE' (7,7) H réel=6 stratégique=9
    - 'DA' (7,7) V réel=6 stratégique=9
    - 'DE' (7,7) V réel=6 stratégique=9

--- Tour 5 — IA 1 (Opportuniste, INTERMEDIAIRE) ---
  Chevalet avant : E E U C B P N
  Action         : passe
  Rang du coup choisi : None / 0
  Aucun coup n'était disponible.

=== Résumé par joueur ===
- IA 1 (Opportuniste, INTERMEDIAIRE) :
    coups joués            : 2
    dont case bonus        : 2 (100 %)
    dont mot double/triple : 0 (0 %)
    lettres posées/coup    : 2.0 en moyenne
    jokers joués           : 0 (score cumulé 0)
    passes                 : 1
    échanges               : 0
```

## Contraintes respectées

- Sélection de coup, réglages par niveau, valeurs des personnages et tirage
  Aléatoire **non modifiés** : `choisir_coup()` garde exactement sa
  signature et son comportement d'avant l'issue.
- Tests existants non modifiés, tous verts (hors les 5 échecs préexistants).
- Aucune modification visible de l'interface (confirmé par les tests de
  confidentialité).
- Aucun push effectué.
