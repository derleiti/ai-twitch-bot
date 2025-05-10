#!/bin/bash

# Farben für die Ausgabe
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Diagnose von Ollama- und Zephyr-Diensten ===${NC}"

# Überprüfe systemd-Dienste
echo -e "${YELLOW}Überprüfe systemd-Dienste:${NC}"
echo -e "1. Ollama-Dienst:"
if systemctl list-unit-files | grep -q ollama; then
    echo -e "   ${GREEN}Ollama-Dienst ist installiert${NC}"
    systemctl status ollama --no-pager | head -n 10
else
    echo -e "   ${RED}Ollama-Dienst ist nicht installiert${NC}"
fi

echo -e "\n2. Zephyr-Dienst:"
if systemctl list-unit-files | grep -q zephyr; then
    echo -e "   ${GREEN}Zephyr-Dienst ist installiert${NC}"
    systemctl status zephyr --no-pager | head -n 10
else
    echo -e "   ${RED}Kein dedizierter Zephyr-Dienst gefunden${NC}"
fi

echo -e "\n3. Twitch-Ollama-Bot-Dienst:"
if systemctl list-unit-files | grep -q twitch-ollama-bot; then
    echo -e "   ${GREEN}Twitch-Ollama-Bot-Dienst ist installiert${NC}"
    systemctl status twitch-ollama-bot --no-pager | head -n 10
else
    echo -e "   ${RED}Twitch-Ollama-Bot-Dienst ist nicht installiert${NC}"
fi

# Überprüfe Startskripte
echo -e "\n${YELLOW}Überprüfe Startskripte:${NC}"
echo -e "1. Ollama Startskript:"
OLLAMA_INIT=$(find /etc/init.d -name "*ollama*" 2>/dev/null)
if [ -n "$OLLAMA_INIT" ]; then
    echo -e "   ${GREEN}Ollama-Startskript gefunden: $OLLAMA_INIT${NC}"
    ls -la $OLLAMA_INIT
else
    echo -e "   ${RED}Kein Ollama-Startskript in /etc/init.d gefunden${NC}"
fi

echo -e "\n2. Zephyr Startskript:"
if [ -f "/root/zephyr/zephyr-start.sh" ]; then
    echo -e "   ${GREEN}Zephyr-Startskript gefunden: /root/zephyr/zephyr-start.sh${NC}"
    ls -la /root/zephyr/zephyr-start.sh
else
    echo -e "   ${RED}Zephyr-Startskript nicht gefunden${NC}"
fi

echo -e "\n3. Twitch-Ollama-Bot Startskript:"
if [ -f "/root/zephyr/start-bot.sh" ]; then
    echo -e "   ${GREEN}Twitch-Ollama-Bot-Startskript gefunden: /root/zephyr/start-bot.sh${NC}"
    ls -la /root/zephyr/start-bot.sh
else
    echo -e "   ${RED}Twitch-Ollama-Bot-Startskript nicht gefunden${NC}"
fi

# Überprüfe laufende Prozesse
echo -e "\n${YELLOW}Überprüfe laufende Prozesse:${NC}"
echo -e "1. Ollama-Prozesse:"
if pgrep -f ollama > /dev/null; then
    echo -e "   ${GREEN}Ollama läuft:${NC}"
    ps aux | grep ollama | grep -v grep
else
    echo -e "   ${RED}Kein Ollama-Prozess gefunden${NC}"
fi

echo -e "\n2. Zephyr/Bot-Prozesse:"
if pgrep -f "python.*twitch-ollama-bot.py\|python.*zephyr" > /dev/null; then
    echo -e "   ${GREEN}Zephyr/Bot-Prozesse gefunden:${NC}"
    ps aux | grep -E "python.*twitch-ollama-bot.py|python.*zephyr" | grep -v grep
else
    echo -e "   ${RED}Keine Zephyr/Bot-Prozesse gefunden${NC}"
fi

# Zusammenfassung und Empfehlungen
echo -e "\n${BLUE}=== Zusammenfassung und Empfehlungen ===${NC}"

if systemctl list-unit-files | grep -q ollama && systemctl list-unit-files | grep -q twitch-ollama-bot && ! systemctl list-unit-files | grep -q zephyr; then
    echo -e "${GREEN}Empfohlene Konfiguration gefunden:${NC} Ollama und Twitch-Ollama-Bot als systemd-Dienste ohne separaten Zephyr-Dienst."
    echo -e "Dies ist die beste Konfiguration. Keine Änderungen notwendig."
elif systemctl list-unit-files | grep -q zephyr; then
    echo -e "${YELLOW}Möglicher Konflikt:${NC} Es wurde ein separater Zephyr-Dienst gefunden, der mit dem Twitch-Ollama-Bot-Dienst in Konflikt stehen könnte."
    echo -e "Empfehlung: Deaktiviere den Zephyr-Dienst und verwende nur den Twitch-Ollama-Bot-Dienst."
    echo -e "  1. ${YELLOW}systemctl stop zephyr${NC}"
    echo -e "  2. ${YELLOW}systemctl disable zephyr${NC}"
    echo -e "  3. ${YELLOW}systemctl start twitch-ollama-bot${NC}"
else
    echo -e "${YELLOW}Unvollständige Konfiguration:${NC} Es fehlen möglicherweise wichtige Dienste."
    
    if ! systemctl list-unit-files | grep -q ollama; then
        echo -e "Ollama-Dienst fehlt. Installiere Ollama mit:"
        echo -e "  ${YELLOW}curl -fsSL https://ollama.com/install.sh | sh${NC}"
    fi
    
    if ! systemctl list-unit-files | grep -q twitch-ollama-bot; then
        echo -e "Twitch-Ollama-Bot-Dienst fehlt. Erstelle ihn mit dem start-bot.sh-Skript:"
        echo -e "  ${YELLOW}cd /root/zephyr && ./start-bot.sh${NC}"
        echo -e "  Wähle 'j' bei der Frage nach dem systemd-Service."
    fi
fi

echo -e "\n${BLUE}=== Diagnose abgeschlossen ===${NC}"
