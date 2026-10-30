# Changelog — Issue #478

## Modifié

- **`jeu.css` : écran de jeu en portrait étroit (≤480px) — barre du haut
  propre (fond, alignement) et chevalet juste sous le plateau.** Suite de
  l'issue #477, après un essai réel sur téléphone Android. Tout confiné au
  palier `@media (max-width: 480px)` déjà introduit par #476/#477 ; aucun
  changement au-dessus (vérifié par capture AVANT/APRÈS strictement
  identique — différence de pixels nulle — à 1024 et 1280px).
  - **Fond plein largeur de la barre système (point 1).** Avant ce
    correctif, `.zone-systeme` (colonne 1 de la grille) et `#historique-menu`
    (colonne 2, bouton « Coups ») portaient chacun leur propre fond, limité
    à leur propre boîte : la bande entre les deux colonnes et la marge
    jusqu'au bord droit de l'écran restaient transparentes, laissant
    apparaître le contenu qui défile derrière (le bogue rapporté : fond
    partiel, bouton « Coups » sur un fond différent). Un pseudo-élément
    séparé (`.container::before`), placé sur la même cellule de grille que
    les deux (`grid-column: 1 / -1`, `grid-row: 1`, empilé sous eux),
    couvre tout le rectangle de la ligne 1 en une seule fois, sans toucher
    au HTML ni déplacer les deux boîtes existantes. Fond en
    `background-attachment: fixed` (comme le tapis du `body`) plutôt qu'un
    dégradé recalculé sur la petite boîte de la barre : un dégradé local
    donnait une teinte visiblement différente de celle du tapis vu juste
    au-dessus pendant le défilement (la « bande de couleur légèrement
    différente » rapportée) — `fixed` ancre le dégradé sur la fenêtre, donc
    des pixels rigoureusement identiques à ceux du `body` à la même
    position écran.
  - **Alignement des 3 éléments de la barre (point 1, suite).** « Retour »,
    la pastille du sac et « Coups » (`.historique-resume`) avaient chacun
    une hauteur naturelle différente (bouton standard, pastille haute avec
    icône 22px, pastille plus basse) — constaté par Alain comme « sac en
    grande pastille d'environ 80px, bouton Coups plus petit et accolé en
    haut à droite ». Les trois sont désormais forcés à une hauteur commune
    de 36px (`box-sizing: border-box`, contenu recentré en flexbox) ; seul
    le sac, trop haut par défaut, voit sa taille réduite (icône/texte) pour
    tenir dans cette hauteur. Barre mesurée à 36px de haut (sous la limite
    de 50px visée par l'issue) aux trois largeurs 360/390/412px.
  - **Bouton « Les personnages » retiré de la barre en portrait (point 1,
    conséquence).** Visible dès que 2 personnages sont actifs (le cas
    courant, dès qu'un ordinateur a un nom — pas un cas rare), il repliait
    la colonne 1 sur une 2e ligne (barre réelle à 80px) alors que
    `--barre-portrait-haut` (décalage `top` du plateau collant) restait une
    valeur fixe à 48px héritée de #477 : une fois la page défilée, le
    plateau collant venait alors recouvrir entièrement cette 2e ligne,
    rendant le bouton « Personnages » totalement invisible (bogue trouvé en
    vérification Playwright, absent du rapport initial d'Alain mais
    bloquant pour l'objectif « barre propre, plateau collant juste
    dessous »). Masqué ici en portrait (même traitement que le bouton
    « ↻ Resynchroniser » déjà écarté par #477, fonctionnalité annexe sans
    équivalent nécessaire sur téléphone, `jeu.js` inchangé, le bouton reste
    affiché tel quel ≥481px) : la barre système tient désormais TOUJOURS sur
    une seule rangée de 36px, ce qui rend `--barre-portrait-haut` fiable.
    Valeur recalculée de 48px à 36px en conséquence et revérifiée par
    défilement Playwright : décalage exact entre le bas de la barre collante
    et le haut du plateau collant, sans espace ni recouvrement, aux trois
    largeurs.
  - **Ordre des blocs sous le plateau (point 2).** Nouvel ordre en portrait,
    de haut en bas : plateau (collant, inchangé), chevalet, boutons d'action
    de l'humain (Annuler, Vérifier et calculer, Jouer, Échanger, Passer),
    cartes des joueurs, champ Dictionnaire — remplace l'ordre de #477
    (dictionnaire, joueurs, chevalet, actions). Seul le `grid-row` de
    chaque zone est modifié (3 à 6) ; aucun élément déplacé dans le HTML,
    aucun identifiant ni écouteur JavaScript touché. Chevalet confirmé
    visible sans défiler à 390×844 et 412×915 ; à 360×640 (le plus petit
    gabarit testé), le chevalet est intégralement visible mais les boutons
    d'action juste en dessous sont partiellement hors cadre (défilement
    nécessaire pour les atteindre, comportement inchangé par rapport à
    #477 pour cette taille).

## Essais

- Vérification Playwright (module `scrabble.serveur`, Chromium piloté en
  tâche de fond, données isolées dans un dossier temporaire) à
  360×640/390×844/412×915/844×390 (paysage) : partie réelle jouée jusqu'à
  l'écran de jeu (dictionnaire ODS8 copié manuellement dans ce worktree par
  une tentative précédente — gitignoré, jamais commité, aucun mot cité
  ici), pas d'état synthétique injecté.
  - Fond de la barre uniforme sur toute la largeur aux trois tailles
    (captures zoomées avant/après + échantillonnage de pixels : variation
    de teinte due au seul dégradé continu du tapis, aucune rupture) ; les
    trois éléments alignés à la même hauteur (36px) ; aucune bande de
    couleur différente au-dessus de la barre pendant le défilement
    (échantillonnage de pixels identique scrollé/non scrollé).
  - Ordre des blocs sous le plateau conforme au point 2 ; chevalet visible
    sans défiler à 390×844/412×915, visible mais actions partiellement hors
    cadre à 360×640 (voir ci-dessus).
  - Plateau collant pendant le défilement du reste du contenu, vérifié par
    mesure exacte des rectangles englobants une fois défilé : bord inférieur
    de la barre collante et bord supérieur du plateau collant exactement
    jointifs (aucun espace, aucun recouvrement) à 360×640 et 390×844 ; à
    412×915 le contenu tient presque entièrement dans la fenêtre (10px de
    défilement possible seulement), insuffisant pour atteindre l'état
    collant complet du plateau — comportement normal, pas un bogue.
  - Panneau « Derniers coups » ouvert sans jamais masquer le plateau
    (comportement #477 inchangé, revérifié).
  - Échange de lettres (remise complète) testé avec succès : modale de
    confirmation lisible, bien positionnée, boutons utilisables. Joker non
    rejoué de bout en bout dans cette vérification (flux de pose complexe,
    cases bonus aléatoires) mais son CSS (`#joker-popover`, positionné
    dynamiquement par `jeu.js`) n'est touché par aucune règle de ce
    correctif — logique inchangée et déjà vérifiée par #477.
  - Aucun défilement horizontal aux trois largeurs portrait
    (`scrollWidth === clientWidth`).
  - Captures 1024/1280px avant/après (même session de jeu, feuille de style
    basculée sans recharger la page pour conserver un état de partie
    identique) : différence de pixels **strictement nulle** aux deux
    tailles, confirmée par comparaison programmatique en plus de l'examen
    visuel — hors dépôt, `/tmp/`, non commitées.
- `pytest -m "not lent"` : 1430 passés, 2 ignorés, 5 désélectionnés
  (tests `lent`).
