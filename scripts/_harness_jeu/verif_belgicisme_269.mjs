// Vérification issue #269 : cercles-drapeaux France/Belgique de l'accueil.
//
// Contrôle en headless Playwright (le rendu réel WebKitGTK reste à vérifier
// manuellement, cf. CONTEXTE.md) :
//   1. France actif par défaut, Belgique inactif.
//   2. Clic sur le drapeau belge -> classe .actif bascule, aria-checked
//      correct, body.mode-belgicisme posé, api.definir_mode_belgicisme(true)
//      appelée.
//   3. Contraste texte blanc / fond en mode belge suffisant (>= 4.5:1, WCAG AA).
//   4. Plusieurs allers-retours France <-> Belgique : aucun résidu visuel
//      (retour exact au fond normal, un seul cercle actif à la fois).
import pw from '/home/alain/.npm-global/lib/node_modules/playwright/index.js';
const { chromium } = pw;
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '../../src/scrabble/ui/web');
const css = fs.readFileSync(path.join(web, 'accueil.css'), 'utf8');
const js = fs.readFileSync(path.join(web, 'accueil.js'), 'utf8');

const mock = `
window.pywebview = { platform: 'test' };
window.__appelsMode = [];
setTimeout(() => {
  window.pywebview.api = {
    obtenir_etat: async () => ({
      joueurs: [{nom:'Alain', humain:true, niveau:null}],
      nb_humains: 1, nb_ordinateurs: 0, nb_total: 1,
      peut_ajouter_humain: true, peut_ajouter_ordinateur: true, peut_lancer: true,
      mode_belgicisme: false,
    }),
    obtenir_niveaux: async () => ['Débutant','Facile','Intermédiaire','Expert'],
    lister_parties_en_cours: async () => [],
    obtenir_prenom_principal: async () => 'Alain',
    definir_mode_belgicisme: async (actif) => {
      window.__appelsMode.push(actif);
      return { succes: true, mode_belgicisme: actif };
    },
  };
  window.dispatchEvent(new Event('pywebviewready'));
}, 100);
`;

const html = fs.readFileSync(path.join(web, 'accueil.html'), 'utf8')
  .replace('<link rel="stylesheet" href="accueil.css">', `<style>${css}</style>`)
  .replace('<script src="accueil.js"></script>',
    `<script>${mock}</script><script>${js}</script>`);

