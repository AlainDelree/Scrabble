/**
 * hauteur_attente.js — synchronisation dynamique de la hauteur de la zone
 * d'attente du tour IA (issue #96, suite du point A de l'issue #95).
 *
 * Le problème récurrent (#92, puis #94) : caler la hauteur de `.zone-attente-ia`
 * (tour d'un ordinateur) sur celle de la zone interactive du tour humain à l'aide
 * d'une CONSTANTE de pixels mesurée à l'avance. Cette constante était mesurée dans
 * Chromium (harnais de test headless) mais le rendu réel se fait sous WebKitGTK
 * (pywebview) : les deux moteurs divergent, d'où un grand vide au-dessus du message
 * d'attente en conditions réelles — deux échecs successifs de valeurs figées.
 *
 * Correctif : on ne fige plus rien. chevalet.js mesure en JS, au moteur courant,
 * la hauteur RÉELLEMENT rendue de `.zone-interactive` (via getBoundingClientRect)
 * et l'applique en `min-height` inline à `.zone-attente-ia`. Ce fichier isole la
 * seule arithmétique de cette synchronisation — volontairement PURE (aucune
 * dépendance au DOM) — afin de pouvoir la tester sous Node avec des hauteurs
 * simulées, sans dépendre d'un vrai moteur de rendu (voir
 * tests/test_hauteur_attente_chevalet.py).
 *
 * Chargement : script classique (pas de module ES, comme le reste du projet). En
 * navigateur (pywebview / Chromium) il s'expose sous `window.HauteurAttente` ; sous
 * Node (tests) il s'exporte via `module.exports`.
 */
(function () {
    'use strict';

    /**
     * Cumule la plus grande hauteur interactive réellement rendue observée.
     *
     * On mémorise le MAXIMUM (le tour humain le plus « chargé » : chevalet révélé
     * + brouillon + actions + message de statut) afin que la zone d'attente du tour
     * IA ne soit jamais plus courte que la plus haute silhouette du tour humain —
     * les deux tours gardent ainsi la même empreinte verticale.
     *
     * Une mesure absente, nulle ou négative (élément masqué, pas encore rendu) est
     * ignorée : elle laisse le maximum courant inchangé. `null`/`undefined` en
     * entrée signifie « aucune mesure valable encore » (repli CSS en vigueur) et
     * n'est remplacé que par une première mesure strictement positive.
     */
    function cumulerHauteur(hauteurMaxCourante, hauteurMesuree) {
        if (!(hauteurMesuree > 0)) {
            return hauteurMaxCourante;
        }
        if (hauteurMaxCourante === null || hauteurMaxCourante === undefined) {
            return hauteurMesuree;
        }
        return Math.max(hauteurMaxCourante, hauteurMesuree);
    }

    /**
     * Traduit le maximum courant en valeur CSS `min-height` (ex. `"280px"`).
     *
     * Renvoie `null` tant qu'aucune hauteur n'a été mesurée : l'appelant laisse
     * alors le repli CSS de `.zone-attente-ia` s'appliquer (premier tour IA
     * survenant avant tout tour humain). La hauteur est arrondie à l'entier le plus
     * proche (les sous-pixels de getBoundingClientRect n'ont pas de sens en pixels
     * CSS de mise en page).
     */
    function minHeightAttente(hauteurMax) {
        if (hauteurMax === null || hauteurMax === undefined) {
            return null;
        }
        return Math.round(hauteurMax) + 'px';
    }

    var api = {
        cumulerHauteur: cumulerHauteur,
        minHeightAttente: minHeightAttente,
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;          // Node (tests unitaires)
    }
    if (typeof window !== 'undefined') {
        window.HauteurAttente = api;   // navigateur (pywebview / Chromium)
    }
})();
