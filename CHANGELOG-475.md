# Changelog — Issue #475

## Ajouté

- **`src/scrabble/serveur/` : prototype de serveur HTTP local, un seul
  joueur.** Sert l'interface existante (`ui/web/`) dans un navigateur à la
  place d'une fenêtre pywebview, en bibliothèque standard uniquement
  (`http.server`) — aucune dépendance ajoutée. Lancement :
  `PYTHONPATH=src python -m scrabble.serveur [--reseau] [--port 8765]
  [--dossier-donnees CHEMIN]`. Détail des options et avertissement de
  sécurité (aucune authentification, réseau local de confiance uniquement)
  dans `CONTEXTE.md`.
  - `donnees.py` : isole `config.json`/`data/parties.db`/`logs/` vers un
    dossier de données utilisateur distinct de celui de l'application de
    bureau (défaut `~/.local/share/scrabble-serveur`), sans modifier
    `config.py`/`persistance/stockage.py` (hors périmètre de l'issue) — en
    redirigeant à l'exécution les valeurs par défaut déjà liées des
    fonctions concernées.
  - `pont.py` : filtre des fonctions du routeur réellement exposées au
    navigateur (publiques, appelables, `set_window` explicitement exclu) et
    `FenetrePont`, qui tient lieu de fenêtre pywebview côté `ApiJeu` pour
    relayer les diffusions d'état (`_diffuser`/`evaluate_js`) en Server-Sent
    Events plutôt que par appel direct à une fenêtre native.
  - `httpd.py` : serveur `ThreadingHTTPServer` — fichiers statiques de
    `ui/web/` avec protection contre toute sortie du dossier (remontées
    `..`, chemins encodés, liens), appels d'API en `POST
    /__scrabble__/api/<fonction>`, flux SSE en `GET
    /__scrabble__/evenements`. Script-pont généré et injecté à la volée dans
    les pages HTML servies (recrée `window.pywebview.api` et l'évènement
    `pywebviewready`) : les fichiers de `ui/web/` ne sont pas modifiés. Ce
    même script traduit en navigation côté navigateur
    (`window.location.href`) les quatre méthodes de contrôle du routeur qui
    naviguent via `load_url` en pywebview (`demarrer_jeu`, `recommencer_jeu`,
    `retourner_accueil`, `annuler_tirage_accueil`) — le routeur, laissé sans
    fenêtre, saute déjà sa propre navigation (code existant), sans qu'aucun
    changement n'ait été nécessaire dans `accueil.js`/`jeu.js`.
  - `cli.py`/`__main__.py` : point d'entrée (`python -m scrabble.serveur`).
  - `tests/test_serveur.py` (20 tests) : isolation des données, protection du
    dossier statique, filtre des fonctions exposées, aller-retour HTTP
    complet, diffusion SSE, contenu du script-pont généré.

## Non modifié

- Aucun fichier de `moteur/`, `dictionnaire/`, `regles/`, `persistance/` ni de
  `src/scrabble/ui/` (Python ou web) — le prototype se branche entièrement
  depuis le nouveau sous-paquet, sans toucher à l'existant.

## Essais

- `pytest -m "not lent"` : 1427 passés, 2 ignorés (préexistants, sans rapport
  avec cette issue), 5 tests `lent` désélectionnés — aucune régression.
- Parcours de bout en bout (accueil → composition 1 humain + 1 ordinateur
  Facile → lancement → coup de l'humain → coup de l'ordinateur → passage →
  quitter → reprendre), rejoué par appels HTTP directs ET par un navigateur
  réel (Chromium/Playwright, script jetable non commité) pour la transition
  Accueil↔Jeu : succès des deux côtés.

## Limite volontairement hors périmètre

- L'onglet Dictionnaire des réglages et `verifier_mot`/`verifier_coup`
  restent, via ce prototype, un oracle de dictionnaire atteignable par
  quiconque se connecte au serveur — leur verrouillage est le chantier
  suivant (explicitement exclu de cette issue).
