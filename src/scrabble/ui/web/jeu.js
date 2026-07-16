/**
 * Écran de jeu - Plateau, chevalet et pose d'un mot (clic-clic)
 *
 * Communique avec l'API Python via pywebview.api.*
 *
 * Confidentialité : le chevalet du joueur courant reste masqué par défaut.
 * Il n'est révélé que sur clic explicite (« voir mes lettres ») et peut être
 * remasqué à tout moment. Chaque rafraîchissement remasque le chevalet.
 *
 * Pose d'un mot (mécanique clic-clic) : une fois le chevalet révélé, un clic
 * sur une lettre la sélectionne, un clic sur une case vide du plateau l'y place
 * (en attente, non validée). Recliquer une lettre en attente la retire. Le sens
 * du mot se déduit dès deux lettres alignées ; pour une seule, un bouton bascule
 * horizontal/vertical. Un joker demande la lettre représentée à la pose. Les
 * boutons « Valider »/« Annuler » confirment ou abandonnent la saisie ; en cas
 * d'erreur du moteur, le message est affiché sans perdre les lettres en attente.
 */

document.addEventListener('DOMContentLoaded', async () => {
    // Attendre que pywebview soit prêt
    await new Promise(resolve => {
        if (window.pywebview) {
            resolve();
        } else {
            window.addEventListener('pywebviewready', resolve);
        }
    });

    const api = window.pywebview.api;

    // Éléments du DOM
    const plateauEl = document.getElementById('plateau');
    const listeScores = document.getElementById('liste-scores');
    const sacNombre = document.getElementById('sac-nombre');
    const tourJoueur = document.getElementById('tour-joueur');
    const chevaletEl = document.getElementById('chevalet');
    const chevaletNom = document.getElementById('chevalet-nom');
    const btnVisibilite = document.getElementById('btn-visibilite');
    const btnRafraichir = document.getElementById('btn-rafraichir');

    // Contrôles de pose d'un mot (mécanique clic-clic)
    const zoneJeu = document.getElementById('zone-jeu');
    const indicateurSens = document.getElementById('indicateur-sens');
    const btnSens = document.getElementById('btn-sens');
    const btnValider = document.getElementById('btn-valider');
    const btnAnnuler = document.getElementById('btn-annuler');
    const messageCoup = document.getElementById('message-coup');

    // Modale de choix de lettre pour un joker
    const jokerModale = document.getElementById('joker-modale');
    const jokerGrille = document.getElementById('joker-grille');
    const jokerAnnuler = document.getElementById('joker-annuler');

    // Libellés des cases bonus (le TYPE de chaque case vient de Python).
    const LABEL_CASE = {
        'MT': 'Mot ×3',
        'MD': 'Mot ×2',
        'LT': 'Lettre ×3',
        'LD': 'Lettre ×2',
        'centre': '★',
        'normale': ''
    };

    // État courant côté vue
    let etat = null;
    let chevaletVisible = false;

    // État de la pose « clic-clic »
    let chevaletLettres = [];   // lettres révélées du joueur courant (ordre chevalet)
    let selection = null;       // index (dans chevaletLettres) de la lettre sélectionnée
    let enAttente = [];          // placements en cours : {ligne, colonne, lettre, joker, index}
    let sensForce = 'H';         // sens choisi quand une seule lettre est en attente

    /**
     * Échappe le HTML pour éviter les injections.
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    /**
     * Icône selon la nature du joueur (cohérent avec l'écran d'accueil).
     */
    function icone(humain) {
        return humain ? '👤' : '🖥️';
    }

    /**
     * Construit une tuile posée sur le plateau (avec sa valeur en indice).
     * ``enAttente`` marque une tuile non encore validée (style distinct).
     */
    function creerTuile(cell, enAttente = false) {
        const tuile = document.createElement('div');
        tuile.className = 'tuile'
            + (cell.joker ? ' tuile-joker' : '')
            + (enAttente ? ' tuile-attente' : '');
        tuile.textContent = cell.lettre;
        return tuile;
    }

    /**
     * Position (ligne, colonne) -> placement en attente, pour recouvrir le
     * plateau des lettres non encore validées.
     */
    function attenteEn(ligne, colonne) {
        return enAttente.find(p => p.ligne === ligne && p.colonne === colonne) || null;
    }

    /**
     * Rend le plateau à partir de l'état (grille de cases typées).
     *
     * Chaque case porte ses coordonnées (data-ligne / data-colonne) pour la
     * pose au clic. Les lettres en attente (non validées) sont dessinées
     * par-dessus les cases vides, avec un style distinct.
     */
    function rendrePlateau() {
        const plateau = etat.plateau;
        plateauEl.innerHTML = '';
        const fragment = document.createDocumentFragment();
        plateau.forEach((ligne, l) => {
            ligne.forEach((cell, c) => {
                const caseEl = document.createElement('div');
                caseEl.className = `case case-${cell.type}`;
                caseEl.title = LABEL_CASE[cell.type] || '';
                caseEl.dataset.ligne = l;
                caseEl.dataset.colonne = c;
                const attente = attenteEn(l, c);
                if (cell.lettre) {
                    // Tuile déjà posée lors d'un tour précédent (immuable).
                    caseEl.appendChild(creerTuile(cell));
                    caseEl.classList.add('occupee');
                } else if (attente) {
                    // Lettre en attente de validation (retirable au clic).
                    caseEl.appendChild(creerTuile(attente, true));
                } else if (cell.type === 'centre') {
                    caseEl.textContent = '★';
                } else {
                    caseEl.textContent = LABEL_CASE[cell.type] || '';
                }
                caseEl.setAttribute('aria-label', `Ligne ${l + 1}, colonne ${c + 1}`);
                fragment.appendChild(caseEl);
            });
        });
        plateauEl.appendChild(fragment);
    }

    /**
     * Rend la liste des scores (tous les joueurs, joueur courant mis en avant).
     */
    function rendreScores(joueurs) {
        listeScores.innerHTML = '';
        joueurs.forEach(joueur => {
            const item = document.createElement('div');
            const nature = joueur.humain ? 'humain' : 'ordinateur';
            item.className = `score-item ${nature}${joueur.courant ? ' courant' : ''}`;

            let typeLabel = joueur.humain ? 'Joueur' : 'Ordinateur';
            if (!joueur.humain && joueur.niveau) {
                const niveauLabel = {
                    'DEBUTANT': 'Débutant',
                    'FACILE': 'Facile',
                    'INTERMEDIAIRE': 'Intermédiaire',
                    'EXPERT': 'Expert'
                }[joueur.niveau] || joueur.niveau;
                typeLabel += ` (${niveauLabel})`;
            }

            item.innerHTML = `
                <span class="score-icone">${icone(joueur.humain)}</span>
                <div class="score-info">
                    <div class="score-nom">${escapeHtml(joueur.nom)}</div>
                    <div class="score-detail">${typeLabel} · ${joueur.nb_lettres} lettre(s)</div>
                </div>
                <span class="score-valeur">${joueur.score}</span>
            `;
            listeScores.appendChild(item);
        });
    }

    /**
     * Met à jour l'indicateur « à qui le tour ».
     */
    function rendreTour(joueurs, indexCourant, terminee, gagnants) {
        if (terminee) {
            tourJoueur.textContent = gagnants && gagnants.length
                ? `Partie terminée — ${gagnants.join(', ')}`
                : 'Partie terminée';
            tourJoueur.className = 'tour-joueur';
            document.querySelector('.tour-label').textContent = '🏁';
            return;
        }
        const courant = joueurs[indexCourant];
        document.querySelector('.tour-label').textContent = 'Au tour de';
        tourJoueur.textContent = `${icone(courant.humain)} ${courant.nom}`;
        tourJoueur.className = 'tour-joueur ' + (courant.humain ? 'humain' : 'ordinateur');
    }

    /**
     * Rend le chevalet du joueur courant en mode MASQUÉ : le bon nombre de
     * rectangles grisés, sans révéler aucune lettre.
     */
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

    /**
     * Rend le chevalet du joueur courant en mode RÉVÉLÉ (lettres + valeurs).
     *
     * Chaque case est cliquable : un clic la sélectionne (surbrillance) pour la
     * poser ensuite sur le plateau. Une lettre déjà déposée en attente est
     * grisée (« utilisée ») et n'est plus sélectionnable tant qu'on ne l'a pas
     * retirée du plateau.
     */
    function rendreChevaletRevele(lettres) {
        chevaletEl.innerHTML = '';
        if (!lettres.length) {
            chevaletEl.innerHTML = '<span class="chevalet-vide">Chevalet vide.</span>';
            return;
        }
        // Indices de lettres actuellement posées en attente sur le plateau.
        const utilises = new Set(enAttente.map(p => p.index));
        lettres.forEach((l, index) => {
            const c = document.createElement('div');
            c.className = 'chevalet-case revelee' + (l.joker ? ' joker' : '');
            if (utilises.has(index)) {
                c.classList.add('utilisee');
            } else if (index === selection) {
                c.classList.add('selectionnee');
            }
            const lettreAffichee = l.joker ? '★' : escapeHtml(l.lettre);
            c.innerHTML = `${lettreAffichee}<span class="val">${l.valeur}</span>`;
            c.dataset.index = index;
            chevaletEl.appendChild(c);
        });
    }

    /**
     * Met à jour le bouton et l'affichage du chevalet selon l'état de visibilité.
     */
    async function majChevalet() {
        const courant = etat.joueurs[etat.index_courant];
        chevaletNom.textContent = courant ? courant.nom : '—';

        if (chevaletVisible) {
            btnVisibilite.textContent = '🙈 Cacher mes lettres';
            // On ne demande QUE le chevalet du joueur courant, un seul à la fois.
            const res = await api.obtenir_chevalet(etat.index_courant);
            if (res.succes) {
                chevaletLettres = res.lettres;
                rendreChevaletRevele(chevaletLettres);
            } else {
                chevaletVisible = false;
                chevaletLettres = [];
                btnVisibilite.textContent = '👁️ Voir mes lettres';
                rendreChevaletMasque(courant ? courant.nb_lettres : 0);
            }
        } else {
            btnVisibilite.textContent = '👁️ Voir mes lettres';
            chevaletLettres = [];
            rendreChevaletMasque(courant ? courant.nb_lettres : 0);
        }
        majControlesJeu();
    }

    /**
     * Sens du mot effectivement utilisé : déduit dès qu'au moins deux lettres
     * sont alignées (ligne -> horizontal, colonne -> vertical) ; sinon le sens
     * choisi manuellement (``sensForce``) pour une seule lettre.
     */
    function sensCourant() {
        if (enAttente.length >= 2) {
            const memeLigne = enAttente.every(p => p.ligne === enAttente[0].ligne);
            return memeLigne ? 'H' : 'V';
        }
        return sensForce;
    }

    /**
     * Met à jour les contrôles de pose (visibilité, indicateur de sens, boutons)
     * selon l'état courant : jouable seulement si le chevalet est révélé et la
     * partie non terminée.
     */
    function majControlesJeu() {
        const jouable = chevaletVisible && etat && !etat.terminee;
        zoneJeu.hidden = !jouable;
        if (!jouable) {
            return;
        }
        // L'indicateur/bascule de sens n'a de sens que pour UNE seule lettre :
        // au-delà, le sens est imposé par l'alignement.
        const sens = sensCourant();
        const libelleSens = sens === 'H' ? '↔ Horizontal' : '↕ Vertical';
        if (enAttente.length >= 2) {
            btnSens.hidden = true;
            indicateurSens.textContent = `Sens : ${libelleSens} (déduit)`;
        } else if (enAttente.length === 1) {
            btnSens.hidden = false;
            btnSens.textContent = `Sens : ${libelleSens} (cliquer pour changer)`;
            indicateurSens.textContent = '';
        } else {
            btnSens.hidden = true;
            indicateurSens.textContent = '';
        }
        btnValider.disabled = enAttente.length === 0;
        btnAnnuler.disabled = enAttente.length === 0;
    }

    /**
     * Affiche un message à l'utilisateur (erreur ou information).
     */
    function afficherMessage(texte, type = 'info') {
        messageCoup.textContent = texte || '';
        messageCoup.className = 'message-coup' + (texte ? ' ' + type : '');
    }

    /**
     * Recharge l'état complet et rafraîchit l'affichage. Remasque le chevalet.
     */
    async function rafraichir() {
        etat = await api.obtenir_etat();
        chevaletVisible = false;
        // Toute pose en cours est abandonnée lors d'un rechargement d'état.
        enAttente = [];
        selection = null;
        sensForce = 'H';
        rendrePlateau();
        rendreScores(etat.joueurs);
        rendreTour(etat.joueurs, etat.index_courant, etat.terminee, etat.gagnants);
        sacNombre.textContent = etat.jetons_sac;
        await majChevalet();
    }

    // --- Gestionnaires d'événements ---

    // Bascule voir / cacher les lettres du joueur courant
    btnVisibilite.addEventListener('click', async () => {
        chevaletVisible = !chevaletVisible;
        await majChevalet();
    });

    // Rafraîchir l'état de la partie
    btnRafraichir.addEventListener('click', rafraichir);

    // --- Pose d'un mot (clic-clic) ---

    /**
     * Rafraîchit uniquement l'affichage lié à la pose en cours (plateau,
     * chevalet révélé, contrôles) sans recharger l'état côté Python.
     */
    function rendrePose() {
        rendrePlateau();
        if (chevaletVisible) {
            rendreChevaletRevele(chevaletLettres);
        }
        majControlesJeu();
    }

    /**
     * Clic sur une lettre du chevalet révélé : la sélectionne (ou la
     * désélectionne si elle l'était déjà). Une lettre déjà posée en attente
     * (« utilisée ») n'est pas sélectionnable.
     */
    chevaletEl.addEventListener('click', (evt) => {
        const caseEl = evt.target.closest('.chevalet-case.revelee');
        if (!caseEl || caseEl.classList.contains('utilisee')) {
            return;
        }
        const index = Number(caseEl.dataset.index);
        selection = (selection === index) ? null : index;
        afficherMessage('');
        rendrePose();
    });

    /**
     * Ouvre la modale de choix de lettre pour un joker et renvoie la lettre
     * choisie (``A``–``Z``) ou ``null`` si l'utilisateur annule.
     */
    function choisirLettreJoker() {
        return new Promise((resolve) => {
            jokerGrille.innerHTML = '';
            const fermer = (valeur) => {
                jokerModale.hidden = true;
                jokerAnnuler.removeEventListener('click', surAnnuler);
                resolve(valeur);
            };
            const surAnnuler = () => fermer(null);
            for (let i = 0; i < 26; i++) {
                const lettre = String.fromCharCode(65 + i);
                const b = document.createElement('button');
                b.className = 'joker-lettre';
                b.textContent = lettre;
                b.addEventListener('click', () => fermer(lettre));
                jokerGrille.appendChild(b);
            }
            jokerAnnuler.addEventListener('click', surAnnuler);
            jokerModale.hidden = false;
        });
    }

    /**
     * Clic sur une case du plateau :
     * - case portant une lettre en attente : on la retire (retour au chevalet) ;
     * - case déjà occupée par une tuile validée : refus (message clair) ;
     * - case vide : on y place la lettre sélectionnée (joker => choix de lettre).
     */
    plateauEl.addEventListener('click', async (evt) => {
        const caseEl = evt.target.closest('.case');
        if (!caseEl) {
            return;
        }
        const ligne = Number(caseEl.dataset.ligne);
        const colonne = Number(caseEl.dataset.colonne);

        // Retrait d'une lettre en attente (recliquer sa case).
        const dejaPosee = attenteEn(ligne, colonne);
        if (dejaPosee) {
            enAttente = enAttente.filter(p => p !== dejaPosee);
            afficherMessage('');
            rendrePose();
            return;
        }

        // Case déjà occupée par une tuile d'un tour précédent : pose interdite.
        if (etat.plateau[ligne][colonne].lettre) {
            afficherMessage('Cette case porte déjà une tuile : impossible d\'y poser une lettre.', 'erreur');
            return;
        }

        // Case vide : il faut une lettre sélectionnée au chevalet.
        if (selection === null) {
            afficherMessage('Sélectionnez d\'abord une lettre de votre chevalet.', 'info');
            return;
        }
        const lettre = chevaletLettres[selection];
        let valeurLettre = lettre.lettre;
        let estJoker = Boolean(lettre.joker);
        if (estJoker) {
            const choix = await choisirLettreJoker();
            if (!choix) {
                return;  // choix annulé : rien n'est posé, la sélection demeure.
            }
            valeurLettre = choix;
        }
        enAttente.push({
            ligne,
            colonne,
            lettre: valeurLettre,
            joker: estJoker,
            index: selection,
        });
        selection = null;
        afficherMessage('');
        rendrePose();
    });

    // Bascule du sens (seulement pertinent pour une unique lettre en attente).
    btnSens.addEventListener('click', () => {
        sensForce = (sensForce === 'H') ? 'V' : 'H';
        majControlesJeu();
    });

    // Annuler : retire toutes les lettres en attente (retour au chevalet).
    btnAnnuler.addEventListener('click', () => {
        enAttente = [];
        selection = null;
        sensForce = 'H';
        afficherMessage('');
        rendrePose();
    });

    // Valider : construit le coup côté Python et l'applique.
    btnValider.addEventListener('click', async () => {
        if (!enAttente.length) {
            return;
        }
        btnValider.disabled = true;
        const placements = enAttente.map(p => ({
            ligne: p.ligne,
            colonne: p.colonne,
            lettre: p.lettre,
            joker: p.joker,
        }));
        let res;
        try {
            res = await api.poser_mot(placements, sensCourant());
        } catch (err) {
            afficherMessage('Erreur inattendue lors de la validation du coup.', 'erreur');
            majControlesJeu();
            return;
        }
        if (res && res.succes) {
            // Le coup est joué : on recharge l'état (nouveau tour, chevalet remasqué)
            // et on vide l'attente. Rien n'est perdu : le moteur a consommé les lettres.
            const points = res.points != null ? res.points : 0;
            await rafraichir();
            afficherMessage(`Coup joué (+${points} point${points > 1 ? 's' : ''}).`, 'succes');
        } else {
            // Échec : on conserve les lettres en attente pour correction.
            const message = (res && res.erreur) ? res.erreur : 'Coup refusé.';
            afficherMessage(message, 'erreur');
            majControlesJeu();
        }
    });

    // --- Initialisation ---
    await rafraichir();
});