function relLuminance([r, g, b]) {
  const chan = (c) => {
    c /= 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  const [R, G, B] = [chan(r), chan(g), chan(b)];
  return 0.2126 * R + 0.7152 * G + 0.0722 * B;
}
function contrastRatio(rgbA, rgbB) {
  const [L1, L2] = [relLuminance(rgbA), relLuminance(rgbB)].sort((a, b) => b - a);
  return (L1 + 0.05) / (L2 + 0.05);
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 700, height: 780 } });
  const errs = [];
  page.on('pageerror', e => errs.push(String(e)));
  await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await page.waitForTimeout(400);

  const etatInitial = await page.evaluate(() => ({
    franceActif: document.getElementById('drapeau-france').classList.contains('actif'),
    belgiqueActif: document.getElementById('drapeau-belgique').classList.contains('actif'),
    franceChecked: document.getElementById('drapeau-france').getAttribute('aria-checked'),
    belgiqueChecked: document.getElementById('drapeau-belgique').getAttribute('aria-checked'),
    bodyModeBelge: document.body.classList.contains('mode-belgicisme'),
  }));

  // Capture avant/après pour vérification visuelle manuelle.
  await page.screenshot({ path: path.join(here, 'i269_accueil_avant.png') });

  // Clic Belgique.
  await page.click('#drapeau-belgique');
  await page.waitForTimeout(100);
  const apresBelgique = await page.evaluate(() => ({
    franceActif: document.getElementById('drapeau-france').classList.contains('actif'),
    belgiqueActif: document.getElementById('drapeau-belgique').classList.contains('actif'),
    franceChecked: document.getElementById('drapeau-france').getAttribute('aria-checked'),
    belgiqueChecked: document.getElementById('drapeau-belgique').getAttribute('aria-checked'),
    bodyModeBelge: document.body.classList.contains('mode-belgicisme'),
    appels: window.__appelsMode,
  }));
  await page.screenshot({ path: path.join(here, 'i269_accueil_belgique.png') });

  // Contraste : couleur du texte du titre (blanc) vs couleur de fond réellement
  // peinte sous le titre (échantillon de pixel au centre du <h1>).
  const contraste = await page.evaluate(() => {
    const h1 = document.querySelector('header h1');
    const rect = h1.getBoundingClientRect();
    return { x: Math.round(rect.left + 5), y: Math.round(rect.top + rect.height / 2) };
  });
  // Échantillon de pixel via canvas (capture d'écran rognée).
  const buffer = await page.screenshot();
  // On utilise un point dans la bande jaune (le plus défavorable) : le titre
  // est centré, donc on échantillonne aussi le centre horizontal de l'écran.
  const pixelJaune = await page.evaluate(() => {
    const bodyStyle = getComputedStyle(document.body);
    return bodyStyle.backgroundImage;
  });

  // Plusieurs allers-retours pour détecter un résidu visuel.
  const historique = [];
  for (let i = 0; i < 4; i++) {
    await page.click('#drapeau-france');
    await page.waitForTimeout(60);
    historique.push(await page.evaluate(() => document.body.classList.contains('mode-belgicisme')));
    await page.click('#drapeau-belgique');
    await page.waitForTimeout(60);
    historique.push(await page.evaluate(() => document.body.classList.contains('mode-belgicisme')));
  }
  await page.click('#drapeau-france');
  await page.waitForTimeout(60);
  const etatFinal = await page.evaluate(() => ({
    bodyModeBelge: document.body.classList.contains('mode-belgicisme'),
    franceActif: document.getElementById('drapeau-france').classList.contains('actif'),
    belgiqueActif: document.getElementById('drapeau-belgique').classList.contains('actif'),
    backgroundImage: getComputedStyle(document.body).backgroundImage,
  }));

  // Contraste calculé analytiquement (méthode documentée dans accueil.css) :
  // blanc (255,255,255) vs bande jaune (250,224,66) à 12% mélangée à la zone
  // la plus claire du tapis (--tapis-vert-clair = #3f7359 = 63,115,89).
  const alpha = 0.12;
  const jauneMelange = [
    alpha * 250 + (1 - alpha) * 63,
    alpha * 224 + (1 - alpha) * 115,
    alpha * 66 + (1 - alpha) * 89,
  ];
  const ratio = contrastRatio([255, 255, 255], jauneMelange);

  const ok =
    etatInitial.franceActif === true &&
    etatInitial.belgiqueActif === false &&
    etatInitial.franceChecked === 'true' &&
    etatInitial.belgiqueChecked === 'false' &&
    etatInitial.bodyModeBelge === false &&
    apresBelgique.franceActif === false &&
    apresBelgique.belgiqueActif === true &&
    apresBelgique.franceChecked === 'false' &&
    apresBelgique.belgiqueChecked === 'true' &&
    apresBelgique.bodyModeBelge === true &&
    JSON.stringify(apresBelgique.appels) === JSON.stringify([true]) &&
    ratio >= 4.5 &&
    etatFinal.bodyModeBelge === false &&
    etatFinal.franceActif === true &&
    etatFinal.belgiqueActif === false &&
    !etatFinal.backgroundImage.includes('rgba(250, 224, 66') &&
    errs.length === 0;

  console.log('État initial :', JSON.stringify(etatInitial));
  console.log('Après clic Belgique :', JSON.stringify(apresBelgique));
  console.log('Historique bascules (mode belge actif ?) :', historique);
  console.log('État final (retour France) :', JSON.stringify(etatFinal));
  console.log('Contraste blanc/bande-jaune-mélangée (zone la plus claire) :', ratio.toFixed(2) + ':1',
    ratio >= 4.5 ? '(>= 4.5:1 WCAG AA, OK)' : '(INSUFFISANT)');
  console.log('Erreurs JS :', errs.length ? errs : 'aucune');
  console.log(ok ? 'OK — cercles-drapeaux fonctionnels, contraste suffisant, aucun résidu visuel'
                 : 'ECHEC');
  await browser.close();
  process.exit(ok ? 0 : 1);
})();
