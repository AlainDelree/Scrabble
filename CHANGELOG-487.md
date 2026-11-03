# Changelog — Issue #487

## Nettoyage

- **Retrait du suivi git de la liste de mots favoris de Titeuf (partie 1).**
  - `data/personnages/titeuf_mots_favoris.txt` (personnage désactivé, dépôt
    public) sort du suivi git — `git rm --cached`, fichier conservé sur le
    disque — et rejoint `.gitignore`, sur le même principe que
    `data/personnages/lettre_mots_meral.txt`.
  - Vérifié par lecture : le chargement
    (`scrabble.moteur.personnages.charger_mots_favoris`, via
    `scrabble.dictionnaire.dictionnaire.lire_liste_mots`) tolère déjà un
    fichier absent (ensemble vide, sans erreur) — aucun changement de code
    nécessaire.
  - `tests/test_moteur_personnages.py` contient une assertion
    (`CHEMIN_MOTS_FAVORIS_TITEUF.exists()`) qui suppose le fichier présent
    sur le disque : elle continue de passer ici (fichier conservé
    localement) mais échouerait dans un clone neuf qui ne l'aurait jamais
    récupéré (plus suivi par git) — signalé sans être corrigé, cette
    vérification étant hors du périmètre couvert (chargement, pas tests).
    Ni l'installeur ni le build PyInstaller n'exigent sa présence
    (`data/personnages` n'est pas embarqué par `scrabble.spec`).
  - `data/personnages/lettre_mots_favoris.txt` inchangé.

- **Retrait du suivi git des captures obsolètes du harnais de vérification
  visuelle (partie 2).**
  - 112 captures PNG (~17 Mo) de `scripts/_harness_jeu/` retirées de git ET
    du disque : 98 fichiers à la racine sans aucune référence (script,
    test ou documentation) au-delà de leur propre script producteur, plus
    les dossiers d'archive `verif_295_out/` (8 fichiers) et
    `verif_298_out/` (6 fichiers) — résultats ponctuels de vérifications
    visuelles passées, non référencés nulle part. Les 31 scripts
    (`.mjs`/`.py`/`.js`) du harnais sont inchangés.
  - Conservées (toujours suivies) : `i443_accueil_personnages_1280x800.png`
    et `i443_jeu_personnages_1280x800.png`, explicitement citées par leur
    nom dans `CHANGELOG.md` (issue #443) — seules captures du dossier
    référencées en dehors de leur propre script générateur.
  - `.gitignore` : nouveau bloc ignorant `scripts/_harness_jeu/*.png` (avec
    exception pour les deux captures ci-dessus) et
    `scripts/_harness_jeu/verif_*_out/`, pour qu'une future capture ou
    sortie de vérification visuelle ne soit plus suivie par défaut. Aucun
    impact sur `issue-attachments/`, `assets/`, `src/scrabble/ui/web/` ni
    les fichiers `resultats_*.csv`.
