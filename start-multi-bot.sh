#!/bin/bash

# Farben für die Ausgabe
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Konfiguration
BASE_DIR="/root/zephyr"
BOT_SCRIPT="$BASE_DIR/multi_platform_bot.py"
YOUTUBE_READER="$BASE_DIR/youtube_chat_reader.py"
WATCHER_SCRIPT="$BASE_DIR/watch_screenshots.py"
LOG_FILE="$BASE_DIR/multi-platform-bot.log"
YOUTUBE_LOG="$BASE_DIR/youtube-chat.log"
WATCHER_LOG="$BASE_DIR/screenshot-watcher.log"
PID_FILE="$BASE_DIR/multi-platform-bot.pid"
VENV_DIR="$BASE_DIR/venv"

# Erkennung, ob das Skript als Systemd-Service läuft
IS_SERVICE=false
if [ -n "$INVOCATION_ID" ] || [[ "$1" == "--service" ]]; then
    IS_SERVICE=true
fi

echo -e "${BLUE}=== Zephyr Multi-Platform Bot Starter ===${NC}"
echo -e "${CYAN}Twitch + YouTube Integration mit Ollama KI${NC}"

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

# Prüfe, ob die Bot-Skripte existieren
if [ ! -f "$BOT_SCRIPT" ]; then
    echo -e "${RED}Fehler: Multi-Platform-Bot-Skript '$BOT_SCRIPT' nicht gefunden!${NC}"
    exit 1
fi

if [ ! -f "$YOUTUBE_READER" ]; then
    echo -e "${YELLOW}Warnung: YouTube Reader '$YOUTUBE_READER' nicht gefunden!${NC}"
    echo -e "${YELLOW}YouTube-Chat-Funktionalität wird nicht verfügbar sein.${NC}"
fi

# Prüfe, ob der Bot bereits läuft
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null; then
        echo -e "${YELLOW}Multi-Platform-Bot läuft bereits mit PID $PID${NC}"
        
        if [ "$IS_SERVICE" = true ]; then
            RESTART="j"
        else
            read -p "Möchtest du den laufenden Bot neu starten? (j/n): " RESTART
        fi
        
        if [ "$RESTART" = "j" ] || [ "$RESTART" = "J" ]; then
            echo -e "${YELLOW}Stoppe laufenden Bot mit PID $PID...${NC}"
            kill "$PID"
            sleep 2
            if ps -p "$PID" > /dev/null; then
                echo -e "${RED}Bot konnte nicht sauber beendet werden, versuche mit SIGKILL...${NC}"
                kill -9 "$PID"
                sleep 1
            fi
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
echo -e "${YELLOW}Prüfe Python-Abhängigkeiten...${NC}"
if [ -d "$VENV_DIR" ]; then
    echo -e "${CYAN}Verwende virtuelle Umgebung: $VENV_DIR${NC}"
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install requests python-dotenv
    
    # Prüfe, ob alle Abhängigkeiten installiert sind
    if ! "$VENV_DIR/bin/python" -c "import requests, dotenv" 2>/dev/null; then
        echo -e "${RED}Fehler: Abhängigkeiten konnten nicht installiert werden.${NC}"
        exit 1
    fi
    
    PYTHON_CMD="$VENV_DIR/bin/python3"
else
    echo -e "${YELLOW}Verwende System-Python...${NC}"
    pip3 install requests python-dotenv 2>/dev/null || {
        echo -e "${YELLOW}Installiere Python-Pakete mit apt...${NC}"
        apt-get update
        apt-get install -y python3-requests
        pip3 install --break-system-packages python-dotenv 2>/dev/null || {
            echo -e "${RED}WARNUNG: Konnte python-dotenv nicht installieren. Der Bot funktioniert möglicherweise nicht korrekt.${NC}"
        }
    }
    PYTHON_CMD="python3"
fi

# Prüfe .env-Datei
ENV_FILE="$BASE_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}FEHLER: .env-Datei nicht gefunden: $ENV_FILE${NC}"
    echo -e "${YELLOW}Bitte erstelle eine .env-Datei mit den erforderlichen Konfigurationen.${NC}"
    echo -e "${CYAN}Beispiel-Inhalt:${NC}"
    echo -e "BOT_USERNAME=dein_bot_name"
    echo -e "OAUTH_TOKEN=oauth:dein_token"
    echo -e "CHANNEL=#dein_kanal"
    echo -e "YOUTUBE_API_KEY=dein_youtube_api_key"
    echo -e "YOUTUBE_CHANNEL_ID=deine_channel_id"
    exit 1
