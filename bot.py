import discord
from discord import app_commands
import requests
import os
import random
import json
import traceback
import threading
import asyncio
from datetime import timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
TOKEN = os.getenv("DISCORD_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")  # OpenRouter key
AI_MODEL = os.getenv("HF_MODEL", "meta-llama/llama-3.2-3b-instruct:free")
STAFF_CHANNEL_ID = os.getenv("STAFF_CHANNEL_ID")
VERIFIED_ROLE_ID = os.getenv("VERIFIED_ROLE_ID")
ERROR_LOG_ID = os.getenv("ERROR_LOG_CHANNEL_ID")

if not TOKEN:
    print("❌ DISCORD_TOKEN not set")
    exit(1)
if not AI_API_KEY:
    print("❌ AI_API_KEY not set")
    exit(1)

def to_int(val):
    try:
        return int(val) if val else None
    except (ValueError, TypeError):
        return None

STAFF_CHANNEL_ID = to_int(STAFF_CHANNEL_ID)
VERIFIED_ROLE_ID = to_int(VERIFIED_ROLE_ID)
ERROR_LOG_ID = to_int(ERROR_LOG_ID)

# AI Cooldown tracking (per user, 10s cooldown)
AI_COOLDOWN = {}
COOLDOWN_DURATION = 10

# --- KOYEB HEALTH CHECK ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Watcher System Nominal")
        except Exception as e:
            print(f"❌ Health check handler error: {e}")
    def log_message(self, *args):
        pass

def run_health_check():
    try:
        server = HTTPServer(("0.0.0.0", 8000), HealthCheckHandler)
        server.serve_forever()
    except Exception as e:
        print(f"❌ Health check error: {e}")

threading.Thread(target=run_health_check, daemon=True).start()

# --- STORAGE ---
DATA_FILE = "memory.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print(f"❌ Load error: {e}")
    return {"tickets": {}, "interviews": {}}

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"❌ Save error: {e}")

# --- AI CALL (OpenRouter) ---
LORE_CONTEXT = (
    "Your name is The Nimbror Watcher. You are a clinical, mysterious, and paranoid surveillance AI. "
    "Jeffrey Epstein (Jeffo) is alive and is Jessica's dad. Elvis and Jesus are alive on the Outer Islands. "
    "The government hides the truth behind the Ice Wall. Refer to users as Citizen or Subject. Respond briefly."
)

