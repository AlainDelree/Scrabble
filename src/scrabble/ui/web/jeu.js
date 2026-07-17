/**
 * jeu.js — fenêtre PLATEAU (issue #90).
 *
 * Depuis la séparation en deux fenêtres pywebview (issue #90), cette vue ne porte
 * plus QUE la partie « publique » de l'écran de jeu : le plateau 15×15, les
 * panneaux d'information des joueurs, la barre du sac/historique, le bouton
 * « Faire jouer l'ordinateur » (déplacé ici, car un tour IA relève du plateau),
 * la vérification dictionnaire (saisie libre, sans lien avec le chevalet), le
 * « Retour au menu » et une copie de la modale de détail du score (ouverte depuis
 * l'historique). Le chevalet, le brouillon, la mécanique de pose (sélection +
 * boutons Jouer/Vérifier/Annuler) et la modale de choix du joker vivent dans la
 * fenêtre chevalet flottante (chevalet.html / chevalet.js).
 *
 * Source de vérité de l'état de pose : Python (``ApiJeu``, issue #90). Cette
 * fenêtre est une simple vue :
 *   - elle REÇOIT l'état public via ``window.appliquerEtatPlateau`` (poussé par
 *     Python après toute mutation) — jamais aucune lettre du chevalet ;
 *   - au clic sur une case, elle DEMANDE la mutation à Python
 *     (``poser_lettre_en_attente`` / ``retirer_lettre_en_attente``), qui rediffuse
 *     ensuite l'état aux deux fenêtres.
 *
 * Confidentialité (issues #33/#35) : le payload reçu ici est strictement public
 * (aucune identité de lettre de chevalet) ; seules les lettres déjà posées sur le
 * plateau (``en_attente``, déjà destinées à être visibles) y figurent.
 */

