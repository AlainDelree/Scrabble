/**
 * chevalet.js — fenêtre flottante du chevalet (issue #90, fusion #100).
 *
 * Cette fenêtre est la vue « privée » du joueur humain de référence : elle
 * affiche un panneau unique de ses lettres, toujours visible et réarrangeable
 * librement (y compris hors tour), ainsi que les contrôles de tour (Annuler /
 * Vérifier et calculer / Jouer, + « remettre ses lettres »). Le clic sur une
 * lettre la sélectionne côté Python (source de vérité) ; la pose effective se
 * fait au clic sur une case de la fenêtre PLATEAU. Un second clic sur une autre
 * case du panneau réarrange localement les lettres (réflexion), sans effet sur
 * la partie. L'état est poussé par Python via ``window.appliquerEtatChevalet``
 * après chaque mutation.
 *
 * Confidentialité (issues #33/#35, #99) : seules les lettres du joueur humain
 * de référence transitent jusqu'ici ; jamais le chevalet d'un ordinateur ni d'un
 * autre humain. Depuis la fusion #100, il n'y a plus de bascule « voir/cacher »
 * ni de boîte d'attente : le panneau du joueur de référence est toujours exposé.
 */
document.addEventListener('DOMContentLoaded', async () => {
    await window.Commun.pretPywebview();
    const api = window.pywebview.api;
    const C = window.Commun;

    // --- Éléments du DOM ---
    const barreDrag = document.getElementById('barre-drag');
    const chevaletNom = document.getElementById('chevalet-nom');
    const badgeHorsTour = document.getElementById('badge-hors-tour');

    const panneauEl = document.getElementById('panneau');
    const btnAidePanneau = document.getElementById('btn-aide-panneau');
    const aidePanneauPopover = document.getElementById('aide-panneau-popover');

    const zoneJeu = document.getElementById('zone-jeu');
    const btnValider = document.getElementById('btn-valider');
    const btnVerifierCoup = document.getElementById('btn-verifier-coup');
    const btnAnnuler = document.getElementById('btn-annuler');
    const btnEchangerTout = document.getElementById('btn-echanger-tout');
    const messageCoup = document.getElementById('message-coup');

    // Modale de choix de lettre pour un joker.
    const jokerModale = document.getElementById('joker-modale');
    const jokerGrille = document.getElementById('joker-grille');
    const jokerAnnuler = document.getElementById('joker-annuler');

    // Modale de détail du score (copie côté chevalet, issue #90).
    const modaleScore = C.creerModaleScore({
        modale: document.getElementById('score-modale'),
        titre: document.getElementById('score-titre'),
        detail: document.getElementById('score-detail'),
        total: document.getElementById('score-total'),
        fermer: document.getElementById('score-fermer'),
    });

    // --- État courant côté vue ---
    let etat = null;                 // dernier payload chevalet reçu de Python
    let dernierMonTour = null;       // pour détecter un changement de tour (issue #100)
    let panneauSignature = null;     // signature des lettres pour (re)bâtir le panneau
    let panneauLettres = [];         // {lettre, valeur, joker, indexOrigine} + 2 vides (null)
    let panneauSelection = null;     // index (dans panneauLettres) de la case sélectionnée
    let jokerModaleOuverte = false;  // évite de rouvrir la modale à chaque push

    // ------------------------------------------------------------------ //
    // Rendu
    // ------------------------------------------------------------------ //

    /** Vrai si c'est le tour du joueur de référence (seul cas où l'on peut poser). */
    function monTour() {
        return Boolean(etat && etat.mon_tour);
    }

    function afficherMessage(texte, type) {
        messageCoup.textContent = texte || '';
        messageCoup.className = 'message-coup' + (texte ? ' ' + (type || 'info') : '');
    }

    /** Indicateur discret « hors tour » (issue #100) : le panneau reste manipulable,
     *  on signale seulement que la pose est indisponible tant que ce n'est pas au
     *  joueur de référence de jouer. */
    function majBadgeHorsTour() {
        if (!badgeHorsTour) {
            return;
        }
        const horsTour = Boolean(etat) && !monTour();
        badgeHorsTour.hidden = !horsTour;
        if (horsTour) {
            badgeHorsTour.textContent = (etat && etat.terminee)
                ? '🏁 Partie terminée — vous pouvez encore réarranger vos lettres.'
                : '⏳ Ce n\'est pas votre tour — vous pouvez réarranger vos lettres.';
        }
    }

    /** Ensemble des index d'origine déjà posés en attente (cases « utilisées »). */
    function indexUtilises() {
        return new Set((etat && etat.en_attente ? etat.en_attente : []).map((p) => p.index));
    }

    function rendrePanneau() {
        chevaletNom.textContent = etat && etat.nom ? etat.nom : '—';
        panneauEl.innerHTML = '';
        if (panneauLettres.length === 0) {
            panneauEl.innerHTML = '<span class="panneau-vide">Chevalet vide.</span>';
            return;
        }
        const utilises = indexUtilises();
        panneauLettres.forEach((l, index) => {
            if (l === null) {
                const vide = document.createElement('div');
                vide.className = 'panneau-case-vide';
                vide.dataset.index = index;
                vide.title = 'Emplacement libre : cliquez d\'abord une lettre, '
                    + 'puis ici pour l\'y déplacer (réflexion, sans effet sur la partie).';
                panneauEl.appendChild(vide);
                return;
            }
            const c = document.createElement('div');
            c.className = 'panneau-case' + (l.joker ? ' joker' : '');
            if (utilises.has(l.indexOrigine)) {
                c.classList.add('utilisee');
            } else if (index === panneauSelection) {
                c.classList.add('selectionnee');
            }
            const lettreAffichee = l.joker ? '★' : C.escapeHtml(l.lettre);
            c.innerHTML = `${lettreAffichee}<span class="val">${l.valeur}</span>`;
            c.dataset.index = index;
            panneauEl.appendChild(c);
        });
    }

    function majControlesJeu() {
        const jouable = monTour();
        const n = (etat && etat.en_attente ? etat.en_attente : []).length;
        const nbLettres = (etat && etat.nb_lettres) || 0;
        // On DÉSACTIVE (plutôt que masquer) les actions de tour hors tour (issue #100).
        btnValider.disabled = !jouable || n === 0;
        btnVerifierCoup.disabled = !jouable || n === 0;
        btnAnnuler.disabled = !jouable || n === 0;
        btnEchangerTout.disabled = !jouable || nbLettres === 0;
    }

    /** Signature des lettres du chevalet (pour ne rebâtir le panneau qu'utile). */
    function signatureLettres(lettres) {
        return (lettres || []).map((l) => (l.joker ? '*' : l.lettre) + l.valeur).join(',');
    }

    /** (Re)construit le panneau à partir des lettres du chevalet. Chaque lettre
     *  garde son ``indexOrigine`` (position dans ``etat.lettres``) pour que la
     *  sélection Python vise la bonne lettre même après un réarrangement local
     *  (point critique du rapport #98). Deux emplacements vides sont ajoutés pour
     *  la réflexion. */
    function reconstruirePanneau() {
        const lettres = etat.lettres || [];
        panneauLettres = lettres.map((l, i) => ({ ...l, indexOrigine: i }));
        if (panneauLettres.length > 0) {
            panneauLettres.push(null, null);
        }
        panneauSelection = null;
    }

    // ------------------------------------------------------------------ //
    // Application d'un état poussé par Python (issue #90, contrat #99/#100)
    // ------------------------------------------------------------------ //
    function appliquerEtatChevalet(payload) {
        etat = payload || {};

        // Changement de tour (issue #100) : ``index_reference`` étant constant pour
        // toute la partie, on détecte le changement via ``mon_tour`` (bascule). Un
        // nouveau tour repart d'un panneau neuf (réarrangement local abandonné).
        const nouveauTour = etat.mon_tour !== dernierMonTour;
        dernierMonTour = etat.mon_tour;
        if (nouveauTour) {
            panneauSignature = null;
        }

        // Le panneau n'est reconstruit qu'au changement de tour ou de contenu du
        // chevalet (échange / nouveau tirage), pas à chaque pose (les lettres ne
        // changent pas en posant).
        const sig = signatureLettres(etat.lettres);
        if (sig !== panneauSignature) {
            reconstruirePanneau();
            panneauSignature = sig;
        }

        // Toute pose/annulation remet la sélection Python à null : on aligne la
        // sélection visuelle locale du panneau dessus (case « utilisée » ou libérée).
        if (etat.selection === null || etat.selection === undefined) {
            panneauSelection = null;
        }

        majBadgeHorsTour();
        rendrePanneau();
        majControlesJeu();

        // Demande de choix de lettre pour un joker (déclenchée par un clic sur une
        // case de la fenêtre plateau) : on ouvre la modale ici.
        if (etat.joker_demande && !jokerModaleOuverte) {
            ouvrirModaleJoker(etat.joker_demande);
        }
    }
    window.appliquerEtatChevalet = appliquerEtatChevalet;

    async function ouvrirModaleJoker(demande) {
        jokerModaleOuverte = true;
        const choix = await C.choisirLettreJoker({
            modale: jokerModale, grille: jokerGrille, annuler: jokerAnnuler,
        });
        jokerModaleOuverte = false;
        if (choix) {
            await api.poser_lettre_en_attente(
                demande.ligne, demande.colonne, choix, true, 0, demande.index);
        } else {
            // Annulé : on abandonne la demande de joker (garde les autres poses).
            await api.selectionner_lettre(null);
        }
    }

    // ------------------------------------------------------------------ //
    // Gestionnaires d'événements
    // ------------------------------------------------------------------ //

    // Clic sur une case du panneau : sémantique unifiée (issue #100).
    //  - 1er clic sur une lettre : sélection côté Python (api.selectionner_lettre)
    //    en visant son index d'origine (robuste au réarrangement local).
    //  - clic suivant sur une case du PLATEAU : pose (gérée par la fenêtre plateau).
    //  - clic suivant sur une autre case du panneau : réarrangement local (déplacement
    //    vers un vide ou échange), et annulation de la sélection Python.
    panneauEl.addEventListener('click', async (evt) => {
        const caseEl = evt.target.closest('.panneau-case, .panneau-case-vide');
        if (!caseEl) {
            return;
        }
        const index = Number(caseEl.dataset.index);
        const lettre = panneauLettres[index];
        const estVide = lettre === null;
        // Une lettre déjà posée (utilisée) n'est ni sélectionnable ni cible d'échange.
        const estUtilisee = !estVide && indexUtilises().has(lettre.indexOrigine);

        if (panneauSelection === null) {
            if (estVide || estUtilisee) {
                return;
            }
            afficherMessage('');
            panneauSelection = index;
            rendrePanneau();
            await api.selectionner_lettre(lettre.indexOrigine);
            return;
        }

        if (panneauSelection === index) {
            // Reclic sur la même lettre : désélection (locale + Python).
            panneauSelection = null;
            rendrePanneau();
            await api.selectionner_lettre(null);
            return;
        }

        if (estUtilisee) {
            return; // on n'échange pas avec une lettre déjà posée
        }

        // Réarrangement local (réflexion) : déplacement vers un vide ou échange.
        if (estVide) {
            panneauLettres[index] = panneauLettres[panneauSelection];
            panneauLettres[panneauSelection] = null;
        } else {
            const tmp = panneauLettres[panneauSelection];
            panneauLettres[panneauSelection] = panneauLettres[index];
            panneauLettres[index] = tmp;
        }
        panneauSelection = null;
        rendrePanneau();
        // Le réarrangement local invalide la sélection Python en cours.
        await api.selectionner_lettre(null);
    });

    // Clic droit : renvoie la lettre vers le vide le plus proche de la fin.
    panneauEl.addEventListener('contextmenu', async (evt) => {
        const caseEl = evt.target.closest('.panneau-case');
        if (!caseEl) {
            return;
        }
        evt.preventDefault();
        const origine = Number(caseEl.dataset.index);
        const lettre = panneauLettres[origine];
        // On ne déplace pas une lettre déjà posée.
        if (lettre === null || indexUtilises().has(lettre.indexOrigine)) {
            return;
        }
        const vides = [];
        panneauLettres.forEach((l, i) => {
            if (l === null) {
                vides.push(i);
            }
        });
        if (vides.length === 0) {
            return;
        }
        const cible = Math.max(...vides);
        panneauLettres[cible] = panneauLettres[origine];
        panneauLettres[origine] = null;
        const avaitSelection = panneauSelection !== null;
        panneauSelection = null;
        rendrePanneau();
        if (avaitSelection) {
            await api.selectionner_lettre(null);
        }
    });

    // ------------------------------------------------------------------ //
    // Déplacement applicatif de la fenêtre (issue #91 point 2, revu issue #92)
    // ------------------------------------------------------------------ //
    // Sous WebKitGTK, .pywebview-drag-region n'est pas géré : on déplace la
    // fenêtre nous-mêmes en écoutant les événements souris sur la seule barre du
    // haut, et en appelant api.deplacer_chevalet() en coordonnées écran absolues.
    //
    // Issue #92 : on repasse des événements *pointeur* (+ setPointerCapture) aux
    // événements *souris classiques* (mousedown/mousemove/mouseup), plus largement
    // et fiablement supportés par le backend WebKitGTK. Le suivi hors de la barre
    // (glissé rapide) est assuré en écoutant mousemove/mouseup sur `document` plutôt
    // que par une capture de pointeur (potentiellement non honorée par WebKitGTK).
    // Le drag reste strictement confiné : il ne démarre qu'au mousedown SUR la barre.
    // Traces console (issue #92) : confirment que le JS reçoit bien les événements ;
    // côté Python, debut_deplacement_chevalet/deplacer_chevalet journalisent aussi.
    if (barreDrag) {
        let dragActif = false;
        let dragOrigWin = { x: 0, y: 0 };   // position fenêtre au début du drag
        let dragOrigSouris = { x: 0, y: 0 }; // position souris (écran) au début
        let dragCible = null;                // {x, y} en attente d'envoi
        let dragRafPlanifie = false;

        function envoyerDeplacement() {
            dragRafPlanifie = false;
            if (dragCible) {
                api.deplacer_chevalet(dragCible.x, dragCible.y);
                dragCible = null;
            }
        }

        async function debutDrag(evt) {
            if (evt.button !== 0) {
                return; // clic gauche uniquement
            }
            console.log('[chevalet] mousedown sur barre-drag reçu — début de drag.');
            let pos;
            try {
                pos = await api.debut_deplacement_chevalet();
            } catch (err) {
                console.log('[chevalet] debut_deplacement_chevalet a échoué :', err);
                return;
            }
            if (!pos || !pos.succes) {
                return;
            }
            dragActif = true;
            dragOrigWin = { x: pos.x, y: pos.y };
            dragOrigSouris = { x: evt.screenX, y: evt.screenY };
        }

        function bougerDrag(evt) {
            if (!dragActif) {
                return;
            }
            dragCible = {
                x: dragOrigWin.x + (evt.screenX - dragOrigSouris.x),
                y: dragOrigWin.y + (evt.screenY - dragOrigSouris.y),
            };
            // rAF : on n'envoie qu'un déplacement par frame (évite d'inonder l'IPC).
            if (!dragRafPlanifie) {
                dragRafPlanifie = true;
                requestAnimationFrame(envoyerDeplacement);
            }
        }

        function finDrag() {
            if (!dragActif) {
                return;
            }
            dragActif = false;
            console.log('[chevalet] fin de drag (mouseup).');
        }

        // Démarrage confiné à la barre ; suivi/fin sur le document entier pour ne
        // pas « décrocher » si le curseur sort de la barre pendant un glissé.
        barreDrag.addEventListener('mousedown', debutDrag);
        document.addEventListener('mousemove', bougerDrag);
        document.addEventListener('mouseup', finDrag);
    }

    // Aide du panneau (icône « i »).
    C.configurerPopover(btnAidePanneau, aidePanneauPopover);

    // Annuler : abandonne toute la pose en cours (via Python).
    btnAnnuler.addEventListener('click', async () => {
        afficherMessage('');
        await api.annuler_pose();
    });

    // Vérifier et calculer : calcule les points sans jouer, ouvre le détail ici.
    btnVerifierCoup.addEventListener('click', async () => {
        btnVerifierCoup.disabled = true;
        let res;
        try {
            res = await api.verifier_coup();
        } catch (err) {
            afficherMessage('Erreur inattendue lors de la vérification du coup.', 'erreur');
            majControlesJeu();
            return;
        }
        if (res && res.succes) {
            const points = res.points != null ? res.points : 0;
            const mot = (res.detail && res.detail.mots && res.detail.mots[0])
                ? res.detail.mots[0].texte : null;
            afficherMessage(
                `Coup valide${mot ? ' (' + mot + ')' : ''} : +${points} point${points > 1 ? 's' : ''}. `
                + `Cliquez « Jouer » pour le poser.`, 'succes');
            if (res.detail) {
                modaleScore.afficher(res.detail, `Coup en attente${mot ? ' — « ' + mot + ' »' : ''}`);
            }
        } else {
            afficherMessage((res && res.erreur) ? res.erreur : 'Coup invalide.', 'erreur');
        }
        majControlesJeu();
    });

    // Jouer : pose le mot formé par les lettres en attente (lues côté Python).
    btnValider.addEventListener('click', async () => {
        btnValider.disabled = true;
        let res;
        try {
            res = await api.poser_mot();
        } catch (err) {
            afficherMessage('Erreur inattendue lors de la validation du coup.', 'erreur');
            majControlesJeu();
            return;
        }
        if (res && res.succes) {
            const points = res.points != null ? res.points : 0;
            afficherMessage(`Coup joué (+${points} point${points > 1 ? 's' : ''}).`, 'succes');
            // Python rediffuse l'état (nouveau tour) : le rendu suit via le push.
        } else {
            afficherMessage((res && res.erreur) ? res.erreur : 'Coup refusé.', 'erreur');
            majControlesJeu();
        }
    });

    // Remettre tout le chevalet et passer (échange complet).
    btnEchangerTout.addEventListener('click', async () => {
        btnEchangerTout.disabled = true;
        let res;
        try {
            res = await api.echanger_tout();
        } catch (err) {
            afficherMessage('Erreur inattendue lors de l\'échange des lettres.', 'erreur');
            majControlesJeu();
            return;
        }
        if (res && res.succes) {
            afficherMessage('Toutes vos lettres ont été remises dans le sac. Tour passé.', 'succes');
        } else {
            afficherMessage((res && res.erreur) || 'Échange impossible.', 'erreur');
            majControlesJeu();
        }
    });

    // --- Initialisation : premier tirage de l'état privé ---
    try {
        const initial = await api.obtenir_etat_chevalet();
        appliquerEtatChevalet(initial);
    } catch (err) {
        // Le premier push de Python prendra le relais si l'appel initial échoue.
    }
});
