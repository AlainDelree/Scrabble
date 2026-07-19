// Vérification headless du tableau de classement final (issue #133, point C) :
//  1. à la fin de partie, le bandeau affiche le message ET un tableau listant
//     TOUS les joueurs, triés par score décroissant ;
//  2. les rangs sont corrects, avec gestion « sportive » des ex-æquo (même score
//     → même rang, annoté « ex æquo », le rang suivant saute) ;
//  3. le contenu (nom, score) correspond à l'état public ;
//  4. pendant la partie (terminee:false), le bandeau reste masqué.
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

// terminee=true, 4 joueurs dont deux à égalité (24 pts) → rangs 1, 2, 2, 4.
function etat(terminee, joueurs, gagnants) {
  const plateau = Array.from({ length: 15 }, () =>
    Array.from({ length: 15 }, () => ({ type: 'normale', lettre: null, joker: false })));
  plateau[7][7].type = 'centre';
  return {
    id_partie: 1, taille: 15, plateau, jetons_sac: 0,
    joueurs, index_courant: 0, terminee, gagnants, en_attente: [], historique: [],
  };
}

const JOUEURS = [
  { index: 0, nom: 'Alain', humain: true, niveau: null, score: 42, nb_lettres: 0, courant: false, position: 'bas' },
  { index: 1, nom: 'Ordi', humain: false, niveau: 'EXPERT', score: 24, nb_lettres: 0, courant: false, position: 'haut' },
  { index: 2, nom: 'Bea', humain: true, niveau: null, score: 24, nb_lettres: 0, courant: false, position: 'gauche' },
  { index: 3, nom: 'Zoe', humain: true, niveau: null, score: 11, nb_lettres: 0, courant: false, position: 'droite' },
];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  const erreurs = [];
  page.on('pageerror', e => erreurs.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') erreurs.push('console: ' + m.text()); });

  await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await page.waitForTimeout(300);

  const bilan = {};

  // Pendant la partie : bandeau masqué, aucun tableau.
  await page.evaluate((e) => window.appliquerEtatPlateau(e), etat(false, JOUEURS, []));
  await page.waitForTimeout(200);
  bilan.en_cours = await page.evaluate(() => ({
    bandeau_masque: document.getElementById('bandeau-fin').hidden,
    pas_de_table: document.querySelectorAll('.classement-final').length === 0,
  }));

  // Fin de partie : message + tableau complet trié.
  await page.evaluate((e) => window.appliquerEtatPlateau(e), etat(true, JOUEURS, ['Alain']));
  await page.waitForTimeout(200);
  bilan.fin = await page.evaluate(() => {
    const bandeau = document.getElementById('bandeau-fin');
    const message = bandeau.querySelector('.bandeau-fin-message');
    const lignes = [...bandeau.querySelectorAll('.classement-final tbody tr')].map((tr) => ({
      rang: tr.querySelector('.classement-rang').textContent,
      nom: tr.querySelector('.classement-nom').textContent,
      score: tr.querySelector('.classement-score').textContent,
      premier: tr.classList.contains('classement-premier'),
    }));
    return {
      bandeau_visible: !bandeau.hidden,
      message: message ? message.textContent : null,
      caption: bandeau.querySelector('.classement-final caption')?.textContent || null,
      lignes,
    };
  });
  await page.screenshot({ path: path.join(here, 'i133_classement.png') });

  // Contrôles d'assertion explicites.
  const l = bilan.fin.lignes;
  bilan.assertions = {
    quatre_lignes: l.length === 4,
    tri_decroissant: l.map((x) => Number(x.score)).every((s, i, a) => i === 0 || a[i - 1] >= s),
    rang1_alain: l[0] && l[0].rang === '1er' && l[0].nom === 'Alain' && l[0].score === '42' && l[0].premier,
    exaequo_rang2: l[1] && l[2] && l[1].rang === '2e ex æquo' && l[2].rang === '2e ex æquo'
      && l[1].score === '24' && l[2].score === '24',
    dernier_rang4: l[3] && l[3].rang === '4e' && l[3].nom === 'Zoe' && l[3].score === '11',
  };

  console.log('ERREURS:', erreurs.length ? erreurs : 'aucune');
  console.log(JSON.stringify(bilan, null, 2));
  await browser.close();
})();
