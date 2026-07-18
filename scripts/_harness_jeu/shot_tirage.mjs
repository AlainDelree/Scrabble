// Vérification visuelle de la modale de tirage d'ordre (issues #82, #83, #115,
// #116).
//
// LEÇON DE LA RÉGRESSION #115 : le garde-fou d'origine (#83) ne testait qu'UN
// seul tirage affiché — un cas qui n'arrive jamais, une partie de Scrabble
// comptant au minimum 2 joueurs. Or toutes les lignes de joueurs sont insérées
// dès le départ (masquées en fondu mais occupant déjà la place) ; dès 2 lignes,
// le sac + le bouton « Tirer une lettre » débordaient de la fenêtre et
// repassaient sous le scroll de secours de l'issue #82. Le test passait au vert
// sur un scénario irréaliste pendant que toute vraie partie défilait.
//
// VIRAGE DE L'ISSUE #116 : après DEUX calibrages de taille inopérants en
// conditions réelles WebKitGTK (Chromium headless mesure autrement), on cesse
// de viser une hauteur de fenêtre précise. Le bouton « Tirer une lettre » est
// désormais ÉPINGLÉ hors du corps scrollable (.tirage-sac-action), dans la même
// zone fixe qu'Annuler / Continuer. Il est donc TOUJOURS visible PAR
// CONSTRUCTION — ce harnais le vérifie à des tailles de fenêtre variées, y
// compris volontairement courtes, SANS jamais dépendre d'un ajustement au pixel.
//
// Ce que l'on vérifie désormais, pour 2 / 3 / 5 joueurs et à plusieurs hauteurs :
//   - le bouton « Tirer une lettre » est ENTIÈREMENT visible sans scroll (il est
//     épinglé, donc vrai quelle que soit la taille) ;
//   - Annuler et Continuer restent visibles ;
//   - la modale ne déborde jamais de la fenêtre ;
//   - même quand le corps DÉFILE (fenêtre courte / 5 joueurs), le bouton épinglé
//     reste visible — c'est tout l'intérêt de l'épinglage.
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

// Fenêtre pywebview par défaut : 700x780 (issue #115). On retire une marge pour
// la barre de titre / chrome. On teste AUSSI une fenêtre volontairement courte
// (620 px utiles) pour prouver que l'épinglage (#116) tient là où le calibrage
// de taille échouait.
const VW = 700;

// Noms de joueurs employés pour remplir la liste des tirages (le premier, plus
// court, sert au cas minimal ; les suivants allongent la liste).
const NOMS = ['Alain', 'Ordinateur Bertrand', 'Marie-Christine',
              'Jean-Baptiste', 'Ordinateur Zoé'];

// Construit le corps de la modale : `n` lignes de tirage + zone du sac (consigne
// + aire) dans le corps scrollable, et le bouton « Tirer une lettre » ÉPINGLÉ
// dans .tirage-sac-action — reproduction fidèle de ce que fait accueil.js (#116).
function remplir(n, consigne) {
  const modale = document.getElementById('modale-tirage');
  modale.hidden = false;
  const liste = document.getElementById('tirage-lettres');
  liste.innerHTML = window.__NOMS.slice(0, n)
    .map(nom => `<li class="visible"><span class="tirage-nom">${nom}</span> a tiré <span class="tirage-lettre">E</span></li>`)
    .join('');
  const zone = document.getElementById('tirage-sac-zone');
  zone.hidden = false;
  zone.innerHTML = `
    <p class="tirage-sac-consigne">${window.__CONSIGNE}</p>
    <div class="tirage-sac-aire" aria-hidden="true"><div class="tirage-sac">🛍️</div></div>`;
  const action = document.getElementById('tirage-sac-action');
  action.hidden = false;
  action.innerHTML =
    '<button type="button" class="btn btn-primaire tirage-sac-bouton">Tirer une lettre</button>';
}

// Remplit la modale puis renvoie les mesures utiles.
async function mesurer(page, vh, n, consigne) {
  await page.setViewportSize({ width: VW, height: vh });
  await page.evaluate(([noms, cons]) => { window.__NOMS = noms; window.__CONSIGNE = cons; },
    [NOMS, consigne]);
  await page.evaluate(`(${remplir.toString()})(${n}, ${JSON.stringify(consigne)})`);
  await page.waitForTimeout(150);
  return page.evaluate((vh) => {
    const r = (id) => document.getElementById(id).getBoundingClientRect();
    const contenu = document.querySelector('#modale-tirage .modale-contenu').getBoundingClientRect();
    const corps = document.querySelector('.modale-corps');
    const btn = document.querySelector('.tirage-sac-bouton').getBoundingClientRect();
    const annuler = r('btn-annuler-tirage');
    const continuer = r('btn-continuer-tirage');
    return {
      vh,
      corpsDefile: corps.scrollHeight > corps.clientHeight + 1,
      // Le bouton épinglé est-il ENTIÈREMENT dans la fenêtre, sans scroll ?
      boutonVisible: btn.top >= -0.5 && btn.bottom <= vh + 0.5,
      annulerVisible: annuler.bottom <= vh + 0.5 && annuler.top >= -0.5,
      continuerVisible: continuer.bottom <= vh + 0.5 && continuer.top >= -0.5,
      // La modale ne déborde jamais de la fenêtre.
      modaleDansFenetre: contenu.top >= -0.5 && contenu.bottom <= vh + 0.5,
    };
  }, vh);
}

const COURTE = 'À toi, Alain ! Secoue le sac, puis tire ta lettre.';
const LONGUE = 'À toi, Marie-Christine de Montrichard ! Secoue le sac, puis tire ta lettre.';

// Chaque scénario : (label, hauteur utile, nb joueurs, consigne, capture).
const SCENARIOS = [
  ['Cas courant minimal — 2 joueurs, fenêtre standard', 732, 2, COURTE, 'tirage_courant.png'],
  ['Cas courant chargé — 3 joueurs + nom long, fenêtre standard', 732, 3, LONGUE, 'tirage_default.png'],
  ['Fenêtre COURTE — 3 joueurs, 620 px utiles (corps défile)', 620, 3, LONGUE, 'tirage_court.png'],
  ['Fenêtre TRÈS courte — 5 joueurs, 520 px utiles', 520, 5, LONGUE, 'tirage_extreme.png'],
];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: VW, height: 732 } });
  await page.setContent(html, { waitUntil: 'domcontentloaded' });

  let toutOk = true;
  for (const [label, vh, n, consigne, shot] of SCENARIOS) {
    const m = await mesurer(page, vh, n, consigne);
    await page.screenshot({ path: path.join(here, shot) });
    // Exigence #116 : le bouton « Tirer » est TOUJOURS visible (épinglé), tout
    // comme Annuler / Continuer, et la modale ne déborde jamais — peu importe
    // que le corps défile ou non.
    const ok = m.boutonVisible && m.annulerVisible && m.continuerVisible
      && m.modaleDansFenetre;
    toutOk = toutOk && ok;
    console.log(`\n— ${label} —`);
    console.log(JSON.stringify(m, null, 2));
    console.log(ok
      ? '✅ Bouton « Tirer une lettre » épinglé visible + Annuler/Continuer visibles + modale dans la fenêtre'
      : '❌ Un élément épinglé est hors de la fenêtre ou la modale déborde');
  }

  await browser.close();
  process.exit(toutOk ? 0 : 1);
})();
