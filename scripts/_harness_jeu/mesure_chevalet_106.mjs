// Mesure fine de la fenêtre chevalet épurée (issue #106, suite #104/#102).
// Deux objectifs #106, mesurés ici sans lancer de fenêtre graphique :
//   1. Symétrie verticale : l'espace vert (fond de fenêtre) au-dessus du cadre
//      blanc (.bloc-panneau) — entre la barre de déplacement et le cadre — doit
//      être visuellement égal à celui en dessous (entre le cadre et le bas de la
//      fenêtre). On mesure gapHaut = bloc.top - barre.bottom et
//      gapBas = innerH - bloc.bottom.
//   2. Largeur : réduire le vide à droite de la dernière case. On mesure
//      videDroite = (bord droit intérieur du cadre) - (bord droit de la rangée).
// On rejoue aussi la largeur intrinsèque de la rangée (460px paddings compris),
// plancher sous lequel la rangée de 9 cases serait compromise.
// Usage : node scripts/_harness_jeu/mesure_chevalet_106.mjs [largeur] [hauteur]
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
  // Largeur intrinsèque de la rangée de 9 cases (7 lettres + 2 vides) + gaps.
  const largeurEnfants = (el) => {
    if (!el) return null;
    let total = 0;
    for (const c of el.children) total += c.getBoundingClientRect().width;
    const style = getComputedStyle(el);
    const gap = parseFloat(style.columnGap || style.gap || '0') || 0;
    total += gap * Math.max(0, el.children.length - 1);
    return Math.round(total);
  };
  const rangee = largeurEnfants(panneau);
  const stBloc = bloc ? getComputedStyle(bloc) : null;
  const padBlocX = stBloc ? parseFloat(stBloc.paddingLeft) + parseFloat(stBloc.paddingRight) : 0;
  const stFen = fen ? getComputedStyle(fen) : null;
  const padFenX = stFen ? parseFloat(stFen.paddingLeft) + parseFloat(stFen.paddingRight) : 0;
  const largeurUtileRangee = Math.round(rangee + padBlocX + padFenX);
  const barreRect = barre ? barre.getBoundingClientRect() : null;
  const blocRect = bloc ? bloc.getBoundingClientRect() : null;
  const panRect = panneau ? panneau.getBoundingClientRect() : null;
  // Espaces verts verticaux autour du cadre blanc :
  const gapHaut = (blocRect && barreRect) ? Math.round(blocRect.top - barreRect.bottom) : null;
  const gapBas = blocRect ? Math.round(window.innerHeight - blocRect.bottom) : null;
  // Vide horizontal à droite : du bord droit de la DERNIÈRE case (dernier enfant du
  // panneau, aligné à gauche) au bord droit intérieur du cadre (bloc.right - padding
  // droit du bloc). NB : mesurer panneau.right serait faux, le conteneur flex
  // s'étirant sur toute la largeur du cadre.
  const padBlocR = stBloc ? parseFloat(stBloc.paddingRight) : 0;
  let derniereCaseDroite = null;
  if (panneau) {
    for (const c of panneau.children) {
      const r = c.getBoundingClientRect().right;
      if (derniereCaseDroite == null || r > derniereCaseDroite) derniereCaseDroite = r;
    }
  }
  const videDroite = (derniereCaseDroite != null && blocRect)
    ? Math.round((blocRect.right - padBlocR) - derniereCaseDroite) : null;
  return {
    innerW: window.innerWidth, innerH: window.innerHeight,
    rangeeCases: rangee, largeurUtileRangee,
    hBarre: rh(barre), hBloc: rh(bloc), wPanneauTitre: rw(document.querySelector('.panneau-titre')),
    basContenu: blocRect ? Math.round(blocRect.bottom) : 0,
    gapHaut, gapBas, symetrieV: (gapHaut != null && gapBas != null) ? Math.abs(gapHaut - gapBas) : null,
    videDroite,
    debordeV: doc.scrollHeight > doc.clientHeight,
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
  await page.screenshot({ path: path.join(here, `i106_chevalet_${W}x${H}.png`) });
  await browser.close();
})();
