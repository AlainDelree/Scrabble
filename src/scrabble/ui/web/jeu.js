/**
 * jeu.js — fenêtre PLATEAU (issue #90).
 *
 * Depuis la séparation en deux fenêtres pywebview (issue #90), cette vue ne porte
 * plus QUE la partie « publique » de l'écran de jeu : le plateau 15×15, les
 * panneaux d'information des joueurs, la barre du sac/historique, le bouton
 * « ▶ Jouer » de la fiche d'un ordinateur courant (issue #149, ex-« Faire jouer
 * l'ordinateur » ; un tour IA relève du plateau, l'humain n'a rien à jouer),
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
    // Modale de fin de partie (issue #142) : remplace l'ancien bandeau de fin.
    // Contient le message de victoire, le classement final, l'évaluation du
    // score, et trois boutons (retour menu / rester / recommencer).
    const modaleFin = document.getElementById('modale-fin');
    const modaleFinMessage = document.getElementById('modale-fin-message');
    const modaleFinClassement = document.getElementById('modale-fin-classement');
    const modaleFinEvaluation = document.getElementById('modale-fin-evaluation');
    const btnFinRetourMenu = document.getElementById('fin-retour-menu');
    const btnFinRester = document.getElementById('fin-rester');
    const btnFinRecommencer = document.getElementById('fin-recommencer');
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
    // Modale générique de confirmation d'une action de tour irréversible
    // (issue #139) : « Passer son tour » et « Remettre toutes ses lettres et
    // passer ». Pilotée via demanderConfirmation() qui renvoie une Promise<bool>.
    const confirmationModale = document.getElementById('confirmation-modale');
    const confirmationTitre = document.getElementById('confirmation-titre');
    const confirmationMessage = document.getElementById('confirmation-message');
    const confirmationAnnuler = document.getElementById('confirmation-annuler');
    const confirmationConfirmer = document.getElementById('confirmation-confirmer');

    // Mode « attente d'un tour d'ordinateur » (issue #35) déplacé côté plateau
    // (issue #90) : bloc + message « En attente du coup de… ». Le déclenchement du
    // coup se fait désormais via le bouton « ▶ Jouer » de la fiche du joueur
    // ordinateur courant (issue #149), plus par un bouton séparé.
    const zoneAttenteIA = document.getElementById('zone-attente-ia');
    const attenteMessageIA = document.getElementById('attente-ia-message');

    // Actions de tour (issue #101) : rapatriées depuis la fenêtre chevalet. Elles
    // ne sont visibles/actives que pendant le tour du joueur humain (voir
    // majActionsTour). Le message de retour dédié (#message-coup) s'affiche sous
    // les boutons, distinct du message éphémère de pose (#message-plateau).
    const zoneJeu = document.getElementById('zone-jeu');
    const btnValider = document.getElementById('btn-valider');
    const btnVerifierCoup = document.getElementById('btn-verifier-coup');
    const btnAnnuler = document.getElementById('btn-annuler');
    const btnPasser = document.getElementById('btn-passer');
    const btnEchangerTout = document.getElementById('btn-echanger-tout');
    // Échange partiel (issue #138) : boutons affichés uniquement en mode partiel.
    const btnCommencerEchange = document.getElementById('btn-commencer-echange');
    const zoneEchangePartiel = document.getElementById('zone-echange-partiel');
    const btnEchangerSelection = document.getElementById('btn-echanger-selection');
    const btnAnnulerEchange = document.getElementById('btn-annuler-echange');
    const messageCoup = document.getElementById('message-coup');

    // Vérification dictionnaire par saisie libre (issue #50/#86) : champ + bouton
    // logés derrière un popover discret dans la gouttière gauche.
    const champVerif = document.getElementById('champ-verif');
    const btnVerifier = document.getElementById('btn-verifier');
    const messageBrouillon = document.getElementById('message-brouillon');
    const definitionBrouillon = document.getElementById('definition-brouillon');
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
        // À la fermeture (bouton ou clic dehors), on retire la surbrillance du
        // coup consulté : le plateau revient alors au dernier coup réel (dont la
        // surbrillance .derniere-pose n'a jamais été touchée), issue #128.
        auFermer: () => retirerSurbrillanceCoupConsulte(),
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
     * Ensemble des cases posées lors du DERNIER coup joué (issue #125), sous
     * forme de clés ``"ligne,colonne"``. Réutilise ``historique[0].positions``
     * (déjà exposé côté Python pour l'animation de pose, issue #62/#58) : aucun
     * nouveau champ n'est ajouté à l'état public. Sert à mettre en surbrillance
     * persistante ces cases (classe ``.derniere-pose``) jusqu'au coup suivant —
     * contrairement à l'animation de pose, qui n'est que temporaire. Vide pour
     * une passe/un échange (positions vides) ou en l'absence d'historique.
     */
    function casesDernierCoup() {
        const historique = etat.historique;
        const tete = Array.isArray(historique) && historique.length ? historique[0] : null;
        const positions = tete && Array.isArray(tete.positions) ? tete.positions : [];
        return new Set(positions.map((p) => `${p.ligne},${p.colonne}`));
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
        // Cases du dernier coup à mettre en surbrillance (issue #125) : calculées
        // une fois par rendu, réappliquées à chaque diffusion → la surbrillance
        // suit automatiquement le dernier coup et disparaît des cases précédentes.
        const dernierCoup = casesDernierCoup();
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
                    // Surbrillance persistante du dernier coup joué (issue #125) :
                    // seulement sur les tuiles validées de ce coup (jamais sur une
                    // lettre en attente, dont le style orange a un autre sens).
                    if (dernierCoup.has(`${l},${c}`)) {
                        caseEl.classList.add('derniere-pose');
                    }
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

        // Joueur courant : l'humain voit une pastille « à vous » ; un ordinateur
        // expose directement un bouton « ▶ Jouer » (issue #149) qui déclenche son
        // coup (api.faire_jouer_ia), à la place de l'ancien label « son tour » et
        // du bouton séparé de la zone d'attente IA (retiré).
        let badgeTour = '';
        if (joueur.courant) {
            badgeTour = joueur.humain
                ? '<span class="panneau-tour">● à vous</span>'
                : '<button type="button" class="btn btn-primaire panneau-btn-jouer">▶ Jouer</button>';
        }
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
        // Le bouton « ▶ Jouer » d'un ordinateur courant (issue #149) déclenche le
        // même flux que l'ancien bouton de la zone d'attente IA. Le panneau est
        // reconstruit à chaque diffusion, donc l'écouteur est (ré)attaché ici.
        const boutonJouer = item.querySelector('.panneau-btn-jouer');
        if (boutonJouer) {
            boutonJouer.addEventListener('click', () => lancerTourIA(boutonJouer));
        }
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

    // Vrai une fois la modale de fin ouverte pour la partie courante (issue #142) :
    // évite de la rouvrir à chaque état repoussé (resynchronisation, etc.) alors
    // que l'utilisateur a choisi « Rester sur la partie ». Remis à faux dès qu'un
    // état de partie NON terminée arrive (nouvelle partie ou reprise en cours).
    let finModaleAffichee = false;

    /**
     * Pilote la modale de fin de partie (issue #142, ex-bandeau des issues
     * #45/#133/#137). Une fois la partie terminée, elle s'ouvre par-dessus le
     * plateau avec le message de victoire, le tableau de classement final listant
     * TOUS les joueurs triés par score décroissant avec leur rang, et l'évaluation
     * officielle du score total combiné (issue #137). Elle ne s'ouvre qu'une fois
     * par partie : si l'utilisateur la ferme (« Rester sur la partie »), un état
     * repoussé plus tard ne la rouvre pas.
     */
    function rendreFinPartie(terminee, gagnants, joueurs, evaluation) {
        if (!terminee) {
            finModaleAffichee = false;
            modaleFin.hidden = true;
            return;
        }

        // (Re)construit le contenu à chaque diffusion : le classement reflète
        // toujours l'état public reçu, même si la modale est déjà (ou pas encore)
        // ouverte.
        modaleFinMessage.textContent = gagnants && gagnants.length
            ? `🏁 Partie terminée — ${gagnants.join(', ')}`
            : '🏁 Partie terminée';

        modaleFinClassement.textContent = '';
        const classement = construireClassement(joueurs);
        if (classement) modaleFinClassement.appendChild(classement);

        modaleFinEvaluation.textContent = '';
        const eval_ = construireEvaluationScore(evaluation);
        if (eval_) modaleFinEvaluation.appendChild(eval_);

        // Ouverture unique : à la transition vers « terminée ». Fermée à la main,
        // la modale ne se rouvre pas tant que la partie reste terminée.
        if (!finModaleAffichee) {
            finModaleAffichee = true;
            modaleFin.hidden = false;
            // Le focus part sur « Rester » : l'action neutre par défaut.
            btnFinRester.focus();
        }
    }

    /**
     * Construit le bloc compact d'évaluation officielle du score total combiné
     * (issue #137, livret Jeux Spear p.10) : total combiné, qualificatif
     * officiel (« Bon/Très bon/Excellent score ») s'il y a lieu, et score
     * individuel de référence (moyenne par joueur, à titre indicatif). La
     * classification est calculée côté Python (une seule source de vérité) et
     * transmise via ``etat.evaluation_score`` ; ici on ne fait qu'afficher.
     * Renvoie null en l'absence d'évaluation exploitable.
     */
    function construireEvaluationScore(evaluation) {
        if (!evaluation || typeof evaluation.total !== 'number') return null;

        const bloc = document.createElement('div');
        bloc.className = 'evaluation-score';

        const ligneTotal = document.createElement('div');
        ligneTotal.className = 'evaluation-score-total';
        let texteTotal = `Total combiné : ${evaluation.total} points`;
        if (evaluation.qualificatif) {
            texteTotal += ` — ${evaluation.qualificatif}`;
        }
        ligneTotal.textContent = texteTotal;
        bloc.appendChild(ligneTotal);

        if (Number(evaluation.nb_joueurs) > 0 && evaluation.moyenne != null) {
            const ligneMoyenne = document.createElement('div');
            ligneMoyenne.className = 'evaluation-score-moyenne';
            ligneMoyenne.textContent =
                `soit environ ${evaluation.moyenne} points par joueur`;
            bloc.appendChild(ligneMoyenne);
        }
        return bloc;
    }

    /** Ordinal français court : 1 → « 1er », n → « ne » (2e, 3e…). */
    function ordinalFr(n) {
        return n === 1 ? '1er' : `${n}e`;
    }

    /**
     * Construit le petit tableau de classement final (issue #133) : tous les
     * joueurs triés par score décroissant avec leur rang. Les ex-æquo partagent
     * le même rang (classement « sportif » : 1, 2, 2, 4) et sont annotés
     * « ex æquo ». Renvoie null en l'absence de joueurs.
     */
    function construireClassement(joueurs) {
        if (!Array.isArray(joueurs) || joueurs.length === 0) return null;
        const tries = joueurs
            .map((j) => ({ nom: j.nom, score: Number(j.score) || 0 }))
            .sort((a, b) => b.score - a.score);
        // Rang « sportif » : à score égal, même rang ; le rang suivant tient
        // compte du nombre d'ex-æquo déjà classés (l'index dans la liste triée).
        let rangPrec = 0;
        let scorePrec = null;
        const lignes = tries.map((j, i) => {
            const rang = (scorePrec !== null && j.score === scorePrec) ? rangPrec : i + 1;
            rangPrec = rang;
            scorePrec = j.score;
            return { nom: j.nom, score: j.score, rang };
        });
        // Nombre de joueurs partageant chaque rang → marquer les ex-æquo.
        const compteRang = {};
        lignes.forEach((l) => { compteRang[l.rang] = (compteRang[l.rang] || 0) + 1; });

        const table = document.createElement('table');
        table.className = 'classement-final';
        const caption = document.createElement('caption');
        caption.textContent = 'Classement final';
        table.appendChild(caption);
        const tbody = document.createElement('tbody');
        lignes.forEach((l) => {
            const tr = document.createElement('tr');
            if (l.rang === 1) tr.classList.add('classement-premier');
            const tdRang = document.createElement('td');
            tdRang.className = 'classement-rang';
            tdRang.textContent = ordinalFr(l.rang) + (compteRang[l.rang] > 1 ? ' ex æquo' : '');
            const tdNom = document.createElement('td');
            tdNom.className = 'classement-nom';
            tdNom.textContent = l.nom;
            const tdScore = document.createElement('td');
            tdScore.className = 'classement-score';
            tdScore.textContent = l.score;
            tr.append(tdRang, tdNom, tdScore);
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        return table;
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

    /**
     * Surbrillance TEMPORAIRE du coup CONSULTÉ dans l'historique (issue #128).
     * Applique la classe ``.coup-consulte`` (visuellement distincte du liseré vert
     * ``.derniere-pose`` du dernier coup réel — voir jeu.css) aux cases des
     * ``positions`` du coup cliqué. Réutilise le même repérage que ``animerPose``.
     * Un appel remplace toujours la surbrillance précédente : cliquer un autre coup
     * déplace le liseré, et une passe/un échange (``positions`` vide) ne surligne
     * rien de nouveau tout en effaçant l'éventuel coup consulté précédent.
     */
    function surbrillerCoupConsulte(positions) {
        retirerSurbrillanceCoupConsulte();
        const cases = Array.isArray(positions) ? positions : [];
        cases.forEach(({ ligne, colonne }) => {
            const caseEl = plateauEl.querySelector(
                `.case[data-ligne="${ligne}"][data-colonne="${colonne}"]`);
            if (caseEl) {
                caseEl.classList.add('coup-consulte');
            }
        });
    }

    /**
     * Retire la surbrillance du coup consulté (issue #128). Appelée à la fermeture
     * de la modale de détail : le plateau retrouve la seule surbrillance du dernier
     * coup réel (``.derniere-pose``, jamais modifiée ici), évitant de laisser un
     * repère trompeur une fois la consultation terminée.
     */
    function retirerSurbrillanceCoupConsulte() {
        plateauEl.querySelectorAll('.case.coup-consulte')
            .forEach((el) => el.classList.remove('coup-consulte'));
    }

    /** Ouvre le détail d'une action de l'historique au clic (issue #37). */
    function ouvrirDetailHistorique(entree) {
        if (!entree) {
            return;
        }
        // Met en surbrillance les cases de CE coup (issue #128), y compris quand
        // c'est déjà le dernier coup (le liseré bleu prime alors le vert). Une
        // passe/un échange (positions vide) n'ajoute aucune surbrillance.
        surbrillerCoupConsulte(entree.positions);
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
        }
        majActionsTour();
    }

    /**
     * Visibilité/activation des actions de tour (issue #101). Ces boutons ne sont
     * affichés QUE pendant le tour du joueur humain de référence (``tour_humain``
     * dans le payload public : avec un seul humain, il équivaut à « c'est au joueur
     * de référence de jouer »). Pendant l'attente d'un tour d'ordinateur ou une
     * fois la partie terminée, la zone est masquée. C'est une aide visuelle : la
     * protection de fond reste le garde de tour côté API (issue #99).
     */
    function majActionsTour() {
        const tourHumain = Boolean(etat && !etat.terminee && etat.tour_humain);
        zoneJeu.hidden = !tourHumain;
        if (!tourHumain) {
            afficherMessageCoup('');
            return;
        }
        const n = enAttente.length;
        const courant = etat.joueurs[etat.index_courant];
        const nbLettres = (courant && courant.nb_lettres) || 0;
        // On DÉSACTIVE les actions selon l'état du coup en attente (rien à annuler/
        // vérifier/jouer tant qu'aucune lettre n'est posée).
        btnValider.disabled = n === 0;
        btnVerifierCoup.disabled = n === 0;
        btnAnnuler.disabled = n === 0;
        // Passer son tour reste un droit normal du jeu : toujours actif pendant
        // le tour de l'humain, indépendamment du coup en attente et du sac
        // (recours pour débloquer un joueur sac vide, issue #132).
        btnPasser.disabled = false;
        // Le sac vide rend l'échange complet impossible : plutôt qu'un bouton
        // cliquable qui échouerait systématiquement (rapport #130, issue #132),
        // on le désactive dans ce cas — « Passer son tour » prend le relais.
        const sacVide = !etat.jetons_sac;
        // Échange partiel (issue #138) : selon le réglage « type_echange », on
        // montre soit l'échange complet (défaut), soit le flux d'échange partiel.
        const partiel = etat.type_echange === 'partiel';
        const modeEchange = partiel && Boolean(etat.mode_echange);
        const nbEchange = Array.isArray(etat.selection_echange)
            ? etat.selection_echange.length : 0;
        const jetonsSac = etat.jetons_sac || 0;
        // Complet : bouton unique, masqué en mode partiel.
        btnEchangerTout.hidden = partiel;
        btnEchangerTout.disabled = nbLettres === 0 || sacVide;
        // Partiel, hors sélection : bouton d'entrée dans le mode.
        btnCommencerEchange.hidden = !(partiel && !modeEchange);
        btnCommencerEchange.disabled = nbLettres === 0 || sacVide;
        // Partiel, en sélection : valider (assez de jetons ?) ou annuler.
        zoneEchangePartiel.hidden = !modeEchange;
        btnEchangerSelection.disabled = nbEchange === 0 || nbEchange > jetonsSac;
    }

    /** Message de retour des actions de tour (issue #101), sous les boutons. */
    function afficherMessageCoup(texte, type) {
        messageCoup.textContent = texte || '';
        messageCoup.className = 'message-coup' + (texte ? ' ' + (type || 'info') : '');
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
        rendreFinPartie(etat.terminee, etat.gagnants, etat.joueurs, etat.evaluation_score);
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
        // Un coup qui rapporte des points déclenche un toast « +X points » près du
        // panneau de son auteur (issue #136), indépendant du toast Scrabble. Une
        // passe/un échange (score_action 0, positions vide) ne déclenche rien.
        const marquant = Number(tete.score_action) > 0;
        if (tete.positions && tete.positions.length) {
            animerPose(tete.positions).then(() => {
                if (marquant) {
                    afficherToastPoints(tete.index_joueur, tete.score_action);
                }
                if (tete.detail && tete.detail.bonus_scrabble) {
                    celebrerScrabble();
                }
            });
        } else if (marquant) {
            afficherToastPoints(tete.index_joueur, tete.score_action);
        }
    }

    // ------------------------------------------------------------------ //
    // Pose « clic-clic » côté plateau (issue #90)
    // ------------------------------------------------------------------ //

    /**
     * Clic sur une case du plateau :
     *  - case portant une lettre en attente : Python retire cette lettre (sans
     *    sélection) ou la remplace par la lettre sélectionnée dans le chevalet,
     *    l'ancienne repartant au chevalet (issue #129) ;
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

        // Case portant une lettre en attente (recliquer sa case). Python décide :
        //  - sans sélection dans le chevalet : retrait simple (comportement d'origine) ;
        //  - avec une lettre sélectionnée : remplacement — l'ancienne lettre revient
        //    au chevalet, la sélection prend sa place (issue #129). Sur un joker
        //    sélectionné, la modale de choix s'ouvre côté chevalet (joker_requis).
        if (attenteEn(ligne, colonne)) {
            afficherMessagePlateau('');
            let res;
            try {
                res = await api.remplacer_ou_retirer_lettre_en_attente(ligne, colonne);
            } catch (err) {
                afficherMessagePlateau('Erreur lors du retrait de la lettre.', 'erreur');
                return;
            }
            if (res && res.joker_requis) {
                afficherMessagePlateau(
                    'Choisissez la lettre du joker dans la fenêtre « Chevalet ».', 'info');
            } else if (res && res.succes === false) {
                afficherMessagePlateau(res.erreur || 'Remplacement impossible.', 'info');
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
    // Modale de fin de partie — trois actions (issue #142)
    // ------------------------------------------------------------------ //

    // « Rester sur la partie » : ferme simplement la modale et laisse le plateau
    // final affiché pour consultation libre. finModaleAffichee reste vrai : la
    // modale ne se rouvrira pas tant que la partie reste terminée.
    function resterSurLaPartie() {
        modaleFin.hidden = true;
    }
    btnFinRester.addEventListener('click', resterSurLaPartie);
    // Clic dehors et Échap = « Rester » (fermeture non destructrice).
    modaleFin.addEventListener('click', (evt) => {
        if (evt.target === modaleFin) resterSurLaPartie();
    });
    document.addEventListener('keydown', (evt) => {
        if (evt.key === 'Escape' && !modaleFin.hidden) resterSurLaPartie();
    });

    // « Retour au menu » : même comportement que le bouton utilitaire du haut.
    // En fin de partie il n'y a jamais de coup en attente : appel direct, sans
    // la modale d'avertissement.
    btnFinRetourMenu.addEventListener('click', () => {
        retournerAuMenu();
    });

    // « Recommencer » : demande à Python une nouvelle partie avec les mêmes
    // joueurs (nouveau tirage). En cas de succès, les deux fenêtres se ferment et
    // l'écran de jeu se rouvre sur la nouvelle partie (piloté par Python) ; en cas
    // d'échec, on réactive le bouton et on signale l'erreur.
    btnFinRecommencer.addEventListener('click', async () => {
        btnFinRecommencer.disabled = true;
        let res;
        try {
            res = await api.recommencer();
        } catch (err) {
            btnFinRecommencer.disabled = false;
            afficherMessagePlateau('Recommencer impossible : ' + err, 'erreur');
            return;
        }
        if (res && res.succes === false) {
            btnFinRecommencer.disabled = false;
            afficherMessagePlateau(
                'Recommencer impossible : ' + (res.erreur || 'erreur inconnue'), 'erreur');
        }
        // Succès : les DEUX fenêtres se ferment, une nouvelle partie s'ouvre (Python).
    });

    // ------------------------------------------------------------------ //
    // Confirmation générique d'une action de tour irréversible (issue #139)
    // ------------------------------------------------------------------ //
    // demanderConfirmation ouvre #confirmation-modale avec le titre/message et le
    // libellé de bouton fournis, puis renvoie une Promise résolue à ``true`` si le
    // joueur confirme, ``false`` s'il annule (bouton Annuler, clic dehors ou Échap).
    // Tant qu'aucune confirmation n'a lieu, AUCUN appel API n'est déclenché.
    let resoudreConfirmation = null;

    function fermerConfirmation(reponse) {
        if (!resoudreConfirmation) return;
        const resoudre = resoudreConfirmation;
        resoudreConfirmation = null;
        confirmationModale.hidden = true;
        resoudre(reponse);
    }

    function demanderConfirmation(titre, message, texteConfirmer) {
        // Une éventuelle demande précédente encore ouverte est traitée comme annulée.
        fermerConfirmation(false);
        confirmationTitre.textContent = titre;
        confirmationMessage.textContent = message;
        confirmationConfirmer.textContent = texteConfirmer || '✓ Confirmer';
        confirmationModale.hidden = false;
        // Le focus part sur « Annuler » : l'action la moins risquée par défaut.
        confirmationAnnuler.focus();
        return new Promise((resoudre) => { resoudreConfirmation = resoudre; });
    }

    confirmationAnnuler.addEventListener('click', () => fermerConfirmation(false));
    confirmationConfirmer.addEventListener('click', () => fermerConfirmation(true));
    confirmationModale.addEventListener('click', (evt) => {
        if (evt.target === confirmationModale) fermerConfirmation(false);
    });
    document.addEventListener('keydown', (evt) => {
        if (evt.key === 'Escape' && !confirmationModale.hidden) fermerConfirmation(false);
    });

    // ------------------------------------------------------------------ //
    // Tour d'un ordinateur (issue #35/#55) — bouton côté plateau (issue #90)
    // ------------------------------------------------------------------ //

    // Bouton « ▶ Jouer » de la fiche d'un ordinateur courant (issue #149,
    // ex-« Faire jouer l'ordinateur » de la zone d'attente, issue #35/#90) : joue
    // UN SEUL tour d'ordinateur. Python rediffuse ensuite l'état aux deux fenêtres ;
    // l'animation de la pose est déclenchée par ``appliquerEtatPlateau`` (nouveau
    // coup en tête d'historique). Le panneau est reconstruit à chaque diffusion :
    // un bouton neuf réapparaît si le joueur suivant est encore un ordinateur.
    async function lancerTourIA(bouton) {
        if (bouton) bouton.disabled = true;
        let res;
        try {
            res = await api.faire_jouer_ia();
        } catch (err) {
            if (bouton) bouton.disabled = false;
            return;
        }
        if (!(res && res.succes) && bouton) {
            bouton.disabled = false;
        }
    }

    // ------------------------------------------------------------------ //
    // Actions de tour (issue #101, déplacées depuis la fenêtre chevalet)
    // ------------------------------------------------------------------ //
    // Ces boutons appellent les mêmes méthodes API qu'auparavant côté chevalet ;
    // seule leur fenêtre d'origine change. Après chaque succès, Python rediffuse
    // l'état aux deux fenêtres et majActionsTour réactualise l'activation.

    // Annuler : abandonne toute la pose en cours (via Python).
    btnAnnuler.addEventListener('click', async () => {
        afficherMessageCoup('');
        await api.annuler_pose();
    });

    // Vérifier et calculer : calcule les points sans jouer, ouvre le détail dans
    // la modale de score de CETTE fenêtre (réutilise le contrôleur modaleScore).
    btnVerifierCoup.addEventListener('click', async () => {
        btnVerifierCoup.disabled = true;
        let res;
        try {
            res = await api.verifier_coup();
        } catch (err) {
            afficherMessageCoup('Erreur inattendue lors de la vérification du coup.', 'erreur');
            majActionsTour();
            return;
        }
        if (res && res.succes) {
            const points = res.points != null ? res.points : 0;
            const mot = (res.detail && res.detail.mots && res.detail.mots[0])
                ? res.detail.mots[0].texte : null;
            afficherMessageCoup(
                `Coup valide${mot ? ' (' + mot + ')' : ''} : +${points} point${points > 1 ? 's' : ''}. `
                + `Cliquez « Jouer » pour le poser.`, 'succes');
            if (res.detail) {
                modaleScore.afficher(res.detail, `Coup en attente${mot ? ' — « ' + mot + ' »' : ''}`);
            }
        } else {
            afficherMessageCoup((res && res.erreur) ? res.erreur : 'Coup invalide.', 'erreur');
        }
        majActionsTour();
    });

    // Jouer : pose le mot formé par les lettres en attente (lues côté Python).
    btnValider.addEventListener('click', async () => {
        btnValider.disabled = true;
        let res;
        try {
            res = await api.poser_mot();
        } catch (err) {
            afficherMessageCoup('Erreur inattendue lors de la validation du coup.', 'erreur');
            majActionsTour();
            return;
        }
        if (res && res.succes) {
            const points = res.points != null ? res.points : 0;
            afficherMessageCoup(`Coup joué (+${points} point${points > 1 ? 's' : ''}).`, 'succes');
            // Python rediffuse l'état (nouveau tour) : le rendu suit via le push.
        } else {
            afficherMessageCoup((res && res.erreur) ? res.erreur : 'Coup refusé.', 'erreur');
            majActionsTour();
        }
    });

    // Passer son tour sans poser ni échanger de lettres (issue #132). Droit
    // normal du jeu, utilisable à tout moment du tour — et seul recours d'un
    // joueur humain sac vide qui ne peut ni poser ni échanger (rapport #130).
    btnPasser.addEventListener('click', async () => {
        // Confirmation obligatoire (issue #139) : un clic accidentel ne doit pas
        // faire perdre le tour. Seule la confirmation déclenche l'appel API.
        const confirme = await demanderConfirmation(
            'Passer votre tour ?',
            'Voulez-vous vraiment passer votre tour sans jouer ?',
            '⏭ Passer mon tour');
        if (!confirme) return;
        btnPasser.disabled = true;
        let res;
        try {
            res = await api.passer();
        } catch (err) {
            afficherMessageCoup('Erreur inattendue lors du passage de tour.', 'erreur');
            majActionsTour();
            return;
        }
        if (res && res.succes) {
            afficherMessageCoup('Tour passé.', 'succes');
            // Python rediffuse l'état (tour suivant ou fin de partie) : le rendu
            // suit via le push.
        } else {
            afficherMessageCoup((res && res.erreur) || 'Impossible de passer le tour.', 'erreur');
            majActionsTour();
        }
    });

    // Remettre tout le chevalet et passer (échange complet).
    btnEchangerTout.addEventListener('click', async () => {
        // Confirmation obligatoire (issue #139) avant d'échanger tout le chevalet
        // et de passer : action rare et irréversible pour le tour en cours.
        const confirme = await demanderConfirmation(
            'Remettre toutes vos lettres ?',
            'Voulez-vous vraiment échanger toutes vos lettres et passer votre tour ?',
            '♻️ Échanger et passer');
        if (!confirme) return;
        btnEchangerTout.disabled = true;
        let res;
        try {
            res = await api.echanger_tout();
        } catch (err) {
            afficherMessageCoup('Erreur inattendue lors de l\'échange des lettres.', 'erreur');
            majActionsTour();
            return;
        }
        if (res && res.succes) {
            afficherMessageCoup('Toutes vos lettres ont été remises dans le sac. Tour passé.', 'succes');
        } else {
            afficherMessageCoup((res && res.erreur) || 'Échange impossible.', 'erreur');
            majActionsTour();
        }
    });

    // Échange partiel (issue #138) : entrer dans le mode de sélection multiple.
    // Le marquage des lettres se fait ensuite côté chevalet (api.basculer_echange).
    btnCommencerEchange.addEventListener('click', async () => {
        btnCommencerEchange.disabled = true;
        let res;
        try {
            res = await api.commencer_echange();
        } catch (err) {
            afficherMessageCoup('Erreur inattendue à l\'ouverture de l\'échange.', 'erreur');
            majActionsTour();
            return;
        }
        if (res && res.succes) {
            afficherMessageCoup(
                'Marquez sur votre chevalet les lettres à échanger, puis validez.', 'info');
        } else {
            afficherMessageCoup((res && res.erreur) || 'Échange impossible.', 'erreur');
            majActionsTour();
        }
    });

    // Échange partiel : valider la sélection (remet les lettres marquées, repioche
    // autant, passe le tour). Python lit la sélection courante (indices None).
    btnEchangerSelection.addEventListener('click', async () => {
        btnEchangerSelection.disabled = true;
        let res;
        try {
            res = await api.echanger_selection();
        } catch (err) {
            afficherMessageCoup('Erreur inattendue lors de l\'échange des lettres.', 'erreur');
            majActionsTour();
            return;
        }
        if (res && res.succes) {
            afficherMessageCoup('Lettres échangées. Tour passé.', 'succes');
        } else {
            afficherMessageCoup((res && res.erreur) || 'Échange impossible.', 'erreur');
            majActionsTour();
        }
    });

    // Échange partiel : annuler la sélection en cours (quitte le mode d'échange).
    btnAnnulerEchange.addEventListener('click', async () => {
        try {
            await api.annuler_echange();
        } catch (err) {
            afficherMessageCoup('Erreur inattendue lors de l\'annulation.', 'erreur');
            return;
        }
        afficherMessageCoup('Sélection d\'échange annulée.', 'info');
    });

    // ------------------------------------------------------------------ //
    // Vérification dictionnaire (lecture seule, issue #50/#86)
    // ------------------------------------------------------------------ //

    function afficherMessageBrouillon(texte, type) {
        messageBrouillon.textContent = texte || '';
        messageBrouillon.className = 'message-brouillon' + (texte ? ' ' + (type || 'info') : '');
    }

    // Affiche la définition sous le verdict (issue #124). ``definition`` est la
    // liste de gloses ODS8 (ou null/absente). On n'appelle cette fonction que
    // pour un mot VALIDE : une liste vide/nulle signifie « pas de définition
    // dans l'index » (mot Hunspell uniquement) et affiche un message clair,
    // cohérent avec l'onglet Dictionnaire des réglages (issue #111).
    function afficherDefinitionBrouillon(definition) {
        if (!definitionBrouillon) return;
        definitionBrouillon.innerHTML = '';
        if (Array.isArray(definition) && definition.length) {
            const ol = document.createElement('ol');
            ol.className = 'definition-gloses';
            definition.forEach((glose) => {
                const li = document.createElement('li');
                li.textContent = glose;
                ol.appendChild(li);
            });
            definitionBrouillon.appendChild(ol);
        } else {
            const p = document.createElement('p');
            p.className = 'definition-indisponible';
            p.textContent = 'Définition indisponible (mots ODS 8 uniquement).';
            definitionBrouillon.appendChild(p);
        }
        definitionBrouillon.hidden = false;
    }

    function masquerDefinitionBrouillon() {
        if (!definitionBrouillon) return;
        definitionBrouillon.innerHTML = '';
        definitionBrouillon.hidden = true;
    }

    async function verifierMotDictionnaire() {
        const mot = champVerif.value;
        if (!mot.trim()) {
            afficherMessageBrouillon('Tapez un mot dans le champ pour le vérifier.', 'info');
            masquerDefinitionBrouillon();
            return;
        }
        let res;
        try {
            res = await api.verifier_mot(mot);
        } catch (err) {
            afficherMessageBrouillon('Erreur inattendue lors de la vérification.', 'invalide');
            masquerDefinitionBrouillon();
            return;
        }
        if (res && res.succes) {
            if (res.valide) {
                afficherMessageBrouillon(`✓ « ${res.mot} » est dans le dictionnaire.`, 'valide');
                // Mot valide : on montre la définition ODS8, ou « indisponible ».
                afficherDefinitionBrouillon(res.definition);
            } else {
                afficherMessageBrouillon(`✗ « ${res.mot} » n'est pas dans le dictionnaire.`, 'invalide');
                masquerDefinitionBrouillon();
            }
        } else {
            afficherMessageBrouillon((res && res.erreur) || 'Vérification impossible.', 'info');
            masquerDefinitionBrouillon();
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

    // Ouverture/fermeture du menu « Derniers coups » (issue #144) : on réutilise
    // le MÊME mécanisme que « Vérification dictionnaire » (C.configurerPopover) —
    // clic sur le bouton pour basculer, fermeture au clic EXTÉRIEUR ou à la touche
    // Échap, mise à jour d'aria-expanded. Cela remplace l'ancienne logique séparée
    // qui devait forcer la bascule native du <details> sous WebKitGTK (issues
    // #49/#56/#60) et ne se fermait pas à la perte de focus. La liste
    // (``historiqueListe``, id #historique-liste) sert de popover : les clics à
    // l'intérieur (ouverture du détail d'un coup) ne la ferment pas, configurerPopover
    // stoppant leur propagation vers document.
    const btnHistorique = document.getElementById('btn-historique');
    C.configurerPopover(btnHistorique, historiqueListe);

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

    /**
     * Toast éphémère « +X points » (issue #136) affiché ~3 s près du panneau du
     * joueur qui vient de jouer, pour tout coup rapportant des points (humain ou
     * ordinateur, quel que soit le nombre de mots formés : X est le score TOTAL
     * du coup). Réutilise le calque plein écran ``#scrabble-fete`` (toujours
     * ``pointer-events: none``) mais, contrairement au toast Scrabble centré, se
     * positionne dynamiquement face au bon panneau selon son côté (bas/haut/
     * gauche/droite, cf. issue #120) pour être clairement associé au bon joueur.
     * Il est indépendant du toast Scrabble : les deux peuvent coexister sans
     * fusion ni logique d'articulation, chacun suivant son propre cycle.
     */
    function afficherToastPoints(indexJoueur, score) {
        const points = Number(score);
        if (!(points > 0)) {
            return;
        }
        // Calque dédié (distinct de #scrabble-fete) : le toast Scrabble vide le
        // sien via innerHTML, on ne veut pas qu'il efface celui-ci au passage.
        const calque = document.getElementById('points-toasts');
        if (!calque) {
            return;
        }
        const joueur = (etat.joueurs || []).find((j) => j.index === indexJoueur);
        const cote = (joueur && joueur.position) || 'bas';
        const slot = slots[cote] || slots.bas;
        const panneau = slot ? slot.querySelector('.panneau-joueur') : null;
        // On ancre le toast sur l'avatar/l'icône du joueur (« près de l'image de
        // profil ») ; à défaut, sur le panneau entier.
        const ancre = panneau
            ? (panneau.querySelector('.panneau-avatar')
                || panneau.querySelector('.panneau-icone')
                || panneau)
            : null;

        // Placement (wrapper) et animation (toast interne) sont séparés : le
        // wrapper porte la transformation de recentrage face au panneau, le toast
        // porte le fondu d'apparition/disparition — aucune des deux ne se marche
        // dessus.
        const wrapper = document.createElement('div');
        wrapper.className = `points-toast-ancre points-toast-${cote}`;
        const toast = document.createElement('div');
        toast.className = 'points-toast';
        toast.textContent = `+${points} point${points > 1 ? 's' : ''}`;
        wrapper.appendChild(toast);

        const gap = 10;
        if (ancre) {
            const r = ancre.getBoundingClientRect();
            const cx = r.left + r.width / 2;
            const cy = r.top + r.height / 2;
            // Le toast pointe vers l'intérieur du plateau selon le côté du panneau.
            if (cote === 'haut') {
                wrapper.style.left = `${cx}px`;
                wrapper.style.top = `${r.bottom + gap}px`;
                wrapper.style.transform = 'translate(-50%, 0)';
            } else if (cote === 'gauche') {
                wrapper.style.left = `${r.right + gap}px`;
                wrapper.style.top = `${cy}px`;
                wrapper.style.transform = 'translate(0, -50%)';
            } else if (cote === 'droite') {
                wrapper.style.left = `${r.left - gap}px`;
                wrapper.style.top = `${cy}px`;
                wrapper.style.transform = 'translate(-100%, -50%)';
            } else { // 'bas' (et repli)
                wrapper.style.left = `${cx}px`;
                wrapper.style.top = `${r.top - gap}px`;
                wrapper.style.transform = 'translate(-50%, -100%)';
            }
        } else {
            // Aucun panneau trouvé : repli discret en bas-centre du calque.
            const c = calque.getBoundingClientRect();
            wrapper.style.left = `${c.left + c.width / 2}px`;
            wrapper.style.top = `${c.top + c.height * 0.82}px`;
            wrapper.style.transform = 'translate(-50%, -50%)';
        }

        calque.appendChild(wrapper);
        // 3 s d'affichage puis disparition automatique (le fondu de sortie est géré
        // par l'animation CSS, dont la durée totale vaut aussi 3 s).
        setTimeout(() => { wrapper.remove(); }, 3000);
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
