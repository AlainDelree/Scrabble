# Changelog — Issue #442

## Ajouté

- **Personnages IA, lot F : fenêtre « Les personnages », consultable à
  l'accueil comme en cours de partie.** Liste tous les personnages du
  registre (nom + description), construite dynamiquement pour qu'un
  personnage ajouté plus tard au registre y apparaisse sans autre
  modification, avec « Aléatoire » toujours en dernier.
  - **Données** (`moteur/personnages.py`) : nouvelle fonction pure
    `lister_personnages(cles_dans_partie=frozenset())`, qui construit
    `{"cle", "prenom", "description", "dans_la_partie"}` pour chaque
    personnage du registre puis l'entrée « Aléatoire » — jamais marquée
    `dans_la_partie`, pour ne jamais laisser deviner un tirage.
  - **Accueil** (`ui/accueil.py` inchangé, `web/accueil.html/js/css`) : un
    lien discret « Les personnages » à côté du sélecteur de personnage,
    qui réutilise la liste déjà chargée par `obtenir_personnages()`
    (aucun appel API supplémentaire).
  - **Écran de jeu** (`ui/jeu.py`, `web/jeu.html/js/css`) : nouvelle
    méthode `ApiJeu.obtenir_personnages()`, lecture pure (aucun effet sur
    le tour en cours, la partie ni la sauvegarde), qui marque
    `dans_la_partie` pour les personnages choisis À L'AVANCE par les
    adversaires — jamais pour un personnage tiré au hasard. Bouton
    « 🎭 Personnages » ajouté à la zone des boutons système (ligne 1,
    aux côtés de « Retour au menu »/« Resynchroniser »/Sac).
  - **Interface commune** (`web/commun.js`, `web/commun.css`) : contrôleur
    `creerModalePersonnages(refs)` et markup `#modale-personnages`
    dupliqué dans les deux fenêtres (même esprit que la modale de détail
    du score) — un seul composant de rendu, liste défilante
    (`overflow-y: auto`) pour rester lisible à 1280×800 même si le
    registre s'allonge. Fermeture par bouton, clic sur le fond ou Échap.
  - **Tests** (`tests/test_moteur_personnages.py`,
    `tests/test_jeu_personnages.py`) : la liste reflète le registre (un
    personnage ajouté dans un test y apparaît), Aléatoire toujours en
    dernier, jamais marqué `dans_la_partie`, et le marquage ne porte que
    sur les personnages choisis explicitement par les adversaires de la
    partie en cours — jamais sur un tirage aléatoire, même quand son
    identité réelle est déjà connue du moteur.
