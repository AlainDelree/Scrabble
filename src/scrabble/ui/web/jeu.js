/**
 * jeu.js — écran de jeu unique (issue #90, refonte #186/#187).
 *
 * Après la refonte en deux colonnes (issue #186) puis la migration du chevalet
 * (issue #187, Issue B), cette vue unique porte TOUT l'écran de jeu : le plateau
 * 15×15, les panneaux d'information des joueurs, la barre du sac/historique, le
 * bouton « ▶ Jouer » de la fiche d'un ordinateur courant (issue #149), la
 * vérification dictionnaire, le « Retour au menu », la modale de détail du score,
 * le sélecteur de lettre du joker (issue #168) ET, désormais, le CHEVALET du
 * joueur humain de référence (panneau des 9 cases, zone C de la marge gauche —
 * bloc « Chevalet du joueur… » plus bas). L'ex-fenêtre chevalet flottante
 * (chevalet.html / chevalet.js, supprimés) n'existe plus ; seule sa mécanique de
 * drag de fenêtre n'a pas été migrée (sans objet sans fenêtre à déplacer).
 *
 * Source de vérité de l'état de pose : Python (``ApiJeu``, issue #90). Cette
 * fenêtre est une simple vue :
 *   - elle REÇOIT l'état public via ``window.appliquerEtatPlateau`` ET l'état
 *     privé du chevalet via ``window.appliquerEtatChevalet`` (tous deux poussés
 *     par Python — ``_diffuser`` — vers cette même fenêtre depuis l'issue #187) ;
 *   - au clic sur une case (plateau ou chevalet), elle DEMANDE la mutation à
 *     Python (``poser_lettre_en_attente`` / ``selectionner_lettre`` / …), qui
 *     rediffuse ensuite l'état.
 *
 * Confidentialité (issues #33/#35, #99) : le payload PLATEAU reçu ici est
 * strictement public (aucune identité de lettre de chevalet) ; le payload
 * CHEVALET porte les lettres du SEUL joueur humain de référence (jamais un
 * ordinateur ni un autre humain). Les deux co-résident maintenant dans ce
 * document, mais sans fuite : Python ne sérialise que les lettres du joueur de
 * référence, exactement comme quand le chevalet avait sa propre fenêtre.
 */

