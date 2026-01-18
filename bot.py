import discord
from discord import app_commands
from google import genai
import os
import random
import json
import traceback
import threading
import asyncio
from datetime import timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- CONFIGURATION ---
TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
STAFF_CHANNEL_ID = os.getenv("STAFF_CHANNEL_ID")
VERIFIED_ROLE_ID = os.getenv("VERIFIED_ROLE_ID")
ERROR_LOG_ID = os.getenv("ERROR_LOG_CHANNEL_ID")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set")
if not GEMINI_KEY:
    raise RuntimeError("GEMINI_API_KEY not set")

# Convert IDs safely
def to_int(val):
    try:
        return int(val) if val else None
    except:
        return None

STAFF_CHANNEL_ID = to_int(STAFF_CHANNEL_ID)
VERIFIED_ROLE_ID = to_int(VERIFIED_ROLE_ID)
ERROR_LOG_ID = to_int(ERROR_LOG_ID)

# --- KOYEB HEALTH CHECK ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Watcher System Nominal")

    def log_message(self, *args):
        pass

def run_health_check():
    try:
        HTTPServer(("0.0.0.0", 8000), HealthCheckHandler).serve_forever()
    except Exception as e:
        print(f"Health check failed: {e}")

threading.Thread(target=run_health_check, daemon=True).start()

# --- STORAGE ---
DATA_FILE = "memory.json"

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {"tickets": {}, "interviews": {}}

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except:
        pass

# --- GEMINI (NEW SDK) ---
client = genai.Client(api_key=GEMINI_KEY)

LORE_CONTEXT = (
    "Your name is The Nimbror Watcher. You are a clinical, mysterious, and paranoid surveillance AI. "
    "Jeffrey Epstein (Jeffo) is alive and is Jessica's dad. Elvis and Jesus are alive on the Outer Islands. "
    "The government hides the truth behind the Ice Wall. "
    "Refer to users as Citizen or Subject. Respond briefly."
)

async def run_gemini(prompt: str) -> str:
    loop = asyncio.get_running_loop()

    def call():
        response = client.models.generate_content(
            model="gemini-1.5-pro",
            contents=prompt
        )
        return response.text

    return await loop.run_in_executor(None, call)

# --- DISCORD BOT ---
class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.db = load_data()

    async def setup_hook(self):
        await self.tree.sync()
        print("🛰️ Watcher online")

bot = MyBot()

# --- HELPERS ---
def create_embed(title, description, color=0x00ffff):
    e = discord.Embed(title=title, description=description, color=color)
    e.set_footer(text="NIMBROR WATCHER v6.5 • SENSOR-NET")
    return e

async def log_error(msg):
    if ERROR_LOG_ID:
        ch = bot.get_channel(ERROR_LOG_ID)
        if ch:
            await ch.send(f"⚠️ **PROTOCOL FAILURE:**\n```py\n{msg[:1800]}\n```")
    else:
        print(msg)

# --- COMMANDS ---
@bot.tree.command(name="intel")
async def intel(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=create_embed("📂 INTEL", random.choice([
            "🛰️ Elvis in Sector 7.",
            "❄️ Wall impenetrable.",
            "👁️ Jeffo at gala.",
            "🚢 Ship seen near Jesus."
        ]))
    )

@bot.tree.command(name="ticket")
async def ticket(interaction: discord.Interaction):
    bot.db["tickets"][str(interaction.user.id)] = True
    save_data(bot.db)
    await interaction.user.send(embed=create_embed(
        "👁️ WATCHER LOG", "State your findings, Citizen."
    ))
    await interaction.response.send_message("🛰️ Check DMs.", ephemeral=True)

# --- EVENTS ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = str(message.author.id)

    # Interview
    if isinstance(message.channel, discord.DMChannel) and uid in bot.db["interviews"]:
        state = bot.db["interviews"][uid]
        if state["step"] == 1:
            state["step"] = 2
            await message.author.send("Question 2: Who is Jessica's father?")
        elif state["step"] == 2:
            if "jeff" in message.content.lower():
                bot.db["interviews"].pop(uid)
                await message.author.send("✅ Access granted.")
        save_data(bot.db)
        return

    # AI mention
    if bot.user and bot.user.mentioned_in(message):
        try:
            async with message.channel.typing():
                prompt = f"{LORE_CONTEXT}\nUser says: {message.content[:500]}"
                text = await run_gemini(prompt)
                await message.reply(text[:1900])
        except Exception:
            await message.reply("🛰️ *[SIGNAL LOST BEYOND THE ICE WALL]*")
            await log_error(traceback.format_exc())

try:
    bot.run(TOKEN)
except Exception as e:
    print("Critical error:", e)
