// Harnais de rendu hors-ligne de l'écran de jeu (issue #38, non commité).
// Mocke pywebview.api pour rendre jeu.html/jeu.css/jeu.js dans un navigateur
// headless et capturer des captures d'écran avant/après.
(function () {
  const L = 'normale';
  // Plateau standard (docstring de regles/plateau.py). '.' = normale.
  const CARTE = [
    ['MT','.','.','LD','.','.','.','MT','.','.','.','LD','.','.','MT'],
    ['.','MD','.','.','.','LT','.','.','.','LT','.','.','.','MD','.'],
    ['.','.','MD','.','.','.','LD','.','LD','.','.','.','MD','.','.'],
    ['LD','.','.','MD','.','.','.','LD','.','.','.','MD','.','.','LD'],
    ['.','.','.','.','MD','.','.','.','.','.','MD','.','.','.','.'],
    ['.','LT','.','.','.','LT','.','.','.','LT','.','.','.','LT','.'],
    ['.','.','LD','.','.','.','LD','.','LD','.','.','.','LD','.','.'],
    ['MT','.','.','LD','.','.','.','centre','.','.','.','LD','.','.','MT'],
    ['.','.','LD','.','.','.','LD','.','LD','.','.','.','LD','.','.'],
    ['.','LT','.','.','.','LT','.','.','.','LT','.','.','.','LT','.'],
    ['.','.','.','.','MD','.','.','.','.','.','MD','.','.','.','.'],
    ['LD','.','.','MD','.','.','.','LD','.','.','.','MD','.','.','LD'],
    ['.','.','MD','.','.','.','LD','.','LD','.','.','.','MD','.','.'],
    ['.','MD','.','.','.','LT','.','.','.','LT','.','.','.','MD','.'],
    ['MT','.','.','LD','.','.','.','MT','.','.','.','LD','.','.','MT'],
  ];
  // Quelques tuiles posées pour juger du contraste (point 4).
  const POSEES = {
    '7,5': 'J', '7,6': 'O', '7,7': 'U', '7,8': 'E', '7,9': 'R',
    '6,7': 'M', '8,7': 'T', '9,7': 'S',
    '5,9': 'C', '6,9': 'A', '8,9': 'E',
  };
  const plateau = CARTE.map((ligne, l) =>
    ligne.map((c, col) => {
      const type = c === '.' ? L : c;
      const key = l + ',' + col;
      return { type, lettre: POSEES[key] || null, joker: false };
    })
  );

  const joueurs = [
    { index: 0, nom: 'Alain', humain: true, niveau: null, score: 148,
      nb_lettres: 7, courant: true, position: 'bas', avatar: 'avatar-01' },
    { index: 1, nom: 'Ordi Nord', humain: false, niveau: 'EXPERT', score: 132,
      nb_lettres: 7, courant: false, position: 'haut', avatar: 'avatar-05' },
    { index: 2, nom: 'Ordi Ouest', humain: false, niveau: 'INTERMEDIAIRE', score: 97,
      nb_lettres: 7, courant: false, position: 'gauche', avatar: 'avatar-09' },
    { index: 3, nom: 'Ordi Est', humain: false, niveau: 'FACILE', score: 110,
      nb_lettres: 6, courant: false, position: 'droite', avatar: 'avatar-12' },
  ];

  // Format allégé en trois paliers (issue #364) : la liste elle-même ne porte
  // plus le détail du score embarqué (``detail``), seulement un booléen
  // ``a_detail`` — le détail se charge à la demande via
  // ``api.obtenir_detail_coup(index)`` (voir plus bas). ``positions`` (cases
  // posées, vide pour une passe/un échange) sert à la surbrillance du coup
  // consulté dans l'historique (jeu.js, ``surbrillerCoupConsulte``).
  const historique = [
    { index: 5, action: 'coup', nom_joueur: 'Ordi Est', humain: false, mot: 'CAVE',
      score_action: 18, a_detail: true, positions: [{ ligne: 6, colonne: 9 }] },
    { index: 4, action: 'coup', nom_joueur: 'Alain', humain: true, mot: 'JOUER',
      score_action: 24, a_detail: true,
      positions: [
        { ligne: 7, colonne: 5 }, { ligne: 7, colonne: 6 }, { ligne: 7, colonne: 7 },
        { ligne: 7, colonne: 8 }, { ligne: 7, colonne: 9 },
      ] },
    { index: 3, action: 'passe', nom_joueur: 'Ordi Ouest', humain: false, mot: null,
      score_action: 0, a_detail: false, positions: [] },
    { index: 2, action: 'coup', nom_joueur: 'Ordi Nord', humain: false, mot: 'MTS',
      score_action: 12, a_detail: true,
      positions: [
        { ligne: 6, colonne: 7 }, { ligne: 8, colonne: 7 }, { ligne: 9, colonne: 7 },
      ] },
  ];

  // Détail du score d'un coup (palier c, issue #364), chargé à la demande par
  // ``api.obtenir_detail_coup(index)`` — plus jamais embarqué dans la liste.
  const detailsCoup = {
    5: { mots: [{ texte: 'CAVE', score: 18, cases_bonus: [] }], total: 18 },
    4: { mots: [{ texte: 'JOUER', score: 24, cases_bonus: [] }], total: 24 },
    2: { mots: [{ texte: 'MTS', score: 12, cases_bonus: [] }], total: 12 },
  };

  // Résumé minimal du dernier coup réel (issue #364, ex-``historique[0]``) :
  // sert à la surbrillance persistante ``.derniere-pose`` du plateau.
  const dernierCoup = { positions: historique[0].positions };

  const chevalet = [
    { lettre: 'A', valeur: 1, joker: false },
    { lettre: 'E', valeur: 1, joker: false },
    { lettre: 'S', valeur: 1, joker: false },
    { lettre: 'R', valeur: 1, joker: false },
    { lettre: 'T', valeur: 1, joker: false },
    { lettre: 'K', valeur: 10, joker: false },
    { lettre: '*', valeur: 0, joker: true },
  ];

  const etat = {
    id_partie: 1, taille: 15, plateau, joueurs,
    index_courant: 0, jetons_sac: 42, nb_humains: 1,
    tour_humain: true, index_panneau: 0, terminee: false,
    gagnants: [], nb_historique: historique.length, dernier_coup: dernierCoup,
  };

  window.pywebview = {
    api: {
      obtenir_etat: async () => JSON.parse(JSON.stringify(etat)),
      obtenir_theme_plateau: async () => window.__THEME__ || 'classique',
      obtenir_chevalet: async () => ({ succes: true, lettres: chevalet }),
      // Paliers b/c de l'historique glissant (issue #364) : la liste sans
      // détail, puis le détail d'UNE entrée à la demande.
      obtenir_historique: async () => JSON.parse(JSON.stringify(historique)),
      obtenir_detail_coup: async (index) => (
        index in detailsCoup
          ? { succes: true, detail: JSON.parse(JSON.stringify(detailsCoup[index])) }
          : { succes: false }
      ),
      verifier_mot: async () => ({ succes: true, valide: true, mot: 'TEST', definition: ['Définition de démonstration.'] }),
      echanger_tout: async () => ({ succes: true }),
      passer: async () => ({ succes: true }),
      faire_jouer_ia: async () => ({ succes: true }),
      poser_mot: async () => ({ succes: true, points: 0 }),
    },
  };
})();
