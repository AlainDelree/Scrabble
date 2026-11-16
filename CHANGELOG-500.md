# Changelog — Issue #500

## Linter

- **Retrait des 27 directives `noqa` devenues inutiles (`RUF100`), sans
  configuration `ruff` (issue #500).**
  - `E402`, `A002` et `N802` ne font partie d'aucune sélection par défaut de
    `ruff` 0.17.4 : les `# noqa: E402`/`A002`/`N802` qu'elles portaient
    étaient donc eux-mêmes signalés comme inutiles (`RUF100`), sans rapport
    avec un éventuel `sys.path.insert` placé avant les imports (vérifié sur
    un script isolé : `E402` ne réapparaît pas une fois la directive
    retirée, précisément parce que la règle n'est pas activée par défaut,
    avec ou sans ce motif).
  - 27 directives retirées, uniquement le commentaire `# noqa: …` (et sa
    justification textuelle le cas échéant) : `main.py` (2, E402),
    `scripts/_harness_jeu/verif_296_webkitgtk.py` (1, E402),
    `scripts/_harness_jeu/verif_belgicisme_270_webkitgtk.py` (1, E402),
    `scripts/_harness_jeu/verif_belgicisme_289_webkitgtk.py` (1, E402),
    `scripts/_harness_jeu/verif_belgicisme_290_webkitgtk.py` (1, E402),
    `scripts/_harness_jeu/verif_belgicisme_291_webkitgtk.py` (1, E402),
    `scripts/_harness_jeu/verif_belgicisme_292_webkitgtk.py` (1, E402),
    `scripts/construire_definitions.py` (2, E402),
    `scripts/generer_classiques.py` (1, E402),
    `scripts/generer_mots_courants.py` (1, E402),
    `scripts/mesurer_force_niveaux.py` (7, E402),
    `scripts/relire_journal_ia.py` (5, E402),
    `src/scrabble/serveur/httpd.py` (1 `A002`, 2 `N802`). Aucun code
    modifié, aucune ligne `# nosec` touchée, aucune configuration `ruff`
    créée.
  - `ruff check . --no-cache` (sélection par défaut, 0.17.4) : 52 → 25
    violations, `RUF100` 27 → 0, aucune violation nouvelle. Suite de tests
    identique avant/après (1467 passés, 6 ignorés, 5 désélectionnés).
