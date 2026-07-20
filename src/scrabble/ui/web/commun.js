/**
 * commun.js — fonctions et constantes partagées par les deux fenêtres de jeu
 * (plateau + chevalet), issue #90.
 *
 * La séparation plateau/chevalet en deux fenêtres pywebview distinctes (jeu.html
 * et chevalet.html) fait que ces deux vues partagent beaucoup de briques : rendu
 * d'une tuile, échappement HTML, libellés des cases bonus, popovers repliés,
 * modale de choix du joker, modale de détail du score. On les factorise ici,
 * exposées sous le namespace global ``window.Commun`` (pywebview charge des
 * scripts classiques, pas des modules ES — d'où le namespace plutôt qu'un
 * ``export``).
 */
(function () {
    'use strict';

    /** Attend que le pont pywebview soit prêt (API Python disponible). */
    function pretPywebview() {
        return new Promise((resolve) => {
            if (window.pywebview && window.pywebview.api) {
                resolve();
            } else {
                window.addEventListener('pywebviewready', resolve, { once: true });
            }
        });
    }

    /** Échappe le HTML pour éviter les injections. */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    /** Icône selon la nature du joueur (cohérent avec l'écran d'accueil). */
    function icone(humain) {
        return humain ? '👤' : '🖥️';
    }

    /**
     * Construit une tuile posée (sur le plateau ou en indice du chevalet) avec sa
     * valeur en points en indice. ``enAttente`` marque une tuile non validée.
     */
    function creerTuile(cell, enAttente) {
        const tuile = document.createElement('div');
        tuile.className = 'tuile'
            + (cell.joker ? ' tuile-joker' : '')
            + (enAttente ? ' tuile-attente' : '');
        tuile.textContent = cell.lettre;
        const valeur = document.createElement('span');
        valeur.className = 'tuile-valeur';
        valeur.textContent = cell.joker ? 0 : (cell.valeur || 0);
        tuile.appendChild(valeur);
        return tuile;
    }

    // Libellés des cases bonus. LABEL_TOOLTIP : info-bulle (français complet,
    // indépendant du thème). LABEL_COMPLET / LABEL_ABREGE : texte affiché DANS la
    // case selon le thème. LABEL_BONUS : phrase utilisée dans le détail de score.
    const LABEL_TOOLTIP = {
        'MT': 'Mot compte triple',
        'MD': 'Mot compte double',
        'LT': 'Lettre compte triple',
        'LD': 'Lettre compte double',
        'centre': 'Case centrale (mot compte double)',
        'normale': ''
    };
    const LABEL_COMPLET = {
        'MT': 'MOT ×3', 'MD': 'MOT ×2', 'LT': 'LET ×3', 'LD': 'LET ×2',
        'centre': '★', 'normale': ''
    };
    const LABEL_ABREGE = {
        'MT': 'MT', 'MD': 'MD', 'LT': 'LT', 'LD': 'LD', 'centre': '★', 'normale': ''
    };
    const LABEL_BONUS = {
        'MT': 'mot compte triple',
        'MD': 'mot compte double',
        'LT': 'lettre compte triple',
        'LD': 'lettre compte double',
        'centre': 'case centrale (mot compte double)',
        'normale': '',
    };
    // Thèmes reconnus (alignés avec scrabble.config.THEMES_PLATEAU et le CSS).
    const THEMES = ['classique', 'vert', 'abrege'];

    // Registre des popovers câblés dans CETTE fenêtre (issue #151). Chaque
    // ``configurerPopover`` y enregistre sa fonction ``fermer`` afin qu'ouvrir un
    // popover puisse refermer tous les autres déjà ouverts (« Derniers coups » vs
    // « Vérification dictionnaire »). Le registre est local à la fenêtre : plateau
    // et chevalet sont deux documents web indépendants avec chacun leur copie de
    // ``commun.js``, donc leurs registres ne se voient pas (cf. limite cross-fenêtre
    // documentée dans l'issue).
    const popoversCables = [];

    /** Ferme tous les popovers câblés de la fenêtre, sauf celui exclu (issue #151). */
    function fermerAutresPopovers(exclu) {
        popoversCables.forEach((p) => {
            if (p.fermer !== exclu) {
                p.fermer();
            }
        });
    }

    /**
     * Ferme TOUS les popovers câblés de la fenêtre (issue #151). Sert au plateau
     * pour refermer « Derniers coups »/« Vérification dictionnaire » restés ouverts
     * quand une action de tour survient — y compris une action déclenchée depuis la
     * fenêtre chevalet, dont l'effet arrive au plateau via la diffusion d'état. Les
     * deux fenêtres étant des documents web indépendants, un clic dans le chevalet
     * ne produit aucun événement dans le plateau : c'est ce signal applicatif qui
     * pallie l'absence de ``blur``/clic extérieur cross-fenêtre.
     */
    function fermerTousPopovers() {
        popoversCables.forEach((p) => p.fermer());
    }

    /**
     * Câble un bouton déclencheur + son popover : ouverture/fermeture au clic sur
     * le bouton, fermeture au clic hors du popover ou à la touche Échap. Met à
     * jour aria-expanded. ``onOuvrir`` (optionnel) est appelé à chaque ouverture.
     * Ouvrir un popover ferme automatiquement tout autre popover câblé encore
     * ouvert dans la même fenêtre (issue #151).
     */
    function configurerPopover(bouton, popover, onOuvrir) {
        if (!bouton || !popover) {
            return;
        }
        const estOuvert = () => !popover.hidden;
        const fermer = () => {
            if (popover.hidden) {
                return;
            }
            popover.hidden = true;
            bouton.setAttribute('aria-expanded', 'false');
        };
        popoversCables.push({ fermer });
        const ouvrir = () => {
            fermerAutresPopovers(fermer);
            popover.hidden = false;
            bouton.setAttribute('aria-expanded', 'true');
            if (typeof onOuvrir === 'function') {
                onOuvrir();
            }
        };
        bouton.addEventListener('click', (evt) => {
            evt.stopPropagation();
            estOuvert() ? fermer() : ouvrir();
        });
        popover.addEventListener('click', (evt) => { evt.stopPropagation(); });
        document.addEventListener('click', () => { fermer(); });
        document.addEventListener('keydown', (evt) => {
            if (evt.key === 'Escape' && estOuvert()) {
                fermer();
            }
        });
    }

    /**
     * Mesure la boîte réellement affichée de la modale du joker (issue #140).
     * Renvoie un objet sérialisable {viewport, documentElement, devicePixelRatio,
     * contenu, grille, annuler} destiné à être remonté à Python pour journalisation
     * (diagnostic du débordement réel en WebKitGTK, sur le modèle du z-order #93).
     * Toutes les valeurs sont arrondies à l'entier pour un journal lisible.
     */
    function mesurerModaleJoker(refs) {
        const boite = (el) => {
            if (!el) {
                return null;
            }
            const r = el.getBoundingClientRect();
            return {
                haut: Math.round(r.top),
                bas: Math.round(r.bottom),
                gauche: Math.round(r.left),
                droite: Math.round(r.right),
                largeur: Math.round(r.width),
                hauteur: Math.round(r.height),
            };
        };
        const contenu = refs.modale.querySelector('.modale-contenu');
        return {
            viewport: { largeur: window.innerWidth, hauteur: window.innerHeight },
            documentElement: {
                largeur: document.documentElement.clientWidth,
                hauteur: document.documentElement.clientHeight,
            },
            devicePixelRatio: window.devicePixelRatio,
            contenu: boite(contenu),
            grille: refs.grille
                ? Object.assign(boite(refs.grille), {
                    scrollHeight: refs.grille.scrollHeight,
                    clientHeight: refs.grille.clientHeight,
                })
                : null,
            annuler: boite(refs.annuler),
        };
    }

    /**
     * Ouvre le sélecteur de lettre d'un joker et renvoie la lettre choisie
     * (``A``–``Z``) ou ``null`` si annulé. ``refs`` = {modale, grille, annuler,
     * bouton?, popover?, auOuvrir?}. ``modale`` est l'élément à afficher/masquer
     * (basculé via ``hidden``) : une vraie modale, ou — depuis l'issue #168 — le
     * popover « Lettre du joker » ancré sur le plateau.
     *
     * Deux options facultatives pour le mode popover (issue #168), sans effet si
     * absentes (compatibilité) :
     *   - ``bouton`` : le bouton d'ancrage, dont ``aria-expanded`` est tenu à jour ;
     *   - ``popover`` (booléen) : câble la fermeture façon « Derniers coups » — un
     *     clic HORS du popover (et de son bouton) ou la touche Échap annule le choix.
     *
     * ``auOuvrir`` (facultatif, issue #140) est appelé une fois le sélecteur rendu,
     * avec les dimensions réelles mesurées (voir :func:`mesurerModaleJoker`), pour
     * remonter un diagnostic à Python. La mesure est différée de deux
     * ``requestAnimationFrame`` pour laisser le vrai moteur de rendu poser la mise
     * en page avant lecture.
     */
    function choisirLettreJoker(refs) {
        return new Promise((resolve) => {
            refs.grille.innerHTML = '';
            // Garde de fermeture unique : empêche un double-résolu et, surtout, que
            // le rAF d'armement des écouteurs (mode popover) ne les pose APRÈS une
            // fermeture déjà survenue dans la même frame (fuite d'écouteurs).
            let ferme = false;
            let surClicExterieur = null;
            let surTouche = null;
            const fermer = (valeur) => {
                if (ferme) {
                    return;
                }
                ferme = true;
                refs.modale.hidden = true;
                refs.annuler.removeEventListener('click', surAnnuler);
                if (surClicExterieur) {
                    document.removeEventListener('click', surClicExterieur, true);
                }
                if (surTouche) {
                    document.removeEventListener('keydown', surTouche);
                }
                if (refs.bouton) {
                    refs.bouton.setAttribute('aria-expanded', 'false');
                }
                resolve(valeur);
            };
            const surAnnuler = () => fermer(null);
            for (let i = 0; i < 26; i++) {
                const lettre = String.fromCharCode(65 + i);
                const b = document.createElement('button');
                b.className = 'joker-lettre';
                b.textContent = lettre;
                b.addEventListener('click', () => fermer(lettre));
                refs.grille.appendChild(b);
            }
            refs.annuler.addEventListener('click', surAnnuler);
            refs.modale.hidden = false;
            if (refs.bouton) {
                refs.bouton.setAttribute('aria-expanded', 'true');
            }
            // Mode popover (issue #168) : fermeture façon « Derniers coups ». Les
            // écouteurs sont différés d'une frame pour ne pas capter le clic/appui
            // qui vient d'ouvrir le sélecteur ; le clic est écouté en phase de
            // capture pour l'attraper même si une cible arrête sa propagation.
            if (refs.popover) {
                surClicExterieur = (evt) => {
                    if (!refs.modale.contains(evt.target)
                        && !(refs.bouton && refs.bouton.contains(evt.target))) {
                        fermer(null);
                    }
                };
                surTouche = (evt) => {
                    if (evt.key === 'Escape') {
                        fermer(null);
                    }
                };
                requestAnimationFrame(() => {
                    if (ferme) {
                        return;
                    }
                    document.addEventListener('click', surClicExterieur, true);
                    document.addEventListener('keydown', surTouche);
                });
            }
            if (typeof refs.auOuvrir === 'function') {
                requestAnimationFrame(() => requestAnimationFrame(() => {
                    try {
                        refs.auOuvrir(mesurerModaleJoker(refs));
                    } catch (e) {
                        // Diagnostic best-effort : une mesure ratée ne bloque pas
                        // l'ouverture de la modale ni le choix de la lettre.
                    }
                }));
            }
        });
    }

    /**
     * Construit un contrôleur de la modale de détail du score (issue #35), commun
     * aux deux fenêtres (chacune héberge sa propre copie de ``#score-modale``,
     * issue #90). ``refs`` = {modale, titre, detail, total, fermer, auFermer?}.
     * ``auFermer`` (facultatif, issue #128) est appelé à chaque fermeture, quelle
     * qu'en soit l'origine (bouton, clic sur le fond) : l'écran de jeu s'en sert
     * pour retirer la surbrillance du coup consulté et rendre la main au dernier
     * coup réel. Renvoie un objet {afficher, afficherSansDetail, fermer}.
     */
    function creerModaleScore(refs) {
        function fermer() {
            refs.modale.hidden = true;
            if (typeof refs.auFermer === 'function') {
                refs.auFermer();
            }
        }
        function afficher(detail, titre) {
            if (!detail || !Array.isArray(detail.mots)) {
                return;
            }
            refs.titre.textContent = titre || 'Détail du score';
            refs.detail.innerHTML = '';
            detail.mots.forEach((mot) => {
                const ligne = document.createElement('div');
                ligne.className = 'score-mot';
                const bonus = (mot.cases_bonus || [])
                    .map((c) => LABEL_BONUS[c.type])
                    .filter(Boolean);
                const bonusHtml = bonus.length
                    ? `<span class="score-bonus">${escapeHtml(bonus.join(', '))}</span>`
                    : '';
                ligne.innerHTML = `
                    <span class="score-mot-texte">${escapeHtml(mot.texte)}</span>
                    <span class="score-mot-points">${mot.score} pt${mot.score > 1 ? 's' : ''}</span>
                    ${bonusHtml}
                `;
                refs.detail.appendChild(ligne);
            });
            if (detail.bonus_scrabble) {
                const bonusLigne = document.createElement('div');
                bonusLigne.className = 'score-mot score-scrabble';
                bonusLigne.innerHTML = `
                    <span class="score-mot-texte">🎉 Scrabble (7 lettres posées)</span>
                    <span class="score-mot-points">+${detail.bonus_scrabble} pts</span>
                `;
                refs.detail.appendChild(bonusLigne);
            }
            refs.total.textContent =
                `Total : ${detail.total} point${detail.total > 1 ? 's' : ''}`;
            refs.modale.hidden = false;
        }
        function afficherSansDetail(nomJoueur, action) {
            refs.titre.textContent = `Action de ${nomJoueur}`;
            refs.detail.innerHTML = '';
            const ligne = document.createElement('div');
            ligne.className = 'score-mot';
            const texte = action === 'echange'
                ? 'Échange de lettres, tour passé. 0 point.'
                : 'Tour passé, aucune lettre jouée. 0 point.';
            ligne.innerHTML = `<span class="score-mot-texte">${escapeHtml(texte)}</span>`;
            refs.detail.appendChild(ligne);
            refs.total.textContent = 'Aucun mot formé — rien à détailler.';
            refs.modale.hidden = false;
        }
        // Fermeture par le bouton dédié ou par un clic sur le fond assombri.
        if (refs.fermer) {
            refs.fermer.addEventListener('click', fermer);
        }
        refs.modale.addEventListener('click', (evt) => {
            if (evt.target === refs.modale) {
                fermer();
            }
        });
        return { afficher, afficherSansDetail, fermer };
    }

    window.Commun = {
        pretPywebview,
        escapeHtml,
        icone,
        creerTuile,
        LABEL_TOOLTIP,
        LABEL_COMPLET,
        LABEL_ABREGE,
        LABEL_BONUS,
        THEMES,
        configurerPopover,
        fermerTousPopovers,
        choisirLettreJoker,
        creerModaleScore,
    };
})();
