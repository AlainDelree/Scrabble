### Ajouté

- **Issue #353** — Mode optionnel `--publier [N]` dans
  `build/rebuild_scrabble.bat`. Sans paramètre, le script se comporte
  exactement comme avant. Avec `--publier`, après un build réussi : calcul
  du SHA-256 de `installeur\output\scrabble.zip` (PowerShell
  `Get-FileHash`), détermination du numéro de build (celui fourni en
  paramètre, sinon incrément de 1 du `build` actuel de `version.json` à la
  racine du clone), écriture de `version.json`, puis `git add` + `git
  commit`. Le script n'exécute jamais `git push` ni `gh release create` —
  un rappel explicite les mentionne comme étapes manuelles restantes.
