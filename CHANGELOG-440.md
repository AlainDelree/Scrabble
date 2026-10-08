# Changelog — Issue #440

## Ajouté

- **Personnages IA, lot D : choix à l'accueil, personnage Aléatoire et
  révélation en fin de partie.** Le registre de personnages (lot B) devient
  utilisable en jeu.
  - **Accueil** (`accueil.html`/`.css`/`.js`) : nouveau sélecteur de
    personnage (`<select>`), à côté de la rangée de boutons de niveau,
    construit dynamiquement depuis `ApiAccueil.obtenir_personnages()` — un
    choix par entrée de `PERSONNAGES`, puis « Aléatoire » toujours en
    dernier (un personnage ajouté plus tard au registre s'y insère sans
    autre modification). Sélectionner une option affiche sa description
    sous le menu (texte de mystère pour « Aléatoire », sans rien révéler).
    Le choix du sélecteur s'applique au prochain ordinateur ajouté par clic
    sur un bouton de niveau, exactement comme le niveau lui-même. Défaut :
    Classique (comportement inchangé pour qui ne touche à rien).
  - `ApiAccueil.ajouter_ordinateur(niveau_label, personnage_cle="classique")` :
    3ᵉ paramètre optionnel, rétro-compatible (tout appel existant à un seul
    argument continue de fonctionner à l'identique). Un personnage précis
    donne son prénom à l'ordinateur ; « Aléatoire » tire un prénom banal du
    pool habituel (`noms_ordinateur.tirer_prenoms`) pour ne rien trahir
    pendant la partie — la résolution réelle n'a lieu qu'au lancement.
  - **Prénoms en double (point 2 de l'issue)** : solution retenue, un
    suffixe numérique croissant (`_nom_sans_doublon`) — « Opportuniste »,
    puis « Opportuniste 2 » si un second ordinateur choisit le même
    personnage. Comparaison insensible à la casse/espaces, symétrique à
    `tirer_prenoms`.
  - **Tirage « Aléatoire »** : `creer_partie()` gagne `personnages_ia`
    (clé par IA, dont `CLE_ALEATOIRE`) et `generateur_aleatoire`
    (`random.Random` injectable, pour un tirage déterministe en test).
    Le tirage a lieu **une seule fois**, à la création, uniformément parmi
    *tout* `PERSONNAGES` (Classique compris, via la nouvelle
    `personnages.tirer_personnage()`) ; l'identité enregistrée dans
    `Joueur.personnage` est toujours la clé réelle tirée, jamais le libellé
    « Aléatoire ». Nouveau champ `Joueur.personnage_aleatoire: bool` qui
    mémorise si ce personnage vient d'un tirage (pour la révélation) —
    sérialisé/désérialisé en base symétriquement à `personnage`, avec
    repli `False` sur une sauvegarde d'avant ce lot.
  - **Révélation en fin de partie** : `scrabble.ui.jeu.revelations_personnages`
    (nouveau), exposée dans `etat_public()` sous `revelations_personnages` —
    liste vide tant que la partie n'est pas terminée (ne fuite jamais en
    cours de partie, l'état public étant diffusé en continu), puis une
    entrée `{nom, personnage_prenom, personnage_description}` par
    ordinateur dont le personnage avait été tiré au hasard. Rendu dans la
    modale de fin de partie (`jeu.html`/`.js`/`.css`, bloc
    `#modale-fin-revelations`), sous l'évaluation du score.
  - **Le personnage influence désormais réellement le jeu** : `jeu.py`
    résout le `ProfilPersonnage` du personnage courant
    (`_profil_joueur_ia`) et le transmet à `Partie.jouer_tour_ia(profil)`
    (paramètre déjà prévu par le lot A, jamais câblé jusqu'ici) — seul le
    point d'appel change, ni `ia.py` ni les réglages par niveau ne sont
    touchés. Un personnage vide ou une clé devenue inconnue retombent sur
    `None` (comportement identique à avant ce lot).
  - **Reprise de partie** : fonctionne sans changement supplémentaire —
    `stockage._reconstruire_joueurs` restaure `personnage`/
    `personnage_aleatoire` tels que sauvegardés ; une partie « Aléatoire »
    reprise avant sa fin garde son identité cachée (le champ stocké est déjà
    la clé réelle, mais `personnage_aleatoire` reste vrai jusqu'à la fin).
  - `recreer_partie_meme_joueurs` (action « Recommencer ») repropage le
    personnage de chaque IA au même titre que son niveau — pas de nouveau
    tirage, même pour un personnage obtenu par « Aléatoire » dans la partie
    d'origine : un « Recommencer » garde le même style de jeu.
  - Journal (`ApiAccueil.ajouter_ordinateur`) : la ligne existante
    (« Accueil : ordinateur ajouté (nom, niveau N) ») gagne en bout de
    phrase le personnage choisi, de façon additive — format existant
    inchangé.

## Tests

- `tests/test_moteur_personnages.py` : `TestTirerPersonnage` (tirage
  déterministe avec générateur injecté, toujours une entrée du registre,
  Classique non exclu, fonctionne sans générateur explicite).
- `tests/test_moteur_partie.py` : `creer_partie` sans `personnages_ia`
  (non-régression), avec personnage explicite, avec `"aleatoire"`
  (identité réelle jamais `"aleatoire"`, déterminisme à générateur égal,
  couverture de tout le registre sur 50 graines) ; `recreer_partie_meme_joueurs`
  conserve le personnage de chaque IA.
- `tests/test_persistance.py` : aller-retour de `personnage_aleatoire`
  (défaut `False`, round-trip `True`, ancienne sauvegarde sans la clé).
- `tests/test_accueil.py` : `obtenir_personnages()` (registre + Aléatoire en
  dernier) ; défaut Classique rétro-compatible (API et `ConfigPartie`) ;
  personnage explicite → prénom du personnage ; personnage inconnu refusé ;
  deux ordinateurs même personnage → prénoms non dupliqués ; « Aléatoire » →
  prénom banal, personnage non résolu avant `lancer_partie` ; `lancer_partie`
  résout « Aléatoire » en identité réelle marquée `personnage_aleatoire=True`,
  un personnage explicite n'est jamais marqué ainsi.
- `tests/test_jeu_personnages.py` (nouveau) : `revelations_personnages`
  (vide en cours de partie, vide pour un personnage choisi explicitement ou
  absent, peuplée pour un tirage Aléatoire en fin de partie, jamais pour un
  humain) ; exposition dans `etat_public` ; `_profil_joueur_ia` (vide,
  clé inconnue, Classique, Opportuniste) ; câblage effectif dans
  `jouer_tours_ia_ui` (le profil résolu atteint `choisir_coup`, non-régression
  sans personnage).

### Suite complète

**926 tests avant ce lot (921 verts, 5 échecs préexistants confirmés par
`git stash` — dictionnaire/accueil/application/journal, sans rapport avec ce
lot), 962 après (957 verts, les 5 mêmes échecs inchangés).**

## Solution retenue pour les prénoms en double

Suffixe numérique croissant (« Opportuniste », « Opportuniste 2»…),
comparaison insensible à la casse/espaces. Alternative écartée : retomber
sur un prénom générique du pool habituel aurait masqué le personnage choisi
dans la liste des joueurs, ce qui semblait moins transparent pour le joueur
qui compose sa table.

## À vérifier à la main par Alain (interface graphique, CCL ne peut pas la lancer)

1. **Sélecteur de personnage à l'accueil** : présent à côté des boutons de
   niveau, Classique sélectionné par défaut, Opportuniste puis Aléatoire
   disponibles, Aléatoire bien en dernière position.
2. **Description affichée** : changer la sélection met à jour le texte sous
   le menu (description réelle pour Classique/Opportuniste, texte de
   mystère pour Aléatoire, sans rien révéler).
3. **Ajout d'un ordinateur avec un personnage précis** : le prénom affiché
   dans « Joueurs autour de la table » est celui du personnage (p. ex.
   « Opportuniste ») ; un second ordinateur sur le même personnage obtient
   « Opportuniste 2 ».
4. **Partie avec Aléatoire** : lancer une partie avec un ordinateur en
   Aléatoire — son prénom affiché pendant la partie est un prénom banal
   (pas « Aléatoire », pas le nom d'un personnage).
5. **Écran de résultat** : en fin de partie, un bloc dédié révèle qui
   était vraiment l'ordinateur tiré au hasard (prénom du personnage +
   description) ; aucun bloc (ou vide) si aucun ordinateur n'était en
   Aléatoire.
6. **Reprise d'une partie sauvegardée** : reprendre une partie avec un
   personnage précis le conserve ; reprendre une partie Aléatoire non
   terminée garde l'identité cachée jusqu'à la fin de cette partie reprise.

## Contraintes respectées

- Moteur d'IA (`ia.py`), réglages par niveau et valeurs des personnages non
  modifiés : seul le point d'appel de `Partie.jouer_tour_ia` (déjà prévu
  pour recevoir un profil) a changé, dans `ui/jeu.py`.
- Aucun nouveau personnage, avatar ou image ; aucun changement de
  personnalité en cours de partie.
- Tests existants non modifiés (sauf la docstring-index de
  `tests/test_jeu.py`, garde-fou de `test_jeu_docstring.py`, mise à jour
  pour lister le nouveau fichier de tests — aucune assertion existante
  changée).
- Pas de push : commits locaux uniquement dans ce worktree.
