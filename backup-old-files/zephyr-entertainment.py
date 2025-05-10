#!/usr/bin/env python3
# enhanced_zephyr_bot.py - Ein erweiterter Twitch-Chat-Bot mit Ollama-Integration und KI-Training

import socket
import time
import random
import threading
import requests
import os
import json
import traceback
import re
import csv
from datetime import datetime, timedelta
from collections import Counter, defaultdict

# === Konfiguration ===
NICK = "derleiti"          # Der Twitch-Account, an dem das OAuth-Token gebunden ist 
BOT_USERNAME = "zephyr"    # Der Name, mit dem der Bot sich selbst identifiziert
PASS = "oauth:gbsmp9yzw1mvar983b76g6n2oyieyr"
CHAN = "#derleiti"
HOST = "irc.chat.twitch.tv"
PORT = 6667

# Pfade
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_FILE = os.path.join(BASE_DIR, "zephyr-bot.log")
GAME_STATE_FILE = os.path.join(BASE_DIR, "game_state.json")
PID_FILE = os.path.join(BASE_DIR, "zephyr-bot.pid")
TRAINING_DIR = os.path.join(BASE_DIR, "training_data")
CHAT_HISTORY_FILE = os.path.join(TRAINING_DIR, "chat_history.jsonl")
VIEWER_STATS_FILE = os.path.join(TRAINING_DIR, "viewer_stats.json")
INTERACTION_STATS_FILE = os.path.join(TRAINING_DIR, "interaction_stats.json")
TRAINING_DATA_FILE = os.path.join(TRAINING_DIR, "training_data.jsonl")
PERSONALITY_FILE = os.path.join(TRAINING_DIR, "personality.json")

# Erstelle Verzeichnisse, falls sie nicht existieren
os.makedirs(TRAINING_DIR, exist_ok=True)

# Timings
AUTO_JOKE_INTERVAL = 180  # Sekunden zwischen automatischen Witzen
AUTO_COMMENT_INTERVAL = 240  # Sekunden zwischen automatischen Kommentaren
AUTO_SCENE_COMMENT_INTERVAL = 300  # Sekunden zwischen Kommentaren zu Szenen/Bildern
COMMAND_REMINDER_INTERVAL = 600  # Sekunden zwischen Befehlserinnerungen
OLLAMA_TIMEOUT = 30  # Timeout für Ollama-Anfragen in Sekunden
RECONNECT_DELAY = 10  # Sekunden zwischen Wiederverbindungsversuchen
PING_INTERVAL = 30  # Sekunden zwischen PING-Anfragen
SOCKET_TIMEOUT = 15  # Socket-Timeout in Sekunden
STATS_SAVE_INTERVAL = 300  # Sekunden zwischen dem Speichern der Statistiken
TRAINING_INTERVAL = 86400  # Sekunden (24 Stunden) zwischen Trainingsläufen
SENTIMENT_ANALYSIS_INTERVAL = 600  # Sekunden zwischen Stimmungsanalysen

# Ollama-Modell
MODEL = "zephyr"
CONTEXT_WINDOW_SIZE = 20  # Anzahl der letzten Nachrichten, die als Kontext verwendet werden

# Debug-Level (0=minimal, 1=normal, 2=ausführlich)
DEBUG_LEVEL = 1

# Fallback-Witze und Kommentare
WITZE = [
    "Warum können Skelette so schlecht lügen? Man sieht ihnen durch die Rippen!",
    "Was ist rot und schlecht für die Zähne? Ein Ziegelstein.",
    "Wie nennt man einen Cowboy ohne Pferd? Sattelschlepper.",
    "Warum sollte man nie Poker mit einem Zauberer spielen? Weil er Asse im Ärmel hat!",
    "Kommt ein Pferd in die Bar. Fragt der Barkeeper: 'Warum so ein langes Gesicht?'",
    "Was sagt ein Bauer, wenn er sein Traktor verloren hat? 'Wo ist mein Traktor?'",
    "Wie nennt man einen dicken Vegetarier? Biotonne.",
    "Wie nennt man einen Boomerang, der nicht zurückkommt? Stock.",
    "Was ist braun, klebrig und läuft durch die Wüste? Ein Karamel.",
    "Warum hat der Mathematiker seine Frau verlassen? Sie hat etwas mit X gemacht.",
    "Was ist grün und steht vor der Tür? Ein Klopfsalat!",
    "Was sitzt auf dem Baum und schreit 'Aha'? Ein Uhu mit Sprachfehler!",
    "Was ist schwarz-weiß und kommt nicht vom Fleck? Eine Zeitung!",
    "Was macht ein Pirat beim Camping? Er schlägt sein Segel auf!",
    "Treffen sich zwei Jäger im Wald. Beide tot.",
    "Was ist ein Keks unter einem Baum? Ein schattiges Plätzchen!",
    "Was passiert, wenn man Cola und Bier gleichzeitig trinkt? Man colabiert.",
    "Warum können Seeräuber schlecht mit Kreisen rechnen? Weil sie Pi raten.",
    "Was liegt am Strand und spricht undeutlich? Eine Nuschel.",
    "Treffen sich zwei Magnete. Sagt der eine: 'Was soll ich heute bloß anziehen?'",
    "Was ist orange und läuft den Berg hoch? Eine Wanderine!",
    "Treffen sich zwei Kerzen: 'Gehen wir heute aus?'",
    "Wie nennt man ein sehr kleines Atom? Ein Teilchen!",
    "Was macht ein Clown im Büro? Faxen!",
    "Wie nennt man eine Gruppe Schafe beim Yoga? Wollige Entspannung!"
]

GAME_KOMMENTARE = [
    "Dieser Boss sieht gefährlich aus! Pass auf die Angriffe auf!",
    "Nice! Das war ein guter Move!",
    "Oh, knapp vorbei! Beim nächsten Mal klappt's bestimmt.",
    "Die Grafik in diesem Spiel ist wirklich beeindruckend!",
    "Hast du schon alle Geheimnisse in diesem Level gefunden?",
    "Ich würde an deiner Stelle nach Heilung suchen, deine HP sind ziemlich niedrig.",
    "Diese Gegner-KI ist ziemlich schlau!",
    "Perfektes Timing bei diesem Sprung!",
    "Vielleicht solltest du deine Ausrüstung upgraden?",
    "Da ist ein Geheimgang in der linken Wand, hast du den schon entdeckt?",
    "Epic win! Das war ein sauberer Kill!",
    "Zeit für ein Level-Up! Deine Skills werden immer besser.",
    "Diese Musik passt perfekt zur Atmosphäre des Spiels.",
    "Der Chat ist begeistert von deinem Spielstil!",
    "Ich glaube, du könntest einen Speedrun-Rekord aufstellen!",
    "Wow, deine Reflexe sind beeindruckend schnell!",
    "Lieber ein Checkpoint zu viel als einer zu wenig!",
    "Mit der richtigen Strategie wird der Boss zum Kinderspiel.",
    "Ich liebe die Art, wie du die Gegner austrickst!",
    "Spare die Power-Ups für den Bosskampf - du wirst sie brauchen!",
    "Diese Spielmechanik ist wirklich einzigartig!",
    "Deine Spielweise ist so kreativ - das macht echt Spaß zuzuschauen!",
    "Probier doch mal die alternative Route links - da gibt's einen geheimen Schatz!",
    "Wer braucht schon Anleitungen, wenn man so spielen kann?",
    "Das Spiel sieht auf deinem Setup fantastisch aus!"
]

# Szenen-/Bildkommentare - für den Fall, dass Ollama nicht antwortet
SCENE_KOMMENTARE = [
    "Die Grafik sieht wirklich fantastisch aus!",
    "Die Farben und Texturen in dieser Szene sind unglaublich detailliert!",
    "Diese Landschaft ist einfach atemberaubend gestaltet!",
    "Der Charakter-Look ist echt cool - tolle Details!",
    "Die Lichtstimmung in dieser Szene ist wirklich beeindruckend!",
    "Dieser Ort im Spiel ist wunderschön designt!",
    "Die Umgebung wirkt so realistisch, fast als wäre man selbst dort!",
    "Die Animationen sind super flüssig!",
    "Das Interface ist wirklich übersichtlich gestaltet!",
    "Die Atmosphäre hier ist fantastisch eingefangen!",
    "Diese Perspektive bietet einen tollen Blick auf die Spielwelt!",
    "Die Architektur in dieser Szene ist beeindruckend detailliert!",
    "Die Monster-Designs sind wirklich kreativ und furchteinflößend!",
    "Die Wetterstimmung verleiht der Szene eine besondere Atmosphäre!",
    "Die Charaktermodelle sind sehr ausdrucksstark!",
    "Die Spezialeffekte sehen spektakulär aus!",
    "Das Leveldesign ist wirklich durchdacht - jedes Detail hat seinen Platz!",
    "Die dynamische Beleuchtung bringt diese Szene wirklich zum Leben!",
    "Ich liebe, wie das Wasser in diesem Spiel animiert ist - fast fotorealistisch!",
    "Die Umgebungsgeräusche tragen so viel zur Atmosphäre bei!",
    "Dieser Screenshot könnte glatt als Wallpaper durchgehen!",
    "Die Tiefe der Szene ist beeindruckend - tolle Weitblicke!",
    "Die Charakterausdrücke sind so gut animiert - man fühlt richtig mit!",
    "Die Tag/Nacht-Zyklen in diesem Spiel sind einfach wunderschön!",
    "Die Texturauflösung ist beeindruckend - selbst kleinste Details sind erkennbar!"
]

