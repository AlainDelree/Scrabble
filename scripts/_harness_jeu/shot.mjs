// Capture d'écran du harnais de rendu (issue #38, non commité).
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
    `<script>window.__THEME__=${JSON.stringify(process.env.THEME || 'classique')};${mock}</script><script>${js}</script>`);

const outName = process.argv[2] || 'shot';
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1000, height: 750 } });
  // Sert depuis le dossier web pour que les avatars (chemin relatif) chargent.
  await page.route('**/*', (route) => {
    const url = route.request().url();
    if (url.startsWith('http') && url.includes('avatars/')) {
      const f = path.join(web, url.split('/').slice(-2).join('/'));
      if (fs.existsSync(f)) return route.fulfill({ path: f });
    }
    route.continue();
  });
  await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await page.waitForTimeout(500);
  const scrollH = await page.evaluate(() => document.body.scrollHeight);
  const vh = await page.evaluate(() => window.innerHeight);
  console.log(`scrollHeight=${scrollH} innerHeight=${vh} scroll=${scrollH > vh ? 'OUI(déborde)' : 'non'}`);
  await page.screenshot({ path: path.join(here, `${outName}.png`) });
  await browser.close();
})();
