# Changelog — Issue #483

## Modifié

- **Serveur téléphone : `poser_mot` limitée en fréquence comme
  `verifier_coup` (anti-sondage du dictionnaire).** L'issue #479 avait
  verrouillé `verifier_mot` (10/min, 200/jour) et `verifier_coup` (30/min,
  1000/jour) côté `src/scrabble/serveur/`, mais pas `poser_mot` : poser des
  mots et observer s'ils sont acceptés ou refusés rouvrait le même oracle de
  dictionnaire. `poser_mot` est désormais ajoutée à `LIMITES_FREQUENCE`
  (`src/scrabble/serveur/securite.py`) avec les mêmes plafonds que
  `verifier_coup` (30/min, 1000/jour) : réutilise tel quel le
  `LimiteurFrequence` existant (aucune seconde implémentation), déjà appliqué
  de façon générique par `src/scrabble/serveur/httpd.py` (`do_POST`) à toute
  fonction présente dans ce dictionnaire. Chaque appel compte, qu'il soit
  accepté ou refusé par le moteur. En cas de dépassement, le refus suit
  exactement le même format que pour `verifier_coup`/`verifier_mot`
  (`{"succes": False, "erreur": "Trop de vérifications, réessayez dans
  quelques minutes."}`, HTTP 200) — affiché par `jeu.js` via
  `afficherMessageCoup`, la même fonction déjà adaptée en portrait par
  l'issue #480 (message qui ne recouvre plus le chevalet, croix de
  fermeture) : aucune modification JS nécessaire. 30 appels/minute et
  1000/jour restent largement au-dessus d'une partie normale (un coup par
  tour). Deux tests ajoutés dans `tests/test_serveur.py`, dans la continuité
  de ceux de l'issue #479 (`test_serveur_limite_la_frequence_de_poser_mot`,
  `test_poser_mot_et_verifier_coup_partagent_les_memes_plafonds`).
  `CONTEXTE.md` mis à jour en conséquence.
