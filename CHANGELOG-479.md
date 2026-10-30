# Changelog — Issue #479

## Ajouté

- **`scrabble/serveur/securite.py` : verrouillage du dictionnaire côté
  serveur.** Le prototype de serveur local (issue #475, complété par #477 et
  #478) exposait, sans aucune limite, plusieurs fonctions répondant
  « valide »/« refusé » pour n'importe quel mot ou n'importe quelle lettre —
  un programme automatique aurait pu ainsi reconstituer le dictionnaire
  (`data/dictionnaire/`, jamais diffusé au navigateur) mot par mot. Trois
  mécaniques, toutes appliquées par `scrabble/serveur/httpd.py` AVANT tout
  appel au routeur, sans toucher à `scrabble/ui/` :
  - **Fonctions de gestion des mots interdites.** `rechercher_mot`,
    `ajouter_mot`, `retirer_mot`, `marquer_classique_mot` (onglet
    Dictionnaire des réglages) sont refusées pour tous les clients du
    serveur (HTTP 403, `{"erreur": "Fonction de gestion du dictionnaire
    indisponible sur ce serveur : réservée à l'application de bureau."}` —
    même format que les erreurs déjà existantes de l'API) et absentes de la
    liste des fonctions exposées au navigateur (`fonctions_exposees`), donc
    jamais appelables même en contournant l'interface. `verifier_mot`
    (champ « Tapez un mot à tester » de l'écran de jeu) n'est PAS concernée
    : c'est une fonction de jeu utile, limitée en fréquence (voir
    ci-dessous), pas interdite. Recherche faite dans `jeu.js`/`accueil.js`/
    `commun.js` : aucune autre fonction exposée ne révèle l'existence d'un
    mot ou ne propose des mots à partir de lettres arbitraires (pas
    d'anagramme, de suggestion ni d'aide au coup dans ce projet).
  - **Lettres posées/vérifiées limitées au chevalet réel.** L'étude de
    faisabilité avait relevé que `poser_lettre_en_attente` (mode «
    finalisation », après le choix de la lettre d'un joker) et
    `verifier_coup`/`poser_mot` (quand `placements` est fourni explicitement
    par l'appelant, au lieu de l'état de pose interne habituel) acceptaient,
    côté `scrabble.ui`, n'importe quelle lettre sans vérifier qu'elle
    provient réellement du chevalet du joueur dont c'est le tour —
    transformant ces fonctions en oracle de dictionnaire à lettres
    arbitraires (y compris `poser_mot`, dont les deux messages d'échec
    distincts, mot invalide vs lettres absentes du chevalet, permettaient
    de distinguer les deux cas). Le contrôle est rejoué côté serveur, en
    lisant le chevalet via les fonctions déjà publiques `obtenir_etat` +
    `obtenir_chevalet` (aucun accès à l'état privé d'`ApiJeu`, donc aucune
    modification de `scrabble/ui/`, satisfaisant la contrainte du point 3
    sans qu'elle soit nécessaire). Un joker du chevalet reste utilisable
    avec n'importe quelle lettre choisie, mais seulement si l'emplacement
    visé du chevalet porte réellement un joker.
  - **Limites de fréquence des vérifications.** `verifier_coup` (30
    appels/minute, 1 000/jour) et `verifier_mot` (10 appels/minute, 200/jour
    — plus stricte car elle accepte n'importe quelle suite de lettres),
    réglables dans `LIMITES_FREQUENCE`/`PALIERS_BLOCAGE_SECONDES`
    (`scrabble/serveur/securite.py`, seul endroit à modifier). Au-delà,
    refus renvoyé comme un échec normal de l'API (`{"succes": false,
    "erreur": "Trop de vérifications, réessayez dans quelques minutes."}`,
    HTTP 200) plutôt qu'une erreur de transport, pour que l'écran de jeu
    existant (`jeu.js`, inchangé) affiche le message tel quel — exactement
    comme un coup refusé par le moteur. Une insistance après un refus
    allonge la pause (1, puis 5, puis 15 minutes, plafonnée), réinitialisée
    au premier appel de nouveau accepté. Compteurs par adresse de client, en
    mémoire du processus serveur : remis à zéro à chaque redémarrage
    (documenté dans `CONTEXTE.md`).
  - **Journal des abus.** Chaque refus (fonction interdite, limite de
    fréquence atteinte, lettre hors chevalet) ajoute une ligne au journal du
    serveur (heure automatique, adresse du client, nom de la fonction/limite
    concernée) — jamais les arguments de l'appel (lettres, mots) ni leurs
    résultats, vérifié par un test dédié.
  - **Onglet Dictionnaire masqué côté serveur.** `scrabble/serveur/pont.py`
    ajoute `style_masquage_dictionnaire()`, une feuille de style injectée
    par le serveur dans toutes les pages HTML servies (comme le
    script-pont) : masque `#onglet-dictionnaire`/`#panneau-dictionnaire`
    (identifiants propres à `accueil.html`), sans toucher à aucun fichier de
    `ui/web/`. Le panneau « Tapez un mot à tester » de l'écran de jeu
    (identifiants distincts, `jeu.html`) n'est pas affecté : il reste
    affiché et fonctionnel, définition comprise. Le bureau garde tous ses
    panneaux (aucun fichier de `ui/web/` modifié).
  - **Tests** (`tests/test_serveur.py`, +50 cas sur ce fichier) : refus des
    quatre fonctions interdites avec le bon format d'erreur, exclusion de
    `fonctions_exposees`, masquage CSS vérifié sur `accueil.html` et absence
    d'effet sur `jeu.html`, refus d'une lettre/placement hors chevalet
    (finalisation et placements explicites, `poser_lettre_en_attente` et
    `verifier_coup`/`poser_mot`), acceptation d'un joker réellement présent
    au chevalet, limites par minute puis par jour (unitaires sur
    `LimiteurFrequence` avec horodatages simulés, puis de bout en bout en
    HTTP pour `verifier_coup`/`verifier_mot`), allongement de la pause en
    cas d'insistance, réinitialisation après la pause, absence des
    arguments dans le journal.

## Essais manuels (hors suite automatisée)

Serveur lancé en sous-processus (PID relevé, arrêté par ce PID en fin
d'essai) avec un dossier de données temporaire, piloté par Chromium/
Playwright en fenêtre téléphone (390×844) avec une copie temporaire (non
commitée) de `data/dictionnaire/` : onglet Dictionnaire absent de
`accueil.html` servie (display `none` calculé), panneau de vérification de
`jeu.html` fonctionnel à l'identique (mot valide → coché + définition
affichée ; mot absent → croix, sans régression), les quatre fonctions
interdites refusées en HTTP direct, déroulé honnête (sélectionner, poser,
vérifier, annuler, passer) jamais bloqué par le nouveau contrôle de
chevalet, triche à la main (lettre hors chevalet, en pose comme en
vérification) refusée avec le message dédié, dépassement des deux limites
de fréquence observé avec refus puis pause allongée en cas d'insistance.
Aucun processus serveur ni Chromium resté actif en fin d'essai.
