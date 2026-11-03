# Changelog — Issue #490

## Sécurité

- **`actualise.py` : lancement du `.bat` de fermeture sans `shell=True`
  (issue #490).**
  - À la fermeture de l'application, le `.bat` dont le chemin a déjà été
    validé (issue #484) n'est plus lancé via `subprocess.Popen([str(bat)],
    shell=True)` : le shell n'intervient plus pour interpréter la ligne de
    commande. Windows exigeant un appel explicite à l'interpréteur pour
    exécuter un `.bat` par `CreateProcess`, l'appel passe désormais par
    `subprocess.Popen(["cmd.exe", "/c", str(bat)])` — une liste d'arguments
    distincts, le chemin du `.bat` restant un argument unique, jamais
    recomposé en chaîne de commande.
  - Comportement observable inchangé : ni dossier de travail ni options de
    création de processus explicites avant ou après ce changement (aucun des
    deux appels n'en précisait), le processus lancé continue de survivre à
    la fermeture de Scrabble et `traiter_flag_actualise` ne bloque pas sur ce
    lancement (toujours un simple `Popen`, sans `wait`/`communicate`).
  - Validation du chemin (`chemin_actualise_valide`), suppression du fichier
    indicateur et lancement au démarrage (`contexte == "demarrage"`)
    inchangés.
  - `tests/test_actualise.py` : l'espion remplaçant `subprocess.Popen`
    capture désormais aussi les arguments nommés de l'appel, et
    `test_traiter_flag_legitime_lance_le_processus_attendu` vérifie que
    l'appel se fait sans `shell=True` (`appels_kwargs == [{}]`) et avec
    `["cmd.exe", "/c", str(bat)]` comme liste d'arguments.
  - Non vérifiable sous Linux (poste de développement de cet agent) :
    à tester par Alain sous Windows avec une vraie mise à jour d'Actualise,
    pour confirmer que le `.bat` se lance bien de cette façon et que le
    comportement observé (fenêtre de mise à jour, redémarrage de Scrabble)
    reste identique à avant ce changement.
