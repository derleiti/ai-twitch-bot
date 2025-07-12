#!/bin/bash

# Screenshot Sync Script – nur eine Datei, ressourcenschonend für X11 & Wayland

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER="root@ailinux.me"
REMOTE_PATH="/root/zephyr/screenshots"
LOCAL_FILE="$SCRIPT_DIR/current_screenshot.jpg"
REMOTE_FILE="$REMOTE_PATH/current_screenshot.jpg"

RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'

echo -e "${BLUE}=== Screenshot Sync gestartet (Wayland/X11 Auto, Hauptmonitor) ===${NC}"
echo "Datei: $LOCAL_FILE"
echo "Server: $REMOTE_FILE"
echo

# Alte Screenshots löschen
echo "Bereinige alte Screenshots…"
rm -f "$SCRIPT_DIR"/current_screenshot.*

# Funktion zur Tool-Installation
install_tool() {
    TOOL=$1
    if ! command -v "$TOOL" &> /dev/null; then
        echo -e "${BLUE}→ Installiere fehlendes Tool: $TOOL${NC}"
        sudo apt update && sudo apt install -y "$TOOL"
    fi
}

# Screenshot-Tool erkennen
SCREENSHOT_CMD=""
if [ "$XDG_SESSION_TYPE" == "wayland" ]; then
    install_tool grim
    if command -v grim &> /dev/null && \
       ! grim "$SCRIPT_DIR/test_grim.png" 2>&1 | grep -q "doesn't support wlr-screencopy"; then
        rm -f "$SCRIPT_DIR/test_grim.png"
        SCREENSHOT_CMD="grim"
        echo -e "${GREEN}→ Wayland erkannt, verwende grim${NC}"
    else
        rm -f "$SCRIPT_DIR/test_grim.png"
        echo -e "${RED}→ grim nicht kompatibel oder fehlend${NC}"
    fi

    if [ -z "$SCREENSHOT_CMD" ]; then
        install_tool spectacle
        if command -v spectacle &> /dev/null; then
            SCREENSHOT_CMD="spectacle"
            echo -e "${GREEN}→ Fallback auf spectacle CLI (KDE/Wayland)${NC}"
        fi
    fi

    if [ -z "$SCREENSHOT_CMD" ]; then
        echo -e "${RED}❌ Kein Screenshot-Tool für Wayland gefunden!${NC}"
        exit 1
    fi

else
    # X11
    install_tool maim
    if command -v maim &> /dev/null; then
        SCREENSHOT_CMD="maim"
        echo -e "${GREEN}→ X11 erkannt, verwende maim${NC}"
    fi

    if [ -z "$SCREENSHOT_CMD" ]; then
        install_tool scrot
        if command -v scrot &> /dev/null; then
            SCREENSHOT_CMD="scrot"
            echo -e "${GREEN}→ Fallback auf scrot unter X11${NC}"
        fi
    fi

    if [ -z "$SCREENSHOT_CMD" ]; then
        echo -e "${RED}❌ Kein Screenshot-Tool für X11 gefunden!${NC}"
        exit 1
    fi
fi

# Remote-Verzeichnis anlegen
echo "Prüfe SSH-Verbindung…"
ssh -o ConnectTimeout=5 $SERVER "mkdir -p $REMOTE_PATH" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${RED}SSH-Verbindung fehlgeschlagen.${NC}"
    exit 1
fi
echo -e "${GREEN}Verbindung OK${NC}"
echo

# Screenshot-Loop
counter=1
while true; do
    echo -e "${BLUE}[$(date '+%H:%M:%S')] Screenshot #$counter${NC}"

    case "$SCREENSHOT_CMD" in
        grim)
            OUTPUT=$(grim -l | grep primary | awk '{print $1}')
            grim -o "$OUTPUT" "$LOCAL_FILE" ;;
        maim)
            GEOM=$(xrandr | awk '/ primary/{print $4}')
            maim -g "$GEOM" "$LOCAL_FILE" ;;
        scrot)
            scrot -o "$LOCAL_FILE" ;;
        spectacle)
            spectacle -b -n -o "$LOCAL_FILE" ;;
    esac

    if [ -f "$LOCAL_FILE" ]; then
        size=$(du -h "$LOCAL_FILE" | cut -f1)
        echo "  📸 Screenshot erstellt ($size)"
        if scp "$LOCAL_FILE" "$SERVER:$REMOTE_FILE" 2>/dev/null; then
            echo -e "  ✅ ${GREEN}Erfolgreich übertragen${NC}"
        else
            echo -e "  ❌ ${RED}Upload fehlgeschlagen${NC}"
        fi
    else
        echo -e "  ❌ ${RED}Screenshot fehlgeschlagen${NC}"
    fi

    echo
    ((counter++))
    sleep 5
done
