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

    // Modales (le tirage d'ordre a migré vers la fenêtre Jeu — issue #170).
    const modaleHumain = document.getElementById('modale-humain');
    const modaleOrdinateur = document.getElementById('modale-ordinateur');

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
                        'AVANCE': 'Avancé',
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

        // Boutons.
        //
        // Un seul joueur humain est autorisé (issue #175) : le bouton « Ajouter
        // un joueur » DISPARAÎT complètement dès qu'un humain est présent (pas de
        // désactivation grisée ni de tooltip) et réapparaît si l'humain est
        // retiré. On pilote donc sa visibilité (``hidden``) et non son état
        // ``disabled``. Le bouton « Ajouter un ordinateur » garde, lui, son
        // comportement historique (désactivé quand la table est pleine).
        btnAjouterHumain.hidden = !etat.peut_ajouter_humain;
        btnAjouterOrdinateur.disabled = !etat.peut_ajouter_ordinateur;
        btnLancer.disabled = !etat.peut_lancer;

        // Messages de limite. La saturation du quota d'humains n'est plus un
        // message affiché (le bouton disparaît silencieusement, issue #175) : ne
        // subsiste que l'information relative aux ordinateurs / à la table pleine.
        let messageLimite = '';
        if (!etat.peut_ajouter_ordinateur) {
            messageLimite = etat.nb_total >= 4
                ? 'Table complète (4 joueurs maximum)'
                : 'Maximum 3 ordinateurs atteint';
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

    /**
     * Transition Accueil→Jeu adaptée au contexte d'exécution (issue #180).
     *
     * Ce fichier est PARTAGÉ par deux coquilles ; on choisit le comportement de
     * transition dynamiquement, sans dupliquer le fichier ni casser la production :
     *
     *  - Chemin de PRODUCTION (`lancer_accueil`/`lancer_jeu`) : l'accueil est une
     *    fenêtre pywebview distincte, détruite après le lancement. On ferme donc la
     *    fenêtre (`api.fermer_fenetre()` → `window.destroy()` côté Python) ; la
     *    boucle rend la main et `lancer_jeu(...)` ouvre l'écran de jeu dans une
     *    nouvelle fenêtre. Comportement historique, INCHANGÉ.
     *
     *  - Coquille UNIFIÉE mono-fenêtre (`lancer_application_unifiee`, issues
     *    #179/#180) : une seule fenêtre physique navigue de `accueil.html` à
     *    `jeu.html` via `load_url`, sans destruction ni recréation. On appelle
     *    alors `api.demarrer_jeu()`, méthode de contrôle du routeur (`ApiRouteur`)
     *    qui charge la partie, bascule la vue et navigue.
     *
     * Détection : la présence de `api.demarrer_jeu` (méthode propre au routeur
     * unifié, ABSENTE de l'`ApiAccueil` de production) distingue les deux
     * contextes. En son absence, on retombe sur `fermerFenetre` — le chemin de
     * production reste strictement intact.
     *
     * @param {function(string): void} onEchec Rappel en cas d'échec réel.
     */
    async function transiterVersJeu(onEchec) {
        if (typeof api.demarrer_jeu === 'function') {
            // Coquille unifiée : navigation load_url dans la même fenêtre.
            try {
                const result = await api.demarrer_jeu();
                if (!result || !result.succes) {
                    const msg = (result && result.erreur)
                        ? result.erreur
                        : "Impossible de démarrer le jeu.";
                    onEchec(msg);
                }
                // En cas de succès : la fenêtre a navigué vers jeu.html.
            } catch (err) {
                onEchec("Erreur au démarrage du jeu : " + err);
            }
        } else {
            // Chemin de production : fermeture de la fenêtre d'accueil.
            await fermerFenetre(onEchec);
        }
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
            // Le tirage d'ordre n'est plus affiché ici (issue #170) : la fenêtre
            // Jeu s'ouvre en état « pré-partie » (écran de tirage affiché à la
            // place du plateau). Transition adaptée au contexte (issue #180) :
            // fermeture de la fenêtre (production) ou navigation load_url (coquille
            // unifiée). En cas d'échec, on réactive le bouton plutôt que de bloquer.
            await transiterVersJeu((msg) => {
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
                // Transition adaptée au contexte (issue #180) : fermeture de la
                // fenêtre (production) ou navigation load_url dans la même fenêtre
                // (coquille unifiée). En cas d'échec, on réactive le bouton plutôt
                // que de rester bloqué.
                await transiterVersJeu((msg) => {
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

    // =====================================================================
    // Panneau Réglages intégré (issue #169).
    //
    // Les réglages ne sont plus une fenêtre pywebview séparée : c'est une
    // seconde VUE de la fenêtre d'accueil (``#vue-reglages``), montrée à la
    // place de la vue configuration (``#vue-config``) au clic sur ⚙, et masquée
    // au clic sur « Fermer » (ou Échap). Toute la logique de l'ex-``reglages.js``
    // est reprise ici et parle à la même ``ApiAccueil`` (méthodes migrées).
    // =====================================================================
    const vueConfig = document.getElementById('vue-config');
    const vueReglages = document.getElementById('vue-reglages');
    const btnFermerReglages = document.getElementById('btn-fermer-reglages');

    // Libellés des sources, renseignés depuis Python au premier chargement.
    let labelsSources = { ods: 'ODS 8', hunspell: 'Hunspell' };
    // Chargement paresseux : on ne peuple l'onglet Général qu'à la première
    // ouverture du panneau (inutile tant que l'utilisateur reste en config).
    let reglagesCharges = false;

    // ---- Onglets (bascule pur CSS/JS, aria-selected pour l'a11y) ----
    const onglets = vueReglages.querySelectorAll('.onglet');
    const panneaux = vueReglages.querySelectorAll('.panneau');

    function activerOnglet(onglet) {
        onglets.forEach((o) => {
            const actif = o === onglet;
            o.classList.toggle('active', actif);
            o.setAttribute('aria-selected', actif ? 'true' : 'false');
        });
        panneaux.forEach((p) => {
            p.classList.toggle('active', p.id === onglet.dataset.panneau);
        });
    }

    onglets.forEach((onglet) => {
        onglet.addEventListener('click', () => activerOnglet(onglet));
    });

    // ---- Onglet Général ----
    const inputPrenomPrincipal = document.getElementById('input-prenom-principal');
    const grilleAvatars = document.getElementById('grille-avatars');
    const selectTheme = document.getElementById('select-theme');
    const selectSource = document.getElementById('select-source');
    const checkBonusFin = document.getElementById('check-bonus-fin');
    const checkVocabulaireHumain = document.getElementById('check-vocabulaire-humain');
    const radiosTypeEchange = document.getElementById('radios-type-echange');
    const statutGeneral = document.getElementById('statut-general');

    let horlogeStatut = null;

    /** Affiche un court message d'enregistrement (vert, ou rouge si erreur). */
    function afficherStatutGeneral(message, erreur) {
        statutGeneral.textContent = message;
        statutGeneral.classList.toggle('erreur', Boolean(erreur));
        statutGeneral.hidden = false;
        if (horlogeStatut) {
            clearTimeout(horlogeStatut);
        }
        horlogeStatut = setTimeout(() => {
            statutGeneral.hidden = true;
        }, 2500);
    }

    /** Construit un groupe de boutons radio [{valeur, libelle}] + valeur active.
     *  Chaque changement enregistre le réglage ``cle`` via l'API Python. */
    function remplirRadios(conteneur, cle, options, valeurActive) {
        conteneur.innerHTML = '';
        (options || []).forEach((opt) => {
            const label = document.createElement('label');
            label.className = 'radio-label';
            const input = document.createElement('input');
            input.type = 'radio';
            input.name = cle;
            input.value = opt.valeur;
            input.checked = opt.valeur === valeurActive;
            input.addEventListener('change', async () => {
                if (!input.checked) {
                    return;
                }
                const retenue = await enregistrerReglage(cle, input.value);
                // La normalisation Python peut retomber sur une autre valeur : on
                // resynchronise le groupe pour ne pas afficher un choix trompeur.
                if (retenue && retenue !== input.value) {
                    syncRadios(conteneur, retenue);
                }
            });
            const span = document.createElement('span');
            span.textContent = opt.libelle;
            label.appendChild(input);
            label.appendChild(span);
            conteneur.appendChild(label);
        });
    }

    /** Recoche l'option ``valeur`` d'un groupe de radios (après normalisation). */
    function syncRadios(conteneur, valeur) {
        conteneur.querySelectorAll('input[type="radio"]').forEach((input) => {
            input.checked = input.value === valeur;
        });
    }

    /** Avatar actuellement choisi (identifiant, ou '' pour « aucun choix »). */
    let avatarChoisi = '';

    /** Met en évidence la vignette sélectionnée dans la grille d'avatars. */
    function syncGrilleAvatars() {
        grilleAvatars.querySelectorAll('.avatar-vignette').forEach((btn) => {
            const actif = btn.dataset.valeur === avatarChoisi;
            btn.classList.toggle('actif', actif);
            btn.setAttribute('aria-checked', actif ? 'true' : 'false');
        });
    }

    /** Construit la grille de vignettes d'avatars [{valeur, image}] + choix actif.
     *  Un clic sélectionne l'avatar ; re-cliquer celui déjà choisi le désélectionne
     *  (retour à « aucun choix »), enregistré via l'API Python. */
    function remplirGrilleAvatars(avatars, valeurActive) {
        avatarChoisi = valeurActive || '';
        grilleAvatars.innerHTML = '';
        (avatars || []).forEach((av) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'avatar-vignette';
            btn.dataset.valeur = av.valeur;
            btn.setAttribute('role', 'radio');
            btn.setAttribute('aria-checked', 'false');
            btn.setAttribute('aria-label', av.valeur);
            btn.title = av.valeur;
            const img = document.createElement('img');
            img.src = av.image;
            img.alt = '';
            btn.appendChild(img);
            btn.addEventListener('click', async () => {
                // Toggle : re-cliquer l'avatar courant revient à « aucun choix ».
                const cible = av.valeur === avatarChoisi ? '' : av.valeur;
                const retenue = await enregistrerReglage('avatar_principal', cible);
                if (retenue !== null) {
                    avatarChoisi = retenue;
                    syncGrilleAvatars();
                }
            });
            grilleAvatars.appendChild(btn);
        });
        syncGrilleAvatars();
    }

    /** Remplit un <select> à partir d'options [{valeur, libelle}] + valeur active. */
    function remplirSelect(select, options, valeurActive) {
        select.innerHTML = '';
        options.forEach((opt) => {
            const el = document.createElement('option');
            el.value = opt.valeur;
            el.textContent = opt.libelle;
            if (opt.valeur === valeurActive) {
                el.selected = true;
            }
            select.appendChild(el);
        });
    }

    async function chargerGeneral() {
        const r = await api.obtenir_reglages_generaux();
        inputPrenomPrincipal.value = r.prenom_principal || '';
        remplirGrilleAvatars(r.avatars, r.avatar_principal);
        remplirSelect(selectTheme, r.themes, r.theme_plateau);
        remplirSelect(selectSource, r.sources, r.source_dictionnaire);
        checkBonusFin.checked = Boolean(r.bonus_fin_partie);
        checkVocabulaireHumain.checked = Boolean(r.vocabulaire_humain);
        remplirRadios(radiosTypeEchange, 'type_echange', r.types_echange, r.type_echange);
        labelsSources = {};
        (r.sources || []).forEach((s) => { labelsSources[s.valeur] = s.libelle; });
    }

    /** Enregistre un réglage et signale le résultat. */
    async function enregistrerReglage(cle, valeur) {
        const res = await api.enregistrer_reglage(cle, valeur);
        if (res.succes) {
            afficherStatutGeneral('Changement sauvé automatiquement', false);
            return res.valeur;
        }
        afficherStatutGeneral(res.erreur || 'Échec de l\'enregistrement.', true);
        return null;
    }

    // Le prénom est en texte libre : on enregistre à la perte de focus.
    inputPrenomPrincipal.addEventListener('change', () => {
        enregistrerReglage('prenom_principal', inputPrenomPrincipal.value.trim());
    });
    selectTheme.addEventListener('change', () => {
        enregistrerReglage('theme_plateau', selectTheme.value);
    });
    selectSource.addEventListener('change', async () => {
        const retenue = await enregistrerReglage('source_dictionnaire', selectSource.value);
        // La normalisation Python peut retomber sur une autre valeur : on
        // resynchronise le menu pour ne pas laisser un choix trompeur affiché.
        if (retenue && retenue !== selectSource.value) {
            selectSource.value = retenue;
        }
    });
    // Case booléenne : on transmet un vrai booléen (accepté par modifier_reglage
    // pour les clés booléennes) et on resynchronise sur la valeur retenue.
    checkBonusFin.addEventListener('change', async () => {
        const retenue = await enregistrerReglage('bonus_fin_partie', checkBonusFin.checked);
        if (retenue !== null) {
            checkBonusFin.checked = Boolean(retenue);
        }
    });
    // Vocabulaire humain (issue #206) : même schéma booléen que le bonus.
    checkVocabulaireHumain.addEventListener('change', async () => {
        const retenue = await enregistrerReglage(
            'vocabulaire_humain', checkVocabulaireHumain.checked);
        if (retenue !== null) {
            checkVocabulaireHumain.checked = Boolean(retenue);
        }
    });

    // ---- Onglet Dictionnaire ----
    const formRecherche = document.getElementById('form-recherche');
    const inputMot = document.getElementById('input-mot');
    const btnRechercher = document.getElementById('btn-rechercher');
    const chargement = document.getElementById('chargement');
    const messageDico = document.getElementById('message-dico');
    const resultat = document.getElementById('resultat');
    const resultatMot = document.getElementById('resultat-mot');
    const sourcesEl = document.getElementById('sources');
    const classiqueEl = document.getElementById('classique');
    const definitionContenu = document.getElementById('definition-contenu');

    function afficherMessageDico(texte) {
        messageDico.textContent = texte;
        messageDico.hidden = !texte;
    }

    /** Construit la carte de statut d'une source, boutons d'action compris. */
    function carteSource(source, statut) {
        const carte = document.createElement('div');
        carte.className = 'source-carte';

        let pastilleClasse = statut.present ? 'present' : 'absent';
        let pastilleTexte = statut.present ? 'Présent' : 'Absent';
        if (statut.indisponible) {
            pastilleClasse = 'indisponible';
            pastilleTexte = 'Indisponible';
        }

        // Détail de l'origine du statut (personnalisation manuelle éventuelle).
        let detail = '';
        if (statut.indisponible) {
            detail = 'Source non chargée (bibliothèque manquante ?).';
        } else if (statut.ajout_manuel) {
            detail = 'Ajouté manuellement.';
        } else if (statut.retrait_manuel) {
            detail = 'Retiré manuellement'
                + (statut.present_brut ? ' (présent d\'origine).' : '.');
        } else if (statut.present_brut) {
            detail = 'Présent d\'origine.';
        } else {
            detail = 'Absent d\'origine.';
        }

        carte.innerHTML = `
            <div class="source-titre">
                <span>${escapeHtml(labelsSources[source] || source)}</span>
                <span class="pastille ${pastilleClasse}">${pastilleTexte}</span>
            </div>
            <div class="source-detail">${escapeHtml(detail)}</div>
            <div class="source-actions"></div>
        `;

        const actions = carte.querySelector('.source-actions');
        if (!statut.indisponible) {
            const btn = document.createElement('button');
            btn.className = 'btn btn-petit '
                + (statut.present ? 'btn-retirer' : 'btn-ajouter');
            btn.textContent = statut.present ? 'Retirer' : 'Ajouter';
            btn.addEventListener('click', () => modifierMot(source, !statut.present));
            actions.appendChild(btn);
        }
        return carte;
    }

    /**
     * Construit la carte « classique du jeu » (issue #204) : étiquette portant
     * sur le mot lui-même, indépendante de la source active. Même style visuel
     * que les cartes par source, avec un bouton marquer/démarquer.
     */
    function carteClassique(statut) {
        const carte = document.createElement('div');
        carte.className = 'source-carte';

        const pastilleClasse = statut.classique ? 'present' : 'absent';
        const pastilleTexte = statut.classique ? 'Classique' : 'Non classique';
        const detail = statut.classique
            ? 'Marqué comme classique du jeu (autorisé pour l\'IA).'
            : 'Non marqué comme classique du jeu.';

        carte.innerHTML = `
            <div class="source-titre">
                <span>Classique du jeu</span>
                <span class="pastille ${pastilleClasse}">${pastilleTexte}</span>
            </div>
            <div class="source-detail">${escapeHtml(detail)}</div>
            <div class="source-actions"></div>
        `;

        const actions = carte.querySelector('.source-actions');
        const btn = document.createElement('button');
        btn.className = 'btn btn-petit '
            + (statut.classique ? 'btn-retirer' : 'btn-ajouter');
        btn.textContent = statut.classique ? 'Retirer' : 'Marquer';
        btn.addEventListener('click', () => modifierClassique(!statut.classique));
        actions.appendChild(btn);
        return carte;
    }

    /** Rend le résultat complet d'une recherche (statut + définition). */
    function afficherResultat(data) {
        resultatMot.textContent = data.mot;
        sourcesEl.innerHTML = '';
        Object.keys(data.sources).forEach((source) => {
            sourcesEl.appendChild(carteSource(source, data.sources[source]));
        });

        classiqueEl.innerHTML = '';
        if (data.classique) {
            classiqueEl.appendChild(carteClassique(data.classique));
        }

        definitionContenu.innerHTML = '';
        if (Array.isArray(data.definition) && data.definition.length) {
            const ol = document.createElement('ol');
            data.definition.forEach((glose) => {
                const li = document.createElement('li');
                li.textContent = glose;
                ol.appendChild(li);
            });
            definitionContenu.appendChild(ol);
        } else {
            const p = document.createElement('p');
            p.className = 'indisponible';
            p.textContent = 'Définition indisponible (mots ODS 8 uniquement).';
            definitionContenu.appendChild(p);
        }
        resultat.hidden = false;
    }

    let motCourant = '';

    async function rechercher(mot) {
        afficherMessageDico('');
        chargement.hidden = false;
        btnRechercher.disabled = true;
        try {
            const data = await api.rechercher_mot(mot);
            if (!data.succes) {
                resultat.hidden = true;
                afficherMessageDico(data.erreur || 'Recherche impossible.');
                return;
            }
            if (!data.mot) {
                resultat.hidden = true;
                afficherMessageDico('Saisissez un mot à rechercher.');
                return;
            }
            motCourant = data.mot;
            afficherResultat(data);
        } finally {
            chargement.hidden = true;
            btnRechercher.disabled = false;
        }
    }

    /** Ajoute ou retire le mot courant d'une source puis rafraîchit l'affichage. */
    async function modifierMot(source, ajouter) {
        if (!motCourant) {
            return;
        }
        const appel = ajouter ? api.ajouter_mot : api.retirer_mot;
        const data = await appel(motCourant, source);
        if (!data.succes) {
            afficherMessageDico(data.erreur || 'Modification impossible.');
            return;
        }
        afficherMessageDico('');
        afficherResultat(data);
    }

    /**
     * Marque ou démarque le mot courant comme « classique du jeu » puis
     * rafraîchit l'affichage. Un refus (mot absent des deux sources) est
     * signalé via le message d'erreur du dictionnaire (issue #204).
     */
    async function modifierClassique(marquer) {
        if (!motCourant) {
            return;
        }
        const data = await api.marquer_classique_mot(motCourant, marquer);
        if (!data.succes) {
            afficherMessageDico(data.erreur || 'Modification impossible.');
            return;
        }
        afficherMessageDico('');
        afficherResultat(data);
    }

    formRecherche.addEventListener('submit', (e) => {
        e.preventDefault();
        rechercher(inputMot.value);
    });

    // ---- Bascule entre les deux vues ----
    /** Montre le panneau Réglages à la place de la configuration (issue #169). */
    async function afficherReglages() {
        // Peuplement paresseux au premier affichage (les valeurs sont ensuite
        // maintenues à jour par les enregistrements en direct).
        if (!reglagesCharges) {
            try {
                await chargerGeneral();
                reglagesCharges = true;
            } catch (err) {
                alert('Impossible de charger les réglages : ' + err);
                return;
            }
        }
        vueConfig.hidden = true;
        vueReglages.hidden = false;
        window.scrollTo(0, 0);
    }

    /** Revient à la vue configuration (« Fermer » ou Échap). */
    function masquerReglages() {
        vueReglages.hidden = true;
        vueConfig.hidden = false;
    }

    btnReglages.addEventListener('click', () => {
        afficherReglages();
    });
    btnFermerReglages.addEventListener('click', () => {
        masquerReglages();
    });

    // Fermer modales avec Escape ; à défaut, revenir de la vue Réglages à la
    // configuration (issue #169), comme le faisait l'ex-fenêtre autonome.
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (!modaleHumain.hidden) {
                cacherModale(modaleHumain);
            } else if (!modaleOrdinateur.hidden) {
                cacherModale(modaleOrdinateur);
            } else if (!vueReglages.hidden) {
                masquerReglages();
            }
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
