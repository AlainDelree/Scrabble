// Diag temporaire (issue #56) : reproduit le comportement du <details>
// « Derniers coups » et logge l'état open avant/après clics sur le summary.
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

  const state = async (label) => {
    const s = await page.evaluate(() => {
      const d = document.getElementById('historique-menu');
      const sum = d.querySelector('summary');
      const r = sum.getBoundingClientRect();
      const ol = document.getElementById('historique-liste');
      const or = ol.getBoundingClientRect();
      // Quel élément est au point milieu du summary ?
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      const top = document.elementFromPoint(cx, cy);
      return {
        open: d.hasAttribute('open'),
        summaryRect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
        olRect: { x: Math.round(or.x), y: Math.round(or.y), w: Math.round(or.width), h: Math.round(or.height) },
        elemAtSummaryCenter: top ? (top.tagName + '.' + top.className) : null,
      };
    });
    console.log(label, JSON.stringify(s));
    return s;
  };

  await state('initial');
  // Clic au centre du summary (là où se trouve le texte "Derniers coups")
  const box = await page.evaluate(() => {
    const sum = document.querySelector('#historique-menu summary');
    const r = sum.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  });
  await page.mouse.click(box.x, box.y);
  await page.waitForTimeout(150);
  await state('apres clic 1 (ouvrir)');

  // Recliquer au meme endroit pour fermer
  const box2 = await page.evaluate(() => {
    const sum = document.querySelector('#historique-menu summary');
    const r = sum.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  });
  console.log('box1', JSON.stringify(box), 'box2', JSON.stringify(box2));
  await page.mouse.click(box2.x, box2.y);
  await page.waitForTimeout(150);
  await state('apres clic 2 (fermer)');

  await browser.close();
})();
