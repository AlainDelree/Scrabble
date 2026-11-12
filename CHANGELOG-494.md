## Non publié

### Corrigé
- `ui/jeu.py` : déclaration d'un `__all__` pour `demarrer_suivi`,
  `enregistrer_action` et `finaliser_partie`, lus dynamiquement par d'autres
  modules et par les tests (monkeypatch), afin que `ruff` (F401) ne les
  signale plus sans recourir à un `# noqa` (issue #494).
