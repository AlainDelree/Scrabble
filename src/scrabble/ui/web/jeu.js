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
 * du mot se déduit de l'alignement des lettres et, pour une lettre unique, est
 * fixé en interne côté Python (issue #43 : sans effet sur la validation ni le
 * score) — aucun contrôle de sens n'est présenté au joueur. Un joker demande la
 * lettre représentée à la pose. Les
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
    // Bandeau de fin de partie (issue #45, point 2) : masqué pendant la partie,
    // il n'affiche l'annonce de fin et les gagnants qu'une fois la partie finie.
    const bandeauFin = document.getElementById('bandeau-fin');
    // Encart d'historique glissant (issue #37) : liste des dernières actions,
    // la plus récente en haut, chaque ligne cliquable pour le détail du coup.
    const historiqueListe = document.getElementById('historique-liste');
    const historiqueCompte = document.getElementById('historique-compte');
    const chevaletEl = document.getElementById('chevalet');
    const chevaletNom = document.getElementById('chevalet-nom');
    const btnVisibilite = document.getElementById('btn-visibilite');
    const btnRafraichir = document.getElementById('btn-rafraichir');
    const btnEchangerTout = document.getElementById('btn-echanger-tout');

    // Mode « attente d'un tour d'ordinateur » (issue #35) : bloc affiché à la
    // place de toute la mécanique interactive quand le joueur courant n'est pas
    // humain, avec le bouton « Faire jouer l'ordinateur ».
    const zoneAttenteIA = document.getElementById('zone-attente-ia');
    const attenteMessageIA = document.getElementById('attente-ia-message');
    const btnJouerIA = document.getElementById('btn-jouer-ia');
    // Éléments interactifs masqués pendant un tour d'ordinateur.
    const chevaletEntete = document.querySelector('.chevalet-entete');
    const zoneReflexion = document.querySelector('.zone-reflexion');

    // Zone de brouillon (réflexion indépendante du plateau)
    const blocBrouillon = document.getElementById('bloc-brouillon');
    const brouillonEl = document.getElementById('brouillon');
    // Vérification dictionnaire par saisie libre (issue #50) : le mot testé est
    // désormais le contenu de ce champ texte, plus les lettres du brouillon. Le
    // champ + le bouton vivent sous « Remettre toutes ses lettres et passer ».
    const champVerif = document.getElementById('champ-verif');
    const btnVerifier = document.getElementById('btn-verifier');
    const messageBrouillon = document.getElementById('message-brouillon');
    const chevaletAide = document.getElementById('chevalet-aide');

    // Contrôles de pose d'un mot (mécanique clic-clic)
    const zoneJeu = document.getElementById('zone-jeu');
    const btnValider = document.getElementById('btn-valider');
    const btnVerifierCoup = document.getElementById('btn-verifier-coup');
    const btnAnnuler = document.getElementById('btn-annuler');
    const messageCoup = document.getElementById('message-coup');

    // Modale de choix de lettre pour un joker
    const jokerModale = document.getElementById('joker-modale');
    const jokerGrille = document.getElementById('joker-grille');
    const jokerAnnuler = document.getElementById('joker-annuler');

    // Modale de détail du score (issue #35)
    const scoreModale = document.getElementById('score-modale');
    const scoreTitre = document.getElementById('score-titre');
    const scoreDetail = document.getElementById('score-detail');
    const scoreTotal = document.getElementById('score-total');
    const scoreFermer = document.getElementById('score-fermer');

    // Libellés des cases bonus (le TYPE de chaque case vient de Python).
    //
    // Trois jeux de libellés :
    //   - LABEL_TOOLTIP : toujours en français complet des vraies boîtes de jeu
    //     francophones ; utilisé pour l'attribut « title » (info-bulle) quel que
    //     soit le thème.
    //   - LABEL_COMPLET : texte affiché DANS la case pour les thèmes non abrégés.
    //   - LABEL_ABREGE  : texte affiché DANS la case pour le thème « abrégé ».
    const LABEL_TOOLTIP = {
        'MT': 'Mot compte triple',
        'MD': 'Mot compte double',
        'LT': 'Lettre compte triple',
        'LD': 'Lettre compte double',
        'centre': 'Case centrale (mot compte double)',
        'normale': ''
    };
    // Version courte affichée DANS la case (le texte complet reste en info-bulle
    // via LABEL_TOOLTIP) : « Mot compte triple » déborderait d'une case de ~30 px.
    // Abréviations lisibles (mot/lettre × 2 ou 3) qui tiennent sans rogner.
    const LABEL_COMPLET = {
        'MT': 'MOT ×3',
        'MD': 'MOT ×2',
        'LT': 'LET ×3',
        'LD': 'LET ×2',
        'centre': '★',
        'normale': ''
    };
    const LABEL_ABREGE = {
        'MT': 'MT',
        'MD': 'MD',
        'LT': 'LT',
        'LD': 'LD',
        'centre': '★',
        'normale': ''
    };
    // Thèmes reconnus (alignés avec scrabble.config.THEMES_PLATEAU et le CSS).
    const THEMES = ['classique', 'vert', 'abrege'];

    // État courant côté vue
    let etat = null;
    let chevaletVisible = false;
    // Mode « chevalet toujours révélé » : vrai lorsqu'il y a au plus un joueur
    // humain (personne à qui cacher ses lettres). Le bouton bascule et le texte
    // d'avertissement de confidentialité sont alors masqués, et le chevalet ne
    // se remasque jamais au rafraîchissement.
    let chevaletTjrsRevele = false;
    // Thème visuel actif et jeu de libellés affichés dans les cases (le thème
    // « abrégé » utilise les étiquettes courtes ; les autres, le texte complet).
    let themePlateau = 'classique';
    let labelVisible = LABEL_COMPLET;

    // Zone de brouillon : copie réordonnable des lettres révélées, INDÉPENDANTE
    // du plateau et de la pose en attente (espace de réflexion pur). Réordonner
    // ici n'affecte ni le chevalet, ni les placements en cours.
    let brouillonLettres = [];  // {lettre, valeur, joker} dans l'ordre affiché
    let brouillonSelection = null;  // index du 1er emplacement d'un échange

    // État de la pose « clic-clic »
    let chevaletLettres = [];   // lettres révélées du joueur courant (ordre chevalet)
    let selection = null;       // index (dans chevaletLettres) de la lettre sélectionnée
    let enAttente = [];          // placements en cours : {ligne, colonne, lettre, joker, index}

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
     *
     * La valeur en points de la lettre est affichée en indice (classe
     * ``.tuile-valeur``), comme sur les lettres du chevalet et du brouillon
     * (issue #56). Un joker vaut toujours 0, cohérent avec le reste de
     * l'application ; ``cell.valeur`` est fourni par Python (case du plateau)
     * ou par le placement en attente (copié depuis le chevalet).
     */
    function creerTuile(cell, enAttente = false) {
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
                // Le type vient de Python en MAJUSCULES (``TypeCase.value`` :
                // « MT », « MD », « LT », « LD »). Les sélecteurs CSS de couleur
                // (``.case-mt`` …) sont en minuscules et les classes HTML sont
                // SENSIBLES À LA CASSE : sans ce toLowerCase(), ``case-MT`` ne
                // matche aucune règle, la case reste transparente et laisse voir
                // le fond brun du plateau — d'où l'absence de couleurs bonus
                // constatée malgré l'issue #30. On normalise donc en minuscules.
                const typeClasse = String(cell.type).toLowerCase();
                caseEl.className = `case case-${typeClasse}`;
                // Info-bulle toujours en français complet (indépendante du thème).
                caseEl.title = LABEL_TOOLTIP[cell.type] || '';
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
                    // Étiquette visible : complète ou abrégée selon le thème.
                    caseEl.textContent = labelVisible[cell.type] || '';
                }
                caseEl.setAttribute('aria-label', `Ligne ${l + 1}, colonne ${c + 1}`);
                fragment.appendChild(caseEl);
            });
        });
        plateauEl.appendChild(fragment);
    }

    /**
     * Construit le panneau d'information **public** d'un joueur sur UNE seule
     * ligne horizontale compacte (issue #47, point 1), IDENTIQUE pour les quatre
     * côtés (haut, gauche, droite, bas) et pour les deux natures (humain comme
     * ordinateur). Contenu minimal aligné sur la même ligne : petit avatar, nom,
     * score, nombre de lettres et — pour le joueur actif — un indicateur « à
     * jouer » court qui ne passe JAMAIS à la ligne suivante. Aucune identité de
     * lettre n'y figure (confidentialité). Les codes couleur (bordure/fond bleu
     * pour l'humain, violet pour l'ordinateur) et le cadre vert du joueur actif
     * sont conservés.
     */
    function creerPanneauJoueur(joueur) {
        const item = document.createElement('div');
        const nature = joueur.humain ? 'humain' : 'ordinateur';
        item.className = `panneau-joueur ${nature}${joueur.courant ? ' courant' : ''}`;
        item.dataset.cote = joueur.position || '';

        // Indicateur du joueur actif (issue #47, point 1) : reformulé TRÈS court
        // pour tenir sur la ligne unique quelle que soit la largeur disponible
        // (« à vous » pour l'humain de référence, « son tour » pour tout autre).
        const badgeTour = joueur.courant
            ? `<span class="panneau-tour">● ${joueur.humain ? 'à vous' : 'son tour'}</span>`
            : '';
        // Avatar SVG attribué côté Python (identifiant -> fichier), en PETIT et
        // intégré à la ligne (issue #47, point 1) plutôt qu'au-dessus. Repli sur
        // l'icône emoji si aucun avatar n'est fourni (compat/robustesse).
        const avatarHtml = joueur.avatar
            ? `<img class="panneau-avatar" src="avatars/${encodeURIComponent(joueur.avatar)}.svg"
                    alt="" width="26" height="26">`
            : `<span class="panneau-icone">${icone(joueur.humain)}</span>`;
        // Distinction humain/ordinateur renforcée (issue #59, point 2) : en plus
        // du code couleur bordure/fond (bleu humain, violet ordinateur), les
        // joueurs ORDINATEUR portent une icône « ordinateur » (🖥️) juste après
        // leur nombre de lettres. Rien n'est ajouté pour un joueur humain, dont
        // la distinction reste la couleur + l'avatar déjà présents. Le titre
        // (info-bulle) explicite l'icône pour l'accessibilité.
        const badgeOrdinateur = joueur.humain
            ? ''
            : '<span class="panneau-ordi" title="Joueur ordinateur" aria-label="Joueur ordinateur">🖥️</span>';
        // Niveau de difficulté de l'ordinateur (issue #63) : libellé français
        // (rien pour un humain, dont ``joueur.niveau`` vaut ``null``). Le badge
        // est TOUJOURS placé à l'intérieur du groupe identité, juste après le
        // nom ; c'est le CSS qui décide de sa disposition selon le côté du
        // panneau (``data-cote``) : SOUS le nom pour les panneaux latéraux
        // (gauche/droite), DERRIÈRE le nom sur la même ligne pour le panneau du
        // haut. Le panneau du bas est réservé à l'humain (aucun niveau).
        const niveauLabel = joueur.niveau
            ? ({
                  DEBUTANT: 'Débutant',
                  FACILE: 'Facile',
                  INTERMEDIAIRE: 'Intermédiaire',
                  EXPERT: 'Expert',
              }[joueur.niveau] || joueur.niveau)
            : '';
        const badgeNiveau = niveauLabel
            ? `<span class="panneau-niveau">${escapeHtml(niveauLabel)}</span>`
            : '';
        // Ligne unique : avatar · [nom (+ niveau)] · score · lettres · (icône
        // ordinateur) · (indicateur à jouer). Le nom et son niveau sont réunis
        // dans un groupe identité que le CSS empile (latéraux) ou aligne (haut).
        // ``white-space: nowrap`` (CSS) garantit que la ligne ne se scinde pas.
        item.innerHTML = `
            ${avatarHtml}
            <span class="panneau-identite">
                <span class="panneau-nom">${escapeHtml(joueur.nom)}</span>
                ${badgeNiveau}
            </span>
            <span class="panneau-score">${joueur.score} pts</span>
            <span class="panneau-lettres">🎴 ${joueur.nb_lettres}</span>
            ${badgeOrdinateur}
            ${badgeTour}
        `;
        return item;
    }

    /**
     * Dispose les panneaux joueurs autour du plateau : chacun est inséré dans le
     * slot du côté que Python lui a assigné (``joueur.position`` : ``"bas"``,
     * ``"haut"``, ``"gauche"`` ou ``"droite"``). Le joueur humain de référence
     * (position ``"bas"``) partage son slot avec le chevalet ci-dessous ; les
     * autres côtés n'affichent que les infos publiques. Un côté sans joueur
     * reste vide (slot masqué par le CSS).
     */
    function rendrePanneaux(joueurs) {
        Object.values(slots).forEach(slot => { slot.innerHTML = ''; });
        joueurs.forEach(joueur => {
            const slot = slots[joueur.position];
            if (slot) {
                slot.appendChild(creerPanneauJoueur(joueur));
            }
        });
    }

    /**
     * Rend le bandeau de fin de partie (issue #45, point 2). L'indicateur « Au
     * tour de … » a été retiré (information déjà portée par le cadre vert et le
     * badge du panneau actif) ; seule reste l'annonce de fin de partie, qui n'est
     * pas redondante. Pendant la partie, le bandeau est masqué (aucune place
     * prise) ; à la fin, il affiche le ou les gagnants.
     */
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

    // Libellés lisibles du type d'action pour l'historique glissant (issue #37).
    const LABEL_ACTION = {
        'coup': 'a posé',
        'passe': 'a passé',
        'echange': 'a échangé',
    };

    /**
     * Résumé texte d'une action de l'historique (mot posé, passe ou échange).
     */
    function resumeAction(entree) {
        const verbe = LABEL_ACTION[entree.action] || entree.action;
        if (entree.action === 'coup') {
            const mot = entree.mot ? ` « ${entree.mot} »` : '';
            return `${verbe}${mot}`;
        }
        return verbe;
    }

    /**
     * Rend l'encart d'historique glissant (issue #37) à partir de
     * ``etat.historique`` : une ligne par action récente, la plus RÉCENTE EN
     * HAUT (ordre déjà fixé côté Python). Chaque ligne affiche le nom du joueur,
     * le type d'action (mot posé / passé / échangé) et le score gagné (0 pour une
     * passe/échange), avec la couleur bleu (humain) / violet (ordinateur)
     * cohérente avec le reste de l'écran. Une ligne est cliquable pour rouvrir le
     * détail du coup ; une action sans détail (passe/échange) est marquée comme
     * telle et signale « rien à détailler » au clic.
     */
    function rendreHistorique(historique) {
        historiqueListe.innerHTML = '';
        const nb = Array.isArray(historique) ? historique.length : 0;
        // Compteur affiché sur le résumé de la barre (issue #47, point 2) : donne
        // un aperçu sans déplier le menu, et n'apparaît pas quand il est vide.
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
        historique.forEach(entree => {
            const item = document.createElement('li');
            const nature = entree.humain ? 'humain' : 'ordinateur';
            const cliquable = Boolean(entree.detail);
            item.className = `historique-ligne ${nature}`
                + (cliquable ? ' cliquable' : '');
            item.dataset.index = entree.index;
            if (cliquable) {
                item.setAttribute('role', 'button');
                item.tabIndex = 0;
                item.title = 'Voir le détail de ce coup';
            } else {
                item.title = 'Aucun détail pour cette action';
            }
            item.innerHTML = `
                <span class="historique-joueur">${icone(entree.humain)} ${escapeHtml(entree.nom_joueur)}</span>
                <span class="historique-action">${escapeHtml(resumeAction(entree))}</span>
                <span class="historique-score">+${entree.score_action} pt${entree.score_action > 1 ? 's' : ''}</span>
            `;
            historiqueListe.appendChild(item);
        });
    }

    /**
     * Ouvre le détail d'une action de l'historique au clic (issue #37). Si
     * l'action a un détail (un coup), on rouvre la modale existante avec CE
     * détail précis (pas nécessairement le dernier), en titrant par le joueur.
     * Une passe ou un échange n'a rien à détailler : on affiche alors un message
     * simple dans la modale plutôt que d'ouvrir un détail vide.
     */
    function ouvrirDetailHistorique(entree) {
        if (!entree) {
            return;
        }
        if (entree.detail) {
            const titre = `Détail du coup de ${entree.nom_joueur}`
                + (entree.mot ? ` — « ${entree.mot} »` : '');
            afficherDetailScore(entree.detail, titre);
        } else {
            afficherMessageSansDetail(entree.nom_joueur, entree.action);
        }
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
     * Affiche un message dans la zone de brouillon (vérification dictionnaire).
     */
    function afficherMessageBrouillon(texte, type = 'info') {
        messageBrouillon.textContent = texte || '';
        messageBrouillon.className = 'message-brouillon' + (texte ? ' ' + type : '');
    }

    /**
     * Rend la zone de brouillon : une case par emplacement (dans l'ordre
     * courant). Le bloc entier est masqué tant que le chevalet n'est pas révélé
     * (ou s'il est vide).
     *
     * Modèle (issue #48) : ``brouillonLettres`` est un tableau de 9 emplacements
     * (N lettres du chevalet + 2 emplacements vides, soit 7+2 = 9 en jeu
     * normal). Chaque case est soit une lettre ``{lettre, valeur, joker}``, soit
     * ``null`` (emplacement vide). Il y a TOUJOURS exactement 2 vides et jamais
     * de saisie de nouvelle lettre : les vides ne se remplissent que par un
     * déplacement depuis un autre emplacement.
     *
     * Interactions retenues (sans glisser-déposer, fiable sous pywebview) :
     *  - clic sur une lettre puis clic sur un emplacement vide → déplacement ;
     *  - clic sur une lettre puis clic sur une autre lettre → échange ;
     *  - clic droit sur une lettre → renvoi vers le vide le plus proche de la
     *    fin (voir gestionnaire ``contextmenu``).
     * Un premier clic sélectionne (surbrillance), recliquer annule la sélection.
     */
    function rendreBrouillon() {
        const afficher = chevaletVisible && brouillonLettres.length > 0;
        blocBrouillon.hidden = !afficher;
        if (!afficher) {
            brouillonSelection = null;
            return;
        }
        brouillonEl.innerHTML = '';
        brouillonLettres.forEach((l, index) => {
            // Emplacement vide : case cliquable (cible d'un déplacement) mais
            // qui ne fait pas partie du « mot » — la vérification dictionnaire
            // l'ignore (voir btnVerifier). Elle porte un data-index pour être
            // reconnue comme cible par le gestionnaire de clic.
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
            const lettreAffichee = l.joker ? '★' : escapeHtml(l.lettre);
            c.innerHTML = `${lettreAffichee}<span class="val">${l.valeur}</span>`;
            c.dataset.index = index;
            brouillonEl.appendChild(c);
        });
    }

    /**
     * Vrai lorsque le joueur courant est un humain et la partie en cours : le
     * panneau du bas est alors interactif (chevalet, brouillon, pose…). Faux
     * pendant un tour d'ordinateur (panneau en attente) ou en fin de partie.
     * Source de vérité côté Python : ``etat.tour_humain`` (voir issue #35).
     */
    function estTourHumain() {
        return Boolean(etat && !etat.terminee && etat.tour_humain);
    }

    /**
     * Bascule entre le mode interactif (tour d'un humain) et le mode « attente »
     * (tour d'un ordinateur) — correction du défaut d'exposition du tour IA
     * (issue #35). En mode attente, toute la mécanique interactive est masquée
     * (le chevalet d'un ordinateur n'est jamais exposé) et un message
     * « En attente du coup de [nom]… » accompagne le bouton « Faire jouer
     * l'ordinateur ». Le bouton n'apparaît que lorsque le joueur courant n'est
     * pas humain et la partie n'est pas terminée.
     */
    function majModeTour() {
        const courant = etat.joueurs[etat.index_courant];
        const attenteIA = Boolean(etat && !etat.terminee && !etat.tour_humain);

        zoneAttenteIA.hidden = !attenteIA;
        if (attenteIA && courant) {
            attenteMessageIA.textContent =
                `En attente du coup de ${courant.nom}…`;
            btnJouerIA.disabled = false;
        }

        // Masquer toute la mécanique interactive tant que ce n'est pas un tour
        // humain : entête (voir/cacher, échanger), chevalet + brouillon, aide.
        if (chevaletEntete) {
            chevaletEntete.hidden = attenteIA;
        }
        if (zoneReflexion) {
            zoneReflexion.hidden = attenteIA;
        }
        if (chevaletAide) {
            // Ne réafficher l'aide que si la confidentialité l'exige aussi.
            chevaletAide.hidden = attenteIA || chevaletTjrsRevele;
        }
        if (attenteIA) {
            zoneJeu.hidden = true;
        }
    }

    /**
     * Met à jour le bouton et l'affichage du chevalet selon l'état de visibilité.
     */
    async function majChevalet() {
        const courant = etat.joueurs[etat.index_courant];
        chevaletNom.textContent = courant ? courant.nom : '—';

        // Tour d'un ordinateur (ou fin de partie) : aucun chevalet n'est exposé
        // ni manipulable — surtout pas celui d'une IA (issue #35). Le panneau
        // reste en mode attente (voir majModeTour) ; on n'appelle même pas
        // obtenir_chevalet pour ne rien faire fuir dans le DOM.
        if (!estTourHumain()) {
            chevaletVisible = false;
            chevaletLettres = [];
            brouillonLettres = [];
            brouillonSelection = null;
            rendreChevaletMasque(0);
            rendreBrouillon();
            majActionsChevalet();
            majControlesJeu();
            return;
        }

        if (chevaletVisible) {
            btnVisibilite.textContent = '🙈 Cacher mes lettres';
            // On ne demande QUE le chevalet du joueur courant, un seul à la fois.
            const res = await api.obtenir_chevalet(etat.index_courant);
            if (res.succes) {
                chevaletLettres = res.lettres;
                rendreChevaletRevele(chevaletLettres);
                // Le brouillon reçoit une COPIE des lettres révélées (réflexion
                // indépendante : réordonner ici n'affecte pas le chevalet), plus
                // 2 emplacements vides finaux (issue #48) : 7 lettres + 2 vides
                // = 9 emplacements en jeu normal. Les vides sont déplaçables
                // librement par le joueur (voir gestionnaires de clic).
                brouillonLettres = chevaletLettres.map(l => ({ ...l }));
                if (brouillonLettres.length > 0) {
                    brouillonLettres.push(null, null);
                }
            } else {
                chevaletVisible = false;
                chevaletLettres = [];
                brouillonLettres = [];
                btnVisibilite.textContent = '👁️ Voir mes lettres';
                rendreChevaletMasque(courant ? courant.nb_lettres : 0);
            }
        } else {
            btnVisibilite.textContent = '👁️ Voir mes lettres';
            chevaletLettres = [];
            brouillonLettres = [];
            rendreChevaletMasque(courant ? courant.nb_lettres : 0);
        }
        brouillonSelection = null;
        rendreBrouillon();
        majActionsChevalet();
        majControlesJeu();
    }

    /**
     * Configure le mode de confidentialité selon le nombre de joueurs humains :
     * avec au plus un humain, le chevalet est toujours révélé (personne à qui le
     * cacher) — le bouton bascule et l'avertissement de confidentialité sont
     * masqués. Avec deux humains ou plus, comportement historique (masqué par
     * défaut, bascule manuelle). À appeler à chaque changement d'état.
     */
    function configurerConfidentialite() {
        chevaletTjrsRevele = (etat.nb_humains || 0) <= 1;
        btnVisibilite.hidden = chevaletTjrsRevele;
        if (chevaletAide) {
            chevaletAide.hidden = chevaletTjrsRevele;
        }
    }

    /**
     * Affiche/masque les actions du chevalet dépendant de sa révélation :
     * bouton « remettre toutes ses lettres et passer » (visible seulement si le
     * chevalet est révélé, la partie en cours et le chevalet non vide).
     */
    function majActionsChevalet() {
        const courant = etat ? etat.joueurs[etat.index_courant] : null;
        const actif = chevaletVisible && etat && !etat.terminee
            && courant && courant.nb_lettres > 0;
        btnEchangerTout.hidden = !actif;
        btnEchangerTout.disabled = false;
    }

    /**
     * Met à jour les contrôles de pose (visibilité, boutons) selon l'état
     * courant : jouable seulement si le chevalet est révélé et la partie non
     * terminée.
     *
     * Aucun contrôle de sens n'est présenté (issue #43) : le sens du mot se
     * déduit de l'alignement des lettres et, pour une lettre unique, est fixé en
     * interne côté Python — ce choix est sans conséquence sur la validation ni le
     * score, donc rien à demander au joueur.
     */
    function majControlesJeu() {
        const jouable = chevaletVisible && etat && !etat.terminee;
        zoneJeu.hidden = !jouable;
        if (!jouable) {
            return;
        }
        btnValider.disabled = enAttente.length === 0;
        // « Vérifier et calculer » (issue #69) : actif dans les mêmes conditions
        // que « Jouer » (au moins une lettre en attente), mais ne joue pas le coup.
        btnVerifierCoup.disabled = enAttente.length === 0;
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
        configurerConfidentialite();
        // Avec au plus un humain, le chevalet reste révélé en permanence ; sinon
        // il se remasque à chaque rechargement (confidentialité entre adversaires).
        chevaletVisible = chevaletTjrsRevele;
        // Toute pose en cours est abandonnée lors d'un rechargement d'état.
        enAttente = [];
        selection = null;
        afficherMessageBrouillon('');
        rendrePlateau();
        rendrePanneaux(etat.joueurs);
        rendreFinPartie(etat.terminee, etat.gagnants);
        rendreHistorique(etat.historique);
        sacNombre.textContent = etat.jetons_sac;
        majModeTour();
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

    // --- Tour d'un ordinateur (issue #35) ---

    // « ▶ Faire jouer l'ordinateur » : joue UN SEUL tour d'ordinateur (celui du
    // joueur courant, via Partie.jouer_tour_ia côté moteur), puis recharge
    // l'écran (issue #55). Si l'ordinateur suivant est encore un ordinateur, le
    // rafraîchissement laisse le bouton visible et cliquable : l'humain reclique
    // pour chaque ordinateur suivant, et le message « En attente du coup de
    // [nom]… » reflète alors le nom de l'ordinateur dont c'est le tour. C'est la
    // SEULE façon de faire avancer le jeu pendant un tour IA : à aucun moment
    // l'humain ne manipule le chevalet d'un ordinateur à sa place (correction du
    // défaut d'exposition).
    btnJouerIA.addEventListener('click', async () => {
        btnJouerIA.disabled = true;
        let res;
        try {
            res = await api.faire_jouer_ia();
        } catch (err) {
            btnJouerIA.disabled = false;
            return;
        }
        if (res && res.succes) {
            await rafraichir();
            // Animation de la pose du coup que l'ordinateur vient de jouer
            // (issue #62, suite de #58) : après le rafraîchissement, la première
            // entrée de l'historique (la plus récente) est le tour IA qu'on vient
            // de jouer si nb_tours vaut 1. On révèle ses cases posées une par une
            // sur ~2,5 s, avec un « tac » à chaque lettre.
            if (res.nb_tours && etat.historique && etat.historique[0]) {
                await animerPose(etat.historique[0].positions);
                // Scrabble posé par l'ordinateur (bonus 50 pts, issue #64) :
                // petit feu d'artifice une fois la pose révélée.
                if (etat.historique[0].detail
                        && etat.historique[0].detail.bonus_scrabble) {
                    celebrerScrabble();
                }
            }
        } else {
            btnJouerIA.disabled = false;
        }
    });

    // --- Son de pose des tuiles (issue #62) ---
    //
    // Un « tac » synthétisé (Web Audio API, aucun fichier externe) joué à chaque
    // lettre révélée. Le contexte audio est créé paresseusement et réveillé au
    // premier usage : les navigateurs exigent un geste utilisateur pour démarrer
    // le son, or l'animation est toujours déclenchée par un clic (« Valider le
    // coup » ou « Faire jouer l'ordinateur »).
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

    /**
     * Joue un bref « tac » évoquant une tuile de bois qui se pose : une salve de
     * bruit blanc très courte passée dans un filtre passe-bande, avec une
     * enveloppe d'amplitude à attaque rapide et décroissance immédiate. Tout est
     * synthétisé — aucun asset audio n'est chargé.
     */
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
            // Décroissance du bruit pour un transitoire net (« clic » de tuile).
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
     * cases nouvellement posées UNE PAR UNE dans l'ordre du mot (celui de la
     * liste ``positions`` fournie par l'API, ``{ligne, colonne}``, calculée par
     * le moteur), avec un « tac » synchronisé à chaque apparition.
     *
     * La révélation totale dure ~2,5 s quel que soit le nombre de lettres : le
     * délai entre lettres vaut ``2500 / nb_lettres`` borné entre 120 et 500 ms
     * (mot très long ou très court). Renvoie une Promesse résolue à la fin de
     * l'animation, pour que l'appelant puisse considérer le tour terminé ensuite.
     *
     * Le plateau vient d'être rafraîchi : les tuiles sont déjà dans leur état
     * final. On les masque donc d'abord (``case-pose-cachee``) puis on les
     * dévoile successivement (``case-pose-revele``).
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
            // Masque toutes les tuiles concernées avant la révélation séquentielle.
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
                        // Laisse l'animation de la dernière tuile se terminer.
                        setTimeout(resolve, delai);
                    }
                }, i * delai);
            });
        });
    }

    /**
     * Célébration festive d'un « Scrabble » (issue #64, suite de #58) : les 7
     * lettres du chevalet posées en un seul coup rapportent le bonus de 50 points
     * (``detail.bonus_scrabble``, calculé côté moteur). Ce moment mérite mieux que
     * de se fondre dans l'historique : on déclenche un bref feu d'artifice.
     *
     * L'effet vit dans le calque plein écran ``#scrabble-fete``, TOUJOURS
     * transparent aux clics (``pointer-events: none`` en CSS) : il ne gêne jamais
     * l'interaction avec le plateau ou les boutons. Une trentaine de particules
     * colorées (palette du thème) jaillissent d'un point central puis s'effacent
     * en ~1,8 s, après quoi le calque est vidé.
     *
     * Accessibilité : si l'utilisateur préfère moins de mouvement
     * (``prefers-reduced-motion: reduce``, comme pour la pose lettre par lettre),
     * on remplace le feu d'artifice par un simple message « 🎉 Scrabble ! » affiché
     * brièvement, sans particule ni mouvement.
     */
    function celebrerScrabble() {
        const calque = document.getElementById('scrabble-fete');
        if (!calque) {
            return;
        }
        // On repart d'un calque propre (au cas où deux Scrabbles s'enchaînent).
        calque.innerHTML = '';

        const reduit = window.matchMedia
            && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        // Toast festif « Scrabble !! Félicitations » (issue #73), affiché EN
        // COMPLÉMENT du feu d'artifice (pas à sa place). Purement visuel : il
        // hérite du pointer-events: none du calque et n'intercepte aucun clic.
        // Il est retiré avec le reste du calque par le setTimeout de nettoyage.
        // En mouvement réduit, il reste identique mais sans fondu (voir CSS).
        const toast = document.createElement('div');
        toast.className = 'scrabble-toast';
        toast.textContent = '🎉 Scrabble !! Félicitations 🥳';
        calque.appendChild(toast);

        if (reduit) {
            // Mouvement réduit : uniquement le toast statique, aucune particule.
            setTimeout(() => { calque.innerHTML = ''; }, 2600);
            return;
        }

        // Feu d'artifice : des particules projetées dans toutes les directions
        // depuis le centre, avec des couleurs de la palette du thème.
        const couleurs = ['#2e7d32', '#1565c0', '#6a1b9a', '#ffd54f', '#ef6d86', '#d21f24'];
        const nb = 32;
        for (let i = 0; i < nb; i += 1) {
            const p = document.createElement('div');
            p.className = 'particule';
            // Direction aléatoire (angle + distance) : jaillissement radial.
            const angle = Math.random() * Math.PI * 2;
            const distance = 120 + Math.random() * 160;
            const dx = Math.cos(angle) * distance;
            // On ajoute une composante « retombée » vers le bas façon gerbe.
            const dy = Math.sin(angle) * distance + 40 + Math.random() * 80;
            p.style.setProperty('--dx', `${Math.round(dx)}px`);
            p.style.setProperty('--dy', `${Math.round(dy)}px`);
            p.style.setProperty('--rot', `${Math.round((Math.random() - 0.5) * 720)}deg`);
            p.style.setProperty('--delai', `${(Math.random() * 0.25).toFixed(2)}s`);
            p.style.setProperty('--col', couleurs[i % couleurs.length]);
            calque.appendChild(p);
        }
        // Nettoyage après la fin de l'animation (particules ~1,85 s, toast ~2,6 s).
        setTimeout(() => { calque.innerHTML = ''; }, 2600);
    }

    // --- Zone de brouillon (réflexion indépendante) ---

    // Déplacement / échange par deux clics successifs (issue #48).
    //  - 1er clic sur une lettre → sélection (surbrillance).
    //  - 2e clic sur la MÊME case → annule la sélection.
    //  - 2e clic sur une AUTRE lettre → échange des deux (comportement
    //    historique).
    //  - 2e clic sur un emplacement VIDE → déplacement de la lettre
    //    sélectionnée vers ce vide, sa case d'origine devenant vide.
    // Un premier clic sur un vide ne fait rien (rien à sélectionner). Aucune
    // saisie de lettre : les vides ne se remplissent que par déplacement.
    brouillonEl.addEventListener('click', (evt) => {
        const caseEl = evt.target.closest('.brouillon-case, .brouillon-case-vide');
        if (!caseEl) {
            return;
        }
        const index = Number(caseEl.dataset.index);
        const estVide = brouillonLettres[index] === null;
        if (brouillonSelection === null) {
            // On ne peut sélectionner qu'une lettre, jamais un vide.
            if (!estVide) {
                brouillonSelection = index;
            }
        } else if (brouillonSelection === index) {
            brouillonSelection = null;  // reclic : on annule la sélection
        } else if (estVide) {
            // Déplacement : la lettre sélectionnée occupe le vide, son
            // emplacement d'origine devient vide à son tour.
            brouillonLettres[index] = brouillonLettres[brouillonSelection];
            brouillonLettres[brouillonSelection] = null;
            brouillonSelection = null;
        } else {
            // Échange des deux lettres, puis on efface la sélection.
            const tmp = brouillonLettres[brouillonSelection];
            brouillonLettres[brouillonSelection] = brouillonLettres[index];
            brouillonLettres[index] = tmp;
            brouillonSelection = null;
        }
        rendreBrouillon();
    });

    // Clic droit sur une lettre → la renvoie vers l'emplacement vide le plus
    // proche de la fin (issue #48). L'emplacement d'origine est libéré PUIS la
    // lettre se place sur le plus grand index vide DISPONIBLE AVANT l'action
    // (donc à l'exclusion de son propre emplacement d'origine). Le menu
    // contextuel du navigateur est supprimé pour cet élément.
    // Cas limite : s'il n'existe aucun autre vide (l'unique vide serait
    // l'origine elle-même), on ne fait rien.
    brouillonEl.addEventListener('contextmenu', (evt) => {
        const caseEl = evt.target.closest('.brouillon-case');
        if (!caseEl) {
            return;  // clic droit hors d'une lettre : menu natif conservé
        }
        evt.preventDefault();
        const origine = Number(caseEl.dataset.index);
        // Vides disponibles AVANT l'action (l'origine est occupée, donc jamais
        // dans cette liste : l'exclusion demandée est ainsi automatique).
        const vides = [];
        brouillonLettres.forEach((l, i) => {
            if (l === null) {
                vides.push(i);
            }
        });
        if (vides.length === 0) {
            return;  // aucun autre vide : rien à faire (cas limite un seul vide)
        }
        const cible = Math.max(...vides);
        brouillonLettres[cible] = brouillonLettres[origine];
        brouillonLettres[origine] = null;
        brouillonSelection = null;
        rendreBrouillon();
    });

    // Vérifier un mot dans le dictionnaire (lecture seule, issue #50). Le mot
    // testé est le contenu LIBRE du champ texte — plus les lettres du brouillon.
    // Aucune contrainte : le joueur peut taper n'importe quelles lettres (même
    // absentes de son chevalet), cet outil de réflexion n'a aucun effet sur la
    // partie. La chaîne est normalisée côté Python (majuscules, accents).
    async function verifierMotDictionnaire() {
        const mot = champVerif.value;
        // Champ vide : message clair, pas d'appel ni d'erreur (équivalent de
        // l'ancien cas « brouillon vide »).
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

    // Entrée dans le champ lance la vérification si le champ n'est pas vide
    // (issue #57) : équivalent au clic sur le bouton, sans dupliquer la logique.
    champVerif.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && champVerif.value.trim()) {
            e.preventDefault();
            verifierMotDictionnaire();
        }
    });

    // Remettre tout le chevalet dans le sac et passer (via Partie.echanger).
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
            // Échange réussi : tour suivant, chevalet remasqué si applicable.
            await rafraichir();
            afficherMessage('Toutes vos lettres ont été remises dans le sac. Tour passé.', 'succes');
        } else {
            // Sac trop pauvre (ou partie terminée) : message clair, rien changé.
            afficherMessage((res && res.erreur) || 'Échange impossible.', 'erreur');
            btnEchangerTout.disabled = false;
        }
    });

    // --- Modale de détail du score (issue #35) ---

    // Libellés lisibles des cases bonus (le TYPE vient de Python). Sert à
    // expliquer un score, p. ex. « mot compte double ».
    const LABEL_BONUS = {
        'MT': 'mot compte triple',
        'MD': 'mot compte double',
        'LT': 'lettre compte triple',
        'LD': 'lettre compte double',
        'centre': 'case centrale (mot compte double)',
        'normale': '',
    };

    /**
     * Ferme la modale de détail du score.
     */
    function fermerScore() {
        scoreModale.hidden = true;
    }

    /**
     * Affiche la modale de détail du score (issue #35, réutilisée par l'encart
     * d'historique de l'issue #37). Le détail (mots formés, score de chaque mot,
     * cases bonus utilisées, bonus « scrabble », total) est fourni tel quel par
     * Python : rien n'est recalculé côté JS. ``titre`` (optionnel) personnalise
     * l'en-tête de la modale (p. ex. le joueur et le mot du coup cliqué) ; à
     * défaut, on garde « Détail du score ». Si aucun détail n'est fourni (cas
     * défensif), la modale n'est pas affichée.
     */
    function afficherDetailScore(detail, titre) {
        if (!detail || !Array.isArray(detail.mots)) {
            return;
        }
        scoreTitre.textContent = titre || 'Détail du score';
        scoreDetail.innerHTML = '';
        detail.mots.forEach(mot => {
            const ligne = document.createElement('div');
            ligne.className = 'score-mot';
            const bonus = (mot.cases_bonus || [])
                .map(c => LABEL_BONUS[c.type])
                .filter(Boolean);
            const bonusHtml = bonus.length
                ? `<span class="score-bonus">${escapeHtml(bonus.join(', '))}</span>`
                : '';
            ligne.innerHTML = `
                <span class="score-mot-texte">${escapeHtml(mot.texte)}</span>
                <span class="score-mot-points">${mot.score} pt${mot.score > 1 ? 's' : ''}</span>
                ${bonusHtml}
            `;
            scoreDetail.appendChild(ligne);
        });
        if (detail.bonus_scrabble) {
            const bonusLigne = document.createElement('div');
            bonusLigne.className = 'score-mot score-scrabble';
            bonusLigne.innerHTML = `
                <span class="score-mot-texte">🎉 Scrabble (7 lettres posées)</span>
                <span class="score-mot-points">+${detail.bonus_scrabble} pts</span>
            `;
            scoreDetail.appendChild(bonusLigne);
        }
        scoreTotal.textContent = `Total : ${detail.total} point${detail.total > 1 ? 's' : ''}`;
        scoreModale.hidden = false;
    }

    /**
     * Affiche dans la modale un message simple pour une action sans détail
     * (passe ou échange) cliquée dans l'historique (issue #37) : il n'y a alors
     * ni mot formé ni score à détailler.
     */
    function afficherMessageSansDetail(nomJoueur, action) {
        scoreTitre.textContent = `Action de ${nomJoueur}`;
        scoreDetail.innerHTML = '';
        const ligne = document.createElement('div');
        ligne.className = 'score-mot';
        // Le titre de la modale nomme déjà le joueur : le texte reste donc
        // impersonnel et va droit au but, sans la tournure « Il s'agit de un
        // échange… » (issue #60).
        const texte = action === 'echange'
            ? 'Échange de lettres, tour passé. 0 point.'
            : 'Tour passé, aucune lettre jouée. 0 point.';
        ligne.innerHTML =
            `<span class="score-mot-texte">${escapeHtml(texte)}</span>`;
        scoreDetail.appendChild(ligne);
        scoreTotal.textContent = 'Aucun mot formé — rien à détailler.';
        scoreModale.hidden = false;
    }

    // Fermeture par le bouton dédié…
    scoreFermer.addEventListener('click', fermerScore);
    // …ou par un clic en dehors du contenu de la modale (sur le fond assombri).
    scoreModale.addEventListener('click', (evt) => {
        if (evt.target === scoreModale) {
            fermerScore();
        }
    });

    // --- Encart d'historique glissant (issue #37) ---

    // Fermeture/ouverture fiable du menu « Derniers coups » (issues #56, #60).
    //
    // Historique du diagnostic :
    //  - #49 avait laissé au <summary> son `display: list-item` natif ;
    //  - #56 avait ajouté `evt.preventDefault()` + bascule manuelle de `open`,
    //    en supposant que preventDefault annulait à coup sûr l'action native.
    //
    // Or le symptôme « s'ouvre mais ne se referme pas » a persisté après #56.
    // Ce qui a été vérifié pour #60 :
    //  1. Le gestionnaire de #56 est bien présent et unique — aucun second
    //     `addEventListener` ni handler global ne touche ce <details> (grep du
    //     projet : un seul point mute `historique-menu` / `.open`).
    //  2. La liste dépliée (.historique-liste) est en `top: 100% + 6px`, donc
    //     SOUS le résumé : elle n'intercepte pas le clic de fermeture.
    //  3. Restait la seule hypothèse compatible avec l'asymétrie ouvre/ne-ferme :
    //     sous WebKitGTK, `preventDefault()` sur le clic d'un <summary> n'annule
    //     PAS toujours la bascule native du <details>. La bascule native se
    //     produit alors quand même et mute déjà `historiqueMenu.open` ; comme
    //     #56 recalculait la cible avec `!historiqueMenu.open` (donc à partir
    //     d'un `open` déjà retourné par le moteur), les deux bascules se
    //     composaient et l'état net repartait à « ouvert » à chaque reclic.
    //
    // Correctif #60 : ne plus JAMAIS déduire l'état cible du DOM (que le moteur
    // peut avoir muté). On tient notre propre intention (`historiqueOuvert`),
    // basculée d'un cran par clic, puis on force `open` dessus — une fois tout
    // de suite (cas des moteurs où preventDefault marche) et une fois en
    // requestAnimationFrame, APRÈS l'éventuelle bascule native, pour qu'elle ne
    // puisse pas gagner la course. Ouverture ET fermeture deviennent fiables
    // quel que soit le comportement de preventDefault.
    const historiqueMenu = document.getElementById('historique-menu');
    const historiqueResume = historiqueMenu
        ? historiqueMenu.querySelector('summary')
        : null;
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

    /**
     * Retrouve l'entrée d'historique correspondant à un élément <li> cliqué
     * (via son ``data-index``, l'index d'origine dans ``partie.historique``).
     */
    function entreeHistoriqueDe(li) {
        if (!li || !etat || !Array.isArray(etat.historique)) {
            return null;
        }
        const index = Number(li.dataset.index);
        return etat.historique.find(e => e.index === index) || null;
    }

    // Clic sur une ligne de l'historique : ouvre le détail du coup concerné
    // (modale réutilisée) — pas nécessairement le dernier coup joué.
    historiqueListe.addEventListener('click', (evt) => {
        const li = evt.target.closest('.historique-ligne');
        ouvrirDetailHistorique(entreeHistoriqueDe(li));
    });
    // Accessibilité : Entrée/Espace sur une ligne focalisée ouvre aussi le détail.
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
            // Valeur en points de la lettre, affichée en indice sur la tuile
            // en attente (issue #56). Un joker vaut toujours 0 ; sinon on
            // reprend la valeur de la lettre du chevalet.
            valeur: estJoker ? 0 : (lettre.valeur || 0),
            index: selection,
        });
        selection = null;
        afficherMessage('');
        rendrePose();
    });

    // Annuler : retire toutes les lettres en attente (retour au chevalet).
    btnAnnuler.addEventListener('click', () => {
        enAttente = [];
        selection = null;
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
            res = await api.poser_mot(placements);
        } catch (err) {
            afficherMessage('Erreur inattendue lors de la validation du coup.', 'erreur');
            majControlesJeu();
            return;
        }
        if (res && res.succes) {
            // Le coup est joué : on recharge l'état (nouveau tour, chevalet remasqué)
            // et on vide l'attente. Rien n'est perdu : le moteur a consommé les lettres.
            // La modale ne s'ouvre PLUS automatiquement (issue #37) : le détail du
            // coup reste accessible à la demande via l'encart d'historique, dont la
            // ligne du coup vient d'apparaître en tête après le rafraîchissement.
            const points = res.points != null ? res.points : 0;
            await rafraichir();
            afficherMessage(`Coup joué (+${points} point${points > 1 ? 's' : ''}).`, 'succes');
            // Animation de la pose du coup humain (issue #62) : identique à celle
            // d'un coup IA. Après le rafraîchissement, la première entrée de
            // l'historique est le coup qu'on vient de valider ; on révèle ses
            // lettres une par une sur ~2,5 s (« tac » à chaque lettre) avant de
            // considérer le tour visuellement terminé.
            if (etat.historique && etat.historique[0]) {
                await animerPose(etat.historique[0].positions);
                // Scrabble posé par l'humain (bonus 50 pts, issue #64) : petit
                // feu d'artifice une fois la pose révélée.
                if (etat.historique[0].detail
                        && etat.historique[0].detail.bonus_scrabble) {
                    celebrerScrabble();
                }
            }
        } else {
            // Échec : on conserve les lettres en attente pour correction.
            const message = (res && res.erreur) ? res.erreur : 'Coup refusé.';
            afficherMessage(message, 'erreur');
            majControlesJeu();
        }
    });

    // Vérifier et calculer (issue #69) : calcule les points du coup en attente
    // SANS le jouer. Aucune lettre en attente n'est perdue, aucun tour n'est
    // consommé : on affiche seulement les points (si valide) ou un message
    // d'erreur clair (si invalide), puis on restaure les contrôles.
    btnVerifierCoup.addEventListener('click', async () => {
        if (!enAttente.length) {
            return;
        }
        btnVerifierCoup.disabled = true;
        const placements = enAttente.map(p => ({
            ligne: p.ligne,
            colonne: p.colonne,
            lettre: p.lettre,
            joker: p.joker,
        }));
        let res;
        try {
            res = await api.verifier_coup(placements);
        } catch (err) {
            afficherMessage('Erreur inattendue lors de la vérification du coup.', 'erreur');
            majControlesJeu();
            return;
        }
        if (res && res.succes) {
            const points = res.points != null ? res.points : 0;
            const mot = (res.detail && res.detail.mots && res.detail.mots[0])
                ? res.detail.mots[0].texte : null;
            const detailMot = mot ? ` (${mot})` : '';
            afficherMessage(
                `Coup valide${detailMot} : +${points} point${points > 1 ? 's' : ''}. `
                + `Cliquez « Jouer » pour le poser.`,
                'succes');
        } else {
            const message = (res && res.erreur) ? res.erreur : 'Coup invalide.';
            afficherMessage(message, 'erreur');
        }
        // Les lettres en attente restent en place : on réactive les contrôles.
        majControlesJeu();
    });

    /**
     * Lit le thème visuel choisi dans les réglages (champ auto-réparant côté
     * Python) et l'applique au plateau : pose la classe CSS ``theme-<nom>`` (qui
     * ne redéfinit que des variables de couleur/contraste) et sélectionne le jeu
     * de libellés affichés dans les cases (abrégés pour « abrege », complets
     * sinon). Une valeur inconnue retombe sur « classique » par sécurité.
     */
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
        labelVisible = (theme === 'abrege') ? LABEL_ABREGE : LABEL_COMPLET;
        // Retire les anciennes classes de thème avant de poser la nouvelle.
        THEMES.forEach(t => plateauEl.classList.remove(`theme-${t}`));
        plateauEl.classList.add(`theme-${theme}`);
    }

    // --- Initialisation ---
    await appliquerTheme();
    await rafraichir();
});
