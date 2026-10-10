# Changelog — Issue #449

## Ajouté

- **Personnages réservés aux parties à deux joueurs (lot I).** Tous les
  réglages et mesures des personnages ont été faits en parties à deux
  joueurs (humain contre un ordinateur) : rien n'a été vérifié à trois ou
  quatre joueurs. Les personnages sont donc réservés aux parties à deux
  joueurs pour cette première diffusion, levables personnage par personnage
  plus tard, sans se presser.
  - **`scrabble.moteur.personnages`** : nouveau champ facultatif
    `Personnage.nb_joueurs_disponibles` (`frozenset[int]`, défaut
    `TOUTES_TAILLES = {2, 3, 4}`), indépendant de `niveaux_disponibles`
    (les deux restrictions se combinent par ET logique). Opportuniste et
    Chasseur de scrabbles sont déclarés disponibles à deux joueurs
    seulement (`NB_JOUEURS_OPPORTUNISTE`/`NB_JOUEURS_CHASSEUR_SCRABBLES`).
    Nouvelles fonctions miroir de celles du lot G (niveaux) :
    `personnages_disponibles_a_nb_joueurs`, `aleatoire_disponible_a_nb_joueurs`,
    `personnage_disponible_a_nb_joueurs`, `libelle_tailles`,
    `libelle_tailles_aleatoire`, `explication_disponibilite_tailles`.
    « Aléatoire » suit une règle déduite comme pour les niveaux : disponible
    uniquement pour une taille où au moins deux personnages (hors lui-même)
    le sont — aujourd'hui disponible à deux joueurs, indisponible à trois ou
    quatre. `tirer_personnage` accepte désormais un paramètre `nb_joueurs`
    optionnel, combiné au niveau. `lister_personnages` expose un nouveau
    champ `tailles_label` par entrée.
  - **`scrabble.moteur.partie`** : `creer_partie` transmet la taille totale
    de la table à `tirer_personnage` pour qu'un tirage « Aléatoire » ne
    choisisse jamais un personnage indisponible à cette taille — comme pour
    le niveau, le moteur lui-même reste sans garde-fou (aucune vérification
    de disponibilité), seule l'UI contrôle en amont.
  - **`scrabble.ui.accueil`** : `obtenir_personnages()` expose `tailles_label`
    ; nouvelle méthode `obtenir_disponibilite_personnage_table()` (le
    sélecteur de personnage doit être désactivé dès que la table compte déjà
    un ordinateur, l'ajout d'un second faisant passer la table à trois
    joueurs ou plus — seul Classique y reste disponible dans le registre
    actuel). `ajouter_ordinateur()` refuse désormais un personnage non
    disponible pour la taille de table résultante (message dédié) et, si
    l'ajout fait passer la table à trois joueurs ou plus, remet
    automatiquement à Classique le personnage de tout ordinateur déjà
    présent (avec un avertissement nommant le joueur concerné, retiré ensuite
    sans être rétabli). `lancer_partie()` refuse de démarrer si un
    personnage assigné n'est plus disponible pour la taille de table finale
    (défense en profondeur).
  - **UI (accueil.html/js/css, commun.js, personnages.css)** : le sélecteur
    de personnage est désactivé avec une explication courte (« Les
    personnages sont réservés aux parties à deux joueurs. ») dès que la
    table comporte déjà un ordinateur ; les avertissements de remise à
    Classique sont affichés au joueur. La fenêtre « Les personnages »
    (accueil et jeu, composant partagé) affiche désormais aussi les tailles
    de table où chaque personnage est disponible, à côté des niveaux déjà
    affichés.
  - **Parties existantes et script de mesure inchangés** : aucune
    vérification de disponibilité n'a lieu au chargement d'une partie
    sauvegardée (une combinaison devenue indisponible continue de se jouer
    normalement) ; `scripts/mesurer_force_niveaux.py` continue de pouvoir
    forcer n'importe quelle combinaison, comme pour les niveaux.
  - Tests : `tests/test_moteur_personnages.py`, `tests/test_accueil.py`,
    `tests/test_accueil_niveaux_visuels.py`, `tests/test_moteur_partie.py`,
    `tests/test_persistance.py`.
