# Changelog — Issue #448

## Ajouté

- **Personnage Chasseur de scrabbles (lot H).** Deuxième personnage après
  Opportuniste (lot B) : guette les coups posant les 7 lettres du chevalet
  (un « scrabble ») et garde ses meilleures lettres pour y arriver. D'après
  le rapport d'investigation (issue #437), classé « réalisable en partie » :
  le bonus direct sur la pose de 7 lettres relève de la même famille de
  calcul que le bonus premium d'Opportuniste ; l'anticipation fine du
  reliquat (deviner par avance qu'on approche d'un scrabble jouable) reste
  hors périmètre.
  - **`scrabble.moteur.ia`** : nouveau champ facultatif
    `ProfilPersonnage.bonus_scrabble` (`int | None`, défaut `None`). À la
    différence de `malus_longueur`/`bonus_premium`/`poids_leave`, ce champ
    n'a aucun réglage de production indexé par niveau à surcharger : il vaut
    0 (neutre) pour tous les niveaux tant qu'aucun personnage ne le
    renseigne. `_score_strategique` l'ajoute au score des coups dont
    `nb_nouvelles == 7` (nouvelle constante `_SEUIL_BONUS_SCRABBLE`), quel
    que soit le niveau. Un profil vide, ou sans ce champ, donne exactement
    le même résultat qu'avant son introduction, pour tous les niveaux, à
    graine égale — vérifié explicitement (comme au lot A).
  - **`scrabble.moteur.personnages`** : nouvelle entrée de registre
    `"chasseur_de_scrabbles"` (prénom « Chasseur de scrabbles »), avec deux
    nouvelles constantes nommées en tête de module (modifiables pour la
    mesure, comme `BONUS_PREMIUM_OPPORTUNISTE`) :
    - `BONUS_SEPT_LETTRES_CHASSEUR = 150` — valeur de départ déduite par
      analogie avec le bonus premium d'Opportuniste (100) : l'événement
      déclencheur (poser les 7 lettres) est bien plus rare que « toucher
      une case premium », donc le bonus doit être encore plus déterminant
      pour l'emporter sur un coup concurrent mieux payé en score brut — 150
      reprend l'échelle d'Opportuniste en l'augmentant d'un facteur
      comparable à celui qui sépare déjà ce dernier (×5) du bonus premium
      de production (20 à EXPERT/CHAMPION_DU_MONDE).
    - `POIDS_LEAVE_CHASSEUR_SCRABBLES = 2.0` — le plafond de production de
      `_POIDS_LEAVE` culmine à 1.0 (EXPERT, CHAMPION_DU_MONDE) ; Chasseur de
      scrabbles double ce plafond pour nettement privilégier la
      conservation des bonnes lettres en vue d'un futur scrabble, par
      analogie avec le facteur multiplicatif net choisi pour Opportuniste.
    - Ces deux valeurs sont des points de départ **raisonnés, non mesurés**
      (le dictionnaire réel n'est pas disponible dans ce worktree isolé,
      voir « Mesure réelle non lancée » ci-dessous) — provisoires,
      destinées à être ajustées par Alain après mesure.
    - Nouvelle constante `NIVEAUX_CHASSEUR_SCRABBLES` (disponibilité par
      niveau, mécanisme du lot G, issue #447) : Avancé à Champion du monde,
      **provisoire** elle aussi — d'après le rapport d'investigation (issue
      #437), les scrabbles sont rares aux niveaux plus bas (environ 0,01
      par partie à Intermédiaire, 0,1 à 0,2 à Avancé), rendant le
      personnage peu perceptible en dessous. Ajustable par Alain en un
      seul endroit (cette constante) après mesure.

## Tests

- `tests/test_moteur_ia.py` : `ProfilPersonnage.bonus_scrabble` vaut `None`
  par défaut ; un coup posant 7 lettres sans profil (ou avec profil vide)
  n'est pas affecté, pour tous les niveaux ; le bonus s'ajoute exactement
  (égalité stricte `score + bonus`) quand `nb_nouvelles == 7` ; le bonus est
  ignoré pour `nb_nouvelles` de 1, 2, 3, 5 et 6 — « le bonus s'applique
  uniquement aux coups qui posent 7 lettres ».
- `tests/test_moteur_personnages.py` : nouvelle classe
  `TestPersonnageChasseurDeScrabbles` —
  - plateau et chevalet fabriqués (`_plateau_chasseur`) où un coup de 7
    lettres (score brut modeste, bonus scrabble intrinsèque +50) est en
    concurrence avec un coup plus court mais mieux payé en score brut
    (lettres chères sur une case mot triple, sans bonus scrabble) ; sans
    personnage, le second l'emporte toujours (AVANCE/EXPERT/
    CHAMPION_DU_MONDE, 0/200 scrabbles choisis sur 200 graines), avec
    Chasseur de scrabbles le premier l'emporte toujours (200/200) — testé
    aux trois niveaux où le personnage est disponible ;
  - présence dans le registre, prénom, description non vide ;
  - présence dans `lister_personnages()` (sélecteur/liste) ;
  - indisponible à Débutant/Facile/Intermédiaire, disponible à
    Avancé/Expert/Champion du monde (mécanisme du lot G) ;
  - libellé « Avancé à Champion du monde » et explication « Disponible à
    partir de Avancé ».
