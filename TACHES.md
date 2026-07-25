# Idées et tâches en attente — Projet Scrabble

Notes diverses à traiter plus tard, pour ne pas perdre le fil entre les
sessions.
-Pour les boutons "Passer" et "Remettre toute ses lettres et passer" -> modal de confirmation
-Rendre plus lisible le bouton "Remettre toute ses lettre et passer"
-Le selecteur de lettre pour le joker est tronqué
-Evaluation de la partie en fonction des points: Échelle d'évaluation des scores Moins de 300 points : Niveau débutant ou partie avec de nombreuses lettres mortes.  De 300 à 400 points : Niveau intermédiaire (joueur occasionnel).  De 400 à 500 points : Bon niveau. Vous arrivez à placer des scrabbles et optimiser les cases multiplicatrices.  Plus de 500 points : Niveau expert ou compétiteur.  -> il faut vérifier si cette évaluation change pour une partie a 2, 3 ou 4 joueurs.
-Lors de la creeation de partie, comme on a abandonné l'idée de plusieurs joueurs humains, il faut sélectionner d'office le joueur humain sans qu'on doive l'ajouter a la main.
-En fin de partie, mettre le tableau de classement dans une modal(Retour menu, Rester sur la partie, Recommencer)
-Dans réglage, pouvoir choisir son avatar(aucun ordi ne peut prendre l'avatar choisi)
-Quand vérifier dictionnaire perd le focus il se referme, il faut que derniers coups fasse de meme.
-Afficher tous les coups du jeu dans derniers coups(les coups les plus récent en haut)

##Creer un fichier meilleurs score
Creer un fichiers meilleur score répartis en 3 catégories(1vs1, 1vs2, 1vs3) et par niveaux(Débutant, facile, Intermédiaire, Avancé, Expert)
Garder les 10 meilleurs score par combinaison catégorie/niveau

## Creer TextField constemment visible pourle dictionnaire

Vu la fréquence d'utilisation du dictionnaire dans l'écran de jeu observée, il faut remplacer le bouton loupe, ouvrant un textfield pour chercher la définition d'un mot par le textefield accessible directement dans l'ecran

## Point de vigilance : gestion d'erreurs dans accueil.py

Dans `src/scrabble/ui/accueil.py`, plusieurs `except (KeyError, TypeError,
Exception)` avalent les erreurs silencieusement (ex.
`sauvegarder_prenom_principal` retourne juste `False` sur toute erreur,
sans log). Pas bloquant, mais à durcir/logger si un bug de sauvegarde
apparaît en pratique.
