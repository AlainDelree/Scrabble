### Ajouté

- **Issue #345** — `build/rebuild_scrabble.bat` produit désormais un second
  artefact : `installeur\output\scrabble.zip`, destiné à être publié comme
  asset de Release GitHub et téléchargé/extrait par l'updater Actualise.

  Avant la compilation Inno Setup, le script télécharge `actualise.zip`
  depuis la Release v1 de `AlainDelree/Actualise` et en extrait
  `Actualise.exe` vers `C:\Temp\ScrabbleBuild\Actualise.exe` (chemin source
  attendu par `installeur\scrabble.iss`) ; tout échec de téléchargement ou
  d'extraction arrête le build avec un message d'erreur explicite.

  Après la compilation, le script génère `manifest.json`
  (`{"build": 1, "supprimer": []}`) puis zippe le contenu de
  `dist\Scrabble\` avec ce manifeste vers `installeur\output\scrabble.zip`
  (nom fixe, sans numéro de version — celui-ci vit dans le tag de la
  Release GitHub), vérifie sa présence et affiche sa taille.
