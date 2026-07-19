// Vérification issue #119 : la zone cliquable de chaque niveau de difficulté
// couvre bien tout le rectangle (haut, bas, centre, texte), pas seulement la
// ligne du texte/du rond. Harnais headless Playwright (comme verif_issue86.mjs
// / verif_issue88.mjs).
import pw from '/home/alain/.npm-global/lib/node_modules/playwright/index.js';
const { chromium } = pw;
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '../../src/scrabble/ui/web');
const css = fs.readFileSync(path.join(web, 'accueil.css'), 'utf8');
const js = fs.readFileSync(path.join(web, 'accueil.js'), 'utf8');

// Mock minimal de pywebview.api : juste assez pour que l'initialisation de
// accueil.js aille jusqu'au bout (obtenir_etat / obtenir_niveaux /
// lister_parties_en_cours), afin que #liste-niveaux soit rempli par le vrai code.
const mock = `
window.pywebview = { api: {
  obtenir_etat: async () => ({
    joueurs: [], nb_humains: 0, nb_ordinateurs: 0,
    peut_ajouter_humain: true, peut_ajouter_ordinateur: true, peut_lancer: false
  }),
  obtenir_niveaux: async () => ['Débutant', 'Facile', 'Intermédiaire', 'Expert'],
  lister_parties_en_cours: async () => [],
} };
`;

const html = fs.readFileSync(path.join(web, 'accueil.html'), 'utf8')
  .replace('<link rel="stylesheet" href="accueil.css">', `<style>${css}</style>`)
  .replace('<script src="accueil.js"></script>',
    `<script>${mock}</script><script>${js}</script>`);

const ZONES = [
  { nom: 'haut',   frac: 0.05 },
  { nom: 'centre', frac: 0.50 },
  { nom: 'bas',    frac: 0.95 },
  { nom: 'texte',  frac: 0.50, surTexte: true },
];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 900, height: 700 } });
  await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await page.waitForTimeout(300);

  // Rendre la modale visible pour pouvoir cliquer réellement à la souris.
  await page.evaluate(() => {
    document.getElementById('modale-ordinateur').hidden = false;
  });
  await page.waitForTimeout(100);

  const nbOptions = await page.evaluate(() =>
    document.querySelectorAll('#liste-niveaux .niveau-option').length);
  if (nbOptions !== 4) {
    console.log(`ECHEC : ${nbOptions} option(s) rendues au lieu de 4`);
    await browser.close();
    process.exit(1);
  }

  let echecs = 0;
  for (let i = 0; i < 4; i++) {
    for (const z of ZONES) {
      // Pré-sélectionner un AUTRE radio, pour prouver que c'est bien le clic
      // qui sélectionne l'option testée (et non un état déjà en place).
      await page.evaluate((idx) => {
        const radios = document.querySelectorAll('#liste-niveaux input[type="radio"]');
        radios[(idx + 1) % radios.length].checked = true;
      }, i);

      const box = await page.evaluate((idx) => {
        const opt = document.querySelectorAll('#liste-niveaux .niveau-option')[idx];
        const r = opt.getBoundingClientRect();
        return { x: r.x, y: r.y, w: r.width, h: r.height };
      }, i);

      let cx, cy;
      if (z.surTexte) {
        const t = await page.evaluate((idx) => {
          const el = document.querySelectorAll('#liste-niveaux .niveau-nom')[idx];
          const r = el.getBoundingClientRect();
          return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
        }, i);
        cx = t.x; cy = t.y;
      } else {
        cx = box.x + box.w / 2;
        cy = box.y + box.h * z.frac;
      }

      await page.mouse.click(cx, cy);

      const checkedIndex = await page.evaluate(() => {
        const radios = [...document.querySelectorAll('#liste-niveaux input[type="radio"]')];
        return radios.findIndex(r => r.checked);
      });

      const ok = checkedIndex === i;
      if (!ok) echecs++;
      console.log(`option ${i} / zone ${z.nom.padEnd(6)} → radio coché = ${checkedIndex} ${ok ? 'OK' : 'ECHEC'}`);
    }
  }

  await browser.close();
  console.log(echecs === 0 ? '\nTOUS OK — zone cliquable complète pour les 4 niveaux'
                           : `\n${echecs} ECHEC(S)`);
  process.exit(echecs === 0 ? 0 : 1);
})();