- **`tests/test_moteur_partie.py`** : `test_creer_partie_aleatoire_peut_tirer_classique`
  mis à jour (ajout de `niveaux_ia=[Niveau.CHAMPION_DU_MONDE]`) — ce test
  historique tirait « Aléatoire » au niveau par défaut (Intermédiaire) en
  s'attendant à voir tout le registre, ce qui n'est plus vrai dès lors
  qu'un personnage (Chasseur de scrabbles) y est indisponible : changement
  structurel attendu du mécanisme de disponibilité par niveau (lot G, issue
  #447), pas une régression de comportement — le test est repris au niveau
  (Champion du monde) où tout le registre actuel reste disponible.
- Suite pytest complète : **1060 verts / 5 échecs préexistants** avant ce
  lot (confirmés préexistants par `git stash` — `test_accueil.py`,
  `test_application.py` ×2, `test_journal_integration.py` ×2) ; **1081
  verts / mêmes 5 échecs** après (21 nouveaux tests, aucune régression).

## Mesure réelle non lancée

Comme pour Opportuniste (lot B), le dictionnaire ODS8 n'est pas présent dans
ce worktree isolé (gitignoré, déposé manuellement) : conformément à la
consigne, il n'a pas été recherché ailleurs, et les deux constantes
ci-dessus n'ont donc pas pu être calibrées par mesure. Six commandes prêtes
à lancer par Alain — Chasseur de scrabbles contre Classique, aux six
niveaux, 100 parties chacun, vocabulaire du jeu réel, export CSV pour le
tableau de style (qui compte déjà les scrabbles par partie, issue #446) :

```
python scripts/mesurer_force_niveaux.py DEBUTANT DEBUTANT \
    --personnage-a chasseur_de_scrabbles --personnage-b classique --vocab palier \
    --parties 100 --csv style_chasseur_vs_classique_debutant.csv

python scripts/mesurer_force_niveaux.py FACILE FACILE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique --vocab palier \
    --parties 100 --csv style_chasseur_vs_classique_facile.csv

python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique --vocab palier \
    --parties 100 --csv style_chasseur_vs_classique_intermediaire.csv

python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique --vocab palier \
    --parties 100 --csv style_chasseur_vs_classique_avance.csv

python scripts/mesurer_force_niveaux.py EXPERT EXPERT \
    --personnage-a chasseur_de_scrabbles --personnage-b classique --vocab palier \
    --parties 100 --csv style_chasseur_vs_classique_expert.csv

python scripts/mesurer_force_niveaux.py CHAMPION_DU_MONDE CHAMPION_DU_MONDE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique --vocab palier \
    --parties 100 --csv style_chasseur_vs_classique_champion.csv
```

Les trois premières commandes (Débutant/Facile/Intermédiaire) forcent une
disponibilité aujourd'hui fermée par le registre (`NIVEAUX_CHASSEUR_SCRABBLES`)
— le script de mesure ne vérifie aucune disponibilité (comme pour
Opportuniste), elles servent à juger si la plage provisoire doit être
élargie vers le bas. À l'inverse, si les trois derniers niveaux montrent un
caractère trop peu perceptible ou un déséquilibre de force excessif, la
plage pourra être resserrée. Décision et ajustement des deux constantes
(`BONUS_SEPT_LETTRES_CHASSEUR`, `POIDS_LEAVE_CHASSEUR_SCRABBLES`) laissés à
Alain.

## Points à vérifier à la main

- Chasseur de scrabbles apparaît dans le sélecteur de personnage à
  l'accueil et dans la fenêtre « Les personnages », avec sa description et
  ses niveaux affichés.
- Les niveaux Débutant/Facile/Intermédiaire sont grisés pour ce personnage ;
  Avancé/Expert/Champion du monde restent actifs.
- Une partie avec un ordinateur Chasseur de scrabbles se déroule normalement
  (nécessite le dictionnaire réel, absent de ce worktree).
