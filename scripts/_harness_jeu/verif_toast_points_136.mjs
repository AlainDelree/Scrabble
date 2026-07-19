// Vérification fonctionnelle temporaire de l'issue #136 (non commité) :
//  1. après un coup HUMAIN marquant, un toast « +X points » apparaît près du
//     panneau du joueur (bon montant, bon côté) ;
//  2. après un coup ORDINATEUR marquant, idem près de son panneau ;
//  3. une passe / un échange (0 point) n'affiche AUCUN toast ;
//  4. le toast disparaît automatiquement au bout de ~3 s ;
//  5. un coup Scrabble (bonus_scrabble) affiche À LA FOIS le toast « +X points »
//     et le toast « Scrabble !! », indépendamment.
import pw from '/home/alain/.npm-global/lib/node_modules/playwright/index.js';
const { chromium } = pw;
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '../../src/scrabble/ui/web');
const css = fs.readFileSync(path.join(web, 'jeu.css'), 'utf8');
const js = fs.readFileSync(path.join(web, 'jeu.js'), 'utf8');
const commCss = fs.readFileSync(path.join(web, 'commun.css'), 'utf8');
const commJs = fs.readFileSync(path.join(web, 'commun.js'), 'utf8');
const mock = fs.readFileSync(path.join(here, 'mock.js'), 'utf8');
const html = fs.readFileSync(path.join(web, 'jeu.html'), 'utf8')
  .replace('<link rel="stylesheet" href="commun.css">', `<style>${commCss}</style>`)
  .replace('<link rel="stylesheet" href="jeu.css">', `<style>${css}</style>`)
  .replace('<script src="commun.js"></script>', `<script>${commJs}</script>`)
  .replace('<script src="jeu.js"></script>',
    `<script>window.__THEME__='classique';${mock}</script><script>${js}</script>`);

// Fabrique un état public : `tete` est le coup le plus récent (celui qui déclenche
// l'animation/le toast). joueurAuteur = index du joueur qui a joué ce coup.
function etat({ index, joueurAuteur, action, score, positions, bonus }) {
  const plateau = Array.from({ length: 15 }, () =>
    Array.from({ length: 15 }, () => ({ type: 'normale', lettre: null, joker: false })));
  plateau[7][7].type = 'centre';
  (positions || []).forEach(({ ligne, colonne }) => {
    plateau[ligne][colonne] = { type: plateau[ligne][colonne].type, lettre: 'A', joker: false };
  });
  const noms = { 0: 'Alain', 1: 'Ordi Nord', 2: 'Ordi Ouest', 3: 'Ordi Est' };
  const tete = {
    index, index_joueur: joueurAuteur, action,
    nom_joueur: noms[joueurAuteur], humain: joueurAuteur === 0,
    mot: action === 'coup' ? 'MOT' : null,
    score_action: score, positions: positions || [],
    detail: action === 'coup'
      ? { mots: [{ texte: 'MOT', score, cases_bonus: [] }], total: score,
          bonus_scrabble: bonus ? 50 : 0 }
      : null,
  };
  const bourrage = Array.from({ length: 6 }, (_, i) => ({
    index: -1 - i, index_joueur: i % 4, action: 'passe',
    nom_joueur: noms[i % 4], humain: (i % 4) === 0, mot: null,
    score_action: 0, positions: [], detail: null }));
  return {
    id_partie: 1, taille: 15, plateau, jetons_sac: 40, en_attente: [],
    joueurs: [
      { index: 0, nom: 'Alain', humain: true, niveau: null, score: 50, nb_lettres: 7, courant: true, position: 'bas', avatar: 'avatar-01' },
      { index: 1, nom: 'Ordi Nord', humain: false, niveau: 'EXPERT', score: 40, nb_lettres: 7, courant: false, position: 'haut', avatar: 'avatar-05' },
      { index: 2, nom: 'Ordi Ouest', humain: false, niveau: 'FACILE', score: 30, nb_lettres: 7, courant: false, position: 'gauche', avatar: 'avatar-09' },
      { index: 3, nom: 'Ordi Est', humain: false, niveau: 'FACILE', score: 20, nb_lettres: 7, courant: false, position: 'droite', avatar: 'avatar-12' },
    ],
    index_courant: 0, terminee: false, gagnants: [],
    historique: [tete, ...bourrage],
  };
}

