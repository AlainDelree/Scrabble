// Vérification headless du sélecteur de lettre du joker repositionné sur la case
// du plateau (issue #201). On mocke l'API pywebview courante, on charge le VRAI
// jeu.html/jeu.css/jeu.js (+ commun), puis pour plusieurs positions de case
// (centre, coins, bords) on déclenche le popover et on mesure :
//   - le popover s'ouvre bien (26 lettres rendues, aucune tronquée à droite) ;
//   - il reste ENTIÈREMENT dans le viewport (aucun bord hors écran).
// Usage : node scripts/_harness_jeu/verif_joker_201.mjs [largeur] [hauteur]
import pw from '/home/alain/.npm-global/lib/node_modules/playwright/index.js';
const { chromium } = pw;
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '../../src/scrabble/ui/web');
const read = (f) => fs.readFileSync(path.join(web, f), 'utf8');
const communCss = read('commun.css');
const communJs = read('commun.js');
const jeuCss = read('jeu.css');
const jeuJs = read('jeu.js');

const W = Number(process.argv[2] || 1000);
const H = Number(process.argv[3] || 750);

// Plateau 15x15 vide (types 'normale'), sauf le centre.
const plateau = Array.from({ length: 15 }, (_, l) =>
  Array.from({ length: 15 }, (_, c) => ({
    type: (l === 7 && c === 7) ? 'centre' : 'normale', lettre: null, joker: false,
  })));

const joueurs = [
  { index: 0, nom: 'Alain', humain: true, niveau: null, score: 0,
    nb_lettres: 7, courant: true, position: 'bas', avatar: 'avatar-01' },
];
const etatPlateau = {
  taille: 15, plateau, joueurs, en_attente: [], historique: [],
  jetons_sac: 42, terminee: false, gagnants: [], index_courant: 0,
};
const chevalet = {
  mon_tour: true, selection: 6, mode_echange: false, selection_echange: [],
  en_attente: [], lettres: [
    { lettre: 'A', valeur: 1, joker: false }, { lettre: 'E', valeur: 1, joker: false },
    { lettre: 'S', valeur: 1, joker: false }, { lettre: 'R', valeur: 1, joker: false },
    { lettre: 'T', valeur: 1, joker: false }, { lettre: 'K', valeur: 10, joker: false },
    { lettre: '*', valeur: 0, joker: true },
  ],
};

const mock = `
  window.__THEME__ = 'classique';
  window.pywebview = { api: {
    obtenir_tirage_ordre: async () => null,
    obtenir_theme_plateau: async () => 'classique',
    obtenir_etat_plateau: async () => (${JSON.stringify(etatPlateau)}),
    obtenir_etat_chevalet: async () => (${JSON.stringify(chevalet)}),
    // Toute pose sur case vide déclenche le sélecteur de joker (lettre * sélectionnée).
    poser_lettre_en_attente: async (l, c) => ({ joker_requis: true, ligne: l, colonne: c, index: 6 }),
    selectionner_lettre: async () => ({ succes: true }),
    journaliser_mesure_fenetre: async () => ({ succes: true }),
  } };
`;

let html = read('jeu.html')
  .replace('<link rel="stylesheet" href="commun.css">', `<style>${communCss}</style>`)
  .replace('<link rel="stylesheet" href="jeu.css">', `<style>${jeuCss}</style>`)
  .replace('<script src="commun.js"></script>', `<script>${mock}</script><script>${communJs}</script>`)
  .replace('<script src="jeu.js"></script>', `<script>${jeuJs}</script>`);

// Ouvre le popover sur la case (l,c) en cliquant dessus, attend le rendu, mesure.
const MESURER_CASE = async (page, l, c) => {
  await page.evaluate(([l, c]) => {
    const caseEl = document.querySelector(`.case[data-ligne="${l}"][data-colonne="${c}"]`);
    caseEl.click();
  }, [l, c]);
  await page.waitForTimeout(150);
  return page.evaluate(() => {
    const pop = document.getElementById('joker-popover');
    const grille = document.getElementById('joker-grille');
    const btns = grille ? Array.from(grille.querySelectorAll('.joker-lettre')) : [];
    const r = pop.getBoundingClientRect();
    const vw = window.innerWidth, vh = window.innerHeight;
    const tronques = btns.filter((b) => {
      const br = b.getBoundingClientRect();
      return br.right > r.right + 0.5 || br.right > vw + 0.5 || br.left < r.left - 0.5;
    }).map((b) => b.textContent.trim());
    return {
      ouvert: !pop.hidden,
      nbLettres: btns.length,
      nbTronques: tronques.length,
      tronques,
      popover: { left: Math.round(r.left), top: Math.round(r.top),
                 right: Math.round(r.right), bottom: Math.round(r.bottom),
                 w: Math.round(r.width), h: Math.round(r.height) },
      viewport: { w: vw, h: vh },
      dansViewport: r.left >= -0.5 && r.top >= -0.5
                    && r.right <= vw + 0.5 && r.bottom <= vh + 0.5,
    };
  });
};

// Referme le popover (Échap) entre deux mesures.
const FERMER = async (page) => {
  await page.keyboard.press('Escape');
  await page.waitForTimeout(120);
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
  const erreurs = [];
  page.on('pageerror', (e) => erreurs.push(String(e)));
  await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await page.waitForTimeout(600);

  // Cases testées : centre, 4 coins, bords — celles où le clamp est sollicité.
  const cases = [
    ['centre', 7, 7], ['coin haut-gauche', 0, 0], ['coin haut-droite', 0, 14],
    ['coin bas-gauche', 14, 0], ['coin bas-droite', 14, 14],
    ['bord droit', 7, 14], ['bord bas', 14, 7],
  ];
  let okGlobal = true;
  for (const [nom, l, c] of cases) {
    const m = await MESURER_CASE(page, l, c);
    const ok = m.ouvert && m.nbLettres === 26 && m.nbTronques === 0 && m.dansViewport;
    okGlobal = okGlobal && ok;
    console.log(`${ok ? '✅' : '❌'} [${nom}] l=${l} c=${c} :`, JSON.stringify(m));
    if (nom === 'centre') {
      await page.screenshot({ path: path.join(here, `i201_joker_${W}x${H}_centre.png`) });
    }
    await FERMER(page);
  }
  if (erreurs.length) {
    okGlobal = false;
    console.log('❌ Erreurs JS :', erreurs);
  }
  console.log(okGlobal ? '\n✅ TOUT OK' : '\n❌ ÉCHEC');
  await browser.close();
  process.exit(okGlobal ? 0 : 1);
})();
