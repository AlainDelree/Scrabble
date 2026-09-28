# Changelog — Issue #433

## Analysé (aucun changement de code)

- **Issue #433** — Demande de présélectionner « Joueur humain » par défaut à
  l'ajout d'un joueur, tant qu'aucun humain n'est déjà présent dans la
  partie. Analyse de `ui/web/accueil.html` / `accueil.js` / `ui/accueil.py` :
  le comportement demandé est **déjà** celui du code actuel, hérité des
  issues #175 et #299. Il n'existe plus de dialogue unique avec sélection de
  type : le bouton « Ajouter un joueur » (`btn-ajouter-humain`) n'ajoute
  QUE des joueurs humains et se cache entièrement (`hidden`, pas de
  `disabled`) dès qu'un humain est présent (`peut_ajouter_humain`
  redevient `False` — voir `test_limite_un_seul_humain`,
  `test_second_humain_refuse_meme_table_non_pleine` dans
  `tests/test_accueil.py`) ; les six boutons de niveau ajoutent directement
  un ordinateur sans étape intermédiaire (issue #299, modale « Ajouter un
  ordinateur » déjà supprimée). Concrètement, tant qu'aucun humain n'existe
  encore : un clic sur « Ajouter un joueur » ouvre `modale-humain`, qui ne
  contient plus qu'un champ prénom — aucune sélection de type à faire, ou
  ajoute même l'humain directement sans modale si un prénom principal est
  déjà enregistré (`accueil.js` lignes 364-381). Le résultat attendu décrit
  dans l'issue est donc déjà obtenu par construction, sans qu'aucun code
  supplémentaire ne soit nécessaire.
