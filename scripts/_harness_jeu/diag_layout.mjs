// Diag temporaire (issue #56) : mesure les rectangles plateau / panneaux.
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
    `<script>window.__THEME__=${JSON.stringify('classique')};${mock}</script><script>${js}</script>`);

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1000, height: 750 } });
  await page.route('**/*', (route) => {
    const url = route.request().url();
    if (url.startsWith('http') && url.includes('avatars/')) {
      const f = path.join(web, url.split('/').slice(-2).join('/'));
      if (fs.existsSync(f)) return route.fulfill({ path: f });
    }
    route.continue();
  });
  await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await page.waitForTimeout(400);

  const data = await page.evaluate(() => {
    const R = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { l: Math.round(r.left), r: Math.round(r.right), cx: Math.round(r.left + r.width / 2), w: Math.round(r.width) };
    };
    const pan = (cote) => {
      const el = document.querySelector(`#slot-${cote} .panneau-joueur`);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { l: Math.round(r.left), r: Math.round(r.right), cx: Math.round(r.left + r.width / 2), w: Math.round(r.width) };
    };
    return {
      plateau: R('#plateau'),
      slotHaut: R('#slot-haut'),
      panHaut: pan('haut'),
      slotGauche: R('#slot-gauche'),
      panGauche: pan('gauche'),
      slotDroite: R('#slot-droite'),
      panDroite: pan('droite'),
      slotBas: R('#slot-bas'),
      panBas: pan('bas'),
      zoneChevalet: R('.zone-chevalet'),
      table: R('.table'),
    };
  });
  console.log(JSON.stringify(data, null, 2));
  await browser.close();
})();
