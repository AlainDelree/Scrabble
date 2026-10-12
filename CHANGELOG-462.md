# Changelog — Issue #462

## Corrigé

- **Accueil : le sélecteur de personnage et le lien « Les personnages »
  restaient affichés quand l'interface des personnages était censée être
  masquée.** L'issue #461 masque côté serveur l'interface des personnages
  dès que moins de deux personnages sont actifs (`zonePersonnage.hidden =
  true`, `accueil.js`), mais ce masquage restait sans effet visuel à
  l'accueil : le libellé « Personnage du prochain ordinateur : », la liste
  déroulante et le lien « Les personnages » restaient visibles. Cause
  exacte : `.zone-personnage { display: flex }` (`accueil.css`) est une
  règle d'auteur, qui l'emporte toujours sur le `[hidden] { display: none }`
  par défaut du navigateur — une règle UA, structurellement perdante face à
  l'auteur quels que soient la spécificité ou l'ordre des règles.

  - **`src/scrabble/ui/web/accueil.css`** : ajout d'une règle globale et
    durable `[hidden] { display: none !important; }` juste après le reset
    `* { ... }`, plutôt qu'un correctif ciblé sur `.zone-personnage` : tout
    élément masqué de l'accueil (présent ou futur) en bénéficie désormais,
    pas seulement le bloc personnage. `.zone-personnage { display: flex }`
    est inchangée : à deux personnages actifs ou plus, l'accueil s'affiche
    exactement comme avant.
  - **`scripts/_harness_jeu/verif_443_personnages.mjs`** : le mock de l'API
    accueil ne définissait pas `interface_personnages_visible`, lacune
    restée invisible tant que le masquage ne produisait aucun effet
    (issue #461/#462) — l'appel manquant aurait désormais fait échouer le
    clic sur « Les personnages » dans ce harnais. Ajout du mock manquant
    (`async () => true`, cohérent avec les 3 personnages actifs de la
    scène). L'échec résiduel de ce script côté fenêtre « Jeu » (mock
    `interface_personnages_visible` absent de `mock.js`) est préexistant,
    confirmé par `git stash` — hors périmètre de ce lot.
  - **`tests/test_accueil_niveaux_visuels.py`** : nouvelle classe
    `TestMasquageHiddenNonEcraseParLeStyle` (3 tests) — vérifie la présence
    de la règle `[hidden] { display: none !important }`, qu'elle cible bien
    l'attribut nu (pas un sélecteur composé du style
    `.zone-personnage[hidden]`, qui laisserait le même piège ouvert pour un
    futur élément), et que `.zone-personnage` garde son `display: flex`
    normal.
  - **`scripts/_harness_jeu/verif_462_accueil_personnages.mjs`** (nouveau) :
    harnais Playwright (1280×800) qui monte `accueil.html` avec l'API
    mockée pour un seul personnage actif puis pour deux, capture les deux
    écrans et vérifie par `getComputedStyle` que le bloc personnage a
    bien `display: none`/hauteur nulle dans le premier cas et `display:
    flex`/hauteur normale dans le second.

  Suite pytest : 1397 → 1400 tests verts (3 ajoutés), mêmes 5 échecs
  préexistants et sans rapport (confirmés par `git stash`) :
  `test_accueil.py::TestApiAccueilInfosTirage::test_infos_tirage_memorisees`,
  `test_application.py::TestRoutageVueActive::test_methode_propre_au_jeu_hors_vue_leve_attribute_error`,
  `test_application.py::TestParcoursCompletUnifie::test_parcours_complet_une_seule_session_et_fermeture`,
  `test_journal_integration.py::TestJournalAccueil::test_ajout_ordinateur_journalise`,
  `test_journal_integration.py::TestJournalAccueil::test_lancer_partie_journalise_avec_nb_joueurs`.
