// Vérification issue #462 : à l'accueil, quand l'interface des personnages
// est masquée (moins de deux personnages actifs), le sélecteur de personnage,
// ses textes d'explication et le lien « Les personnages » doivent disparaître
// réellement — pas seulement porter l'attribut ``hidden``. Même technique que
// verif_443_personnages.mjs (accueil.html monté avec une API mockée).
import pw from '/home/alain/.npm-global/lib/node_modules/playwright/index.js';
const { chromium } = pw;
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '../../src/scrabble/ui/web');

function lire(nom) {
  return fs.readFileSync(path.join(web, nom), 'utf8');
}

function construireHtml({ interfaceVisible, personnages }) {
  const accueilCss = lire('accueil.css');
  const personnagesCss = lire('personnages.css');
  const commun = lire('commun.js');
  const genres = lire('genres.js');
  const accueilJs = lire('accueil.js');
  const mockAccueil = `
    window.pywebview = {
      api: {
        obtenir_etat: async () => ({
          joueurs: [{ nom: 'Alain', humain: true, niveau: null, personnage_libelle: '' }],
          nb_humains: 1, nb_ordinateurs: 0, nb_total: 1,
          peut_ajouter_humain: false, peut_ajouter_ordinateur: true, peut_lancer: true,
          mode_belgicisme: false,
        }),
        lister_parties_en_cours: async () => [],
        obtenir_disponibilite_niveaux: async () => [],
        obtenir_disponibilite_niveaux_personnage: async () => ({ niveaux: [], explication: '' }),
        obtenir_disponibilite_personnage_table: async () => ({ restreint: false }),
        obtenir_personnages: async () => (${JSON.stringify(personnages)}),
        obtenir_prenom_principal: async () => 'Alain',
        interface_personnages_visible: async () => ${interfaceVisible},
      },
    };
  `;
  return lire('accueil.html')
    .replace('<link rel="stylesheet" href="accueil.css">', `<style>${accueilCss}</style>`)
    .replace('<link rel="stylesheet" href="personnages.css">', `<style>${personnagesCss}</style>`)
    .replace('<script src="genres.js"></script>', `<script>${genres}</script>`)
    .replace('<script src="commun.js"></script>', `<script>${commun}</script>`)
    .replace('<script src="accueil.js"></script>', `<script>${mockAccueil}</script><script>${accueilJs}</script>`);
}

const PERSONNAGES_UN_SEUL = [
  { cle: 'classique', prenom: 'Classique', description: 'Joue normalement selon son niveau.' },
];

const PERSONNAGES_DEUX = [
  { cle: 'classique', prenom: 'Classique', description: 'Joue normalement selon son niveau.' },
  { cle: 'opportuniste', prenom: 'Opportuniste', description: 'Se précipite sur les cases bonus.' },
  { cle: 'aleatoire', prenom: 'Aléatoire', description: 'Un caractère sera tiré au sort.' },
];

async function captureScenario(browser, { nom, interfaceVisible, personnages }) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const errs = [];
  page.on('pageerror', e => errs.push(String(e)));
  const html = construireHtml({ interfaceVisible, personnages });
  await page.setContent(html, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await page.waitForTimeout(300);

  const info = await page.evaluate(() => {
    const zone = document.getElementById('zone-personnage');
    const style = window.getComputedStyle(zone);
    const btn = document.getElementById('btn-les-personnages');
    const rectZone = zone.getBoundingClientRect();
    return {
      hiddenAttr: zone.hidden,
      display: style.display,
      visibilityVisible: style.display !== 'none',
      hauteurZone: rectZone.height,
      boutonPersonnagesVisible: !!(btn.offsetWidth || btn.offsetHeight),
    };
  });

  await page.screenshot({ path: path.join(here, `i462_accueil_${nom}_1280x800.png`) });
  await page.close();
  return { nom, errs, ...info };
}

(async () => {
  const browser = await chromium.launch();

  const resultats = [];
  resultats.push(await captureScenario(browser, {
    nom: 'un_personnage',
    interfaceVisible: false,
    personnages: PERSONNAGES_UN_SEUL,
  }));
  resultats.push(await captureScenario(browser, {
    nom: 'deux_personnages',
    interfaceVisible: true,
    personnages: PERSONNAGES_DEUX,
  }));

  await browser.close();

  for (const r of resultats) {
    console.log(JSON.stringify(r));
  }

  const scenarioUn = resultats.find(r => r.nom === 'un_personnage');
  const scenarioDeux = resultats.find(r => r.nom === 'deux_personnages');

  const ok = scenarioUn.hiddenAttr === true
    && scenarioUn.display === 'none'
    && scenarioUn.hauteurZone === 0
    && !scenarioUn.boutonPersonnagesVisible
    && scenarioDeux.hiddenAttr === false
    && scenarioDeux.display !== 'none'
    && scenarioDeux.hauteurZone > 0
    && scenarioDeux.boutonPersonnagesVisible
    && resultats.every(r => r.errs.length === 0);

  console.log(ok ? 'OK — zone-personnage réellement masquée à un seul personnage, visible à deux'
                 : 'ECHEC');
  process.exit(ok ? 0 : 1);
})();
