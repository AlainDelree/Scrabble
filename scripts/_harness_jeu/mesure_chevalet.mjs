// Mesure réelle de la fenêtre chevalet (issue #92, diagnostic point 4/5).
// Rend chevalet.html/.css/.js dans Chromium headless, à la taille exacte de la
// fenêtre pywebview, et mesure : débordement horizontal (scrollWidth), largeur
// naturelle de chaque bloc, et hauteur des deux states (tour humain / tour IA).
// Usage : node scripts/_harness_jeu/mesure_chevalet.mjs [largeur] [hauteur]
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
const H = Number(process.argv[3] || 400);

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
    index_courant: 0, nom: 'Alain', tour_humain: true, terminee: false,
    nb_humains: 1, nb_lettres: 7, lettres, selection: null,
    en_attente: [], joker_demande: null,
  };
}
function etatIA() {
  return {
    index_courant: 1, nom: 'Ordi Nord', tour_humain: false, terminee: false,
    nb_humains: 1, nb_lettres: 7, lettres: [], selection: null,
    en_attente: [], joker_demande: null,
  };
}

const mock = `
  window.pywebview = { api: {
    obtenir_etat_chevalet: async () => (${JSON.stringify(etatHumain())}),
    selectionner_lettre: async () => ({ succes: true }),
    annuler_pose: async () => ({ succes: true }),
    verifier_coup: async () => ({ succes: true, points: 0, detail: null }),
    poser_mot: async () => ({ succes: true, points: 0 }),
    echanger_tout: async () => ({ succes: true }),
    poser_lettre_en_attente: async () => ({ succes: true }),
    debut_deplacement_chevalet: async () => ({ succes: true, x: 0, y: 0 }),
    deplacer_chevalet: async () => ({ succes: true }),
  } };
  window.__ETAT_IA__ = ${JSON.stringify(etatIA())};
  window.__ETAT_HUMAIN__ = ${JSON.stringify(etatHumain())};
`;

let html = read('chevalet.html')
  .replace('<link rel="stylesheet" href="commun.css">', `<style>${communCss}</style>`)
  .replace('<link rel="stylesheet" href="chevalet.css">', `<style>${chevaletCss}</style>`)
  .replace('<script src="commun.js"></script>', `<script>${mock}</script><script>${communJs}</script>`)
  .replace('<script src="chevalet.js"></script>', `<script>${chevaletJs}</script>`);

const MESURE = () => {
  const doc = document.documentElement;
  const fen = document.querySelector('.chevalet-fenetre');
  const zr = document.querySelector('.zone-reflexion');
  const bc = document.querySelector('.bloc-chevalet');
  const bb = document.querySelector('.bloc-brouillon');
  const zj = document.getElementById('zone-jeu');
  const r = (el) => el ? Math.round(el.getBoundingClientRect().width) : null;
  const rh = (el) => el ? Math.round(el.getBoundingClientRect().height) : null;
  return {
    innerW: window.innerWidth, innerH: window.innerHeight,
    docScrollW: doc.scrollWidth, docClientW: doc.clientWidth,
    debordeH: doc.scrollWidth > doc.clientWidth,
    fenScrollW: fen ? fen.scrollWidth : null,
    fenClientW: fen ? fen.clientWidth : null,
    fenDeborde: fen ? fen.scrollWidth > fen.clientWidth + 1 : null,
    fenScrollH: fen ? fen.scrollHeight : null,
    fenClientH: fen ? fen.clientHeight : null,
    fenDebordeV: fen ? fen.scrollHeight > fen.clientHeight + 1 : null,
    wZoneReflexion: r(zr), wBlocChevalet: r(bc), wBlocBrouillon: r(bb), wZoneJeu: r(zj),
    hZoneReflexion: rh(zr), hZoneJeu: rh(zj),
  };
};

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await page.waitForTimeout(300);

  // État tour humain (révélé d'office car nb_humains<=1).
  const humain = await page.evaluate(MESURE);
  console.log(`[${W}x${H}] TOUR HUMAIN`, JSON.stringify(humain, null, 0));
  await page.screenshot({ path: path.join(here, `i92_chevalet_humain_${W}.png`) });

  // Bascule en tour IA (mesure de la hauteur de la zone d'attente).
  await page.evaluate(() => window.appliquerEtatChevalet(window.__ETAT_IA__));
  await page.waitForTimeout(150);
  const ia = await page.evaluate(() => {
    const z = document.getElementById('zone-attente-ia');
    const fen = document.querySelector('.chevalet-fenetre');
    const r = z.getBoundingClientRect();
    return {
      attenteHidden: z.hidden,
      hAttente: Math.round(r.height),
      hFenetre: Math.round(fen.getBoundingClientRect().height),
      fenDebordeV: fen.scrollHeight > fen.clientHeight + 1,
    };
  });
  console.log(`[${W}x${H}] TOUR IA`, JSON.stringify(ia, null, 0));
  await page.screenshot({ path: path.join(here, `i92_chevalet_ia_${W}.png`) });

  await browser.close();
})();
