#!/bin/bash

# Screenshot Sync Script
# Macht alle 5 Sekunden einen Screenshot und überträgt ihn zum Server

# Script-Verzeichnis ermitteln
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SERVER="root@ailinux.me"
REMOTE_PATH="/root/zephyr/screenshots"
LOCAL_FILE="$SCRIPT_DIR/current_screenshot.png"
REMOTE_FILE="$REMOTE_PATH/current_screenshot.png"

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Screenshot Sync gestartet ===${NC}"
echo "Lokale Datei: $LOCAL_FILE"
echo "Remote Pfad: $REMOTE_FILE"
echo "Intervall: 5 Sekunden"
echo "Drücke Ctrl+C zum Beenden"
echo

# Screenshot-Tool ermitteln (Priorität: Desktop-spezifische Tools)
if command -v spectacle &> /dev/null; then
    SCREENSHOT_CMD="spectacle -b -n -o"
    echo -e "${GREEN}Verwende spectacle (KDE nativ - empfohlen)${NC}"
elif command -v maim &> /dev/null; then
    SCREENSHOT_CMD="maim"
    echo -e "${GREEN}Verwende maim (schnell und flackerfrei)${NC}"
elif command -v scrot &> /dev/null; then
    SCREENSHOT_CMD="scrot"
    echo -e "${GREEN}Verwende scrot (leichtgewichtig)${NC}"
elif command -v import &> /dev/null; then
    SCREENSHOT_CMD="import -window root"
    echo -e "${GREEN}Verwende ImageMagick import${NC}"
elif command -v grim &> /dev/null; then
    SCREENSHOT_CMD="grim"
    echo -e "${GREEN}Verwende grim (Wayland)${NC}"
elif command -v gnome-screenshot &> /dev/null; then
    SCREENSHOT_CMD="gnome-screenshot -f"
    echo -e "${RED}⚠️  Verwende gnome-screenshot (kann flackern)${NC}"
else
    echo -e "${RED}Fehler: Kein Screenshot-Tool gefunden!${NC}"
    echo "Installiere eins der folgenden Tools:"
    echo "  KDE: spectacle sollte bereits installiert sein"
    echo "  Ubuntu/Debian: sudo apt install maim"
    echo "  oder: sudo apt install scrot"
    echo "  oder: sudo apt install imagemagick"
    exit 1
fi

echo -e "${GREEN}Screenshot-Tool gefunden: $SCREENSHOT_CMD${NC}"

# Remote-Verzeichnis erstellen (einmalig)
echo "Erstelle Remote-Verzeichnis..."
ssh $SERVER "mkdir -p $REMOTE_PATH" 2>/dev/null

if [ $? -ne 0 ]; then
    echo -e "${RED}Fehler: Kann nicht zum Server verbinden!${NC}"
    echo "Stelle sicher, dass SSH-Keys konfiguriert sind."
    exit 1
fi

echo -e "${GREEN}Verbindung zum Server OK${NC}"
echo

# Hauptschleife
counter=1
while true; do
    echo -e "${BLUE}[$(date '+%H:%M:%S')] Screenshot #$counter${NC}"
    
    # Screenshot erstellen
    if $SCREENSHOT_CMD "$LOCAL_FILE" 2>/dev/null; then
        # Dateigröße anzeigen
        size=$(du -h "$LOCAL_FILE" | cut -f1)
        echo "  📸 Screenshot erstellt ($size)"
        
        # Zum Server übertragen
        if scp "$LOCAL_FILE" "$SERVER:$REMOTE_FILE" 2>/dev/null; then
            echo -e "  ✅ ${GREEN}Erfolgreich übertragen${NC}"
        else
            echo -e "  ❌ ${RED}Übertragung fehlgeschlagen${NC}"
        fi
    else
        echo -e "  ❌ ${RED}Screenshot fehlgeschlagen${NC}"
    fi
    
    echo
    ((counter++))
    sleep 5
done
