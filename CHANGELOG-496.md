# Changelog — Issue #496

## Sécurité

- **Suppressions de sécurité : directive `noqa` retirée des 15 lignes
  justifiées par l'issue #495, `nosec` et la raison conservés (issue
  #496).**
  - `S311`/`S603`/`S607`/`S104` ne sont pas dans la sélection par défaut de
    `ruff` : le `# noqa: S…` qu'elles portaient était donc lui-même signalé
    comme inutile (`RUF100`), ajoutant 15 violations que l'outil d'audit
    externe ne demande pas — seul `# nosec` avec la ligne de raison au-dessus
    lui suffit.
  - 15 lignes modifiées, seule la partie `# noqa: S…` retirée, `# nosec
    B…` et la ligne de raison au-dessus inchangés : `main.py` (68),
    `src/scrabble/actualise.py` (103, 114), `src/scrabble/serveur/cli.py`
    (106), `src/scrabble/moteur/tirage.py` (36), `moteur/ordre.py` (104),
    `moteur/partie.py` (329), `moteur/ia.py` (814), `src/scrabble/ui/
    accueil.py` (981), `ui/api_tour_fin_partie.py` (262), `ui/jeu.py`
    (1225), `scripts/mesurer_force_niveaux.py` (570, 731, 740, 742).
  - `ruff check .` (sélection par défaut, sans cache) : 67 → 52 violations
    totales, `RUF100` 42 → 27.
