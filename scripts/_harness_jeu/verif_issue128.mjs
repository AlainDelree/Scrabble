// Vérification fonctionnelle temporaire de l'issue #128 (non commité) :
//  1. cliquer un coup PASSÉ dans « Derniers coups » surligne ses cases sur le
//     plateau (.coup-consulte), distinctes du dernier coup réel (.derniere-pose) ;
//  2. la modale de détail reste OUVERTE sans recouvrir une grande partie du
//     plateau (fond transparent + panneau resserré sur le bord droit) ;
//  3. fermer la modale retire .coup-consulte et restaure la surbrillance du
//     dernier coup réel (.derniere-pose sur les cases du coup1).
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

// État public minimal : un DERNIER coup (coup1) en tête, puis un coup PASSÉ
// (coup0) avec ses propres positions + detail (donc cliquable), puis des lignes
// de remplissage. coupN = liste de [ligne, colonne, lettre].
function etat(coup1, coup0) {
  const plateau = Array.from({ length: 15 }, () =>
    Array.from({ length: 15 }, () => ({ type: 'normale', lettre: null, joker: false })));
  plateau[7][7].type = 'centre';
  [...coup1, ...coup0].forEach(([l, c, lettre]) => {
    plateau[l][c] = { type: plateau[l][c].type, lettre, joker: false };
  });
  const tete = { index: 4, action: 'coup', nom_joueur: 'Ordi', humain: false, mot: 'JOUER',
    score_action: 24, positions: coup1.map(([l, c]) => ({ ligne: l, colonne: c })),
    detail: { mots: [{ texte: 'JOUER', score: 24, cases_bonus: [] }], total: 24 } };
  const passe = { index: 3, action: 'coup', nom_joueur: 'Alain', humain: true, mot: 'CAVE',
    score_action: 18, positions: coup0.map(([l, c]) => ({ ligne: l, colonne: c })),
    detail: { mots: [{ texte: 'CAVE', score: 18, cases_bonus: [] }], total: 18 } };
  const remplissage = Array.from({ length: 6 }, (_, i) => ({
    index: 2 - i, action: 'passe', nom_joueur: `Joueur ${i}`, humain: i % 2 === 0,
    mot: null, score_action: 0, positions: [], detail: null }));
  return {
    id_partie: 1, taille: 15, plateau, jetons_sac: 40,
    joueurs: [
      { index: 0, nom: 'Alain', humain: true, niveau: null, score: 10, nb_lettres: 7, courant: true, position: 'bas' },
      { index: 1, nom: 'Ordi', humain: false, niveau: 'EXPERT', score: 8, nb_lettres: 7, courant: false, position: 'haut' },
    ],
    index_courant: 0, terminee: false, gagnants: [], en_attente: [],
    historique: [tete, passe, ...remplissage],
  };
}

