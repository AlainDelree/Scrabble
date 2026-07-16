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
    const modaleTransition = document.getElementById('modale-transition');

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
     * Charge et affiche les parties en cours
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

        if (result.succes) {
            document.getElementById('message-transition').textContent = result.message;
            afficherModale(modaleTransition);
        } else {
            alert(result.erreur);
            btnLancer.disabled = false;
            btnLancer.textContent = 'Lancer la partie';
        }
    });

    // Fermer modale transition
    document.getElementById('btn-fermer-transition').addEventListener('click', () => {
        // Fermer la fenêtre pywebview
        if (window.pywebview) {
            window.close();
        }
    });

    // Reprendre une partie (délégation d'événement)
    partiesEnCours.addEventListener('click', async (e) => {
        if (e.target.classList.contains('btn-reprendre')) {
            const id = parseInt(e.target.dataset.id, 10);
            const result = await api.reprendre(id);
            if (result.succes) {
                document.getElementById('message-transition').textContent = result.message;
                afficherModale(modaleTransition);
            } else {
                alert(result.erreur);
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
