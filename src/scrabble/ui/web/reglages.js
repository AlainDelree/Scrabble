/**
 * reglages.js — logique de la fenêtre de réglages à onglets (issue #111).
 *
 * Deux onglets : « Général » (prénom principal, thème, source de dictionnaire,
 * persistés via l'API Python ``reglages``/``config``) et « Dictionnaire »
 * (recherche d'un mot, statut par source ODS/Hunspell, ajout/retrait manuel,
 * définition). Communique avec ``ApiReglages`` via ``window.pywebview.api.*``.
 *
 * pywebview charge des scripts classiques (pas des modules ES) : pas d'import,
 * on garde de petits utilitaires locaux.
 */

document.addEventListener('DOMContentLoaded', async () => {
    await new Promise((resolve) => {
        if (window.pywebview && window.pywebview.api) {
            resolve();
        } else {
            window.addEventListener('pywebviewready', resolve, { once: true });
        }
    });

    const api = window.pywebview.api;

    /** Échappe le HTML pour éviter toute injection. */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    // Libellés des sources, renseignés depuis Python à l'initialisation.
    let labelsSources = { ods: 'ODS 8', hunspell: 'Hunspell' };

    // ============================ Onglets ============================
    const onglets = document.querySelectorAll('.onglet');
    const panneaux = document.querySelectorAll('.panneau');

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

    // ========================= Onglet Général =========================
    const inputPrenom = document.getElementById('input-prenom');
    const selectTheme = document.getElementById('select-theme');
    const selectSource = document.getElementById('select-source');
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
        inputPrenom.value = r.prenom_principal || '';
        remplirSelect(selectTheme, r.themes, r.theme_plateau);
        remplirSelect(selectSource, r.sources, r.source_dictionnaire);
        labelsSources = {};
        (r.sources || []).forEach((s) => { labelsSources[s.valeur] = s.libelle; });
    }

    /** Enregistre un réglage et signale le résultat. */
    async function enregistrer(cle, valeur) {
        const res = await api.enregistrer_reglage(cle, valeur);
        if (res.succes) {
            afficherStatutGeneral('Enregistré.', false);
            return res.valeur;
        }
        afficherStatutGeneral(res.erreur || 'Échec de l\'enregistrement.', true);
        return null;
    }

    // Le prénom est en texte libre : on enregistre à la perte de focus.
    inputPrenom.addEventListener('change', () => {
        enregistrer('prenom_principal', inputPrenom.value.trim());
    });
    selectTheme.addEventListener('change', () => {
        enregistrer('theme_plateau', selectTheme.value);
    });
    selectSource.addEventListener('change', async () => {
        const retenue = await enregistrer('source_dictionnaire', selectSource.value);
        // La normalisation Python peut retomber sur une autre valeur : on
        // resynchronise le menu pour ne pas laisser un choix trompeur affiché.
        if (retenue && retenue !== selectSource.value) {
            selectSource.value = retenue;
        }
    });

    // ====================== Onglet Dictionnaire =======================
    const formRecherche = document.getElementById('form-recherche');
    const inputMot = document.getElementById('input-mot');
    const btnRechercher = document.getElementById('btn-rechercher');
    const chargement = document.getElementById('chargement');
    const messageDico = document.getElementById('message-dico');
    const resultat = document.getElementById('resultat');
    const resultatMot = document.getElementById('resultat-mot');
    const sourcesEl = document.getElementById('sources');
    const definitionContenu = document.getElementById('definition-contenu');

    function afficherMessage(texte) {
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

    /** Rend le résultat complet d'une recherche (statut + définition). */
    function afficherResultat(data) {
        resultatMot.textContent = data.mot;
        sourcesEl.innerHTML = '';
        Object.keys(data.sources).forEach((source) => {
            sourcesEl.appendChild(carteSource(source, data.sources[source]));
        });

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
        afficherMessage('');
        chargement.hidden = false;
        btnRechercher.disabled = true;
        try {
            const data = await api.rechercher_mot(mot);
            if (!data.succes) {
                resultat.hidden = true;
                afficherMessage(data.erreur || 'Recherche impossible.');
                return;
            }
            if (!data.mot) {
                resultat.hidden = true;
                afficherMessage('Saisissez un mot à rechercher.');
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
            afficherMessage(data.erreur || 'Modification impossible.');
            return;
        }
        afficherMessage('');
        afficherResultat(data);
    }

    formRecherche.addEventListener('submit', (e) => {
        e.preventDefault();
        rechercher(inputMot.value);
    });

    // =========================== Fermeture ============================
    const btnFermer = document.getElementById('btn-fermer');
    btnFermer.addEventListener('click', async () => {
        btnFermer.disabled = true;
        const res = await api.fermer_fenetre();
        if (!res || !res.succes) {
            btnFermer.disabled = false;
            afficherStatutGeneral(
                (res && res.erreur) || 'Fermeture impossible.', true);
        }
    });

    // Échap ferme la fenêtre (raccourci confortable).
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            btnFermer.click();
        }
    });

    // ========================= Initialisation =========================
    await chargerGeneral();
    inputMot.focus();
});
