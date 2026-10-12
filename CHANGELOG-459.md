# Changelog — Issue #459

## Modifié

- **Personnages IA : désactivation de Chasseur de scrabbles et Lettré, code
  conservé pour une réactivation éventuelle.** Après mesure
  (`scripts/mesurer_force_niveaux.py`, parties réellement jouées), l'effet
  des deux personnages est trop discret pour être remarqué en jeu : environ
  0,45 scrabble supplémentaire par partie à Avancé et 0,2 à Intermédiaire
  pour Chasseur de scrabbles, environ deux mots de sa liste par partie pour
  Lettré (mesures du 12 octobre 2026). Alain abandonne les deux — rien n'est
  supprimé (code, constantes de réglage, listes de mots, tests de
  comportement), pour une réactivation éventuelle si une meilleure idée de
  calibrage apparaît. Les personnages qui restent proposés sont Classique,
  Opportuniste, Titeuf et Aléatoire.

  - **`scrabble/moteur/personnages.py`** : nouveau champ facultatif
    `Personnage.actif` (vrai par défaut). Les entrées `"chasseur_de_scrabbles"`
    et `"lettre"` du registre déclarent `actif=False`, avec un commentaire
    donnant la raison et la procédure de réactivation (repasser à `True`).
    `tirer_personnage`, `personnages_disponibles_a_niveau`,
    `personnages_disponibles_a_nb_joueurs` et `lister_personnages` (fenêtre
    « Les personnages ») n'incluent plus désormais que les personnages
    actifs — donc aussi `aleatoire_disponible_a_niveau`/
    `aleatoire_disponible_a_nb_joueurs`, qui ne comptent plus que les
    personnages actifs. Nouvelle fonction `personnage_actif(cle)`. L'accès
    direct par clé (`obtenir_personnage`, `profil_pour_niveau`,
    `PERSONNAGES[cle]`) reste inchangé : un personnage inactif demeure une
    entrée normale du registre, résolue à l'identique — une partie
    sauvegardée qui le mentionne continue de se charger et de se jouer sans
    aucun changement de comportement, et le script de mesure peut toujours
    le forcer explicitement. Docstring du module mise à jour (nouvelle
    section « Désactivation de Chasseur de scrabbles et Lettré »).

  - **`scrabble/ui/accueil.py`** : `ApiAccueil.obtenir_personnages` (sélecteur
    de l'accueil, et fenêtre « Les personnages » à l'accueil qui réutilise
    cette même méthode) n'inclut plus que les personnages actifs.
    `ApiAccueil.ajouter_ordinateur` refuse désormais l'ajout d'un ordinateur
    sur un personnage inactif, avec un message dédié nommant le personnage
    (« <Personnage> n'est pas disponible actuellement. »), contrôle qui
    précède celui de niveau/taille de table.

  - Aléatoire reste disponible à Débutant (Classique + Titeuf) et de Facile
    à Champion du monde (Classique + Opportuniste), à deux joueurs — exactement
    comme avant cette désactivation, Chasseur de scrabbles et Lettré n'ayant
    jamais été les seuls personnages supplémentaires à ces niveaux — et
    indisponible aux autres tailles de table (seul Classique y figure).

  - **Tests adaptés** (`tests/test_moteur_personnages.py`,
    `tests/test_jeu_personnages.py`, `tests/test_accueil.py`,
    `tests/test_moteur_partie.py`) : les tests qui supposaient la présence des
    deux personnages dans le sélecteur, la liste affichée, le tirage
    d'Aléatoire ou la disponibilité par niveau/taille sont mis à jour pour
    refléter leur exclusion (ou, pour un test de pur contrôle de taille de
    table sans rapport avec cette désactivation, réactivés localement via
    `monkeypatch.setitem` le temps du test). Nouveaux tests couvrant
    explicitement l'issue #459 : absence des deux personnages de toute liste
    proposée à tous les niveaux, jamais tirés par Aléatoire sur de
    nombreuses graines, refus de l'ajout avec message clair, résolution de
    profil inchangée pour un personnage inactif (partie sauvegardée jouable
    normalement), et réactivation de l'indicateur dans un test (sans
    modifier le code) qui remet le personnage dans le sélecteur et dans le
    tirage. Aucun test de comportement du Chasseur de scrabbles ou du Lettré
    n'est supprimé.

  Comportement de Classique, Opportuniste, Titeuf et du moteur d'IA
  inchangé. 1360 tests au total : 1355 verts avant ce lot (5 échecs
  préexistants, sans rapport, confirmés par `git stash` :
  `test_accueil::test_infos_tirage_memorisees`, deux dans
  `test_application.py`, deux dans `test_journal_integration.py`) ; après
  adaptation, même compte de tests verts plus les nouveaux (voir le rapport
  de clôture pour le détail), les 5 mêmes échecs préexistants subsistant
  seuls.
