#!/usr/bin/env python3
# zephyr-monitor.py - Ein Überwachungstool für den Zephyr-Bot

import os
import sys
import json
import time
import argparse
import subprocess
from datetime import datetime, timedelta
from collections import Counter

# Farbcodes für die Ausgabe
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Pfade
BASE_DIR = "/home/zombie/zephyr"
LOG_FILE = os.path.join(BASE_DIR, "zephyr-bot.log")
PID_FILE = os.path.join(BASE_DIR, "zephyr-bot.pid")
TRAINING_DIR = os.path.join(BASE_DIR, "training_data")
CHAT_HISTORY_FILE = os.path.join(TRAINING_DIR, "chat_history.jsonl")
VIEWER_STATS_FILE = os.path.join(TRAINING_DIR, "viewer_stats.json")
INTERACTION_STATS_FILE = os.path.join(TRAINING_DIR, "interaction_stats.json")
PERSONALITY_FILE = os.path.join(TRAINING_DIR, "personality.json")

def clear_screen():
    """Löscht den Bildschirm."""
    os.system('cls' if os.name == 'nt' else 'clear')

def check_bot_status():
    """Prüft, ob der Bot läuft und gibt den Status zurück."""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            
            # Prüfe, ob der Prozess läuft
            try:
                os.kill(pid, 0)  # Sende Signal 0 (keine Aktion), nur um zu prüfen, ob der Prozess existiert
                return True, pid
            except OSError:  # Prozess existiert nicht
                return False, pid
        except:
            return False, None
    else:
        return False, None

def get_log_tail(lines=10):
    """Gibt die letzten n Zeilen des Logs zurück."""
    if not os.path.exists(LOG_FILE):
        return ["Log-Datei nicht gefunden"]
    
    try:
        result = subprocess.run(['tail', '-n', str(lines), LOG_FILE], 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE,
                              text=True)
        return result.stdout.splitlines()
    except:
        return ["Fehler beim Lesen der Log-Datei"]

def load_stats():
    """Lädt alle verfügbaren Statistiken."""
    stats = {}
    
    # Lade Viewer-Statistiken
    if os.path.exists(VIEWER_STATS_FILE):
        try:
            with open(VIEWER_STATS_FILE, 'r', encoding='utf-8') as f:
                stats['viewers'] = json.load(f)
        except:
            stats['viewers'] = {"Fehler": "Konnte Viewer-Statistiken nicht laden"}
    else:
        stats['viewers'] = {"Info": "Keine Viewer-Statistiken verfügbar"}
    
    # Lade Interaktions-Statistiken
    if os.path.exists(INTERACTION_STATS_FILE):
        try:
            with open(INTERACTION_STATS_FILE, 'r', encoding='utf-8') as f:
                stats['interactions'] = json.load(f)
        except:
            stats['interactions'] = {"Fehler": "Konnte Interaktions-Statistiken nicht laden"}
    else:
        stats['interactions'] = {"Info": "Keine Interaktions-Statistiken verfügbar"}
    
    # Lade Persönlichkeitsprofil
    if os.path.exists(PERSONALITY_FILE):
        try:
            with open(PERSONALITY_FILE, 'r', encoding='utf-8') as f:
                stats['personality'] = json.load(f)
        except:
            stats['personality'] = {"Fehler": "Konnte Persönlichkeitsprofil nicht laden"}
    else:
        stats['personality'] = {"Info": "Kein Persönlichkeitsprofil verfügbar"}
    
    # Zähle Chat-History-Einträge
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                stats['chat_history_count'] = len(lines)
                
                # Analysiere die letzten 100 Nachrichten
                recent_messages = lines[-100:] if len(lines) > 100 else lines
                users = []
                commands = []
                for line in recent_messages:
                    try:
                        msg = json.loads(line)
                        users.append(msg.get('user', 'unknown'))
                        if msg.get('is_command', False) and 'content' in msg:
                            cmd = msg['content'].split()[0].lower() if ' ' in msg['content'] else msg['content'].lower()
                            commands.append(cmd)
                    except:
                        continue
                
                stats['recent_users'] = dict(Counter(users).most_common(5))
                stats['recent_commands'] = dict(Counter(commands).most_common(5))
        except:
            stats['chat_history_count'] = "Fehler beim Zählen der Chat-History"
    else:
        stats['chat_history_count'] = 0
    
    return stats

