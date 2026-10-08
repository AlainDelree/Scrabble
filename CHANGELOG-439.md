# Changelog — Issue #439

## Ajouté

- **Personnages IA, lot B : personnage Opportuniste.** Nouveau module
  `src/scrabble/moteur/personnages.py` : registre unique `PERSONNAGES`
  (dict clé → `Personnage(cle, prenom, description, profil)`), chaque
  entrée associant un prénom, une description de caractère en français et
  un `ProfilPersonnage` (issue #438, lot A). Ajouter un personnage revient
  à ajouter une entrée à ce dict.
  - `classique` : `ProfilPersonnage()` vide — comportement standard,
    identique bit à bit à l'absence de profil.
  - `opportuniste` : `bonus_premium=28`, `poids_leave=0.0`. Combinaison de
    deux réglages déjà existants du lot A, aucun nouveau calcul, conforme
    au rapport d'investigation #437. `poids_leave=0.0` reprend telle
    quelle la valeur de production de DEBUTANT/FACILE. `bonus_premium=28`
    est dérivé de l'échelle existante (`_BONUS_PREMIUM` va de 3 à 20 par
    paliers +2/+3/+4/+8/+0) : valeur la plus haute déjà calibrée (20,
    EXPERT/CHAMPION_DU_MONDE) + le plus grand palier observé entre deux
    niveaux adjacents (+8, AVANCE → EXPERT) = 28. Surcharge **plate** (pas
    indexée par niveau) : le trait de caractère ne varie pas avec la force
    du joueur, par construction de `ProfilPersonnage`.
- `scripts/mesurer_force_niveaux.py` : `ConfigJoueur` gagne un champ
  `personnage: str | None`, résolu par la nouvelle méthode `profil()` vers
  le `ProfilPersonnage` du registre et transmis directement à
  `ia.choisir_coup(..., profil=...)` — la même voie qu'un futur appelant en
  production, par opposition au patch transitoire
  (`_strategie_surchargee`) utilisé pour `--malus-a`/`--bonus-a`/
  `--poids-leave-a`. Les deux mécanismes se composent sans conflit. Deux
  nouvelles options CLI `--personnage-a`/`--personnage-b` (validées contre
  `PERSONNAGES`), reflétées dans `ConfigJoueur.label()` pour les CSV/résumés,
  et un exemple d'usage dans la docstring du script (forme recommandée par
  le rapport #437, point 5).

## Tests

- `tests/test_moteur_personnages.py` (nouveau) :
  - `TestPersonnageOpportuniste` : sur un plateau avec `CADRE` déjà posé
    au centre (pour que seuls certains coups ultérieurs touchent une case
    bonus — un plateau vide biaiserait tout premier coup via la case
    centrale) et un chevalet `SOIRIT` fixe, la proportion de coups choisis
    touchant une case à multiplicateur, moyennée sur 300 graines, est
    strictement supérieure pour Opportuniste par rapport à Classique, aux
    niveaux INTERMEDIAIRE et FACILE.
  - `TestPersonnageClassiqueInchange` : le profil `classique` du registre a
    ses trois champs à `None`, et `choisir_coup` avec ce profil produit
    exactement le même coup, graine par graine, que sans profil du tout,
    pour les 6 niveaux (même scénario que le test Opportuniste).

## Mesure de force (Opportuniste vs Classique)

**Non exécutée dans ce worktree** : `data/dictionnaire/` y est vide (dépôt
manuel, gitignoré — voir `data/dictionnaire/README.md`), ce qui est normal
pour un worktree isolé fraîchement créé mais bloque
`scripts/mesurer_force_niveaux.py` (`_verifier_dictionnaire_installe`
s'arrête avec un message clair). Le périmètre de cette tâche interdit de
lire un autre répertoire de travail pour copier le dictionnaire. Les tests
unitaires ci-dessus (sur des mini-dictionnaires synthétiques, comme le
reste de la suite `test_moteur_ia.py`) ne demandent pas ce fichier et
passent normalement.

Commandes prêtes à lancer par Alain (dictionnaire disponible dans son
checkout principal), un niveau intermédiaire et un niveau élevé, protocole
identique aux recalibrages précédents (taux de victoire + IC 95 %, écart
moyen de points), vocabulaire du jeu réel (`--vocab palier`) :

```
python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
    --personnage-a opportuniste --personnage-b classique \
    --vocab palier --parties 200 --csv opportuniste_vs_classique_intermediaire.csv

python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
    --personnage-a opportuniste --personnage-b classique \
    --vocab palier --parties 200 --csv opportuniste_vs_classique_avance.csv
```

Si le taux de victoire d'Opportuniste s'écarte nettement de ~50 % (force
différente de Classique au même niveau), réduire/augmenter
`BONUS_PREMIUM_OPPORTUNISTE` dans `src/scrabble/moteur/personnages.py` en
conséquence — valeur à ajuster uniquement sur validation d'Alain, pas en
boucle automatique.

## Contraintes respectées

- Aucune valeur par niveau (`_MALUS_LONGUEUR`/`_BONUS_PREMIUM`/
  `_POIDS_LEAVE`) modifiée.
- Aucun changement d'UI : le personnage reste inutilisable en jeu, seulement
  par les tests et le script de mesure.
- Tests existants non modifiés ; 5 échecs préexistants confirmés par un
  lancement de la suite avant toute modification (dictionnaire
  accueil/application/journal, sans rapport avec ce lot) — inchangés après.

## Incident mineur

Au cours de l'investigation, une lecture par erreur d'un fichier dans un
autre worktree (`/home/alain/scrabble-issue438/CHANGELOG-438.md`, hors
périmètre strict de cette tâche) a eu lieu — lecture seule, sans
modification ni conséquence. Le contenu recherché existait de toute façon
dans le périmètre autorisé (fusionné dans `CHANGELOG.md` de ce worktree).
Signalé par souci de transparence.
