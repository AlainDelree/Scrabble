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

// La 1re entrée (1320×940) reproduit la taille de fenêtre par défaut à
// l'ouverture du jeu (webview 1320×980, cf. lancer_jeu ; ~940px de contenu
// après décor de fenêtre). C'est ce cas — icône seule, décor visible — qui
// faisait chevaucher la loupe et le « S » du décor (issue #87). Les autres
// largeurs couvrent le repli icône (<1780px) et le libellé complet (≥1780px).
const cas = [
  { w: 1320, h: 940, nom: 'ouverture' },
  { w: 1200, h: 900 },
  { w: 1400, h: 900 },
  { w: 1600, h: 900 },
  { w: 1920, h: 900 },
];
(async () => {
  const browser = await chromium.launch();
  for (const { w, h, nom } of cas) {
    const page = await browser.newPage({ viewport: { width: w, height: h } });
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
      // Vrai chevauchement visuel = intersection des rectangles sur les DEUX
      // axes (issue #87). L'ancien test ne regardait que l'axe horizontal : or
      // le décor est désormais décalé vers le bas (top:64px) pour passer SOUS le
      // bouton, si bien qu'ils peuvent partager la même bande horizontale sans
      // jamais se recouvrir à l'écran.
      const chevaucheDecor = decorVisible
        && rb.left < rd.right && rb.right > rd.left
        && rb.top < rd.bottom && rb.bottom > rd.top;
      return {
        btnLeft: Math.round(rb.left), btnRight: Math.round(rb.right),
        btnBottom: Math.round(rb.bottom),
        sacLeft: Math.round(rs.left),
        decorRight: decorVisible ? Math.round(rd.right) : null,
        decorTop: decorVisible ? Math.round(rd.top) : null,
        labelAffiche: getComputedStyle(lib).display !== 'none',
        chevaucheContenu: rb.right > rs.left,
        chevaucheDecor,
        surEcran: rb.left >= 0 && rb.right <= window.innerWidth,
      };
    });
    console.log(`w=${w}${nom ? ' (' + nom + ')' : ''}`, JSON.stringify(info));
    await page.screenshot({ path: path.join(here, `i86_w${w}.png`), clip: { x: 0, y: 0, width: Math.min(w, 700), height: 160 } });
    await page.close();
  }
  await browser.close();
})();
