# Changelog — Issue #488

## Sécurité

- **Cache du Trie (`trie_cache.pkl`/`trie_ia_cache*.pkl`) sorti du dossier où
  l'on dépose les dictionnaires tiers (issue #488).**
  - Nouveau sous-dossier dédié `DOSSIER_CACHE_DICO` (`cache/dictionnaire/`
    sous le dossier de données de l'application) dans
    `src/scrabble/dictionnaire/dictionnaire.py` : `CHEMIN_CACHE`,
    `CHEMIN_CACHE_IA` et `FICHIERS_CACHE_IA_PALIER` y pointent désormais, au
    lieu de `DOSSIER_DICO_UTILISATEUR` (qui reste, lui, réservé aux
    personnalisations éditables `mots_ajoutes_*`/`mots_retires_*`/
    `classiques_*`, inchangées).
  - Avant ce changement, `DOSSIER_DICO_UTILISATEUR` était en mode
    développement le même dossier physique que `data/dictionnaire/`, là où
    les dictionnaires tiers sont déposés à la main : un fichier déposé dans
    ce dossier pouvait remplacer le cache et être rechargé par
    `pickle.load` (la validation d'en-tête de `_cache_valide` a lieu APRÈS
    le chargement, donc ne protège pas). Format du cache et logique de
    fraîcheur inchangés — seul l'emplacement change.
  - `.gitignore` : nouvelle entrée `cache/`.
  - `data/dictionnaire/README.md` et `CONTEXTE.md` : mise à jour pour ne
    plus décrire le cache comme vivant dans `data/dictionnaire/`.
  - Les anciens fichiers de cache qui pourraient rester dans
    `data/dictionnaire/` ne sont plus jamais lus (les chemins par défaut ont
    changé) ; ils ne sont pas non plus supprimés automatiquement — le cache
    se régénère simplement au premier lancement à son nouvel emplacement.
  - Tests : `tests/test_dictionnaire.py` — assertion existante mise à jour
    (`FICHIERS_CACHE_IA_PALIER` pointe vers `DOSSIER_CACHE_DICO`) et nouveau
    test `test_cache_dictionnaire_separe_du_dossier_de_depot_des_dictionnaires`
    vérifiant que le dossier de cache n'est ni `DOSSIER_DICO` ni
    `DOSSIER_DICO_UTILISATEUR`, ni un de leurs sous-dossiers.
  - `build/` et `installeur/` : aucune référence câblée à ces fichiers de
    cache — `data/dictionnaire/` (dictionnaires, définitions, caches,
    personnalisations) est déjà entièrement exclu du build PyInstaller et de
    l'installeur Inno Setup depuis l'issue #460 (dépôt public, licences
    floues) ; ce déplacement ne modifie donc aucun comportement de ces
    scripts.
