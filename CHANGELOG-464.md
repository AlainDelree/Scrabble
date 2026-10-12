# Changelog — Issue #464

## Ajouté

- **Marqueur pytest `lent` et exclusion propre des échecs dépendant de
  l'environnement, documentés dans `CONTEXTE.md`.** Chaque issue forçait
  CCL à lancer la suite deux fois (code d'origine puis le sien) pour
  prouver que cinq échecs systématiques dans les dossiers de travail
  isolés étaient préexistants — 4 à 7 minutes perdues à chaque fois.

  - **`pytest.ini`** : déclaration du marqueur `lent` (tests > 8 s).
  - **`tests/test_moteur_ia.py`** : marqueur `@pytest.mark.lent` sur les
    quatre tests de `TestProgressionTrieIaRestreint` (12 à 44 s, simulations
    de parties complètes) et sur `test_expert_score_moyen_entre_intermediaire_et_avance`
    (~7,4 s ici, 9-15 s rapportés sur le poste d'Alain). Ces tests restent
    dans la suite complète ; `-m "not lent"` les exclut désormais (24,9 s
    contre 137,1 s pour la suite complète, mesuré en séquentiel sans
    `pytest-xdist`).
  - **`tests/_aides_test_environnement.py`** (nouveau) : helper
    `palier_vocabulaire_indisponible(nom_palier)`, vrai quand le fichier de
    vocabulaire IA d'un palier est absent du disque (`data/dictionnaire/`
    gitignoré, fourni manuellement — absent d'un dossier de travail isolé).
  - **`tests/test_accueil.py`** : `test_infos_tirage_memorisees` ignoré
    (raison explicite) si le palier `intermediaire` est indisponible —
    cause réelle : `ApiAccueil.ajouter_ordinateur("Intermédiaire")` refuse
    silencieusement (vocabulaire IA absent), donc la table ne compte jamais
    les 3 joueurs attendus.
  - **`tests/test_journal_integration.py`** : `test_ajout_ordinateur_journalise`
    (palier `facile`) et `test_lancer_partie_journalise_avec_nb_joueurs`
    (palier `intermediaire`) ignorés pour la même cause — aucun ordinateur
    n'est réellement ajouté, donc rien n'est journalisé.
  - **`tests/test_application.py`** : `test_methode_propre_au_jeu_hors_vue_leve_attribute_error`
    et `test_parcours_complet_une_seule_session_et_fermeture` ignorés si le
    `theme_plateau` lu dans le `config.json` réel du poste (non mocké) n'est
    pas `"classique"`. Cause réelle, distincte des hypothèses de l'issue
    (interface graphique/dictionnaire) : voir note ci-dessous.
  - **`CONTEXTE.md`** : nouvelle section « Tests » (commande par défaut,
    quand relancer la suite complète, interdiction de comparer avec le code
    d'origine sauf échec lié aux fichiers modifiés, `-n auto` optionnel).

## Note — défaut potentiel révélé, non corrigé (hors périmètre de l'issue)

`ApiTirageOrdre.obtenir_theme_plateau()`
(`src/scrabble/ui/api_tirage_ordre.py:214`) retombe sur `"classique"` si la
valeur lue est inconnue, mais le défaut réel de `theme_plateau` dans
`CONFIG_DEFAUT` (`src/scrabble/config.py:90`) est `"vert"` depuis l'issue
#342. Les deux tests cités ci-dessus attendent `"classique"` et ne passent
sur le poste d'Alain que parce que son `config.json` (gitignoré, jamais
réécrit depuis avant l'issue #342) a conservé l'ancienne valeur — un hasard
d'état local, pas une garantie du code. Signalé sans être corrigé, les
vérifications n'étant pas modifiées (consigne de l'issue).
