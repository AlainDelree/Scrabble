/**
 * Écran de jeu - Plateau et chevalet (lecture seule)
 *
 * Communique avec l'API Python via pywebview.api.*
 *
 * Confidentialité : le chevalet du joueur courant reste masqué par défaut.
 * Il n'est révélé que sur clic explicite (« voir mes lettres ») et peut être
 * remasqué à tout moment. Chaque rafraîchissement remasque le chevalet.
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
     */
    function creerTuile(cell) {
        const tuile = document.createElement('div');
        tuile.className = 'tuile' + (cell.joker ? ' tuile-joker' : '');
        tuile.textContent = cell.lettre;
        return tuile;
    }

    /**
     * Rend le plateau à partir de l'état (grille de cases typées).
     */
    function rendrePlateau(plateau) {
        plateauEl.innerHTML = '';
        const fragment = document.createDocumentFragment();
        plateau.forEach((ligne, l) => {
            ligne.forEach((cell, c) => {
                const caseEl = document.createElement('div');
                caseEl.className = `case case-${cell.type}`;
                caseEl.title = LABEL_CASE[cell.type] || '';
                if (cell.lettre) {
                    caseEl.appendChild(creerTuile(cell));
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
     */
    function rendreChevaletRevele(lettres) {
        chevaletEl.innerHTML = '';
        if (!lettres.length) {
            chevaletEl.innerHTML = '<span class="chevalet-vide">Chevalet vide.</span>';
            return;
        }
        lettres.forEach(l => {
            const c = document.createElement('div');
            c.className = 'chevalet-case revelee' + (l.joker ? ' joker' : '');
            const lettreAffichee = l.joker ? '★' : escapeHtml(l.lettre);
            c.innerHTML = `${lettreAffichee}<span class="val">${l.valeur}</span>`;
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
                rendreChevaletRevele(res.lettres);
            } else {
                chevaletVisible = false;
                btnVisibilite.textContent = '👁️ Voir mes lettres';
                rendreChevaletMasque(courant ? courant.nb_lettres : 0);
            }
        } else {
            btnVisibilite.textContent = '👁️ Voir mes lettres';
            rendreChevaletMasque(courant ? courant.nb_lettres : 0);
        }
    }

    /**
     * Recharge l'état complet et rafraîchit l'affichage. Remasque le chevalet.
     */
    async function rafraichir() {
        etat = await api.obtenir_etat();
        chevaletVisible = false;
        rendrePlateau(etat.plateau);
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

    // --- Initialisation ---
    await rafraichir();
});
