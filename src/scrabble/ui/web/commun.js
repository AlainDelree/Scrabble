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

    /**
     * Câble un bouton déclencheur + son popover : ouverture/fermeture au clic sur
     * le bouton, fermeture au clic hors du popover ou à la touche Échap. Met à
     * jour aria-expanded. ``onOuvrir`` (optionnel) est appelé à chaque ouverture.
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
        const ouvrir = () => {
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
     * Ouvre la modale de choix de lettre d'un joker et renvoie la lettre choisie
     * (``A``–``Z``) ou ``null`` si annulé. ``refs`` = {modale, grille, annuler}.
     */
    function choisirLettreJoker(refs) {
        return new Promise((resolve) => {
            refs.grille.innerHTML = '';
            const fermer = (valeur) => {
                refs.modale.hidden = true;
                refs.annuler.removeEventListener('click', surAnnuler);
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
        });
    }

    /**
     * Construit un contrôleur de la modale de détail du score (issue #35), commun
     * aux deux fenêtres (chacune héberge sa propre copie de ``#score-modale``,
     * issue #90). ``refs`` = {modale, titre, detail, total, fermer}. Renvoie un
     * objet {afficher, afficherSansDetail, fermer}.
     */
    function creerModaleScore(refs) {
        function fermer() {
            refs.modale.hidden = true;
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
        choisirLettreJoker,
        creerModaleScore,
    };
})();
