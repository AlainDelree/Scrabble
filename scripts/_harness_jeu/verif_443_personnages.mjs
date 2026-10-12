// Vérification issue #443 (lot F bis) : la fenêtre « Les personnages » de
// l'accueil doit avoir exactement la même présentation que celle du jeu
// (même composant commun.js/personnages.css), et l'entrée Aléatoire doit
// être marquée « Dans cette partie » en jeu dès qu'un adversaire y est réglé.
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

async function capture(page, outName) {
  await page.screenshot({ path: path.join(here, outName) });
}

(async () => {
  const browser = await chromium.launch();
  const errs = [];

  // ----- Accueil -----
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
        obtenir_personnages: async () => ([
          { cle: 'classique', prenom: 'Classique', description: 'Joue normalement selon son niveau.' },
          { cle: 'opportuniste', prenom: 'Opportuniste', description: 'Se précipite sur les cases bonus dès qu\\u2019elles sont à sa portée, quitte à négliger la qualité des lettres qu\\u2019il garde sur son chevalet.' },
          { cle: 'aleatoire', prenom: 'Aléatoire', description: 'Un caractère sera tiré au sort au lancement de la partie et restera secret jusqu\\u2019à l\\u2019écran de résultat.' },
        ]),
        obtenir_prenom_principal: async () => 'Alain',
        // Interface personnages visible (issue #461) : la scène ci-dessus
        // compte 3 personnages actifs dans le registre (classique,
        // opportuniste, aléatoire), donc bien au-dessus du seuil de deux
        // qui la ferait masquer — sans cette entrée, l'appel API échoue et
        // zone-personnage/#btn-les-personnages restent masqués (issue
        // #462 : la correction du masquage CSS rend ce mock obligatoire,
        // alors qu'il passait inaperçu avant faute d'effet visible).
        interface_personnages_visible: async () => true,
      },
    };
  `;
  const accueilHtml = lire('accueil.html')
    .replace('<link rel="stylesheet" href="accueil.css">', `<style>${accueilCss}</style>`)
    .replace('<link rel="stylesheet" href="personnages.css">', `<style>${personnagesCss}</style>`)
    .replace('<script src="genres.js"></script>', `<script>${genres}</script>`)
    .replace('<script src="commun.js"></script>', `<script>${commun}</script>`)
    .replace('<script src="accueil.js"></script>', `<script>${mockAccueil}</script><script>${accueilJs}</script>`);

  const pageAccueil = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  pageAccueil.on('pageerror', e => errs.push('accueil: ' + String(e)));
  await pageAccueil.setContent(accueilHtml, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await pageAccueil.waitForTimeout(300);
  await pageAccueil.click('#btn-les-personnages');
  await pageAccueil.waitForTimeout(150);
  await capture(pageAccueil, 'i443_accueil_personnages_1280x800.png');
  const infoAccueil = await pageAccueil.evaluate(() => ({
    visible: !document.getElementById('modale-personnages').hidden,
    nbEntrees: document.querySelectorAll('.personnage-entree').length,
    nbNoms: document.querySelectorAll('.personnage-entree-nom').length,
    nbTags: document.querySelectorAll('.personnage-tag').length,
    largeurModale: document.querySelector('.modale-personnages-contenu').getBoundingClientRect().width,
  }));

  // ----- Jeu -----
  const communCss = lire('commun.css');
  const jeuCss = lire('jeu.css');
  const jeuJs = lire('jeu.js');
  const mockJeu = fs.readFileSync(path.join(here, 'mock.js'), 'utf8');
  const jeuHtml = lire('jeu.html')
    .replace('<link rel="stylesheet" href="commun.css">', `<style>${communCss}</style>`)
    .replace('<link rel="stylesheet" href="jeu.css">', `<style>${jeuCss}</style>`)
    .replace('<link rel="stylesheet" href="personnages.css">', `<style>${personnagesCss}</style>`)
    .replace('<script src="commun.js"></script>', `<script>${commun}</script>`)
    .replace('<script src="jeu.js"></script>', `<script>${mockJeu}</script><script>${jeuJs}</script>`);

  const pageJeu = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  pageJeu.on('pageerror', e => errs.push('jeu: ' + String(e)));
  await pageJeu.setContent(jeuHtml, { waitUntil: 'networkidle', baseURL: 'http://localhost/' });
  await pageJeu.waitForTimeout(300);
  await pageJeu.click('#btn-les-personnages');
  await pageJeu.waitForTimeout(150);
  await capture(pageJeu, 'i443_jeu_personnages_1280x800.png');
  const infoJeu = await pageJeu.evaluate(() => ({
    visible: !document.getElementById('modale-personnages').hidden,
    nbEntrees: document.querySelectorAll('.personnage-entree').length,
    nbNoms: document.querySelectorAll('.personnage-entree-nom').length,
    nbTags: document.querySelectorAll('.personnage-tag').length,
    largeurModale: document.querySelector('.modale-personnages-contenu').getBoundingClientRect().width,
    tagSurAleatoire: (() => {
      const entrees = [...document.querySelectorAll('.personnage-entree')];
      const aleatoire = entrees.find(e => e.querySelector('.personnage-entree-nom').textContent === 'Aléatoire');
      return !!(aleatoire && aleatoire.querySelector('.personnage-tag'));
    })(),
  }));

  console.log('Accueil :', JSON.stringify(infoAccueil));
  console.log('Jeu     :', JSON.stringify(infoJeu));
  console.log('Erreurs JS :', errs.length ? errs : 'aucune');

  const ok = infoAccueil.visible && infoJeu.visible
    && infoAccueil.nbEntrees === 3 && infoJeu.nbEntrees === 3
    && infoAccueil.nbTags === 0 // jamais de marquage à l'accueil
    && infoJeu.tagSurAleatoire === true
    && infoAccueil.largeurModale === infoJeu.largeurModale
    && errs.length === 0;

  console.log(ok ? 'OK — présentations identiques, Aléatoire marqué en jeu, jamais à l\'accueil'
                 : 'ECHEC');
  await browser.close();
  process.exit(ok ? 0 : 1);
})();
