// Vérification issues #269 + #270 + #271 + #272 : cercles-drapeaux
// France/Belgique de l'accueil, et fond du mode Belgicisme.
//
// Contrôle en headless Playwright — le rendu réel WebKitGTK a été vérifié
// manuellement par capture GTK+WebKit2 (issues #270/#271/#272, cf.
// verif_belgicisme_270_webkitgtk.py et accueil.css) :
//   1. France actif par défaut, Belgique inactif.
//   2. Clic sur le drapeau belge -> classe .actif bascule, aria-checked
//      correct, body.mode-belgicisme posé, api.definir_mode_belgicisme(true)
//      appelée.
//   3. Fond blanc + voile tricolore noir/jaune/rouge quasi-opaque (alpha
//      0.95, issue #272 — remplace l'alpha 0.22/0.32/0.26 trop pâle de #271,
//      qui remplaçait le bandeau opaque 6px de #270, qui remplaçait lui-même
//      le voile 12% invisible sur fond vert de #269) sur TOUTE la surface.
//   4. Titre, sous-titre et légendes des drapeaux en texte noir uniforme
//      (#1a1a1a), SANS plaque de fond (issue #272 — supprime le système de
//      plaques blanches de #271) en mode Belgicisme — inchangés (texte
//      blanc, pas de plaque) en mode France.
//   5. Plusieurs allers-retours France <-> Belgique : aucun résidu visuel
//      (retour exact au fond normal, un seul cercle actif à la fois).
import pw from '/home/alain/.npm-global/lib/node_modules/playwright/index.js';
const { chromium } = pw;
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '../../src/scrabble/ui/web');
const css = fs.readFileSync(path.join(web, 'accueil.css'), 'utf8');
const js = fs.readFileSync(path.join(web, 'accueil.js'), 'utf8');