fi

# Prüfe, ob Ollama läuft
echo -e "${YELLOW}Prüfe Ollama-Server...${NC}"
if ! curl -s --fail http://localhost:11434/api/version > /dev/null; then
    echo -e "${RED}Ollama-Server scheint nicht zu laufen!${NC}"
    echo -e "${YELLOW}Versuche Ollama zu starten...${NC}"
    
    if systemctl is-active --quiet ollama; then
        echo -e "${YELLOW}Ollama-Dienst läuft, aber API antwortet nicht. Neustart...${NC}"
        systemctl restart ollama
    else
        echo -e "${YELLOW}Ollama-Dienst starten...${NC}"
        systemctl start ollama
    fi
    
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

# Teste YouTube-API (falls konfiguriert)
echo -e "${YELLOW}Teste Platform-Konfigurationen...${NC}"
if [ -f "$YOUTUBE_READER" ]; then
    echo -e "${CYAN}Teste YouTube-Chat-Konfiguration...${NC}"
    timeout 10 "$PYTHON_CMD" "$YOUTUBE_READER" --test 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}YouTube-Konfiguration OK${NC}"
    else
        echo -e "${YELLOW}YouTube-Konfiguration möglicherweise unvollständig (normal, wenn kein Live-Stream aktiv)${NC}"
    fi
fi

# Stelle sicher, dass die Bot-Skripte ausführbar sind
chmod +x "$BOT_SCRIPT"
[ -f "$YOUTUBE_READER" ] && chmod +x "$YOUTUBE_READER"
[ -f "$WATCHER_SCRIPT" ] && chmod +x "$WATCHER_SCRIPT"

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

# Starte den Multi-Platform-Bot
echo -e "${YELLOW}Starte Zephyr Multi-Platform-Bot...${NC}"
"$PYTHON_CMD" "$BOT_SCRIPT" >> "$LOG_FILE" 2>&1 &
BOT_PID=$!

# Warte kurz, um zu sehen, ob der Prozess sofort stirbt
sleep 3
if ps -p $BOT_PID > /dev/null; then
    echo -e "${GREEN}✓ Multi-Platform-Bot erfolgreich gestartet mit PID $BOT_PID${NC}"
    
    # Starte auch den Screenshot-Watcher, falls vorhanden
    if [ -f "$WATCHER_SCRIPT" ]; then
        echo -e "${YELLOW}Starte Screenshot-Watcher...${NC}"
        nohup "$PYTHON_CMD" "$WATCHER_SCRIPT" >> "$WATCHER_LOG" 2>&1 &
        WATCHER_PID=$!
        sleep 1
        if ps -p $WATCHER_PID > /dev/null; then
            echo -e "${GREEN}✓ Screenshot-Watcher gestartet mit PID $WATCHER_PID${NC}"
        else
            echo -e "${YELLOW}⚠ Screenshot-Watcher konnte nicht gestartet werden${NC}"
        fi
    fi
    
    echo -e "\n${BLUE}=== Bot-Features ===${NC}"
    echo -e "1. ${GREEN}Multi-Platform:${NC} Unterstützt Twitch und YouTube gleichzeitig"
    echo -e "2. ${GREEN}Automatische Witze:${NC} Der Bot erzählt regelmäßig Witze im Chat"
    echo -e "3. ${GREEN}Bildanalyse:${NC} Kommentiert Screenshots mit LLaVA Vision-Modell"
    echo -e "4. ${GREEN}Spielkommentare:${NC} Kommentiert das laufende Spiel automatisch"
    echo -e "5. ${GREEN}Chat-Interaktion:${NC} Antwortet auf Fragen und Befehle"
    echo -e "6. ${GREEN}Screenshot-Watcher:${NC} Überwacht automatisch neue Screenshots"
    
    echo -e "\n${PURPLE}=== Verfügbare Befehle ===${NC}"
    echo -e "${CYAN}!witz${NC} - Zufälliger Witz"
    echo -e "${CYAN}!info${NC} - Aktuelle Spielinfos"
    echo -e "${CYAN}!stats${NC} - Spielstatistiken"
    echo -e "${CYAN}!bild / !scene${NC} - Kommentiert aktuellen Screenshot"
    echo -e "${CYAN}!spiel NAME${NC} - Setzt aktuelles Spiel"
    echo -e "${CYAN}!ort NAME${NC} - Setzt aktuellen Ort"
    echo -e "${CYAN}!tod${NC} - Erhöht Todeszähler"
    echo -e "${CYAN}!level X${NC} - Setzt Level"
    echo -e "${CYAN}!frag zephyr ...${NC} - Direkte Frage an den Bot"
    echo -e "${CYAN}!hilfe${NC} - Zeigt Hilfe an"
    
    echo -e "\n${BLUE}=== Überwachung ===${NC}"
    echo -e "Multi-Platform-Bot Logs: ${YELLOW}tail -f $LOG_FILE${NC}"
    echo -e "YouTube-Chat Logs: ${YELLOW}tail -f $YOUTUBE_LOG${NC}"
    echo -e "Screenshot-Watcher Logs: ${YELLOW}tail -f $WATCHER_LOG${NC}"
    echo -e "Bot manuell stoppen: ${YELLOW}kill $BOT_PID${NC}"
    echo -e "Alle Logs ansehen: ${YELLOW}tail -f $BASE_DIR/*.log${NC}"
    
