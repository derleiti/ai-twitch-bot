#!/usr/bin/env python3
# zephyr-entertainment.py - A wrapper that calls the Twitch-Ollama bot

import os
import sys
import subprocess
import time

# Path to the actual bot
BOT_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "twitch-ollama-bot.py")

def main():
    print(f"zephyr-entertainment.py: Starting Twitch-Ollama bot from {BOT_SCRIPT}")
    
    # Check if the bot script exists
    if not os.path.exists(BOT_SCRIPT):
        print(f"ERROR: Bot script not found at {BOT_SCRIPT}")
        return 1
    
    # Make the bot script executable
    try:
        os.chmod(BOT_SCRIPT, 0o755)
    except Exception as e:
        print(f"WARNING: Could not make bot script executable: {e}")
    
    # Execute the actual bot script
    try:
        result = subprocess.run([sys.executable, BOT_SCRIPT], check=True)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Bot execution failed with code {e.returncode}")
        return e.returncode
    except Exception as e:
        print(f"ERROR: Failed to execute bot: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
