// Vérification issues #269 + #270 + #271 + #272 + #289 + #290 + #291 + #292 :
// cercles-drapeaux France/Belgique de l'accueil, et fond du mode Belgicisme.
//
// Contrôle en headless Playwright — le rendu réel WebKitGTK a été vérifié
// manuellement par capture GTK+WebKit2 (issues #270/#271/#272/#289/#290/#291/
// #292, cf. verif_belgicisme_292_webkitgtk.py et accueil.css) :
//   1. France actif par défaut, Belgique inactif.
//   2. Clic sur le drapeau belge -> classe .actif bascule, aria-checked
//      correct, body.mode-belgicisme posé, api.definir_mode_belgicisme(true)
//      appelée.
//   3. Fond en image (`images/drapeau-belge.jpg`, issue #292 — remplace le
//      voile CSS en `linear-gradient` des issues #271/#272 qui ne rendait
//      jamais le tissu ondulé voulu par Alain), étiré sur toute la surface
//      (`background-size: 100% 100%`).
//   4. Sous-titre et légendes des drapeaux en texte noir uniforme
//      (#1a1a1a), SANS plaque de fond (issue #272 — supprime le système de
//      plaques blanches de #271) en mode Belgicisme — inchangés (texte
//      blanc, pas de plaque) en mode France. Le titre principal ("Scrabble")
//      n'est PLUS concerné par cette règle depuis #290 : voir point 7.
//   5. Plusieurs allers-retours France <-> Belgique : aucun résidu visuel
//      (retour exact au fond normal, un seul cercle actif à la fois).
//   6. Panneau quasi opaque central (issue #289, opacité réduite à 60% par
//      #290 puis 50% par #291, remontée à 95% par #292 — l'image de fond
//      n'a plus besoin de transparaître à travers le panneau) : à plusieurs
//      largeurs de fenêtre (700px repli, ~1280px résolution cible, 1920px
//      pleine largeur), `.container` reste entièrement contenu dans le
//      panneau de `.container::before` (aucun débordement sur le fond), et
//      le panneau laisse toujours une marge visible avec le bord de la
//      fenêtre (drapeau visible en bordure comme au centre à travers le
//      panneau, quasiment opaque).
//   7. Titre en tuiles de Scrabble (issue #290) : en mode Belgicisme, chaque
//      lettre de "Scrabble" (8 `<span class="lettre-scrabble">`) porte un
//      fond opaque crème (#f5e6c8) et un contour doré — pas de couleur de
//      texte uniforme sur le h1 lui-même. En mode France, ces spans restent
//      sans style propre (texte blanc hérité du h1, comme avant #290).
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

  // Fond en image de drapeau ondulé, étiré sur toute la surface (issue
  // #292 — remplace le voile CSS en `linear-gradient` des issues #271/#272).
  const fond = await page.evaluate(() => {
    const style = getComputedStyle(document.body);
    return {
      backgroundColor: style.backgroundColor,
      backgroundImage: style.backgroundImage,
      backgroundSize: style.backgroundSize,
    };
  });
  const fondOk =
    fond.backgroundImage.includes('drapeau-belge.jpg') &&
    /100%\s*100%/.test(fond.backgroundSize);

  // Sous-titre/légendes en texte noir uniforme, SANS plaque de fond (issue
  // #272 — supprime le système de plaques blanches ciblées de #271). Le
  // titre principal n'est PLUS dans ce groupe depuis #290 (vérifié à part
  // ci-dessous, en tuiles).
  const textes = await page.evaluate(() => {
    const lire = (sel) => {
      const el = document.querySelector(sel);
      const style = getComputedStyle(el);
      return { color: style.color, backgroundColor: style.backgroundColor };
    };
    return {
      sousTitre: lire('.subtitle'),
      legendeFrance: lire('.drapeau-choix:nth-child(1) .drapeau-legende'),
      legendeBelgique: lire('.drapeau-choix:nth-child(2) .drapeau-legende'),
    };
  });
  const noirSansPlaque = (v) =>
    v.color === 'rgb(26, 26, 26)' &&
    (v.backgroundColor === 'rgba(0, 0, 0, 0)' || v.backgroundColor === 'transparent');
  const textesOk =
    noirSansPlaque(textes.sousTitre) &&
    noirSansPlaque(textes.legendeFrance) &&
    noirSansPlaque(textes.legendeBelgique);

  // Titre en tuiles de Scrabble (issue #290) : les 8 lettres de "Scrabble"
  // (`header h1 .lettre-scrabble`) doivent chacune porter un fond opaque
  // crème et une couleur de texte sombre distincte de la couleur France
  // (blanc) — la preuve que le titre n'est plus un texte plat mais bien
  // composé de tuiles individuelles en mode Belgicisme.
  const tuiles = await page.evaluate(() => {
    const spans = Array.from(document.querySelectorAll('header h1 .lettre-scrabble'));
    return spans.map((el) => {
      const style = getComputedStyle(el);
      return { texte: el.textContent, color: style.color, backgroundColor: style.backgroundColor };
    });
  });
  const tuilesOk =
    tuiles.length === 8 &&
    tuiles.map((t) => t.texte).join('') === 'Scrabble' &&
    tuiles.every((t) => t.backgroundColor === 'rgb(245, 230, 200)' && t.color === 'rgb(74, 52, 24)');

  // Panneau quasi opaque central (issue #289, opacité 60% par #290, 50% par
  // #291, 95% par #292) : à plusieurs largeurs de fenêtre (700px repli,
  // ~1280px résolution cible, 1920px pleine largeur déjà correcte avant
  // #289 — ne doit pas être cassée), `.container` doit rester entièrement
  // contenu dans le panneau de `.container::before`, et le panneau doit
  // toujours laisser une marge visible avec le bord de fenêtre (drapeau
  // visible en bordure).
  const largeursPanneau = [700, 1280, 1920];
  const mesuresPanneau = [];
  for (const largeur of largeursPanneau) {
    await page.setViewportSize({ width: largeur, height: 780 });
    await page.waitForTimeout(60);
    const mesure = await page.evaluate(() => {
      const conteneur = document.querySelector('.container');
      const rectConteneur = conteneur.getBoundingClientRect();
      const stylePanneau = getComputedStyle(conteneur, '::before');
      const largeurPanneau = parseFloat(stylePanneau.width);
      const centreFenetre = window.innerWidth / 2;
      const panneauGauche = centreFenetre - largeurPanneau / 2;
      const panneauDroit = centreFenetre + largeurPanneau / 2;
      return {
        largeurFenetre: window.innerWidth,
        fondPanneau: stylePanneau.backgroundColor,
        largeurPanneau,
        panneauGauche,
        panneauDroit,
        conteneurGauche: rectConteneur.left,
        conteneurDroit: rectConteneur.right,
      };
    });
    mesuresPanneau.push({ largeur, ...mesure });
  }
  await page.setViewportSize({ width: 700, height: 780 });
  await page.waitForTimeout(60);
  const TOLERANCE = 1;
  const panneauOk = mesuresPanneau.every((m) =>
    m.conteneurGauche >= m.panneauGauche - TOLERANCE &&
    m.conteneurDroit <= m.panneauDroit + TOLERANCE &&
    m.panneauGauche > 0 &&
    m.panneauDroit < m.largeurFenetre &&
    m.fondPanneau === 'rgba(255, 255, 255, 0.95)'
  );

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
    tuilesOk &&
    panneauOk &&
    etatFinal.bodyModeBelge === false &&
    etatFinal.franceActif === true &&
    etatFinal.belgiqueActif === false &&
    etatFinal.backgroundColor !== 'rgb(13, 13, 13)' &&
    !etatFinal.backgroundImage.includes('drapeau-belge.jpg') &&
    franceInchange(etatFinal) &&
    errs.length === 0;

  console.log('État initial :', JSON.stringify(etatInitial));
  console.log('Après clic Belgique :', JSON.stringify(apresBelgique));
  console.log('Fond blanc + voile tricolore quasi-opaque (issue #272) :', JSON.stringify(fond), fondOk ? '(OK)' : '(INSUFFISANT)');
  console.log('Sous-titre/légendes texte noir sans plaque (issue #272) :', JSON.stringify(textes), textesOk ? '(OK)' : '(INSUFFISANT)');
  console.log('Titre en tuiles de Scrabble (issue #290) :', JSON.stringify(tuiles), tuilesOk ? '(OK)' : '(INSUFFISANT)');
  console.log('Panneau translucide central (issues #289/#290), par largeur :', JSON.stringify(mesuresPanneau), panneauOk ? '(OK)' : '(DEBORDEMENT/OPACITE)');
  console.log('Historique bascules (mode belge actif ?) :', historique);
  console.log('État final (retour France) :', JSON.stringify(etatFinal));
  console.log('Erreurs JS :', errs.length ? errs : 'aucune');
  console.log(ok ? 'OK — cercles-drapeaux fonctionnels, fond image drapeau, texte sans plaque, titre en tuiles, panneau quasi opaque (95%) sans débordement à 700/1280/1920px, aucun résidu visuel'
                 : 'ECHEC');
  await browser.close();
  process.exit(ok ? 0 : 1);
})();
