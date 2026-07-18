// Vérification visuelle de la modale de tirage d'ordre (issues #82, #83, #115).
//
// LEÇON DE LA RÉGRESSION #115 : le garde-fou d'origine (#83) ne testait qu'UN
// seul tirage affiché — un cas qui n'arrive jamais, une partie de Scrabble
// comptant au minimum 2 joueurs. Or toutes les lignes de joueurs sont insérées
// dès le départ (masquées en fondu mais occupant déjà la place) ; dès 2 lignes,
// le sac + le bouton « Tirer une lettre » débordaient de la fenêtre 720 px et
// repassaient sous le scroll de secours de l'issue #82. Le test passait au vert
// sur un scénario irréaliste pendant que toute vraie partie défilait.
//
// Ce harnais teste désormais le CAS COURANT RÉEL (2 à 3 joueurs), à la taille
// de fenêtre effective (780 px, issue #115) :
//   1. CAS COURANT MINIMAL — 2 joueurs, consigne sur une ligne. Le bouton
//      « Tirer une lettre » doit être ENTIÈREMENT visible, sans aucun scroll.
//   2. CAS COURANT CHARGÉ — 3 joueurs + consigne sur deux lignes (nom long).
//      Idem : bouton entièrement visible sans scroll (exigence relevée #115 ;
//      l'issue #82 se contentait de garder Annuler/Continuer épinglés).
//   3. FILET DE SÉCURITÉ (issue #82) — 5 joueurs + consigne sur deux lignes.
//      Le contenu déborde et le corps défile ; les boutons Annuler / Continuer
//      restent épinglés et visibles, et le bouton « Tirer une lettre » reste
//      intégralement atteignable en scrollant (pas de troncature nette).
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
// la barre de titre / chrome de la fenêtre → hauteur utile conservatrice.
const VW = 700, VH = 732;

// Noms de joueurs employés pour remplir la liste des tirages (le premier, plus
// court, sert au cas minimal ; les suivants allongent la liste).
const NOMS = ['Alain', 'Ordinateur Bertrand', 'Marie-Christine',
              'Jean-Baptiste', 'Ordinateur Zoé'];

// Construit le corps de la modale : `n` lignes de tirage + zone du sac avec le
// bouton « Tirer une lettre ». `consigne` peut tenir sur une ou deux lignes.
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
    <div class="tirage-sac-aire" aria-hidden="true"><div class="tirage-sac">🛍️</div></div>
    <button type="button" class="btn btn-primaire tirage-sac-bouton">Tirer une lettre</button>`;
}

// Remplit la modale puis renvoie les mesures utiles.
async function mesurer(page, n, consigne) {
  await page.evaluate(([noms, cons]) => { window.__NOMS = noms; window.__CONSIGNE = cons; },
    [NOMS, consigne]);
  await page.evaluate(`(${remplir.toString()})(${n}, ${JSON.stringify(consigne)})`);
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

const COURTE = 'À toi, Alain ! Secoue le sac, puis tire ta lettre.';
const LONGUE = 'À toi, Marie-Christine de Montrichard ! Secoue le sac, puis tire ta lettre.';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: VW, height: VH } });
  await page.setContent(html, { waitUntil: 'domcontentloaded' });

  // --- Cas 1 : cas courant minimal (2 joueurs) — issue #115 -----------------
  const casMinimal = await mesurer(page, 2, COURTE);
  await page.screenshot({ path: path.join(here, 'tirage_courant.png') });
  const okMinimal = casMinimal.boutonVisibleSansScroll && !casMinimal.corpsDefile
    && casMinimal.annulerVisible && casMinimal.continuerVisible;
  console.log('— Cas courant minimal (2 joueurs, consigne 1 ligne) —');
  console.log(JSON.stringify(casMinimal, null, 2));
  console.log(okMinimal
    ? '✅ Bouton « Tirer une lettre » entièrement visible sans scroll'
    : '❌ Bouton tronqué ou scroll indésirable');

  // --- Cas 2 : cas courant chargé (3 joueurs, nom long) — issue #115 --------
  const casCharge = await mesurer(page, 3, LONGUE);
  await page.screenshot({ path: path.join(here, 'tirage_default.png') });
  const okCharge = casCharge.boutonVisibleSansScroll && !casCharge.corpsDefile
    && casCharge.annulerVisible && casCharge.continuerVisible;
  console.log('\n— Cas courant chargé (3 joueurs, consigne 2 lignes) —');
  console.log(JSON.stringify(casCharge, null, 2));
  console.log(okCharge
    ? '✅ Bouton « Tirer une lettre » entièrement visible sans scroll'
    : '❌ Bouton tronqué ou scroll indésirable');

  // --- Cas 3 : filet de sécurité (5 joueurs, nom long) — issue #82 ----------
  const casExtreme = await mesurer(page, 5, LONGUE);
  await page.screenshot({ path: path.join(here, 'tirage_extreme.png') });
  const okExtreme = casExtreme.annulerVisible && casExtreme.continuerVisible
    && casExtreme.boutonAtteignable;
  console.log('\n— Filet de sécurité (5 joueurs, consigne 2 lignes) —');
  console.log(JSON.stringify(casExtreme, null, 2));
  console.log(okExtreme
    ? '✅ Annuler + Continuer visibles, bouton « Tirer » atteignable au scroll'
    : '❌ Boutons tronqués ou bouton « Tirer » inatteignable');

  await browser.close();
  process.exit(okMinimal && okCharge && okExtreme ? 0 : 1);
})();
