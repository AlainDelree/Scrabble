// Vérification issues #269 + #270 : cercles-drapeaux France/Belgique de
// l'accueil, et bandeau tricolore du mode Belgicisme.
//
// Contrôle en headless Playwright — le rendu réel WebKitGTK a été vérifié
// manuellement par capture GTK+WebKit2 (issue #270, cf. accueil.css) :
//   1. France actif par défaut, Belgique inactif.
//   2. Clic sur le drapeau belge -> classe .actif bascule, aria-checked
//      correct, body.mode-belgicisme posé, api.definir_mode_belgicisme(true)
//      appelée.
//   3. Bandeau tricolore noir/jaune/rouge opaque (6px, haut de page) présent
//      en mode belge — remplace depuis #270 le voile rgba() à 12% sur toute
//      la page (invisible à l'œil sur fond vert saturé, cf. accueil.css).
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

  // Bandeau tricolore (issue #270) : couleurs opaques du drapeau belge
  // présentes dans le background-image, limitées à une bande fine en haut
  // (background-size 6px de haut) — donc jamais sous le texte, aucune
  // contrainte de contraste à vérifier ici.
  const bandeau = await page.evaluate(() => {
    const style = getComputedStyle(document.body);
    return { backgroundImage: style.backgroundImage, backgroundSize: style.backgroundSize };
  });
  const bandeauOk =
    bandeau.backgroundImage.includes('rgb(0, 0, 0)') &&
    bandeau.backgroundImage.includes('rgb(250, 224, 66)') &&
    bandeau.backgroundImage.includes('rgb(237, 41, 57)') &&
    /\b6px\b/.test(bandeau.backgroundSize);

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
    bandeauOk &&
    etatFinal.bodyModeBelge === false &&
    etatFinal.franceActif === true &&
    etatFinal.belgiqueActif === false &&
    !etatFinal.backgroundImage.includes('rgb(250, 224, 66)') &&
    errs.length === 0;

  console.log('État initial :', JSON.stringify(etatInitial));
  console.log('Après clic Belgique :', JSON.stringify(apresBelgique));
  console.log('Historique bascules (mode belge actif ?) :', historique);
  console.log('État final (retour France) :', JSON.stringify(etatFinal));
  console.log('Bandeau tricolore (issue #270) :', JSON.stringify(bandeau), bandeauOk ? '(OK)' : '(INSUFFISANT)');
  console.log('Erreurs JS :', errs.length ? errs : 'aucune');
  console.log(ok ? 'OK — cercles-drapeaux fonctionnels, bandeau tricolore visible, aucun résidu visuel'
                 : 'ECHEC');
  await browser.close();
  process.exit(ok ? 0 : 1);
})();
