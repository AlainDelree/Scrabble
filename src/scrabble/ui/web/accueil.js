/**
 * Écran d'accueil - Configuration de partie Scrabble
 *
 * Communique avec l'API Python via pywebview.api.*
 */

document.addEventListener('DOMContentLoaded', async () => {
    // Attendre que le pont pywebview soit VRAIMENT prêt (issue #145).
    //
    // pywebview pose ``window.pywebview`` (jeton/infos plateforme) AVANT de
    // publier ``window.pywebview.api`` (les méthodes Python exposées). L'ancien
    // test ``if (window.pywebview)`` résolvait donc la promesse trop tôt :
    // ``api`` capturait l'objet encore dépourvu de méthodes et le premier
    // ``await api.obtenir_etat()`` (tout en bas de l'initialisation) échouait
    // silencieusement — l'écran restait donc vide. C'est ce qui masquait le
    // joueur humain ajouté d'office par #141 : l'ajout côté Python avait bien
    // lieu, mais le rendu initial ne s'exécutait jamais, donnant l'illusion que
    // rien n'avait changé. On attend désormais ``window.pywebview.api``, comme
    // ``commun.js`` et ``reglages.js`` (``{ once: true }`` pour ne pas laisser
    // traîner l'écouteur).
    await new Promise(resolve => {
        if (window.pywebview && window.pywebview.api) {
            resolve();
        } else {
            window.addEventListener('pywebviewready', resolve, { once: true });
        }
    });

    const api = window.pywebview.api;

    // Éléments du DOM
    const listeJoueurs = document.getElementById('liste-joueurs');
    const messageVide = document.getElementById('message-vide');
    const nbHumains = document.getElementById('nb-humains');
    const nbOrdinateurs = document.getElementById('nb-ordinateurs');
    const btnAjouterHumain = document.getElementById('btn-ajouter-humain');
    const btnAjouterOrdinateur = document.getElementById('btn-ajouter-ordinateur');
    const btnLancer = document.getElementById('btn-lancer');

    // Modales
    const modaleHumain = document.getElementById('modale-humain');
    const modaleOrdinateur = document.getElementById('modale-ordinateur');
    const modaleTirage = document.getElementById('modale-tirage');
    const tirageLettres = document.getElementById('tirage-lettres');
    const tirageOrdreResultat = document.getElementById('tirage-ordre-resultat');
    const tirageSacZone = document.getElementById('tirage-sac-zone');
    const tirageSacAction = document.getElementById('tirage-sac-action');
    const btnContinuerTirage = document.getElementById('btn-continuer-tirage');
    const btnAnnulerTirage = document.getElementById('btn-annuler-tirage');

    // Formulaires
    const formHumain = document.getElementById('form-humain');
    const formOrdinateur = document.getElementById('form-ordinateur');
    const inputPrenom = document.getElementById('input-prenom');
    const checkboxSauvegarder = document.getElementById('checkbox-sauvegarder');
    const listeNiveaux = document.getElementById('liste-niveaux');

    // Parties en cours
    const sectionReprise = document.getElementById('section-reprise');
    const partiesEnCours = document.getElementById('parties-en-cours');

    // Bouton réglages (issue #111)
    const btnReglages = document.getElementById('btn-reglages');

    // État
    let premierHumainAjoute = false;

    /**
     * Met à jour l'affichage en fonction de l'état reçu
     */
    function mettreAJourAffichage(etat) {
        // Vider et reconstruire la liste
        listeJoueurs.innerHTML = '';

        if (etat.joueurs.length === 0) {
            listeJoueurs.innerHTML = '<p class="vide" id="message-vide">Aucun joueur. Ajoutez des joueurs pour commencer.</p>';
        } else {
            etat.joueurs.forEach((joueur, index) => {
                const item = document.createElement('div');
                item.className = `joueur-item ${joueur.humain ? 'humain' : 'ordinateur'}`;

                // Avatar configuré du joueur humain de référence (issue #148) :
                // s'il est fourni par Python, on affiche le portrait SVG choisi
                // dans les réglages (le même que celui utilisé pendant la partie),
                // sinon on retombe sur l'icône générique 👤 / 🖥️.
                const icone = joueur.avatar
                    ? `<img class="joueur-avatar" src="avatars/${encodeURIComponent(joueur.avatar)}.svg" alt="" width="28" height="28">`
                    : `<span class="joueur-icone">${joueur.humain ? '👤' : '🖥️'}</span>`;
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
                    ${icone}
                    <div class="joueur-info">
                        <div class="joueur-nom">${escapeHtml(joueur.nom)}</div>
                        <div class="joueur-type">${typeLabel}</div>
                    </div>
                    <button class="btn-retirer" title="Retirer" data-index="${index}">✕</button>
                `;
                listeJoueurs.appendChild(item);
            });
        }

        // Compteurs
        nbHumains.textContent = etat.nb_humains;
        nbOrdinateurs.textContent = etat.nb_ordinateurs;

        // Boutons
        btnAjouterHumain.disabled = !etat.peut_ajouter_humain;
        btnAjouterOrdinateur.disabled = !etat.peut_ajouter_ordinateur;
        btnLancer.disabled = !etat.peut_lancer;

        // Messages de limite
        let messageLimite = '';
        if (!etat.peut_ajouter_humain && !etat.peut_ajouter_ordinateur) {
            messageLimite = 'Table complète (4 joueurs maximum)';
        } else if (!etat.peut_ajouter_humain) {
            messageLimite = 'Maximum 4 joueurs humains atteint';
        } else if (!etat.peut_ajouter_ordinateur) {
            messageLimite = 'Maximum 3 ordinateurs atteint';
        }

        // Supprimer l'ancien message s'il existe
        const ancienMessage = document.querySelector('.message-limite');
        if (ancienMessage) ancienMessage.remove();

        if (messageLimite) {
            const p = document.createElement('p');
            p.className = 'message-limite';
            p.textContent = messageLimite;
            document.querySelector('.actions').after(p);
        }

        // Suivre si un humain a été ajouté
        if (etat.nb_humains > 0) {
            premierHumainAjoute = true;
        }
    }

    /**
     * Échappe le HTML pour éviter les injections
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Charge et affiche les niveaux de difficulté
     */
    async function chargerNiveaux() {
        const niveaux = await api.obtenir_niveaux();
        listeNiveaux.innerHTML = '';
        niveaux.forEach((niveau, index) => {
            // Le rectangle cliquable est le <label> lui-même (issue #119) : ainsi
            // un clic n'importe où dans le rectangle (y compris le padding
            // au-dessus/en dessous du texte) sélectionne bien le bouton radio.
            const label = document.createElement('label');
            label.className = 'niveau-option';
            label.innerHTML = `
                <input type="radio" name="niveau" id="niveau-${index}" value="${niveau}" ${index === 2 ? 'checked' : ''}>
                <span class="niveau-nom">${niveau}</span>
            `;
            listeNiveaux.appendChild(label);
        });
    }

    /**
     * Charge et affiche les parties proposées à l'accueil.
     *
     * Depuis les issues #54 et #150, `api.lister_parties_en_cours()` renvoie au
     * plus deux encarts (0 à 2 éléments) : la partie en cours la plus récente à
     * reprendre, et la partie terminée la plus récente à consulter. Une partie
     * terminée (`partie.terminee`) porte un badge « Terminée » et son bouton
     * s'intitule « Consulter » (il ouvre l'écran de jeu sur le plateau final,
     * modale de fin de partie #138 affichée) plutôt que « Reprendre ».
     */
    async function chargerPartiesEnCours() {
        const parties = await api.lister_parties_en_cours();
        partiesEnCours.innerHTML = '';

        if (parties.length === 0) {
            partiesEnCours.innerHTML = '<p class="vide">Aucune partie enregistrée.</p>';
            return;
        }

        parties.forEach(partie => {
            const item = document.createElement('div');
            item.className = 'partie-item';

            const date = new Date(partie.date_maj);
            const dateStr = date.toLocaleDateString('fr-FR', {
                day: 'numeric',
                month: 'short',
                hour: '2-digit',
                minute: '2-digit'
            });

            // Chaque joueur est un objet {nom, score} depuis l'issue #76 : on
            // affiche le score courant à côté du nom (ex. « Alice (14 pts) »).
            const joueursStr = partie.joueurs
                .map(j => `${escapeHtml(j.nom)} (${j.score} pts)`)
                .join(', ');

            // Partie terminée (issue #150) : badge « Terminée » + bouton
            // « Consulter » ; libellé de date adapté.
            const terminee = Boolean(partie.terminee);
            const badge = terminee
                ? '<span class="partie-badge">Terminée</span>'
                : '';
            const libelleBouton = terminee ? 'Consulter' : 'Reprendre';
            const libelleDate = terminee ? 'Terminée le' : 'Dernière activité';

            item.innerHTML = `
                <div class="partie-info">
                    <div class="partie-joueurs">${joueursStr}${badge}</div>
                    <div class="partie-date">${libelleDate} : ${dateStr}</div>
                </div>
                <button class="btn btn-reprendre" data-id="${partie.id}">${libelleBouton}</button>
            `;
            partiesEnCours.appendChild(item);
        });
    }

    /**
     * Ferme la fenêtre d'accueil depuis Python (issue #53).
     *
     * Appelle `api.fermer_fenetre()` qui déclenche `window.destroy()` côté
     * Python — plus fiable que `window.close()` côté JS, ignoré par certains
     * backends pywebview (GTK/WebKit sous Linux).
     *
     * Filet de sécurité : on ne signale un échec (via `onEchec(message)`, qui
     * réactive le bouton) que si `fermer_fenetre()` renvoie explicitement un
     * échec ou lève une exception. On se fie donc uniquement à la réponse de
     * `fermer_fenetre()` : si elle réussit, `window.destroy()` a été demandé et
     * la fenêtre est détruite — le reste du JS n'a plus d'effet visible.
     *
     * Historique (issue #57) : un timer de 3 s (issue #53) affichait à tort
     * « La fenêtre n'a pas pu se fermer » sur une fermeture pourtant réussie.
     * Cause : sur une fermeture réussie, `fermer_fenetre()` renvoie
     * `{succes: true}` immédiatement mais la destruction effective de la fenêtre
     * (backend GTK/WebKit) est traitée sur la boucle d'événements GUI, avec une
     * latence variable (accentuée par l'ouverture concurrente de la fenêtre de
     * jeu). Quand cette latence dépassait 3 s, le timer — laissé volontairement
     * en place en cas de succès — se déclenchait alors que tout allait bien. Le
     * timeout arbitraire est donc supprimé : `destroy()` ne peut pas « échouer
     * en silence » (une vraie erreur remonte via l'exception capturée côté
     * Python et renvoyée dans `result.erreur`).
     *
     * @param {function(string): void} onEchec Rappel en cas d'échec réel.
     */
    async function fermerFenetre(onEchec) {
        try {
            const result = await api.fermer_fenetre();
            if (!result || !result.succes) {
                const msg = (result && result.erreur)
                    ? result.erreur
                    : "Impossible de fermer la fenêtre.";
                onEchec(msg);
            }
            // En cas de succès : la fenêtre est détruite, rien à faire de plus.
        } catch (err) {
            onEchec("Erreur lors de la fermeture : " + err);
        }
    }

    const DELAI_LIGNE = 450;  // ms entre deux révélations de lettre

    /** Petite promesse d'attente (ms). */
    function attendre(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Tour d'un joueur HUMAIN dans le tirage d'ordre (issue #61, simplifié
     * issue #166) : au lieu de révéler automatiquement sa lettre, on affiche
     * une simple image STATIQUE du sac de lettres avec, juste en dessous, le
     * bouton « Tirer une lettre » qui dévoile sa lettre.
     *
     * La mécanique de « secouage » du sac (suivi du curseur + son, issues
     * #61/#68/#71) a été retirée : elle n'affichait plus correctement le sac
     * pendant l'animation et n'apportait rien au flux. Le reste (révélation de
     * la lettre au clic, suite de la séquence) est inchangé.
     *
     * @param {HTMLElement} li Ligne de résultat correspondante (nom + lettre).
     * @param {{nom: string, lettre: string}} t Tirage du joueur humain.
     * @returns {Promise<void>} résolue une fois la lettre tirée.
     */
    function tourHumain(li, t) {
        return new Promise((resolve) => {
            // La ligne apparaît, mais la lettre reste masquée jusqu'au tirage.
            li.classList.add('visible', 'en-attente-tirage');

            // Corps scrollable : consigne + image statique du sac de lettres.
            tirageSacZone.hidden = false;
            tirageSacZone.innerHTML = `
                <p class="tirage-sac-consigne">À toi, ${escapeHtml(t.nom)} ! Tire ta lettre.</p>
                <div class="tirage-sac" role="img" aria-label="Sac de lettres">
                    <svg viewBox="0 0 100 110" width="120" height="132" aria-hidden="true">
                        <path class="tirage-sac-corps" d="M22 42 Q50 28 78 42 L88 96 Q50 112 12 96 Z"/>
                        <path class="tirage-sac-col" d="M34 40 Q50 22 66 40 Q50 34 34 40 Z"/>
                        <line class="tirage-sac-cordon" x1="34" y1="40" x2="66" y2="40"/>
                        <text class="tirage-sac-glyphe" x="50" y="80" text-anchor="middle">?</text>
                    </svg>
                </div>
            `;

            // Zone épinglée (issue #116), hors du corps scrollable : le bouton
            // « Tirer une lettre » reste visible par construction, comme
            // Annuler / Continuer, quelle que soit la taille de fenêtre.
            tirageSacAction.hidden = false;
            tirageSacAction.innerHTML =
                '<button type="button" class="btn btn-primaire tirage-sac-bouton">Tirer une lettre</button>';

            const bouton = tirageSacAction.querySelector('.tirage-sac-bouton');

            bouton.addEventListener('click', () => {
                li.classList.remove('en-attente-tirage');  // dévoile la lettre
                tirageSacZone.hidden = true;
                tirageSacZone.innerHTML = '';
                tirageSacAction.hidden = true;
                tirageSacAction.innerHTML = '';
                resolve();
            }, { once: true });
        });
    }

    /**
     * Affiche le résultat du tirage d'ordre (issue #54) et attend que
     * l'utilisateur clique « Continuer » avant de résoudre.
     *
     * Les joueurs ordinateurs sont révélés séquentiellement en fondu (issue
     * #58). Pour chaque joueur HUMAIN, la révélation automatique est remplacée
     * par une image statique du sac + un bouton « Tirer une lettre » (issue
     * #61, simplifié #166) : la séquence se met en pause jusqu'au clic sur
     * « Tirer une lettre », puis reprend. Le résultat « Ordre de jeu : … »
     * n'apparaît qu'une fois TOUTES les lettres révélées.
     *
     * Deux garde-fous (issue #67) :
     * - « Continuer » reste désactivé tant que TOUS les tirages ne sont pas
     *   terminés (y compris le tirage du/des joueurs humains) ; il ne devient
     *   actif qu'une fois l'ordre de jeu final affiché.
     * - « Annuler » est actif à tout moment : un clic supprime la partie
     *   fraîchement créée (``api.annuler_partie_creee()``) et interrompt la
     *   séquence, même en plein tour humain, pour revenir à la configuration.
     *
     * @param {{tirages: Array<{nom: string, lettre: string, humain: boolean}>, ordre: string[]}} tirage
     * @returns {Promise<boolean>} ``true`` si l'utilisateur valide (« Continuer »),
     *   ``false`` s'il annule (« Annuler ») — la partie créée est alors supprimée.
     */
    /**
     * Mesure la géométrie réelle de la modale de tirage et la transmet au
     * journal Python (issue #116). Sert à objectiver, en conditions réelles
     * WebKitGTK, la hauteur réellement disponible dans la fenêtre — là où les
     * mesures headless Chromium des issues #83/#115 ont échoué deux fois.
     * Best-effort : toute erreur (API absente en test, DOM incomplet) est
     * silencieusement ignorée, la trace ne doit jamais gêner le tirage.
     */
    function journaliserGeometrieTirage() {
        try {
            if (!api || typeof api.journaliser_mesure_fenetre !== 'function') return;
            const contenu = modaleTirage.querySelector('.modale-contenu');
            const corps = modaleTirage.querySelector('.modale-corps');
            const arrondi = (v) => Math.round(v);
            api.journaliser_mesure_fenetre({
                fenetre_innerHeight: window.innerHeight,
                fenetre_innerWidth: window.innerWidth,
                vh40_px: arrondi(window.innerHeight * 0.40),
                contenu_hauteur: contenu ? arrondi(contenu.getBoundingClientRect().height) : null,
                corps_client: corps ? corps.clientHeight : null,
                corps_scroll: corps ? corps.scrollHeight : null,
            });
        } catch (_e) {
            /* trace best-effort : on ignore toute erreur */
        }
    }

    async function afficherTirageOrdre(tirage) {
        tirageLettres.innerHTML = '';
        tirageOrdreResultat.textContent = '';
        tirageOrdreResultat.classList.remove('visible');
        tirageSacZone.hidden = true;
        tirageSacZone.innerHTML = '';
        tirageSacAction.hidden = true;
        tirageSacAction.innerHTML = '';

        // La modale est réutilisée d'un lancement à l'autre : on force « Continuer »
        // à l'état désactivé tant que le tirage n'est pas mené à son terme.
        btnContinuerTirage.disabled = true;

        const lignes = tirage.tirages.map(t => {
            const li = document.createElement('li');
            li.innerHTML = `<span class="tirage-nom">${escapeHtml(t.nom)}</span> a tiré <span class="tirage-lettre">${escapeHtml(t.lettre)}</span>`;
            tirageLettres.appendChild(li);
            return li;
        });

        afficherModale(modaleTirage);

        // Diagnostic (issue #116) : après deux correctifs de taille inopérants en
        // conditions réelles, on objective la géométrie effective sous WebKitGTK
        // en la transmettant au journal Python — plus fiable qu'une mesure
        // headless Chromium. Purement informatif, tolérant à l'échec.
        journaliserGeometrieTirage();

        // Promesse d'annulation : « Annuler » peut résoudre à tout instant, même
        // pendant que la séquence de révélation attend un tour humain.
        const annulation = new Promise((resolve) => {
            btnAnnulerTirage.onclick = () => resolve(true);
        });

        // Séquence de révélation, puis attente du clic « Continuer ».
        const sequence = (async () => {
            for (let i = 0; i < lignes.length; i++) {
                const t = tirage.tirages[i];
                if (t.humain) {
                    await tourHumain(lignes[i], t);
                } else {
                    await attendre(DELAI_LIGNE);
                    lignes[i].classList.add('visible');
                }
            }

            await attendre(DELAI_LIGNE);
            tirageOrdreResultat.textContent =
                'Ordre de jeu : ' + tirage.ordre.map(String).join(', ');
            tirageOrdreResultat.classList.add('visible');

            // Tirage terminé : « Continuer » devient enfin actif.
            btnContinuerTirage.disabled = false;
            await new Promise((resolve) => {
                btnContinuerTirage.onclick = () => resolve();
            });
            return false;  // validation normale
        })();

        const annule = await Promise.race([annulation, sequence]);

        // Nettoyage des gestionnaires (la séquence peut rester orpheline si
        // l'annulation l'emporte pendant un tour humain — la modale est cachée).
        btnContinuerTirage.onclick = null;
        btnAnnulerTirage.onclick = null;
        tirageSacZone.hidden = true;
        tirageSacZone.innerHTML = '';
        tirageSacAction.hidden = true;
        tirageSacAction.innerHTML = '';

        if (annule) {
            // Supprime la partie créée entre-temps de la persistance (issue #67).
            await api.annuler_partie_creee();
        }
        cacherModale(modaleTirage);
        return !annule;
    }

    /**
     * Affiche une modale
     */
    function afficherModale(modale) {
        modale.hidden = false;
    }

    /**
     * Cache une modale
     */
    function cacherModale(modale) {
        modale.hidden = true;
    }

    // --- Gestionnaires d'événements ---

    // Bouton ajouter humain
    btnAjouterHumain.addEventListener('click', async () => {
        const prenomPrincipal = await api.obtenir_prenom_principal();

        // Si prénom principal existe ET c'est le premier humain, ajouter directement
        if (prenomPrincipal && !premierHumainAjoute) {
            const result = await api.ajouter_humain(prenomPrincipal, false);
            if (result.succes) {
                mettreAJourAffichage(result.etat);
                return;
            }
        }

        // Sinon, ouvrir la modale
        inputPrenom.value = '';
        checkboxSauvegarder.checked = false;
        afficherModale(modaleHumain);
        inputPrenom.focus();
    });

    // Formulaire ajout humain
    formHumain.addEventListener('submit', async (e) => {
        e.preventDefault();
        const prenom = inputPrenom.value.trim();
        const sauvegarder = checkboxSauvegarder.checked;

        if (!prenom) {
            inputPrenom.focus();
            return;
        }

        const result = await api.ajouter_humain(prenom, sauvegarder);
        if (result.succes) {
            cacherModale(modaleHumain);
            mettreAJourAffichage(result.etat);
        } else {
            alert(result.erreur);
        }
    });

    // Annuler modale humain
    document.getElementById('btn-annuler-humain').addEventListener('click', () => {
        cacherModale(modaleHumain);
    });

    // Bouton ajouter ordinateur
    btnAjouterOrdinateur.addEventListener('click', () => {
        afficherModale(modaleOrdinateur);
    });

    // Formulaire ajout ordinateur
    formOrdinateur.addEventListener('submit', async (e) => {
        e.preventDefault();
        const niveauRadio = document.querySelector('input[name="niveau"]:checked');
        if (!niveauRadio) {
            alert('Veuillez sélectionner un niveau.');
            return;
        }

        const result = await api.ajouter_ordinateur(niveauRadio.value);
        if (result.succes) {
            cacherModale(modaleOrdinateur);
            mettreAJourAffichage(result.etat);
        } else {
            alert(result.erreur);
        }
    });

    // Annuler modale ordinateur
    document.getElementById('btn-annuler-ordinateur').addEventListener('click', () => {
        cacherModale(modaleOrdinateur);
    });

    // Retirer un joueur (délégation d'événement)
    listeJoueurs.addEventListener('click', async (e) => {
        if (e.target.classList.contains('btn-retirer')) {
            const index = parseInt(e.target.dataset.index, 10);
            const result = await api.retirer_joueur(index);
            if (result.succes) {
                mettreAJourAffichage(result.etat);
                // Réinitialiser si plus d'humain
                const etat = result.etat;
                if (etat.nb_humains === 0) {
                    premierHumainAjoute = false;
                }
            }
        }
    });

    // Lancer la partie
    btnLancer.addEventListener('click', async () => {
        btnLancer.disabled = true;
        btnLancer.textContent = 'Création en cours...';

        const result = await api.lancer_partie();

        if (result.succes && result.pret) {
            // Montrer le résultat du tirage d'ordre avant de fermer l'accueil
            // (issue #54) : l'utilisateur voit la lettre tirée par chaque
            // joueur et l'ordre de jeu qui en résulte, puis clique « Continuer ».
            if (result.tirage_ordre) {
                const continuer = await afficherTirageOrdre(result.tirage_ordre);
                if (!continuer) {
                    // Annulation (issue #67) : la partie créée a été supprimée de
                    // la persistance. On revient à la configuration des joueurs
                    // sans fermer l'accueil ni ouvrir l'écran de jeu. Le bouton
                    // est réactivé et la liste de reprise rafraîchie (la partie
                    // fantôme ne doit plus y figurer).
                    btnLancer.disabled = false;
                    btnLancer.textContent = 'Lancer la partie';
                    await chargerPartiesEnCours();
                    return;
                }
            }
            // Fermer la fenêtre d'accueil depuis Python — l'écran de jeu
            // s'ouvrira automatiquement après la fermeture. En cas d'échec,
            // on réactive le bouton plutôt que de rester bloqué.
            await fermerFenetre((msg) => {
                alert(msg);
                btnLancer.disabled = false;
                btnLancer.textContent = 'Lancer la partie';
            });
        } else if (!result.succes) {
            alert(result.erreur);
            btnLancer.disabled = false;
            btnLancer.textContent = 'Lancer la partie';
        }
    });

    // Reprendre une partie (délégation d'événement)
    partiesEnCours.addEventListener('click', async (e) => {
        if (e.target.classList.contains('btn-reprendre')) {
            const id = parseInt(e.target.dataset.id, 10);
            const btnReprendre = e.target;
            // Libellé d'origine (« Reprendre » ou « Consulter » pour une partie
            // terminée, issue #150) à restaurer en cas d'échec.
            const libelleInitial = btnReprendre.textContent;
            btnReprendre.disabled = true;
            btnReprendre.textContent = 'Chargement...';

            const result = await api.reprendre(id);
            if (result.succes && result.pret) {
                // Fermer la fenêtre d'accueil depuis Python — l'écran de jeu
                // s'ouvrira automatiquement après la fermeture. En cas
                // d'échec, on réactive le bouton plutôt que de rester bloqué.
                await fermerFenetre((msg) => {
                    alert(msg);
                    btnReprendre.disabled = false;
                    btnReprendre.textContent = libelleInitial;
                });
            } else if (!result.succes) {
                alert(result.erreur);
                btnReprendre.disabled = false;
                btnReprendre.textContent = libelleInitial;
            }
        }
    });

    // Ouvrir la fenêtre de réglages à onglets (issue #111). Elle s'ouvre comme
    // seconde fenêtre par-dessus l'accueil ; à sa fermeture on revient ici.
    btnReglages.addEventListener('click', async () => {
        btnReglages.disabled = true;
        try {
            const res = await api.ouvrir_reglages();
            if (res && !res.succes) {
                alert(res.erreur || 'Impossible d\'ouvrir les réglages.');
            }
        } finally {
            btnReglages.disabled = false;
        }
    });

    // Fermer modales avec Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (!modaleHumain.hidden) cacherModale(modaleHumain);
            if (!modaleOrdinateur.hidden) cacherModale(modaleOrdinateur);
        }
    });

    // Clic en dehors de la modale pour fermer
    [modaleHumain, modaleOrdinateur].forEach(modale => {
        modale.addEventListener('click', (e) => {
            if (e.target === modale) {
                cacherModale(modale);
            }
        });
    });

    // --- Initialisation ---
    const etatInitial = await api.obtenir_etat();
    mettreAJourAffichage(etatInitial);
    await chargerNiveaux();
    await chargerPartiesEnCours();
});