def display_dashboard(stats, log_lines):
    """Zeigt das Dashboard an."""
    clear_screen()
    
    # Bot-Status
    running, pid = check_bot_status()
    if running:
        status = f"{Colors.GREEN}AKTIV (PID: {pid}){Colors.ENDC}"
    else:
        status = f"{Colors.RED}INAKTIV{Colors.ENDC}"
    
    # Aktuelle Zeit
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Header
    print(f"{Colors.HEADER}{Colors.BOLD}ZEPHYR-BOT ÜBERWACHUNG{Colors.ENDC}")
    print(f"Status: {status} | Zeit: {current_time}\n")
    
    # Statistiken
    print(f"{Colors.BLUE}{Colors.BOLD}INTERAKTIONS-STATISTIKEN:{Colors.ENDC}")
    if 'interactions' in stats:
        interactions = stats['interactions']
        sentiment = interactions.get('sentiment', 'unbekannt')
        sentiment_color = Colors.GREEN if sentiment in ['positiv', 'sehr positiv'] else \
                          Colors.RED if sentiment in ['negativ', 'sehr negativ'] else \
                          Colors.YELLOW
        
        print(f"Nachrichten: {interactions.get('messages', 0)} | Befehle: {interactions.get('commands', 0)}")
        print(f"Witze: {interactions.get('jokes', 0)} | Fragen: {interactions.get('questions', 0)} | Spiele: {interactions.get('games', 0)}")
        print(f"Chat-Stimmung: {sentiment_color}{sentiment}{Colors.ENDC}")
    
    print(f"\n{Colors.BLUE}{Colors.BOLD}VIEWER-STATISTIKEN:{Colors.ENDC}")
    if 'viewers' in stats:
        if len(stats['viewers']) > 0:
            # Top 5 aktivste Viewer
            sorted_viewers = sorted(stats['viewers'].items(), 
                                   key=lambda x: x[1]['messages'] if isinstance(x[1], dict) and 'messages' in x[1] else 0, 
                                   reverse=True)[:5]
            print("Top Viewer:")
            for user, user_stats in sorted_viewers:
                if isinstance(user_stats, dict) and 'messages' in user_stats:
                    print(f"  {user}: {user_stats['messages']} Nachrichten, {user_stats['commands']} Befehle")
        else:
            print("Keine Viewer-Statistiken verfügbar")
    
    # Persönlichkeitsprofil
    print(f"\n{Colors.BLUE}{Colors.BOLD}PERSÖNLICHKEITSPROFIL:{Colors.ENDC}")
    if 'personality' in stats and isinstance(stats['personality'], dict):
        pers = stats['personality']
        for trait, value in pers.items():
            # Farbliche Darstellung je nach Wert (1-10 Skala)
            if isinstance(value, (int, float)):
                color = Colors.RED if value < 4 else Colors.YELLOW if value < 7 else Colors.GREEN
                bar = '█' * int(value) + '░' * (10 - int(value))
                print(f"  {trait.capitalize()}: {color}{bar} {value}/10{Colors.ENDC}")
    
    # Letzte Befehle
    print(f"\n{Colors.BLUE}{Colors.BOLD}LETZTE BEFEHLE:{Colors.ENDC}")
    if 'recent_commands' in stats:
        for cmd, count in stats['recent_commands'].items():
            print(f"  {cmd}: {count}x")
    
    # Chat-History Anzahl
    print(f"\n{Colors.BLUE}{Colors.BOLD}TRAINING-DATEN:{Colors.ENDC}")
    print(f"Chat-History-Einträge: {stats.get('chat_history_count', 0)}")
    
    # Letzte Logs
    print(f"\n{Colors.BLUE}{Colors.BOLD}LETZTE LOGS:{Colors.ENDC}")
    for line in log_lines:
        # Farbliche Hervorhebung von Fehlern
        if "ERROR" in line:
            print(f"{Colors.RED}{line}{Colors.ENDC}")
        elif "WARN" in line:
            print(f"{Colors.YELLOW}{line}{Colors.ENDC}")
        else:
            print(line)
    
    # Befehle
    print(f"\n{Colors.YELLOW}{Colors.BOLD}BEFEHLE:{Colors.ENDC}")
    print(f"  {Colors.GREEN}r{Colors.ENDC} - Aktualisieren | {Colors.GREEN}q{Colors.ENDC} - Beenden | {Colors.GREEN}s{Colors.ENDC} - Bot starten/stoppen")
    print(f"  {Colors.GREEN}v{Colors.ENDC} - Viewer-Details | {Colors.GREEN}l{Colors.ENDC} - Mehr Logs anzeigen | {Colors.GREEN}t{Colors.ENDC} - Trainings-Details")

