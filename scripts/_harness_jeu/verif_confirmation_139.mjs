// Vérification fonctionnelle de l'issue #139 (non commité) :
//  1. cliquer « Passer son tour » ouvre la modale de confirmation SANS appeler
//     l'API ; « Annuler » ferme sans appel ; re-cliquer puis « Confirmer »
//     déclenche enfin api.passer().
//  2. idem pour « Remettre toutes ses lettres et passer » → api.echanger_tout().
//  3. le bouton « Remettre… » est désormais un vrai bouton (.btn.btn-secondaire)
//     et non plus un lien discret (.lien-discret) : fond gris plein, moins
//     proéminent que « Jouer » (.btn-primaire).
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

// État minimal : tour du joueur humain, sac non vide, chevalet plein → les deux
// boutons sont actifs (voir majActionsTour). type_echange non défini = complet.
function etat() {
  const plateau = Array.from({ length: 15 }, () =>
    Array.from({ length: 15 }, () => ({ type: 'normale', lettre: null, joker: false })));
  plateau[7][7].type = 'centre';
  return {
    id_partie: 1, taille: 15, plateau, jetons_sac: 42, nb_humains: 1,
    tour_humain: true, index_panneau: 0,
    joueurs: [
      { index: 0, nom: 'Alain', humain: true, niveau: null, score: 10, nb_lettres: 7, courant: true, position: 'bas' },
      { index: 1, nom: 'Ordi', humain: false, niveau: 'EXPERT', score: 8, nb_lettres: 7, courant: false, position: 'haut' },
    ],
    index_courant: 0, terminee: false, gagnants: [], en_attente: [], historique: [],
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
  await page.evaluate((e) => window.appliquerEtatPlateau(e), etat());
  await page.waitForTimeout(300);

  // Espionne les appels API : on remplace passer/echanger_tout par des compteurs
  // (l'objet window.pywebview.api est celui capturé par jeu.js → même référence).
  await page.evaluate(() => {
    window.__calls = { passer: 0, echanger: 0 };
    const a = window.pywebview.api;
    const p = a.passer, e = a.echanger_tout;
    a.passer = async (...args) => { window.__calls.passer++; return p(...args); };
    a.echanger_tout = async (...args) => { window.__calls.echanger++; return e(...args); };
  });

  const bilan = {};
  const modaleOuverte = () => page.evaluate(() =>
    !document.getElementById('confirmation-modale').hidden);
  const compteurs = () => page.evaluate(() => ({ ...window.__calls }));

  // --- Style du bouton « Remettre… » (point 3) --------------------------------
  bilan.style_bouton_remettre = await page.evaluate(() => {
    const b = document.getElementById('btn-echanger-tout');
    const bg = getComputedStyle(b).backgroundColor;
    return {
      est_bouton: b.classList.contains('btn') && b.classList.contains('btn-secondaire'),
      plus_de_lien_discret: !b.classList.contains('lien-discret'),
      fond_gris_plein: bg === 'rgb(224, 224, 224)',           // .btn-secondaire
      pas_style_primaire: !b.classList.contains('btn-primaire'),
    };
  });

  // --- 1. « Passer son tour » --------------------------------------------------
  await page.click('#btn-passer');
  await page.waitForTimeout(150);
  const passer_modale_ouverte = await modaleOuverte();
  const passer_titre = await page.evaluate(() =>
    document.getElementById('confirmation-titre').textContent.trim());
  const passer_avant_confirm = await compteurs();
  // Annulation : aucun appel, modale refermée.
  await page.click('#confirmation-annuler');
  await page.waitForTimeout(150);
  const passer_apres_annuler = { ouverte: await modaleOuverte(), calls: await compteurs() };
  // Re-clic puis confirmation : l'appel a lieu.
  await page.click('#btn-passer');
  await page.waitForTimeout(120);
  await page.click('#confirmation-confirmer');
  await page.waitForTimeout(150);
  bilan.passer = {
    modale_ouverte_au_clic: passer_modale_ouverte,
    titre: passer_titre,
    aucun_appel_avant_confirmation: passer_avant_confirm.passer === 0,
    annuler_ferme_sans_appel: !passer_apres_annuler.ouverte && passer_apres_annuler.calls.passer === 0,
    confirmation_appelle_une_fois: (await compteurs()).passer === 1,
    modale_fermee_apres_confirmation: !(await modaleOuverte()),
  };

  // --- 2. « Remettre toutes ses lettres et passer » ---------------------------
  // On réactive le bouton (majActionsTour l'a désactivé après le clic précédent).
  await page.evaluate(() => { document.getElementById('btn-echanger-tout').disabled = false; });
  await page.click('#btn-echanger-tout');
  await page.waitForTimeout(150);
  const ech_modale_ouverte = await modaleOuverte();
  const ech_titre = await page.evaluate(() =>
    document.getElementById('confirmation-titre').textContent.trim());
  const ech_avant_confirm = await compteurs();
  // Clic dehors = annulation (aucun appel).
  await page.click('#confirmation-modale', { position: { x: 10, y: 10 } });
  await page.waitForTimeout(150);
  const ech_apres_dehors = { ouverte: await modaleOuverte(), calls: await compteurs() };
  await page.evaluate(() => { document.getElementById('btn-echanger-tout').disabled = false; });
  await page.click('#btn-echanger-tout');
  await page.waitForTimeout(120);
  await page.click('#confirmation-confirmer');
  await page.waitForTimeout(150);
  bilan.echanger_tout = {
    modale_ouverte_au_clic: ech_modale_ouverte,
    titre: ech_titre,
    aucun_appel_avant_confirmation: ech_avant_confirm.echanger === 0,
    clic_dehors_ferme_sans_appel: !ech_apres_dehors.ouverte && ech_apres_dehors.calls.echanger === 0,
    confirmation_appelle_une_fois: (await compteurs()).echanger === 1,
  };

  await page.screenshot({ path: path.join(here, 'i139_boutons_actions.png') });

  console.log('ERREURS:', erreurs.length ? erreurs : 'aucune');
  console.log(JSON.stringify(bilan, null, 2));
  await browser.close();
})();
