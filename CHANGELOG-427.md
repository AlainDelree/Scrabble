### Corrigé

- **Issue #427** — `PermissionError [WinError 5]` au premier lancement sur un
  compte Windows standard (non-administrateur), confirmé en conditions
  réelles. La correction de l'issue #421 redirigeait déjà toutes les
  écritures runtime (logs, `config.json`, `parties.db`, caches/personnali-
  sations du dictionnaire) vers un dossier unique `RACINE_DONNEES_UTILISATEUR`
  hors du dossier d'installation — mais avait choisi `C:\Scrabble` (racine du
  disque système) en le supposant non protégé comme `Program Files`. Testé en
  situation réelle, cette hypothèse s'est révélée fausse : Windows refuse
  aussi la création de dossiers à la racine de `C:\` à un compte standard.
  `src/scrabble/config.py` calcule désormais ce dossier via
  `%LOCALAPPDATA%\Scrabble` sous Windows (`os.environ["LOCALAPPDATA"]`,
  emplacement conçu pour les données utilisateur, toujours inscriptible sans
  droits admin), avec repli XDG (`~/.local/share/Scrabble`) si l'app gelée
  tournait un jour hors Windows. Comme tous les autres modules (`journal.py`,
  `persistance/stockage.py`, `dictionnaire/dictionnaire.py`) dérivaient déjà
  leurs chemins d'écriture de cette même constante, aucun autre fichier n'a dû
  être modifié. Comportement inchangé en mode non gelé (dev/tests sous
  Linux) : `RACINE_DONNEES_UTILISATEUR` reste la racine du projet.
