// Mesure réelle de la fenêtre chevalet épurée (issue #102).
// Depuis #102, la fenêtre ne contient plus que la barre de déplacement et le
// panneau des lettres (en-tête vert + aide retirés). On mesure la hauteur et la
// largeur naturelles du contenu pour recalibrer CHEVALET_HAUTEUR/LARGEUR.
// Usage : node scripts/_harness_jeu/mesure_chevalet_102.mjs [largeur] [hauteur]
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

const W = Number(process.argv[2] || 880);
const H = Number(process.argv[3] || 300);

const lettres = [
  { lettre: 'A', valeur: 1, joker: false },
  { lettre: 'E', valeur: 1, joker: false },
  { lettre: 'S', valeur: 1, joker: false },
  { lettre: 'R', valeur: 1, joker: false },
  { lettre: 'T', valeur: 1, joker: false },
  { lettre: 'K', valeur: 10, joker: false },
  { lettre: '*', valeur: 0, joker: true },
];

function etatHumain() {
  return {
    index_courant: 0, nom: 'Alain', mon_tour: true, tour_humain: true,
    terminee: false, nb_humains: 1, nb_lettres: 7, lettres, selection: null,
    en_attente: [], joker_demande: null,
  };
}

const mock = `
  window.pywebview = { api: {
    obtenir_etat_chevalet: async () => (${JSON.stringify(etatHumain())}),
    selectionner_lettre: async () => ({ succes: true }),
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
  const barre = document.querySelector('.barre-drag');
  const fen = document.querySelector('.chevalet-fenetre');
  const bloc = document.querySelector('.bloc-panneau');
  const panneau = document.getElementById('panneau');
  const rh = (el) => el ? Math.round(el.getBoundingClientRect().height) : null;
  const rw = (el) => el ? Math.round(el.getBoundingClientRect().width) : null;
  // Hauteur totale réellement occupée = bas du dernier élément visible.
  const bas = (el) => el ? Math.round(el.getBoundingClientRect().bottom) : 0;
  const droite = (el) => el ? Math.round(el.getBoundingClientRect().right) : 0;
  return {
    innerW: window.innerWidth, innerH: window.innerHeight,
    hBarre: rh(barre), hFen: rh(fen), hBloc: rh(bloc), hPanneau: rh(panneau),
    wBloc: rw(bloc), wPanneau: rw(panneau),
    basContenu: Math.max(bas(barre), bas(fen)),
    droiteContenu: Math.max(droite(barre), droite(bloc)),
    docScrollH: doc.scrollHeight, docClientH: doc.clientHeight,
    debordeV: doc.scrollHeight > doc.clientHeight,
    docScrollW: doc.scrollWidth, docClientW: doc.clientWidth,
    debordeH: doc.scrollWidth > doc.clientWidth,
  };
};

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await page.waitForTimeout(300);
  const m = await page.evaluate(MESURE);
  console.log(`[${W}x${H}]`, JSON.stringify(m, null, 0));
  await page.screenshot({ path: path.join(here, `i102_chevalet_${W}x${H}.png`) });
  await browser.close();
})();
