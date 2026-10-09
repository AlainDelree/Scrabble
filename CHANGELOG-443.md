# Changelog — Issue #443

## Modifié

- **Personnages IA, lot F bis : liste de l'accueil alignée sur celle du jeu,
  texte de Classique reformulé, marque « Dans cette partie » pour Aléatoire.**
  Corrige trois défauts relevés à l'essai du lot F (#442).
  - **Texte de Classique** (`moteur/personnages.py`) : description remplacée
    par « Joue normalement selon son niveau. » (plus clair que « Joue sans
    biais de personnalité... »).
  - **Styles de la fenêtre « Les personnages » isolés dans un seul fichier**
    (nouveau `web/personnages.css`, retiré de `commun.css`) : chargé par les
    DEUX fenêtres (`accueil.html`, `jeu.html`), qui ne peuvent donc plus
    diverger. L'accueil ne chargeait jamais `commun.css` (feuille
    entièrement autonome, propre à sa fenêtre) : c'est ce qui laissait la
    liste des personnages en texte brut, sans nom en évidence ni séparateur
    ni bouton « Fermer » stylé — même composant JS (`creerModalePersonnages`
    de `commun.js`), même markup, mais aucun style appliqué. La fenêtre de
    l'accueil est désormais visuellement identique à celle du jeu (vérifié
    par capture à 1280×800).
  - **Marque « Dans cette partie » pour l'entrée Aléatoire** (`moteur/
    personnages.py`, `ui/jeu.py`) : nouveau paramètre
    `lister_personnages(cles_dans_partie, aleatoire_dans_partie=False)` —
    l'entrée Aléatoire elle-même est désormais marquée dès qu'au moins un
    adversaire a été RÉGLÉ sur Aléatoire (`ApiJeu.obtenir_personnages`
    calcule ce drapeau séparément de `cles_dans_partie`, qui continue de
    n'inclure que des personnages choisis explicitement). Aucune fuite
    d'identité : le libellé « (Aléatoire) » est déjà affiché à côté du
    prénom de cet adversaire pendant toute la partie ; seul le personnage
    réellement tiré reste secret, jamais marqué lui-même.
  - **Tests** (`tests/test_moteur_personnages.py`,
    `tests/test_jeu_personnages.py`) : nouvelle description de Classique ;
    `aleatoire_dans_partie` ne marque que l'entrée Aléatoire ; marquage de
    l'entrée Aléatoire en jeu quand un adversaire y est réglé, absence de
    marquage sinon ; un personnage seulement tiré au hasard (jamais choisi
    explicitement) reste non marqué lui-même ; mêmes données
    (`ApiJeu`/`ApiAccueil.obtenir_personnages`) et même composant JS/CSS
    utilisés par les deux fenêtres.
  - **Vérification visuelle** (`scripts/_harness_jeu/verif_443_personnages.mjs`,
    captures `i443_accueil_personnages_1280x800.png` /
    `i443_jeu_personnages_1280x800.png`) : harnais Playwright headless
    comparant les deux fenêtres (même largeur de modale, mêmes classes,
    marquage Aléatoire visible en jeu, absent à l'accueil).
