# Changelog — Issue #454

## Ajouté

- **Personnage Lettré, les mots rares au bonus de score (lot K, Avancé/Expert/
  Champion du monde).** Reprend exactement le mécanisme de Titeuf (lot J,
  issue #452) avec sa propre liste — des mots rares/littéraires plutôt que
  de cour de récré — et ajoute le levier qui manquait pour que le style se
  voie aux niveaux « meilleur coup » (Avancé, Champion du monde), où le
  tirage pondéré de Titeuf n'a par construction aucun effet.

  - **`data/personnages/lettre_mots_favoris.txt`** : liste de mots favoris
    fournie par Alain avant ce lot (2813 mots rares/littéraires croisés
    depuis Lexique 3 et l'ODS8), déjà présente et non vide au démarrage de
    ce lot — non reconstruite.

  - **`scrabble.moteur.ia`** : nouveau champ facultatif de
    `ProfilPersonnage`, `bonus_favori: int | None` (neutre par défaut,
    `None` traité comme 0). Généralise `bonus_scrabble` au critère de LISTE
    de `mots_favoris` : ajoute une constante au score stratégique
    (`_score_strategique`) des coups dont le mot principal est un mot
    favori — seul champ de ce module qui agit sur le score à TOUS les
    niveaux, y compris Avancé/Champion du monde (meilleur coup), puisqu'il
    intervient avant le tri plutôt qu'après comme `poids_tirage_favori`.
    Sans effet tant que `mots_favoris` est vide ou absent ; aucun impact sur
    Titeuf ni sur aucun autre personnage, qui ne renseignent pas ce champ.

  - **`scrabble.moteur.personnages`** : nouvelles constantes
    `BONUS_FAVORI_LETTRE = 40` (calcul détaillé dans le docstring du module
    et le rapport de l'issue, par analogie avec l'échelle de
    `_BONUS_PREMIUM`/`_MALUS_LONGUEUR` déjà en production — le dictionnaire
    réel n'étant pas disponible dans ce worktree isolé pour la mesurer par
    parties jouées), `CHEMIN_MOTS_FAVORIS_LETTRE`, `MOTS_FAVORIS_LETTRE`
    (chargée avec la même fonction `charger_mots_favoris` que Titeuf),
    `PRENOM_LETTRE = "Lettré"`, `NIVEAUX_LETTRE = {AVANCE, EXPERT,
    CHAMPION_DU_MONDE}` (provisoire, à ajuster par Alain après mesure),
    `NB_JOUEURS_LETTRE = {2}`. Nouvelle entrée `"lettre"` dans le registre
    `PERSONNAGES`, sans tirage pondéré (`poids_tirage_favori` non
    renseigné) : le bonus de score suffit sur les niveaux où ce personnage
    est disponible.

  - **Conséquence attendue (règle déjà en place, lot G) :** Avancé, Expert
    et Champion du monde comptaient déjà au moins deux personnages réels —
    aucun changement de disponibilité d'Aléatoire à ces niveaux, qui couvre
    simplement un personnage de plus.

  - **`scripts/mesurer_force_niveaux.py`** : nouvel exemple de commande
    documenté (Lettré contre Classique à Avancé/Expert/Champion du monde,
    200 parties chacune, avec tableau de style) ; l'indicateur de style
    « Coups dont le mot principal est un mot favori » (ajouté par le lot J)
    était déjà générique — aucun changement de code requis, il lit la liste
    propre à chaque joueur via son profil résolu.

  - **Tests** (`tests/test_moteur_ia.py`, `tests/test_moteur_personnages.py`,
    `tests/test_moteur_partie.py`, `tests/test_mesurer_force_niveaux_style.py`,
    `tests/test_persistance.py`) : neutralité du nouveau champ (`bonus_favori`
    absent de tout autre personnage, y compris Titeuf), application du bonus
    à tous les niveaux, nécessité du bonus démontrée sur un scénario fabriqué
    (sans lui, le mot favori perd quand même, malgré l'élargissement des
    coups candidats), choix du mot favori nettement plus fréquent que
    Classique à Avancé/Expert/Champion du monde (niveaux « meilleur coup »),
    mot favori hors vocabulaire du niveau accessible, mot absent du lexique
    ignoré sans erreur, liste indépendante de celle de Titeuf, disponibilité
    (niveaux + deux joueurs), tirage Aléatoire couvrant Lettré à Avancé,
    reprise d'une partie sauvegardée avec un Lettré, indicateur de style
    utilisant bien la liste du Lettré (nouvelle partie type sans coup
    jouable, comme pour Titeuf).

    Un test existant, qui encodait explicitement la liste exacte des
    personnages tirables par Aléatoire à Avancé à deux joueurs
    (`test_creer_partie_aleatoire_peut_tirer_opportuniste_a_deux_joueurs`),
    est mis à jour pour inclure `"lettre"` — cas prévu par les contraintes de
    l'issue. Deux échecs préexistants (calibrage `part_vocabulaire_court` du
    Chasseur de scrabbles, issue antérieure à ce lot, confirmé par
    `git stash`) et cinq autres échecs préexistants variant selon le dossier
    de travail (non liés aux personnages) sont laissés de côté, comme
    convenu.
