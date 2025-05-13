#!/bin/bash

# Farben für die Ausgabe
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Konfiguration
BASE_DIR="/root/zephyr"
BOT_SCRIPT="$BASE_DIR/twitch-ollama-bot.py"
LOG_FILE="$BASE_DIR/twitch-ollama-bot.log"
PID_FILE="$BASE_DIR/twitch-ollama-bot.pid"
VENV_DIR="$BASE_DIR/venv"

# Erkennung, ob das Skript als Systemd-Service läuft
IS_SERVICE=false
if [ -n "$INVOCATION_ID" ] || [[ "$1" == "--service" ]]; then
    IS_SERVICE=true
fi

echo -e "${BLUE}=== Twitch-Ollama-Bot Starter ===${NC}"

# Prüfe, ob das Hauptverzeichnis existiert
if [ ! -d "$BASE_DIR" ]; then
    echo -e "${RED}Fehler: Das Verzeichnis $BASE_DIR existiert nicht!${NC}"
    echo -e "${YELLOW}Erstelle Verzeichnis...${NC}"
    mkdir -p "$BASE_DIR"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Verzeichnis erstellt: $BASE_DIR${NC}"
    else
        echo -e "${RED}Konnte Verzeichnis nicht erstellen. Bitte manuell anlegen.${NC}"
        exit 1
    fi
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
        
        # Bei Service-Modus automatisch neustarten ohne Nachfrage
        if [ "$IS_SERVICE" = true ]; then
            RESTART="j"
        else
            read -p "Möchtest du den laufenden Bot neu starten? (j/n): " RESTART
        fi
        
        if [ "$RESTART" = "j" ] || [ "$RESTART" = "J" ]; then
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

# Erstelle virtuelle Umgebung, wenn sie nicht existiert
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Erstelle virtuelle Python-Umgebung...${NC}"
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo -e "${RED}Fehler beim Erstellen der virtuellen Umgebung.${NC}"
        echo -e "${YELLOW}Versuche python3-venv zu installieren...${NC}"
        apt-get update && apt-get install -y python3-venv python3-full
        python3 -m venv "$VENV_DIR"
        if [ $? -ne 0 ]; then
            echo -e "${RED}Konnte virtuelle Umgebung nicht erstellen. Fahre mit Systeminstallation fort.${NC}"
        fi
    fi
fi

