#!/bin/bash

# Farben für die Ausgabe
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Verzeichnis aufräumen ===${NC}"

# Wechsle ins Zielverzeichnis
cd /root/zephyr

# Liste aller Dateien im Verzeichnis
echo -e "${YELLOW}Aktuelle Dateien im Verzeichnis:${NC}"
ls -la

echo -e "\n${YELLOW}Erstelle Backup-Verzeichnis...${NC}"
mkdir -p backup-old-files
chmod 755 backup-old-files

# Dateien, die behalten werden sollen
KEEP_FILES=(
    "twitch-ollama-bot.py"
    "start-bot.sh"
    "game_state.json"
    "venv"
    "training_data"
    "README.md"
    "cleanup-services.sh"
    "diagnose-services.sh"
)

# Verschiebe alle anderen Dateien ins Backup-Verzeichnis
echo -e "\n${YELLOW}Verschiebe nicht benötigte Dateien ins Backup-Verzeichnis...${NC}"
for file in *; do
    # Überspringe Verzeichnisse und die zu behaltenden Dateien
    if [ "$file" = "backup-old-files" ] || [ "$file" = "venv" ] || [ "$file" = "training_data" ]; then
        continue
    fi
    
    KEEP=0
    for keep_file in "${KEEP_FILES[@]}"; do
        if [ "$file" = "$keep_file" ]; then
            KEEP=1
            break
        fi
    done
    
    if [ $KEEP -eq 0 ]; then
        echo -e "  Verschiebe $file nach backup-old-files/"
        mv "$file" backup-old-files/
    fi
done

# Überprüfe, ob die Backup-Dateien von twitch-ollama-bot.py noch existieren
if [ -f "backup-old-files/twitch-ollama-bot.py.bak_cleanup" ]; then
    echo -e "${YELLOW}Backup-Dateien von twitch-ollama-bot.py gefunden.${NC}"
    echo -e "Diese werden für die Wiederherstellung aufbewahrt."
fi

# Erstelle eine kurze Zusammenfassung der Aufräumaktion
echo -e "\n${BLUE}=== Zusammenfassung ===${NC}"
echo -e "${GREEN}Folgende Dateien wurden behalten:${NC}"
for file in "${KEEP_FILES[@]}"; do
    if [ -e "$file" ]; then
        echo "  - $file"
    fi
done

echo -e "\n${YELLOW}Folgende Dateien wurden ins Backup-Verzeichnis verschoben:${NC}"
ls -la backup-old-files/

echo -e "\n${GREEN}Aufräumen abgeschlossen.${NC}"
echo -e "${BLUE}Wichtig:${NC} Falls du eine Datei wiederherstellen musst, findest du sie im Verzeichnis 'backup-old-files'."
