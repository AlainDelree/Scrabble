# Changelog — Issue #441

## Modifié

- **Personnages IA, lot D bis : prénoms aléatoires conservés, personnage
  affiché entre parenthèses.** Revient sur le choix du lot D (#440) qui
  faisait porter à l'ordinateur le prénom de son personnage (« Opportuniste »,
  « Opportuniste 2 ») : le prénom redevient un tirage banal dans la liste
  habituelle, et le personnage s'affiche à côté, entre parenthèses.
  - **Prénoms** (`ui/accueil.py`) : `ApiAccueil.ajouter_ordinateur()` tire
    toujours le prénom via `noms_ordinateur.tirer_prenoms()`, quel que soit
    le personnage choisi — fini la branche qui donnait le prénom du
    personnage. Suppression de `_nom_sans_doublon()` (plus de raison d'être :
    `tirer_prenoms()` exclut déjà les prénoms pris à la table, donc deux
    ordinateurs sur le même personnage ont toujours des prénoms distincts,
    sans suffixe numérique).
  - **Libellé entre parenthèses** (`moteur/personnages.py`) : deux nouvelles
    fonctions pures, réutilisées par l'accueil et l'écran de jeu.
    - `libelle_choix_accueil(personnage_cle)` — pour la clé **non résolue**
      du sélecteur de l'accueil (peut être `CLE_ALEATOIRE`) : chaîne vide
      pour Classique (ou l'absence de personnage), « Aléatoire » pour
      `CLE_ALEATOIRE`, sinon le prénom du personnage choisi.
    - `libelle_personnage_partie(personnage_cle, personnage_aleatoire,
      reveler=False)` — pour l'identité **réelle** d'un `Joueur` en partie :
      chaîne vide pour Classique choisi explicitement, le prénom du
      personnage sinon ; pour un tirage « Aléatoire »
      (`personnage_aleatoire=True`), reste « Aléatoire » tant que
      `reveler` est faux (pendant toute la partie), puis devient
      « Aléatoire : `<Personnage>` » une fois révélé — Classique compris,
      jamais le prénom seul (pour ne pas laisser croire à un défaut
      d'affichage).
  - **Accueil** (`ui/accueil.py`, `web/accueil.js`) :
    `ApiAccueil.obtenir_etat()` expose un nouveau champ
    `joueurs[i].personnage_libelle` (calculé via `libelle_choix_accueil`),
    affiché par le JS après le prénom, entre parenthèses
    (`Commun.nomAvecPersonnage`).
  - **Écran de jeu** (`ui/jeu.py`, `web/jeu.js`) :
    `serialiser_joueur_public()` gagne un paramètre `reveler_personnage`
    (`partie.terminee`, câblé depuis `etat_public()`) et un champ de
    réponse `personnage_libelle` (via `libelle_personnage_partie`). Le champ
    `nom` lui-même reste inchangé — seul l'affichage ajoute le personnage ;
    aucun effet sur l'historique des coups ni les sauvegardes. Le JS utilise
    ce libellé dans les trois affichages du prénom d'un ordinateur : le
    panneau joueur pendant la partie, le tableau de classement final et le
    message de victoire de la modale de fin de partie (tous les trois via
    la fonction partagée `Commun.nomAvecPersonnage`, ajoutée à `commun.js`).
  - **Sélecteur de personnage** (`web/accueil.html`) : libellé changé en
    « Personnage du prochain ordinateur : » (au lieu de « Personnage : »),
    pour que son rôle soit clair — aucun changement d'emplacement ni de
    comportement.
  - Le bloc de révélation dédié de la modale de fin de partie
    (« 🎭 Personnages Aléatoire dévoilés », `revelations_personnages()`)
    est conservé tel quel : il reste la source de la description complète
    du personnage révélé, en complément du libellé compact désormais affiché
    inline à côté du prénom.

## Tests

- `tests/test_moteur_personnages.py` : nouvelles classes
  `TestLibelleChoixAccueil` et `TestLibellePersonnagePartie` couvrant les
  deux fonctions de libellé (Classique, personnage explicite, Aléatoire
  non révélé, Aléatoire révélé pour chaque personnage du registre, Classique
  compris).
- `tests/test_accueil.py` :
  - `test_ajouter_ordinateur_personnage_explicite_porte_son_prenom` →
    renommé `..._porte_un_prenom_tire_au_hasard`, vérifie désormais que le
    prénom vient de `PRENOMS_ORDINATEUR`, indépendamment du personnage.
  - `test_ajouter_deux_ordinateurs_meme_personnage_noms_non_dupliques` →
    renommé `..._prenoms_distincts`, vérifie l'absence de suffixe numérique.
  - Nouvelle classe `TestObtenirEtatPersonnageLibelle` (Classique, personnage
    explicite, Aléatoire, joueur humain).
  - Deux assertions de forme exacte de `obtenir_etat()["joueurs"]`
    (`TestApiAccueilJoueurHumainParDefaut`, `TestApiAccueilAvatarPrincipal`)
    mises à jour avec le nouveau champ `personnage_libelle`.
- `tests/test_jeu_personnages.py` : nouvelle classe
  `TestPersonnageLibelleAffichage` (Classique, sans personnage, personnage
  explicite, Aléatoire pendant la partie, Aléatoire révélé pour chaque
  personnage du registre, personnage explicite jamais révélé, joueur humain).
- `tests/test_journal_integration.py` :
  `test_ouverture_accueil_place_le_joueur_humain_par_defaut` mise à jour
  (même raison que ci-dessus : forme exacte de `obtenir_etat()["joueurs"]`).
- Aucune modification des tests de persistance (`test_persistance.py`) ni du
  reste de `test_jeu_personnages.py` (révélation, `_profil_joueur_ia`,
  câblage IA) : comportement inchangé, déjà couvert par le lot D.
- Suite complète avant ces modifications : 957 passés / 5 échecs
  préexistants (confirmés par `git stash`, indépendants de cette issue —
  `test_infos_tirage_memorisees`, deux tests de `test_application.py`, deux
  de `test_journal_integration.py`). Après : 978 passés / 5 échecs, la même
  liste préexistante inchangée.

## Non traité

- L'écran de tirage d'ordre en début de partie (`detail_tirage_ordre`,
  liste « X a tiré la lettre Y ») n'affiche pas le personnage : ce n'est pas
  l'un des quatre emplacements listés par l'issue (accueil, tableau des
  scores, écran de jeu, écran de résultat), et son alimentation
  (`noms_creation`, simple liste de prénoms) est distincte de
  `etat_public()`. Laissé tel quel par prudence de périmètre.