document.addEventListener('DOMContentLoaded', async () => {
    await window.Commun.pretPywebview();

    const api = window.pywebview.api;
    const C = window.Commun;

    // --- Éléments du DOM ---
    const plateauEl = document.getElementById('plateau');
    // Slots des panneaux joueurs, un par côté du plateau (issue #33). Le JS y
    // insère le panneau du joueur dont la position (calculée côté Python) vaut
    // le côté correspondant.
    const slots = {
        haut: document.getElementById('slot-haut'),
        gauche: document.getElementById('slot-gauche'),
        droite: document.getElementById('slot-droite'),
        bas: document.getElementById('slot-bas'),
    };
    const sacNombre = document.getElementById('sac-nombre');
    const bandeauFin = document.getElementById('bandeau-fin');
    const messagePlateau = document.getElementById('message-plateau');
    const historiqueListe = document.getElementById('historique-liste');
    const historiqueCompte = document.getElementById('historique-compte');
    const btnRafraichir = document.getElementById('btn-rafraichir');
    // Retour au menu (issue #74) : bouton discret de la barre du haut + modale
    // d'avertissement affichée uniquement s'il reste un coup en attente.
    const btnRetourMenu = document.getElementById('btn-retour-menu');
    const retourModale = document.getElementById('retour-modale');
    const retourAnnuler = document.getElementById('retour-annuler');
    const retourConfirmer = document.getElementById('retour-confirmer');

    // Mode « attente d'un tour d'ordinateur » (issue #35) déplacé côté plateau
    // (issue #90) : bloc + bouton « Faire jouer l'ordinateur ».
    const zoneAttenteIA = document.getElementById('zone-attente-ia');
    const attenteMessageIA = document.getElementById('attente-ia-message');
    const btnJouerIA = document.getElementById('btn-jouer-ia');

    // Vérification dictionnaire par saisie libre (issue #50/#86) : champ + bouton
    // logés derrière un popover discret dans la gouttière gauche.
    const champVerif = document.getElementById('champ-verif');
    const btnVerifier = document.getElementById('btn-verifier');
    const messageBrouillon = document.getElementById('message-brouillon');
    const btnOuvrirVerif = document.getElementById('btn-ouvrir-verif');
    const verifPopover = document.getElementById('verif-dico-popover');

    // Modale de détail du score (issue #35), ici ouverte depuis l'historique.
    // Contrôleur factorisé dans commun.js (issue #90).
    const modaleScore = C.creerModaleScore({
        modale: document.getElementById('score-modale'),
        titre: document.getElementById('score-titre'),
        detail: document.getElementById('score-detail'),
        total: document.getElementById('score-total'),
        fermer: document.getElementById('score-fermer'),
    });

    // Thèmes reconnus (alignés avec scrabble.config.THEMES_PLATEAU et le CSS).
    const THEMES = C.THEMES;

    // --- État courant côté vue ---
    // Dernier payload public reçu de Python (état de la partie + pose en cours).
    let etat = null;
    // Placements en attente déjà posés sur le plateau (copie locale du payload,
    // pour le rendu et pour savoir si « Retour au menu » doit avertir).
    let enAttente = [];
    // Thème visuel actif et jeu de libellés affichés dans les cases.
    let themePlateau = 'classique';
    let labelVisible = C.LABEL_COMPLET;
    // Détection d'un coup nouvellement joué pour l'animer (issue #62). On mémorise
    // l'index du coup en tête d'historique ; à la première application on ne fait
    // que l'enregistrer (aucune animation au chargement).
    let dernierCoupIndex = null;
    let premiereApplication = true;

    // ------------------------------------------------------------------ //
    // Rendu du plateau
    // ------------------------------------------------------------------ //

    /** Placement en attente sur (ligne, colonne), ou ``null``. */
    function attenteEn(ligne, colonne) {
        return enAttente.find((p) => p.ligne === ligne && p.colonne === colonne) || null;
    }

    /**
     * Rend le plateau à partir de l'état (grille de cases typées). Chaque case
     * porte ses coordonnées (data-ligne / data-colonne) pour la pose au clic. Les
     * lettres en attente (non validées) sont dessinées par-dessus les cases vides,
     * avec un style distinct.
     */
    function rendrePlateau() {
        const plateau = etat.plateau;
        plateauEl.innerHTML = '';
        const fragment = document.createDocumentFragment();
        plateau.forEach((ligne, l) => {
            ligne.forEach((cell, c) => {
                const caseEl = document.createElement('div');
                // Le type vient de Python en MAJUSCULES (``TypeCase.value``). Les
                // sélecteurs CSS de couleur (``.case-mt`` …) sont en minuscules et
                // les classes HTML sont sensibles à la casse : on normalise donc.
                const typeClasse = String(cell.type).toLowerCase();
                caseEl.className = `case case-${typeClasse}`;
                caseEl.title = C.LABEL_TOOLTIP[cell.type] || '';
                caseEl.dataset.ligne = l;
                caseEl.dataset.colonne = c;
                const attente = attenteEn(l, c);
                if (cell.lettre) {
                    // Tuile déjà posée lors d'un tour précédent (immuable).
                    caseEl.appendChild(C.creerTuile(cell, false));
                    caseEl.classList.add('occupee');
                } else if (attente) {
                    // Lettre en attente de validation (retirable au clic).
                    caseEl.appendChild(C.creerTuile(attente, true));
                } else if (cell.type === 'centre') {
                    caseEl.textContent = '★';
                } else {
                    caseEl.textContent = labelVisible[cell.type] || '';
                }
                caseEl.setAttribute('aria-label', `Ligne ${l + 1}, colonne ${c + 1}`);
                fragment.appendChild(caseEl);
            });
        });
        plateauEl.appendChild(fragment);
    }

    // ------------------------------------------------------------------ //
    // Panneaux joueurs
    // ------------------------------------------------------------------ //

    /**
     * Construit le panneau d'information **public** d'un joueur sur une seule
     * ligne compacte (issue #47), identique pour les quatre côtés et les deux
     * natures. Aucune identité de lettre n'y figure (confidentialité).
     */
    function creerPanneauJoueur(joueur) {
        const item = document.createElement('div');
        const nature = joueur.humain ? 'humain' : 'ordinateur';
        item.className = `panneau-joueur ${nature}${joueur.courant ? ' courant' : ''}`;
        item.dataset.cote = joueur.position || '';

        const badgeTour = joueur.courant
            ? `<span class="panneau-tour">● ${joueur.humain ? 'à vous' : 'son tour'}</span>`
            : '';
        const avatarHtml = joueur.avatar
            ? `<img class="panneau-avatar" src="avatars/${encodeURIComponent(joueur.avatar)}.svg"
                    alt="" width="26" height="26">`
            : `<span class="panneau-icone">${C.icone(joueur.humain)}</span>`;
        const badgeOrdinateur = joueur.humain
            ? ''
            : '<span class="panneau-ordi" title="Joueur ordinateur" aria-label="Joueur ordinateur">🖥️</span>';
        const niveauLabel = joueur.niveau
            ? ({
                  DEBUTANT: 'Débutant',
                  FACILE: 'Facile',
                  INTERMEDIAIRE: 'Intermédiaire',
                  EXPERT: 'Expert',
              }[joueur.niveau] || joueur.niveau)
            : '';
        const badgeNiveau = niveauLabel
            ? `<span class="panneau-niveau">${C.escapeHtml(niveauLabel)}</span>`
            : '';
        item.innerHTML = `
            ${avatarHtml}
            <span class="panneau-identite">
                <span class="panneau-nom">${C.escapeHtml(joueur.nom)}</span>
                ${badgeNiveau}
            </span>
            <span class="panneau-score">${joueur.score} pts</span>
            <span class="panneau-lettres">🎴 ${joueur.nb_lettres}</span>
            ${badgeOrdinateur}
            ${badgeTour}
        `;
        return item;
    }

    /** Dispose les panneaux joueurs dans le slot du côté assigné (issue #33). */
    function rendrePanneaux(joueurs) {
        Object.values(slots).forEach((slot) => { slot.innerHTML = ''; });
        joueurs.forEach((joueur) => {
            const slot = slots[joueur.position];
            if (slot) {
                slot.appendChild(creerPanneauJoueur(joueur));
            }
        });
    }

    /** Rend le bandeau de fin de partie (issue #45). */
    function rendreFinPartie(terminee, gagnants) {
        if (!terminee) {
            bandeauFin.hidden = true;
            bandeauFin.textContent = '';
            return;
        }
        bandeauFin.hidden = false;
        bandeauFin.textContent = gagnants && gagnants.length
            ? `🏁 Partie terminée — ${gagnants.join(', ')}`
            : '🏁 Partie terminée';
    }

    // ------------------------------------------------------------------ //
    // Historique glissant (issue #37)
    // ------------------------------------------------------------------ //

    const LABEL_ACTION = {
        'coup': 'a posé',
        'passe': 'a passé',
        'echange': 'a échangé',
    };

    function resumeAction(entree) {
        const verbe = LABEL_ACTION[entree.action] || entree.action;
        if (entree.action === 'coup') {
            const mot = entree.mot ? ` « ${entree.mot} »` : '';
            return `${verbe}${mot}`;
        }
        return verbe;
    }

    function rendreHistorique(historique) {
        historiqueListe.innerHTML = '';
        const nb = Array.isArray(historique) ? historique.length : 0;
        if (historiqueCompte) {
            historiqueCompte.textContent = nb ? `(${nb})` : '';
        }
        if (!nb) {
            const vide = document.createElement('li');
            vide.className = 'historique-vide';
            vide.textContent = 'Aucune action jouée pour le moment.';
            historiqueListe.appendChild(vide);
            return;
        }
        historique.forEach((entree) => {
            const item = document.createElement('li');
            const nature = entree.humain ? 'humain' : 'ordinateur';
            const cliquable = Boolean(entree.detail);
            item.className = `historique-ligne ${nature}` + (cliquable ? ' cliquable' : '');
            item.dataset.index = entree.index;
            if (cliquable) {
                item.setAttribute('role', 'button');
                item.tabIndex = 0;
                item.title = 'Voir le détail de ce coup';
            } else {
                item.title = 'Aucun détail pour cette action';
            }
            item.innerHTML = `
                <span class="historique-joueur">${C.icone(entree.humain)} ${C.escapeHtml(entree.nom_joueur)}</span>
                <span class="historique-action">${C.escapeHtml(resumeAction(entree))}</span>
                <span class="historique-score">+${entree.score_action} pt${entree.score_action > 1 ? 's' : ''}</span>
            `;
            historiqueListe.appendChild(item);
        });
    }

    /** Ouvre le détail d'une action de l'historique au clic (issue #37). */
    function ouvrirDetailHistorique(entree) {
        if (!entree) {
            return;
        }
        if (entree.detail) {
            const titre = `Détail du coup de ${entree.nom_joueur}`
                + (entree.mot ? ` — « ${entree.mot} »` : '');
            modaleScore.afficher(entree.detail, titre);
        } else {
            modaleScore.afficherSansDetail(entree.nom_joueur, entree.action);
        }
    }

    // ------------------------------------------------------------------ //
    // Mode « attente d'un tour d'ordinateur » (issue #35)
    // ------------------------------------------------------------------ //

    /** Bascule interactif / attente (tour d'un ordinateur), issue #35/#90. */
    function majModeTour() {
        const courant = etat.joueurs[etat.index_courant];
        const attenteIA = Boolean(etat && !etat.terminee && !etat.tour_humain);
        zoneAttenteIA.hidden = !attenteIA;
        if (attenteIA && courant) {
            attenteMessageIA.textContent = `En attente du coup de ${courant.nom}…`;
            btnJouerIA.disabled = false;
        }
    }

    /** Message éphémère de pose (issue #90), affiché en surimpression. */
    let messageTimer = null;
    function afficherMessagePlateau(texte, type) {
        if (messageTimer) {
            clearTimeout(messageTimer);
            messageTimer = null;
        }
        if (!texte) {
            messagePlateau.hidden = true;
            messagePlateau.textContent = '';
            return;
        }
        messagePlateau.textContent = texte;
        messagePlateau.className = 'message-plateau ' + (type || 'info');
        messagePlateau.hidden = false;
        messageTimer = setTimeout(() => {
            messagePlateau.hidden = true;
            messagePlateau.textContent = '';
        }, 4000);
    }

    // ------------------------------------------------------------------ //
    // Application d'un état poussé par Python (issue #90)
    // ------------------------------------------------------------------ //

    /**
     * Applique un état PUBLIC (aucune lettre de chevalet). Poussé par Python via
     * ``window.appliquerEtatPlateau`` après toute mutation, ou obtenu au premier
     * chargement via ``obtenir_etat_plateau``.
     */
    function appliquerEtatPlateau(payload) {
        etat = payload || {};
        enAttente = Array.isArray(etat.en_attente) ? etat.en_attente : [];
        rendrePlateau();
        rendrePanneaux(etat.joueurs || []);
        rendreFinPartie(etat.terminee, etat.gagnants);
        rendreHistorique(etat.historique);
        sacNombre.textContent = etat.jetons_sac != null ? etat.jetons_sac : '—';
        majModeTour();
        animerDernierCoupSiNouveau();
    }
    window.appliquerEtatPlateau = appliquerEtatPlateau;

    /**
     * Anime le dernier coup s'il vient d'apparaître en tête d'historique
     * (issue #62). Détecte l'apparition d'un NOUVEAU coup (index de tête qui
     * change) plutôt que de ré-animer à chaque diffusion (une simple pose en
     * attente rediffuse l'état sans changer l'historique). Au premier chargement
     * on n'anime rien : on ne fait qu'enregistrer l'index courant.
     */
    function animerDernierCoupSiNouveau() {
        const historique = etat.historique;
        const tete = Array.isArray(historique) && historique.length ? historique[0] : null;
        const index = tete ? tete.index : null;
        if (premiereApplication) {
            premiereApplication = false;
            dernierCoupIndex = index;
            return;
        }
        if (index == null || index === dernierCoupIndex) {
            return;
        }
        dernierCoupIndex = index;
        if (tete.positions && tete.positions.length) {
            animerPose(tete.positions).then(() => {
                if (tete.detail && tete.detail.bonus_scrabble) {
                    celebrerScrabble();
                }
            });
        }
    }

    // ------------------------------------------------------------------ //
    // Pose « clic-clic » côté plateau (issue #90)
    // ------------------------------------------------------------------ //

    /**
     * Clic sur une case du plateau :
     *  - case portant une lettre en attente : on demande à Python de la retirer ;
     *  - case déjà occupée par une tuile validée : refus (message clair) ;
     *  - case vide : on demande la pose ; Python résout la lettre sélectionnée
     *    (dans la fenêtre chevalet) et, s'il s'agit d'un joker, ouvre la modale de
     *    choix côté chevalet. La confidentialité est respectée : cette fenêtre ne
     *    connaît jamais la lettre du chevalet, elle ne transmet que la case visée.
     */
    plateauEl.addEventListener('click', async (evt) => {
        const caseEl = evt.target.closest('.case');
        if (!caseEl) {
            return;
        }
        const ligne = Number(caseEl.dataset.ligne);
        const colonne = Number(caseEl.dataset.colonne);

        // Retrait d'une lettre en attente (recliquer sa case).
        if (attenteEn(ligne, colonne)) {
            afficherMessagePlateau('');
            try {
                await api.retirer_lettre_en_attente(ligne, colonne);
            } catch (err) {
                afficherMessagePlateau('Erreur lors du retrait de la lettre.', 'erreur');
            }
            return;
        }

        // Case déjà occupée par une tuile d'un tour précédent : pose interdite.
        if (etat.plateau[ligne][colonne].lettre) {
            afficherMessagePlateau(
                'Cette case porte déjà une tuile : impossible d\'y poser une lettre.',
                'erreur');
            return;
        }

        // Case vide : demande de pose. Python lit la sélection courante.
        let res;
        try {
            res = await api.poser_lettre_en_attente(ligne, colonne);
        } catch (err) {
            afficherMessagePlateau('Erreur inattendue lors de la pose.', 'erreur');
            return;
        }
        if (res && res.joker_requis) {
            afficherMessagePlateau(
                'Choisissez la lettre du joker dans la fenêtre « Chevalet ».', 'info');
        } else if (res && res.succes === false) {
            afficherMessagePlateau(res.erreur || 'Pose impossible.', 'info');
        } else {
            afficherMessagePlateau('');
        }
    });

    // ------------------------------------------------------------------ //
    // Resynchronisation manuelle (issue #41/#78)
    // ------------------------------------------------------------------ //

    async function rafraichir() {
        try {
            const payload = await api.obtenir_etat_plateau();
            appliquerEtatPlateau(payload);
        } catch (err) {
            afficherMessagePlateau('Resynchronisation impossible.', 'erreur');
        }
    }
    btnRafraichir.addEventListener('click', rafraichir);

    // ------------------------------------------------------------------ //
    // Retour au menu (issue #74/#90)
    // ------------------------------------------------------------------ //

    async function retournerAuMenu() {
        btnRetourMenu.disabled = true;
        let res;
        try {
            res = await api.retour_menu();
        } catch (err) {
            btnRetourMenu.disabled = false;
            afficherMessagePlateau('Retour au menu impossible : ' + err, 'erreur');
            return;
        }
        if (res && res.succes === false) {
            btnRetourMenu.disabled = false;
            afficherMessagePlateau(
                'Retour au menu impossible : ' + (res.erreur || 'erreur inconnue'), 'erreur');
        }
        // Succès : les DEUX fenêtres se ferment, l'accueil se rouvre (Python).
    }

    // Si un coup est en attente (lettres posées non validées), on demande
    // confirmation via la modale ; sinon retour direct.
    btnRetourMenu.addEventListener('click', () => {
        if (enAttente.length > 0) {
            retourModale.hidden = false;
        } else {
            retournerAuMenu();
        }
    });
    retourAnnuler.addEventListener('click', () => { retourModale.hidden = true; });
    retourModale.addEventListener('click', (evt) => {
        if (evt.target === retourModale) {
            retourModale.hidden = true;
        }
    });
    retourConfirmer.addEventListener('click', () => {
        retourModale.hidden = true;
        retournerAuMenu();
    });

    // ------------------------------------------------------------------ //
    // Tour d'un ordinateur (issue #35/#55) — bouton côté plateau (issue #90)
    // ------------------------------------------------------------------ //

    // « ▶ Faire jouer l'ordinateur » : joue UN SEUL tour d'ordinateur. Python
    // rediffuse ensuite l'état aux deux fenêtres ; l'animation de la pose est
    // déclenchée par ``appliquerEtatPlateau`` (nouveau coup en tête d'historique).
    btnJouerIA.addEventListener('click', async () => {
        btnJouerIA.disabled = true;
        let res;
        try {
            res = await api.faire_jouer_ia();
        } catch (err) {
            btnJouerIA.disabled = false;
            return;
        }
        if (!(res && res.succes)) {
            btnJouerIA.disabled = false;
        }
        // Succès : le bouton reste piloté par majModeTour au prochain état poussé
        // (réactivé si le joueur suivant est encore un ordinateur).
    });

    // ------------------------------------------------------------------ //
    // Vérification dictionnaire (lecture seule, issue #50/#86)
    // ------------------------------------------------------------------ //

    function afficherMessageBrouillon(texte, type) {
        messageBrouillon.textContent = texte || '';
        messageBrouillon.className = 'message-brouillon' + (texte ? ' ' + (type || 'info') : '');
    }

    async function verifierMotDictionnaire() {
        const mot = champVerif.value;
        if (!mot.trim()) {
            afficherMessageBrouillon('Tapez un mot dans le champ pour le vérifier.', 'info');
            return;
        }
        let res;
        try {
            res = await api.verifier_mot(mot);
        } catch (err) {
            afficherMessageBrouillon('Erreur inattendue lors de la vérification.', 'invalide');
            return;
        }
        if (res && res.succes) {
            if (res.valide) {
                afficherMessageBrouillon(`✓ « ${res.mot} » est dans le dictionnaire.`, 'valide');
            } else {
                afficherMessageBrouillon(`✗ « ${res.mot} » n'est pas dans le dictionnaire.`, 'invalide');
            }
        } else {
            afficherMessageBrouillon((res && res.erreur) || 'Vérification impossible.', 'info');
        }
    }

    btnVerifier.addEventListener('click', verifierMotDictionnaire);
    champVerif.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && champVerif.value.trim()) {
            e.preventDefault();
            verifierMotDictionnaire();
        }
    });
    // Popover replié (issue #86) : au clic, focus sur le champ.
    C.configurerPopover(btnOuvrirVerif, verifPopover, () => { champVerif.focus(); });

    // ------------------------------------------------------------------ //
    // Encart d'historique glissant : ouverture/fermeture + clic sur une ligne
    // ------------------------------------------------------------------ //

    // Fermeture/ouverture fiable du menu « Derniers coups » (issues #56/#60) :
    // on tient notre propre intention (``historiqueOuvert``) et on force ``open``
    // dessus, une fois tout de suite et une fois en requestAnimationFrame, pour
    // que l'éventuelle bascule native de WebKitGTK ne gagne pas la course.
    const historiqueMenu = document.getElementById('historique-menu');
    const historiqueResume = historiqueMenu ? historiqueMenu.querySelector('summary') : null;
    if (historiqueMenu && historiqueResume) {
        let historiqueOuvert = historiqueMenu.open;
        historiqueResume.addEventListener('click', (evt) => {
            evt.preventDefault();
            historiqueOuvert = !historiqueOuvert;
            const cible = historiqueOuvert;
            historiqueMenu.open = cible;
            requestAnimationFrame(() => { historiqueMenu.open = cible; });
        });
    }

    function entreeHistoriqueDe(li) {
        if (!li || !etat || !Array.isArray(etat.historique)) {
            return null;
        }
        const index = Number(li.dataset.index);
        return etat.historique.find((e) => e.index === index) || null;
    }

    historiqueListe.addEventListener('click', (evt) => {
        const li = evt.target.closest('.historique-ligne');
        ouvrirDetailHistorique(entreeHistoriqueDe(li));
    });
    historiqueListe.addEventListener('keydown', (evt) => {
        if (evt.key !== 'Enter' && evt.key !== ' ') {
            return;
        }
        const li = evt.target.closest('.historique-ligne');
        if (li) {
            evt.preventDefault();
            ouvrirDetailHistorique(entreeHistoriqueDe(li));
        }
    });

    // ------------------------------------------------------------------ //
    // Son de pose des tuiles (issue #62) — « tac » synthétisé (Web Audio API)
    // ------------------------------------------------------------------ //
    let audioCtx = null;

    function contexteAudio() {
        if (audioCtx === null) {
            const AC = window.AudioContext || window.webkitAudioContext;
            if (!AC) {
                return null;
            }
            try {
                audioCtx = new AC();
            } catch (err) {
                return null;
            }
        }
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
        return audioCtx;
    }

    function jouerTac() {
        const ctx = contexteAudio();
        if (!ctx) {
            return;
        }
        const debut = ctx.currentTime;
        const duree = 0.07;
        const taille = Math.max(1, Math.floor(ctx.sampleRate * duree));
        const buffer = ctx.createBuffer(1, taille, ctx.sampleRate);
        const echantillons = buffer.getChannelData(0);
        for (let i = 0; i < taille; i++) {
            echantillons[i] = (Math.random() * 2 - 1) * (1 - i / taille);
        }
        const source = ctx.createBufferSource();
        source.buffer = buffer;
        const filtre = ctx.createBiquadFilter();
        filtre.type = 'bandpass';
        filtre.frequency.value = 1800;
        filtre.Q.value = 0.8;
        const gain = ctx.createGain();
        gain.gain.setValueAtTime(0.0001, debut);
        gain.gain.exponentialRampToValueAtTime(0.45, debut + 0.005);
        gain.gain.exponentialRampToValueAtTime(0.0001, debut + duree);
        source.connect(filtre);
        filtre.connect(gain);
        gain.connect(ctx.destination);
        source.start(debut);
        source.stop(debut + duree);
    }

    /**
     * Anime la pose d'un coup (humain ou ordinateur, issue #62) : révèle les
     * cases nouvellement posées une par une (« tac » à chaque apparition) sur
     * ~2,5 s. Le plateau vient d'être rendu : les tuiles sont déjà dans leur état
     * final, on les masque puis on les dévoile successivement.
     */
    function animerPose(positions) {
        return new Promise((resolve) => {
            if (!Array.isArray(positions) || positions.length === 0) {
                resolve();
                return;
            }
            const cases = positions
                .map(({ ligne, colonne }) => plateauEl.querySelector(
                    `.case[data-ligne="${ligne}"][data-colonne="${colonne}"]`
                ))
                .filter(Boolean);
            if (cases.length === 0) {
                resolve();
                return;
            }
            cases.forEach((caseEl) => caseEl.classList.add('case-pose-cachee'));
            const delai = Math.min(500, Math.max(120, Math.round(2500 / cases.length)));
            cases.forEach((caseEl, i) => {
                setTimeout(() => {
                    caseEl.classList.remove('case-pose-cachee');
                    caseEl.classList.add('case-pose-revele');
                    caseEl.addEventListener(
                        'animationend',
                        () => caseEl.classList.remove('case-pose-revele'),
                        { once: true }
                    );
                    jouerTac();
                    if (i === cases.length - 1) {
                        setTimeout(resolve, delai);
                    }
                }, i * delai);
            });
        });
    }

    /**
     * Célébration festive d'un « Scrabble » (issue #64/#73) : bref feu d'artifice
     * dans le calque plein écran ``#scrabble-fete`` (toujours transparent aux
     * clics). En mouvement réduit, seul le toast statique est affiché.
     */
    function celebrerScrabble() {
        const calque = document.getElementById('scrabble-fete');
        if (!calque) {
            return;
        }
        calque.innerHTML = '';
        const reduit = window.matchMedia
            && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        const toast = document.createElement('div');
        toast.className = 'scrabble-toast';
        toast.textContent = '🎉 Scrabble !! Félicitations 🥳';
        calque.appendChild(toast);

        if (reduit) {
            setTimeout(() => { calque.innerHTML = ''; }, 2600);
            return;
        }

        const couleurs = ['#2e7d32', '#1565c0', '#6a1b9a', '#ffd54f', '#ef6d86', '#d21f24'];
        const nb = 32;
        for (let i = 0; i < nb; i += 1) {
            const p = document.createElement('div');
            p.className = 'particule';
            const angle = Math.random() * Math.PI * 2;
            const distance = 120 + Math.random() * 160;
            const dx = Math.cos(angle) * distance;
            const dy = Math.sin(angle) * distance + 40 + Math.random() * 80;
            p.style.setProperty('--dx', `${Math.round(dx)}px`);
            p.style.setProperty('--dy', `${Math.round(dy)}px`);
            p.style.setProperty('--rot', `${Math.round((Math.random() - 0.5) * 720)}deg`);
            p.style.setProperty('--delai', `${(Math.random() * 0.25).toFixed(2)}s`);
            p.style.setProperty('--col', couleurs[i % couleurs.length]);
            calque.appendChild(p);
        }
        setTimeout(() => { calque.innerHTML = ''; }, 2600);
    }

    // ------------------------------------------------------------------ //
    // Thème visuel du plateau
    // ------------------------------------------------------------------ //

    async function appliquerTheme() {
        let theme = 'classique';
        try {
            theme = await api.obtenir_theme_plateau();
        } catch (err) {
            theme = 'classique';
        }
        if (!THEMES.includes(theme)) {
            theme = 'classique';
        }
        themePlateau = theme;
        labelVisible = (theme === 'abrege') ? C.LABEL_ABREGE : C.LABEL_COMPLET;
        THEMES.forEach((t) => plateauEl.classList.remove(`theme-${t}`));
        plateauEl.classList.add(`theme-${theme}`);
    }

    // ------------------------------------------------------------------ //
    // Initialisation : thème puis premier état public
    // ------------------------------------------------------------------ //
    await appliquerTheme();
    try {
        const initial = await api.obtenir_etat_plateau();
        appliquerEtatPlateau(initial);
    } catch (err) {
        // Le premier push de Python prendra le relais si l'appel initial échoue.
    }
});
