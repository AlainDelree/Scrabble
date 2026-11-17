# Tests

À lire avant de modifier la suite de tests, `pytest.ini`, ou avant de
lancer la suite dans un dossier de travail isolé.

`pytest.ini` : `pythonpath = src`, `testpaths = tests`. 45 fichiers
`test_*.py` couvrant surtout le moteur, environ 1 400 tests, 2 à 3,5
minutes en séquentiel.

Par défaut, lancer **sans** les tests lents :

```
pytest -m "not lent"
```

Les tests portant le marqueur `lent` (déclaré dans `pytest.ini`, > 8 s
chacun, surtout `tests/test_moteur_ia.py::TestProgressionTrieIaRestreint` —
simulations de parties complètes) restent dans la suite complète ; seule
l'exclusion via `-m "not lent"` est ajoutée. Relancer la suite
**complète** (avec les tests lents, simple `pytest`) uniquement si le
travail modifie le moteur d'IA, les réglages de niveau ou la progression
des niveaux, et dans tous les cas une seule fois en fin de travail.

Si `pytest-xdist` est installé (ne pas l'installer sinon), paralléliser
avec `-n auto` sur l'une ou l'autre commande.

Dans un dossier de travail isolé (clone secondaire sans les données
manuellement déposées dans `data/dictionnaire/`, ni `config.json`
persistant du poste), quelques tests sont ignorés proprement (`SKIPPED`,
raison explicite dans le rapport pytest) — vocabulaire IA par palier ou
`config.json` du poste absents, sans rapport avec le code modifié. Ils
s'exécutent normalement sur un poste complet qui possède ces données. **Ne
pas relancer la suite sur le code d'origine pour comparer** : ces skips
suffisent à distinguer un échec préexistant d'un échec introduit, sauf
échec inattendu et lié aux fichiers modifiés.

`SMOKE_TEST.md` (racine) = checklist de tests **manuels** obligatoires
avant livraison (les tests headless Chromium ne couvrent pas le rendu
WebKitGTK réel).
