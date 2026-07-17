// Vérification visuelle/fonctionnelle temporaire de l'issue #88 (non commité).
// Objectif : l'icône « i » d'aide du brouillon (.btn-aide-info) reste sur la
// MÊME ligne que le texte du titre (.brouillon-titre) tant que la largeur le
// permet — au lieu de repasser à la ligne du dessous (bug #88, suite #86).
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

// « défaut à l'ouverture » (fenêtre courante typique) et « maximisée ».
const tailles = [
  { nom: 'defaut', width: 1366, height: 768 },
  { nom: 'maximisee', width: 1920, height: 1080 },
];

(async () => {
  const browser = await chromium.launch();
  let toutOK = true;
  const bilan = {};
  for (const t of tailles) {
    const page = await browser.newPage({ viewport: { width: t.width, height: t.height } });
    await page.route('**/*', (route) => {
      const url = route.request().url();
      if (url.startsWith('http') && url.includes('avatars/')) {
        const f = path.join(web, url.split('/').slice(-2).join('/'));
        if (fs.existsSync(f)) return route.fulfill({ path: f });
      }
      route.continue();
    });
    await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
    await page.waitForTimeout(300);

    const mesure = await page.evaluate(() => {
      const titre = document.querySelector('.brouillon-titre');
      const btn = document.querySelector('#btn-aide-brouillon');
      const rt = titre.getBoundingClientRect();
      const rb = btn.getBoundingClientRect();
      // Centre vertical du bouton dans la plage verticale du titre => même ligne.
      const centreBtn = rb.top + rb.height / 2;
      const memeLigne = centreBtn >= rt.top && centreBtn <= rt.bottom;
      // Le bouton est bien À DROITE (après) du texte, pas dessous.
      const apresTexte = rb.left >= rt.left;
      return {
        titreRect: { top: Math.round(rt.top), bottom: Math.round(rt.bottom), left: Math.round(rt.left), right: Math.round(rt.right) },
        btnRect: { top: Math.round(rb.top), bottom: Math.round(rb.bottom), left: Math.round(rb.left) },
        memeLigne, apresTexte,
      };
    });
    const ok = mesure.memeLigne && mesure.apresTexte;
    toutOK = toutOK && ok;
    bilan[t.nom] = { ...mesure, OK: ok };
    await page.screenshot({ path: path.join(here, `i88_${t.nom}.png`) });
    await page.close();
  }

  console.log(JSON.stringify(bilan, null, 2));
  console.log('RESULTAT:', toutOK ? 'OK — icône sur la même ligne que le titre' : 'ECHEC — icône repliée');
  await browser.close();
  process.exit(toutOK ? 0 : 1);
})();
