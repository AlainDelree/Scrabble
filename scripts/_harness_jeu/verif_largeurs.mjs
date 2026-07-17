// Vérif responsive du bouton Vérification dictionnaire (issue #86, non commité).
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

const largeurs = [1200, 1400, 1600, 1920];
(async () => {
  const browser = await chromium.launch();
  for (const w of largeurs) {
    const page = await browser.newPage({ viewport: { width: w, height: 900 } });
    await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
    await page.waitForTimeout(250);
    const info = await page.evaluate(() => {
      const a = document.querySelector('.verif-dico-ancre');
      const btn = document.getElementById('btn-ouvrir-verif');
      const lib = document.querySelector('.verif-dico-libelle');
      // 1er élément de contenu à gauche = le sac.
      const sac = document.querySelector('.sac');
      const decor = document.querySelector('.decor-scrabble');
      const rb = btn.getBoundingClientRect();
      const rs = sac.getBoundingClientRect();
      const rd = decor.getBoundingClientRect();
      const decorVisible = getComputedStyle(decor).display !== 'none';
      return {
        btnLeft: Math.round(rb.left), btnRight: Math.round(rb.right),
        sacLeft: Math.round(rs.left),
        decorRight: decorVisible ? Math.round(rd.right) : null,
        labelAffiche: getComputedStyle(lib).display !== 'none',
        chevaucheContenu: rb.right > rs.left,
        chevaucheDecor: decorVisible ? rb.left < rd.right : false,
        surEcran: rb.left >= 0 && rb.right <= window.innerWidth,
      };
    });
    console.log(`w=${w}`, JSON.stringify(info));
    await page.screenshot({ path: path.join(here, `i86_w${w}.png`), clip: { x: 0, y: 0, width: Math.min(w, 700), height: 120 } });
    await page.close();
  }
  await browser.close();
})();
