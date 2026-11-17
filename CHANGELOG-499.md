# Changelog — Issue #499

## Sécurité

- **`actualise.py` : raisons séparées pour `S603` et `S607` sur le
  lancement de `cmd.exe` (issue #499).**
  - `src/scrabble/actualise.py` (ligne du `subprocess.Popen(["cmd.exe", "/c",
    str(bat)])`) : le commentaire unique au-dessus de cette ligne, qui ne
    justifiait que `S603` (chemin `bat` validé), est remplacé par deux
    raisons distinctes, chacune nommant son code : `S603` reprend la
    justification existante (chemin déjà validé par `chemin_actualise_valide`,
    autres arguments constants) ; `S607` explique pourquoi `cmd.exe` est
    lancé par son nom court plutôt que par un chemin complet (interpréteur
    système Windows, risque accepté car il suppose déjà un accès en
    écriture au dossier de l'application). Ligne de code et `# nosec
    B603,B607` inchangés ; la ligne 114 (`S603` seul) n'est pas touchée.
