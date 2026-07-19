// Vérification fonctionnelle temporaire de l'issue #144 (non commité) :
//  1. « Derniers coups » se ferme au clic EXTÉRIEUR et à Échap (comme
//     « Vérification dictionnaire », via C.configurerPopover) ;
//  2. l'encart affiche TOUT l'historique (ici 12 coups > 8), la plus récente en
//     haut, et devient scrollable au-delà de sa hauteur plafond.
import pw from '/home/alain/.npm-global/lib/node_modules/playwright/index.js';
const { chromium } = pw;
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '../../src/scrabble/ui/web');
const css = fs.readFileSync(path.join(web, 'jeu.css'), 'utf8');
const commCss = fs.readFileSync(path.join(web, 'commun.css'), 'utf8');
const js = fs.readFileSync(path.join(web, 'jeu.js'), 'utf8');
const commJs = fs.readFileSync(path.join(web, 'commun.js'), 'utf8');
const mock = fs.readFileSync(path.join(here, 'mock.js'), 'utf8');
const html = fs.readFileSync(path.join(web, 'jeu.html'), 'utf8')
  .replace('<link rel="stylesheet" href="commun.css">', `<style>${commCss}</style>`)
  .replace('<link rel="stylesheet" href="jeu.css">', `<style>${css}</style>`)
  .replace('<script src="commun.js"></script>', `<script>${commJs}</script>`)
  .replace('<script src="jeu.js"></script>',
    `<script>window.__THEME__='classique';${mock}</script><script>${js}</script>`);

// État public minimal valide, avec un historique de 12 coups (> 8), la plus
// récente en tête (index 11 → 0). Chaque coup a un `detail` ⇒ ligne cliquable.
function etatAvecHistorique(nbCoups) {
  const plateau = Array.from({ length: 15 }, () =>
    Array.from({ length: 15 }, () => ({ type: 'normale', lettre: null, joker: false })));
  plateau[7][7].type = 'centre';
  const historique = [];
  for (let i = nbCoups - 1; i >= 0; i--) {           // du plus récent au plus ancien
    historique.push({
      index: i, action: 'coup', nom_joueur: i % 2 ? 'Ordi' : 'Alain', humain: i % 2 === 0,
      mot: 'MOT' + i, score_action: i + 1, positions: [],
      detail: { mots: [{ texte: 'MOT' + i, score: i + 1, cases_bonus: [] }], total: i + 1 },
    });
  }
  return {
    id_partie: 1, taille: 15, plateau, jetons_sac: 40,
    joueurs: [
      { index: 0, nom: 'Alain', humain: true, niveau: null, score: 10, nb_lettres: 7, courant: true, position: 'bas' },
      { index: 1, nom: 'Ordi', humain: false, niveau: 'EXPERT', score: 8, nb_lettres: 7, courant: false, position: 'haut' },
    ],
    index_courant: 0, terminee: false, gagnants: [], en_attente: [],
    historique,
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

  // 20 coups : bien plus que l'ancien plafond de 8, et assez pour dépasser la
  // hauteur plafond du popover (donc pour vérifier le défilement).
  const NB = 20;
  await page.evaluate((etat) => window.appliquerEtatPlateau(etat), etatAvecHistorique(NB));
  await page.waitForTimeout(300);

  const bilan = {};
  // État initial : popover masqué, aria-expanded=false.
  bilan.listeInitCachee = await page.getAttribute('#historique-liste', 'hidden') !== null;
  bilan.ariaInit = await page.getAttribute('#btn-historique', 'aria-expanded');

  // Ouverture au clic sur le bouton.
  await page.click('#btn-historique');
  await page.waitForTimeout(150);
  bilan.ouvertVisible = await page.isVisible('#historique-liste');
  bilan.ariaOuvert = await page.getAttribute('#btn-historique', 'aria-expanded');

  // Affichage COMPLET : NB lignes, compteur (NB), la plus récente (MOT19) en tête.
  bilan.nbLignes = await page.evaluate(() =>
    document.querySelectorAll('#historique-liste .historique-ligne').length);
  bilan.compteur = (await page.textContent('#historique-compte')).trim();
  bilan.premiereAction = await page.evaluate(() => {
    const l = document.querySelector('#historique-liste .historique-ligne .historique-action');
    return l ? l.textContent.trim() : null;
  });
  // Scrollable : le contenu dépasse la hauteur plafond du popover.
  bilan.scrollable = await page.evaluate(() => {
    const ol = document.getElementById('historique-liste');
    return ol.scrollHeight > ol.clientHeight + 1;
  });
  await page.screenshot({ path: path.join(here, 'i144_historique_ouvert.png') });

  // Fermeture au clic EXTÉRIEUR (sur le plateau).
  await page.click('#plateau');
  await page.waitForTimeout(150);
  bilan.fermeClicExterieur = !(await page.isVisible('#historique-liste'));
  bilan.ariaApresClicExt = await page.getAttribute('#btn-historique', 'aria-expanded');

  // Réouverture puis fermeture via Échap.
  await page.click('#btn-historique');
  await page.waitForTimeout(120);
  bilan.rouvert = await page.isVisible('#historique-liste');
  await page.keyboard.press('Escape');
  await page.waitForTimeout(120);
  bilan.fermeEchap = !(await page.isVisible('#historique-liste'));

  // Clic sur une ligne : ouvre la modale de détail (#score-modale) SANS que le
  // clic « intérieur » ne referme le popover (configurerPopover stoppe sa
  // propagation vers document).
  await page.click('#btn-historique');
  await page.waitForTimeout(120);
  bilan.nbCliquables = await page.evaluate(() =>
    document.querySelectorAll('#historique-liste .historique-ligne.cliquable').length);
  await page.click('#historique-liste .historique-ligne.cliquable', { timeout: 4000 })
    .catch((e) => { bilan.erreurClicLigne = e.message.split('\n')[0]; });
  await page.waitForTimeout(150);
  bilan.detailOuvertAuClicLigne = await page.isVisible('#score-modale');
  bilan.popoverResteOuvertApresClicLigne = await page.isVisible('#historique-liste');

  console.log('ERREURS:', erreurs.length ? erreurs : 'aucune');
  console.log(JSON.stringify(bilan, null, 2));
  await browser.close();
})();
