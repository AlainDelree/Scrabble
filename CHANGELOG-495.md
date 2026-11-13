# Changelog — Issue #495

## Sécurité

- **Faux positifs de sécurité jugés par le second audit externe : justifiés
  en ligne plutôt que cachés (issue #495).**
  - `src/scrabble/ui/jeu.py` (`_graine_avatar`) : l'empreinte MD5 servant à
    dériver une graine reproductible pour le choix d'avatar déclare
    désormais `usedforsecurity=False` — valeur obtenue inchangée, plus de
    signalement `ruff` S324 / Bandit B324.
  - Lancements de processus à arguments fixes ou déjà validés (`main.py`,
    `src/scrabble/actualise.py` ×2), écoute sur toutes les interfaces
    derrière l'option explicite `--reseau` (`src/scrabble/serveur/cli.py`,
    valeur par défaut : boucle locale), et usages de `random` pour le hasard
    de jeu — tirage du sac, ordre de tour, choix de l'IA, jamais un secret
    (`src/scrabble/moteur/ia.py`, `moteur/ordre.py`, `moteur/partie.py`,
    `moteur/tirage.py`, `src/scrabble/ui/accueil.py`,
    `ui/api_tour_fin_partie.py`, `ui/jeu.py`,
    `scripts/mesurer_force_niveaux.py`) : chaque emplacement porte désormais
    un commentaire expliquant la raison, suivi de la suppression précise
    (`# noqa: S603  # nosec B603`, et équivalents S607/B607, S104/B104,
    S311/B311). Remplace la consigne précédente interdisant tout
    `noqa`/`nosec` sur une ligne de sécurité.
  - Laissés intacts pour décision (hors périmètre autorisé par l'issue) :
    trois lectures `pickle.load` du cache du Trie
    (`src/scrabble/dictionnaire/dictionnaire.py`, S301/B301) et une requête
    SQL partiellement construite par chaîne, déjà paramétrée pour sa valeur
    utilisateur (`src/scrabble/persistance/stockage.py`, S608/B608).
