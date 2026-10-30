# Changelog — Issue #477

## Modifié

- **`jeu.css`/`jeu.html` : écran de jeu en portrait étroit (≤480px) —
  plateau toujours visible, chevalet sur une rangée, barre du haut
  compacte.** Tout confiné au palier `@media (max-width: 480px)` déjà
  introduit par l'issue #476 ; aucun changement au-dessus (vérifié
  pixel-pour-pixel à 1024/1280px).
  - **Chevalet sur une seule rangée.** Les 2 emplacements vides du
    chevalet servent au réarrangement local (déplacement d'une lettre
    sélectionnée vers un vide, clic droit = renvoi vers le vide le plus à
    droite — `jeu.js`) : ils sont donc conservés. Tuiles réduites de
    40×44px à 32×36px (lettre + valeur toujours lisibles) : les 9
    emplacements tiennent sur une seule rangée sans repli dès 360px de
    large (remplace le `flex-wrap: wrap` ajouté par #476, qui repliait
    le dernier emplacement vide sur sa propre ligne).
  - **Plateau collant.** `.container` passe en grille 2 colonnes ; la
    barre système et le plateau sont `position: sticky` et s'empilent en
    haut de l'écran (fond opaque assorti au tapis vert pour masquer le
    contenu qui défile dessous) pendant que joueurs/chevalet/actions/
    dictionnaire/historique défilent en dessous. `display: contents` sur
    `.colonne-gauche`/`.zone-historique-permanente` replace leurs enfants
    directement dans la grille (id/classes/écouteurs JS inchangés, aucun
    élément déplacé dans le HTML).
  - **Barre du haut compacte.** Retour / Sac / « Derniers coups » sur une
    seule ligne au-dessus du plateau (grille 2 colonnes, même ligne de
    grille). « Retour au menu » et « Derniers coups » affichent un
    libellé raccourci (« Retour », « Coups ») via deux `<span>`
    basculés par CSS — libellé complet toujours porté par `aria-label`/
    `title`, modales et affichage ordinateur inchangés.
  - **« Derniers coups » sans masquer le plateau.** Le popover (ancré en
    absolu sous son bouton par défaut) est détaché en `position: fixed`
    et ancré sous le bloc collant complet (barre + plateau), ciblé par
    **`#historique-liste`** (id, pas la classe partagée
    `.historique-liste` — le joker, `#joker-popover`, réutilise cette
    classe et sa position est calculée dynamiquement par `jeu.js` ; un
    sélecteur de classe lui aurait ajouté un décalage non voulu, détecté
    en vérification Playwright puis corrigé).
  - **Bouton « ↻ Resynchroniser » masqué en portrait** (`display: none`
    à ≤480px, inchangé au-dessus) — remplacé par le rattrapage
    automatique côté serveur, voir ci-dessous.
  - Boutons d'action (point 6, optionnel) laissés inchangés : le gain
    mesuré n'était pas net (voir « Essais »).
- **`src/scrabble/serveur/pont.py` : rattrapage automatique après un
  décrochage, en remplacement du bouton « ↻ Resynchroniser » masqué en
  portrait.** Nouvelle fonction `script_rattrapage()` : script injecté
  dans toutes les pages HTML, qui recharge l'état du plateau et du
  chevalet (`obtenir_etat_plateau`/`obtenir_etat_chevalet` puis
  `window.appliquerEtatPlateau`/`appliquerEtatChevalet` — mêmes
  fonctions que le bouton, `jeu.js` inchangé) quand la page redevient
  visible (réveil du téléphone, retour d'un changement d'onglet) et
  quand le flux SSE se reconnecte (nouvelle constante publique
  `EVENEMENT_SSE_OUVERTURE`, déclenchée par `httpd._script_pont` sur
  `EventSource.onopen` — connexion initiale et reconnexions automatiques
  du navigateur).
  - **Écart au périmètre déclaré de l'issue (signalé, minimal) :**
    l'injection du script dans les pages HTML et la connexion SSE vivent
    dans `httpd.py` (`_script_pont`/`_servir_statique`), pas dans
    `pont.py` — modifier `pont.py` seul rendait le rattrapage
    inatteignable par le navigateur. Édition de `httpd.py` strictement
    additive (import + 3 lignes dans `_script_pont` pour déclencher
    l'évènement SSE + concaténation du script de `pont.py` à l'injection
    existante) : aucune ligne existante modifiée, et `scrabble/serveur/`
    n'est importé nulle part par `scrabble/ui/`— zéro effet sur
    l'application de bureau (jamais chargé par pywebview).
  - Tests ajoutés dans `tests/test_serveur.py` : contenu du script de
    rattrapage, déclenchement de l'évènement SSE par `_script_pont`,
    présence du script dans une page `jeu.html` servie.

## Essais

- `pytest -m "not lent"` : 1426 passés, 5 ignorés (préexistants, données
  manquantes de ce poste de travail isolé), 1 échec **préexistant**
  (`test_serveur_diffuse_l_etat_via_sse`, confirmé identique sur le code
  d'origine — absence de `data/dictionnaire/` complet dans ce worktree,
  sans rapport avec cette issue), 5 tests `lent` désélectionnés.
- Vérification Playwright (module `scrabble.serveur`, Chromium piloté en
  tâche de fond, données isolées dans un dossier temporaire) à
  360×640/390×844/412×915/844×390(paysage) : chevalet sur une rangée
  sans débordement horizontal, plateau collant pendant le défilement du
  reste du contenu, popover « Derniers coups » ne recouvrant jamais le
  plateau, sélecteur de joker et flux d'échange partiel lisibles et
  utilisables au doigt, rattrapage automatique déclenché (vérifié au
  niveau DOM : `visibilitychange` et réouverture SSE appellent bien
  `obtenir_etat_plateau`/`obtenir_etat_chevalet`).
  - **Limite de cette vérification (signalée) :** le worktree n'a pas pu
    recevoir de dictionnaire réel — le périmètre strict de la tâche
    interdit toute lecture hors de ce worktree, ce qui exclut la copie
    demandée par l'issue depuis le clone principal du dépôt. Le parcours
    de jeu réel (coups validés par le dictionnaire, calcul de score,
    IA) n'a donc pas pu être rejoué de bout en bout ; la mise en page a
    été vérifiée en injectant un état de plateau/chevalet synthétique
    directement via `window.appliquerEtatPlateau`/`appliquerEtatChevalet`
    (mêmes fonctions que celles utilisées par le vrai flux de jeu).
  - Captures 1024/1280px avant/après (hors dépôt, `/tmp/`, non commitées) :
    différence de pixels strictement nulle.
