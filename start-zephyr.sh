#!/bin/bash

# Zephyr Multi-Platform Bot Starter v2.0
# Startet Twitch + YouTube Bot mit Bildanalyse

# Farben
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Konfiguration
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_SCRIPT="$BASE_DIR/zephyr_multi_bot.py"
PID_FILE="$BASE_DIR/zephyr_multi_bot.pid"
LOG_FILE="$BASE_DIR/zephyr_multi_bot.log"

echo -e "${BLUE}🤖 Zephyr Multi-Platform Bot v2.0${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${PURPLE}🎮 Twitch + 🎥 YouTube + 👁️ Vision AI${NC}"
echo -e "${BLUE}========================================${NC}"

# Funktion: Status prüfen
check_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Bot läuft bereits (PID: $PID)${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠️  Verwaiste PID-Datei gefunden, entfernt${NC}"
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
                    echo -e "${GREEN}✅ Bot erfolgreich gestoppt${NC}"
                    rm -f "$PID_FILE"
                    return 0
                fi
                sleep 1
            done
            
            # Force kill falls nötig
            echo -e "${YELLOW}⚠️  Erzwinge Beendigung...${NC}"
            kill -9 "$PID" 2>/dev/null
            rm -f "$PID_FILE"
            echo -e "${GREEN}✅ Bot gestoppt${NC}"
        else
            echo -e "${YELLOW}⚠️  PID-Datei existiert, aber Prozess läuft nicht${NC}"
            rm -f "$PID_FILE"
        fi
    else
        echo -e "${RED}❌ Bot läuft nicht${NC}"
    fi
}

# Funktion: Abhängigkeiten prüfen
check_dependencies() {
    echo -e "${YELLOW}🔍 Prüfe Abhängigkeiten...${NC}"
    
    # Python 3
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 nicht gefunden${NC}"
        return 1
    fi
    
    # Ollama Server
    if ! curl -s --fail http://localhost:11434/api/version > /dev/null; then
        echo -e "${RED}❌ Ollama-Server nicht erreichbar${NC}"
        echo -e "${YELLOW}💡 Starte Ollama mit: ollama serve${NC}"
        return 1
    fi
    
    # Python-Pakete
    python3 -c "import requests, dotenv" 2>/dev/null || {
        echo -e "${YELLOW}📦 Installiere Python-Pakete...${NC}"
        pip3 install requests python-dotenv
    }
    
    # .env-Datei
    if [ ! -f "$BASE_DIR/.env" ]; then
        echo -e "${YELLOW}⚠️  Keine .env-Datei gefunden${NC}"
        echo -e "${YELLOW}💡 Erstelle .env aus .env.backup...${NC}"
        
        if [ -f "$BASE_DIR/.env.backup" ]; then
            cp "$BASE_DIR/.env.backup" "$BASE_DIR/.env"
            echo -e "${GREEN}✅ .env-Datei erstellt${NC}"
            echo -e "${YELLOW}📝 Bitte .env-Datei bearbeiten und API-Keys hinzufügen${NC}"
        else
            echo -e "${RED}❌ Keine .env.backup gefunden${NC}"
            return 1
        fi
    fi
    
    # Screenshots-Verzeichnis
    mkdir -p "$BASE_DIR/screenshots"
    
    echo -e "${GREEN}✅ Abhängigkeiten OK${NC}"
    return 0
}

# Funktion: Bot starten
start_bot() {
    echo -e "${YELLOW}🚀 Starte Zephyr Multi-Platform Bot...${NC}"
    
    # Prüfe Abhängigkeiten
    if ! check_dependencies; then
        echo -e "${RED}❌ Abhängigkeiten fehlen${NC}"
        return 1
    fi
    
    # Prüfe Hauptskript
    if [ ! -f "$MAIN_SCRIPT" ]; then
        echo -e "${RED}❌ Hauptskript nicht gefunden: $MAIN_SCRIPT${NC}"
        return 1
    fi
    
    # Starte Bot
    cd "$BASE_DIR"
    nohup python3 "$MAIN_SCRIPT" > "$LOG_FILE" 2>&1 &
    BOT_PID=$!
    
    # Warte kurz und prüfe Status
    sleep 3
    if ps -p $BOT_PID > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Bot erfolgreich gestartet (PID: $BOT_PID)${NC}"
        echo -e "${BLUE}📊 Logs: tail -f $LOG_FILE${NC}"
        echo -e "${BLUE}🛑 Stoppen: $0 stop${NC}"
        return 0
    else
        echo -e "${RED}❌ Bot konnte nicht gestartet werden${NC}"
        echo -e "${YELLOW}📋 Logs prüfen: cat $LOG_FILE${NC}"
        return 1
    fi
}

