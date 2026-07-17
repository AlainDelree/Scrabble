/**
 * chevalet.js — fenêtre flottante du chevalet (issue #90).
 *
 * Cette fenêtre est la vue « privée » : elle affiche les lettres du joueur
 * humain courant, la zone de brouillon (réflexion) et les contrôles de tour
 * (Annuler / Vérifier et calculer / Jouer, + « remettre ses lettres »). Le clic
 * sur une lettre la sélectionne côté Python (source de vérité, issue #90) ; la
 * pose effective se fait au clic sur une case de la fenêtre PLATEAU. L'état est
 * poussé par Python via ``window.appliquerEtatChevalet`` après chaque mutation.
 *
 * Confidentialité (issues #33/#35) : seules les lettres du joueur humain courant
 * transitent jusqu'ici ; jamais le chevalet d'un ordinateur. La bascule
 * « voir / cacher mes lettres » reste locale (parties à ≥ 2 humains).
 */
document.addEventListener('DOMContentLoaded', async () => {
    await window.Commun.pretPywebview();
    const api = window.pywebview.api;
    const C = window.Commun;

    // --- Éléments du DOM ---
    const chevaletEl = document.getElementById('chevalet');
    const chevaletNom = document.getElementById('chevalet-nom');
    const btnVisibilite = document.getElementById('btn-visibilite');
    const chevaletEntete = document.querySelector('.chevalet-entete');
    const zoneReflexion = document.querySelector('.zone-reflexion');
    const chevaletAide = document.getElementById('chevalet-aide');

    const zoneAttenteIA = document.getElementById('zone-attente-ia');
    const attenteMessageIA = document.getElementById('attente-ia-message');

    const blocBrouillon = document.getElementById('bloc-brouillon');
    const brouillonEl = document.getElementById('brouillon');
    const btnAideBrouillon = document.getElementById('btn-aide-brouillon');
    const aideBrouillonPopover = document.getElementById('aide-brouillon-popover');

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
    let chevaletVisible = false;
    let chevaletTjrsRevele = false;  // vrai si ≤ 1 humain (rien à cacher)
    let dernierIndexCourant = null;  // pour détecter un changement de tour
    let brouillonSignature = null;   // signature des lettres pour (re)bâtir le brouillon
    let brouillonLettres = [];       // {lettre, valeur, joker} + 2 vides (null)
    let brouillonSelection = null;
    let jokerModaleOuverte = false;  // évite de rouvrir la modale à chaque push

    // ------------------------------------------------------------------ //
    // Rendu
    // ------------------------------------------------------------------ //

    function estTourHumain() {
        return Boolean(etat && !etat.terminee && etat.tour_humain);
    }

    function afficherMessage(texte, type) {
        messageCoup.textContent = texte || '';
        messageCoup.className = 'message-coup' + (texte ? ' ' + (type || 'info') : '');
    }

    /** Bascule interactif / attente (tour d'un ordinateur). */
    function majModeTour() {
        const attenteIA = Boolean(etat && !etat.terminee && !etat.tour_humain);
        zoneAttenteIA.hidden = !attenteIA;
        if (attenteIA) {
            attenteMessageIA.textContent = `En attente du coup de ${etat.nom}…`;
        }
        if (chevaletEntete) {
            chevaletEntete.hidden = attenteIA;
        }
        if (zoneReflexion) {
            zoneReflexion.hidden = attenteIA;
        }
        if (chevaletAide) {
            chevaletAide.hidden = attenteIA || chevaletTjrsRevele;
        }
        if (attenteIA) {
            zoneJeu.hidden = true;
        }
    }

    function rendreChevaletMasque(nbLettres) {
        chevaletEl.innerHTML = '';
        if (!nbLettres) {
            chevaletEl.innerHTML = '<span class="chevalet-vide">Chevalet vide.</span>';
            return;
        }
        for (let i = 0; i < nbLettres; i++) {
            const c = document.createElement('div');
            c.className = 'chevalet-case masquee';
            c.textContent = '?';
            chevaletEl.appendChild(c);
        }
    }

    function rendreChevaletRevele(lettres) {
        chevaletEl.innerHTML = '';
        if (!lettres.length) {
            chevaletEl.innerHTML = '<span class="chevalet-vide">Chevalet vide.</span>';
            return;
        }
        const utilises = new Set((etat.en_attente || []).map((p) => p.index));
        lettres.forEach((l, index) => {
            const c = document.createElement('div');
            c.className = 'chevalet-case revelee' + (l.joker ? ' joker' : '');
            if (utilises.has(index)) {
                c.classList.add('utilisee');
            } else if (index === etat.selection) {
                c.classList.add('selectionnee');
            }
            const lettreAffichee = l.joker ? '★' : C.escapeHtml(l.lettre);
            c.innerHTML = `${lettreAffichee}<span class="val">${l.valeur}</span>`;
            c.dataset.index = index;
            chevaletEl.appendChild(c);
        });
    }

    function rendreChevalet() {
        const courant = etat && etat.nom ? etat.nom : '—';
        chevaletNom.textContent = courant;
        if (!estTourHumain()) {
            rendreChevaletMasque(0);
            return;
        }
        if (chevaletVisible) {
            btnVisibilite.textContent = '🙈 Cacher mes lettres';
            rendreChevaletRevele(etat.lettres || []);
        } else {
            btnVisibilite.textContent = '👁️ Voir mes lettres';
            rendreChevaletMasque(etat.nb_lettres || 0);
        }
    }

    function afficherMessageBrouillon() { /* réservé si besoin futur */ }

    function rendreBrouillon() {
        const afficher = chevaletVisible && brouillonLettres.length > 0;
        blocBrouillon.hidden = !afficher;
        if (!afficher) {
            brouillonSelection = null;
            return;
        }
        brouillonEl.innerHTML = '';
        brouillonLettres.forEach((l, index) => {
            if (l === null) {
                const vide = document.createElement('div');
                vide.className = 'brouillon-case-vide';
                vide.dataset.index = index;
                vide.title = 'Emplacement vide : cliquez d\'abord une lettre, '
                    + 'puis ici pour l\'y déplacer. Figure aussi une lettre déjà '
                    + 'posée sur le plateau à intégrer à la réflexion.';
                brouillonEl.appendChild(vide);
                return;
            }
            const c = document.createElement('div');
            c.className = 'brouillon-case' + (l.joker ? ' joker' : '');
            if (index === brouillonSelection) {
                c.classList.add('selectionnee');
            }
            const lettreAffichee = l.joker ? '★' : C.escapeHtml(l.lettre);
            c.innerHTML = `${lettreAffichee}<span class="val">${l.valeur}</span>`;
            c.dataset.index = index;
            brouillonEl.appendChild(c);
        });
    }

    function majActionsChevalet() {
        const actif = chevaletVisible && estTourHumain() && (etat.nb_lettres || 0) > 0;
        btnEchangerTout.hidden = !actif;
        btnEchangerTout.disabled = false;
    }

    function majControlesJeu() {
        const jouable = chevaletVisible && estTourHumain();
        zoneJeu.hidden = !jouable;
        if (!jouable) {
            return;
        }
        const n = (etat.en_attente || []).length;
        btnValider.disabled = n === 0;
        btnVerifierCoup.disabled = n === 0;
        btnAnnuler.disabled = n === 0;
    }

    /** Signature des lettres du chevalet (pour ne rebâtir le brouillon qu'utile). */
    function signatureLettres(lettres) {
        return (lettres || []).map((l) => (l.joker ? '*' : l.lettre) + l.valeur).join(',');
    }

    function reconstruireBrouillon() {
        const lettres = etat.lettres || [];
        brouillonLettres = lettres.map((l) => ({ ...l }));
        if (brouillonLettres.length > 0) {
            brouillonLettres.push(null, null);
        }
        brouillonSelection = null;
    }

    function configurerConfidentialite() {
        chevaletTjrsRevele = (etat.nb_humains || 0) <= 1;
        btnVisibilite.hidden = chevaletTjrsRevele;
        if (chevaletAide) {
            chevaletAide.hidden = chevaletTjrsRevele;
        }
    }

    // ------------------------------------------------------------------ //
    // Application d'un état poussé par Python (issue #90)
    // ------------------------------------------------------------------ //
    function appliquerEtatChevalet(payload) {
        etat = payload || {};
        configurerConfidentialite();

        // Changement de tour : on remasque (confidentialité) et on repart d'un
        // brouillon neuf. Le brouillon n'est PAS reconstruit à chaque pose (les
        // lettres du chevalet ne changent pas en posant), seulement au changement
        // de tour, à un échange (lettres différentes) ou à la révélation.
        const nouveauTour = etat.index_courant !== dernierIndexCourant;
        dernierIndexCourant = etat.index_courant;
        if (nouveauTour) {
            chevaletVisible = chevaletTjrsRevele;
            brouillonSignature = null;
        }

        const sig = signatureLettres(etat.lettres);
        if (chevaletVisible && sig !== brouillonSignature) {
            reconstruireBrouillon();
            brouillonSignature = sig;
        }

        majModeTour();
        rendreChevalet();
        rendreBrouillon();
        majActionsChevalet();
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

    // Bascule voir / cacher les lettres.
    btnVisibilite.addEventListener('click', () => {
        chevaletVisible = !chevaletVisible;
        if (chevaletVisible) {
            reconstruireBrouillon();
            brouillonSignature = signatureLettres(etat.lettres);
        }
        rendreChevalet();
        rendreBrouillon();
        majActionsChevalet();
        majControlesJeu();
    });

    // Clic sur une lettre du chevalet révélé : sélection côté Python.
    chevaletEl.addEventListener('click', async (evt) => {
        const caseEl = evt.target.closest('.chevalet-case.revelee');
        if (!caseEl || caseEl.classList.contains('utilisee')) {
            return;
        }
        const index = Number(caseEl.dataset.index);
        afficherMessage('');
        await api.selectionner_lettre(index);
    });

    // Brouillon : déplacement / échange par deux clics (réflexion locale).
    brouillonEl.addEventListener('click', (evt) => {
        const caseEl = evt.target.closest('.brouillon-case, .brouillon-case-vide');
        if (!caseEl) {
            return;
        }
        const index = Number(caseEl.dataset.index);
        const estVide = brouillonLettres[index] === null;
        if (brouillonSelection === null) {
            if (!estVide) {
                brouillonSelection = index;
            }
        } else if (brouillonSelection === index) {
            brouillonSelection = null;
        } else if (estVide) {
            brouillonLettres[index] = brouillonLettres[brouillonSelection];
            brouillonLettres[brouillonSelection] = null;
            brouillonSelection = null;
        } else {
            const tmp = brouillonLettres[brouillonSelection];
            brouillonLettres[brouillonSelection] = brouillonLettres[index];
            brouillonLettres[index] = tmp;
            brouillonSelection = null;
        }
        rendreBrouillon();
    });

    // Clic droit : renvoie la lettre vers le vide le plus proche de la fin.
    brouillonEl.addEventListener('contextmenu', (evt) => {
        const caseEl = evt.target.closest('.brouillon-case');
        if (!caseEl) {
            return;
        }
        evt.preventDefault();
        const origine = Number(caseEl.dataset.index);
        const vides = [];
        brouillonLettres.forEach((l, i) => {
            if (l === null) {
                vides.push(i);
            }
        });
        if (vides.length === 0) {
            return;
        }
        const cible = Math.max(...vides);
        brouillonLettres[cible] = brouillonLettres[origine];
        brouillonLettres[origine] = null;
        brouillonSelection = null;
        rendreBrouillon();
    });

    // Aide du brouillon (icône « i »).
    C.configurerPopover(btnAideBrouillon, aideBrouillonPopover);

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
            btnEchangerTout.disabled = false;
            return;
        }
        if (res && res.succes) {
            afficherMessage('Toutes vos lettres ont été remises dans le sac. Tour passé.', 'succes');
        } else {
            afficherMessage((res && res.erreur) || 'Échange impossible.', 'erreur');
            btnEchangerTout.disabled = false;
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
