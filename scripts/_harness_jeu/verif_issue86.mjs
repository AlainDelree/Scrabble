// Vérification visuelle/fonctionnelle temporaire de l'issue #86 (non commité).
import pw from '/home/alain/.npm-global/lib/node_modules/playwright/index.js';
const { chromium } = pw;
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '../../src/scrabble/ui/web');
const css = fs.readFileSync(path.join(web, 'jeu.css'), 'utf8');
const js = fs.readFileSync(path.join(web, 'jeu.js'), 'utf8');
const mock = fs.readFileSync(path.join(here, 'mock.js'), 'utf8');
const html = fs.readFileSync(path.join(web, 'jeu.html'), 'utf8')
  .replace('<link rel="stylesheet" href="jeu.css">', `<style>${css}</style>`)
  .replace('<script src="jeu.js"></script>',
    `<script>window.__THEME__='classique';${mock}</script><script>${js}</script>`);

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  await page.route('**/*', (route) => {
    const url = route.request().url();
    if (url.startsWith('http') && url.includes('avatars/')) {
      const f = path.join(web, url.split('/').slice(-2).join('/'));
      if (fs.existsSync(f)) return route.fulfill({ path: f });
    }
    route.continue();
  });
  const erreurs = [];
  page.on('pageerror', e => erreurs.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') erreurs.push('console: ' + m.text()); });

  await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await page.waitForTimeout(300);

  // Le chevalet + brouillon sont déjà révélés (un seul humain à la table).
  await page.waitForTimeout(200);

  const bilan = {};
  // 1. Bouton de vérification à gauche, libellé visible (fenêtre large).
  bilan.btnVerifVisible = await page.isVisible('#btn-ouvrir-verif');
  bilan.libelleVisible = await page.isVisible('.verif-dico-libelle');
  bilan.popoverInitCache = await page.getAttribute('#verif-dico-popover', 'hidden') !== null;
  // La vérif ne doit PLUS être dans la zone chevalet.
  bilan.champVerifDansChevalet = await page.evaluate(() =>
    !!document.querySelector('.zone-chevalet #champ-verif'));

  // Ouvrir le popover de vérif et tester un mot.
  await page.click('#btn-ouvrir-verif');
  await page.waitForTimeout(150);
  bilan.popoverOuvert = await page.isVisible('#verif-dico-popover');
  await page.fill('#champ-verif', 'test');
  await page.click('#btn-verifier');
  await page.waitForTimeout(150);
  bilan.messageVerif = (await page.textContent('#message-brouillon')).trim();
  await page.screenshot({ path: path.join(here, 'i86_verif_ouvert.png') });
  // Fermeture via Échap.
  await page.keyboard.press('Escape');
  await page.waitForTimeout(150);
  bilan.popoverFermeEchap = !(await page.isVisible('#verif-dico-popover'));

  // 2. Aide brouillon repliée derrière « i ».
  bilan.aidePermanenteAbsente = await page.evaluate(() =>
    !document.querySelector('.brouillon-aide'));
  bilan.iconeIVisible = await page.isVisible('#btn-aide-brouillon');
  bilan.aidePopoverInitCache = !(await page.isVisible('#aide-brouillon-popover'));
  await page.click('#btn-aide-brouillon');
  await page.waitForTimeout(150);
  bilan.aidePopoverOuvert = await page.isVisible('#aide-brouillon-popover');
  bilan.aideTexte = (await page.textContent('#aide-brouillon-popover')).trim().slice(0, 40);
  await page.screenshot({ path: path.join(here, 'i86_aide_ouvert.png') });
  // Fermeture clic extérieur.
  await page.click('#plateau');
  await page.waitForTimeout(150);
  bilan.aideFermeeClicExt = !(await page.isVisible('#aide-brouillon-popover'));

  // 3. Couleur de fond de .zone-chevalet.
  bilan.fondChevalet = await page.evaluate(() =>
    getComputedStyle(document.querySelector('.zone-chevalet')).backgroundColor);

  console.log('ERREURS:', erreurs.length ? erreurs : 'aucune');
  console.log(JSON.stringify(bilan, null, 2));
  await browser.close();
})();
