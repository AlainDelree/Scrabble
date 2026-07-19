# SMOKE_TEST.md — Checklist de test manuel

> **Objectif.** Ce document liste tous les flux à **vérifier manuellement** avant
> une « mise en production » : installation du jeu chez un tiers, ou après un gros
> changement touchant plusieurs fenêtres (accueil, jeu/plateau, chevalet, réglages).
>
> **Pourquoi.** Plusieurs régressions récentes (tirage d'ordre tronqué, modale du
> joker tronquée après le resserrage de la fenêtre chevalet) n'ont été détectées
> **qu'en jouant manuellement**, alors que les tests automatisés (dont les harnais
> Playwright headless) étaient au vert. Les tests headless tournent sous **Chromium**,
> mais le jeu s'exécute réellement sous **WebKitGTK** (pywebview) : les différences de
> rendu ne sont pas couvertes par l'automatisation. Les tests automatisés restent
> utiles, mais **ne remplacent pas** ce passage manuel.
>
> **Usage.** Copiez cette liste (ou cochez directement les cases `- [ ]`) et parcourez-la
> de bout en bout sur la vraie application. Une case non cochée = à revérifier.
>
> **À tenir à jour.** Ce fichier doit être complété **à chaque nouvelle fonctionnalité
> significative** ou modification d'un flux existant. Si vous ajoutez un bouton, une
> modale ou un écran, ajoutez la ligne correspondante ici dans le même commit.

---

## 1. Accueil / configuration de partie

### Composition de la table
- [ ] Ajouter un **joueur humain** (bouton « Ajouter un joueur ») : saisir un prénom, valider.
- [ ] Cocher « Toujours utiliser ce prénom » à l'ajout et vérifier qu'il est bien mémorisé (proposé par défaut ensuite).
- [ ] Annuler la modale d'ajout d'un joueur humain (bouton « Annuler ») : aucun joueur ajouté.
- [ ] Ajouter un **ordinateur niveau Débutant**.
- [ ] Ajouter un **ordinateur niveau Facile**.
- [ ] Ajouter un **ordinateur niveau Intermédiaire** (niveau sélectionné par défaut).
- [ ] Ajouter un **ordinateur niveau Expert**.
- [ ] **Retirer** un joueur (bouton ✕) : le joueur disparaît de la table.
- [ ] Le compteur « N humain(s), N ordinateur(s) » se met à jour correctement à chaque ajout/retrait.
- [ ] Le bouton « Lancer la partie » reste **désactivé** tant que la composition est insuffisante, puis s'active.