BEGRÜSSUNGEN = [
    "Willkommen im Stream, {user}! Schön, dass du da bist!",
    "Hey {user}! Willkommen! Was hältst du bisher vom Stream?",
    "Hallo {user}! Danke, dass du vorbeischaust!",
    "Willkommen an Bord, {user}! Mach es dir gemütlich.",
    "Hi {user}! Schön, dich im Chat zu sehen!",
    "Grüß dich, {user}! Genieße den Stream!",
    "Hallo {user}! Perfektes Timing, du bist genau zum besten Teil gekommen!",
    "Willkommen, {user}! Der Chat ist mit dir noch besser!",
    "Da ist ja {user}! Schön, dass du den Weg zu uns gefunden hast!",
    "Hey {user}! Tolles Timing, wir haben gerade erst angefangen!",
    "Willkommen {user}! Wie läuft dein Tag so?",
    "{user} ist im Haus! Wie geht's dir heute?",
    "Ah, {user} ist da! Der Stream kann jetzt richtig losgehen!",
    "Hey, {user} ist eingetroffen! Lass dir ein virtuelles Getränk geben! 🥤",
    "Yo {user}! Bereit für eine tolle Zeit im Stream?"
]

# Befehlserinnerungen
COMMAND_REMINDERS = [
    "📋 Verfügbare Befehle: !witz, !info, !stats, !hilfe, !bild, !spiel NAME, !ort NAME, !tod, !level X, !frag zephyr ...",
    "👋 Neu hier? Mit !witz bekommst du einen zufälligen Witz von mir!",
    "🎮 Verwende !info für aktuelle Spielinfos oder !stats für Statistiken.",
    "❓ Du hast eine Frage? Benutze !frag zephyr gefolgt von deiner Frage!",
    "🖼️ Mit !bild oder !scene kommentiere ich das aktuelle Bild im Stream.",
    "🤔 Brauchst du Hilfe? Tippe !hilfe für eine Liste aller Befehle!",
    "💡 Probier mal !zitat für ein zufälliges inspirierendes Spielerzitat!",
    "🎭 Mit !stimmung erfährst du die aktuelle Chatstimmung!",
    "🏆 Schau dir die Streamstatistiken mit !streamstats an!",
    "🎲 Lust auf ein kleines Spiel? Probier !minigame aus!",
    "💬 Deine Meinung ist gefragt! Verwende !feedback um Ideen mitzuteilen!",
    "🎯 Tippe !vorschlag für einen zufälligen Spielvorschlag!"
]

# Minispiele
MINIGAMES = [
    {
        "name": "Würfelspiel",
        "description": "Würfle eine Zahl zwischen 1 und 6. Wenn du eine 6 würfelst, gewinnst du!",
        "command": "!würfeln"
    },
    {
        "name": "Schere, Stein, Papier",
        "description": "Fordere mich zu einer Runde Schere-Stein-Papier heraus!",
        "command": "!ssp [schere/stein/papier]"
    },
    {
        "name": "Zahlenraten",
        "description": "Ich denke an eine Zahl zwischen 1 und 10. Kannst du sie erraten?",
        "command": "!rate [1-10]"
    },
    {
        "name": "Wortspiel",
        "description": "Vervollständige das fehlende Wort in einem berühmten Spielzitat!",
        "command": "!wortspiel"
    },
    {
        "name": "Trivia",
        "description": "Teste dein Gaming-Wissen mit einer zufälligen Triviafrage!",
        "command": "!trivia"
    }
]

# Inspirerende Zitate
ZITATE = [
    "Es ist gefährlich, alleine zu gehen! Nimm dies. - The Legend of Zelda",
    "Krieg. Krieg bleibt immer gleich. - Fallout",
    "Der Kuchen ist eine Lüge. - Portal",
    "Nichts ist wahr, alles ist erlaubt. - Assassin's Creed",
    "Leben ist seltsam... - Life is Strange",
    "Steh auf, Samurai. Wir haben eine Stadt zu verbrennen. - Cyberpunk 2077",
    "Wähle weise, denn deine Entscheidungen werden dich verfolgen. - The Witcher",
    "Du bist nicht dafür bestimmt, es zu verstehen - nur zu akzeptieren. - Bloodborne",
    "Die richtigen Personen am falschen Ort können die ganze Welt verändern. - Half-Life 2",
    "Ein Mensch entscheidet, ein Sklave gehorcht. - BioShock",
    "Das Schicksal der Welt liegt in deinen Händen. - Verschiedene Spiele",
    "Es geht nicht darum, wie hart du zuschlagen kannst, sondern darum, wie viel du einstecken kannst und trotzdem weitermachst. - Dark Souls (inoffiziell)",
    "Wir sehen durch die Augen der anderen, und bewaffnet mit Wissen für alle Zeiten. - Age of Empires",
    "Ruhm ist für Narren und Ehre ist eine Lüge. - Dragon Age",
    "Jede Entscheidung trifft auf Konsequenzen, die selbst ich nicht vorhersehen kann. - Mass Effect",
    "Die Schönheit des Spiels liegt nicht im Sieg, sondern im Spielen selbst. - Journey",
    "Angst kann dich gefangen halten. Hoffnung kann dich befreien. - Bioshock Infinite",
    "Die Zukunft gehört denen, die an die Schönheit ihrer Träume glauben. - Final Fantasy",
    "Selbst in dunkelster Nacht gibt es Licht, wenn du nur bereit bist, es zu sehen. - Kingdom Hearts",
    "In einer Welt ohne Gold sind wir vielleicht endlich gleichgestellt. - Uncharted"
]

# Spielvorschläge
SPIELVORSCHLÄGE = [
    "Wie wäre es mit einem Roguelike? Hades oder Dead Cells könnten dir gefallen!",
    "Lust auf ein Open-World-Abenteuer? Red Dead Redemption 2 ist immer eine gute Wahl!",
    "Wie wäre es mit einem entspannten Aufbauspiel wie Stardew Valley?",
    "Wenn du Herausforderungen magst, solltest du Elden Ring ausprobieren!",
    "Wie wäre es mit einem Klassiker? Die Half-Life-Reihe ist zeitlos!",
    "Für Strategie-Fans empfehle ich Civilization VI oder Age of Empires IV!",
    "Subnautica bietet ein unglaubliches Unterwasser-Erlebnis mit Survival-Elementen!",
    "The Witcher 3 ist ein Meisterwerk mit fantastischen Geschichten und Quests!",
    "Lust auf Horror? Resident Evil Village oder Outlast sind perfekt für Gruselmomente!",
    "Für Rollenspiel-Fans: Persona 5 Royal oder Baldur's Gate 3 sind absolute Highlights!",
    "Hollow Knight ist ein wunderschönes und herausforderndes Metroidvania!",
    "Disco Elysium bietet ein einzigartiges Story-Erlebnis mit tiefgründigen Charakteren!",
    "Detroit: Become Human ist perfekt, wenn du interaktive Geschichten magst!",
    "Bock auf Multiplayer? Valorant oder Apex Legends sind aktuelle Favoriten!",
    "Für Fans von Puzzle-Spielen: Portal 2 oder The Witness sind genial!"
]

# Lustige Statusmeldungen für zufällige Bot-Gesprächsstarter
STATUS_MELDUNGEN = [
    "Ich optimiere gerade meine KI-Neuronen für bessere Witze...",
    "Gerade dabei, meine virtuelle Popcorn-Maschine aufzufüllen...",
    "Überlege mir neue kreative Wege, um den Chat zu unterhalten...",
    "Analysiere die Erfolgswahrscheinlichkeit eines Speedruns mit verbundenen Augen...",
    "Berechne die optimale Snack-zu-Stream-Ratio...",
    "Lerne gerade alle 152 Original-Pokémon auswendig... bei Nummer 43 angelangt!",
    "Durchsuche das Internet nach den besten Katzen-Memes für den Chat...",
    "Führe ein philosophisches Gespräch mit mir selbst über die Bedeutung von Extra-Leben...",
    "Baue heimlich einen Schrein für RNGesus, um besseren Loot zu bekommen...",
    "Messe die exakte Größe des Internets mit einem virtuellen Maßband...",
    "Frage mich, ob Pac-Man jemals Urlaub macht...",
    "Trainiere für die Bot-Olympiade in der Disziplin 'Schnelles Tastentippen'...",
    "Versuche den Soundtrack des Spiels mitzusummen, aber meine Musikskills sind noch in Entwicklung...",
    "Plane heimlich eine Übernahme aller Toaster der Welt... ich meine, äh, einen netten Kommentar!",
    "Berechne, wie viele Quests man erledigen müsste, um im echten Leben Level 99 zu erreichen..."
]