else
    echo -e "${RED}FEHLER: Multi-Platform-Bot konnte nicht gestartet werden oder wurde sofort beendet${NC}"
    echo -e "Überprüfe die Logs für weitere Details: ${YELLOW}cat $LOG_FILE${NC}"
    exit 1
fi

# Erstellen eines systemd-Service (optional)
create_service_file() {
    if [ "$IS_SERVICE" = true ]; then
        return 0
    fi
    
    if [ -d "/etc/systemd/system" ]; then
        echo -e "\n${YELLOW}Möchtest du einen systemd-Service für den Multi-Platform-Bot erstellen? (j/n): ${NC}"
        read create_service
        
        if [ "$create_service" = "j" ] || [ "$create_service" = "J" ]; then
            SYSTEMD_SERVICE="/etc/systemd/system/zephyr-multi-bot.service"
            
            echo -e "${YELLOW}Erstelle systemd-Service-Datei...${NC}"
            
            cat > "$SYSTEMD_SERVICE" << EOLS
[Unit]
Description=Zephyr Multi-Platform Chatbot (Twitch + YouTube)
After=network.target ollama.service
Requires=ollama.service

[Service]
Type=simple
User=root
WorkingDirectory=$BASE_DIR
ExecStart=$BASE_DIR/start-multi-bot.sh --service
Restart=on-failure
RestartSec=10
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

[Install]
WantedBy=multi-user.target
EOLS
            
            systemctl daemon-reload
            
            echo -e "${GREEN}Service-Datei erstellt: $SYSTEMD_SERVICE${NC}"
            echo -e "Du kannst den Bot jetzt mit folgenden Befehlen steuern:"
            echo -e "${YELLOW}systemctl start zephyr-multi-bot${NC} - Bot starten"
            echo -e "${YELLOW}systemctl stop zephyr-multi-bot${NC} - Bot stoppen"
            echo -e "${YELLOW}systemctl enable zephyr-multi-bot${NC} - Bot beim Systemstart automatisch starten"
            echo -e "${YELLOW}systemctl status zephyr-multi-bot${NC} - Bot-Status anzeigen"
            
            echo -e "\nMöchtest du den Bot beim Systemstart automatisch starten? (j/n): "
            read enable_service
            
            if [ "$enable_service" = "j" ] || [ "$enable_service" = "J" ]; then
                systemctl enable zephyr-multi-bot
                echo -e "${GREEN}Bot wird jetzt beim Systemstart automatisch gestartet.${NC}"
            fi
        fi
    fi
}

# Frage, ob ein systemd-Service erstellt werden soll
create_service_file

# Im Service-Modus blockieren wir das Skript
if [ "$IS_SERVICE" = true ]; then
    echo -e "${BLUE}Laufe im Service-Modus. Prozess bleibt aktiv.${NC}"
    while ps -p $BOT_PID > /dev/null; do
        sleep 10
    done
    echo -e "${RED}Bot-Prozess wurde beendet, Service wird heruntergefahren.${NC}"
fi

exit 0
