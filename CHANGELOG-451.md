# Changelog — Issue #451

## Ajouté

- **Tirage pondéré en faveur des scrabbles et part de mots longs connus,
  réglables par niveau pour le Chasseur (lot H ter).** Après le lot H bis
  (#450), la mesure (hypothétique, dictionnaire absent de ce worktree, voir
  le rapport de l'issue) indiquait deux défauts distincts : à Intermédiaire,
  le style de Chasseur de scrabbles ne se voyait presque pas (le tirage
  uniforme dans la tranche des 15 % meilleurs coups dilue l'effet d'un
  scrabble qui n'y figure qu'une fois sur 10 à 15 coups) ; à Avancé, il était
  au contraire trop fort (vocabulaire long intégral, sans aucun levier pour
  en retenir une partie). Ce lot ajoute deux réglages indépendants pour
  corriger chaque défaut séparément, sans toucher aux réglages par niveau,
  aux autres personnages ni au tirage Aléatoire.

  - **`scrabble.moteur.ia`** : deux nouveaux champs facultatifs de
    `ProfilPersonnage`, tous deux neutres par défaut (`None`) :
    - `poids_tirage_scrabble: float | None`. S'applique UNIQUEMENT à
      l'étape du tirage dans la tranche de meilleurs coups, pour les niveaux
      qui tirent au hasard (DEBUTANT, FACILE, INTERMEDIAIRE, EXPERT) —
      aucun effet sur AVANCE/CHAMPION_DU_MONDE (meilleur coup, jamais un
      tirage dans une tranche). Nouvelle fonction privée
      `_tirer_dans_tranche(tranche, rng, profil)` : sans le champ renseigné,
      c'est exactement `rng.choice(tranche).coup` (même appel, même
      consommation du générateur aléatoire qu'avant son introduction) ; avec
      une valeur renseignée, les coups de la tranche posant les 7 lettres du
      chevalet (`nb_nouvelles == _SEUIL_BONUS_SCRABBLE`, même critère que
      `bonus_scrabble`) reçoivent ce poids dans un tirage pondéré
      (`rng.choices`), les autres coups gardant le poids 1 — la COMPOSITION
      de la tranche (déjà calculée par `_trier_par_score_strategique`) ne
      change jamais, seules les probabilités à l'intérieur changent.
      `_choisir_top5`/`_choisir_intermediaire`/`_choisir_facile`/
      `_choisir_debutant` reçoivent chacune un nouveau paramètre optionnel
      `profil` et délèguent à cette fonction ; `_choisir_avance` reste
      inchangée (pas de paramètre `profil` : aucun effet par construction).
    - `part_vocabulaire_long: float | None`. Affine `vocabulaire_long` (lot H
      bis) : parmi les mots de 7 lettres et plus du lexique complet qui
      élargissent les coups candidats, seule cette fraction reste
      accessible — jamais les mots courts, ni ceux déjà dans le vocabulaire
      du niveau (ceux-là ne passent jamais par ce filtre, par construction
      de `_generer_coups_candidats` : seuls les mots ajoutés par la seconde
      génération, donc absents du vocabulaire du niveau, y sont soumis).
      Nouvelle fonction privée `_mot_connu_vocabulaire_long(mot,
      part_vocabulaire_long)` : hachage SHA-256 stable du texte du mot
      (PAS le `hash()` intégré de Python, randomisé d'un processus à
      l'autre via `PYTHONHASHSEED`) comparé à `part_vocabulaire_long` — un
      même mot est donc toujours connu ou toujours inconnu, indépendamment
      de la graine de la partie et de l'ordre de génération des coups.
      `None` ou `1.0` (défaut) : tous les mots longs restent accessibles,
      comportement identique, bit à bit, à celui du lot H bis.
  - **`scrabble.moteur.personnages`** :
    - `POIDS_TIRAGE_SCRABBLE_CHASSEUR = 5.0` : nouvelle constante, champ
      plat (comme les trois réglages précédents du Chasseur) — voir le
      calcul ci-dessous.
    - `PART_VOCABULAIRE_LONG_CHASSEUR = {INTERMEDIAIRE: 1.0, AVANCE: 0.5}` :
      table niveau → part, PAS un champ plat (contrairement aux autres
      réglages du personnage) puisque l'intention demande deux valeurs
      différentes selon le niveau. Nouveau champ optionnel
      `Personnage.part_vocabulaire_long_par_niveau` (`dict[Niveau, float] |
      None`, défaut `None`) et nouvelle fonction publique
      `profil_pour_niveau(cle, niveau)` : renvoie `PERSONNAGES[cle].profil`
      tel quel, sauf si `part_vocabulaire_long_par_niveau` est renseigné ET
      contient une entrée pour `niveau`, auquel cas `part_vocabulaire_long`
      est remplacé par cette valeur (tous les autres champs inchangés).
      `niveau=None`, ou un niveau absent de la table, laissent le profil
      inchangé. **`.profil` (accès direct) reste la valeur PLATE, sans
      résolution de niveau** — c'est délibéré : les tests existants du lot H
      bis qui lisent `PERSONNAGES["chasseur_de_scrabbles"].profil`
      directement (AVANCE/EXPERT/CHAMPION_DU_MONDE) continuent de voir
      `part_vocabulaire_long=None` (100 %, comportement du lot H bis) sans
      aucune modification — seuls les appelants qui connaissent le niveau du
      joueur (le jeu réel, le script de mesure) doivent appeler
      `profil_pour_niveau`, jamais `.profil` directement.
  - **`scrabble.ui.jeu`** : `_profil_joueur_ia(joueur)` résout désormais via
    `profil_pour_niveau(joueur.personnage, joueur.niveau)` au lieu de
    `obtenir_personnage(joueur.personnage).profil` — c'est ce chemin qui
    fait que la part de vocabulaire long par niveau du Chasseur s'applique
    réellement en jeu (`joueur.niveau` est toujours renseigné pour un joueur
    IA). Sans effet pour tout personnage sans table de surcharge (Classique,
    Opportuniste) : `profil_pour_niveau` y renvoie alors exactement
    `.profil`, comme avant.
  - **`scripts/mesurer_force_niveaux.py`** : `ConfigJoueur.profil()` résout
    pareillement via `profil_pour_niveau(self.personnage, self.niveau)` au
    lieu de l'accès direct `PERSONNAGES[self.personnage].profil` — **même
    chemin que le jeu réel**, condition explicitement demandée par l'issue
    pour que le tirage pondéré et la part de vocabulaire long réglés par
    personnage s'appliquent identiquement en mesure et en partie.

### Calcul justifiant `POIDS_TIRAGE_SCRABBLE_CHASSEUR = 5.0`

Aux niveaux concernés, la tranche de meilleurs coups compte, en pratique, de
l'ordre de 10 à 20 coups. Sans ce champ (tirage uniforme), la probabilité de
tirer un scrabble présent dans la tranche n'est que `1/n` (10 % à n = 10,
5 % à n = 20) — c'est précisément le constat de départ de l'issue (0,05
scrabble/partie à Intermédiaire contre 0,02 pour Classique, dans la marge
d'erreur). Avec un poids `w` sur ce seul coup parmi les `n` de la tranche
(chaque autre coup gardant le poids 1), cette probabilité devient
`w / (n - 1 + w)`. Pour `w = 5` : `5 / (10 - 1 + 5) = 5/14 ≈ 36 %` à n = 10,
et `5 / (20 - 1 + 5) = 5/24 ≈ 21 %` à n = 20 — une hausse d'un facteur 3 à 4
par rapport au tirage uniforme, tout en laissant encore la majorité des
tirages aux autres coups de la tranche (ni un passage au tirage toujours
gagnant, qui romprait la règle « même tranche, probabilités seulement
modifiées », ni un effet encore dilué au point de rester dans la marge
d'erreur).

### Calcul justifiant `PART_VOCABULAIRE_LONG_CHASSEUR`

- **Intermédiaire : 1,0 (100 %, inchangé).** Le constat de départ à ce
  niveau est que le style ne se voit pas assez, pas qu'il est trop fort :
  rien à retirer côté vocabulaire, le levier est le tirage pondéré ci-dessus.
- **Avancé : 0,5 (50 %).** Le constat de départ à ce niveau (qui joue
  toujours son meilleur coup, donc insensible au tirage pondéré) est
  l'inverse : Chasseur trop fort (61 % de victoires, environ +20 points par
  partie contre Classique), un écart que faire varier `poids_leave` de 1,0 à
  2,0 ne corrigeait pas (l'écart restait de 14 à 23 points, la force venant
  du vocabulaire, pas du leave). Réduire de moitié le vocabulaire long
  accessible hors du vocabulaire du niveau est un point de départ médian
  entre « tout » (trop fort) et « rien » (retour à Classique) — à affiner
  par Alain après mesure réelle (voir les commandes ci-dessous).

### Neutralité stricte

- Un profil sans `poids_tirage_scrabble` (absent, ou `ProfilPersonnage()`
  vide) consomme le générateur aléatoire EXACTEMENT comme avant
  l'introduction du champ, pour les six niveaux — testé explicitement avec
  un générateur espion qui compte les appels à `choice`/`choices` et compare
  `getstate()` avant/après (`TestNeutraliteTirage`, paramétrée sur
  `list(Niveau)`), pas seulement le coup produit.
- Un profil sans `part_vocabulaire_long` (ou `1.0`) reproduit bit à bit
  l'ensemble de coups candidats du lot H bis (`TestPartVocabulaireLong`).
- Les deux champs restent `None` pour Classique et Opportuniste — strictement
  additifs, aucun effet de bord.
- `profil_pour_niveau` pour un personnage sans table de surcharge (Classique,
  Opportuniste), ou pour un niveau absent de la table, renvoie exactement
  `.profil` — aucune mutation du profil de base du registre.
- Le tirage Aléatoire et les réglages par niveau (`_MALUS_LONGUEUR`,
  `_BONUS_PREMIUM`, `_POIDS_LEAVE`) ne sont pas touchés.

### Journal de décision et évaluation

`evaluer_coups` n'a reçu aucune modification : la pondération du tirage
n'intervient qu'après le tri (dans `choisir_coup`, jamais dans
`_trier_par_score_strategique`), donc le journal (alternatives, rang du coup
choisi) reste calculé exactement comme avant. La part de vocabulaire long
étant une fonction pure du texte du mot (pas de l'aléa de la partie),
`evaluer_coups` appelé avec le même `profil`/`dictionnaire_complet` que
`choisir_coup` reste automatiquement en phase avec l'ensemble de coups
candidats réellement consulté — aucune logique de cohérence supplémentaire à
écrire.

### Tests ajoutés

- `tests/test_moteur_ia.py` : `TestNeutraliteTirage` (consommation du
  générateur aléatoire identique sur les six niveaux, paramétrée) ;
  `TestTirageSPondereDansLaTranche` (fréquence de tirage proche de la valeur
  théorique et nettement supérieure au tirage uniforme sur une tranche
  fabriquée, à 10/15/20 coups ; composition de la tranche inchangée ; tirage
  réellement pondéré, pas déterministe, même à poids élevé) ;
  `TestMotConnuVocabulaireLong` (déterminisme et indépendance de l'ordre,
  bornes à 0,0/1,0, proportion proche de la part sur une liste de mots
  fabriquée, plusieurs valeurs) ; `TestPartVocabulaireLong` (part à 100 %
  identique au lot H bis, part à 0 % sans aucun mot long hors vocabulaire,
  mots courts et vocabulaire du niveau non concernés quelle que soit la
  part, résultat stable entre deux appels, neutralité des autres profils).
- `tests/test_moteur_personnages.py` : `TestPoidsTirageScrabbleChasseur`
  (constante, neutralité des autres personnages, et confirmation du
  correctif — Chasseur choisit désormais plus souvent le scrabble que
  Classique à Intermédiaire, pas seulement à Avancé/Expert/Champion du
  monde comme au lot H bis) ; `TestPartVocabulaireLongChasseur` (valeurs de
  la table, `.profil` qui ne porte jamais la résolution par niveau,
  `profil_pour_niveau` pour Intermédiaire/Avancé/niveau absent/`None`/clé
  inconnue, non-mutation du profil de base, neutralité pour Classique et
  Opportuniste).
- **Tests verts** : 1143 avant ce lot (1138 passés + 5 échecs préexistants,
  sans rapport avec ce lot — reconfirmés préexistants via `git stash`) ;
  **1182 après** (1177 passés + les 5 mêmes échecs préexistants, inchangés).
  Aucune régression, 39 tests nets ajoutés.

## Commandes de mesure prêtes à l'emploi

À lancer par Alain avec le dictionnaire réel installé (absent de ce worktree
isolé). Même script, même chemin que le jeu réel (`ConfigJoueur.profil()`
passe maintenant par `profil_pour_niveau`, voir plus haut) : le tirage
pondéré et la part de vocabulaire long s'y appliquent donc bien.

**Point 6 — tirage pondéré, Intermédiaire, plusieurs valeurs de
`POIDS_TIRAGE_SCRABBLE_CHASSEUR`.** Éditer la constante dans
`src/scrabble/moteur/personnages.py` entre chaque commande (le script ne
propose pas de surcharge en ligne de commande pour un champ de personnage
propre à un seul d'entre eux, comme pour `BONUS_PREMIUM_OPPORTUNISTE` —
mêmes conventions que pour Opportuniste) :

```
# POIDS_TIRAGE_SCRABBLE_CHASSEUR = 5.0 (valeur de départ)
python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_intermediaire_poids5.csv

# Puis éditer POIDS_TIRAGE_SCRABBLE_CHASSEUR = 3.0, relancer :
python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_intermediaire_poids3.csv

# Puis POIDS_TIRAGE_SCRABBLE_CHASSEUR = 8.0, relancer :
python scripts/mesurer_force_niveaux.py INTERMEDIAIRE INTERMEDIAIRE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_intermediaire_poids8.csv
```

**Point 11 — part de vocabulaire long, Avancé, plusieurs valeurs de
`PART_VOCABULAIRE_LONG_CHASSEUR[Niveau.AVANCE]`**, pour amener l'écart de
points près de zéro (objectif de l'issue) :

```
# PART_VOCABULAIRE_LONG_CHASSEUR[Niveau.AVANCE] = 0.5 (valeur de départ)
python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_avance_part50.csv

# Puis éditer la table à 0.25, relancer :
python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_avance_part25.csv

# Puis à 0.75, relancer :
python scripts/mesurer_force_niveaux.py AVANCE AVANCE \
    --personnage-a chasseur_de_scrabbles --personnage-b classique \
    --vocab palier --parties 100 \
    --csv style_chasseur_vs_classique_avance_part75.csv
```

Si le taux de victoire/l'écart de points à Avancé reste loin de ~50 %/0 après
ces trois valeurs, affiner par dichotomie autour de la valeur la plus
proche. Si au contraire Intermédiaire montre déjà un style visible sans
distordre le taux de victoire (Chasseur doit rester proche de 50 % contre
Classique à niveau égal, comme pour Opportuniste), la valeur de départ du
poids de tirage peut rester 5,0 sans ajustement supplémentaire. Valeurs à
ajuster uniquement sur validation d'Alain, pas en boucle automatique.
