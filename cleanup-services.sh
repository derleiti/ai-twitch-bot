#!/bin/bash

# Farben für die Ausgabe
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Bereinige und konfiguriere Dienste ===${NC}"

# Stoppe alle relevanten Dienste
echo -e "${YELLOW}Stoppe alle relevanten Dienste...${NC}"
services=("twitch-ollama-bot" "zephyr" "ollama")
for service in "${services[@]}"; do
    if systemctl list-unit-files | grep -q $service; then
        echo -e "  Stoppe $service..."
        systemctl stop $service
    fi
done

# Deaktiviere nicht benötigte Dienste
echo -e "\n${YELLOW}Deaktiviere nicht benötigte Dienste...${NC}"
if systemctl list-unit-files | grep -q zephyr.service; then
    echo -e "  Deaktiviere zephyr.service..."
    systemctl disable zephyr.service
    # Optionale Entfernung der Dienstdatei
    read -p "  Soll die zephyr.service-Datei entfernt werden? (j/n): " remove_zephyr
    if [ "$remove_zephyr" = "j" ] || [ "$remove_zephyr" = "J" ]; then
        rm -f /etc/systemd/system/zephyr.service
        echo -e "  ${GREEN}zephyr.service entfernt.${NC}"
    fi
fi

# Prüfe, ob es mehrere Ollama-Dienste gibt
echo -e "\n${YELLOW}Prüfe auf mehrere Ollama-Dienste...${NC}"
ollama_services=$(systemctl list-unit-files | grep -E "ollama.*\.service" | wc -l)
if [ $ollama_services -gt 1 ]; then
    echo -e "  ${RED}Mehrere Ollama-Dienste gefunden!${NC}"
    systemctl list-unit-files | grep -E "ollama.*\.service"
    
    echo -e "  ${YELLOW}Deaktiviere alle Ollama-Dienste außer dem Hauptdienst...${NC}"
    for service in $(systemctl list-unit-files | grep -E "ollama.*\.service" | awk '{print $1}' | grep -v "^ollama.service$"); do
        echo -e "  Deaktiviere $service..."
        systemctl disable $service
        read -p "  Soll die $service-Datei entfernt werden? (j/n): " remove_service
        if [ "$remove_service" = "j" ] || [ "$remove_service" = "J" ]; then
            rm -f /etc/systemd/system/$service
            echo -e "  ${GREEN}$service entfernt.${NC}"
        fi
    done
fi

# Lade systemd neu
echo -e "\n${YELLOW}Lade systemd-Konfiguration neu...${NC}"
systemctl daemon-reload

# Konfiguriere den korrekten Ollama-Dienst
echo -e "\n${YELLOW}Konfiguriere den Ollama-Dienst...${NC}"
if [ ! -f "/etc/systemd/system/ollama.service" ] || ! grep -q "Description=Ollama Server" "/etc/systemd/system/ollama.service"; then
    echo -e "  Erstelle ollama.service..."
    cat > "/etc/systemd/system/ollama.service" << 'EOL'
[Unit]
Description=Ollama Server
After=network-online.target
Wants=network-online.target

[Service]
User=root
ExecStart=/usr/local/bin/ollama serve
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOL
    systemctl daemon-reload
    echo -e "  ${GREEN}ollama.service erstellt.${NC}"
fi

# Konfiguriere den Bot-Dienst
echo -e "\n${YELLOW}Konfiguriere den Bot-Dienst...${NC}"
if [ ! -f "/etc/systemd/system/twitch-ollama-bot.service" ]; then
    echo -e "  Erstelle twitch-ollama-bot.service..."
    cat > "/etc/systemd/system/twitch-ollama-bot.service" << EOL
[Unit]
Description=Twitch Ollama Chatbot
After=network.target ollama.service
Requires=ollama.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/zephyr
ExecStart=/root/zephyr/start-bot.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOL
    systemctl daemon-reload
    echo -e "  ${GREEN}twitch-ollama-bot.service erstellt.${NC}"
fi

# Aktiviere und starte die korrekten Dienste
echo -e "\n${YELLOW}Aktiviere die korrekten Dienste...${NC}"
echo -e "  Aktiviere ollama.service..."
systemctl enable ollama.service
echo -e "  Aktiviere twitch-ollama-bot.service..."
systemctl enable twitch-ollama-bot.service

echo -e "\n${YELLOW}Starte die Dienste...${NC}"
echo -e "  Starte ollama.service..."
systemctl start ollama.service
echo -e "  Warte 5 Sekunden, bis Ollama bereit ist..."
sleep 5
echo -e "  Starte twitch-ollama-bot.service..."
systemctl start twitch-ollama-bot.service

# Aktualisiere die Bot-Konfiguration für die deutsche Sprache
echo -e "\n${YELLOW}Aktualisiere Bot-Konfiguration für deutsche Sprache...${NC}"
if [ -f "/root/zephyr/twitch-ollama-bot.py" ]; then
    cp /root/zephyr/twitch-ollama-bot.py /root/zephyr/twitch-ollama-bot.py.bak_cleanup
    
    # Suche nach der get_response_from_ollama-Funktion und füge den System-Prompt hinzu
    if grep -q "messages.*role.*user.*content" /root/zephyr/twitch-ollama-bot.py; then
        if ! grep -q "Du bist ein hilfreicher Twitch-Bot" /root/zephyr/twitch-ollama-bot.py; then
            sed -i '/def get_response_from_ollama/,/return None/{
                s/"messages": \[{"role": "user", "content": prompt}\],/"messages": \[{"role": "system", "content": "Du bist ein hilfreicher Twitch-Bot namens zephyr. Antworte immer auf Deutsch, kurz und prägnant."}, {"role": "user", "content": prompt}\],/g
            }' /root/zephyr/twitch-ollama-bot.py
            
            if grep -q "Du bist ein hilfreicher Twitch-Bot" /root/zephyr/twitch-ollama-bot.py; then
                echo -e "  ${GREEN}System-Prompt für deutsche Sprache hinzugefügt.${NC}"
                echo -e "  ${YELLOW}Starte den Bot neu...${NC}"
                systemctl restart twitch-ollama-bot.service
            else
                echo -e "  ${RED}Fehler beim Hinzufügen des System-Prompts.${NC}"
                echo -e "  ${YELLOW}Manuelle Bearbeitung erforderlich.${NC}"
            fi
        else
            echo -e "  ${GREEN}System-Prompt für deutsche Sprache ist bereits vorhanden.${NC}"
        fi
    else
        echo -e "  ${RED}Die get_response_from_ollama-Funktion hat nicht das erwartete Format.${NC}"
        echo -e "  ${YELLOW}Manuelle Bearbeitung erforderlich.${NC}"
    fi
fi

# Zeige Status der Dienste
echo -e "\n${BLUE}=== Status der Dienste ===${NC}"
echo -e "${YELLOW}Ollama:${NC}"
systemctl status ollama.service --no-pager | head -n 5
echo -e "\n${YELLOW}Twitch-Ollama-Bot:${NC}"
systemctl status twitch-ollama-bot.service --no-pager | head -n 5

echo -e "\n${GREEN}Dienste wurden bereinigt und konfiguriert.${NC}"
echo -e "${BLUE}Sollten noch Probleme auftreten, kann ein Systemneustart helfen:${NC} sudo reboot"
