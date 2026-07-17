// Vérification visuelle de la modale de tirage d'ordre (issue #82).
// Confirme qu'à la taille de fenêtre par défaut du lancement, les boutons
// « Annuler » et « Continuer » sont entièrement visibles sans scroll, dans
// le cas le plus haut (sac affiché + consigne sur deux lignes).
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

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: VW, height: VH } });
  await page.setContent(html, { waitUntil: 'domcontentloaded' });

  // Affiche la modale de tirage dans son état le plus chargé : quelques
  // lettres déjà tirées + zone du sac avec une consigne à nom long (2 lignes).
  await page.evaluate(() => {
    const modale = document.getElementById('modale-tirage');
    modale.hidden = false;
    const liste = document.getElementById('tirage-lettres');
    liste.innerHTML = ['Marie-Christine', 'Ordinateur Bertrand', 'Jean-Baptiste']
      .map(n => `<li class="visible"><span class="tirage-nom">${n}</span> a tiré <span class="tirage-lettre">E</span></li>`)
      .join('');
    const zone = document.getElementById('tirage-sac-zone');
    zone.hidden = false;
    zone.innerHTML = `
      <p class="tirage-sac-consigne">À toi, Marie-Christine de Montrichard ! Secoue le sac, puis tire ta lettre.</p>
      <div class="tirage-sac-aire" aria-hidden="true"><div class="tirage-sac">🛍️</div></div>
      <button type="button" class="btn btn-primaire tirage-sac-bouton">Tirer une lettre</button>`;
  });
  await page.waitForTimeout(200);

  const res = await page.evaluate((vh) => {
    const r = (id) => document.getElementById(id).getBoundingClientRect();
    const annuler = r('btn-annuler-tirage');
    const continuer = r('btn-continuer-tirage');
    return {
      vh,
      annulerBottom: Math.round(annuler.bottom),
      continuerBottom: Math.round(continuer.bottom),
      annulerVisible: annuler.bottom <= vh && annuler.top >= 0,
      continuerVisible: continuer.bottom <= vh && continuer.top >= 0,
    };
  }, VH);

  console.log(JSON.stringify(res, null, 2));
  console.log(res.annulerVisible && res.continuerVisible
    ? '✅ Boutons Annuler + Continuer visibles sans scroll'
    : '❌ Boutons tronqués');
  await page.screenshot({ path: path.join(here, 'tirage_default.png') });
  await browser.close();
  process.exit(res.annulerVisible && res.continuerVisible ? 0 : 1);
})();