### Lancement et tirage d'ordre
- [ ] **Lancer une nouvelle partie** : le tirage d'ordre se déclenche (modale « Tirage de l'ordre de jeu »).
- [ ] Pour **chaque joueur humain**, secouer le sac puis **tirer une lettre** (bouton « Tirer une lettre »).
- [ ] Le bouton « Tirer une lettre » reste **toujours visible** même si le contenu de la modale déborde (corps scrollable, bouton épinglé — issues #82/#116).
- [ ] Une fois tous les tirages faits, l'**ordre de jeu** s'affiche et le bouton « Continuer » **s'active**.
- [ ] **Annuler** le tirage (bouton « Annuler ») : retour à l'accueil sans lancer la partie.
- [ ] **Continuer** : la fenêtre d'accueil se ferme et l'écran de jeu s'ouvre (avec la fenêtre chevalet).

### Reprise de partie
- [ ] **Reprendre une partie en cours** depuis la section « Reprendre une partie » (bouton « Reprendre ») : l'état de la partie est restauré.
- [ ] Si aucune partie n'est en cours, le message « Aucune partie en cours. » s'affiche.

### Réglages depuis l'accueil (bouton ⚙)
- [ ] **Ouvrir les réglages** (bouton ⚙ en haut de l'accueil).
- [ ] **Onglet Général** — changer le **prénom principal** (le changement est sauvegardé automatiquement à la perte de focus).
- [ ] **Onglet Général** — changer le **thème du plateau** (menu déroulant) : message « Changement sauvé automatiquement ».
- [ ] **Onglet Général** — changer la **source du dictionnaire** (prend effet à la prochaine partie).
- [ ] **Onglet Dictionnaire** — rechercher un **mot existant** : affichage du statut par source + définition si disponible.
- [ ] **Onglet Dictionnaire** — rechercher un **mot inexistant** : statut « Absent » sur les sources.
- [ ] **Onglet Dictionnaire** — **ajouter** un mot à une source (bouton « Ajouter ») puis vérifier son statut « Présent (ajouté manuellement) ».
- [ ] **Onglet Dictionnaire** — **retirer** un mot d'une source (bouton « Retirer ») puis vérifier le statut mis à jour.
- [ ] **Fermer les réglages** (bouton « Fermer » ou touche **Échap**) : retour à l'accueil.

---

## 2. Écran de jeu (plateau)

### Affichage
- [ ] Le **plateau 15×15** s'affiche correctement (cases bonus colorées, étoile centrale ★, tooltips des cases).
- [ ] Les **panneaux des joueurs** s'affichent aux **bonnes positions** autour du plateau (haut/gauche/droite/bas), avec avatar, nom, badge de niveau, score, nombre de lettres, badge ordinateur 🖥️.
- [ ] Le **badge de tour** (« ● à vous » / « ● son tour ») désigne le bon joueur courant.
- [ ] Le **sac de lettres** 🎒 affiche le nombre de jetons restants et se met à jour.

### Poser un coup (clic-clic depuis le chevalet)
- [ ] **Poser un mot valide** : sélectionner une lettre dans la fenêtre chevalet, cliquer une case vide du plateau, répéter, puis « ✓ Jouer » → coup accepté, score attribué.
- [ ] **Poser un mot invalide** : « ✓ Jouer » affiche un **message d'erreur clair** et ne joue pas le coup.
- [ ] **Retirer une lettre en attente** : recliquer sa case sur le plateau la remet au chevalet.
- [ ] **Annuler un coup en attente** (bouton « ✗ Annuler ») : toutes les lettres en attente reviennent au chevalet.
- [ ] Cliquer une **case déjà occupée** par une tuile validée : message d'erreur (pas de superposition).

### Joker
- [ ] **Utiliser un joker** : poser le joker sur une case → la **modale de choix de lettre** s'ouvre **dans la fenêtre chevalet** ; le message du plateau renvoie bien vers cette fenêtre.
- [ ] Choisir une lettre dans la modale joker : le joker est posé avec la lettre choisie (affichée, valeur 0).
- [ ] **Annuler** la modale joker : la pose du joker est abandonnée, les autres poses sont conservées.

### Vérification et calcul
- [ ] **« 🔎 Vérifier et calculer »** un coup en attente **sans le jouer** : message « Coup valide (MOT) : +N points » et ouverture du **détail du score** (mots formés, bonus, total).
- [ ] Sur un coup invalide, « Vérifier et calculer » renvoie un message d'erreur explicite.

### Ordinateur
- [ ] **Faire jouer l'ordinateur** (bouton « ▶ Faire jouer l'ordinateur » dans la zone d'attente) : l'IA joue **un** tour, l'animation de pose se déclenche.
- [ ] Vérifier le comportement pour **chaque niveau** présent dans la partie (Débutant / Facile / Intermédiaire / Expert), si possible.

### Échange
- [ ] **Échanger tout son chevalet** (bouton « ♻️ Remettre toutes ses lettres et passer ») : le chevalet est vidé dans le sac et le tour passe.

### Historique
- [ ] Ouvrir l'**historique** « 🕑 Derniers coups » (compteur à jour, coup le plus récent en haut).
- [ ] Ouvrir le **détail d'un coup** (clic sur une ligne cliquable) : modale de score détaillée.
- [ ] Une ligne « a passé » / « a échangé » (sans détail) affiche l'info sans planter.

### Vérification dictionnaire (loupe)
- [ ] Ouvrir le **popover de vérification dictionnaire** (bouton « 🔎 Vérification dictionnaire »).
- [ ] Vérifier un **mot présent** dans le dictionnaire : « ✓ … est dans le dictionnaire ».
- [ ] Vérifier un **mot absent** : « ✗ … n'est pas dans le dictionnaire ».

### Thème du plateau
- [ ] Après avoir changé le **thème du plateau** dans les Réglages, (re)lancer/afficher une partie et vérifier que l'habillage (couleurs / étiquettes des cases) est bien appliqué.
      _Note : le choix du thème se fait dans les Réglages, pas dans l'écran de jeu ; celui-ci se contente d'appliquer le thème configuré._

### Retour au menu et fermeture
- [ ] **« 🏠 Retour au menu » sans coup en attente** : retour immédiat à l'accueil (partie persistée).
- [ ] **« 🏠 Retour au menu » avec un coup en attente** : la **modale de confirmation** « Revenir au menu ? » s'affiche.
  - [ ] « Rester sur la partie » ferme la modale sans quitter.
  - [ ] « 🏠 Revenir au menu » confirme et retourne à l'accueil.
- [ ] **Fermer la fenêtre plateau par la croix** (contrôle natif de la fenêtre) : vérifier la **fermeture croisée** avec la fenêtre chevalet (les deux se ferment).
- [ ] **« ↻ Resynchroniser »** : recharge l'état du plateau sans incohérence.

### Fin de partie
- [ ] Terminer une partie (**sac épuisé** ou **chevalet vidé**) : le **bandeau de fin** « 🏁 Partie terminée — {gagnant(s)} » s'affiche.
- [ ] En cas de **Scrabble** (7 lettres posées, +50 pts) : la **célébration / feu d'artifice** (toast « 🎉 Scrabble !! » + particules) se déclenche.
      _Avec `prefers-reduced-motion`, seul le toast statique doit s'afficher, sans animation._

---

## 3. Fenêtre chevalet

- [ ] Le **panneau de lettres** est **toujours visible** (7 lettres + emplacements vides), y compris **pendant le tour d'un ordinateur**.
- [ ] **Sélectionner** une lettre (clic) : surbrillance ; recliquer la désélectionne.
- [ ] **Réarranger** librement les lettres (clic sur une case vide, échange de deux lettres) : purement local, sans effet sur la partie.
- [ ] **Clic droit** sur une lettre : elle est renvoyée vers un emplacement vide en fin de chevalet.
- [ ] Une lettre déjà posée en attente (grisée « utilisée ») n'est ni sélectionnable ni déplaçable.
- [ ] **Déplacer la fenêtre chevalet** en glissant la **barre du haut** (« 🎴 Mon chevalet ⠿ déplacer ») : la fenêtre suit le curseur.
- [ ] La fenêtre chevalet reste **au-dessus du plateau** (always-on-top)…
- [ ] …mais peut **passer sous d'autres applications** (elle n'est pas au-dessus de tout le système hors de l'app).
- [ ] Le chevalet reste réarrangeable **hors tour** (pas de blocage, pas de bascule voir/cacher).

---

## 4. Général — navigation et cycle de vie des fenêtres

- [ ] Naviguer **accueil ↔ jeu** (lancer une partie, revenir au menu) : transitions propres, pas de fenêtre bloquée.
- [ ] Naviguer **accueil ↔ réglages** (ouvrir puis fermer) : retour correct à l'accueil.
- [ ] **Lancer le jeu depuis zéro** (démarrage de l'application → accueil) : l'accueil s'affiche correctement.
- [ ] Faire **plusieurs allers-retours** entre les fenêtres (accueil → jeu → menu → jeu → réglages…) : vérifier qu'**aucune fenêtre ne reste bloquée ou orpheline** (pas de fenêtre chevalet fantôme, pas de plateau resté ouvert).
- [ ] Fermer l'application proprement : aucune fenêtre résiduelle.

---

_Dernière mise à jour : voir l'historique git de ce fichier. Complétez cette checklist à chaque nouvelle fonctionnalité significative._