const listeCases = (sel) =>
  [...document.querySelectorAll(sel)].map((el) => `${el.dataset.ligne},${el.dataset.colonne}`).sort();

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  const erreurs = [];
  page.on('pageerror', e => erreurs.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') erreurs.push('console: ' + m.text()); });

  await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await page.waitForTimeout(300);

  const coup1 = [[7, 5, 'J'], [7, 6, 'O'], [7, 7, 'U'], [7, 8, 'E'], [7, 9, 'R']]; // dernier coup
  const coup0 = [[5, 2, 'C'], [5, 3, 'A'], [5, 4, 'V'], [5, 5, 'E']];              // coup passé
  await page.evaluate((e) => window.appliquerEtatPlateau(e), etat(coup1, coup0));
  await page.waitForTimeout(400);

  const bilan = {};

  // État initial : seul le dernier coup (coup1) est surligné en .derniere-pose,
  // aucun .coup-consulte.
  bilan.initial = await page.evaluate((c1) => {
    const dp = [...document.querySelectorAll('.case.derniere-pose')]
      .map((el) => `${el.dataset.ligne},${el.dataset.colonne}`).sort();
    return {
      derniere_pose: dp,
      derniere_pose_exact: JSON.stringify(dp) === JSON.stringify(c1.map(([l, c]) => `${l},${c}`).sort()),
      aucun_consulte: document.querySelectorAll('.case.coup-consulte').length === 0,
    };
  }, coup1);

  // Ouvre le menu « Derniers coups » puis clique la ligne du coup PASSÉ (index 3).
  await page.click('.historique-resume');
  await page.waitForTimeout(200);
  await page.click('.historique-ligne[data-index="3"]');
  await page.waitForTimeout(250);

  // 1. Surbrillance du coup consulté sur les cases de coup0, et modale ouverte.
  bilan.clic_coup_passe = await page.evaluate((c0) => {
    const cc = [...document.querySelectorAll('.case.coup-consulte')]
      .map((el) => `${el.dataset.ligne},${el.dataset.colonne}`).sort();
    return {
      coup_consulte: cc,
      coup_consulte_exact: JSON.stringify(cc) === JSON.stringify(c0.map(([l, c]) => `${l},${c}`).sort()),
      modale_ouverte: !document.getElementById('score-modale').hidden,
      // Issue #133 : le coup consulté est désormais un FOND ORANGE PLEIN #ff8f00
      // (case + tuile) et non plus un liseré bleu. On vérifie les deux fonds.
      style: (() => {
        const el = document.querySelector('.case.coup-consulte');
        if (!el) return null;
        const tuile = el.querySelector('.tuile');
        const caseBg = getComputedStyle(el).backgroundColor;
        const tuileBg = tuile ? getComputedStyle(tuile).backgroundColor : null;
        return {
          caseBg, tuileBg,
          orange_plein: caseBg === 'rgb(255, 143, 0)' && tuileBg === 'rgb(255, 143, 0)',
        };
      })(),
    };
  }, coup0);

  // 2. La modale ne recouvre plus une grande partie du plateau : on mesure l'aire
  //    d'intersection panneau/plateau et le fond (doit être transparent).
  bilan.modale_peu_intrusive = await page.evaluate(() => {
    const panneau = document.querySelector('#score-modale .modale-score');
    const plateau = document.getElementById('plateau');
    const a = panneau.getBoundingClientRect();
    const p = plateau.getBoundingClientRect();
    const inter = !(a.right <= p.left || a.left >= p.right || a.bottom <= p.top || a.top >= p.bottom);
    const aireInter = inter
      ? (Math.min(a.right, p.right) - Math.max(a.left, p.left)) *
        (Math.min(a.bottom, p.bottom) - Math.max(a.top, p.top))
      : 0;
    const airePlateau = p.width * p.height;
    const fond = getComputedStyle(document.getElementById('score-modale')).backgroundColor;
    return {
      recouvre_plateau: inter,
      part_plateau_recouverte: Math.round((aireInter / airePlateau) * 100), // en %
      fond_transparent: fond === 'rgba(0, 0, 0, 0)' || fond === 'transparent',
    };
  });
  await page.screenshot({ path: path.join(here, 'i128_coup_consulte.png') });

  // 3. Fermeture de la modale : .coup-consulte retiré, .derniere-pose (coup1) restauré.
  await page.click('#score-fermer');
  await page.waitForTimeout(200);
  bilan.apres_fermeture = await page.evaluate((c1) => {
    const dp = [...document.querySelectorAll('.case.derniere-pose')]
      .map((el) => `${el.dataset.ligne},${el.dataset.colonne}`).sort();
    return {
      aucun_consulte: document.querySelectorAll('.case.coup-consulte').length === 0,
      derniere_pose_restauree: JSON.stringify(dp) === JSON.stringify(c1.map(([l, c]) => `${l},${c}`).sort()),
      modale_fermee: document.getElementById('score-modale').hidden,
    };
  }, coup1);

  // 4. Une passe (positions vide) ne surligne rien de nouveau : on ré-ouvre le
  //    menu et clique une passe (non cliquable → aucun détail, aucune surbrillance).
  bilan.passe_ne_surligne_rien = await page.evaluate(() => {
    // Ligne de remplissage index 2 : action 'passe', detail null → non cliquable.
    const li = document.querySelector('.historique-ligne[data-index="2"]');
    return { non_cliquable: li ? !li.classList.contains('cliquable') : null };
  });

  console.log('ERREURS:', erreurs.length ? erreurs : 'aucune');
  console.log(JSON.stringify(bilan, null, 2));
  await browser.close();
})();
