# Changelog — Issue #471

## Ajouté

- **`installeur\scrabble.iss` : droit de modification pour le groupe
  « Utilisateurs » sur `{app}` et `C:\Actualise`.** Nouvelles entrées
  `Permissions: users-modify` dans `[Dirs]` (alias Inno Setup résolu via le
  SID universel `S-1-5-32-545`, indépendant de la langue de Windows), avec
  héritage aux sous-dossiers et fichiers. Sans ce droit, Actualise — lancé
  depuis un compte standard, sans droits administrateur — ne peut pas
  remplacer les fichiers du jeu lors d'une mise à jour (constaté sur le
  build 13 : `PermissionError` sur une DLL, contourné à la main par Alain
  via `icacls`). Les droits existants ne sont ni supprimés ni réinitialisés
  (ajout uniquement), notamment ceux déjà présents sur l'instance partagée
  `C:\Actualise`.
- **`installeur\README.md` : section expliquant ces droits**, avec la
  commande `icacls` à lancer à la main sur un poste déjà installé avant
  cette version (une réinstallation ou installation par-dessus les applique
  automatiquement, mais pas une simple mise à jour via Actualise).