const mock = `
window.pywebview = { platform: 'test' };
window.__appelsMode = [];
setTimeout(() => {
  window.pywebview.api = {
    obtenir_etat: async () => ({
      joueurs: [{nom:'Alain', humain:true, niveau:null}],
      nb_humains: 1, nb_ordinateurs: 0, nb_total: 1,
      peut_ajouter_humain: true, peut_ajouter_ordinateur: true, peut_lancer: true,
      mode_belgicisme: false,
    }),
    obtenir_niveaux: async () => ['Débutant','Facile','Intermédiaire','Expert'],
    lister_parties_en_cours: async () => [],
    obtenir_prenom_principal: async () => 'Alain',
    definir_mode_belgicisme: async (actif) => {
      window.__appelsMode.push(actif);
      return { succes: true, mode_belgicisme: actif };
    },
  };
  window.dispatchEvent(new Event('pywebviewready'));
}, 100);
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
  await page.waitForTimeout(400);

  const etatInitial = await page.evaluate(() => ({
    franceActif: document.getElementById('drapeau-france').classList.contains('actif'),
    belgiqueActif: document.getElementById('drapeau-belgique').classList.contains('actif'),
    franceChecked: document.getElementById('drapeau-france').getAttribute('aria-checked'),
    belgiqueChecked: document.getElementById('drapeau-belgique').getAttribute('aria-checked'),
    bodyModeBelge: document.body.classList.contains('mode-belgicisme'),
  }));

  // Capture avant/après pour vérification visuelle manuelle.
  await page.screenshot({ path: path.join(here, 'i269_accueil_avant.png') });

  // Clic Belgique.
  await page.click('#drapeau-belgique');
  await page.waitForTimeout(100);
  const apresBelgique = await page.evaluate(() => ({
    franceActif: document.getElementById('drapeau-france').classList.contains('actif'),
    belgiqueActif: document.getElementById('drapeau-belgique').classList.contains('actif'),
    franceChecked: document.getElementById('drapeau-france').getAttribute('aria-checked'),
    belgiqueChecked: document.getElementById('drapeau-belgique').getAttribute('aria-checked'),
    bodyModeBelge: document.body.classList.contains('mode-belgicisme'),
    appels: window.__appelsMode,
  }));
  await page.screenshot({ path: path.join(here, 'i269_accueil_belgique.png') });

  // Fond blanc + voile tricolore quasi-opaque sur toute la surface
  // (issue #272, alpha 0.95 — remplace l'alpha 0.22/0.32/0.26 trop pâle de
  // #271) : fond blanc uni + les trois couleurs franches du drapeau belge
  // présentes dans le background-image, étalées sur 100% de la surface.
  const fond = await page.evaluate(() => {
    const style = getComputedStyle(document.body);
    return {
      backgroundColor: style.backgroundColor,
      backgroundImage: style.backgroundImage,
      backgroundSize: style.backgroundSize,
    };
  });
  const fondOk =
    fond.backgroundColor === 'rgb(255, 255, 255)' &&
    fond.backgroundImage.includes('rgba(0, 0, 0, 0.95)') &&
    fond.backgroundImage.includes('rgba(250, 224, 66, 0.95)') &&
    fond.backgroundImage.includes('rgba(237, 41, 57, 0.95)') &&
    /100%\s*100%/.test(fond.backgroundSize);

  // Titre/sous-titre/légendes en texte noir uniforme, SANS plaque de fond
  // (issue #272 — supprime le système de plaques blanches ciblées de #271 :
  // tout le contenu repose sur la bande jaune, un texte sombre y suffit).
  const textes = await page.evaluate(() => {
    const lire = (sel) => {
      const el = document.querySelector(sel);
      const style = getComputedStyle(el);
      return { color: style.color, backgroundColor: style.backgroundColor };
    };
    return {
      titre: lire('header h1'),
      sousTitre: lire('.subtitle'),
      legendeFrance: lire('.drapeau-choix:nth-child(1) .drapeau-legende'),
      legendeBelgique: lire('.drapeau-choix:nth-child(2) .drapeau-legende'),
    };
  });
  const noirSansPlaque = (v) =>
    v.color === 'rgb(26, 26, 26)' &&
    (v.backgroundColor === 'rgba(0, 0, 0, 0)' || v.backgroundColor === 'transparent');
  const textesOk =
    noirSansPlaque(textes.titre) &&
    noirSansPlaque(textes.sousTitre) &&
    noirSansPlaque(textes.legendeFrance) &&
    noirSansPlaque(textes.legendeBelgique);

  // Plusieurs allers-retours pour détecter un résidu visuel.
  const historique = [];
  for (let i = 0; i < 4; i++) {
    await page.click('#drapeau-france');
    await page.waitForTimeout(60);
    historique.push(await page.evaluate(() => document.body.classList.contains('mode-belgicisme')));
    await page.click('#drapeau-belgique');
    await page.waitForTimeout(60);
    historique.push(await page.evaluate(() => document.body.classList.contains('mode-belgicisme')));
  }
  await page.click('#drapeau-france');
  await page.waitForTimeout(60);
  const etatFinal = await page.evaluate(() => {
    const style = getComputedStyle(document.body);
    const h1 = getComputedStyle(document.querySelector('header h1'));
    return {
      bodyModeBelge: document.body.classList.contains('mode-belgicisme'),
      franceActif: document.getElementById('drapeau-france').classList.contains('actif'),
      belgiqueActif: document.getElementById('drapeau-belgique').classList.contains('actif'),
      backgroundImage: style.backgroundImage,
      backgroundColor: style.backgroundColor,
      titreCouleur: h1.color,
      titreFond: h1.backgroundColor,
    };
  });

  // Mode France (initial et après retour) : texte blanc, aucune plaque —
  // strictement inchangé par le mode Belgicisme (issues #271/#272).
  const franceInchange = (etat) =>
    etat.titreCouleur === 'rgb(255, 255, 255)' &&
    (etat.titreFond === 'rgba(0, 0, 0, 0)' || etat.titreFond === 'transparent');
  const titreInitial = await page.evaluate(() => {
    const h1 = getComputedStyle(document.querySelector('header h1'));
    return { titreCouleur: h1.color, titreFond: h1.backgroundColor };
  });

  const ok =
    etatInitial.franceActif === true &&
    etatInitial.belgiqueActif === false &&
    etatInitial.franceChecked === 'true' &&
    etatInitial.belgiqueChecked === 'false' &&
    etatInitial.bodyModeBelge === false &&
    franceInchange(titreInitial) &&
    apresBelgique.franceActif === false &&
    apresBelgique.belgiqueActif === true &&
    apresBelgique.franceChecked === 'false' &&
    apresBelgique.belgiqueChecked === 'true' &&
    apresBelgique.bodyModeBelge === true &&
    JSON.stringify(apresBelgique.appels) === JSON.stringify([true]) &&
    fondOk &&
    textesOk &&
    etatFinal.bodyModeBelge === false &&
    etatFinal.franceActif === true &&
    etatFinal.belgiqueActif === false &&
    etatFinal.backgroundColor !== 'rgb(255, 255, 255)' &&
    !etatFinal.backgroundImage.includes('rgba(250, 224, 66,') &&
    franceInchange(etatFinal) &&
    errs.length === 0;

  console.log('État initial :', JSON.stringify(etatInitial));
  console.log('Après clic Belgique :', JSON.stringify(apresBelgique));
  console.log('Fond blanc + voile tricolore quasi-opaque (issue #272) :', JSON.stringify(fond), fondOk ? '(OK)' : '(INSUFFISANT)');
  console.log('Titre/sous-titre/légendes texte noir sans plaque (issue #272) :', JSON.stringify(textes), textesOk ? '(OK)' : '(INSUFFISANT)');
  console.log('Historique bascules (mode belge actif ?) :', historique);
  console.log('État final (retour France) :', JSON.stringify(etatFinal));
  console.log('Erreurs JS :', errs.length ? errs : 'aucune');
  console.log(ok ? 'OK — cercles-drapeaux fonctionnels, fond blanc+tricolore franc, texte sans plaque, aucun résidu visuel'
                 : 'ECHEC');
  await browser.close();
  process.exit(ok ? 0 : 1);
})();
