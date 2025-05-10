import os
import asyncio
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import AuthScope
from dotenv import load_dotenv

# .env laden
load_dotenv()

CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("TWITCH_ACCESS_TOKEN")
BOT_NICK = os.getenv("BOT_USERNAME")  # z. B. "zephyrbot"

if not CLIENT_ID or not ACCESS_TOKEN:
    raise ValueError("❌ Twitch API-Konfiguration fehlt! Bitte .env prüfen.")

async def update_stream_info(game_title="Just Chatting", stream_title="Mit Zephyr live auf Twitch"):
    twitch = await Twitch(CLIENT_ID, CLIENT_SECRET)
    await twitch.set_user_authentication(ACCESS_TOKEN, [AuthScope.CHANNEL_MANAGE_BROADCAST], ACCESS_TOKEN)

    # Nutzer-ID holen
    user_data = await twitch.get_users(logins=[BOT_NICK])
    if not user_data['data']:
        raise ValueError(f"❌ Benutzer {BOT_NICK} nicht gefunden!")
    broadcaster_id = user_data['data'][0]['id']

    # Spiel suchen
    game_id = "509658"  # Just Chatting (Fallback)
    games = await twitch.search_categories(game_title)
    for g in games['data']:
        if g['name'].lower() == game_title.lower():
            game_id = g['id']
            break

    # Kanalinfo setzen
    await twitch.modify_channel_information(broadcaster_id, {
        "title": stream_title,
        "game_id": game_id
    })

    print(f"✅ Stream-Info aktualisiert: '{stream_title}' (Spiel: {game_title})")

# Nur ausführen, wenn direkt gestartet
if __name__ == "__main__":
    asyncio.run(update_stream_info("Baldur's Gate 3", "🎮 Zephyr kämpft in Baldur's Gate 3!"))
