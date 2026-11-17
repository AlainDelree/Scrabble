# Serveur local (prototype)

À lire avant de toucher `src/scrabble/serveur/`.

Prototype **un seul joueur de confiance**, pour essayer l'interface
existante dans un navigateur (bureau, puis téléphone sur le même réseau
local) sans attendre une vraie version « serveur » du jeu. Bibliothèque
standard uniquement (`http.server`) : aucune dépendance ajoutée.

```
PYTHONPATH=src python -m scrabble.serveur [--reseau] [--port 8765] [--dossier-donnees CHEMIN]
```

- Par défaut : écoute sur `127.0.0.1` seulement (cette machine). `--reseau`
  bascule sur `0.0.0.0` (joignable depuis un téléphone du même réseau
  local) — le serveur ne touche à aucun pare-feu, à l'utilisateur de
  l'ouvrir si besoin.
- Port par défaut **8765** (délibérément différent de 8000).
- `--dossier-donnees` : dossier de données utilisateur du serveur
  (`config.json`, `data/parties.db`, `logs/`) — **distinct** de celui de
  l'application de bureau par défaut, pour ne jamais mélanger ni écraser
  les parties du bureau. Le dictionnaire (`data/dictionnaire/`, lu depuis
  la racine du dépôt) n'est lui jamais copié ni redirigé : il reste la
  seule copie en lecture, partagée.

**AUCUNE authentification.** Affiché au démarrage : réservé à un réseau
local de confiance, jamais à exposer sur Internet.

**Une seule partie à la fois** (même modèle que le bureau : un seul
routeur d'API par processus). Un second navigateur qui se connecte partage
le MÊME état de partie que le premier (pas de comptes, pas de session par
onglet) — limite connue du prototype, non résolue.

Les fonctions qui, côté bureau, supposent une fenêtre pywebview native
sont adaptées dans `serveur/` sans toucher à `ui/` :
- navigation Accueil↔Jeu : le routeur laissé sans fenêtre saute sa
  navigation Python ; un script injecté dans les pages HTML navigue à sa
  place (`window.location.href`) sur succès ;
- diffusion d'état après chaque coup : relayée en Server-Sent Events
  (`/__scrabble__/evenements`) vers le JS déjà présent côté client ;
- positionnement/maximisation de fenêtre : code déjà tolérant à une
  fenêtre absente, aucune adaptation nécessaire.

## Verrouillage du dictionnaire

Le dictionnaire (`data/dictionnaire/`) n'est jamais diffusé au navigateur ;
tout appel permettant de le reconstituer mot par mot est verrouillé côté
serveur, dans `scrabble/serveur/securite.py` (réglages ci-dessous), appliqué
par `scrabble/serveur/httpd.py` AVANT tout appel au routeur :

- **Fonctions interdites** — les quatre méthodes de gestion des mots de
  l'onglet Dictionnaire des réglages (`rechercher_mot`, `ajouter_mot`,
  `retirer_mot`, `marquer_classique_mot`) sont refusées pour tous les
  clients (HTTP 403) et absentes de la liste des fonctions exposées au
  navigateur — jamais appelables depuis le téléphone. `verifier_mot`
  (champ « Tapez un mot à tester » de l'écran de jeu) n'est PAS concernée :
  limitée en fréquence (ci-dessous), pas interdite. L'onglet Dictionnaire
  des réglages est masqué en CSS, injecté par le serveur dans les pages
  HTML servies — aucun fichier de `ui/web/` modifié, le bureau garde
  l'onglet.
- **Lettres hors chevalet** — `poser_lettre_en_attente` (choix de la
  lettre d'un joker) et `verifier_coup`/`poser_mot` (quand `placements`
  est fourni explicitement) sont recontrôlées contre le chevalet réel du
  joueur dont c'est le tour, lu via les fonctions déjà publiques
  `obtenir_etat` + `obtenir_chevalet` — aucun accès à l'état privé
  d'`ApiJeu`, donc aucune modification de `scrabble/ui/`. Un joker du
  chevalet reste utilisable avec n'importe quelle lettre choisie,
  seulement si l'emplacement visé porte réellement un joker.
- **Limites de fréquence** — réglables dans `scrabble/serveur/securite.py`
  (`LIMITES_FREQUENCE`, `PALIERS_BLOCAGE_SECONDES`) : `verifier_coup` et
  `poser_mot` (même oracle accepté/refusé, chaque appel compte qu'il soit
  accepté ou refusé) 30 appels/minute et 1 000/jour, `verifier_mot` 10
  appels/minute et 200/jour (plus stricte : elle accepte n'importe quelle
  suite de lettres). Au-delà, refus `{"succes": False, "erreur": "Trop de
  vérifications, réessayez dans quelques minutes."}` ; une insistance
  après un refus allonge la pause (1, 5, puis 15 minutes, plafonnée),
  réinitialisée au premier appel de nouveau accepté. Par adresse de
  client (pas de comptes pour l'instant — la limite sera rattachée au
  compte quand les comptes existeront). **Compteurs en mémoire du
  processus serveur : remis à zéro à chaque redémarrage.**
- **Journal des abus** — chaque refus (fonction interdite, limite
  atteinte, lettre hors chevalet) ajoute une ligne au journal du serveur
  (heure, adresse, fonction/limite concernée) — jamais les arguments de
  l'appel (lettres, mots) ni leurs résultats.
