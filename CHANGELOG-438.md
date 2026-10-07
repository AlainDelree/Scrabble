# Changelog — Issue #438

## Ajouté

- **Personnages IA, lot A : infrastructure neutre.** Nouvelle classe
  `ProfilPersonnage` (`src/scrabble/moteur/ia.py`) : surcharges optionnelles
  (`malus_longueur`, `bonus_premium`, `poids_leave`) des réglages déjà
  indexés par `Niveau`, toutes à `None` par défaut. Un profil absent ou
  vide reproduit bit à bit le calcul d'avant son introduction — les dicts
  `_MALUS_LONGUEUR`/`_BONUS_PREMIUM`/`_POIDS_LEAVE` restent la seule source
  de vérité du calibrage, jamais modifiés ni redéfinis par un profil.
  Branché en paramètre optionnel final (défaut `None`) de
  `_score_strategique`, `choisir_coup` (`ia.py`) et `Partie.jouer_tour_ia`
  (`src/scrabble/moteur/partie.py`).
- `Joueur.personnage` : champ texte facultatif (`""` par défaut), sérialisé
  dans la sauvegarde SQLite symétriquement à `niveau`
  (`src/scrabble/persistance/stockage.py`, `_joueurs_vers_json`/
  `_reconstruire_joueurs`). Une ancienne sauvegarde sans la clé `personnage`
  se recharge avec un personnage vide (`.get(..., "")`).
- Aucun personnage n'est encore sélectionnable : pas de changement d'UI.

## Corrigé

- `Partie.jouer_tour_ia` ne transmet désormais `profil` à
  `ia.choisir_coup` que lorsqu'il est renseigné (au lieu de toujours
  transmettre `profil=None`), pour ne rien changer à la signature reçue par
  les appelants/tests existants qui substituent `choisir_coup` par une
  fonction sans ce paramètre.

## Tests

- `tests/test_moteur_ia.py` : `TestProfilPersonnageNeutre` (profil vide ou
  absent ⇒ même score stratégique et même coup choisi, à graine égale, pour
  les 6 niveaux) et `TestProfilPersonnageSurcharge` (un champ renseigné
  change bien le résultat, sans muter les dicts indexés par niveau).
- `tests/test_moteur_partie.py` : `jouer_tour_ia` ne transmet pas `profil`
  sans personnage (compatibilité des faux `choisir_coup` existants) / le
  transmet bien quand fourni.
- `tests/test_persistance.py` : aller-retour de sauvegarde avec et sans
  personnage, et rechargement d'une sauvegarde simulée d'avant #438 (clé
  `personnage` retirée directement en base) sans la clé.

## Reprise de travail partiel

Ce lot reprend un worktree déjà entamé lors d'une tentative précédente de
l'issue #438 (code de l'infrastructure déjà écrit, non commité). 8 tests
existants échouaient, tous pour la même cause : `jouer_tour_ia` transmettait
toujours `profil=profil` (même `None`) à `choisir_coup`, ce qui cassait les
tests qui monkeypatchent `choisir_coup` par une fonction sans paramètre
`profil` (`TypeError: ... got an unexpected keyword argument 'profil'`).
Corrigé en ne transmettant `profil` que s'il n'est pas `None` — aucun test
existant modifié. Les 5 échecs restants (`test_accueil.py`,
`test_application.py`, `test_journal_integration.py`) préexistent au backup
de cette tentative (vérifié par `git stash`) et sont sans rapport avec ce
lot.

## Tests avant/après

- Avant correction du bug de reprise : 892 passés, 8 échoués (tous liés à ce
  lot) sur 900.
- Après correction, avant ajout des tests du lot A : 895 passés, 5 échoués
  (préexistants, sans rapport) sur 900.
- Après ajout des tests du lot A : 917 passés, 5 échoués (préexistants) sur
  922.
