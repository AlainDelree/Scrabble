# Changelog — Issue #458

## Corrigé

- **Tests des personnages désynchronisés des réglages mesurés, et rendus
  robustes aux futurs réglages.** Après les deux lots de mesure (bonus de
  mot favori du Lettré, 40 → 20 ; part de mots courts connus du Chasseur de
  scrabbles à Avancé, 0,7 → 0,55), six tests de
  `tests/test_moteur_personnages.py` échouaient : certains figeaient
  l'ancienne valeur en dur (`BONUS_FAVORI_LETTRE == 40`,
  `PART_VOCABULAIRE_COURT_CHASSEUR == {... 0.7, ... 0.7}`), d'autres
  construisaient un scénario fabriqué (plateau/chevalet réels) dont l'écart
  de score caché entre le mot favori et le coup concurrent dépendait
  implicitement de l'ancien bonus (40), sans marge suffisante avec le
  nouveau (20) à EXPERT/CHAMPION_DU_MONDE (où les tranches de malus/bonus
  de score stratégique diffèrent d'AVANCE).

  - **`TestPartVocabulaireCourtChasseur.test_valeurs_de_depart`,
    `test_profil_pour_niveau_intermediaire`, `test_profil_pour_niveau_avance`**
    : ne vérifient plus les chiffres exacts, seulement les niveaux couverts
    et le domaine de valeur (une part dans `]0, 1]`), ou comparent au
    contenu actuel de `PART_VOCABULAIRE_COURT_CHASSEUR` plutôt qu'à un
    chiffre écrit en dur.

  - **`TestPersonnageLettre.test_lettre_joue_toujours_le_mot_favori_sur_ce_scenario`**
    et **`TestMotsFavorisLettreComplement.test_lettre_joue_un_mot_du_fichier_complementaire`**
    : nouveau scénario fabriqué CONSTRUIT à partir de
    `bonus_favori` lui-même (nouveaux ``CoupNote`` synthétiques, même
    principe que `_coup_note` dans `test_moteur_ia.py`, sans case bonus ni
    malus de longueur ni reliquat — donc rigoureusement indépendant du
    niveau) : le coup concurrent l'emporte d'exactement
    `bonus_favori - 1` points avant bonus, donc le mot favori l'emporte de
    peu (1 point) une fois le bonus ajouté, quelle que soit sa valeur
    actuelle ou future. La sélection réelle (`_choisir_avance`/
    `_choisir_top5`, selon le niveau) est rejouée sur ces coups triés, pour
    continuer à exercer le même code que `choisir_coup`.

  - **`TestPersonnageLettre.test_lettre_profil_mots_favoris_et_bonus_favori`**
    : retrait de l'assertion `BONUS_FAVORI_LETTRE == 40` (seul le câblage du
    profil sur la constante reste vérifié).

  - **Documentation** : le docstring du module de tests précise désormais
    que les constantes de réglage par personnage sont ajustées par mesure
    et ne doivent jamais être figées dans un test.

  Aucune valeur de réglage ni aucun comportement du jeu n'a été modifié —
  seuls les tests (et leur documentation) ont changé.
  137 tests passent dans `tests/test_moteur_personnages.py` (contre 131
  avant correction, 6 en échec). Sur l'ensemble de la suite : 1281 tests
  verts après correction (1275 avant), les 5 mêmes échecs préexistants et
  sans rapport (`test_accueil`, `test_application`, `test_journal_integration`)
  subsistent, confirmés préexistants.