def start_stop_bot():
    """Startet oder stoppt den Bot."""
    running, pid = check_bot_status()
    
    if running:
        # Stoppe den Bot
        print(f"Stoppe Bot mit PID {pid}...")
        try:
            os.kill(pid, 15)  # SIGTERM
            time.sleep(2)
            
            # Prüfe, ob der Bot gestoppt wurde
            try:
                os.kill(pid, 0)
                print("Bot konnte nicht sauber beendet werden, versuche mit SIGKILL...")
                os.kill(pid, 9)  # SIGKILL
                time.sleep(1)
            except OSError:
                pass  # Prozess existiert nicht mehr, ist also gestoppt
            
            # Entferne PID-Datei
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
            
            print("Bot wurde gestoppt.")
        except Exception as e:
            print(f"Fehler beim Stoppen des Bots: {e}")
    else:
        # Starte den Bot
        script_path = os.path.join(BASE_DIR, "enhanced-zephyr-start.sh")
        
        if not os.path.exists(script_path):
            print(f"Fehler: Start-Skript '{script_path}' nicht gefunden!")
            input("Drücke Enter, um fortzufahren...")
            return
        
        print("Starte Bot...")
        try:
            subprocess.Popen(['bash', script_path], 
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE)
            print("Bot-Startbefehl wurde ausgeführt.")
        except Exception as e:
            print(f"Fehler beim Starten des Bots: {e}")
    
    input("Drücke Enter, um fortzufahren...")

def show_viewer_details(stats):
    """Zeigt detaillierte Informationen über die Viewer an."""
    clear_screen()
    
    print(f"{Colors.HEADER}{Colors.BOLD}DETAILLIERTE VIEWER-STATISTIKEN{Colors.ENDC}\n")
    
    if 'viewers' in stats and isinstance(stats['viewers'], dict) and len(stats['viewers']) > 0:
        # Sortiere Viewer nach Anzahl der Nachrichten
        sorted_viewers = sorted(stats['viewers'].items(), 
                               key=lambda x: x[1]['messages'] if isinstance(x[1], dict) and 'messages' in x[1] else 0, 
                               reverse=True)
        
        for user, user_stats in sorted_viewers:
            if isinstance(user_stats, dict):
                print(f"{Colors.BOLD}{user}{Colors.ENDC}:")
                
                # Nachrichten und Befehle
                print(f"  Nachrichten: {user_stats.get('messages', 0)}")
                print(f"  Befehle: {user_stats.get('commands', 0)}")
                
                # Erste und letzte Aktivität
                first_seen = user_stats.get('first_seen', 'unbekannt')
                last_seen = user_stats.get('last_seen', 'unbekannt')
                
                if first_seen != 'unbekannt':
                    try:
                        first_seen_dt = datetime.fromisoformat(first_seen)
                        first_seen = first_seen_dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        pass
                
                if last_seen != 'unbekannt':
                    try:
                        last_seen_dt = datetime.fromisoformat(last_seen)
                        last_seen = last_seen_dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        pass
                
                print(f"  Erste Aktivität: {first_seen}")
                print(f"  Letzte Aktivität: {last_seen}")
                
                # Bevorzugte Befehle
                if 'favorite_commands' in user_stats and user_stats['favorite_commands']:
                    print("  Bevorzugte Befehle:")
                    fav_commands = user_stats['favorite_commands']
                    if isinstance(fav_commands, dict):
                        sorted_commands = sorted(fav_commands.items(), key=lambda x: x[1], reverse=True)
                        for cmd, count in sorted_commands[:5]:  # Zeige nur die Top 5
                            print(f"    {cmd}: {count}x")
                
                print("")  # Leerzeile zwischen Benutzern
    else:
        print("Keine Viewer-Statistiken verfügbar.")
    
    input("\nDrücke Enter, um zum Dashboard zurückzukehren...")

