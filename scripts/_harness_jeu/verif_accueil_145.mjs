// Vérification issue #145 : le joueur humain seedé d'office (#141) apparaît
// bien au PREMIER rendu de l'accueil, y compris quand le pont pywebview publie
// window.pywebview.api APRÈS le DOMContentLoaded (la course réelle qui faisait
// échouer silencieusement le rendu initial). Harnais headless Playwright.
import pw from '/home/alain/.npm-global/lib/node_modules/playwright/index.js';
const { chromium } = pw;
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '../../src/scrabble/ui/web');
const css = fs.readFileSync(path.join(web, 'accueil.css'), 'utf8');
const js = fs.readFileSync(path.join(web, 'accueil.js'), 'utf8');

// Mock reproduisant la SÉQUENCE réelle de pywebview : window.pywebview (jeton)
// est posé tout de suite, mais window.pywebview.api (les méthodes) n'arrive
// qu'un peu plus tard, suivi de l'événement 'pywebviewready'. Un garde qui ne
// teste que window.pywebview résoudrait trop tôt et raterait le rendu initial.
const mock = `
window.pywebview = { platform: 'test' }; // .api PAS encore présent
setTimeout(() => {
  window.pywebview.api = {
    obtenir_etat: async () => ({
      joueurs: [{nom:'Alain', humain:true, niveau:null}],
      nb_humains: 1, nb_ordinateurs: 0, nb_total: 1,
      peut_ajouter_humain: true, peut_ajouter_ordinateur: true, peut_lancer: true
    }),
    obtenir_niveaux: async () => ['Débutant','Facile','Intermédiaire','Expert'],
    lister_parties_en_cours: async () => [],
    obtenir_prenom_principal: async () => 'Alain',
  };
  window.dispatchEvent(new Event('pywebviewready'));
}, 250);
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
  await page.waitForTimeout(700); // laisse passer la publication différée de .api

  const info = await page.evaluate(() => ({
    noms: [...document.querySelectorAll('#liste-joueurs .joueur-item .joueur-nom')].map(e => e.textContent),
    nbHumains: document.getElementById('nb-humains')?.textContent,
    vide: !!document.getElementById('message-vide'),
  }));
  const ok = info.noms.length === 1 && info.noms[0] === 'Alain' && !info.vide && errs.length === 0;
  console.log('Rendu:', JSON.stringify(info), '| erreurs JS:', errs.length ? errs : 'aucune');
  console.log(ok ? 'OK — Alain rendu au premier affichage malgré .api différé'
                 : 'ECHEC');
  await browser.close();
  process.exit(ok ? 0 : 1);
})();
