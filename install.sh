#!/usr/bin/env bash
#
# install.sh — Installeur Linux pour Scrabble (Ubuntu 24.04)
#
# Usage : bash install.sh
#
# Ce script clone (ou met à jour) le dépôt Scrabble dans ~/Scrabble,
# installe les dépendances Python, propose de récupérer le dictionnaire
# ODS8 depuis une clé USB, puis crée un alias shell et une entrée dans
# le menu des applications. Il est idempotent : le relancer ne casse
# rien si tout est déjà installé.

set -e

REPO_URL="https://github.com/AlainDelree/Scrabble.git"
INSTALL_DIR="$HOME/Scrabble"
DICO_DIR="$INSTALL_DIR/data/dictionnaire/French-Scrabble-ODS8-main"
BASHRC="$HOME/.bashrc"
ALIAS_LINE="alias scrabble='python3 $HOME/Scrabble/main.py'"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/scrabble.desktop"

echo "=== Installation de Scrabble ==="
echo

# 1. Vérification des prérequis
echo "--- Vérification des prérequis ---"
manquants=()
for cmd in git python3 pip3; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        manquants+=("$cmd")
    fi
done

if [ "${#manquants[@]}" -ne 0 ]; then
    echo "Erreur : les outils suivants sont introuvables : ${manquants[*]}"
    echo "Installez-les puis relancez ce script, par exemple :"
    echo "  sudo apt update && sudo apt install -y git python3 python3-pip"
    exit 1
fi
echo "OK : git, python3 et pip3 sont disponibles."
echo

# 2. Clonage ou mise à jour du dépôt
echo "--- Récupération du code ---"
if [ -d "$INSTALL_DIR" ]; then
    echo "Le dossier $INSTALL_DIR existe déjà, mise à jour..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    echo "Clonage du dépôt dans $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi
echo

# 3. Installation des dépendances Python
echo "--- Installation des dépendances Python ---"
pip3 install -r "$INSTALL_DIR/requirements.txt" --break-system-packages
echo

# 4. Dictionnaire ODS8
echo "--- Dictionnaire ODS8 ---"
if [ -d "$DICO_DIR" ]; then
    echo "Le dictionnaire ODS8 est déjà présent ($DICO_DIR)."
else
    mkdir -p "$INSTALL_DIR/data/dictionnaire"

    trouves=()
    if [ -d "/media/$USER" ]; then
        while IFS= read -r -d '' chemin; do
            trouves+=("$chemin")
        done < <(find "/media/$USER" -maxdepth 3 -type d -name "French-Scrabble-ODS8-main" -print0 2>/dev/null)
    fi

    source_choisie=""
    if [ "${#trouves[@]}" -gt 0 ]; then
        echo "Dossier(s) ODS8 trouvé(s) sur des supports amovibles :"
        i=1
        for chemin in "${trouves[@]}"; do
            echo "  $i) $chemin"
            i=$((i + 1))
        done
        echo "  M) Entrer un chemin manuellement"
        echo "  N) Ignorer (le jeu démarrera sans ODS8, Hunspell sera utilisé)"
        read -r -p "Votre choix : " choix

        if [[ "$choix" =~ ^[0-9]+$ ]] && [ "$choix" -ge 1 ] && [ "$choix" -le "${#trouves[@]}" ]; then
            source_choisie="${trouves[$((choix - 1))]}"
        elif [[ "$choix" =~ ^[Mm]$ ]]; then
            read -r -p "Chemin complet du dossier French-Scrabble-ODS8-main : " source_choisie
        fi
    else
        echo "Aucune clé USB avec un dossier French-Scrabble-ODS8-main détectée sous /media/$USER."
        read -r -p "Entrer un chemin manuellement ? (chemin, ou vide pour ignorer) : " source_choisie
    fi

    if [ -n "$source_choisie" ] && [ -d "$source_choisie" ]; then
        echo "Copie de $source_choisie vers $DICO_DIR..."
        cp -r "$source_choisie" "$DICO_DIR"
        echo "Dictionnaire ODS8 installé."
    else
        echo "Aucun dictionnaire ODS8 installé : le jeu démarrera sans ODS8 (Hunspell sera utilisé)."
    fi
fi
echo

# 5. Alias dans ~/.bashrc
echo "--- Alias shell ---"
if [ -f "$BASHRC" ] && grep -Fq "$ALIAS_LINE" "$BASHRC"; then
    echo "L'alias 'scrabble' est déjà présent dans $BASHRC."
else
    {
        echo ""
        echo "# Alias Scrabble (ajouté par install.sh)"
        echo "$ALIAS_LINE"
    } >> "$BASHRC"
    echo "Alias 'scrabble' ajouté à $BASHRC."
fi
echo

# 6. Entrée dans le menu des applications
echo "--- Entrée dans le menu des applications ---"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=Scrabble
Exec=python3 $HOME/Scrabble/main.py
Icon=$HOME/Scrabble/assets/scrabble.ico
Type=Application
Categories=Game;
EOF
chmod +x "$DESKTOP_FILE"
echo "Fichier créé : $DESKTOP_FILE"
echo

# 7. Message de fin
echo "=== Installation terminée ==="
echo "Lancez le jeu avec la commande 'scrabble' (après 'source ~/.bashrc')"
echo "ou depuis le menu des applications."
