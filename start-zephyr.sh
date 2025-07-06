#!/bin/bash

# Zephyr Multi-Platform Bot Starter v2.0
# Optimiert für systemd und manuellen Start

# Farben
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Konfiguration
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_SCRIPT="$BASE_DIR/zephyr_multi_bot.py"
PID_FILE="$BASE_DIR/zephyr_multi_bot.pid"
LOG_FILE="$BASE_DIR/logs/main.log"

echo -e "${BLUE}🤖 Zephyr Multi-Platform Bot v2.0${NC}"
echo -e "${BLUE}========================================${NC}"

# Funktion: Status prüfen
check_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Bot läuft (PID: $PID)${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠️  Verwaiste PID-Datei entfernt${NC}"
            rm "$PID_FILE"
        fi
    fi
    echo -e "${RED}❌ Bot läuft nicht${NC}"
    return 1
}

# Funktion: Bot stoppen
stop_bot() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo -e "${YELLOW}🛑 Stoppe Bot (PID: $PID)...${NC}"
            kill "$PID"
            
            # Warte auf sauberes Beenden
            for i in {1..10}; do
                if ! ps -p "$PID" > /dev/null 2>&1; then
                    echo -e "${GREEN}✅ Bot gestoppt${NC}"
                    rm -f "$PID_FILE"
                    return 0
                fi
                sleep 1
            done
            
            # Force kill
            echo -e "${YELLOW}⚠️  Erzwinge Beendigung...${NC}"
            kill -9 "$PID" 2>/dev/null
            rm -f "$PID_FILE"
        fi
    fi
    echo -e "${GREEN}✅ Bot gestoppt${NC}"
}

# Funktion: Abhängigkeiten prüfen
check_dependencies() {
    echo -e "${YELLOW}🔍 Prüfe Abhängigkeiten...${NC}"
    
    # Python 3
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 nicht gefunden${NC}"
        return 1
    fi
    
    # Python-Pakete
    python3 -c "import requests, dotenv, socket, threading, json" 2>/dev/null || {
        echo -e "${YELLOW}📦 Installiere Python-Pakete...${NC}"
        pip3 install requests python-dotenv
    }
    
    # Ollama-Server
    if ! curl -s --fail http://localhost:11434/api/version > /dev/null; then
        echo -e "${YELLOW}⚠️  Ollama-Server nicht erreichbar${NC}"
        echo -e "${YELLOW}💡 Starte Ollama mit: systemctl start ollama${NC}"
    else
        echo -e "${GREEN}✅ Ollama-Server erreichbar${NC}"
    fi
    
    # Verzeichnisse
    mkdir -p "$BASE_DIR/logs"
    mkdir -p "$BASE_DIR/screenshots"
    
    # .env-Datei
    if [ ! -f "$BASE_DIR/.env" ]; then
        echo -e "${YELLOW}⚠️  .env-Datei nicht gefunden${NC}"
        echo -e "${YELLOW}💡 Erstelle .env-Vorlage...${NC}"
        cat > "$BASE_DIR/.env" << 'EOF'
# Twitch-Konfiguration
ENABLE_TWITCH=true
BOT_USERNAME=dein_bot_name
OAUTH_TOKEN=oauth:dein_oauth_token
CHANNEL=#dein_kanal
BOT_NAME=zephyr

# YouTube-Konfiguration  
ENABLE_YOUTUBE=false
YOUTUBE_API_KEY=dein_youtube_api_key
YOUTUBE_CHANNEL_ID=deine_kanal_id
YOUTUBE_BOT_NAME=ZephyrBot

# Ollama-Konfiguration
OLLAMA_MODEL=zephyr
VISION_MODEL=llava

# Vision-Konfiguration
ENABLE_VISION=true
SCREENSHOT_ANALYSIS_INTERVAL=30

# Timing-Konfiguration
JOKE_INTERVAL=300
YOUTUBE_POLLING_INTERVAL=10
EOF
        echo -e "${GREEN}✅ .env-Vorlage erstellt${NC}"
        echo -e "${YELLOW}📝 Bitte .env-Datei mit deinen Daten füllen!${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ Abhängigkeiten OK${NC}"
    return 0
}

# Funktion: Bot starten
start_bot() {
    echo -e "${YELLOW}🚀 Starte Bot...${NC}"
    
    if ! check_dependencies; then
        echo -e "${RED}❌ Abhängigkeiten nicht erfüllt${NC}"
        return 1
    fi
    
    if [ ! -f "$MAIN_SCRIPT" ]; then
        echo -e "${RED}❌ Hauptskript nicht gefunden${NC}"
        return 1
    fi
    
    # Starte Bot
    cd "$BASE_DIR"
    nohup python3 "$MAIN_SCRIPT" > "$LOG_FILE" 2>&1 &
    
    # Warte und prüfe
    sleep 3
    if check_status > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Bot gestartet${NC}"
        echo -e "${BLUE}📋 Logs: tail -f $LOG_FILE${NC}"
        return 0
    else
        echo -e "${RED}❌ Bot konnte nicht gestartet werden${NC}"
        echo -e "${YELLOW}📋 Logs prüfen: cat $LOG_FILE${NC}"
        return 1
    fi
}

# Funktion: Service-Mode für systemd
service_mode() {
    echo -e "${BLUE}🔧 Service-Modus${NC}"
    
    if check_status > /dev/null 2>&1; then
        stop_bot
        sleep 2
    fi
    
    # Starte im Vordergrund für systemd
    cd "$BASE_DIR"
    exec python3 "$MAIN_SCRIPT"
}

# Hauptschalter
case "${1:-help}" in
    "start")
        if check_status > /dev/null 2>&1; then
            echo -e "${YELLOW}⚠️  Bot läuft bereits${NC}"
        else
            start_bot
        fi
        ;;
    "stop")
        stop_bot
        ;;
    "restart")
        echo -e "${YELLOW}🔄 Neustart...${NC}"
        stop_bot
        sleep 2
        start_bot
        ;;
    "status")
        check_status
        ;;
    "logs")
        if [ -f "$LOG_FILE" ]; then
            echo -e "${BLUE}📋 Live-Logs:${NC}"
            tail -f "$LOG_FILE"
        else
            echo -e "${RED}❌ Keine Logs gefunden${NC}"
        fi
        ;;
    "--service"|"service")
        service_mode
        ;;
    *)
        echo -e "${BLUE}Verwendung: $0 {start|stop|restart|status|logs}${NC}"
        echo -e ""
        echo -e "${YELLOW}Befehle:${NC}"
        echo -e "  start   - Bot starten"
        echo -e "  stop    - Bot stoppen"
        echo -e "  restart - Bot neu starten"
        echo -e "  status  - Status prüfen"
        echo -e "  logs    - Live-Logs anzeigen"
        ;;
esac