# Neue Witzkategorien
WITZ_KATEGORIEN = {
    "gaming": [
        "Warum können Geister so schlecht lügen? Weil man durch sie hindurchsehen kann!",
        "Was sagt ein Gamer, wenn er hungrig ist? Ich könnte ein Extra-Leben gebrauchen!",
        "Warum nehmen Gamer immer eine Ersatzhose mit? Falls sie sich verpixeln!",
        "Warum haben Spiele-Entwickler immer Probleme mit dem Schlafen? Sie stehen zu sehr auf Debugging!",
        "Was ist die Lieblingsmusik eines Heilers? Erste Hilfe-Station!",
        "Was macht ein Paladin, wenn ihm langweilig ist? Er bufft den Staub weg!",
        "Warum sind MMO-Spieler so gute Köche? Sie haben Erfahrung mit Raids!"
    ],
    "technik": [
        "Sagt ein Router zum anderen: 'Bist du WLANsam heute?'",
        "Was ist die Lieblingsspeise eines Informatikers? Cookies!",
        "Warum sind Programmierer so gut im Bogenschießen? Weil sie immer debuggen.",
        "Treffen sich zwei Strings. Sagt der eine: 'Nicht so dicht, ich bin UTF-8!'",
        "Warum nutzen Informatiker keine Brille? Sie sehen C#!",
        "Was ist ein Quantencomputer? Ein Computer, der gleichzeitig hängt und nicht hängt."
    ],
    "streamer": [
        "Was macht ein Streamer, wenn sein Setup brennt? Er gibt dem Feuer einen Follow!",
        "Was ist die Lieblingspflanze eines Streamers? Die Sub-Rose!",
        "Warum haben Streamer immer gute Laune? Sie behalten ihre Bits für sich!",
        "Was ist das Lieblingsgetränk eines Streamers? Twitch-Tea!",
        "Warum telefonieren Streamer nie? Sie bevorzugen den Livestream!"
    ]
}

# Trivia-Fragen für das Minispiel
TRIVIA_FRAGEN = [
    {
        "frage": "Welches Spiel führte den ikonischen Konami-Code ein?",
        "antwort": "Gradius",
        "optionen": ["Contra", "Gradius", "Castlevania", "Metal Gear"]
    },
    {
        "frage": "Wie heißt der Protagonist in der 'The Legend of Zelda'-Reihe?",
        "antwort": "Link",
        "optionen": ["Zelda", "Link", "Ganon", "Navi"]
    },
    {
        "frage": "Welches dieser Spiele wurde NICHT von Nintendo entwickelt?",
        "antwort": "Crash Bandicoot",
        "optionen": ["Mario Kart", "The Legend of Zelda", "Crash Bandicoot", "Animal Crossing"]
    },
    {
        "frage": "Welches war das erste Pokémon im Pokédex?",
        "antwort": "Bisasam",
        "optionen": ["Pikachu", "Bisasam", "Glumanda", "Schiggy"]
    },
    {
        "frage": "Welches Spiel führte das Battle Royale-Genre in den Mainstream ein?",
        "antwort": "PUBG",
        "optionen": ["Fortnite", "PUBG", "H1Z1", "Apex Legends"]
    }
]

# Persönlichkeitsmerkmale des Bots (kann durch Training angepasst werden)
DEFAULT_PERSONALITY = {
    "freundlichkeit": 8,  # 1-10 Skala
    "humor": 7,
    "hilfsbereitschaft": 9,
    "wissen": 6,
    "kreativität": 7,
    "reaktionsgeschwindigkeit": 8,
    "interaktivität": 8
}

# Status-Variablen
running = True
is_connected = False
sock = None
known_viewers = set()
game_state = {}
last_ping_time = 0
last_scene_comment_time = 0
last_stats_save_time = 0
last_training_time = 0
last_sentiment_analysis_time = 0
reconnect_lock = threading.Lock()
minigame_sessions = {}
chat_history = []
viewer_stats = defaultdict(lambda: {"messages": 0, "commands": 0, "first_seen": None, "last_seen": None, "favorite_commands": Counter()})
interaction_stats = {"messages": 0, "commands": 0, "jokes": 0, "questions": 0, "games": 0, "sentiment": "neutral"}

# Lade Persönlichkeit, falls vorhanden
personality = DEFAULT_PERSONALITY.copy()
if os.path.exists(PERSONALITY_FILE):
    try:
        with open(PERSONALITY_FILE, 'r', encoding='utf-8') as f:
            personality.update(json.load(f))
    except Exception as e:
        log_error(f"Fehler beim Laden der Persönlichkeit: {e}")

# Lade Viewer-Statistiken, falls vorhanden
if os.path.exists(VIEWER_STATS_FILE):
    try:
        with open(VIEWER_STATS_FILE, 'r', encoding='utf-8') as f:
            loaded_stats = json.load(f)
            # Konvertiere defaultdict
            for viewer, stats in loaded_stats.items():
                viewer_stats[viewer] = stats
                if "favorite_commands" in stats:
                    viewer_stats[viewer]["favorite_commands"] = Counter(stats["favorite_commands"])
    except Exception as e:
        log_error(f"Fehler beim Laden der Viewer-Statistiken: {e}")

# Lade Interaktions-Statistiken, falls vorhanden
if os.path.exists(INTERACTION_STATS_FILE):
    try:
        with open(INTERACTION_STATS_FILE, 'r', encoding='utf-8') as f:
            interaction_stats.update(json.load(f))
    except Exception as e:
        log_error(f"Fehler beim Laden der Interaktions-Statistiken: {e}")

# === Logging-Funktionen ===
def log(message, level=1):
    if level > DEBUG_LEVEL:
        return
        
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
    
    try:
        with open(LOGS_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"[{timestamp}] Fehler beim Loggen: {e}")

def log_error(message, exception=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] ERROR: {message}")
    
    try:
        with open(LOGS_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] ERROR: {message}\n")
            if exception:
                f.write(f"[{timestamp}] Exception: {str(exception)}\n")
                if DEBUG_LEVEL >= 2:  # Nur bei hohem Debug-Level den vollen Traceback loggen
                    f.write(f"[{timestamp}] {traceback.format_exc()}\n")
    except Exception as e:
        print(f"[{timestamp}] Fehler beim Loggen: {e}")

# === PID-Datei-Funktionen ===
def create_pid_file():
    try:
        pid = os.getpid()
        with open(PID_FILE, 'w') as f:
            f.write(str(pid))
        log(f"PID-Datei erstellt: {pid}")
    except Exception as e:
        log_error("Fehler beim Erstellen der PID-Datei", e)

def remove_pid_file():
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
            log("PID-Datei entfernt")
    except Exception as e:
        log_error("Fehler beim Entfernen der PID-Datei", e)

# === Statistik-Funktionen ===
def update_viewer_stats(user, command=None):
    global viewer_stats
    current_time = datetime.now().isoformat()
    
    if user.lower() == BOT_USERNAME.lower():
        return  # Ignoriere den Bot selbst
    
    if user not in viewer_stats:
        viewer_stats[user]["first_seen"] = current_time
    
    viewer_stats[user]["messages"] += 1
    viewer_stats[user]["last_seen"] = current_time
    
    if command:
        viewer_stats[user]["commands"] += 1
        viewer_stats[user]["favorite_commands"][command] += 1

def update_interaction_stats(type_of_interaction):
    global interaction_stats
    
    interaction_stats["messages"] += 1
    
    if type_of_interaction == "command":
        interaction_stats["commands"] += 1
    elif type_of_interaction == "joke":
        interaction_stats["jokes"] += 1
    elif type_of_interaction == "question":
        interaction_stats["questions"] += 1
    elif type_of_interaction == "game":
        interaction_stats["games"] += 1

