# SMOKE_TEST.md — Checklist de test manuel

> **Objectif.** Ce document liste tous les flux à **vérifier manuellement** avant
> une « mise en production » : installation du jeu chez un tiers, ou après un gros
> changement touchant les écrans de l'application (accueil, jeu, réglages).
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
- [ ] **Continuer** : l'écran de jeu s'ouvre (plateau + panneau chevalet intégré en zone C, une seule fenêtre).

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
- [ ] **Poser un mot valide** : sélectionner une lettre dans le panneau chevalet, cliquer une case vide du plateau, répéter, puis « ✓ Jouer » → coup accepté, score attribué.
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
- [ ] Vérifier le comportement pour **chaque niveau** présent dans la partie (Débutant / Facile / Intermédiaire / Avancé / Expert), si possible.

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

## 5. Coquille unifiée (mono-fenêtre) — vérification AVANT bascule de `main.py` (issue #182)

> **Statut.** La coquille unifiée (`lancer_application_unifiee`, une seule fenêtre
> physique + un chevalet compagnon persistant, une seule boucle `webview.start()`)
> **n'est PAS branchée par défaut** : `main.py` utilise toujours
> `lancer_accueil`/`lancer_jeu`. Cette section liste ce qu'Alain doit vérifier
> **visuellement, sur son poste (WebKitGTK réel)**, avant toute décision de
> basculer `main.py`. Les tests automatisés sont headless et **ne peuvent pas**
> garantir l'absence de flash de fenêtre, le bon repositionnement du chevalet, ni
> — point le plus sensible — qu'aucun processus ne reste actif après fermeture.

### Comment lancer la coquille unifiée pour ce test (sans toucher à la production)

Depuis la racine du dépôt (`src` sur le `PYTHONPATH`, comme en test) :

```bash
PYTHONPATH=src python -m scrabble.ui.application
```

C'est le **seul** moyen d'activer la coquille unifiée à ce stade ; `main.py`
reste inchangé.

### Transitions (aucun flash de fenêtre, une seule fenêtre physique)

- [ ] **Accueil → Jeu (nouvelle partie)** : « Lancer la partie » → l'écran de jeu apparaît **dans la même fenêtre** (pas de fermeture/réouverture, pas de flash blanc/vert).
- [ ] **Accueil → Jeu (reprise)** : « Reprendre une partie » → même fenêtre, plateau directement jouable (pas d'écran de tirage).
- [ ] **Tirage d'ordre** : pour une nouvelle partie, l'écran de tirage s'affiche, puis « Continuer » **révèle le chevalet** et bascule sur le plateau, sans clignotement.
- [ ] **Jeu → Accueil (Retour au menu)** : « 🏠 Retour au menu » → l'accueil réapparaît dans la même fenêtre, le **chevalet disparaît** (masqué, pas détruit).
- [ ] **Jeu → Jeu (Recommencer)** : « Recommencer » (modale de fin) → nouvelle partie, nouvel écran de tirage, chevalet remis en place ensuite.
- [ ] **Annuler le tirage** : bouton « Annuler » de l'écran de tirage → retour à l'accueil, la partie annulée **n'apparaît pas** dans « Reprendre une partie ».
- [ ] Enchaîner **plusieurs allers-retours** (accueil → jeu → menu → jeu → recommencer → menu…) : aucune latence croissante, aucune fenêtre fantôme.

### Chevalet compagnon (positionnement après CHAQUE transition)

- [ ] Après **chaque** entrée en jeu, le chevalet est **bien positionné** (bas-centre) et **lié au plateau** (au-dessus de lui, suit le plateau).
- [ ] Le chevalet reste **masqué** en vue Accueil et **pendant un tirage d'ordre** (jamais visible hors du jeu jouable).
- [ ] Le chevalet **réapparaît correctement** (bonnes lettres, bon endroit) à la reprise/au recommencement, sans rester coincé à un ancien emplacement.

### ⚠️ Fermeture par la croix ✕ — POINT CRITIQUE (risque de processus fantôme)

> Mal câblé, ce point pourrait laisser un **processus tourner indéfiniment en
> arrière-plan**. À vérifier avec un terminal ouvert en parallèle.

- [ ] Fermer par le **✕ de la fenêtre principale pendant que le JEU est actif** : les **deux** fenêtres (principale + chevalet) disparaissent, l'application quitte.
- [ ] Fermer par le **✕ de la fenêtre principale pendant que l'ACCUEIL est actif** (chevalet masqué) : l'application quitte quand même **entièrement** (le chevalet masqué ne doit pas survivre).
- [ ] Si la barre/croix du **chevalet** est atteignable : la fermer détruit **aussi** la fenêtre principale et quitte.
- [ ] **VÉRIFICATION PROCESSUS** — après CHACUNE des fermetures ci-dessus, contrôler dans un terminal qu'**aucun** processus ne reste :

  ```bash
  ps aux | grep -i "scrabble\|python -m scrabble.ui.application" | grep -v grep
  ```

  La commande ne doit **rien** afficher. Si un processus subsiste → **ne pas basculer `main.py`** et le signaler.

- [ ] Fermer par ✕ **avec un coup en attente** (lettres posées non validées) : la croix ferme **sans** blocage ni boîte de confirmation implicite (la confirmation ne concerne QUE le bouton applicatif « Retour au menu »).

### Décision de bascule

- [ ] Toutes les cases ci-dessus cochées **ET** aucun processus résiduel constaté sur plusieurs fermetures consécutives → la bascule de `main.py` vers `lancer_application_unifiee` peut être envisagée dans une issue dédiée.

---

_Dernière mise à jour : voir l'historique git de ce fichier. Complétez cette checklist à chaque nouvelle fonctionnalité significative._
