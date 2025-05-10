#!/bin/bash

# Farben für die Ausgabe
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Konfiguration
BASE_DIR="/home/zombie/zephyr"
BOT_SCRIPT="$BASE_DIR/enhanced-zephyr-bot.py"
LOG_FILE="$BASE_DIR/zephyr-bot.log"
PID_FILE="$BASE_DIR/zephyr-bot.pid"
TRAINING_DIR="$BASE_DIR/training_data"

echo -e "${BLUE}=== Erweiterter Zephyr Bot Starter ===${NC}"

# Prüfe, ob das Hauptverzeichnis existiert
if [ ! -d "$BASE_DIR" ]; then
    echo -e "${RED}Fehler: Das Verzeichnis $BASE_DIR existiert nicht!${NC}"
    mkdir -p "$BASE_DIR"
    echo -e "${GREEN}Verzeichnis erstellt: $BASE_DIR${NC}"
fi

# Erstelle Training-Verzeichnis, falls es nicht existiert
if [ ! -d "$TRAINING_DIR" ]; then
    echo -e "${YELLOW}Erstelle Training-Daten-Verzeichnis...${NC}"
    mkdir -p "$TRAINING_DIR"
fi

# Prüfe, ob das Bot-Skript existiert
if [ ! -f "$BOT_SCRIPT" ]; then
    echo -e "${RED}Fehler: Bot-Skript '$BOT_SCRIPT' nicht gefunden!${NC}"
    exit 1
fi

# Prüfe, ob der Bot läuft und stoppe ihn, falls nötig
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null; then
        echo -e "${YELLOW}Bot läuft bereits mit PID $PID${NC}"
        read -p "Möchtest du den laufenden Bot neu starten? (j/n): " restart
        if [ "$restart" = "j" ] || [ "$restart" = "J" ]; then
            echo -e "${YELLOW}Stoppe laufenden Bot mit PID $PID...${NC}"
            kill "$PID"
            sleep 2
            # Prüfe, ob der Bot gestoppt wurde
            if ps -p "$PID" > /dev/null; then
                echo -e "${RED}Bot konnte nicht sauber beendet werden, versuche mit SIGKILL...${NC}"
                kill -9 "$PID"
                sleep 1
            fi
            # Prüfe nochmal
            if ! ps -p "$PID" > /dev/null; then
                echo -e "${GREEN}Bot erfolgreich gestoppt.${NC}"
                echo "$(date) - Bot wurde für Neustart gestoppt." >> "$LOG_FILE"
                rm "$PID_FILE"
            else
                echo -e "${RED}Bot konnte nicht beendet werden. Start abgebrochen.${NC}"
                exit 1
            fi
        else
            echo -e "${BLUE}Start abgebrochen.${NC}"
            exit 0
        fi
    else
        echo -e "${YELLOW}Alte PID-Datei gefunden, aber Bot ist nicht aktiv. Entferne alte PID-Datei.${NC}"
        rm "$PID_FILE"
    fi
fi

# Prüfe, ob alle erforderlichen Python-Pakete installiert sind
echo -e "${YELLOW}Prüfe erforderliche Python-Pakete...${NC}"
pip install -q requests
pip install -q python-dateutil

# Warte auf Ollama-Server
echo -e "${YELLOW}Warte auf Ollama-Server...${NC}"
for i in {1..60}; do
    if curl -s --fail http://localhost:11434/api/version > /dev/null; then
        echo -e "${GREEN}Ollama-Server bereit nach $i Sekunden${NC}"
        break
    fi
    
    if [ $i -eq 60 ]; then
        echo -e "${RED}FEHLER: Ollama-Server nach 60 Sekunden nicht erreichbar!${NC}"
        echo "Bitte starte Ollama mit 'ollama serve' und versuche es erneut."
        exit 1
    fi
    
    echo -n "."
    sleep 1
done

# Stelle sicher, dass das Bot-Skript ausführbar ist
chmod +x "$BOT_SCRIPT"

# Starte den Bot im Hintergrund
echo -e "${YELLOW}Starte Erweiterten Zephyr-Bot...${NC}"
python3 "$BOT_SCRIPT" &
BOT_PID=$!

# Warte kurz, um zu sehen, ob der Prozess sofort stirbt
sleep 2
if ps -p $BOT_PID > /dev/null; then
    echo -e "${GREEN}✓ Bot erfolgreich gestartet mit PID $BOT_PID${NC}"
    
    echo -e "\n${BLUE}=== Bot-Features ===${NC}"
    echo -e "1. ${GREEN}KI-Training:${NC} Der Bot lernt automatisch aus dem Chat"
    echo -e "2. ${GREEN}Erweiterte Befehle:${NC} !witz [kategorie], !zitat, !stimmung, !minigame, uvm."
    echo -e "3. ${GREEN}Minispiele:${NC} Würfeln, Schere-Stein-Papier, Trivia und mehr"
    echo -e "4. ${GREEN}Stimmungsanalyse:${NC} Der Bot passt sich der Chatstimmung an"
    echo -e "5. ${GREEN}Persönlichkeitsentwicklung:${NC} Der Bot entwickelt seine Persönlichkeit basierend auf Interaktionen"
    
    echo -e "\n${BLUE}Wie überwache ich den Bot?${NC}"
    echo -e "Logs ansehen: ${YELLOW}tail -f $LOG_FILE${NC}"
    echo -e "Bot manuell stoppen: ${YELLOW}kill $BOT_PID${NC}"
    echo -e "Bot Statistiken: ${YELLOW}cat $TRAINING_DIR/viewer_stats.json${NC}"
else
    echo -e "${RED}FEHLER: Bot konnte nicht gestartet werden oder wurde sofort beendet${NC}"
    echo -e "Überprüfe die Logs für weitere Details: ${YELLOW}cat $LOG_FILE${NC}"
    exit 1
fi

exit 0