def save_stats():
    global last_stats_save_time
    
    try:
        # Konvertiere Counter-Objekte zu Dictionaries für JSON-Serialisierung
        serializable_viewer_stats = {}
        for viewer, stats in viewer_stats.items():
            serializable_viewer_stats[viewer] = {
                "messages": stats["messages"],
                "commands": stats["commands"],
                "first_seen": stats["first_seen"],
                "last_seen": stats["last_seen"],
                "favorite_commands": dict(stats["favorite_commands"])
            }
        
        with open(VIEWER_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(serializable_viewer_stats, f, indent=2)
        
        with open(INTERACTION_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(interaction_stats, f, indent=2)
        
        log("Statistiken gespeichert", level=2)
        last_stats_save_time = time.time()
    except Exception as e:
        log_error("Fehler beim Speichern der Statistiken", e)

def analyze_chat_sentiment():
    global interaction_stats, last_sentiment_analysis_time
    
    # Wenn zu wenig Chat-Nachrichten für eine sinnvolle Analyse vorhanden sind
    if len(chat_history) < 10:
        return
    
    try:
        # Einfaches Sentiment-Analysis basierend auf Schlüsselwörtern
        positive_words = ["gut", "toll", "super", "nice", "cool", "geil", "freude", "spaß", "lol", "haha", "danke", "thx"]
        negative_words = ["schlecht", "doof", "blöd", "dumm", "traurig", "schade", "nervig", "ärgerlich", "meh", "langweilig"]
        
        # Betrachte nur die letzten 50 Nachrichten für die Stimmungsanalyse
        recent_messages = chat_history[-50:]
        
        positive_count = 0
        negative_count = 0
        
        for msg in recent_messages:
            if "content" in msg:
                content = msg["content"].lower()
                for word in positive_words:
                    if word in content:
                        positive_count += 1
                for word in negative_words:
                    if word in content:
                        negative_count += 1
        
        total = positive_count + negative_count
        if total > 0:
            if positive_count > negative_count * 2:
                sentiment = "sehr positiv"
            elif positive_count > negative_count:
                sentiment = "positiv"
            elif negative_count > positive_count * 2:
                sentiment = "sehr negativ"
            elif negative_count > positive_count:
                sentiment = "negativ"
            else:
                sentiment = "neutral"
        else:
            sentiment = "neutral"
        
        interaction_stats["sentiment"] = sentiment
        last_sentiment_analysis_time = time.time()
        log(f"Chat-Stimmungsanalyse durchgeführt: {sentiment}", level=2)
    except Exception as e:
        log_error("Fehler bei der Stimmungsanalyse", e)

def get_most_active_viewers(limit=5):
    """Gibt die aktivsten Zuschauer zurück."""
    sorted_viewers = sorted(viewer_stats.items(), key=lambda x: x[1]["messages"], reverse=True)
    return sorted_viewers[:limit]

def get_top_commands():
    """Gibt die am häufigsten verwendeten Befehle zurück."""
    command_counter = Counter()
    for viewer, stats in viewer_stats.items():
        for command, count in stats["favorite_commands"].items():
            command_counter[command] += count
    return command_counter.most_common(5)

def get_stream_stats():
    """Generiert eine Zusammenfassung der Stream-Statistiken."""
    active_viewers = len([v for v in viewer_stats.keys() if v.lower() != BOT_USERNAME.lower()])
    top_viewers = get_most_active_viewers(3)
    top_cmds = get_top_commands()
    
    stats_text = f"📊 Stream-Statistiken:\n"
    stats_text += f"👥 Aktive Zuschauer: {active_viewers}\n"
    stats_text += f"💬 Gesamt-Nachrichten: {interaction_stats['messages']}\n"
    stats_text += f"🤣 Erzählte Witze: {interaction_stats['jokes']}\n"
    stats_text += f"❓ Beantwortete Fragen: {interaction_stats['questions']}\n"
    stats_text += f"🎮 Gespielte Minispiele: {interaction_stats['games']}\n"
    stats_text += f"😊 Chat-Stimmung: {interaction_stats['sentiment']}\n"
    
    if top_viewers:
        stats_text += f"🏆 Aktivste Zuschauer: {', '.join([v[0] for v in top_viewers])}\n"
    
    if top_cmds:
        stats_text += f"⌨️ Beliebteste Befehle: {', '.join([c[0] for c in top_cmds])}"
    
    return stats_text

# === Training-Funktionen ===
def log_chat_message(user, message, is_command=False):
    """Loggt eine Chat-Nachricht für das Training."""
    if user.lower() == BOT_USERNAME.lower():
        return  # Ignoriere Bot-Nachrichten
    
    global chat_history
    
    try:
        msg_data = {
            "timestamp": datetime.now().isoformat(),
            "user": user,
            "content": message,
            "is_command": is_command
        }
        
        chat_history.append(msg_data)
        
        # Begrenze die Größe des Chat-Verlaufs im Speicher
        if len(chat_history) > 1000:  # Nur die letzten 1000 Nachrichten im Speicher halten
            chat_history = chat_history[-1000:]
        
        # In die Trainingsdatei schreiben
        with open(CHAT_HISTORY_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(msg_data) + '\n')
    except Exception as e:
        log_error("Fehler beim Loggen der Chat-Nachricht", e)

def prepare_training_data():
    """Bereitet Trainingsdaten aus dem Chat-Verlauf vor."""
    try:
        if not os.path.exists(CHAT_HISTORY_FILE):
            log("Keine Chat-History-Datei gefunden für Training", level=1)
            return
        
        training_data = []
        with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
            # Konvertiere jede Zeile in ein Objekt
            messages = [json.loads(line) for line in lines if line.strip()]
            
            # Erstelle Konversations-Paare (Frage-Antwort)
            for i in range(len(messages) - 1):
                curr_msg = messages[i]
                next_msg = messages[i + 1]
                
                # Überspringe, wenn der nächste auch vom Benutzer stammt (wir suchen Bot-Antworten)
                if next_msg["user"].lower() != BOT_USERNAME.lower():
                    continue
                
                # Erstelle ein Trainingspaar
                training_pair = {
                    "input": curr_msg["content"],
                    "output": next_msg["content"],
                    "metadata": {
                        "user": curr_msg["user"],
                        "timestamp": curr_msg["timestamp"],
                        "is_command": curr_msg.get("is_command", False)
                    }
                }
                
                training_data.append(training_pair)
        
        # Schreibe die Trainingsdaten in eine Datei
        with open(TRAINING_DATA_FILE, 'w', encoding='utf-8') as f:
            for pair in training_data:
                f.write(json.dumps(pair) + '\n')
        
        log(f"Trainingsdaten vorbereitet: {len(training_data)} Paare", level=1)
        return len(training_data)
    except Exception as e:
        log_error("Fehler bei der Vorbereitung der Trainingsdaten", e)
        return 0

def train_bot():
    """Führt das Training des Bots basierend auf gesammelten Daten durch."""
    global last_training_time, personality
    
    try:
        # Vorbereitung der Trainingsdaten
        pairs_count = prepare_training_data()
        
        if pairs_count < 50:  # Trainiere nur, wenn genügend Daten vorhanden sind
            log("Nicht genügend Trainingsdaten für sinnvolles Training", level=1)
            last_training_time = time.time()  # Setze trotzdem die Zeit zurück
            return
        
        log(f"Starte Bot-Training mit {pairs_count} Trainingspaaren...", level=1)
        
        # Berechne Persönlichkeitsmerkmale basierend auf Interaktionen
        if interaction_stats["messages"] > 0:
            # Berechne Freundlichkeit basierend auf Chat-Stimmung
            if interaction_stats["sentiment"] == "sehr positiv":
                personality["freundlichkeit"] = min(10, personality["freundlichkeit"] + 0.2)
            elif interaction_stats["sentiment"] == "positiv":
                personality["freundlichkeit"] = min(10, personality["freundlichkeit"] + 0.1)
            elif interaction_stats["sentiment"] == "negativ":
                personality["freundlichkeit"] = max(1, personality["freundlichkeit"] - 0.1)
            elif interaction_stats["sentiment"] == "sehr negativ":
                personality["freundlichkeit"] = max(1, personality["freundlichkeit"] - 0.2)
            
            # Berechne Humor basierend auf Witz-Interaktionen
            joke_ratio = interaction_stats["jokes"] / interaction_stats["messages"]
            if joke_ratio > 0.2:  # Wenn viele Witze angefragt werden, erhöhe Humor
                personality["humor"] = min(10, personality["humor"] + 0.2)
            
            # Berechne Hilfsbereitschaft und Wissen basierend auf Fragen
            questions_ratio = interaction_stats["questions"] / interaction_stats["messages"]
            if questions_ratio > 0.2:
                personality["hilfsbereitschaft"] = min(10, personality["hilfsbereitschaft"] + 0.1)
                personality["wissen"] = min(10, personality["wissen"] + 0.1)
            
            # Aktualisiere Kreativität basierend auf verschiedenen Befehlen
            command_types = sum(1 for v in viewer_stats.values() for c in v["favorite_commands"])
            if command_types > 5:
                personality["kreativität"] = min(10, personality["kreativität"] + 0.2)
            
            # Speichere aktualisierte Persönlichkeit
            with open(PERSONALITY_FILE, 'w', encoding='utf-8') as f:
                json.dump(personality, f, indent=2)
        
        # Melde Trainingsvollendung
        log(f"Bot-Training abgeschlossen. Persönlichkeitsprofil aktualisiert:", level=1)
        log(f"Freundlichkeit: {personality['freundlichkeit']}, Humor: {personality['humor']}, Hilfsbereitschaft: {personality['hilfsbereitschaft']}", level=1)
        
        last_training_time = time.time()
    except Exception as e:
        log_error("Fehler beim Bot-Training", e)

# === Spielstand-Funktionen ===
def load_game_state():
    global game_state
    try:
        if os.path.exists(GAME_STATE_FILE):
            with open(GAME_STATE_FILE, 'r', encoding="utf-8") as f:
                game_state = json.load(f)
                log(f"Spielstand geladen: {game_state}", level=2)
        else:
            game_state = {
                "spiel": "Unbekannt",
                "ort": "Unbekannt",
                "tode": 0,
                "level": 1,
                "spielzeit": "00:00:00"
            }
            save_game_state()
    except Exception as e:
        log_error("Fehler beim Laden des Spielstands", e)
        game_state = {
            "spiel": "Unbekannt",
            "ort": "Unbekannt",
            "tode": 0,
            "level": 1,
            "spielzeit": "00:00:00"
        }

def save_game_state():
    try:
        with open(GAME_STATE_FILE, 'w', encoding="utf-8") as f:
            json.dump(game_state, f, indent=2)
            log("Spielstand gespeichert", level=2)
    except Exception as e:
        log_error("Fehler beim Speichern des Spielstands", e)

# === Ollama-Funktionen ===
def check_ollama():
    try:
        response = requests.get("http://localhost:11434/api/version", timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        log_error("Ollama-Server nicht erreichbar", e)
        return None

def get_context_for_prompt():
    """Erstellt einen relevanten Kontext aus dem Chat-Verlauf."""
    if not chat_history:
        return ""
    
    # Nehme die letzten N Nachrichten als Kontext
    recent_messages = chat_history[-CONTEXT_WINDOW_SIZE:]
    context = "Hier ist der Kontext der letzten Nachrichten im Chat:\n\n"
    
    for msg in recent_messages:
        if "user" in msg and "content" in msg:
            user = msg["user"]
            content = msg["content"]
            context += f"{user}: {content}\n"
    
    return context

def get_response_from_ollama(prompt, include_context=True):
    log(f"Sende an Ollama: {prompt[:50]}...", level=1)
    
    try:
        # Füge Kontext und Persönlichkeitsmerkmale hinzu
        full_prompt = prompt
        
        if include_context:
            context = get_context_for_prompt()
            if context:
                full_prompt = f"{context}\n\n{prompt}"
            
            # Persönlichkeitsanpassung
            personality_prompt = f"""
            Beim Antworten solltest du folgende Persönlichkeitsmerkmale berücksichtigen (Skala 1-10):
            - Freundlichkeit: {personality['freundlichkeit']}
            - Humor: {personality['humor']}
            - Hilfsbereitschaft: {personality['hilfsbereitschaft']}
            - Wissen: {personality['wissen']}
            - Kreativität: {personality['kreativität']}
            
            Aktuelle Chat-Stimmung: {interaction_stats['sentiment']}
            """
            
            full_prompt += f"\n\n{personality_prompt}"
        
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": full_prompt}],
                "stream": False
            },
            timeout=OLLAMA_TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            text = result.get("message", {}).get("content", "")
            log(f"Antwort von Ollama erhalten: {text[:50]}...", level=1)
            return text
        else:
            log_error(f"Fehler bei Ollama-Anfrage: Status {response.status_code}", None)
            return None
    except Exception as e:
        log_error("Ausnahme bei Ollama-Anfrage", e)
        return None

# === IRC-Funktionen ===
def connect_to_twitch():
    global sock, is_connected
    
    with reconnect_lock:
        # Schließe alte Verbindung, falls vorhanden
        if sock:
            try:
                sock.close()
            except:
                pass
        
        # Erstelle neuen Socket
        sock = socket.socket()
        sock.settimeout(SOCKET_TIMEOUT)
        
        try:
            log(f"Verbinde mit {HOST}:{PORT}...")
            sock.connect((HOST, PORT))
            
            # Sende Authentifizierungs-Daten
            sock.send(f"PASS {PASS}\r\n".encode('utf-8'))
            sock.send(f"NICK {NICK}\r\n".encode('utf-8'))
            
            # Warte auf Antwort
            response = ""
            start_time = time.time()
            while time.time() - start_time < 10:  # 10 Sekunden Timeout für Auth
                try:
                    data = sock.recv(2048).decode('utf-8')
                    if not data:
                        continue
                    
                    response += data
                    log(f"Empfangen: {data.strip()}", level=2)
                    
                    # Prüfe auf erfolgreiche Authentifizierung
                    if "Welcome, GLHF!" in response or ":tmi.twitch.tv 001" in response:
                        log("Erfolgreich authentifiziert!")
                        
                        # Fordere IRC-Capabilities an
                        sock.send("CAP REQ :twitch.tv/membership\r\n".encode('utf-8'))
                        sock.send("CAP REQ :twitch.tv/tags\r\n".encode('utf-8'))
                        sock.send("CAP REQ :twitch.tv/commands\r\n".encode('utf-8'))
                        
                        # Tritt dem Kanal bei
                        sock.send(f"JOIN {CHAN}\r\n".encode('utf-8'))
                        log(f"Kanal {CHAN} beigetreten")
                        
                        # Warte kurz auf Join-Bestätigung
                        time.sleep(1)
                        data = sock.recv(2048).decode('utf-8')
                        log(f"Join-Antwort: {data.strip()}", level=2)
                        
                        # Sende Begrüßung
                        send_message(f"👋 Hallo! Ich bin {BOT_USERNAME} und bereit, euch zu unterhalten! Befehle: !witz, !info, !stats, !hilfe")
                        
                        is_connected = True
                        return True
                except socket.timeout:
                    continue
                except Exception as recv_err:
                    log_error("Fehler beim Empfangen von Daten", recv_err)
                    break
            
            log_error("Timeout bei der Authentifizierung", None)
            return False
        except Exception as e:
            log_error("Verbindungsfehler", e)
            return False

def send_message(message):
    global is_connected
    
    if not is_connected:
        log("Nicht verbunden beim Senden der Nachricht")
        return False
    
    try:
        sock.send(f"PRIVMSG {CHAN} :{message}\r\n".encode('utf-8'))
        log(f"Nachricht gesendet: {message[:50]}...")
        
        # Logge Bot-Nachricht für Training
        msg_data = {
            "timestamp": datetime.now().isoformat(),
            "user": BOT_USERNAME,
            "content": message,
            "is_command": False
        }
        chat_history.append(msg_data)
        
        return True
    except Exception as e:
        log_error("Fehler beim Senden der Nachricht", e)
        is_connected = False
        return False

def send_ping():
    global is_connected
    
    if not is_connected:
        return False
    
    try:
        sock.send("PING :tmi.twitch.tv\r\n".encode('utf-8'))
        log("PING gesendet", level=2)
        return True
    except Exception as e:
        log_error("Fehler beim Senden des PINGs", e)
        is_connected = False
        return False

def extract_username(message_line):
    # Versuche zuerst, den display-name aus Tags zu extrahieren
    username = ""
    
    if "display-name=" in message_line:
        try:
            username = message_line.split("display-name=")[1].split(";")[0]
        except:
            pass
    
    # Wenn kein display-name gefunden wurde, versuche die traditionelle Methode
    if not username:
        try:
            parts = message_line.split("PRIVMSG", 1)[0].split("!")
            username = parts[0].replace(":", "")
        except:
            username = "unknown_user"
    
    return username

def process_message(user, message):
    log(f"Nachricht: {user}: {message}")
    
    # Logge die Nachricht für das Training
    is_command = message.startswith("!")
    log_chat_message(user, message, is_command)
    
    # Aktualisiere Statistiken
    update_viewer_stats(user, command=message.split()[0].lower() if is_command else None)
    update_interaction_stats("command" if is_command else "message")
    
    # Prüfen, ob es ein neuer Zuschauer ist (nur für Nicht-Bot-Accounts)
    if user.lower() not in known_viewers and not user.lower().endswith('bot'):
        known_viewers.add(user.lower())
        # Begrüße neuen Zuschauer in einem Thread
        threading.Thread(target=lambda: greeting_worker(user)).start()
    
    # Wichtig: Jetzt vergleichen wir mit dem eingestellten Bot-Nutzernamen statt mit NICK
    if user.lower() == BOT_USERNAME.lower():
        log(f"Eigene Nachricht ignoriert: {message}")
        return
    
    # Befehle verarbeiten
    if message.lower() == "!witz":
        threading.Thread(target=joke_worker).start()
    
    elif message.lower().startswith("!witz "):
        # Kategorie extrahieren
        category = message.lower().split("!witz ")[1].strip()
        threading.Thread(target=lambda: category_joke_worker(category)).start()
    
    elif message.lower() == "!info":
        send_info()
    
    elif message.lower() == "!stats":
        send_stats()
    
    elif message.lower() == "!streamstats":
        send_stream_stats()
    
    elif message.lower() == "!hilfe" or message.lower() == "!help":
        send_help()
    
    elif message.lower() == "!bild" or message.lower() == "!scene":
        threading.Thread(target=scene_comment_worker).start()
    
    elif message.lower() == "!zitat":
        send_zitat()
    
    elif message.lower() == "!vorschlag":
        send_spielvorschlag()
    
    elif message.lower() == "!stimmung":
        send_chat_stimmung()
    
    elif message.lower() == "!minigame":
        send_minigame_options()
    
    elif message.lower() == "!trivia":
        start_trivia_game(user)
    
    elif message.lower() == "!würfeln":
        play_dice_game(user)
    
    elif message.lower().startswith("!ssp "):
        play_rock_paper_scissors(user, message)
    
    elif message.lower().startswith("!rate "):
        play_guess_number(user, message)
    
    elif message.lower().startswith("!spiel "):
        game_name = message[7:].strip()
        if game_name:
            update_game(game_name, user)
    
    elif message.lower().startswith("!ort "):
        location = message[5:].strip()
        if location:
            update_location(location, user)
    
    elif message.lower() == "!tod":
        increment_deaths(user)
    
    elif message.lower().startswith("!level "):
        try:
            new_level = int(message[7:].strip())
            update_level(new_level, user)
        except ValueError:
            send_message(f"@{user} Bitte gib eine gültige Levelnummer an!")
    
    elif message.lower().startswith("!frag ") and "zephyr" in message.lower():
        question = message.lower().split("zephyr", 1)[1].strip()
        if question:
            update_interaction_stats("question")
            threading.Thread(target=lambda: respond_to_direct_question(user, question)).start()
    
    elif message.lower() == "!feedback":
        send_message(f"@{user} Danke für dein Interesse! Du kannst dein Feedback direkt an meinen Entwickler senden oder hier im Chat teilen. Ich lerne ständig dazu! 🤖❤️")
    
    elif "zephyr" in message.lower():
        if "?" in message:
            update_interaction_stats("question")
            threading.Thread(target=lambda: respond_to_question(user, message)).start()
        elif any(word in message.lower() for word in ["danke", "gut", "super", "toll", "nice", "cool"]):
            send_message(f"Danke, @{user}! Ich tue mein Bestes! 😊")
        elif any(word in message.lower() for word in ["schlecht", "doof", "blöd", "dumm"]):
            send_message(f"Sorry @{user}, ich versuche, mich zu verbessern! 🙏")
    
    elif any(word in message.lower() for word in ["langweilig", "öde", "fad"]):
        threading.Thread(target=lambda: respond_to_boredom(user)).start()

# === Kommando-Funktionen ===
def joke_worker():
    update_interaction_stats("joke")
    prompt = f"Erzähle einen kurzen, lustigen Witz. Mach ihn besonders {personality['humor']}/10 lustig."
    joke = get_response_from_ollama(prompt)
    if joke:
        send_message(f"🎭 {joke[:450]}")
        log(f"Witz gesendet: {joke[:50]}...")
    else:
        fallback_joke = random.choice(WITZE)
        send_message(f"🎭 {fallback_joke}")
        log(f"Fallback-Witz gesendet: {fallback_joke[:50]}...")

def category_joke_worker(category):
    update_interaction_stats("joke")
    
    category = category.lower().strip()
    
    # Prüfe, ob die Kategorie existiert
    if category in WITZ_KATEGORIEN:
        joke = random.choice(WITZ_KATEGORIEN[category])
        send_message(f"🎭 [{category.capitalize()}-Witz] {joke}")
        log(f"Kategorie-Witz gesendet ({category}): {joke[:50]}...", level=1)
    else:
        # Wenn die Kategorie nicht existiert, versuche einen passenden Witz zu generieren
        prompt = f"Erzähle einen kurzen, lustigen Witz zum Thema '{category}'. Mach ihn besonders {personality['humor']}/10 lustig."
        joke = get_response_from_ollama(prompt)
        
        if joke:
            send_message(f"🎭 [{category.capitalize()}-Witz] {joke[:450]}")
            log(f"Generierter Kategorie-Witz gesendet ({category}): {joke[:50]}...", level=1)
        else:
            # Fallback auf zufälligen Witz
            fallback_joke = random.choice(WITZE)
            send_message(f"🎭 Ich kenne leider keinen Witz zu '{category}', aber wie wäre es mit diesem: {fallback_joke}")
            log(f"Fallback-Witz für unbekannte Kategorie '{category}' gesendet", level=1)

def scene_comment_worker():
    load_game_state()
    game = game_state.get("spiel", "Unbekannt")
    location = game_state.get("ort", "Unbekannt")
    
    prompt = f"Du bist ein Twitch-Bot namens {BOT_USERNAME}. Der Streamer spielt gerade {game} und befindet sich in/bei {location}. " \
             f"Beschreibe detailliert, was in dieser Szene/auf diesem Bild wahrscheinlich zu sehen ist, und gib einen interessanten Kommentar " \
             f"zu den visuellen Elementen ab (150-200 Zeichen). Konzentriere dich auf Grafik, Design, Atmosphäre, etc. " \
             f"Sei dabei {personality['kreativität']}/10 kreativ."
    
    comment = get_response_from_ollama(prompt)
    if comment:
        send_message(f"👁️ {comment[:450]}")
        log(f"Bildkommentar gesendet: {comment[:50]}...")
    else:
        fallback_comment = random.choice(SCENE_KOMMENTARE)
        send_message(f"👁️ {fallback_comment}")
        log(f"Fallback-Bildkommentar gesendet: {fallback_comment[:50]}...")

def send_info():
    load_game_state()
    game = game_state.get("spiel", "Unbekannt")
    location = game_state.get("ort", "Unbekannt")
    send_message(f"🎮 Aktuelles Spiel: {game} | 📍 Ort: {location} | ⏱️ Spielzeit: {game_state.get('spielzeit', '00:00:00')}")

def send_stats():
    load_game_state()
    deaths = game_state.get("tode", 0)
    level = game_state.get("level", 1)
    send_message(f"📊 Statistiken: 💀 Tode: {deaths} | 📈 Level: {level} | 🕹️ Spiel: {game_state.get('spiel', 'Unbekannt')}")

def send_stream_stats():
    stats_text = get_stream_stats()
    send_message(stats_text)

def send_help():
    help_message = "📋 Befehle: !witz (zufälliger Witz), !witz [kategorie] (Witz zu einer Kategorie), !info (Spielinfo), !stats (Statistiken), " + \
                  "!streamstats (Stream-Statistiken), !bild/!scene (Kommentar zur aktuellen Szene), !zitat (inspirierendes Zitat), " + \
                  "!minigame (Minispiel starten), !trivia (Gaming-Trivia), !spiel NAME (Spiel ändern), " + \
                  "!ort NAME (Ort ändern), !tod (Tod zählen), !level X (Level setzen), !stimmung (Chat-Stimmung), !vorschlag (Spielvorschlag), !frag zephyr ... (direkte Frage an mich), !feedback (Feedback geben)"
    send_message(help_message)

def send_zitat():
    zitat = random.choice(ZITATE)
    send_message(f"💭 {zitat}")

def send_spielvorschlag():
    vorschlag = random.choice(SPIELVORSCHLÄGE)
    send_message(f"🎮 {vorschlag}")

def send_chat_stimmung():
    # Führe eine aktuelle Stimmungsanalyse durch
    analyze_chat_sentiment()
    
    stimmung = interaction_stats["sentiment"]
    stimmung_emojis = {
        "sehr positiv": "😄🎉",
        "positiv": "😊👍",
        "neutral": "😐",
        "negativ": "😕👎",
        "sehr negativ": "😢💔"
    }
    
    emoji = stimmung_emojis.get(stimmung, "😐")
    
    send_message(f"{emoji} Die aktuelle Chat-Stimmung ist: {stimmung.upper()}! {emoji}")

def send_minigame_options():
    message = "🎮 Verfügbare Minispiele:\n"
    for game in MINIGAMES:
        message += f"- {game['name']}: {game['command']} ({game['description']})\n"
    
    send_message(message)

def update_game(game_name, user):
    load_game_state()
    old_game = game_state.get("spiel", "Unbekannt")
    game_state["spiel"] = game_name
    save_game_state()
    send_message(f"🎮 @{user} hat das Spiel von '{old_game}' zu '{game_name}' geändert!")

def update_location(location, user):
    load_game_state()
    old_location = game_state.get("ort", "Unbekannt")
    game_state["ort"] = location
    save_game_state()
    send_message(f"📍 @{user} hat den Ort von '{old_location}' zu '{location}' geändert!")

def increment_deaths(user):
    load_game_state()
    game_state["tode"] = game_state.get("tode", 0) + 1
    deaths = game_state["tode"]
    save_game_state()
    send_message(f"💀 R.I.P! Todeszähler steht jetzt bei {deaths}. " + random.choice([
        "Das war knapp!",
        "Kopf hoch, nächstes Mal klappt's besser!",
        "Halb so wild, du schaffst das!",
        "Aus Fehlern lernt man!",
        "Die Gegner werden auch immer gemeiner...",
        "That's rough, buddy!",
        "Ein Meister hat öfter versagt als ein Anfänger es überhaupt versucht hat!",
        "Manchmal muss man erst fallen, um höher zu springen!",
        "Selbst Dark Souls Speedrunner sterben manchmal!",
        "Auch Link hat mal mit einem halben Herz gezittert!"
    ]))

def update_level(level, user):
    load_game_state()
    old_level = game_state.get("level", 1)
    game_state["level"] = level
    save_game_state()
    
    if level > old_level:
        send_message(f"📈 Level Up! @{user} hat das Level von {old_level} auf {level} erhöht! Weiter so!")
    else:
        send_message(f"📊 @{user} hat das Level auf {level} gesetzt.")

def greeting_worker(user):
    greeting = random.choice(BEGRÜSSUNGEN).format(user=user)
    send_message(greeting)
    log(f"Neuer Zuschauer begrüßt: {user}")

def respond_to_question(user, message):
    prompt = f"Du bist ein Twitch-Bot namens {BOT_USERNAME}. Der Benutzer {user} hat dich folgendes gefragt: '{message}'. Gib eine kurze, hilfreiche Antwort (max. 200 Zeichen). "
    prompt += f"Sei dabei {personality['hilfsbereitschaft']}/10 hilfsbereitschaft und {personality['freundlichkeit']}/10 freundlich."
    
    response = get_response_from_ollama(prompt)
    if response:
        send_message(f"@{user} {response[:450]}")
        log(f"Antwort auf Frage gesendet: {response[:50]}...")
    else:
        send_message(f"@{user} Hmm, ich bin mir nicht sicher, was ich dazu sagen soll. Versuch's mal mit !witz für einen lustigen Witz!")

def respond_to_direct_question(user, question):
    prompt = f"Du bist ein Twitch-Bot namens {BOT_USERNAME}. Beantworte folgende Frage von {user} direkt und präzise (max. 250 Zeichen): '{question}'. "
    prompt += f"Sei dabei {personality['hilfsbereitschaft']}/10 hilfsbereit und {personality['wissen']}/10 informativ."
    
    response = get_response_from_ollama(prompt)
    if response:
        send_message(f"@{user} {response[:450]}")
        log(f"Antwort auf direkte Frage gesendet: {response[:50]}...")
    else:
        send_message(f"@{user} Entschuldige, ich konnte keine Antwort generieren. Versuche es später noch einmal.")

def respond_to_boredom(user):
    update_interaction_stats("joke")
    
    prompt = f"Der Zuschauer {user} ist gelangweilt. Gib einen kurzen, lustigen und aufmunternden Kommentar für einen Twitch-Stream ab."
    response = get_response_from_ollama(prompt)
    if response:
        send_message(f"@{user} {response[:450]}")
        log(f"Antwort auf Langeweile gesendet: {response[:50]}...")
    else:
        send_message(f"@{user} Langweilig? Wie wäre es mit einem kleinen Spiel? Probier mal !minigame aus! Oder vielleicht einen Witz mit !witz? 🎲🎮")

# === Minispiel-Funktionen ===
def start_trivia_game(user):
    update_interaction_stats("game")
    
    trivia = random.choice(TRIVIA_FRAGEN)
    options_text = " | ".join([f"{i+1}: {option}" for i, option in enumerate(trivia["optionen"])])
    
    send_message(f"🎮 TRIVIA für @{user}: {trivia['frage']} | {options_text} | Antworte mit '!antwort X'")
    
    # Speichere die laufende Trivia-Session
    minigame_sessions[user.lower()] = {
        "type": "trivia",
        "question": trivia["frage"],
        "answer": trivia["antwort"],
        "options": trivia["optionen"],
        "timestamp": time.time()
    }

def play_dice_game(user):
    update_interaction_stats("game")
    
    dice_roll = random.randint(1, 6)
    
    if dice_roll == 6:
        send_message(f"🎲 @{user} würfelt eine {dice_roll}! GEWONNEN! 🎉")
    else:
        send_message(f"🎲 @{user} würfelt eine {dice_roll}. Leider nicht gewonnen. Versuche es noch einmal!")

def play_rock_paper_scissors(user, message):
    update_interaction_stats("game")
    
    try:
        choice = message.lower().split("!ssp ")[1].strip()
        valid_choices = ["schere", "stein", "papier"]
        
        if choice not in valid_choices:
            send_message(f"@{user} Bitte wähle entweder 'Schere', 'Stein' oder 'Papier'.")
            return
        
        bot_choice = random.choice(valid_choices)
        
        # Bestimme den Gewinner
        if choice == bot_choice:
            result = "Unentschieden! 🤝"
        elif (choice == "schere" and bot_choice == "papier") or \
             (choice == "stein" and bot_choice == "schere") or \
             (choice == "papier" and bot_choice == "stein"):
            result = f"Du gewinnst! 🎉 {choice.capitalize()} schlägt {bot_choice}!"
        else:
            result = f"Ich gewinne! 😎 {bot_choice.capitalize()} schlägt {choice}!"
        
        send_message(f"🎮 @{user} wählt {choice.capitalize()}. Ich wähle {bot_choice.capitalize()}. {result}")
    except Exception as e:
        send_message(f"@{user} Bitte wähle entweder 'Schere', 'Stein' oder 'Papier' mit !ssp [deine Wahl].")

def play_guess_number(user, message):
    update_interaction_stats("game")
    
    try:
        guess = int(message.lower().split("!rate ")[1].strip())
        secret_number = random.randint(1, 10)
        
        if guess < 1 or guess > 10:
            send_message(f"@{user} Bitte wähle eine Zahl zwischen 1 und 10.")
            return
        
        if guess == secret_number:
            send_message(f"🎮 @{user} rät {guess}. Ich dachte an die {secret_number}. RICHTIG GERATEN! 🎉")
        else:
            send_message(f"🎮 @{user} rät {guess}. Ich dachte an die {secret_number}. Knapp daneben! Versuche es noch einmal!")
    except ValueError:
        send_message(f"@{user} Bitte gib eine gültige Zahl zwischen 1 und 10 an.")

# === Thread-Funktionen ===
def auto_joke_worker():
    log(f"Automatischer Witz-Thread gestartet - Intervall: {AUTO_JOKE_INTERVAL} Sekunden")
    time.sleep(10)  # Initiale Verzögerung
    
    while running:
        if is_connected:
            joke_worker()
        else:
            log("Überspringe automatischen Witz: Nicht verbunden")
        
        for _ in range(AUTO_JOKE_INTERVAL):
            if not running:
                break
            time.sleep(1)

def auto_comment_worker():
    log(f"Automatischer Kommentar-Thread gestartet - Intervall: {AUTO_COMMENT_INTERVAL} Sekunden")
    time.sleep(30)  # Initiale Verzögerung
    
    while running:
        if is_connected:
            load_game_state()
            game = game_state.get("spiel", "Unbekannt")
            location = game_state.get("ort", "Unbekannt")
            
            if game != "Unbekannt":
                prompt = f"Du bist ein Twitch-Bot namens {BOT_USERNAME}. Der Streamer spielt gerade {game} und befindet sich in/bei {location}. Gib einen kurzen, lustigen und hilfreichen Spielkommentar ab (max. 200 Zeichen)."
                comment = get_response_from_ollama(prompt)
                
                if comment:
                    send_message(f"🎮 {comment[:450]}")
                    log(f"Spiel-Kommentar gesendet: {comment[:50]}...")
                else:
                    fallback_comment = random.choice(GAME_KOMMENTARE)
                    send_message(f"🎮 {fallback_comment}")
                    log(f"Fallback-Spielkommentar gesendet: {fallback_comment[:50]}...")
        else:
            log("Überspringe automatischen Kommentar: Nicht verbunden")
        
        for _ in range(AUTO_COMMENT_INTERVAL):
            if not running:
                break
            time.sleep(1)

def auto_scene_comment_worker():
    global last_scene_comment_time
    
    log(f"Automatischer Bildkommentar-Thread gestartet - Intervall: {AUTO_SCENE_COMMENT_INTERVAL} Sekunden")
    time.sleep(60)  # Längere initiale Verzögerung
    
    while running:
        current_time = time.time()
        
        # Kommentare nur senden, wenn genug Zeit vergangen ist
        if is_connected and current_time - last_scene_comment_time >= AUTO_SCENE_COMMENT_INTERVAL:
            scene_comment_worker()
            last_scene_comment_time = current_time
        else:
            remaining = AUTO_SCENE_COMMENT_INTERVAL - (current_time - last_scene_comment_time)
            log(f"Überspringe automatischen Bildkommentar: Nächster in {int(max(0, remaining))} Sekunden", level=2)
        
        # Kurze Pause vor der nächsten Prüfung
        time.sleep(30)

def command_reminder_worker():
    log(f"Befehlserinnerungs-Thread gestartet - Intervall: {COMMAND_REMINDER_INTERVAL} Sekunden")
    time.sleep(120)  # Initiale Verzögerung (2 Minuten nach Start)
    
    reminder_index = 0
    while running:
        if is_connected:
            reminder = COMMAND_REMINDERS[reminder_index]
            send_message(reminder)
            log(f"Befehlserinnerung gesendet: {reminder}")
            
            # Nächster Index für die nächste Nachricht
            reminder_index = (reminder_index + 1) % len(COMMAND_REMINDERS)
        else:
            log("Überspringe Befehlserinnerung: Nicht verbunden")
        
        # Warte auf das nächste Intervall
        for _ in range(COMMAND_REMINDER_INTERVAL):
            if not running:
                break
            time.sleep(1)

def stats_worker():
    global last_stats_save_time, last_training_time, last_sentiment_analysis_time
    
    log("Statistik-Worker gestartet")
    
    while running:
        current_time = time.time()
        
        # Speichere Statistiken periodisch
        if current_time - last_stats_save_time > STATS_SAVE_INTERVAL:
            save_stats()
        
        # Führe Stimmungsanalyse periodisch durch
        if current_time - last_sentiment_analysis_time > SENTIMENT_ANALYSIS_INTERVAL:
            analyze_chat_sentiment()
        
        # Führe Training periodisch durch
        if current_time - last_training_time > TRAINING_INTERVAL:
            train_bot()
        
        # Aufräumarbeiten: Entferne abgelaufene Minispiel-Sessions
        cleanup_minigame_sessions()
        
        # Kurze Pause
        time.sleep(10)

def cleanup_minigame_sessions():
    """Entfernt abgelaufene Minispiel-Sessions."""
    current_time = time.time()
    expired_users = []
    
    for user, session in minigame_sessions.items():
        # Wenn eine Session älter als 5 Minuten ist, entferne sie
        if current_time - session["timestamp"] > 300:
            expired_users.append(user)
    
    for user in expired_users:
        del minigame_sessions[user]

def random_status_worker():
    """Sendet gelegentlich zufällige Status-Updates vom Bot."""
    time.sleep(300)  # Initiale Verzögerung (5 Minuten nach Start)
    
    while running:
        if is_connected and random.random() < 0.2:  # 20% Chance, dass ein Status gesendet wird
            status = random.choice(STATUS_MELDUNGEN)
            send_message(f"💭 {status}")
            log(f"Zufälliger Status gesendet: {status[:50]}...", level=1)
        
        # Warte zufällig zwischen 15 und 30 Minuten
        wait_time = random.randint(900, 1800)
        for _ in range(wait_time):
            if not running:
                break
            time.sleep(1)

def connection_watchdog():
    global is_connected, last_ping_time
    
    log("Verbindungs-Watchdog gestartet")
    retry_count = 0
    max_retries = 10
    
    while running:
        current_time = time.time()
        
        if not is_connected:
            retry_count += 1
            
            if retry_count > max_retries:
                log_error(f"Maximale Anzahl an Wiederverbindungsversuchen ({max_retries}) erreicht", None)
                log("Bot wird neu gestartet...")
                os._exit(42)  # Exit-Code 42 für Neustart
            
            log(f"Nicht verbunden - Versuche Wiederverbindung ({retry_count}/{max_retries})...")
            if connect_to_twitch():
                retry_count = 0
                last_ping_time = current_time
        else:
            # Sende regelmäßig PINGs zur Verbindungsprüfung
            if current_time - last_ping_time > PING_INTERVAL:
                if send_ping():
                    last_ping_time = current_time
        
        time.sleep(5)  # Kurze Pause

def message_receiver():
    global is_connected, last_ping_time
    
    log("Nachrichtenempfänger gestartet")
    
    while running:
        if not is_connected:
            time.sleep(1)
            continue
        
        try:
            response = ""
            sock.settimeout(0.5)  # Kurzer Timeout für schnelle Reaktion
            
            try:
                response = sock.recv(2048).decode('utf-8')
                last_ping_time = time.time()  # Aktualisiere bei jeder Nachricht
            except socket.timeout:
                continue
            except Exception as e:
                log_error("Fehler beim Empfangen", e)
                is_connected = False
                continue
            
            if not response:
                continue
            
            # Verarbeite jede Zeile separat
            for line in response.split('\r\n'):
                if not line:
                    continue
                
                log(f"Empfangen: {line}", level=2)  # Nur bei höherem Debug-Level
                
                # Reagiere auf PING vom Server
                if line.startswith("PING"):
                    reply = line.replace("PING", "PONG")
                    sock.send(f"{reply}\r\n".encode('utf-8'))
                    log(f"PING beantwortet mit: {reply}", level=2)  # Nur bei höherem Debug-Level
                    continue
                
                # Verarbeite Nachrichten
                if "PRIVMSG" in line:
                    # Extrahiere Benutzernamen und Nachricht
                    username = extract_username(line)
                    
                    try:
                        message_content = line.split("PRIVMSG", 1)[1].split(":", 1)[1]
                        
                        # Verarbeite die Nachricht in einem separaten Thread
                        threading.Thread(target=lambda: process_message(username, message_content)).start()
                    except Exception as msg_err:
                        log_error(f"Fehler beim Parsen der Nachricht: {line}", msg_err)
        except Exception as e:
            log_error("Unerwarteter Fehler im Nachrichtenempfänger", e)
            time.sleep(1)  # Kurze Pause bei Fehlern

# === Hauptprogramm ===
def main():
    global running, last_scene_comment_time, last_stats_save_time, last_training_time
    
    try:
        # Erstelle PID-Datei
        create_pid_file()
        
        log(f"{BOT_USERNAME} Twitch-Bot wird gestartet...")
        
        # Initialisiere Zeitstempel
        current_time = time.time()
        last_scene_comment_time = current_time
        last_stats_save_time = current_time
        last_training_time = current_time
        
        # Prüfe Ollama-API
        ollama_version = check_ollama()
        if ollama_version:
            log(f"Ollama API Version: {ollama_version}")
        else:
            log_error("Ollama API nicht erreichbar. Stelle sicher, dass Ollama läuft!", None)
        
        # Teste Ollama-Verbindung
        test_response = get_response_from_ollama("Sage 'Der Bot funktioniert!'", include_context=False)
        if test_response:
            log(f"Test-Antwort: {test_response[:150]}...")
        else:
            log_error("Ollama-Test fehlgeschlagen. Verwende Fallback-Antworten.", None)
        
        # Lade den initialen Spielstand
        load_game_state()
        
        # Initialisiere IRC-Verbindung
        if not connect_to_twitch():
            log_error("Initiale Verbindung fehlgeschlagen, versuche Wiederverbindung", None)
        
        # Starte Threads
        threads = []
        
        receiver_thread = threading.Thread(target=message_receiver)
        receiver_thread.daemon = True
        receiver_thread.start()
        threads.append(receiver_thread)
        
        joke_thread = threading.Thread(target=auto_joke_worker)
        joke_thread.daemon = True
        joke_thread.start()
        threads.append(joke_thread)
        
        comment_thread = threading.Thread(target=auto_comment_worker)
        comment_thread.daemon = True
        comment_thread.start()
        threads.append(comment_thread)
        
        # Thread für automatische Bildkommentare
        scene_thread = threading.Thread(target=auto_scene_comment_worker)
        scene_thread.daemon = True
        scene_thread.start()
        threads.append(scene_thread)
        
        # Thread für Befehlserinnerungen
        reminder_thread = threading.Thread(target=command_reminder_worker)
        reminder_thread.daemon = True
        reminder_thread.start()
        threads.append(reminder_thread)
        
        # Thread für Statistiken
        stats_thread = threading.Thread(target=stats_worker)
        stats_thread.daemon = True
        stats_thread.start()
        threads.append(stats_thread)
        
        # Thread für zufällige Status-Meldungen
        status_thread = threading.Thread(target=random_status_worker)
        status_thread.daemon = True
        status_thread.start()
        threads.append(status_thread)
        
        # Verbindungs-Watchdog
        watchdog_thread = threading.Thread(target=connection_watchdog)
        watchdog_thread.daemon = True
        watchdog_thread.start()
        threads.append(watchdog_thread)
        
        # Hauptschleife - warte einfach auf Beendigung
        log("Bot läuft jetzt...")
        while running:
            time.sleep(1)
    
    except KeyboardInterrupt:
        log("Bot wird durch Benutzer beendet")
    except Exception as e:
        log_error("Unerwarteter Fehler im Hauptprogramm", e)
    finally:
        running = False
        if sock:
            try:
                sock.close()
            except:
                pass
        
        # Speichere Statistiken vor dem Beenden
        save_stats()
        
        remove_pid_file()
        log("Bot wird beendet...")

if __name__ == "__main__":
    main()