// Lit l'état des toasts « +X points » présents et leur position relative au
// panneau du côté donné.
async function lireToast(page, cote) {
  return page.evaluate((cote) => {
    const w = document.querySelector('#points-toasts .points-toast-ancre');
    if (!w) return { present: false };
    const toast = w.querySelector('.points-toast');
    const tr = toast.getBoundingClientRect();
    const slot = document.getElementById('slot-' + cote);
    const panneau = slot && slot.querySelector('.panneau-joueur');
    const pr = panneau ? panneau.getBoundingClientRect() : null;
    // « près du panneau » : centre du toast à moins de ~140 px du panneau.
    let distance = null;
    if (pr) {
      const tx = tr.left + tr.width / 2, ty = tr.top + tr.height / 2;
      const dx = Math.max(pr.left - tx, 0, tx - pr.right);
      const dy = Math.max(pr.top - ty, 0, ty - pr.bottom);
      distance = Math.round(Math.hypot(dx, dy));
    }
    return {
      present: true,
      texte: toast.textContent,
      classe: w.className,
      distance_au_panneau: distance,
      pres_du_panneau: distance !== null && distance <= 140,
    };
  }, cote);
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  const erreurs = [];
  page.on('pageerror', e => erreurs.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') erreurs.push('console: ' + m.text()); });

  await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await page.waitForTimeout(300);

  const bilan = {};

  // Premier état : enregistre juste l'index de tête (aucune animation, 1re appli).
  await page.evaluate((e) => window.appliquerEtatPlateau(e),
    etat({ index: 0, joueurAuteur: 3, action: 'passe', score: 0, positions: [] }));
  await page.waitForTimeout(200);

  // --- 1. Coup HUMAIN marquant (joueur 0, panneau 'bas', +24 sur 3 cases) ---
  await page.evaluate((e) => window.appliquerEtatPlateau(e), etat({
    index: 1, joueurAuteur: 0, action: 'coup', score: 24,
    positions: [{ ligne: 7, colonne: 6 }, { ligne: 7, colonne: 7 }, { ligne: 7, colonne: 8 }],
  }));
  // animerPose dure ~2,5 s : le toast apparaît APRÈS. On attend puis on lit.
  await page.waitForTimeout(3200);
  bilan.coup_humain = await lireToast(page, 'bas');
  await page.screenshot({ path: path.join(here, 'i136_toast_humain.png') });

  // Laisse le toast humain expirer (durée 3 s) avant le test suivant.
  await page.waitForTimeout(1200);
  bilan.humain_expire = await lireToast(page, 'bas');

  // --- 2. Coup ORDINATEUR marquant (joueur 1, panneau 'haut', +30) ---
  await page.evaluate((e) => window.appliquerEtatPlateau(e), etat({
    index: 2, joueurAuteur: 1, action: 'coup', score: 30,
    positions: [{ ligne: 5, colonne: 5 }, { ligne: 5, colonne: 6 }],
  }));
  await page.waitForTimeout(3200);
  bilan.coup_ia = await lireToast(page, 'haut');
  await page.screenshot({ path: path.join(here, 'i136_toast_ia.png') });
  await page.waitForTimeout(1200);

  // --- 3. PASSE : aucun toast ---
  await page.evaluate((e) => window.appliquerEtatPlateau(e), etat({
    index: 3, joueurAuteur: 2, action: 'passe', score: 0, positions: [],
  }));
  await page.waitForTimeout(600);
  bilan.passe_aucun_toast = await lireToast(page, 'gauche');

  // --- 3bis. ÉCHANGE : aucun toast ---
  await page.evaluate((e) => window.appliquerEtatPlateau(e), etat({
    index: 4, joueurAuteur: 3, action: 'echange', score: 0, positions: [],
  }));
  await page.waitForTimeout(600);
  bilan.echange_aucun_toast = await lireToast(page, 'droite');

  // --- 5. Coup SCRABBLE : toast « +X points » ET toast Scrabble, indépendants ---
  await page.evaluate((e) => window.appliquerEtatPlateau(e), etat({
    index: 5, joueurAuteur: 0, action: 'coup', score: 76, bonus: true,
    positions: Array.from({ length: 7 }, (_, i) => ({ ligne: 9, colonne: 4 + i })),
  }));
  await page.waitForTimeout(3500);
  bilan.scrabble = {
    points: await lireToast(page, 'bas'),
    scrabble_toast_present: await page.evaluate(
      () => Boolean(document.querySelector('#scrabble-fete .scrabble-toast'))),
  };

  console.log('ERREURS:', erreurs.length ? erreurs : 'aucune');
  console.log(JSON.stringify(bilan, null, 2));
  await browser.close();
})();
