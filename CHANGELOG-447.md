# Changelog — Issue #447

## Ajouté

- **Disponibilité des personnages IA selon le niveau de l'adversaire (lot
  G).** Un personnage n'a de sens qu'aux niveaux où son style se voit
  réellement (les mesures du lot B/C montrent qu'à Débutant, Opportuniste
  joue sur case bonus à peine plus souvent que Classique, 20,5 % contre
  20,1 % — son caractère n'y est pas perceptible). Règle générale : le jeu
  empêche désormais de choisir une combinaison personnage/niveau non
  disponible.
  - **`scrabble.moteur.personnages`** : nouveau champ facultatif
    `Personnage.niveaux_disponibles` (`frozenset[Niveau]`, défaut
    `TOUS_NIVEAUX` — un futur personnage sans déclaration reste disponible
    partout, comme Classique). Opportuniste déclare
    `NIVEAUX_OPPORTUNISTE` = tous les niveaux sauf Débutant.
  - Nouvelles fonctions : `personnages_disponibles_a_niveau`,
    `aleatoire_disponible_a_niveau` (Aléatoire n'a de sens qu'avec au moins
    deux personnages réels disponibles à ce niveau — règle **déduite**
    automatiquement des déclarations, sans qu'Aléatoire déclare quoi que ce
    soit : aujourd'hui indisponible à Débutant, seul Classique y figurant),
    `personnage_disponible_a_niveau`, `libelle_niveaux`/
    `libelle_niveaux_aleatoire` (texte « Tous les niveaux » ou « Facile à
    Champion du monde »), `explication_disponibilite_niveaux` (texte court,
    p. ex. « Disponible à partir de Facile », ou le message dédié
    d'Aléatoire).
  - `tirer_personnage` accepte désormais un `niveau` optionnel qui restreint
    le tirage aux personnages disponibles à ce niveau (défaut `None` :
    comportement historique inchangé, tout le registre). `creer_partie`
    (`scrabble.moteur.partie`) le lui transmet pour le niveau de l'IA
    concernée — le tirage reste fait une seule fois à la création de la
    partie, déterministe et injectable, identité réelle enregistrée comme
    avant. `creer_partie` lui-même ne vérifie aucune disponibilité (ni
    moteur ni IA modifiés) : le script `mesurer_force_niveaux.py` peut
    continuer à forcer n'importe quelle combinaison.
  - **`scrabble.ui.accueil.ApiAccueil`** : `ajouter_ordinateur` refuse
    désormais une combinaison personnage/niveau non disponible (message
    nommant le personnage et le niveau), défense en profondeur en plus du
    grisage côté accueil — un appel sans personnage (défaut Classique)
    continue de fonctionner sans changement. Nouvelle méthode
    `obtenir_disponibilite_niveaux_personnage(personnage_cle)` (disponibilité
    par niveau + courte explication), distincte du contrôle déjà existant
    sur le vocabulaire IA (`obtenir_disponibilite_niveaux`, combiné côté JS).
    `obtenir_personnages` et `scrabble.moteur.personnages.lister_personnages`
    exposent désormais `niveaux_label` par personnage (et pour Aléatoire),
    pour l'affichage dans « Les personnages » (accueil et jeu, même
    présentation — contrôleur commun dans `commun.js`).
  - Accueil (`accueil.html`/`.js`/`.css`) : les boutons de niveau où le
    personnage sélectionné n'est pas disponible sont réellement désactivés
    et grisés, avec l'explication affichée sous le sélecteur — mise à jour
    immédiate à chaque changement de personnage. Tous les boutons restent
    actifs pour Classique. Distinct du grisage (non désactivant) déjà
    existant pour le vocabulaire IA indisponible : les deux signaux se
    combinent par bouton.
  - Aucune vérification de disponibilité au chargement d'une partie
    sauvegardée (`reprendre_partie`) : une combinaison devenue indisponible
    se recharge et se joue normalement.

## Tests

- `tests/test_moteur_personnages.py` : disponibilité par défaut
  (`TOUS_NIVEAUX`), Opportuniste refusé à Débutant et accepté de Facile à
  Champion, Aléatoire indisponible à Débutant et disponible dès qu'un second
  personnage y est ajouté (registre patché en test), tirage restreint au
  niveau, libellés/explications.
- `tests/test_accueil.py` : refus serveur (message) pour Opportuniste et
  Aléatoire à Débutant, acceptation de Facile à Champion, appel sans
  personnage inchangé, `obtenir_disponibilite_niveaux_personnage`.
- `tests/test_moteur_partie.py` : tirage Aléatoire restreint au niveau de
  l'IA concernée dans `creer_partie`.
- `tests/test_persistance.py` : chargement d'une partie sauvegardée avec une
  combinaison aujourd'hui non disponible (Opportuniste à Débutant).
- `tests/test_accueil_niveaux_visuels.py` : câblage JS/HTML/CSS du grisage
  par personnage et de l'affichage des niveaux dans « Les personnages ».
- Deux tests existants qui vérifiaient l'exact des clés renvoyées par
  `lister_personnages`/`obtenir_personnages` (`{"cle", "prenom",
  "description", "dans_la_partie"}` / sans `dans_la_partie`) ont été mis à
  jour pour inclure le nouveau champ `niveaux_label` — changement structurel
  nécessaire au point 5 de l'issue, pas une régression de comportement.
