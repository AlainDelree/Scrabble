# Changelog — Issue #480

## Modifié

- **`jeu.css`/`jeu.js`/`jeu.html` : en portrait étroit, les messages de coup
  ne recouvrent plus le chevalet et la fenêtre de détail du score reçoit une
  croix de fermeture.** Suite de l'issue #478 : le chevalet s'y trouve
  désormais juste au-dessus de la zone d'actions humaine, et le message
  `#message-coup` (erreur de pose, erreur ou résultat de « Vérifier et
  calculer »…), ancré en surimpression au-dessus de cette zone et sans
  minuteur pour les erreurs, en recouvrait le bas des lettres — rendant leur
  sélection difficile pour corriger un mot refusé. Tout confiné au palier
  `@media (max-width: 480px)` (point 1/2) et au palier `@media (max-width:
  880px)` pour la croix de la modale de score (point 3) ; aucun changement
  au-dessus (vérifié par capture AVANT/APRÈS strictement identique —
  différence de pixels nulle — à 1024 et 1280px).
  - **Message de retour remis dans le flux (point 1).** En portrait
    (≤480px), `#message-coup` n'est plus positionné en surimpression
    (`position: absolute`, ancré par le bas) mais redevient un enfant normal
    de `.zone-actions-humain` (`position: relative`, pleine largeur,
    `border-radius` réduit en bandeau, retour à la ligne natif) : il
    s'affiche désormais SOUS les boutons d'action, repoussant simplement la
    suite du contenu (fiche joueur, puis Dictionnaire) sans jamais chevaucher
    le chevalet, les boutons ou le plateau. La règle `.message-coup:empty {
    display: none; }` (déjà en place) continue d'éviter toute pastille ou
    espace résiduel quand le message est vide. Comportement ≥481px
    (bureau) inchangé — toujours en surimpression, aspect identique.
  - **Croix de fermeture et fermeture au toucher (point 2).** En portrait,
    une croix « ✕ » est ajoutée par la feuille de style à droite du message
    quand il n'est pas vide (`.message-coup:not(:empty)::after`, purement
    décorative) ; un clic ou toucher sur le message entier le vide, via un
    nouvel écouteur dans `jeu.js` qui appelle la même fonction
    `afficherMessageCoup('')` que l'auto-effacement existant. Cet écouteur
    est posé sans condition de largeur : sur bureau, le message peut donc
    aussi disparaître au clic (aspect de la surimpression inchangé), comme
    le permettait l'issue. N'interfère pas avec l'auto-effacement des
    messages de succès (« Coup joué », « Tour passé ») : `afficherMessageCoup`
    annule de toute façon l'ancien minuteur à chaque nouvel appel, que ce
    soit un appel automatique ou un clic utilisateur.
  - **Croix de fermeture de la modale de détail du score (point 3).**
    Nouveau bouton `#score-fermer-croix` (`jeu.html`, premier enfant de
    `.modale-score`, `aria-label="Fermer"`), masqué par défaut et dévoilé
    uniquement ≤880px (coin haut droit, cible tactile 40×40px). Branché dans
    `jeu.js` sur `modaleScore.fermer()` — EXACTEMENT le même chemin de
    fermeture que le bouton « Fermer » existant (`#score-fermer`, qui
    appelle la même fonction interne du contrôleur `creerModaleScore` de
    `commun.js`, non modifié) : retrait de la surbrillance du coup consulté
    et remasquage de « ✓ Jouer » inclus. Le clic en dehors et les boutons
    « Fermer »/« ✓ Jouer » existants restent inchangés et fonctionnels.
    Autres fenêtres modales du jeu qui se ferment seulement par clic dehors
    + bouton + Échap (même problème potentiel de bouton de fermeture loin du
    doigt sur petit écran, non traitées par cette issue) : fin de partie
    (`#modale-fin`), retour au menu avec coup en attente (`#retour-modale`),
    confirmation générique d'action irréversible (`#confirmation-modale`,
    utilisée entre autres pour l'échange complet et le passage de tour) et
    « Les personnages » (`#modale-personnages`). Le détail d'un coup de
    l'historique réutilise `#score-modale` (pas de fenêtre séparée).
  - **Inventaire (point 4).** Recherche exhaustive, dans `jeu.html`,
    `jeu.js`, `accueil.html`, `accueil.js`, `commun.js`, `commun.css`,
    `jeu.css`, `accueil.css`, de tout message/bandeau/bulle/popover/modale
    sans minuteur de disparition — détail dans le rapport de l'issue
    (tableau complet avec déclencheur, fermeture actuelle et risque de
    recouvrement en portrait pour chaque élément : `#message-coup`,
    `#message-plateau`, toasts de points, `#message-brouillon`, sélecteur de
    joker, `#score-modale`, `#modale-fin`, `#retour-modale`,
    `#confirmation-modale`, `#modale-personnages`, popovers « Derniers
    coups » et « Vérification dictionnaire », modales de l'accueil…). Seuls
    les éléments déjà traités aux points 1 à 3 ont été corrigés ici ; les
    autres sont seulement signalés, sans modification.
