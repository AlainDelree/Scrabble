# Changelog — Issue #460

## Changé

- **Build et installateur : retrait des dictionnaires de l'archive
  publique, désinstallation qui conserve les données déposées à la main.**
  Le dépôt du jeu étant public, Actualise télécharge les mises à jour
  (archive de Release) sans identifiant : tout ce qui y était embarqué était
  donc public. Les dictionnaires et listes de mots de `data/dictionnaire/`
  ne sont désormais plus embarqués ni dans l'archive `scrabble-vN.zip`
  d'Actualise, ni dans `Scrabble-Setup.exe` ; ils sont déposés à la main par
  Alain dans `{dossier d'installation}\data\` sur chaque poste, séparément
  des mises à jour du programme.

  - **`scrabble.spec`** : la fonction `ajouter_elements_dictionnaire`
    (listes `ELEMENTS_DICTIONNAIRE`/`ELEMENTS_DICTIONNAIRE_TIERS`, issue
    #339) est retirée. Plus aucun fichier de `data/dictionnaire/`
    (dictionnaires tiers ODS8/Hunspell, `definitions.json`,
    `mots_courants*.txt`, caches `trie_cache*.pkl`,
    `belgicismes_a_revoir.csv`, personnalisations `mots_ajoutes_*`/
    `mots_retires_*`, `classiques_*`, `README.md`) n'est embarqué. Les
    autres embarquements (ressources de l'interface, icône) sont inchangés ;
    `data/personnages/` n'est pas concerné. La règle qui faisait échouer le
    build si aucun dictionnaire tiers n'était trouvé sur le disque de build
    est supprimée (elle n'a plus de sens, ce script ne lit plus ce dossier)
    et remplacée par un message d'information dans le journal du build
    (`avertir_dictionnaires_non_embarques`). Le garde-fou de taille de
    l'archive (`verifier_taille_datas`/`SEUIL_TAILLE_DATAS_OCTETS`) est
    conservé.

  - **`build/rebuild_scrabble.bat`** : l'étape 0 ne vérifie plus la présence
    de `data\dictionnaire\French-Scrabble-ODS8-main` (elle affiche
    désormais un message d'information équivalent) ; le `robocopy` qui copie
    les sources vers le répertoire de build local exclut maintenant
    `data\dictionnaire` (chemin complet, pour ne pas confondre avec
    `src\scrabble\dictionnaire\`, le code source), devenu inutile à copier
    puisque plus lu par `scrabble.spec`.

  - **`installeur/scrabble.iss`** : la désinstallation ne supprime plus
    `{app}\data` en bloc (section `[UninstallDelete]`) — elle ne touche plus
    ni à `data\dictionnaire\` ni aux fichiers de `data\personnages\` déposés
    à la main (ex. `lettre_mots_meral.txt`, jamais suivi par git), qui
    doivent survivre à une désinstallation ou réinstallation. Les entrées de
    nettoyage pour `{app}\logs` et `{app}\config.json` sont conservées. Un
    message s'affiche désormais à la fin de l'installation
    (`AfficherMessageDictionnaires`) pour rappeler que les dictionnaires ne
    sont pas inclus et doivent être copiés à la main dans `{app}\data\`
    avant le premier lancement.

  - **Documentation** : `data/dictionnaire/README.md` et
    `installeur/README.md` décrivent désormais explicitement ce qui est
    embarqué et ce qui ne l'est pas, l'emplacement où déposer les données
    sur un PC, et le fait que les mises à jour d'Actualise ne touchent pas
    aux données (elle ne supprime que les chemins listés dans le manifeste
    de l'archive, qui ne référence jamais `data/dictionnaire`).

  Comportement du jeu au lancement, chargement des données et personnages
  inchangés. Aucun build Windows n'a été lancé pour cette issue (vérification
  manuelle de l'archive à faire après un build réel, voir le rapport de
  clôture de l'issue).
