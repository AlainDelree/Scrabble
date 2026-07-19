// Vérification visuelle/fonctionnelle temporaire de l'issue #125 (non commité) :
//  1. barre du haut réorganisée (Derniers coups à gauche, Sac à droite) ;
//  2. menu déroulant « Derniers coups » qui ne recouvre plus le plateau ;
//  3. surbrillance persistante (.derniere-pose) sur les cases du dernier coup,
//     retirée/réappliquée quand un nouveau coup est joué.
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

// Construit un état public minimal mais valide, avec un dernier coup dont on
// connaît les positions. `coup` = liste de [ligne, colonne, lettre].
function etatAvecCoup(coup, index) {
  const plateau = Array.from({ length: 15 }, () =>
    Array.from({ length: 15 }, () => ({ type: 'normale', lettre: null, joker: false })));
  // Case centrale typée pour vérifier la lisibilité de la surbrillance dessus.
  plateau[7][7].type = 'centre';
  coup.forEach(([l, c, lettre]) => { plateau[l][c] = { type: plateau[l][c].type, lettre, joker: false }; });
  // Quelques tuiles d'un tour ANTÉRIEUR (ne doivent PAS être surlignées).
  plateau[5][5] = { type: 'normale', lettre: 'A', joker: false };
  plateau[5][6] = { type: 'normale', lettre: 'X', joker: false };
  // Dernier coup en tête, PUIS 7 entrées de remplissage pour un menu déroulant
  // pleine hauteur (8 lignes) : le pire cas pour un éventuel chevauchement du
  // menu « Derniers coups » avec le plateau.
  const tete = { index, action: 'coup', nom_joueur: 'Ordi', humain: false, mot: 'MOT', score_action: 20,
    positions: coup.map(([l, c]) => ({ ligne: l, colonne: c })),
    detail: { mots: [{ texte: 'MOT', score: 20, cases_bonus: [] }], total: 20 } };
  const remplissage = Array.from({ length: 7 }, (_, i) => ({
    index: index - 1 - i, action: 'coup', nom_joueur: `Joueur ${i}`, humain: i % 2 === 0,
    mot: 'MOTMOT', score_action: 12, positions: [], detail: null }));
  return {
    id_partie: 1, taille: 15, plateau, jetons_sac: 40,
    joueurs: [
      { index: 0, nom: 'Alain', humain: true, niveau: null, score: 10, nb_lettres: 7, courant: true, position: 'bas' },
      { index: 1, nom: 'Ordi', humain: false, niveau: 'EXPERT', score: 8, nb_lettres: 7, courant: false, position: 'haut' },
    ],
    index_courant: 0, terminee: false, gagnants: [], en_attente: [],
    historique: [tete, ...remplissage],
  };
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  const erreurs = [];
  page.on('pageerror', e => erreurs.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') erreurs.push('console: ' + m.text()); });

  await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await page.waitForTimeout(300);

  // Premier coup : « JOUER » horizontal, ligne 7, colonnes 5→9.
  const coup1 = [[7, 5, 'J'], [7, 6, 'O'], [7, 7, 'U'], [7, 8, 'E'], [7, 9, 'R']];
  await page.evaluate((etat) => window.appliquerEtatPlateau(etat), etatAvecCoup(coup1, 4));
  await page.waitForTimeout(400);

  const bilan = {};

  // 1. Disposition de la barre : Derniers coups à gauche, puis Sac,
  //    Resynchroniser, Retour au menu à droite (dans cet ordre).
  const boites = await page.evaluate(() => {
    const b = (sel) => {
      const el = document.querySelector(sel);
      const r = el.getBoundingClientRect();
      return { x: Math.round(r.x), right: Math.round(r.right) };
    };
    return {
      hist: b('.historique-menu'),
      sac: b('.sac'),
      resync: b('#btn-rafraichir'),
      retour: b('#btn-retour-menu'),
    };
  });
  bilan.ordre_hist_avant_sac = boites.hist.right < boites.sac.x;
  bilan.ordre_sac_avant_resync = boites.sac.right <= boites.resync.x;
  bilan.ordre_resync_avant_retour = boites.resync.right <= boites.retour.x;
  // « Derniers coups » est le tout premier élément de la barre (à gauche), le sac
  // ouvre le groupe droit : un grand vide (margin-left:auto) les sépare.
  bilan.hist_est_premier = boites.hist.x < boites.sac.x
    && boites.hist.x < boites.resync.x && boites.hist.x < boites.retour.x;
  bilan.grand_vide_median = (boites.sac.x - boites.hist.right) > 300;
  bilan._boites = boites;

  // 2. Ouverture du menu « Derniers coups » : ne doit pas recouvrir le plateau.
  await page.click('.historique-resume');
  await page.waitForTimeout(250);
  const chevauche = await page.evaluate(() => {
    const liste = document.querySelector('.historique-liste');
    const plateau = document.getElementById('plateau');
    const a = liste.getBoundingClientRect();
    const p = plateau.getBoundingClientRect();
    const inter = !(a.right <= p.left || a.left >= p.right || a.bottom <= p.top || a.top >= p.bottom);
    const aireInter = inter
      ? (Math.min(a.right, p.right) - Math.max(a.left, p.left)) *
        (Math.min(a.bottom, p.bottom) - Math.max(a.top, p.top))
      : 0;
    return { inter, aireInter: Math.round(aireInter),
             liste: { l: Math.round(a.left), r: Math.round(a.right) },
             plateau: { l: Math.round(p.left), r: Math.round(p.right) } };
  });
  bilan.menu_ne_recouvre_pas_plateau = !chevauche.inter;
  bilan._menu = chevauche;
  await page.screenshot({ path: path.join(here, 'i125_barre_menu_ouvert.png') });
  await page.click('.historique-resume'); // referme
  await page.waitForTimeout(150);

  // 3. Surbrillance : .derniere-pose sur les 5 cases du coup1, et NULLE PART ailleurs.
  bilan.surbrillance = await page.evaluate((coup) => {
    const attendu = new Set(coup.map(([l, c]) => `${l},${c}`));
    const cases = [...document.querySelectorAll('.case.derniere-pose')]
      .map((el) => `${el.dataset.ligne},${el.dataset.colonne}`).sort();
    const attenduTri = [...attendu].sort();
    // Une case antérieure (5,5) occupée mais hors dernier coup ne doit pas l'avoir.
    const anterieure = document.querySelector('.case[data-ligne="5"][data-colonne="5"]');
    return {
      cases, attendu: attenduTri,
      exact: JSON.stringify(cases) === JSON.stringify(attenduTri),
      anterieure_non_surlignee: !anterieure.classList.contains('derniere-pose'),
    };
  }, coup1);

  // Style effectif appliqué (box-shadow non vide) sur une case surlignée.
  bilan.surbrillance_style = await page.evaluate(() => {
    const el = document.querySelector('.case.derniere-pose');
    return el ? getComputedStyle(el).boxShadow.slice(0, 40) : null;
  });

  // 4. Nouveau coup joué : l'ancienne surbrillance disparaît, la nouvelle apparaît.
  const coup2 = [[8, 7, 'S'], [9, 7, 'A'], [10, 7, 'C']];
  await page.evaluate((etat) => window.appliquerEtatPlateau(etat), etatAvecCoup(coup2, 5));
  await page.waitForTimeout(500);
  bilan.surbrillance_apres_nouveau_coup = await page.evaluate((coup) => {
    const attendu = new Set(coup.map(([l, c]) => `${l},${c}`)); // coup2
    const cases = [...document.querySelectorAll('.case.derniere-pose')]
      .map((el) => `${el.dataset.ligne},${el.dataset.colonne}`).sort();
    // Une case de l'ANCIEN coup (7,5) ne doit plus être surlignée.
    const ancienne = document.querySelector('.case[data-ligne="7"][data-colonne="5"]');
    return {
      cases, attendu: [...attendu].sort(),
      exact: JSON.stringify(cases) === JSON.stringify([...attendu].sort()),
      ancienne_non_surlignee: !ancienne.classList.contains('derniere-pose'),
    };
  }, coup2);
  await page.screenshot({ path: path.join(here, 'i125_surbrillance.png') });

  console.log('ERREURS:', erreurs.length ? erreurs : 'aucune');
  console.log(JSON.stringify(bilan, null, 2));
  await browser.close();
})();