# Funktion: Logs anzeigen
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo -e "${BLUE}📋 Aktuelle Logs (Ctrl+C zum Beenden):${NC}"
        tail -f "$LOG_FILE"
    else
        echo -e "${RED}❌ Keine Logs gefunden${NC}"
    fi
}

# Funktion: Quick-Setup
quick_setup() {
    echo -e "${BLUE}⚡ Quick Setup für Zephyr Bot${NC}"
    echo -e "${YELLOW}===============================${NC}"
    
    # Prüfe .env
    if [ ! -f "$BASE_DIR/.env" ]; then
        if [ -f "$BASE_DIR/.env.backup" ]; then
            cp "$BASE_DIR/.env.backup" "$BASE_DIR/.env"
            echo -e "${GREEN}✅ .env-Datei aus Backup erstellt${NC}"
        else
            echo -e "${RED}❌ Keine .env.backup gefunden${NC}"
            return 1
        fi
    fi
    
    echo -e "${YELLOW}📝 Bitte folgende Werte in .env konfigurieren:${NC}"
    echo -e "${BLUE}Twitch:${NC}"
    echo -e "  BOT_USERNAME=dein_bot_name"
    echo -e "  OAUTH_TOKEN=oauth:dein_token"
    echo -e "  CHANNEL=#dein_kanal"
    echo -e ""
    echo -e "${BLUE}YouTube:${NC}"
    echo -e "  YOUTUBE_API_KEY=dein_api_key"
    echo -e "  YOUTUBE_CHANNEL_ID=deine_kanal_id"
    echo -e "  YOUTUBE_BOT_NAME=ZephyroBot"
    echo -e ""
    echo -e "${YELLOW}💡 Nach Konfiguration: $0 start${NC}"
}

# Funktion: Service-Mode (für systemd)
run_service_mode() {
    echo -e "${BLUE}🔧 Service-Modus aktiviert${NC}"
    
    # Stoppe existierenden Bot falls läuft
    if check_status > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Stoppe existierenden Bot...${NC}"
        stop_bot > /dev/null 2>&1
        sleep 2
    fi
    
    # Starte Bot
    echo -e "${YELLOW}🚀 Starte Bot im Service-Modus...${NC}"
    
    # Prüfe Abhängigkeiten
    if ! check_dependencies; then
        echo -e "${RED}❌ Abhängigkeiten fehlen${NC}"
        exit 1
    fi
    
    # Prüfe Hauptskript
    if [ ! -f "$MAIN_SCRIPT" ]; then
        echo -e "${RED}❌ Hauptskript nicht gefunden: $MAIN_SCRIPT${NC}"
        exit 1
    fi
    
    # Starte Bot im Vordergrund für systemd
    cd "$BASE_DIR"
    echo -e "${GREEN}✅ Starte Python-Skript im Service-Modus...${NC}"
    exec python3 "$MAIN_SCRIPT"
}

# Hauptmenü
case "${1:-help}" in
    "start")
        if check_status; then
            echo -e "${YELLOW}⚠️  Bot läuft bereits${NC}"
            exit 1
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
        show_logs
        ;;
    "setup")
        quick_setup
        ;;
    "--service"|"service")
        run_service_mode
        ;;
    "help"|*)
        echo -e "${BLUE}Verwendung: $0 {start|stop|restart|status|logs|setup}${NC}"
        echo -e ""
        echo -e "${YELLOW}Befehle:${NC}"
        echo -e "  start   - Bot starten"
        echo -e "  stop    - Bot stoppen"
        echo -e "  restart - Bot neu starten"
        echo -e "  status  - Status prüfen"
        echo -e "  logs    - Live-Logs anzeigen"
        echo -e "  setup   - Quick-Setup"
        echo -e ""
        echo -e "${BLUE}Beispiel:${NC}"
        echo -e "  $0 setup   # Erste Konfiguration"
        echo -e "  $0 start   # Bot starten"
        echo -e "  $0 logs    # Logs verfolgen"
        ;;
esac