document.addEventListener('DOMContentLoaded', async () => {
    await window.Commun.pretPywebview();

    const api = window.pywebview.api;
    const C = window.Commun;

    // --- Éléments du DOM ---
    const plateauEl = document.getElementById('plateau');
    // Slots des fiches joueurs, empilés verticalement dans la zone B de la marge
    // gauche (issues #33, #186 puis #195). De haut en bas : haut → gauche →
    // droite → bas (ordre DOM). Le JS insère chaque fiche dans le slot désigné
    // par sa position (calculée côté Python), de sorte que la lecture de haut en
    // bas suive l'ordre de jeu, l'humain de référence restant en bas.
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
    // Sélecteur de lettre du joker (issues #168/#201). Popover en position fixe,
    // masqué tant qu'aucun joker n'est en cours de pose ; ouvrirSelecteurJoker() le
    // révèle et le place DIRECTEMENT sur la case du plateau où le joker est posé
    // (issue #201), au lieu de l'ancrer à un bouton de la marge gauche étroite où
    // la grille des 26 lettres était tronquée. Plus de bouton d'ancrage.
    const jokerPopover = document.getElementById('joker-popover');
    const jokerGrille = document.getElementById('joker-grille');
    const jokerAnnuler = document.getElementById('joker-annuler');
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

    // Actions de tour (issue #101, réorganisées issue #160) : rapatriées depuis la
    // fenêtre chevalet, désormais réparties de part et d'autre de la fiche du joueur
    // humain (gauche : échange + passer ; droite : annuler + vérifier + jouer). Les
    // deux zones ne sont visibles/actives que pendant le tour du joueur humain (voir
    // majActionsTour). Le message de retour dédié (#message-coup) est rattaché à la
    // SECTION parente, hors des zones masquées (issue #243), pour rester visible même
    // pendant le tour de l'ordinateur ; il s'affiche en surimpression au-dessus des
    // boutons, distinct du message éphémère de pose (#message-plateau). L'ancien cadre d'attente d'un tour d'ordinateur
    // (#zone-attente-ia et son message) est supprimé (issue #160) : le tour d'un
    // ordinateur se déclenche via le bouton « ▶ Jouer » de sa fiche (issue #149).
    const zoneActionsGauche = document.getElementById('zone-actions-gauche');
    const zoneActionsDroite = document.getElementById('zone-actions-droite');
    const btnValider = document.getElementById('btn-valider');
    const btnVerifierCoup = document.getElementById('btn-verifier-coup');
    // Bouton « Jouer » embarqué dans la modale « Vérifier et calculer » (issue
    // #225) : ferme la modale et pose le coup en un seul clic.
    const btnScoreJouer = document.getElementById('score-jouer');
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
        // surbrillance .derniere-pose n'a jamais été touchée), issue #128. On
        // remasque aussi le « Jouer » embarqué (issue #225) : il n'a de sens que
        // pour un coup en attente et ne doit pas réapparaître en consultation
        // d'historique.
        auFermer: () => {
            retirerSurbrillanceCoupConsulte();
            if (btnScoreJouer) btnScoreJouer.hidden = true;
        },
        // Clic « dehors » sur le calque de la modale (issue #228, suite de #225).
        // Ce calque plein écran (z-index 100) recouvre le bandeau d'actions : un
        // clic sur le bouton « Jouer » principal (#btn-valider) est alors capté
        // ici comme un clic dehors et ne faisait que fermer la modale, imposant
        // un second clic pour poser réellement le coup. Si le clic tombe sur le
        // rectangle de #btn-valider et qu'un coup est en attente (bouton actif),
        // on pose le coup en un seul clic ; jouerCoup() referme lui-même la
        // modale. Sinon on renvoie false : fermeture simple habituelle.
        surClicDehors: (evt) => {
            if (btnValider.disabled) return false;
            const r = btnValider.getBoundingClientRect();
            const surBouton = evt.clientX >= r.left && evt.clientX <= r.right
                && evt.clientY >= r.top && evt.clientY <= r.bottom;
            if (!surBouton) return false;
            jouerCoup();
            return true;
        },
    });

    // Thèmes reconnus (alignés avec scrabble.config.THEMES_PLATEAU et le CSS).
    const THEMES = C.THEMES;

    // --- État courant côté vue ---
    // Dernier payload public reçu de Python (état de la partie + pose en cours).
    let etat = null;
    // Placements en attente déjà posés sur le plateau (copie locale du payload,
    // pour le rendu et pour savoir si « Retour au menu » doit avertir).
    let enAttente = [];
    // Jeu de libellés affichés dans les cases.
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

    /** Empile les fiches joueurs dans le slot assigné (ordre de jeu, issue #195). */
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

            // Célébration (issue #227) : feu d'artifice de victoire UNIQUEMENT si
            // le joueur humain de référence figure parmi les gagnants (victoire ou
            // ex æquo). On ne fête pas une partie perdue par l'humain. Déclenché
            // ici, dans l'ouverture unique, pour ne jouer qu'une seule fois.
            const humainGagne = Array.isArray(gagnants) && gagnants.length
                && (joueurs || []).some((j) => j.humain && gagnants.includes(j.nom));
            if (humainGagne) {
                celebrerVictoire();
            }
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

    /** Bascule interactif / attente (tour d'un ordinateur), issue #35/#90.
     *  L'ancien cadre d'attente d'un tour d'ordinateur a été supprimé (issue #160) : pendant le
     *  tour d'un ordinateur, majActionsTour masque simplement les deux zones
     *  d'actions, et le coup se déclenche via le bouton « ▶ Jouer » de la fiche de
     *  l'ordinateur courant (issue #149). */
    function majModeTour() {
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
        // Les deux zones d'actions (gauche/droite) apparaissent/disparaissent
        // ensemble, uniquement pendant le tour du joueur humain (issue #160).
        zoneActionsGauche.hidden = !tourHumain;
        zoneActionsDroite.hidden = !tourHumain;
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
    let messageCoupTimer = null;
    function afficherMessageCoup(texte, type, dureeMs) {
        if (messageCoupTimer) {
            clearTimeout(messageCoupTimer);
            messageCoupTimer = null;
        }
        messageCoup.textContent = texte || '';
        messageCoup.className = 'message-coup' + (texte ? ' ' + (type || 'info') : '');
        // Auto-effacement optionnel (issue #226) : le message « Coup joué » est posé
        // APRÈS le rendu déclenché par le push d'état (qui, passé au tour de
        // l'ordinateur, a déjà vidé la zone via majActionsTour). Plus aucun rendu ne
        // survient ensuite tant qu'aucun bouton n'est cliqué, si bien que le message
        // resterait affiché indéfiniment. On le fait disparaître de lui-même, comme
        // le toast « +N points » du joueur humain (3 s, cf. afficherToastPoints).
        if (texte && dureeMs) {
            messageCoupTimer = setTimeout(() => {
                messageCoup.textContent = '';
                messageCoup.className = 'message-coup';
                messageCoupTimer = null;
            }, dureeMs);
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
    // Sélecteur de lettre du joker (issue #168)
    // ------------------------------------------------------------------ //

    // Garde de réentrance : un seul sélecteur de joker ouvert à la fois (Python
    // ne demande qu'un choix à la fois, mais on se protège d'un double push).
    let jokerSelecteurOuvert = false;

    /**
     * Place le popover du sélecteur de joker directement sur/à côté de la case du
     * plateau ``caseEl`` (issue #201). Le popover est en ``position: fixed`` : on
     * lui pose des coordonnées viewport (centré sous la case, remonté au-dessus
     * si la place manque en bas), puis on le recadre dans la fenêtre — même
     * technique que les toasts de score (issue #198) — pour qu'il ne déborde
     * jamais du plateau ni de l'écran, quelle que soit la position de la case
     * (coin, bord). La grille des 26 lettres étant déjà rendue au moment de
     * l'appel, ``getBoundingClientRect`` renvoie ses dimensions réelles.
     */
    function positionnerPopoverJoker(caseEl) {
        const marge = 8;
        const popRect = jokerPopover.getBoundingClientRect();
        // Case introuvable (ne devrait pas arriver) : repli centré à l'écran.
        if (!caseEl) {
            jokerPopover.style.left =
                `${Math.max(marge, (window.innerWidth - popRect.width) / 2)}px`;
            jokerPopover.style.top =
                `${Math.max(marge, (window.innerHeight - popRect.height) / 2)}px`;
            return;
        }
        const caseRect = caseEl.getBoundingClientRect();
        // Idéal : popover centré horizontalement sur la case, juste en dessous.
        let left = caseRect.left + caseRect.width / 2 - popRect.width / 2;
        let top = caseRect.bottom + marge;
        // Pas la place en dessous : on tente au-dessus de la case (sinon on
        // laissera le recadrage viewport ci-après le maintenir visible).
        if (top + popRect.height > window.innerHeight - marge) {
            const dessus = caseRect.top - marge - popRect.height;
            if (dessus >= marge) {
                top = dessus;
            }
        }
        // Recadrage final dans le viewport (issue #198) : jamais hors des bords.
        left = Math.min(left, window.innerWidth - marge - popRect.width);
        left = Math.max(left, marge);
        top = Math.min(top, window.innerHeight - marge - popRect.height);
        top = Math.max(top, marge);
        jokerPopover.style.left = `${left}px`;
        jokerPopover.style.top = `${top}px`;
    }

    /**
     * Ouvre le sélecteur de lettre du joker : popover en surimpression posé
     * DIRECTEMENT sur la case du plateau où le joker vient d'être posé (issue
     * #201), au lieu d'un menu déroulant ancré dans la marge gauche étroite où la
     * grille des 26 lettres était tronquée (issue #168). Ce nouvel emplacement,
     * sur le plateau bien plus large que la marge, affiche l'alphabet complet sans
     * troncature et évite les allers-retours de souris marge ⇄ plateau.
     *
     * ``demande`` = {ligne, colonne, index} renvoyé par Python dans la réponse
     * ``joker_requis`` (au clic sur une case avec un joker sélectionné). La
     * confidentialité est préservée : ``index`` est une simple position de
     * chevalet — déjà connue de cette fenêtre puisque Python la lui renvoie — et
     * jamais la lettre ; ``ligne``/``colonne`` désignent la case déjà cliquée. À
     * la sélection, on finalise la pose par le MÊME appel API qu'auparavant
     * (``poser_lettre_en_attente(l, c, lettre, true, 0, index)``) ; à l'abandon,
     * on relâche la sélection (``selectionner_lettre(null)``), le joker
     * redevenant disponible au chevalet — contrat métier inchangé (issue #201).
     */
    async function ouvrirSelecteurJoker(demande) {
        if (jokerSelecteurOuvert) {
            return;
        }
        jokerSelecteurOuvert = true;
        // Referme d'abord les autres popovers de la barre (« Derniers coups » /
        // « Vérification dictionnaire ») pour ne pas empiler deux surimpressions.
        C.fermerTousPopovers();
        // Case du plateau visée : le popover s'ouvre dessus (issue #201).
        const caseEl = plateauEl.querySelector(
            `.case[data-ligne="${demande.ligne}"][data-colonne="${demande.colonne}"]`);
        let choix = null;
        try {
            // La grille des 26 lettres est construite de façon SYNCHRONE par
            // choisirLettreJoker (rendu immédiat, popover visible) : on peut le
            // placer sur la case dès le retour de l'appel, avant peinture, sans
            // aucun flash à sa position par défaut.
            const promesse = C.choisirLettreJoker({
                modale: jokerPopover, grille: jokerGrille, annuler: jokerAnnuler,
                popover: true,
            });
            positionnerPopoverJoker(caseEl);
            choix = await promesse;
        } finally {
            jokerSelecteurOuvert = false;
            jokerPopover.hidden = true;
        }
        if (choix) {
            try {
                await api.poser_lettre_en_attente(
                    demande.ligne, demande.colonne, choix, true, 0, demande.index);
                afficherMessagePlateau('');
            } catch (err) {
                afficherMessagePlateau('Erreur lors de la pose du joker.', 'erreur');
            }
        } else {
            // Abandon (Annuler, clic extérieur ou Échap) : on relâche la sélection.
            try {
                await api.selectionner_lettre(null);
            } catch (err) {
                /* best-effort : l'abandon ne doit jamais planter le jeu */
            }
            afficherMessagePlateau('');
        }
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

    // ================================================================== //
    // Chevalet du joueur humain de référence (migré en zone C, issue #187)
    // ================================================================== //
    // Le panneau des 9 cases (7 lettres + 2 vides) et toute sa logique vivaient
    // jusqu'ici dans une fenêtre pywebview flottante séparée (chevalet.js,
    // supprimée). Ils sont désormais RELOCALISÉS dans ce document, en zone C de la
    // marge gauche. Les appels API (``api.selectionner_lettre`` /
    // ``basculer_echange`` / ``obtenir_etat_chevalet``) sont ceux de la MÊME
    // instance ``ApiJeu`` que le reste de jeu.js utilise déjà : aucune nouvelle
    // méthode API n'est requise. La logique de sélection/réarrangement travaille
    // sur des index d'un tableau plat (``panneauLettres``), indépendante de la
    // disposition visuelle — le passage d'un flex horizontal à une grille 3×3
    // (voir jeu.css) n'y change rien. La seule mécanique NON migrée est le drag de
    // la fenêtre flottante (``.barre-drag`` / ``deplacer_chevalet``) : sans fenêtre
    // à déplacer, elle est sans objet.
    //
    // Confidentialité (issues #33/#35, #99) — À NOTER : les lettres PRIVÉES du
    // chevalet (``etatChevalet.lettres``) et l'état PUBLIC du plateau (``etat``)
    // co-résident maintenant dans le même document JS. Ce n'est PAS une fuite :
    // Python (``ApiJeu._etat_chevalet``) ne sérialise toujours que les lettres du
    // seul joueur humain de référence, jamais celles d'un ordinateur ni d'un autre
    // humain — exactement comme quand le chevalet avait sa propre fenêtre. La
    // garantie de l'issue #99 est donc inchangée ; seule la localisation du DOM
    // change.
    const panneauEl = document.getElementById('panneau');

    // Dernier payload chevalet reçu de Python (état privé du joueur de référence).
    // Distinct de ``etat`` (état public du plateau) : ne jamais les confondre.
    let etatChevalet = null;
    let dernierMonTour = null;       // pour détecter un changement de tour (issue #100)
    let panneauSignature = null;     // signature des lettres pour (re)bâtir le panneau
    let panneauLettres = [];         // {lettre, valeur, joker, indexOrigine} + 2 vides (null)
    let panneauSelection = null;     // index (dans panneauLettres) de la case sélectionnée

    /** Ensemble des index d'origine déjà posés en attente (cases « utilisées »). */
    function indexUtilises() {
        return new Set(
            (etatChevalet && etatChevalet.en_attente ? etatChevalet.en_attente : [])
                .map((p) => p.index));
    }

    /** Vrai si le mode de marquage pour l'échange partiel est actif (issue #138). */
    function enModeEchange() {
        return Boolean(etatChevalet && etatChevalet.mode_echange);
    }

    /** Ensemble des index d'origine marqués pour l'échange partiel (issue #138). */
    function indexEchange() {
        return new Set(
            (etatChevalet && Array.isArray(etatChevalet.selection_echange))
                ? etatChevalet.selection_echange : []);
    }

    function rendrePanneau() {
        if (!panneauEl) {
            return;
        }
        panneauEl.innerHTML = '';
        if (panneauLettres.length === 0) {
            panneauEl.innerHTML = '<span class="panneau-vide">Chevalet vide.</span>';
            return;
        }
        const utilises = indexUtilises();
        const echange = indexEchange();
        const modeEchange = enModeEchange();
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
            if (modeEchange) {
                // Marquage d'échange partiel (issue #138) : surbrillance distincte
                // de la sélection de pose ; les lettres déjà posées ne comptent pas.
                if (!utilises.has(l.indexOrigine) && echange.has(l.indexOrigine)) {
                    c.classList.add('a-echanger');
                }
            } else if (utilises.has(l.indexOrigine)) {
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

    /** Signature des lettres du chevalet (pour ne rebâtir le panneau qu'utile). */
    function signatureLettres(lettres) {
        return (lettres || []).map((l) => (l.joker ? '*' : l.lettre) + l.valeur).join(',');
    }

    /** (Re)construit le panneau à partir des lettres du chevalet. Chaque lettre
     *  garde son ``indexOrigine`` (position dans ``etatChevalet.lettres``) pour que
     *  la sélection Python vise la bonne lettre même après un réarrangement local
     *  (point critique du rapport #98). Deux emplacements vides sont ajoutés pour
     *  la réflexion. */
    function reconstruirePanneau() {
        const lettres = etatChevalet.lettres || [];
        panneauLettres = lettres.map((l, i) => ({ ...l, indexOrigine: i }));
        if (panneauLettres.length > 0) {
            panneauLettres.push(null, null);
        }
        panneauSelection = null;
    }

    /**
     * Applique un état PRIVÉ du chevalet (lettres du joueur de référence). Poussé
     * par Python via ``window.appliquerEtatChevalet`` après toute mutation, ou
     * obtenu au premier chargement via ``obtenir_etat_chevalet`` (issue #90,
     * contrat #99/#100). Le choix de la lettre d'un joker reste piloté par le menu
     * déroulant du plateau (issue #168) : rien à faire ici.
     */
    function appliquerEtatChevalet(payload) {
        etatChevalet = payload || {};

        // Changement de tour (issue #100) : ``index_reference`` étant constant pour
        // toute la partie, on détecte le changement via ``mon_tour`` (bascule). Un
        // nouveau tour repart d'un panneau neuf (réarrangement local abandonné).
        const nouveauTour = etatChevalet.mon_tour !== dernierMonTour;
        dernierMonTour = etatChevalet.mon_tour;
        if (nouveauTour) {
            panneauSignature = null;
        }

        // Le panneau n'est reconstruit qu'au changement de tour ou de contenu du
        // chevalet (échange / nouveau tirage), pas à chaque pose (les lettres ne
        // changent pas en posant).
        const sig = signatureLettres(etatChevalet.lettres);
        if (sig !== panneauSignature) {
            reconstruirePanneau();
            panneauSignature = sig;
        }

        // Toute pose/annulation remet la sélection Python à null : on aligne la
        // sélection visuelle locale du panneau dessus.
        if (etatChevalet.selection === null || etatChevalet.selection === undefined) {
            panneauSelection = null;
        }

        rendrePanneau();
    }
    window.appliquerEtatChevalet = appliquerEtatChevalet;

    // Clic sur une case du panneau : sémantique unifiée (issue #100).
    //  - 1er clic sur une lettre : sélection côté Python (api.selectionner_lettre)
    //    en visant son index d'origine (robuste au réarrangement local).
    //  - clic suivant sur une case du PLATEAU : pose (gérée plus haut dans jeu.js).
    //  - clic suivant sur une autre case du panneau : réarrangement local
    //    (déplacement vers un vide ou échange), et annulation de la sélection Python.
    if (panneauEl) {
        panneauEl.addEventListener('click', async (evt) => {
            const caseEl = evt.target.closest('.panneau-case, .panneau-case-vide');
            if (!caseEl) {
                return;
            }
            const index = Number(caseEl.dataset.index);
            const lettre = panneauLettres[index];
            const estVide = lettre === null;
            // Une lettre déjà posée n'est ni sélectionnable ni cible d'échange.
            const estUtilisee = !estVide && indexUtilises().has(lettre.indexOrigine);

            // Mode échange partiel (issue #138) : le clic marque/démarque la lettre
            // pour l'échange (sélection multiple), sans toucher à la pose. Aucun
            // réarrangement local dans ce mode : l'unique action est le marquage.
            if (enModeEchange()) {
                if (estVide) {
                    return;
                }
                await api.basculer_echange(lettre.indexOrigine);
                return;
            }

            if (panneauSelection === null) {
                if (estVide || estUtilisee) {
                    return;
                }
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
            // En mode échange partiel (issue #138), le panneau ne sert qu'au
            // marquage : pas de réarrangement local par clic droit.
            if (enModeEchange()) {
                return;
            }
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
    }

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
        // Un nouveau coup en tête d'historique = une action de tour vient d'être
        // appliquée (pose, échange ou passage), y compris déclenchée depuis la
        // fenêtre chevalet. On referme alors les popovers du plateau restés ouverts
        // (« Derniers coups », « Vérification dictionnaire ») : c'est ce signal
        // applicatif qui pallie l'absence de clic extérieur cross-fenêtre (issue #151).
        C.fermerTousPopovers();
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
     *    (dans la fenêtre chevalet) et, s'il s'agit d'un joker, renvoie
     *    ``joker_requis`` — on ouvre alors le sélecteur de lettre du joker, menu
     *    déroulant de CETTE fenêtre plateau (issue #168). La confidentialité est
     *    respectée : cette fenêtre ne connaît jamais la lettre du chevalet, elle ne
     *    transmet que la case visée et reçoit en retour l'``index`` (position) de la
     *    lettre à finaliser, jamais son identité.
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
        //    sélectionné, le sélecteur de lettre s'ouvre ici même (menu déroulant du
        //    plateau, issue #168 ; joker_requis).
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
                // Joker : le choix de la lettre se fait dans le menu déroulant du
                // plateau (issue #168), plus dans la fenêtre chevalet.
                ouvrirSelecteurJoker(
                    { ligne: res.ligne, colonne: res.colonne, index: res.index });
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
            // Joker : ouverture du sélecteur de lettre (menu déroulant du plateau,
            // issue #168) au lieu d'un renvoi vers la fenêtre chevalet.
            ouvrirSelecteurJoker(
                { ligne: res.ligne, colonne: res.colonne, index: res.index });
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
            // Ce fichier est PARTAGÉ par deux coquilles ; on choisit le retour
            // dynamiquement, sans dupliquer le fichier ni casser la production :
            //  - Coquille UNIFIÉE (issues #179/#181) : `api.retourner_accueil()`,
            //    méthode de contrôle du routeur (ABSENTE de l'ApiJeu de
            //    production) qui masque le chevalet, réinitialise l'accueil et
            //    navigue par `load_url` dans la MÊME fenêtre.
            //  - PRODUCTION (`lancer_jeu`) : `api.retour_menu()` détruit les deux
            //    fenêtres ; la boucle rend la main et l'accueil se rouvre.
            res = (typeof api.retourner_accueil === 'function')
                ? await api.retourner_accueil()
                : await api.retour_menu();
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
        // Succès : coquille unifiée → navigation vers accueil.html ; production →
        // les DEUX fenêtres se ferment et l'accueil se rouvre.
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
            // Détection dynamique de la coquille (cf. `retournerAuMenu`) :
            //  - UNIFIÉE : `api.recommencer_jeu()` (routeur) crée la nouvelle
            //    partie et recharge `jeu.html` dans la MÊME fenêtre.
            //  - PRODUCTION : `api.recommencer()` détruit les fenêtres et la
            //    récursion `lancer_jeu` rouvre l'écran de jeu.
            res = (typeof api.recommencer_jeu === 'function')
                ? await api.recommencer_jeu()
                : await api.recommencer();
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
                // Coup validé et en attente : on propose de le poser directement
                // depuis la modale (issue #225), sans repasser par le bouton
                // « Jouer » principal masqué derrière le calque de la modale.
                if (btnScoreJouer) btnScoreJouer.hidden = false;
            }
        } else {
            afficherMessageCoup((res && res.erreur) ? res.erreur : 'Coup invalide.', 'erreur');
        }
        majActionsTour();
    });

    // Jouer : pose le mot formé par les lettres en attente (lues côté Python).
    // Factorisé (issue #225) car deux boutons y mènent désormais : le « Jouer »
    // principal (#btn-valider) et le « Jouer » de la modale « Vérifier et calculer »
    // (#score-jouer). On ferme d'abord la modale de score si elle est encore
    // ouverte : un seul clic suffit alors à poser le coup, sans le double clic
    // (fermer la modale, puis cliquer Jouer) qui déroutait les joueuses.
    async function jouerCoup() {
        modaleScore.fermer();
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
            afficherMessageCoup(`Coup joué (+${points} point${points > 1 ? 's' : ''}).`, 'succes', 3000);
            // Python rediffuse l'état (nouveau tour) : le rendu suit via le push.
        } else {
            afficherMessageCoup((res && res.erreur) ? res.erreur : 'Coup refusé.', 'erreur');
            majActionsTour();
        }
    }
    btnValider.addEventListener('click', jouerCoup);
    if (btnScoreJouer) {
        btnScoreJouer.addEventListener('click', jouerCoup);
    }

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
            // Auto-effacement (issue #243, cohérent avec #226) : le message est posé
            // APRÈS le push d'état (passé au tour de l'ordinateur, majActionsTour a
            // masqué les boutons et vidé la zone). Sans minuterie il resterait figé
            // jusqu'au prochain clic. Il vit désormais hors du conteneur masqué
            // (#message-coup remonté sur la section, cf. jeu.html) : il est donc
            // visible immédiatement, puis disparaît de lui-même.
            afficherMessageCoup('Tour passé.', 'succes', 4000);
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
            // Idem « Tour passé » : visible tout de suite (message hors du conteneur
            // masqué) puis auto-effacé (issue #243).
            afficherMessageCoup('Toutes vos lettres ont été remises dans le sac. Tour passé.', 'succes', 4000);
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
            // Idem « Tour passé » : visible tout de suite (message hors du conteneur
            // masqué) puis auto-effacé (issue #243).
            afficherMessageCoup('Lettres échangées. Tour passé.', 'succes', 4000);
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
    // Remet le popover de vérification à zéro (issue #196) : champ vidé, verdict
    // et définition effacés, pour qu'une réouverture démarre sur un champ vierge
    // prêt à recevoir une nouvelle recherche (plus besoin d'effacer à la main).
    function reinitialiserVerifDictionnaire() {
        champVerif.value = '';
        afficherMessageBrouillon('');
        masquerDefinitionBrouillon();
    }

    // Popover replié (issue #86) : au clic, focus sur le champ ; à la fermeture,
    // on efface la recherche précédente (issue #196).
    C.configurerPopover(
        btnOuvrirVerif, verifPopover,
        () => { champVerif.focus(); },
        reinitialiserVerifDictionnaire,
    );

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
                    // Surbrillance bleue temporaire (issue #197) : teinte bleue à
                    // l'instant de la pose, estompée vers la couleur d'origine sur
                    // ~5 s par l'animation CSS ``pose-fraiche-fondu`` (fond de tuile).
                    // On retire la classe à la fin du fondu pour laisser la case dans
                    // son état normal. Indépendant du nombre de lettres du coup : même
                    // une pose d'une seule lettre reste nettement repérable.
                    caseEl.classList.add('case-pose-fraiche');
                    setTimeout(
                        () => caseEl.classList.remove('case-pose-fraiche'),
                        5000
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
     * Célébration de FIN DE PARTIE gagnée par le joueur humain (issue #227) :
     * un feu d'artifice volontairement plus long et plus fourni que celui d'un
     * Scrabble (``celebrerScrabble``). Là où le Scrabble tire ~32 particules en
     * une seule salve centrale de ~1,6 s, la victoire enchaîne plusieurs SALVES
     * (``NB_SALVES``) réparties sur ~5 s, chacune jaillissant d'un point différent
     * de l'écran avec son propre éclair (flash) et une pluie de particules aux
     * formes (carrés/ronds) et couleurs variées, avec retombée gravitaire.
     *
     * Le calque ``#victoire-fete`` est plein écran, AU-DESSUS de la modale de fin,
     * mais toujours ``pointer-events: none`` : les particules décorent l'écran
     * sans jamais masquer durablement ni bloquer le score final et les boutons.
     * En mouvement réduit, seul le toast statique « 🏆 Victoire ! » est affiché.
     */
    function celebrerVictoire() {
        const calque = document.getElementById('victoire-fete');
        if (!calque) {
            return;
        }
        calque.innerHTML = '';
        const reduit = window.matchMedia
            && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        const toast = document.createElement('div');
        toast.className = 'victoire-toast';
        toast.textContent = '🏆 Victoire ! Bravo 🎉';
        calque.appendChild(toast);

        if (reduit) {
            setTimeout(() => { calque.innerHTML = ''; }, 4000);
            return;
        }

        // Palette plus riche que celle du Scrabble (6 teintes) : on ajoute or,
        // orange, rose, cyan, magenta, lime et blanc pour un rendu festif varié.
        const couleurs = [
            '#2e7d32', '#1565c0', '#6a1b9a', '#ffd54f', '#ef6d86', '#d21f24',
            '#ff8f00', '#00bcd4', '#e91e63', '#8bc34a', '#ffffff', '#ffca28',
        ];
        const NB_SALVES = 9;         // nombre de salves successives
        const INTERVALLE = 550;      // ms entre deux salves
        const DUREE_PARTICULE = 1800; // durée d'animation d'une particule (ms)

        // Lance une salve : un éclair central + une gerbe de particules radiales,
        // à une position (ox, oy) exprimée en pourcentage du viewport. On évite les
        // bords extrêmes et on privilégie la moitié haute pour un effet « ciel ».
        function lancerSalve() {
            if (!document.body.contains(calque)) {
                return;
            }
            const ox = 12 + Math.random() * 76;   // 12 %..88 % en largeur
            const oy = 14 + Math.random() * 46;   // 14 %..60 % en hauteur
            const base = couleurs[Math.floor(Math.random() * couleurs.length)];

            const flash = document.createElement('div');
            flash.className = 'eclat-flash';
            flash.style.left = `${ox}%`;
            flash.style.top = `${oy}%`;
            flash.style.setProperty('--col', base);
            calque.appendChild(flash);
            setTimeout(() => flash.remove(), 700);

            const nb = 26 + Math.floor(Math.random() * 12); // 26..37 particules
            for (let i = 0; i < nb; i += 1) {
                const p = document.createElement('div');
                p.className = 'particule-victoire';
                if (Math.random() < 0.45) {
                    p.classList.add('etincelle-ronde');
                }
                const angle = Math.random() * Math.PI * 2;
                const distance = 90 + Math.random() * 160;
                const dx = Math.cos(angle) * distance;
                const dy = Math.sin(angle) * distance;
                p.style.left = `${ox}%`;
                p.style.top = `${oy}%`;
                p.style.setProperty('--dx', `${Math.round(dx)}px`);
                p.style.setProperty('--dy', `${Math.round(dy)}px`);
                // Retombée gravitaire (chute verticale supplémentaire).
                p.style.setProperty('--chute', `${60 + Math.round(Math.random() * 100)}px`);
                p.style.setProperty('--rot', `${Math.round((Math.random() - 0.5) * 720)}deg`);
                p.style.setProperty('--col', couleurs[Math.floor(Math.random() * couleurs.length)]);
                calque.appendChild(p);
                // Retrait individuel après l'animation pour éviter l'accumulation
                // de nœuds pendant les ~5 s de célébration.
                setTimeout(() => p.remove(), DUREE_PARTICULE + 200);
            }
        }

        lancerSalve();
        let salves = 1;
        const minuteur = setInterval(() => {
            lancerSalve();
            salves += 1;
            if (salves >= NB_SALVES) {
                clearInterval(minuteur);
            }
        }, INTERVALLE);

        // Nettoyage final : après la dernière salve et le temps qu'elle s'éteigne.
        const dureeTotale = NB_SALVES * INTERVALLE + DUREE_PARTICULE + 400;
        setTimeout(() => { calque.innerHTML = ''; }, dureeTotale);
    }

    /**
     * Toast éphémère « +X points » (issue #136) affiché ~3 s près de la fiche du
     * joueur qui vient de jouer, pour tout coup rapportant des points (humain ou
     * ordinateur, quel que soit le nombre de mots formés : X est le score TOTAL
     * du coup). Injecté dans le calque plein écran ``#points-toasts`` (toujours
     * ``pointer-events: none``), indépendant du toast Scrabble centré : les deux
     * peuvent coexister sans fusion, chacun suivant son propre cycle.
     *
     * Positionnement (issue #198) : depuis la refonte en 4 zones (#186), les
     * fiches ne sont plus disposées en croix autour du plateau mais empilées
     * verticalement dans la marge gauche (zone B) ; l'ancien calcul, qui poussait
     * le toast vers l'« intérieur du plateau » selon la position logique du
     * panneau (haut/bas/gauche/droite), envoyait donc les toasts hors écran
     * (notamment vers la gauche pour un panneau « droite »). On ancre désormais le
     * toast juste à droite de la fiche réelle, pointant vers le plateau (qui
     * domine la colonne droite), avec un recadrage final dans le viewport pour
     * qu'il reste toujours visible quelle que soit la géométrie.
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
        // On ancre le toast sur la fiche entière (bord droit) plutôt que sur le
        // seul avatar : dans la marge gauche étroite, cela place le bandeau juste
        // à côté de la fiche, dans la zone du plateau, sans recouvrir le nom ni le
        // score du joueur.
        const ancre = slot ? slot.querySelector('.panneau-joueur') : null;

        // Placement (wrapper) et animation (toast interne) sont séparés : le
        // wrapper porte la transformation de recentrage face à la fiche, le toast
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
            const cy = r.top + r.height / 2;
            // Les fiches sont toutes empilées dans la marge gauche : le toast
            // pointe vers la droite, dans la zone du plateau, quel que soit le
            // « côté » logique du panneau.
            wrapper.style.left = `${r.right + gap}px`;
            wrapper.style.top = `${cy}px`;
            wrapper.style.transform = 'translate(0, -50%)';
        } else {
            // Aucune fiche trouvée : repli discret en bas-centre du calque.
            const c = calque.getBoundingClientRect();
            wrapper.style.left = `${c.left + c.width / 2}px`;
            wrapper.style.top = `${c.top + c.height * 0.82}px`;
            wrapper.style.transform = 'translate(-50%, -50%)';
        }

        calque.appendChild(wrapper);
        // Recadrage final dans le viewport : après ajout, on mesure le toast rendu
        // (le wrapper a une transformation de recentrage) et on translate le
        // wrapper pour que le bandeau ne dépasse jamais d'un bord, garantissant
        // qu'il reste toujours visible (issue #198).
        const marge = 8;
        const rect = toast.getBoundingClientRect();
        let dx = 0;
        let dy = 0;
        if (rect.right > window.innerWidth - marge) {
            dx = (window.innerWidth - marge) - rect.right;
        }
        if (rect.left + dx < marge) {
            dx = marge - rect.left;
        }
        if (rect.bottom > window.innerHeight - marge) {
            dy = (window.innerHeight - marge) - rect.bottom;
        }
        if (rect.top + dy < marge) {
            dy = marge - rect.top;
        }
        if (dx || dy) {
            wrapper.style.left = `${parseFloat(wrapper.style.left) + dx}px`;
            wrapper.style.top = `${parseFloat(wrapper.style.top) + dy}px`;
        }
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
        labelVisible = (theme === 'abrege') ? C.LABEL_ABREGE : C.LABEL_COMPLET;
        THEMES.forEach((t) => plateauEl.classList.remove(`theme-${t}`));
        plateauEl.classList.add(`theme-${theme}`);
    }

    // ------------------------------------------------------------------ //
    // Diagnostic : espace vertical réel sous le plateau (issue #152)
    // ------------------------------------------------------------------ //

    // Hauteur minimale de la fenêtre chevalet (issue #140/#141) : c'est la place
    // qu'il faut pouvoir loger sous le plateau, sans qu'elle empiète, une fois le
    // chevalet posé en bas de l'écran.
    const CHEVALET_MIN_PX = 175;

    /**
     * Mesure et journalise la géométrie verticale réelle de l'écran de jeu
     * (issue #152), sur le modèle de la trace de tirage (#116) et de la modale du
     * joker (#140). Objective la régression « moins d'espace sous le plateau » :
     * hauteur totale de la fenêtre, bas réel du plateau, et espace restant en
     * dessous — pour vérifier qu'il reste au moins la hauteur d'un chevalet
     * (CHEVALET_MIN_PX). La mesure est différée de deux requestAnimationFrame pour
     * laisser WebKitGTK poser la mise en page avant lecture. Best-effort : toute
     * erreur (API absente en test, DOM incomplet) est silencieusement ignorée, la
     * trace ne doit jamais gêner le jeu.
     */
    function journaliserGeometriePlateau() {
        try {
            if (!api || typeof api.journaliser_mesure_fenetre !== 'function') return;
            const rect = plateauEl.getBoundingClientRect();
            const hauteurFenetre = window.innerHeight;
            const arrondi = (v) => Math.round(v);
            const espaceSous = arrondi(hauteurFenetre - rect.bottom);
            api.journaliser_mesure_fenetre({
                fenetre_hauteur: hauteurFenetre,
                fenetre_largeur: window.innerWidth,
                plateau_haut: arrondi(rect.top),
                plateau_bas: arrondi(rect.bottom),
                plateau_hauteur: arrondi(rect.height),
                espace_sous_plateau: espaceSous,
                chevalet_min: CHEVALET_MIN_PX,
                espace_suffisant: espaceSous >= CHEVALET_MIN_PX,
            });
        } catch (_e) {
            /* trace best-effort : on ignore toute erreur */
        }
    }

    // ------------------------------------------------------------------ //
    // Tirage de l'ordre de jeu (issue #170)
    // ------------------------------------------------------------------ //
    // Au tout début d'une NOUVELLE partie, Python expose le détail du tirage via
    // api.obtenir_tirage_ordre(). Tant que l'ordre n'est pas déterminé, l'écran
    // de tirage occupe la fenêtre à la place du plateau, des fiches ET de la
    // barre globale (masqués par body.tirage-en-cours, voir jeu.css) ; la fenêtre
    // chevalet a été créée masquée côté Python. Le flux est repris de l'ex-modale
    // de l'accueil (issues #54/#61/#166). En reprise de partie, obtenir_tirage_
    // ordre() renvoie null : on saute directement à l'affichage du plateau.
    const ecranTirage = document.getElementById('ecran-tirage');
    const tirageLettres = document.getElementById('tirage-lettres');
    const tirageOrdreResultat = document.getElementById('tirage-ordre-resultat');
    const tirageSacZone = document.getElementById('tirage-sac-zone');
    const tirageSacAction = document.getElementById('tirage-sac-action');
    const btnContinuerTirage = document.getElementById('btn-continuer-tirage');
    const btnAnnulerTirage = document.getElementById('btn-annuler-tirage');

    const DELAI_LIGNE = 450;  // ms entre deux révélations de lettre
    const attendreTirage = (ms) => new Promise((r) => setTimeout(r, ms));

    // Tour d'un joueur HUMAIN : sa ligne ne figure PAS dans la liste #tirage-lettres
    // (réservée aux tirages déjà terminés des ordinateurs, issue #176). On affiche
    // seulement un libellé simple « À toi de piocher une lettre » au-dessus de
    // l'image du sac + le bouton « Tirer une lettre » (issue #61, simplifié #166 ;
    // image sac.png depuis #171). Au clic, la ligne masquée rejoint la liste.
    function tourHumainTirage(li) {
        return new Promise((resolve) => {
            tirageSacZone.hidden = false;
            tirageSacZone.innerHTML = `
                <p class="tirage-sac-consigne">À toi de piocher une lettre</p>
                <img class="tirage-sac" src="images/sac.png" alt="Sac de lettres">
            `;
            tirageSacAction.hidden = false;
            tirageSacAction.innerHTML =
                '<button type="button" class="btn btn-primaire tirage-sac-bouton">Tirer une lettre</button>';
            const bouton = tirageSacAction.querySelector('.tirage-sac-bouton');
            bouton.addEventListener('click', () => {
                // La ligne du joueur humain rejoint la liste, révélée en fondu.
                li.classList.remove('tirage-humain-attente');
                li.classList.add('visible');
                tirageSacZone.hidden = true;
                tirageSacZone.innerHTML = '';
                tirageSacAction.hidden = true;
                tirageSacAction.innerHTML = '';
                resolve();
            }, { once: true });
        });
    }

    // Affiche le résultat du tirage puis attend « Continuer » (true) ou
    // « Annuler » (false). « Continuer » ne s'active qu'une fois TOUTES les
    // lettres révélées (garde issue #67).
    async function afficherTirageOrdre(tirage) {
        tirageLettres.innerHTML = '';
        tirageOrdreResultat.textContent = '';
        tirageOrdreResultat.classList.remove('visible');
        tirageSacZone.hidden = true;
        tirageSacZone.innerHTML = '';
        tirageSacAction.hidden = true;
        tirageSacAction.innerHTML = '';
        btnContinuerTirage.disabled = true;

        const lignes = tirage.tirages.map((t) => {
            const li = document.createElement('li');
            li.innerHTML = `<span class="tirage-nom">${C.escapeHtml(t.nom)}</span> a tiré <span class="tirage-lettre">${C.escapeHtml(t.lettre)}</span>`;
            // La ligne du joueur humain reste hors de la liste tant qu'il n'a pas
            // tiré : masquée (display:none) plutôt qu'affichée avec un « ? »
            // (issue #176). Elle rejoint la liste au clic sur « Tirer une lettre ».
            if (t.humain) {
                li.classList.add('tirage-humain-attente');
            }
            tirageLettres.appendChild(li);
            return li;
        });

        // « Annuler » peut résoudre à tout instant, même pendant un tour humain.
        const annulation = new Promise((resolve) => {
            btnAnnulerTirage.onclick = () => resolve(true);
        });

        const sequence = (async () => {
            for (let i = 0; i < lignes.length; i++) {
                const t = tirage.tirages[i];
                if (t.humain) {
                    await tourHumainTirage(lignes[i]);
                } else {
                    await attendreTirage(DELAI_LIGNE);
                    lignes[i].classList.add('visible');
                }
            }
            await attendreTirage(DELAI_LIGNE);
            tirageOrdreResultat.textContent =
                'Ordre de jeu : ' + tirage.ordre.map(String).join(', ');
            tirageOrdreResultat.classList.add('visible');
            btnContinuerTirage.disabled = false;
            await new Promise((resolve) => {
                btnContinuerTirage.onclick = () => resolve();
            });
            return false;  // validation normale
        })();

        const annule = await Promise.race([annulation, sequence]);
        btnContinuerTirage.onclick = null;
        btnAnnulerTirage.onclick = null;
        tirageSacZone.hidden = true;
        tirageSacZone.innerHTML = '';
        tirageSacAction.hidden = true;
        tirageSacAction.innerHTML = '';
        return !annule;
    }

    let tirage = null;
    try {
        tirage = await api.obtenir_tirage_ordre();
    } catch (err) {
        tirage = null;  // en cas d'échec, on ouvre directement le plateau
    }
    if (tirage) {
        document.body.classList.add('tirage-en-cours');
        ecranTirage.hidden = false;
        const continuer = await afficherTirageOrdre(tirage);
        if (!continuer) {
            // Annulation : Python supprime la partie et rouvre l'accueil ; plus
            // rien à initialiser côté plateau. Détection dynamique de la coquille
            // (cf. `retournerAuMenu`) :
            //  - UNIFIÉE : `api.annuler_tirage_accueil()` (routeur) supprime la
            //    partie puis navigue vers `accueil.html` dans la MÊME fenêtre.
            //  - PRODUCTION : `api.annuler_tirage()` supprime la partie et détruit
            //    les fenêtres ; l'accueil se rouvre.
            btnAnnulerTirage.disabled = true;
            btnContinuerTirage.disabled = true;
            if (typeof api.annuler_tirage_accueil === 'function') {
                await api.annuler_tirage_accueil();
            } else {
                await api.annuler_tirage();
            }
            return;
        }
        // Continuer : Python marque le tirage terminé ; on réaffiche le plateau,
        // les fiches, la barre globale et le panneau chevalet intégré (zone C).
        try {
            await api.terminer_tirage();
        } catch (err) {
            /* une erreur de fin de tirage ne doit pas bloquer le jeu */
        }
        ecranTirage.hidden = true;
        document.body.classList.remove('tirage-en-cours');
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
    // Premier tirage de l'état PRIVÉ du chevalet (issue #187, ex-chevalet.js) :
    // amorce le panneau des 9 cases dès le chargement, avant toute mutation. Le
    // premier push de Python (_diffuser) prendra le relais si l'appel échoue.
    try {
        const initialChevalet = await api.obtenir_etat_chevalet();
        appliquerEtatChevalet(initialChevalet);
    } catch (err) {
        /* le premier push de Python amorcera le chevalet si cet appel échoue */
    }

    // Révélation du plateau (issue #191). Jusqu'ici ``body.jeu-en-init`` (posée
    // en dur dans jeu.html) maintenait le plateau, les fiches et le décor cachés
    // pour éviter tout flash au lancement. Maintenant que la décision est prise
    // (écran de tirage affiché, ou plateau à afficher directement en reprise) et
    // que l'état initial est appliqué, on peut révéler l'interface. Si l'écran de
    // tirage est encore actif, ``body.tirage-en-cours`` continue seul de masquer
    // le plateau ; il ne sera visible qu'après « Continuer » (terminer_tirage).
    document.body.classList.remove('jeu-en-init');

    // Diagnostic géométrie (issue #152) : deux rAF pour lire la mise en page réelle
    // une fois le plateau rendu et posé par WebKitGTK.
    requestAnimationFrame(() => {
        requestAnimationFrame(journaliserGeometriePlateau);
    });
});