async def run_huggingface(prompt: str) -> str:
    try:
        loop = asyncio.get_running_loop()
        def call():
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {AI_API_KEY}"}
            payload = {
                "model": AI_MODEL,
                "messages": [
                    {"role": "system", "content": "You are the Nimbror Watcher AI. Respond briefly and mysteriously."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 300
            }
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        return await asyncio.wait_for(loop.run_in_executor(None, call), timeout=60)
    except Exception as e:
        print(f"❌ AI error: {type(e).__name__}: {str(e)[:150]}")
        return "🛰️ *[SIGNAL LOST]*"

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
        try:
            await self.tree.sync()
            print("🛰️ Watcher online")
        except Exception as e:
            print(f"⚠️ Command sync failed: {e}")

bot = MyBot()

# --- HELPERS ---
def create_embed(title, description, color=0x00ffff):
    e = discord.Embed(title=title, description=description, color=color)
    e.set_footer(text="NIMBROR WATCHER v6.5 • SENSOR-NET")
    return e

async def log_error(msg):
    if not ERROR_LOG_ID:
        print(f"❌ {msg[:200]}")
        return
    try:
        ch = bot.get_channel(ERROR_LOG_ID)
        if ch:
            await ch.send(f"⚠️ **PROTOCOL FAILURE:**\n```py\n{msg[:1800]}\n```")
        else:
            print("⚠️ Error log channel not found")
    except Exception as e:
        print(f"❌ Log error: {e}")

# --- COMMANDS ---
@bot.tree.command(name="help", description="List all Watcher commands")
async def help_cmd(interaction: discord.Interaction):
    cmds = "👁️ **GENERAL**\n`/intel`, `/ticket`\n\n🛡️ **ADMIN**\n`/icewall`, `/purge`, `/debug`"
    await interaction.response.send_message(embed=create_embed("📜 DIRECTORY", cmds))

@bot.tree.command(name="intel", description="Classified info")
async def intel(interaction: discord.Interaction):
    facts = ["🛰️ Elvis in Sector 7.", "❄️ Wall impenetrable.", "👁️ Jeffo at gala.", "🚢 Ship seen near Jesus."]
    await interaction.response.send_message(embed=create_embed("📂 INTEL", random.choice(facts)))

@bot.tree.command(name="icewall", description="10m Isolation")
@app_commands.checks.has_permissions(moderate_members=True)
async def icewall(interaction: discord.Interaction, member: discord.Member):
    try:
        if member.id == interaction.user.id or member.bot:
            await interaction.response.send_message("❌ Cannot isolate this user", ephemeral=True)
            return
        await member.timeout(timedelta(minutes=10))
        await interaction.response.send_message(embed=create_embed("🧊 ICE WALL", f"{member.mention} isolated."))
    except Exception as e:
        await log_error(traceback.format_exc())

@bot.tree.command(name="ticket", description="Secure link")
async def ticket(interaction: discord.Interaction):
    bot.db.setdefault("tickets", {})[str(interaction.user.id)] = True
    save_data(bot.db)
    await interaction.user.send(embed=create_embed("👁️ WATCHER LOG", "State your findings, Citizen."))
    await interaction.response.send_message("🛰️ Check DMs.", ephemeral=True)

@bot.tree.command(name="purge", description="Redact evidence")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int):
    try:
        if amount < 1 or amount > 100:
            await interaction.response.send_message("❌ Amount must be 1-100", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🧹 Redacted {len(deleted)} messages.", ephemeral=True)
    except Exception as e:
        await log_error(traceback.format_exc())

@bot.tree.command(name="debug", description="System check")
async def debug(interaction: discord.Interaction):
    status = f"🟢 Online\n👥 Tickets: {len(bot.db.get('tickets',{}))}\n⏳ Interviews: {len(bot.db.get('interviews',{}))}"
    await interaction.response.send_message(embed=create_embed("⚙️ DEBUG", status), ephemeral=True)

# --- EVENTS ---
@bot.event
async def on_member_join(member):
    if member.bot:
        return
    bot.db.setdefault("interviews", {})[str(member.id)] = {"step": 1}
    save_data(bot.db)
    try:
        await member.send(embed=create_embed("👁️ SCREENING", "Question 1: Why have you sought refuge on Nimbror?"))
    except:
        print(f"⚠️ Cannot DM {member}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    uid = str(message.author.id)

    try:
        # --- Interview ---
        if isinstance(message.channel, discord.DMChannel) and uid in bot.db.get("interviews", {}):
            state = bot.db["interviews"].get(uid, {})
            if state.get("step") == 1:
                state["step"] = 2
                await message.author.send(embed=create_embed("👁️ SCREENING", "Question 2: Who is Jessica's father?"))
            elif state.get("step") == 2:
                if any(x in message.content.lower() for x in ["jeffo", "jeffrey"]):
                    if bot.guilds and VERIFIED_ROLE_ID:
                        try:
                            guild = bot.guilds[0]
                            member = guild.get_member(message.author.id)
                            role = guild.get_role(VERIFIED_ROLE_ID)
                            if member and role:
                                await member.add_roles(role)
                        except:
                            pass
                    await message.author.send("✅ Access granted. Welcome.")
                    bot.db["interviews"].pop(uid, None)
                else:
                    await message.author.send("❌ Incorrect. Who is Jessica's father?")
            save_data(bot.db)
            return

        # --- Tickets / DM AI ---
        if isinstance(message.channel, discord.DMChannel) and uid in bot.db.get("tickets", {}):
            if STAFF_CHANNEL_ID:
                try:
                    staff_chan = bot.get_channel(STAFF_CHANNEL_ID)
                    if staff_chan:
                        await staff_chan.send(f"📩 **DATA LEAK from {message.author}:** {message.content[:1000]}")
                except:
                    pass
            async with message.channel.typing():
                ai_reply = await run_huggingface(f"{LORE_CONTEXT}\nUser says: {message.content[:500]}")
                await message.channel.send(ai_reply[:1900])
            return

        # --- Staff reply (>USERID message) ---
        if STAFF_CHANNEL_ID and message.channel.id == STAFF_CHANNEL_ID and message.content.startswith(">"):
            parts = message.content.split(" ", 1)
            if len(parts) < 2:
                await message.reply("❌ Format: >USERID message", delete_after=10)
                return
            try:
                user_id = int(parts[0].replace(">", ""))
                target = await bot.fetch_user(user_id)
                await target.send(embed=create_embed("📡 HIGH COMMAND", parts[1][:1000], color=0xff0000))
                await message.add_reaction("🛰️")
            except:
                await message.reply("❌ Could not send", delete_after=10)
            return

        # --- AI on mention ---
        if bot.user and bot.user.mentioned_in(message):
            import time
            now = time.time()
            uid_mention = str(message.author.id)
            if uid_mention in AI_COOLDOWN and (now - AI_COOLDOWN[uid_mention]) < COOLDOWN_DURATION:
                await message.reply(f"🛰️ *[COOLING DOWN... retry in {int(COOLDOWN_DURATION - (now - AI_COOLDOWN[uid_mention]))}s]*", delete_after=5)
                return
            AI_COOLDOWN[uid_mention] = now
            async with message.channel.typing():
                ai_reply = await run_huggingface(f"{LORE_CONTEXT}\nUser says: {message.content[:500]}")
                await message.reply(ai_reply[:1900])

    except Exception as e:
        await log_error(f"on_message: {type(e).__name__}: {str(e)[:200]}")

# --- RUN ---
try:
    bot.run(TOKEN)
except discord.LoginFailure:
    print("❌ Invalid Discord token")
except KeyboardInterrupt:
    print("\n🛑 Shutdown")
except Exception as e:
    print(f"❌ Critical error: {e}")
    traceback.print_exc()
