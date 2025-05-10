#!/bin/bash

# Farben für die Ausgabe
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Ollama-API Fix-Script ===${NC}"

# Überprüfe, ob Ollama läuft
echo -e "${YELLOW}Prüfe Ollama-Status...${NC}"
if systemctl is-active --quiet ollama; then
    echo -e "${GREEN}Ollama-Service läuft.${NC}"
else
    echo -e "${RED}Ollama-Service ist nicht aktiv.${NC}"
    echo -e "${YELLOW}Starte Ollama...${NC}"
    systemctl start ollama
    sleep 3
    if systemctl is-active --quiet ollama; then
        echo -e "${GREEN}Ollama-Service wurde erfolgreich gestartet.${NC}"
    else
        echo -e "${RED}Ollama-Service konnte nicht gestartet werden.${NC}"
        exit 1
    fi
fi

# Teste Ollama-Version
echo -e "${YELLOW}Teste Ollama-API Version...${NC}"
VERSION_RESPONSE=$(curl -s http://localhost:11434/api/version)
if [ $? -eq 0 ] && [ ! -z "$VERSION_RESPONSE" ]; then
    echo -e "${GREEN}Ollama-API ist erreichbar: $VERSION_RESPONSE${NC}"
else
    echo -e "${RED}Kann keine Verbindung zur Ollama-API herstellen.${NC}"
    exit 1
fi

# Prüfe, ob das Zephyr-Modell installiert ist
echo -e "${YELLOW}Prüfe verfügbare Modelle...${NC}"
MODELS_RESPONSE=$(curl -s http://localhost:11434/api/tags)
if [[ $MODELS_RESPONSE == *"zephyr"* ]]; then
    echo -e "${GREEN}Zephyr-Modell ist installiert.${NC}"
else
    echo -e "${YELLOW}Zephyr-Modell ist nicht installiert oder nicht erkennbar. Installiere Modell...${NC}"
    ollama pull zephyr
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Zephyr-Modell wurde erfolgreich installiert.${NC}"
    else
        echo -e "${RED}Fehler beim Installieren des Zephyr-Modells.${NC}"
        exit 1
    fi
fi

# Teste die generate-API mit dem Zephyr-Modell
echo -e "${YELLOW}Teste generate-API mit Zephyr-Modell...${NC}"
GENERATE_TEST=$(curl -s -X POST http://localhost:11434/api/generate -d '{
  "model": "zephyr",
  "prompt": "Sage Hallo",
  "stream": false
}')

if [ $? -eq 0 ] && [ ! -z "$GENERATE_TEST" ]; then
    echo -e "${GREEN}generate-API funktioniert: ${GENERATE_TEST:0:50}...${NC}"
else
    echo -e "${RED}generate-API funktioniert nicht.${NC}"
    
    # Teste alternativ die chat-API
    echo -e "${YELLOW}Teste chat-API als Alternative...${NC}"
    CHAT_TEST=$(curl -s -X POST http://localhost:11434/api/chat -d '{
      "model": "zephyr",
      "messages": [{"role": "user", "content": "Sage Hallo"}],
      "stream": false
    }')
    
    if [ $? -eq 0 ] && [ ! -z "$CHAT_TEST" ]; then
        echo -e "${GREEN}chat-API funktioniert: ${CHAT_TEST:0:50}...${NC}"
        echo -e "${YELLOW}Aktualisiere .env-Datei, um chat-API zu verwenden...${NC}"
        
        # Aktualisiere die .env-Datei
        if [ -f "/root/zephyr/.env" ]; then
            # Sichere die alte .env-Datei
            cp "/root/zephyr/.env" "/root/zephyr/.env.bak"
            # Ersetze den API-Endpunkt
            sed -i 's|OLLAMA_URL=http://localhost:11434/api/generate|OLLAMA_URL=http://localhost:11434/api/chat|g' "/root/zephyr/.env"
            echo -e "${GREEN}.env-Datei wurde aktualisiert.${NC}"
            
            # Aktualisiere auch den Bot-Code
            echo -e "${YELLOW}Aktualisiere Bot-Code für chat-API...${NC}"
            if [ -f "/root/zephyr/twitch-ollama-bot.py" ]; then
                # Sichere das alte Bot-Skript
                cp "/root/zephyr/twitch-ollama-bot.py" "/root/zephyr/twitch-ollama-bot.py.bak"
                
                # Aktualisiere den Code für die chat-API
                sed -i '/def get_response_from_ollama/,/return None/{s/response = requests.post(/response = requests.post(/; s/"model": MODEL,/"model": MODEL, "messages": \[{"role": "user", "content": prompt}\],/; s/"prompt": prompt,//}' "/root/zephyr/twitch-ollama-bot.py"
                
                sed -i 's/text = result.get("response", "").strip()/text = result.get("message", {}).get("content", "").strip()/g' "/root/zephyr/twitch-ollama-bot.py"
                
                echo -e "${GREEN}Bot-Code wurde aktualisiert.${NC}"
            else
                echo -e "${RED}Bot-Skript nicht gefunden.${NC}"
            fi
        else
            echo -e "${RED}.env-Datei nicht gefunden.${NC}"
        fi
    else
        echo -e "${RED}Auch die chat-API funktioniert nicht. Ollama scheint nicht korrekt konfiguriert zu sein.${NC}"
        echo -e "${YELLOW}Versuche, Ollama komplett neu zu installieren...${NC}"
        
        # Empfehlung für eine Neuinstallation
        echo -e "\n${YELLOW}Empfehlung: Installiere Ollama neu mit folgenden Befehlen:${NC}"
        echo -e "systemctl stop ollama"
        echo -e "rm -rf /root/.ollama"  # Vorsicht: Löscht alle Modelle!
        echo -e "apt purge -y ollama"
        echo -e "apt autoremove -y"
        echo -e "curl -fsSL https://ollama.com/install.sh | sh"
        echo -e "systemctl start ollama"
        echo -e "ollama pull zephyr"
    fi
fi

echo -e "\n${BLUE}=== Test abgeschlossen ===${NC}"
echo -e "Falls der Bot weiterhin Probleme hat, starte ihn neu mit: ${YELLOW}systemctl restart twitch-ollama-bot${NC}"
