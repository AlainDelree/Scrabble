/**
 * Écran d'accueil - Configuration de partie Scrabble
 *
 * Communique avec l'API Python via pywebview.api.*
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
    const btnContinuerTirage = document.getElementById('btn-continuer-tirage');

    // Formulaires
    const formHumain = document.getElementById('form-humain');
    const formOrdinateur = document.getElementById('form-ordinateur');
    const inputPrenom = document.getElementById('input-prenom');
    const checkboxSauvegarder = document.getElementById('checkbox-sauvegarder');
    const listeNiveaux = document.getElementById('liste-niveaux');

    // Parties en cours
    const sectionReprise = document.getElementById('section-reprise');
    const partiesEnCours = document.getElementById('parties-en-cours');

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

                const icone = joueur.humain ? '👤' : '🖥️';
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
                    <span class="joueur-icone">${icone}</span>
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
            const div = document.createElement('div');
            div.className = 'niveau-option';
            div.innerHTML = `
                <input type="radio" name="niveau" id="niveau-${index}" value="${niveau}" ${index === 2 ? 'checked' : ''}>
                <label for="niveau-${index}">${niveau}</label>
            `;
            listeNiveaux.appendChild(div);
        });
    }

    /**
     * Charge et affiche la partie en cours proposée à la reprise.
     *
     * Depuis l'issue #54, `api.lister_parties_en_cours()` ne renvoie que la
     * partie la plus récente (liste de 0 ou 1 élément) : on n'affiche donc
     * qu'un seul encart de reprise.
     */
    async function chargerPartiesEnCours() {
        const parties = await api.lister_parties_en_cours();
        partiesEnCours.innerHTML = '';

        if (parties.length === 0) {
            partiesEnCours.innerHTML = '<p class="vide">Aucune partie en cours.</p>';
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

            item.innerHTML = `
                <div class="partie-info">
                    <div class="partie-joueurs">${partie.joueurs.map(escapeHtml).join(', ')}</div>
                    <div class="partie-date">Dernière activité : ${dateStr}</div>
                </div>
                <button class="btn btn-reprendre" data-id="${partie.id}">Reprendre</button>
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
     * Fabrique un générateur de son « sac de lettres secoué » (issue #61).
     *
     * Web Audio pur, sans fichier externe : chaque appel à `secouer()` déclenche
     * une courte bouffée de bruit blanc filtrée (passe-bande) avec une enveloppe
     * de gain qui monte puis retombe — l'illusion de lettres qui s'entrechoquent.
     * Les bouffées sont **bridées** (une toutes les ~90 ms max) et de faible
     * volume pour éviter tout son continu strident. Rien de continu n'est joué :
     * `arreter()` n'a donc qu'à cesser d'en planifier, et `fermer()` libère le
     * contexte audio quand on a fini (clic « Tirer » ou sortie de zone).
     */
    function creerSonSac() {
        const AC = window.AudioContext || window.webkitAudioContext;
        let ctx = null;
        let bufferBruit = null;
        let dernierBruit = -Infinity;

        function assurerContexte() {
            if (!AC) return null;
            if (!ctx) {
                ctx = new AC();
                // Buffer de bruit blanc réutilisé pour toutes les bouffées.
                const buf = ctx.createBuffer(1, Math.floor(ctx.sampleRate * 0.3), ctx.sampleRate);
                const data = buf.getChannelData(0);
                for (let i = 0; i < data.length; i++) {
                    data[i] = Math.random() * 2 - 1;
                }
                bufferBruit = buf;
            }
            if (ctx.state === 'suspended') ctx.resume();
            return ctx;
        }

        return {
            secouer() {
                const c = assurerContexte();
                if (!c) return;
                const now = c.currentTime;
                if (now - dernierBruit < 0.09) return;  // bridage anti-strident
                dernierBruit = now;

                const duree = 0.05 + Math.random() * 0.05;
                const src = c.createBufferSource();
                src.buffer = bufferBruit;

                const filtre = c.createBiquadFilter();
                filtre.type = 'bandpass';
                filtre.frequency.value = 2200 + Math.random() * 2600;
                filtre.Q.value = 0.7;

                const gain = c.createGain();
                const volume = 0.05 + Math.random() * 0.04;  // faible
                gain.gain.setValueAtTime(0.0001, now);
                gain.gain.linearRampToValueAtTime(volume, now + 0.006);
                gain.gain.exponentialRampToValueAtTime(0.0001, now + duree);

                src.connect(filtre).connect(gain).connect(c.destination);
                src.start(now);
                src.stop(now + duree + 0.02);
            },
            arreter() {
                // Les bouffées sont brèves et s'auto-terminent : il suffit de
                // cesser d'en planifier (l'appelant arrête d'appeler secouer()).
                dernierBruit = -Infinity;
            },
            fermer() {
                if (ctx) {
                    ctx.close().catch(() => {});
                    ctx = null;
                }
            },
        };
    }

    /**
     * Tour d'un joueur HUMAIN dans le tirage d'ordre (issue #61) : au lieu de
     * révéler automatiquement sa lettre, on affiche un sac que le joueur secoue
     * en passant la souris dessus (secousse visuelle + son) puis un bouton
     * « Tirer une lettre » qui dévoile sa lettre.
     *
     * @param {HTMLElement} li Ligne de résultat correspondante (nom + lettre).
     * @param {{nom: string, lettre: string}} t Tirage du joueur humain.
     * @returns {Promise<void>} résolue une fois la lettre tirée.
     */
    function tourHumain(li, t) {
        return new Promise((resolve) => {
            // La ligne apparaît, mais la lettre reste masquée jusqu'au tirage.
            li.classList.add('visible', 'en-attente-tirage');

            tirageSacZone.hidden = false;
            tirageSacZone.innerHTML = `
                <p class="tirage-sac-consigne">À toi, ${escapeHtml(t.nom)} ! Secoue le sac, puis tire ta lettre.</p>
                <div class="tirage-sac-aire" aria-hidden="true">
                    <div class="tirage-sac" title="Secoue-moi !" role="img" aria-label="Sac de lettres à secouer">
                        <svg viewBox="0 0 100 110" width="120" height="132" aria-hidden="true">
                            <path class="tirage-sac-corps" d="M22 42 Q50 28 78 42 L88 96 Q50 112 12 96 Z"/>
                            <path class="tirage-sac-col" d="M34 40 Q50 22 66 40 Q50 34 34 40 Z"/>
                            <line class="tirage-sac-cordon" x1="34" y1="40" x2="66" y2="40"/>
                            <text class="tirage-sac-glyphe" x="50" y="80" text-anchor="middle">?</text>
                        </svg>
                    </div>
                </div>
                <button type="button" class="btn btn-primaire tirage-sac-bouton">Tirer une lettre</button>
            `;

            const aire = tirageSacZone.querySelector('.tirage-sac-aire');
            const sac = tirageSacZone.querySelector('.tirage-sac');
            const bouton = tirageSacZone.querySelector('.tirage-sac-bouton');
            const son = creerSonSac();

            // Le sac se déplace dans une large zone carrée en suivant le curseur
            // (issue #68) : bien plus perceptible qu'une simple rotation.
            function surMouvement(e) {
                const rect = aire.getBoundingClientRect();
                // Écart normalisé du curseur au centre de la zone, borné à [-1, 1].
                const nx = Math.max(-1, Math.min(1,
                    (e.clientX - (rect.left + rect.width / 2)) / (rect.width / 2)));
                const ny = Math.max(-1, Math.min(1,
                    (e.clientY - (rect.top + rect.height / 2)) / (rect.height / 2)));
                // Amplitude max = espace libre entre le sac et les bords de la zone,
                // pour que le sac suive le curseur sans jamais déborder.
                const maxX = Math.max(0, (rect.width - sac.offsetWidth) / 2);
                const maxY = Math.max(0, (rect.height - sac.offsetHeight) / 2);
                const tx = nx * maxX;
                const ty = ny * maxY;
                // Rotation proportionnelle à l'écart horizontal (effet de balancement).
                const angle = nx * 12;
                sac.style.transform =
                    `translate(${tx.toFixed(1)}px, ${ty.toFixed(1)}px) rotate(${angle.toFixed(1)}deg)`;
                son.secouer();
            }
            function surSortie() {
                // Désactivation propre si l'on quitte la zone avant de tirer.
                sac.style.transform = '';
                son.arreter();
            }

            aire.addEventListener('mousemove', surMouvement);
            aire.addEventListener('mouseleave', surSortie);

            bouton.addEventListener('click', () => {
                aire.removeEventListener('mousemove', surMouvement);
                aire.removeEventListener('mouseleave', surSortie);
                son.arreter();
                son.fermer();
                li.classList.remove('en-attente-tirage');  // dévoile la lettre
                tirageSacZone.hidden = true;
                tirageSacZone.innerHTML = '';
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
     * par une interaction « secouer le sac puis tirer » (issue #61) : la
     * séquence se met en pause jusqu'au clic sur « Tirer une lettre », puis
     * reprend. Le résultat « Ordre de jeu : … » n'apparaît qu'une fois TOUTES
     * les lettres révélées.
     *
     * @param {{tirages: Array<{nom: string, lettre: string, humain: boolean}>, ordre: string[]}} tirage
     * @returns {Promise<void>} résolue quand l'utilisateur valide la modale.
     */
    async function afficherTirageOrdre(tirage) {
        tirageLettres.innerHTML = '';
        tirageOrdreResultat.textContent = '';
        tirageOrdreResultat.classList.remove('visible');
        tirageSacZone.hidden = true;
        tirageSacZone.innerHTML = '';

        const lignes = tirage.tirages.map(t => {
            const li = document.createElement('li');
            li.innerHTML = `<span class="tirage-nom">${escapeHtml(t.nom)}</span> a tiré <span class="tirage-lettre">${escapeHtml(t.lettre)}</span>`;
            tirageLettres.appendChild(li);
            return li;
        });

        afficherModale(modaleTirage);

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

        await new Promise((resolve) => {
            btnContinuerTirage.onclick = () => {
                cacherModale(modaleTirage);
                btnContinuerTirage.onclick = null;
                resolve();
            };
        });
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
                await afficherTirageOrdre(result.tirage_ordre);
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
            e.target.disabled = true;
            e.target.textContent = 'Chargement...';

            const btnReprendre = e.target;
            const result = await api.reprendre(id);
            if (result.succes && result.pret) {
                // Fermer la fenêtre d'accueil depuis Python — l'écran de jeu
                // s'ouvrira automatiquement après la fermeture. En cas
                // d'échec, on réactive le bouton plutôt que de rester bloqué.
                await fermerFenetre((msg) => {
                    alert(msg);
                    btnReprendre.disabled = false;
                    btnReprendre.textContent = 'Reprendre';
                });
            } else if (!result.succes) {
                alert(result.erreur);
                btnReprendre.disabled = false;
                btnReprendre.textContent = 'Reprendre';
            }
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
