# Ressources — icône de l'application

Icône de l'application : une **tuile de Scrabble** stylisée (lettre « S »
valant 1 point), dans le style visuel des tuiles du plateau (fond bois/beige,
bordure dorée, lettre brun foncé). Elle remplace l'icône « disquette » qui
n'était que le défaut de PyInstaller (issue #161).

| Fichier             | Rôle                                                             |
|---------------------|------------------------------------------------------------------|
| `scrabble.svg`      | Source vectorielle (référence, réutilisable).                    |
| `scrabble.ico`      | Icône multi-résolutions (16→256) pour Windows / PyInstaller.     |
| `scrabble-256.png`  | Aperçu / usage général (Linux, docs).                            |

Régénérer (rendu déterministe) :

```bash
python scripts/generer_icone.py
```

## Référence dans le packaging Windows

Dans `scrabble.spec` (généré côté Windows, non versionné car `*.spec` est
dans `.gitignore`), pointer l'exécutable sur cette icône :

```python
exe = EXE(
    ...
    icon='assets/scrabble.ico',
)
```

Puis reconstruire avec PyInstaller ; l'icône apparaît alors dans la barre des
tâches Windows à la place de la disquette.
