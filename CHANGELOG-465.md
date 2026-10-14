# Changelog — Issue #465

## Corrigé

- **`CONTEXTE.md` : phrase obsolète sur le dictionnaire comme prérequis de
  build.** La section « Données » décrivait encore le dépôt du dictionnaire
  ODS8/Hunspell comme nécessaire « avant tout build », avec l'ancien
  comportement « le jeu démarre mais valide zéro mot ». Depuis l'issue #460,
  le dictionnaire n'est plus du tout lu par le build (`scrabble.spec`) ; et
  depuis l'issue #463, son absence empêche carrément de démarrer/reprendre
  une partie (au lieu de démarrer en validant zéro mot). Phrase corrigée en
  conséquence.

## Vérifié (sans modification)

- **`build\rebuild_scrabble.bat` étape 0** : la vérification de
  `data\dictionnaire\French-Scrabble-ODS8-main` visée par cette issue avait
  déjà été retirée par l'issue #460 (commit `e3f44b2`), remplacée par un
  message d'information et la vérification d'Inno Setup conservée. Rien à
  changer dans ce fichier.
- **`installeur\README.md`** et **`data\dictionnaire\README.md`** :
  présentent déjà correctement le dictionnaire comme nécessaire pour jouer,
  pas pour builder (section « Dictionnaires : absents du build et de
  l'installeur », issue #460). Rien à changer.
- **Contrôle de sécurité** : `git ls-files data/dictionnaire` ne retourne
  que `data/dictionnaire/README.md` — aucun dictionnaire, liste de mots,
  cache `.pkl` ni fichier de définitions suivi par git. `.gitignore` ignore
  `data/dictionnaire/*` en bloc (sauf le README) et
  `data/personnages/lettre_mots_meral.txt` nommément. Aucun fichier de ce
  type dans `installeur/` (seuls `scrabble.iss` et `README.md` suivis), ni
  listé dans `scrabble.spec` (`datas` ne contient que l'icône et
  `src/scrabble/ui/web/`) ni dans `installeur\scrabble.iss`.
