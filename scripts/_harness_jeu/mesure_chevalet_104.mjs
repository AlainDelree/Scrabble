// Mesure fine de la fenêtre chevalet épurée (issue #104, suite #102).
// Objectif #104 : resserrer encore la fenêtre (620×190 laissait un vide notable
// à droite et un peu sous la rangée). On mesure ici non plus la largeur « étirée »
// du bloc (qui remplit la fenêtre) mais la largeur INTRINSÈQUE réellement réclamée
// par chaque contenu :
//   - la rangée de 9 cases (7 lettres + 2 vides) = contenu utile pivot ;
//   - la barre de déplacement (titre + poignée) ;
//   - le titre du panneau, autorisé à passer sur plusieurs lignes.
// On mesure dans une fenêtre volontairement large (1200) pour lire les largeurs
// naturelles sans contrainte, puis on rejoue à la taille candidate pour vérifier
// l'absence de débordement / de vide.
// Usage : node scripts/_harness_jeu/mesure_chevalet_104.mjs [largeur] [hauteur]
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

const W = Number(process.argv[2] || 1200);
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
  const rw = (el) => el ? Math.round(el.getBoundingClientRect().width) : null;
  const rh = (el) => el ? Math.round(el.getBoundingClientRect().height) : null;
  // Largeur intrinsèque : somme réelle des enfants du flex (rangée de cases) ou
  // scrollWidth (contenu qui déborderait s'il était contraint).
  const largeurEnfants = (el) => {
    if (!el) return null;
    let max = 0;
    for (const c of el.children) {
      const r = c.getBoundingClientRect();
      max = Math.max(max, r.right);
    }
    const base = el.getBoundingClientRect().left;
    // largeur occupée = de left du parent au right du dernier enfant
    let total = 0;
    for (const c of el.children) total += c.getBoundingClientRect().width;
    // + gaps
    const style = getComputedStyle(el);
    const gap = parseFloat(style.columnGap || style.gap || '0') || 0;
    total += gap * Math.max(0, el.children.length - 1);
    return Math.round(total);
  };
  // Largeur intrinsèque de la barre : titre + poignée + gap + paddings.
  const barreIntrinseque = () => {
    if (!barre) return null;
    const st = getComputedStyle(barre);
    const padX = parseFloat(st.paddingLeft) + parseFloat(st.paddingRight);
    const gap = parseFloat(st.columnGap || st.gap || '0') || 0;
    let contenu = 0, n = 0;
    for (const c of barre.children) { contenu += c.getBoundingClientRect().width; n++; }
    contenu += gap * Math.max(0, n - 1);
    return Math.round(contenu + padX);
  };
  // Largeur intrinsèque du bloc-panneau à partir de sa rangée de cases :
  // rangée + paddings horizontaux du bloc + paddings de la fenêtre.
  const rangee = largeurEnfants(panneau);
  const stBloc = bloc ? getComputedStyle(bloc) : null;
  const padBlocX = stBloc ? parseFloat(stBloc.paddingLeft) + parseFloat(stBloc.paddingRight) : 0;
  const stFen = fen ? getComputedStyle(fen) : null;
  const padFenX = stFen ? parseFloat(stFen.paddingLeft) + parseFloat(stFen.paddingRight) : 0;
  const largeurUtileRangee = Math.round(rangee + padBlocX + padFenX);
  return {
    innerW: window.innerWidth, innerH: window.innerHeight,
    // Largeurs intrinsèques (dans fenêtre large, sans contrainte) :
    rangeeCases: rangee,               // 9 cases + gaps
    largeurUtileRangee,                // rangée + paddings bloc + fenêtre
    barreIntrinseque: barreIntrinseque(),
    wPanneauTitre: rw(document.querySelector('.panneau-titre')),
    // Hauteur :
    hBarre: rh(barre), hBloc: rh(bloc), hPanneau: rh(panneau),
    basContenu: Math.max(
      barre ? Math.round(barre.getBoundingClientRect().bottom) : 0,
      bloc ? Math.round(bloc.getBoundingClientRect().bottom) : 0
    ),
    // Débordements à la taille courante :
    debordeV: doc.scrollHeight > doc.clientHeight,
    debordeH: doc.scrollWidth > doc.clientWidth,
    docScrollH: doc.scrollHeight, docClientH: doc.clientHeight,
    docScrollW: doc.scrollWidth, docClientW: doc.clientWidth,
  };
};

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await page.waitForTimeout(300);
  const m = await page.evaluate(MESURE);
  console.log(`[${W}x${H}]`, JSON.stringify(m, null, 0));
  await page.screenshot({ path: path.join(here, `i104_chevalet_${W}x${H}.png`) });
  await browser.close();
})();
