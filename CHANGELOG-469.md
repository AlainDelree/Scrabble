# Issue #469 — Installeur : ligne `#13#10` seule faisant échouer la compilation ISPP

- Correction de `installeur\scrabble.iss` (procédure `AfficherMessageDictionnaires`,
  section `[Code]`) : les deux lignes composées uniquement de `#13#10 +` (après
  l'indentation) ont été ramenées en fin de la ligne de texte précédente, sur
  la même ligne. Le préprocesseur ISPP d'Inno Setup traite tout `#` en début
  de ligne comme une directive de préprocesseur ; isolé, `#13#10` était donc
  rejeté avec « Unknown preprocessor directive » (build 13, issue #468). Le
  texte affiché à l'utilisateur (contenu et retours à la ligne) est inchangé.
- Vérification du reste de `installeur\scrabble.iss` : aucune autre ligne ne
  commence par un `#` qui ne soit pas une vraie directive ISPP voulue
  (`#define`, `#ifndef`/`#endif`).
