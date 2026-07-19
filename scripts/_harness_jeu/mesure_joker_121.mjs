// Mesure headless de la modale de choix de lettre du joker (issue #121).
// Objectif : dans la fenêtre chevalet (480×175 depuis #106), la grille A-Z des
// 26 lettres a besoin de bien plus que 175 px de haut ; la modale débordait
// (dernières lignes V-W-X-Y-Z invisibles) et le bouton Annuler disparaissait.
// On ouvre réellement la modale (via joker_demande) puis on mesure :
//   - hauteurNecessaire : hauteur intrinsèque du contenu (titre + grille + bouton)
//     s'il n'était pas borné (scrollHeight du contenu) → confirme le déficit ;
//   - debordeModale : le contenu déborde-t-il de la fenêtre ?
//   - annulerVisible : le bouton Annuler est-il entièrement dans la fenêtre ?
//   - derniereLettreAccessible : peut-on atteindre le « Z » en scrollant la grille
//     sans que le bouton Annuler ne soit poussé hors champ ?
// Usage : node scripts/_harness_jeu/mesure_joker_121.mjs [largeur] [hauteur]
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

// État avec une demande de joker en cours : appliquerEtatChevalet ouvre alors la
// modale de choix de lettre (ouvrirModaleJoker).
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
  const annuler = document.getElementById('joker-annuler');
  const lettresBtn = grille ? Array.from(grille.querySelectorAll('.joker-lettre')) : [];
  const lettreZ = lettresBtn[lettresBtn.length - 1] || null;
  const r = (el) => el ? el.getBoundingClientRect() : null;
  const cR = r(contenu), gR = r(grille), aR = r(annuler), zR = r(lettreZ);
  const innerH = window.innerHeight;
  const dansFenetre = (rect) => rect && rect.top >= -0.5 && rect.bottom <= innerH + 0.5;
  return {
    modaleOuverte: contenu ? !document.getElementById('joker-modale').hidden : false,
    nbLettres: lettresBtn.length,
    innerH,
    // Hauteur qu'occuperait le contenu si rien ne le bornait (grille non scrollable).
    hauteurContenuScroll: contenu ? contenu.scrollHeight : null,
    hauteurContenuVisible: cR ? Math.round(cR.height) : null,
    contenuDeborde: cR ? Math.round(cR.bottom) > innerH + 1 || Math.round(cR.top) < -1 : null,
    grilleScrollable: grille ? grille.scrollHeight > grille.clientHeight + 1 : null,
    grilleScrollH: grille ? grille.scrollHeight : null,
    grilleClientH: grille ? grille.clientHeight : null,
    annulerVisible: dansFenetre(aR),
    annulerBottom: aR ? Math.round(aR.bottom) : null,
    lettreZbottom: zR ? Math.round(zR.bottom) : null,
    debordeV: doc.scrollHeight > doc.clientHeight,
  };
};

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await page.waitForTimeout(400);

  const avant = await page.evaluate(MESURE);
  console.log(`[${W}x${H}] AVANT scroll grille :`, JSON.stringify(avant, null, 0));
  await page.screenshot({ path: path.join(here, `i121_joker_${W}x${H}_initial.png`) });

  // On amène le « Z » dans la vue (comme le ferait un clic réel) et on vérifie qu'il
  // devient pleinement visible dans la grille ET que le bouton Annuler reste visible.
  const apres = await page.evaluate(() => {
    const grille = document.getElementById('joker-grille');
    const annuler = document.getElementById('joker-annuler');
    const lettresBtn = Array.from(grille.querySelectorAll('.joker-lettre'));
    const z = lettresBtn[lettresBtn.length - 1];
    z.scrollIntoView({ block: 'nearest' });
    const zR = z.getBoundingClientRect();
    const aR = annuler.getBoundingClientRect();
    const gR = grille.getBoundingClientRect();
    const innerH = window.innerHeight;
    // Le Z est « accessible » s'il est entièrement dans la zone visible de la grille.
    const zDansGrille = zR.top >= gR.top - 0.5 && zR.bottom <= gR.bottom + 0.5;
    return {
      zVisibleApresScroll: zDansGrille && zR.bottom <= innerH + 0.5,
      zTop: Math.round(zR.top), zBottom: Math.round(zR.bottom),
      grilleTop: Math.round(gR.top), grilleBottom: Math.round(gR.bottom),
      annulerVisibleApresScroll: aR.top >= -0.5 && aR.bottom <= innerH + 0.5,
      annulerBottom: Math.round(aR.bottom),
      innerH,
    };
  });
  console.log(`[${W}x${H}] APRÈS scroll grille :`, JSON.stringify(apres, null, 0));
  await page.screenshot({ path: path.join(here, `i121_joker_${W}x${H}_scrolle.png`) });

  await browser.close();
})();