# Installiere Abhängigkeiten
if [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Installiere erforderliche Python-Pakete in virtueller Umgebung...${NC}"
    "$VENV_DIR/bin/pip" install requests python-dotenv
else
    echo -e "${YELLOW}Prüfe erforderliche Python-Pakete im System...${NC}"
    # Versuche, die Pakete mit apt zu installieren, wenn sie nicht über pip installiert werden können
    pip3 install requests python-dotenv 2>/dev/null || {
        echo -e "${YELLOW}Installiere Python-Pakete mit apt...${NC}"
        apt-get update
        apt-get install -y python3-requests
        # python-dotenv gibt es möglicherweise nicht als Paket, versuche es mit --break-system-packages
        pip3 install --break-system-packages python-dotenv 2>/dev/null || {
            echo -e "${RED}WARNUNG: Konnte python-dotenv nicht installieren. Der Bot funktioniert möglicherweise nicht korrekt.${NC}"
        }
    }
fi

# Prüfe, ob Ollama läuft
echo -e "${YELLOW}Prüfe Ollama-Server...${NC}"
if ! curl -s --fail http://localhost:11434/api/version > /dev/null; then
    echo -e "${RED}Ollama-Server scheint nicht zu laufen!${NC}"
    echo -e "${YELLOW}Versuche Ollama zu starten...${NC}"
    
    # Versuche Ollama zu starten
    if systemctl is-active --quiet ollama; then
        echo -e "${YELLOW}Ollama-Dienst läuft, aber API antwortet nicht. Neustart...${NC}"
        systemctl restart ollama
    else
        echo -e "${YELLOW}Ollama-Dienst starten...${NC}"
        systemctl start ollama
    fi
    
    # Warte auf Ollama-Server
    echo -e "${YELLOW}Warte auf Ollama-Server...${NC}"
    for i in {1..60}; do
        if curl -s --fail http://localhost:11434/api/version > /dev/null; then
            echo -e "${GREEN}Ollama-Server bereit nach $i Sekunden${NC}"
            break
        fi
        
        if [ $i -eq 60 ]; then
            echo -e "${RED}FEHLER: Ollama-Server nach 60 Sekunden nicht erreichbar!${NC}"
            echo -e "${YELLOW}Bitte starte Ollama mit 'ollama serve' und versuche es erneut.${NC}"
            exit 1
        fi
        
        echo -n "."
        sleep 1
    done
else
    echo -e "${GREEN}Ollama-Server läuft.${NC}"
fi

# Prüfe, ob erforderliche Modelle verfügbar sind
echo -e "${YELLOW}Prüfe erforderliche Modelle...${NC}"
for MODEL in "zephyr" "llava"; do
    if ! curl -s --fail "http://localhost:11434/api/tags" | grep -q "\"name\":\"$MODEL\""; then
        echo -e "${YELLOW}Modell '$MODEL' scheint nicht verfügbar zu sein. Versuche zu pullen...${NC}"
        ollama pull $MODEL
        if [ $? -ne 0 ]; then
            echo -e "${RED}WARNUNG: Konnte Modell '$MODEL' nicht herunterladen.${NC}"
            echo -e "${YELLOW}Der Bot wird möglicherweise nicht korrekt funktionieren.${NC}"
            echo -e "${YELLOW}Du kannst das Modell später manuell installieren mit: 'ollama pull $MODEL'${NC}"
        else
            echo -e "${GREEN}Modell '$MODEL' erfolgreich heruntergeladen.${NC}"
        fi
    else
        echo -e "${GREEN}Modell '$MODEL' ist verfügbar.${NC}"
    fi
done

# Stelle sicher, dass das Bot-Skript ausführbar ist
chmod +x "$BOT_SCRIPT"

# Stelle sicher, dass das Screenshots-Verzeichnis existiert
SCREENSHOTS_DIR="$BASE_DIR/screenshots"
if [ ! -d "$SCREENSHOTS_DIR" ]; then
    echo -e "${YELLOW}Erstelle Screenshots-Verzeichnis...${NC}"
    mkdir -p "$SCREENSHOTS_DIR"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Verzeichnis erstellt: $SCREENSHOTS_DIR${NC}"
    else
        echo -e "${RED}Konnte Screenshots-Verzeichnis nicht erstellen.${NC}"
    fi
fi

# Starte den Bot im Hintergrund
echo -e "${YELLOW}Starte Twitch-Ollama-Bot...${NC}"
if [ -d "$VENV_DIR" ]; then
    "$VENV_DIR/bin/python3" "$BOT_SCRIPT" &
else
    python3 "$BOT_SCRIPT" &
fi
BOT_PID=$!

# Warte kurz, um zu sehen, ob der Prozess sofort stirbt
sleep 2
if ps -p $BOT_PID > /dev/null; then
    echo -e "${GREEN}✓ Bot erfolgreich gestartet mit PID $BOT_PID${NC}"
    
    echo -e "\n${BLUE}=== Bot-Features ===${NC}"
    echo -e "1. ${GREEN}Automatische Witze:${NC} Der Bot erzählt regelmäßig Witze im Chat"
    echo -e "2. ${GREEN}Spielkommentare:${NC} Kommentiert das laufende Spiel"
    echo -e "3. ${GREEN}Bildkommentare:${NC} Beschreibt und kommentiert Szenen im Stream"
    echo -e "4. ${GREEN}Befehlserinnerungen:${NC} Erinnert an verfügbare Befehle"
    echo -e "5. ${GREEN}Fragen-Beantwortung:${NC} Beantwortet Fragen über Ollama"
    
    echo -e "\n${BLUE}Wie überwache ich den Bot?${NC}"
    echo -e "Logs ansehen: ${YELLOW}tail -f $LOG_FILE${NC}"
    echo -e "Bot manuell stoppen: ${YELLOW}kill $BOT_PID${NC}"
    
    # Starte auch den Screenshot-Watcher, falls vorhanden
    WATCHER_SCRIPT="$BASE_DIR/watch_screenshots.py"
    if [ -f "$WATCHER_SCRIPT" ]; then
        echo -e "\n${YELLOW}Starte Screenshot-Watcher...${NC}"
        chmod +x "$WATCHER_SCRIPT"
        if [ -d "$VENV_DIR" ]; then
            nohup "$VENV_DIR/bin/python3" "$WATCHER_SCRIPT" >> "$BASE_DIR/watcher.log" 2>&1 &
        else
            nohup python3 "$WATCHER_SCRIPT" >> "$BASE_DIR/watcher.log" 2>&1 &
        fi
        WATCHER_PID=$!
        if ps -p $WATCHER_PID > /dev/null; then
            echo -e "${GREEN}✓ Screenshot-Watcher gestartet mit PID $WATCHER_PID${NC}"
        else
            echo -e "${RED}FEHLER: Screenshot-Watcher konnte nicht gestartet werden${NC}"
        fi
    fi
else
    echo -e "${RED}FEHLER: Bot konnte nicht gestartet werden oder wurde sofort beendet${NC}"
    echo -e "Überprüfe die Logs für weitere Details: ${YELLOW}cat $LOG_FILE${NC}"
    exit 1
fi

# Erstellen eines systemd-Service (optional)
create_service_file() {
    # Wenn im Service-Modus, überspringe die interaktive Abfrage
    if [ "$IS_SERVICE" = true ]; then
        return 0
    fi
    
    if [ -d "/etc/systemd/system" ]; then
        echo -e "\n${YELLOW}Möchtest du einen systemd-Service für den Bot erstellen? (j/n): ${NC}"
        read create_service
        
        if [ "$create_service" = "j" ] || [ "$create_service" = "J" ]; then
            SYSTEMD_SERVICE="/etc/systemd/system/twitch-ollama-bot.service"
            
            echo -e "${YELLOW}Erstelle systemd-Service-Datei...${NC}"
            
            cat > "$SYSTEMD_SERVICE" << EOLS
[Unit]
Description=Twitch Ollama Chatbot
After=network.target ollama.service
Requires=ollama.service

[Service]
Type=simple
User=root
WorkingDirectory=$BASE_DIR
ExecStart=$BASE_DIR/start-bot.sh --service
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOLS
            
            systemctl daemon-reload
            
            echo -e "${GREEN}Service-Datei erstellt: $SYSTEMD_SERVICE${NC}"
            echo -e "Du kannst den Bot jetzt mit folgenden Befehlen steuern:"
            echo -e "${YELLOW}systemctl start twitch-ollama-bot${NC} - Bot starten"
            echo -e "${YELLOW}systemctl stop twitch-ollama-bot${NC} - Bot stoppen"
            echo -e "${YELLOW}systemctl enable twitch-ollama-bot${NC} - Bot beim Systemstart automatisch starten"
            
            echo -e "\nMöchtest du den Bot beim Systemstart automatisch starten? (j/n): "
            read enable_service
            
            if [ "$enable_service" = "j" ] || [ "$enable_service" = "J" ]; then
                systemctl enable twitch-ollama-bot
                echo -e "${GREEN}Bot wird jetzt beim Systemstart automatisch gestartet.${NC}"
            fi
        fi
    fi
}

# Frage, ob ein systemd-Service erstellt werden soll (nur im interaktiven Modus)
create_service_file

# Im Service-Modus blockieren wir das Skript, damit systemd den Prozess nicht beendet
if [ "$IS_SERVICE" = true ]; then
    echo -e "${BLUE}Laufe im Service-Modus. Prozess bleibt aktiv.${NC}"
    # Halte das Skript am Laufen, solange der Bot läuft
    while ps -p $BOT_PID > /dev/null; do
        sleep 10
    done
    echo -e "${RED}Bot-Prozess wurde beendet, Service wird heruntergefahren.${NC}"
fi

exit 0
