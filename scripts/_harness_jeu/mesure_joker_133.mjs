// Mesure headless HORIZONTALE de la modale de choix de lettre du joker (issue #133,
// point B). L'issue #121 avait réglé le débordement VERTICAL (grille scrollable +
// bouton Annuler épinglé). Une capture d'écran laissait craindre un débordement
// HORIZONTAL (lettres H..N tronquées à droite) depuis le resserrage de la fenêtre
// chevalet à 480 px (#104/#106). On mesure ici, à 480 px de large :
//   - largeur intrinsèque de la grille (scrollWidth) vs sa largeur visible (clientWidth) ;
//   - débordement horizontal du contenu / du document (scrollWidth > clientWidth) ;
//   - pour CHAQUE bouton-lettre : son bord droit dépasse-t-il la zone visible de la
//     grille et/ou de la fenêtre (lettre tronquée à droite) ?
// Usage : node scripts/_harness_jeu/mesure_joker_133.mjs [largeur] [hauteur]
import pw from '/home/alain/.npm-global/lib/node_modules/playwright/index.js';
const { chromium } = pw;
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '../../src/scrabble/ui/web');
const read = (f) => fs.readFileSync(path.join(web, f), 'utf8');
const communCss = read('commun.css');
const chevaletCss = read('chevalet.css');
const communJs = read('commun.js');
const chevaletJs = read('chevalet.js');

const W = Number(process.argv[2] || 480);
const H = Number(process.argv[3] || 175);

const lettres = [
  { lettre: 'A', valeur: 1, joker: false },
  { lettre: 'E', valeur: 1, joker: false },
  { lettre: 'S', valeur: 1, joker: false },
  { lettre: 'R', valeur: 1, joker: false },
  { lettre: 'T', valeur: 1, joker: false },
  { lettre: 'K', valeur: 10, joker: false },
  { lettre: '*', valeur: 0, joker: true },
];

function etatJoker() {
  return {
    index_courant: 0, nom: 'Alain', mon_tour: true, tour_humain: true,
    terminee: false, nb_humains: 1, nb_lettres: 7, lettres, selection: null,
    en_attente: [], joker_demande: { ligne: 7, colonne: 7, index: 6 },
  };
}

const mock = `
  window.pywebview = { api: {
    obtenir_etat_chevalet: async () => (${JSON.stringify(etatJoker())}),
    selectionner_lettre: async () => ({ succes: true }),
    poser_lettre_en_attente: async () => ({ succes: true }),
    debut_deplacement_chevalet: async () => ({ succes: true, x: 0, y: 0 }),
    deplacer_chevalet: async () => ({ succes: true }),
  } };
`;

let html = read('chevalet.html')
  .replace('<link rel="stylesheet" href="commun.css">', `<style>${communCss}</style>`)
  .replace('<link rel="stylesheet" href="chevalet.css">', `<style>${chevaletCss}</style>`)
  .replace('<script src="commun.js"></script>', `<script>${mock}</script><script>${communJs}</script>`)
  .replace('<script src="chevalet.js"></script>', `<script>${chevaletJs}</script>`);

const MESURE = () => {
  const doc = document.documentElement;
  const contenu = document.querySelector('#joker-modale .modale-contenu');
  const grille = document.getElementById('joker-grille');
  const lettresBtn = grille ? Array.from(grille.querySelectorAll('.joker-lettre')) : [];
  const innerW = window.innerWidth;
  const gR = grille ? grille.getBoundingClientRect() : null;
  const cR = contenu ? contenu.getBoundingClientRect() : null;
  // Un bouton est « tronqué à droite » si son bord droit dépasse le bord droit
  // visible de la grille (au pixel près) ou celui de la fenêtre.
  const tronques = lettresBtn
    .map((b) => {
      const r = b.getBoundingClientRect();
      return {
        lettre: b.textContent.trim().charAt(0),
        right: Math.round(r.right),
        depasseGrille: gR ? r.right > gR.right + 0.5 : null,
        depasseFenetre: r.right > innerW + 0.5,
      };
    })
    .filter((x) => x.depasseGrille || x.depasseFenetre);
  return {
    modaleOuverte: contenu ? !document.getElementById('joker-modale').hidden : false,
    nbLettres: lettresBtn.length,
    innerW,
    contenuLargeurVisible: cR ? Math.round(cR.width) : null,
    contenuDroite: cR ? Math.round(cR.right) : null,
    contenuDebordeH: contenu ? contenu.scrollWidth > contenu.clientWidth + 1 : null,
    grilleLargeurVisible: grille ? grille.clientWidth : null,
    grilleScrollW: grille ? grille.scrollWidth : null,
    grilleDebordeH: grille ? grille.scrollWidth > grille.clientWidth + 1 : null,
    grilleDroite: gR ? Math.round(gR.right) : null,
    docDebordeH: doc.scrollWidth > doc.clientWidth,
    docScrollW: doc.scrollWidth,
    docClientW: doc.clientWidth,
    nbBoutonsTronques: tronques.length,
    boutonsTronques: tronques,
  };
};

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await page.waitForTimeout(400);

  const m = await page.evaluate(MESURE);
  console.log(`[${W}x${H}] MESURE HORIZONTALE :`, JSON.stringify(m, null, 2));
  await page.screenshot({ path: path.join(here, `i133_joker_${W}x${H}.png`) });

  await browser.close();
})();
