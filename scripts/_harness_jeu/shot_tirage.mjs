// Vérification visuelle de la modale de tirage d'ordre (issues #82 et #83).
//
// Deux cas sont couverts :
//   1. CAS COURANT (issue #83) — un seul joueur humain, un seul tirage affiché
//      ("Alain a tiré", consigne sur une ligne). Le bouton « Tirer une lettre »
//      doit être ENTIÈREMENT visible, sans aucun scroll : c'est le cas normal
//      qui, avant le correctif #83, était coupé net par le scroll de secours.
//   2. CAS CHARGÉ (issue #82) — plusieurs lettres tirées + consigne sur deux
//      lignes (nom long). Le contenu déborde et le corps défile ; les boutons
//      Annuler / Continuer restent épinglés et visibles, et le bouton « Tirer
//      une lettre » reste intégralement atteignable en scrollant (pas de
//      troncature nette à une limite fixe).
import pw from '/home/alain/.npm-global/lib/node_modules/playwright/index.js';
const { chromium } = pw;
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '../../src/scrabble/ui/web');
const css = fs.readFileSync(path.join(web, 'accueil.css'), 'utf8');
let html = fs.readFileSync(path.join(web, 'accueil.html'), 'utf8')
  .replace('<link rel="stylesheet" href="accueil.css">', `<style>${css}</style>`)
  .replace('<script src="accueil.js"></script>', '');

// Fenêtre pywebview par défaut : 700x720. On retire une marge pour la barre
// de titre / chrome de la fenêtre → hauteur utile conservatrice.
const VW = 700, VH = 672;

// Remplit la modale de tirage puis renvoie les mesures utiles.
async function mesurer(page, remplir) {
  await page.evaluate(remplir);
  await page.waitForTimeout(200);
  return page.evaluate((vh) => {
    const r = (id) => document.getElementById(id).getBoundingClientRect();
    const corps = document.querySelector('.modale-corps');
    const corpsR = corps.getBoundingClientRect();
    const btn = document.querySelector('.tirage-sac-bouton').getBoundingClientRect();
    const annuler = r('btn-annuler-tirage');
    const continuer = r('btn-continuer-tirage');
    // Bas du bouton relatif au haut du contenu scrollable : doit rester
    // dans scrollHeight pour être atteignable en scrollant.
    const btnBottomDansScroll = (btn.bottom - corpsR.top) + corps.scrollTop;
    return {
      vh,
      corpsDefile: corps.scrollHeight > corps.clientHeight + 1,
      // Bouton « Tirer une lettre » entièrement visible sans scroll ?
      boutonVisibleSansScroll: btn.bottom <= corpsR.bottom + 0.5 && btn.top >= corpsR.top - 0.5,
      // Bouton intégralement atteignable dans la zone scrollable ?
      boutonAtteignable: btnBottomDansScroll <= corps.scrollHeight + 0.5,
      annulerVisible: annuler.bottom <= vh && annuler.top >= 0,
      continuerVisible: continuer.bottom <= vh && continuer.top >= 0,
    };
  }, VH);
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: VW, height: VH } });
  await page.setContent(html, { waitUntil: 'domcontentloaded' });

  // --- Cas 1 : cas courant (issue #83) -------------------------------------
  const casCourant = await mesurer(page, () => {
    const modale = document.getElementById('modale-tirage');
    modale.hidden = false;
    const liste = document.getElementById('tirage-lettres');
    liste.innerHTML =
      '<li class="visible en-attente-tirage"><span class="tirage-nom">Alain</span> a tiré <span class="tirage-lettre">?</span></li>';
    const zone = document.getElementById('tirage-sac-zone');
    zone.hidden = false;
    zone.innerHTML = `
      <p class="tirage-sac-consigne">À toi, Alain ! Secoue le sac, puis tire ta lettre.</p>
      <div class="tirage-sac-aire" aria-hidden="true"><div class="tirage-sac">🛍️</div></div>
      <button type="button" class="btn btn-primaire tirage-sac-bouton">Tirer une lettre</button>`;
  });
  await page.screenshot({ path: path.join(here, 'tirage_courant.png') });
  const okCourant = casCourant.boutonVisibleSansScroll && !casCourant.corpsDefile
    && casCourant.annulerVisible && casCourant.continuerVisible;
  console.log('— Cas courant (1 joueur humain, 1 tirage) —');
  console.log(JSON.stringify(casCourant, null, 2));
  console.log(okCourant
    ? '✅ Bouton « Tirer une lettre » entièrement visible sans scroll'
    : '❌ Bouton tronqué ou scroll indésirable');

  // --- Cas 2 : cas chargé (issue #82) --------------------------------------
  const casCharge = await mesurer(page, () => {
    const liste = document.getElementById('tirage-lettres');
    liste.innerHTML = ['Marie-Christine', 'Ordinateur Bertrand', 'Jean-Baptiste']
      .map(n => `<li class="visible"><span class="tirage-nom">${n}</span> a tiré <span class="tirage-lettre">E</span></li>`)
      .join('');
    const zone = document.getElementById('tirage-sac-zone');
    zone.innerHTML = `
      <p class="tirage-sac-consigne">À toi, Marie-Christine de Montrichard ! Secoue le sac, puis tire ta lettre.</p>
      <div class="tirage-sac-aire" aria-hidden="true"><div class="tirage-sac">🛍️</div></div>
      <button type="button" class="btn btn-primaire tirage-sac-bouton">Tirer une lettre</button>`;
  });
  await page.screenshot({ path: path.join(here, 'tirage_default.png') });
  const okCharge = casCharge.annulerVisible && casCharge.continuerVisible
    && casCharge.boutonAtteignable;
  console.log('\n— Cas chargé (3 tirages, nom long) —');
  console.log(JSON.stringify(casCharge, null, 2));
  console.log(okCharge
    ? '✅ Annuler + Continuer visibles, bouton « Tirer » atteignable au scroll'
    : '❌ Boutons tronqués ou bouton « Tirer » inatteignable');

  await browser.close();
  process.exit(okCourant && okCharge ? 0 : 1);
})();
