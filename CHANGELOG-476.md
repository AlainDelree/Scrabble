# Changelog — Issue #476

## Modifié

- **`jeu.css` : palier responsive supplémentaire sous 480px pour le
  chevalet.** Le seul élément de l'écran de jeu encore sujet à un
  débordement horizontal en dessous d'environ 400px de large était le
  chevalet (9 tuiles de 40px en rangée unique `flex-wrap: nowrap`,
  issue #189) — la marge gauche elle-même repasse déjà en une colonne
  pleine largeur dès 880px (`@media (max-width: 880px)`, inchangé) et tout
  son autre contenu (boutons, fiches joueurs, actions de tour) était déjà
  en `flex-wrap: wrap`. Nouveau palier `@media (max-width: 480px)` : le
  panneau du chevalet (`.zone-chevalet .panneau`) passe en `flex-wrap: wrap`
  — les 9 tuiles se répartissent sur deux rangées centrées dès que la
  largeur manque, en conservant leur taille pleine de 40×44px (cible
  tactile ≥40px préservée, pas de réduction des tuiles).
- **`accueil.css` : panneau de fond du mode Belgicisme
  (`.container::before`) corrigé pour ne plus déborder en portrait.** Sa
  largeur (`clamp(620px, 94vw, 720px)`) imposait un plancher fixe de 620px
  **quelle que soit la largeur de fenêtre**, car ce pseudo-élément est en
  `position: absolute` et n'est donc jamais borné par la largeur réelle de
  son parent (contrairement à `.container`, qui utilise la même formule
  mais reste naturellement borné par son conteneur) — un vrai débordement
  horizontal (mesuré : `scrollWidth` ≈ 490px pour une fenêtre de 360px).
  Remplacé par `width: min(94vw, 720px)`, qui reproduit le comportement de
  `.container` à toutes les largeurs sans aucun changement au-delà
  d'environ 660px (où `94vw` dépassait déjà l'ancien plancher).
- **`accueil.css` : titre « Scrabble » (`header h1 .lettre-scrabble`) rendu
  responsive.** Les 8 tuiles de 3.2rem (fixes) + le `padding-right` réservé
  de 56px pour le bouton ⚙ ne tenaient plus dans une fenêtre de téléphone en
  portrait ; `.container` ayant `overflow: hidden`, le titre était
  silencieusement tronqué (pas de barre de défilement visible, juste des
  lettres coupées en haut de l'écran). Taille des tuiles, interstice et
  `padding-right` passés en `clamp()` : mêmes valeurs maximales qu'avant
  (donc rendu identique au-delà d'environ 730px de large, bien au-dessus du
  seuil de 880px), tuiles réduites proportionnellement à la largeur en
  dessous.

## Essais

- Harnais Playwright existant (`scripts/_harness_jeu/`, mock/méthodes de
  `shot.mjs`/`verif_accueil_145.mjs`) : son mock (`mock.js`) s'est avéré
  périmé vis-à-vis de l'API actuelle de `jeu.js` (`obtenir_etat` au lieu de
  `obtenir_etat_plateau`/`obtenir_etat_chevalet`, décalage antérieur à cette
  issue, probablement issue #364) — sans rapport avec cette tâche, mais le
  plateau/chevalet ne se rendait pas avec le mock tel quel. Contourné par un
  script de vérification ad hoc (non commité, exécuté depuis `/tmp`,
  conforme au périmètre « fichiers modifiés » de cette issue) qui appelle
  directement `window.appliquerEtatPlateau`/`window.appliquerEtatChevalet`
  une fois `jeu.js` initialisé, avec les mêmes données d'exemple que le
  mock existant.
- Mesures automatisées (scrollWidth vs innerWidth, tailles réelles des
  tuiles/cases) et captures d'écran aux largeurs 360/412/430/768/1024/1280,
  écran de jeu et accueil (configuration, mode Belgicisme, réglages/onglet
  Règles), avant et après modification — voir le corps du rapport de
  l'issue pour le détail chiffré par largeur.
- Comparaison pixel par pixel (Pillow `ImageChops.difference`) des captures
  avant/après à 1024px et 1280px pour l'écran de jeu et l'accueil :
  différence nulle (`bbox=None`) dans les quatre cas — aucun changement
  visuel au-dessus de 880px.
- `pytest -m "not lent"` : 1404 passed, 5 skipped (skips documentés,
  dossier `data/dictionnaire/` et `config.json` du poste absents de ce
  worktree, sans rapport avec les fichiers modifiés), 0 failed.
