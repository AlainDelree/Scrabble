# Changelog — Issue #455

## Ajouté

- **Personnage Lettré : liste de mots complémentaire locale, hors git.**
  Alain peut maintenant ajouter des mots favoris au Lettré sans qu'ils
  soient publiés dans le dépôt.

  - **`data/personnages/lettre_mots_meral.txt`** (nouveau chemin, jamais
    créé dans le dépôt) : second fichier facultatif, un mot par ligne,
    mêmes règles de normalisation que `lettre_mots_favoris.txt` (accents et
    majuscules normalisés, lignes vides ignorées). Absent ou vide : aucune
    différence avec le comportement d'avant ce lot. Ajouté à `.gitignore`.

  - **`scrabble.moteur.personnages`** : nouvelle fonction
    `charger_mots_favoris_avec_complement(chemin, chemin_complement)`,
    réutilisant deux fois `charger_mots_favoris` existante (fichier absent
    -> ensemble vide pour cette moitié) puis union des deux résultats.
    `MOTS_FAVORIS_LETTRE` est désormais chargée avec cette fonction
    (`CHEMIN_MOTS_FAVORIS_LETTRE` + nouvelle constante
    `CHEMIN_MOTS_FAVORIS_LETTRE_MERAL`) ; le jeu utilise donc l'union des
    deux listes, sans doublon. Titeuf continue d'appeler
    `charger_mots_favoris` seule, comportement inchangé — la nouvelle
    fonction est disponible pour lui ou un futur personnage à liste s'il en
    a besoin plus tard.

  - **Indicateur de style du script de mesure**
    (`scripts/mesurer_force_niveaux.py`) : aucune modification nécessaire,
    il lit déjà `profil.mots_favoris` (qui porte désormais l'union) plutôt
    que la constante du fichier habituel directement.

  - **Tests** (`tests/test_moteur_personnages.py`,
    `TestMotsFavorisLettreComplement`) : fichier absent (résultat identique
    à `charger_mots_favoris` seule), fichier présent (mots pris en compte),
    union sans doublon, mot du complément absent du lexique ignoré sans
    filtrage dédié, et un scénario fabriqué où un mot présent seulement
    dans le fichier complémentaire est joué par le Lettré à Avancé/Expert/
    Champion du monde. Les tests existants de chargement de la liste réelle
    (`TestMotsFavorisLettre`) passent sans modification : le fichier
    complémentaire n'existe pas dans ce worktree isolé.