def show_more_logs(lines=50):
    """Zeigt mehr Logzeilen an."""
    clear_screen()
    
    print(f"{Colors.HEADER}{Colors.BOLD}ERWEITERTE LOG-ANZEIGE{Colors.ENDC}\n")
    
    log_lines = get_log_tail(lines)
    
    for line in log_lines:
        # Farbliche Hervorhebung von Fehlern
        if "ERROR" in line:
            print(f"{Colors.RED}{line}{Colors.ENDC}")
        elif "WARN" in line:
            print(f"{Colors.YELLOW}{line}{Colors.ENDC}")
        else:
            print(line)
    
    input("\nDrücke Enter, um zum Dashboard zurückzukehren...")

def show_training_details():
    """Zeigt Details zu den Trainingsdaten an."""
    clear_screen()
    
    print(f"{Colors.HEADER}{Colors.BOLD}TRAININGS-DETAILS{Colors.ENDC}\n")
    
    # Überprüfe Chat-History
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
                print(f"Chat-History-Einträge: {len(lines)}")
                
                # Analyse der Chat-History
                users = []
                commands = 0
                regular_msgs = 0
                bot_responses = 0
                
                # Zeitliche Verteilung
                time_distribution = {
                    "letzte_stunde": 0,
                    "heute": 0,
                    "gestern": 0,
                    "aelter": 0
                }
                
                now = datetime.now()
                one_hour_ago = now - timedelta(hours=1)
                today_start = datetime(now.year, now.month, now.day)
                yesterday_start = today_start - timedelta(days=1)
                
                for line in lines:
                    try:
                        msg = json.loads(line)
                        
                        # Zähle Nachrichten nach Typ
                        if 'user' in msg:
                            if msg['user'].lower() == 'zephyr':
                                bot_responses += 1
                            else:
                                users.append(msg['user'])
                                if msg.get('is_command', False):
                                    commands += 1
                                else:
                                    regular_msgs += 1
                        
                        # Analysiere Zeitstempel
                        if 'timestamp' in msg:
                            try:
                                msg_time = datetime.fromisoformat(msg['timestamp'])
                                
                                if msg_time > one_hour_ago:
                                    time_distribution["letzte_stunde"] += 1
                                elif msg_time > today_start:
                                    time_distribution["heute"] += 1
                                elif msg_time > yesterday_start:
                                    time_distribution["gestern"] += 1
                                else:
                                    time_distribution["aelter"] += 1
                            except:
                                pass
                    except:
                        continue
                
                unique_users = len(set(users))
                
                print(f"\n{Colors.BLUE}{Colors.BOLD}NACHRICHTEN-ANALYSE:{Colors.ENDC}")
                print(f"Benutzernachrichten: {regular_msgs + commands}")
                print(f"Bot-Antworten: {bot_responses}")
                print(f"Befehle: {commands}")
                print(f"Eindeutige Benutzer: {unique_users}")
                
                print(f"\n{Colors.BLUE}{Colors.BOLD}ZEITLICHE VERTEILUNG:{Colors.ENDC}")
                print(f"Letzte Stunde: {time_distribution['letzte_stunde']}")
                print(f"Heute: {time_distribution['heute']}")
                print(f"Gestern: {time_distribution['gestern']}")
                print(f"Älter: {time_distribution['aelter']}")
                
                # Top-Benutzer
                user_counts = Counter(users)
                print(f"\n{Colors.BLUE}{Colors.BOLD}TOP-BENUTZER:{Colors.ENDC}")
                for user, count in user_counts.most_common(10):
                    print(f"  {user}: {count} Nachrichten")
                
                # Zeige die neuesten Trainings-Einträge
                print(f"\n{Colors.BLUE}{Colors.BOLD}NEUESTE CHAT-NACHRICHTEN:{Colors.ENDC}")
                for line in lines[-5:]:
                    try:
                        msg = json.loads(line)
                        timestamp = msg.get('timestamp', 'unbekannt')
                        user = msg.get('user', 'unbekannt')
                        content = msg.get('content', '')
                        
                        # Formatiere Zeitstempel
                        if timestamp != 'unbekannt':
                            try:
                                timestamp_dt = datetime.fromisoformat(timestamp)
                                timestamp = timestamp_dt.strftime("%Y-%m-%d %H:%M:%S")
                            except:
                                pass
                        
                        # Kürze lange Inhalte
                        if len(content) > 50:
                            content = content[:47] + "..."
                        
                        # Farbliche Hervorhebung von Bot-Nachrichten
                        if user.lower() == 'zephyr':
                            print(f"  {timestamp} {Colors.GREEN}{user}{Colors.ENDC}: {content}")
                        else:
                            print(f"  {timestamp} {Colors.YELLOW}{user}{Colors.ENDC}: {content}")
                    except:
                        print(f"  Fehler beim Parsen der Nachricht")
        except Exception as e:
            print(f"Fehler beim Analysieren der Chat-History: {e}")
    else:
        print("Keine Chat-History gefunden.")
    
    input("\nDrücke Enter, um zum Dashboard zurückzukehren...")

