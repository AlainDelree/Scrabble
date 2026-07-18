// Diagnostic issue #108 : le message de résultat (#message-coup), affiché sous
// la barre d'actions de tour au clic sur « Vérifier et calculer », déborde-t-il
// sous le bord bas de la fenêtre plateau maximisée à la résolution cible ?
//
// On rejoue jeu.html/jeu.css/commun.css/jeu.js/commun.js hors-ligne, on force le
// tour humain (zone-jeu visible), on remplit #message-coup d'un texte long (ex.
// « Le mot 'XLE' n'existe pas dans le dictionnaire »), puis on mesure la position
// du bas du message par rapport à la hauteur visible du viewport.
//
// Usage : node scripts/_harness_jeu/mesure_message_108.mjs [largeur] [hauteur]
import pw from '/home/alain/.npm-global/lib/node_modules/playwright/index.js';
const { chromium } = pw;
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '../../src/scrabble/ui/web');
const read = (f) => fs.readFileSync(path.join(web, f), 'utf8');

const W = Number(process.argv[2] || 1280);
const H = Number(process.argv[3] || 760);

// --- État public d'une partie en cours, tour du joueur humain. ---
const L = 'normale';
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
const POSEES = { '7,5':'J','7,6':'O','7,7':'U','7,8':'E','7,9':'R',
  '6,7':'M','8,7':'T','9,7':'S','5,9':'C','6,9':'A','8,9':'E' };
const plateau = CARTE.map((ligne, l) => ligne.map((c, col) => ({
  type: c === '.' ? L : c, lettre: POSEES[l + ',' + col] || null, joker: false })));
const joueurs = [
  { index: 0, nom: 'Alain', humain: true, niveau: null, score: 148, nb_lettres: 7, courant: true, position: 'bas', avatar: 'avatar-01' },
  { index: 1, nom: 'Ordi Nord', humain: false, niveau: 'EXPERT', score: 132, nb_lettres: 7, courant: false, position: 'haut', avatar: 'avatar-05' },
  { index: 2, nom: 'Ordi Ouest', humain: false, niveau: 'INTERMEDIAIRE', score: 97, nb_lettres: 7, courant: false, position: 'gauche', avatar: 'avatar-09' },
  { index: 3, nom: 'Ordi Est', humain: false, niveau: 'FACILE', score: 110, nb_lettres: 6, courant: false, position: 'droite', avatar: 'avatar-12' },
];
const historique = [
  { index: 5, action: 'coup', nom_joueur: 'Ordi Est', humain: false, mot: 'CAVE', score_action: 18, detail: { mots: [{ texte: 'CAVE', score: 18, cases_bonus: [] }], total: 18 } },
  { index: 4, action: 'coup', nom_joueur: 'Alain', humain: true, mot: 'JOUER', score_action: 24, detail: { mots: [{ texte: 'JOUER', score: 24, cases_bonus: [] }], total: 24 } },
];
const etat = {
  id_partie: 1, taille: 15, plateau, joueurs, index_courant: 0, jetons_sac: 42,
  nb_humains: 1, tour_humain: true, index_panneau: 0, terminee: false,
  gagnants: [], historique, en_attente: [{ ligne: 7, colonne: 10, lettre: 'X' }],
};

const mock = `
  window.__THEME__ = 'classique';
  window.pywebview = { api: {
    obtenir_etat_plateau: async () => JSON.parse(JSON.stringify(${JSON.stringify(etat)})),
    obtenir_theme_plateau: async () => 'classique',
    verifier_coup: async () => ({ succes: false, erreur: "Le mot 'XLE' n'existe pas dans le dictionnaire." }),
    poser_mot: async () => ({ succes: true, points: 0 }),
    annuler_pose: async () => ({ succes: true }),
    echanger_tout: async () => ({ succes: true }),
    faire_jouer_ia: async () => ({ succes: true }),
    verifier_mot: async () => ({ succes: true, valide: true, mot: 'TEST' }),
    poser_lettre_en_attente: async () => ({ succes: true }),
    retirer_lettre_en_attente: async () => ({ succes: true }),
    retour_menu: async () => ({ succes: true }),
  } };
`;

const html = read('jeu.html')
  .replace('<link rel="stylesheet" href="commun.css">', `<style>${read('commun.css')}</style>`)
  .replace('<link rel="stylesheet" href="jeu.css">', `<style>${read('jeu.css')}</style>`)
  .replace('<script src="commun.js"></script>', `<script>${mock}</script><script>${read('commun.js')}</script>`)
  .replace('<script src="jeu.js"></script>', `<script>${read('jeu.js')}</script>`);

const MESURE = () => {
  const doc = document.documentElement;
  const msg = document.getElementById('message-coup');
  const zone = document.getElementById('zone-jeu');
  const r = (el) => el ? el.getBoundingClientRect() : null;
  const rm = r(msg), rz = r(zone);
  const round = (x) => x == null ? null : Math.round(x);
  return {
    innerW: window.innerWidth, innerH: window.innerHeight,
    zoneJeuVisible: zone ? !zone.hidden : false,
    msgTexte: msg ? msg.textContent : null,
    msgTop: round(rm && rm.top), msgBottom: round(rm && rm.bottom),
    // Débordement : le bas du message dépasse-t-il le bord bas visible ?
    depasseBas: rm ? Math.round(rm.bottom - window.innerHeight) : null,
    coupe: rm ? (rm.bottom > window.innerHeight + 0.5) : null,
    scrollH: doc.scrollHeight, clientH: doc.clientHeight,
    debordeV: doc.scrollHeight > doc.clientHeight,
  };
};

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  await page.route('**/*', (route) => {
    const url = route.request().url();
    if (url.startsWith('http') && url.includes('avatars/')) {
      const f = path.join(web, url.split('/').slice(-2).join('/'));
      if (fs.existsSync(f)) return route.fulfill({ path: f });
    }
    route.continue();
  });
  await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await page.waitForTimeout(400);
  // Clic réel sur « Vérifier et calculer » (le bouton est activé par un coup en attente).
  await page.evaluate(() => {
    const b = document.getElementById('btn-verifier-coup');
    if (b) b.disabled = false;
  });
  await page.click('#btn-verifier-coup');
  await page.waitForTimeout(200);
  const m = await page.evaluate(MESURE);
  console.log(`[${W}x${H}]`, JSON.stringify(m, null, 0));
  await page.screenshot({ path: path.join(here, `i108_message_${W}x${H}.png`), fullPage: false });
  await browser.close();
})();
