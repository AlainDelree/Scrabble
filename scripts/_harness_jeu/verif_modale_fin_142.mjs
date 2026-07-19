// Vérification headless de la modale de fin de partie (issue #142) :
//  1. pendant la partie (terminee:false), la modale #modale-fin reste masquée ;
//  2. à la fin (terminee:true), elle s'ouvre par-dessus le plateau avec le message
//     de victoire, le tableau de classement final et l'évaluation du score ;
//  3. les TROIS actions sont câblées :
//     - « Rester sur la partie » ferme la modale SANS appeler l'API ;
//     - « Retour au menu » appelle api.retour_menu() ;
//     - « Recommencer » appelle api.recommencer() ;
//  4. une fois fermée par « Rester », un état terminé repoussé ne la rouvre pas ;
//  5. un clic dehors ferme la modale (= rester).
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

const JOUEURS = [
  { index: 0, nom: 'Alain', humain: true, niveau: null, score: 42, nb_lettres: 0, courant: false, position: 'bas' },
  { index: 1, nom: 'Ordi', humain: false, niveau: 'EXPERT', score: 24, nb_lettres: 0, courant: false, position: 'haut' },
  { index: 2, nom: 'Bea', humain: true, niveau: null, score: 24, nb_lettres: 0, courant: false, position: 'gauche' },
];

function etat(terminee, gagnants) {
  const plateau = Array.from({ length: 15 }, () =>
    Array.from({ length: 15 }, () => ({ type: 'normale', lettre: null, joker: false })));
  plateau[7][7].type = 'centre';
  return {
    id_partie: 1, taille: 15, plateau, jetons_sac: 0,
    joueurs: JOUEURS, index_courant: 0, terminee, gagnants,
    en_attente: [], historique: [],
    evaluation_score: terminee
      ? { total: 90, moyenne: 30, nb_joueurs: 3, qualificatif: 'Bon score' }
      : null,
  };
}

const modaleOuverte = (page) => page.evaluate(() =>
  !document.getElementById('modale-fin').hidden);

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  const erreurs = [];
  page.on('pageerror', e => erreurs.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') erreurs.push('console: ' + m.text()); });

  await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await page.waitForTimeout(300);

  // Espionne les appels API menu/recommencer (référence partagée avec jeu.js).
  await page.evaluate(() => {
    window.__calls = { retour: 0, recommencer: 0 };
    const a = window.pywebview.api;
    a.retour_menu = async () => { window.__calls.retour++; return { succes: true }; };
    a.recommencer = async () => { window.__calls.recommencer++; return { succes: true }; };
  });
  const compteurs = () => page.evaluate(() => ({ ...window.__calls }));

  const bilan = {};

  // 1. Pendant la partie : modale masquée.
  await page.evaluate((e) => window.appliquerEtatPlateau(e), etat(false, []));
  await page.waitForTimeout(150);
  bilan.en_cours_masquee = !(await modaleOuverte(page));

  // 2. Fin de partie : la modale s'ouvre avec son contenu.
  await page.evaluate((e) => window.appliquerEtatPlateau(e), etat(true, ['Alain']));
  await page.waitForTimeout(200);
  bilan.ouverture = await page.evaluate(() => {
    const m = document.getElementById('modale-fin');
    return {
      ouverte: !m.hidden,
      message: document.getElementById('modale-fin-message').textContent,
      lignes_classement: m.querySelectorAll('.classement-final tbody tr').length,
      a_evaluation: !!m.querySelector('.evaluation-score'),
      trois_boutons: !!document.getElementById('fin-retour-menu')
        && !!document.getElementById('fin-rester')
        && !!document.getElementById('fin-recommencer'),
    };
  });
  await page.screenshot({ path: path.join(here, 'i142_modale_fin.png') });

  // 3a. « Rester sur la partie » ferme sans appeler l'API.
  await page.click('#fin-rester');
  await page.waitForTimeout(150);
  bilan.rester = {
    modale_fermee: !(await modaleOuverte(page)),
    aucun_appel: JSON.stringify(await compteurs()) === JSON.stringify({ retour: 0, recommencer: 0 }),
  };

  // 4. Un nouvel état terminé repoussé ne rouvre pas la modale (déjà consultée).
  await page.evaluate((e) => window.appliquerEtatPlateau(e), etat(true, ['Alain']));
  await page.waitForTimeout(150);
  bilan.pas_de_reouverture = !(await modaleOuverte(page));

  // Retour à une partie en cours puis fin : la modale se rouvre (nouveau cycle).
  await page.evaluate((e) => window.appliquerEtatPlateau(e), etat(false, []));
  await page.waitForTimeout(100);
  await page.evaluate((e) => window.appliquerEtatPlateau(e), etat(true, ['Alain']));
  await page.waitForTimeout(150);
  bilan.reouverture_apres_nouveau_cycle = await modaleOuverte(page);

  // 3b. « Retour au menu » appelle api.retour_menu().
  await page.click('#fin-retour-menu');
  await page.waitForTimeout(150);
  bilan.retour_menu_appelle = (await compteurs()).retour === 1;

  // 5. Clic dehors ferme la modale (= rester). On la rouvre d'abord.
  await page.evaluate(() => { document.getElementById('modale-fin').hidden = false; });
  await page.click('#modale-fin', { position: { x: 8, y: 8 } });
  await page.waitForTimeout(150);
  bilan.clic_dehors_ferme = !(await modaleOuverte(page));

  // 3c. « Recommencer » appelle api.recommencer().
  await page.evaluate(() => { document.getElementById('modale-fin').hidden = false; });
  await page.click('#fin-recommencer');
  await page.waitForTimeout(150);
  bilan.recommencer_appelle = (await compteurs()).recommencer === 1;

  bilan.assertions_ok = bilan.en_cours_masquee
    && bilan.ouverture.ouverte && bilan.ouverture.lignes_classement === 3
    && bilan.ouverture.a_evaluation && bilan.ouverture.trois_boutons
    && bilan.rester.modale_fermee && bilan.rester.aucun_appel
    && bilan.pas_de_reouverture && bilan.reouverture_apres_nouveau_cycle
    && bilan.retour_menu_appelle && bilan.clic_dehors_ferme
    && bilan.recommencer_appelle;

  console.log('ERREURS:', erreurs.length ? erreurs : 'aucune');
  console.log(JSON.stringify(bilan, null, 2));
  await browser.close();
  process.exit(bilan.assertions_ok && erreurs.length === 0 ? 0 : 1);
})();