def main():
    """Hauptfunktion zur Ausführung des Monitors."""
    parser = argparse.ArgumentParser(description='Zephyr-Bot Monitor')
    parser.add_argument('--refresh', type=int, default=10, help='Aktualisierungsintervall in Sekunden (Standard: 10)')
    args = parser.parse_args()
    
    refresh_interval = args.refresh
    
    try:
        while True:
            stats = load_stats()
            log_lines = get_log_tail()
            display_dashboard(stats, log_lines)
            
            # Warte auf Benutzereingabe mit Timeout
            print(f"\nAktualisiere in {refresh_interval} Sekunden (oder drücke eine Taste)...")
            
            # Nicht-blockierendes Einlesen der Tastatur
            import select
            import sys
            
            # Warte auf Benutzereingabe oder Timeout
            rlist, _, _ = select.select([sys.stdin], [], [], refresh_interval)
            
            if rlist:
                key = sys.stdin.read(1).lower()
                
                if key == 'q':  # Beenden
                    print("Beende Monitor...")
                    break
                elif key == 's':  # Start/Stop Bot
                    start_stop_bot()
                elif key == 'v':  # Viewer-Details
                    show_viewer_details(stats)
                elif key == 'l':  # Mehr Logs
                    show_more_logs()
                elif key == 't':  # Trainings-Details
                    show_training_details()
                # Bei anderen Tasten einfach Aktualisieren (wird im nächsten Schleifendurchlauf gemacht)
    except KeyboardInterrupt:
        print("\nMonitor wird beendet...")
    except Exception as e:
        print(f"Fehler im Monitor: {e}")
        input("Drücke Enter, um zu beenden...")

if __name__ == "__main__":
    main()
