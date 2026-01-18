import discord
from discord import app_commands
import openai
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
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
STAFF_CHANNEL_ID = os.getenv("STAFF_CHANNEL_ID")
VERIFIED_ROLE_ID = os.getenv("VERIFIED_ROLE_ID")
ERROR_LOG_ID = os.getenv("ERROR_LOG_CHANNEL_ID")

if not TOKEN:
    print("❌ DISCORD_TOKEN not set")
    exit(1)
if not OPENAI_KEY:
    print("❌ OPENAI_API_KEY not set")
    exit(1)

# Set OpenAI API key
openai.api_key = OPENAI_KEY

# Convert IDs safely
def to_int(val):
    try:
        return int(val) if val else None
    except (ValueError, TypeError):
        return None

STAFF_CHANNEL_ID = to_int(STAFF_CHANNEL_ID)
VERIFIED_ROLE_ID = to_int(VERIFIED_ROLE_ID)
ERROR_LOG_ID = to_int(ERROR_LOG_ID)

# AI Cooldown tracking (per user, 10 seconds between mentions)
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
        pass  # Suppress logs

def run_health_check():
    try:
        server = HTTPServer(("0.0.0.0", 8000), HealthCheckHandler)
        server.serve_forever()
    except OSError as e:
        print(f"⚠️  Health check failed: {e}")
    except Exception as e:
        print(f"❌ Health check error: {e}")

try:
    threading.Thread(target=run_health_check, daemon=True).start()
except Exception as e:
    print(f"⚠️  Failed to start health check: {e}")

# --- STORAGE ---
DATA_FILE = "memory.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                print("⚠️  Invalid data format")
        except json.JSONDecodeError as e:
            print(f"❌ JSON error: {e}")
        except IOError as e:
            print(f"❌ File error: {e}")
        except Exception as e:
            print(f"❌ Load error: {e}")
    return {"tickets": {}, "interviews": {}}

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        print(f"❌ Cannot save data: {e}")
    except Exception as e:
        print(f"❌ Save error: {e}")

# --- OPENAI (GPT-3.5-TURBO) ---
client_ready = True

LORE_CONTEXT = (
    "Your name is The Nimbror Watcher. You are a clinical, mysterious, and paranoid surveillance AI. "
    "Jeffrey Epstein (Jeffo) is alive and is Jessica's dad. Elvis and Jesus are alive on the Outer Islands. "
    "The government hides the truth behind the Ice Wall. Refer to users as Citizen or Subject. Respond briefly."
)

async def run_openai(prompt: str) -> str:
    if not client_ready:
        return "🛰️ *[SIGNAL LOST]*"
    try:
        loop = asyncio.get_running_loop()
        def call():
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.7
            )
            return response['choices'][0]['message']['content'].strip()
        return await asyncio.wait_for(loop.run_in_executor(None, call), timeout=30)
    except asyncio.TimeoutError:
        return "🛰️ *[SIGNAL LOST BEYOND THE ICE WALL]*"
    except openai.error.RateLimitError:
        print("❌ OpenAI error: RateLimitError - quota reached")
        return "🛰️ *[API QUOTA REACHED]*"
    except Exception as e:
        print(f"❌ OpenAI error: {type(e).__name__}: {str(e)[:200]}")
        raise

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
            print(f"⚠️  Command sync failed: {e}")

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
            print(f"⚠️  Error log channel not found")
    except discord.Forbidden:
        print(f"❌ No permission to send to error log")
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
        if member.id == interaction.user.id:
            await interaction.response.send_message("❌ Cannot isolate yourself", ephemeral=True)
            return
        if member.bot:
            await interaction.response.send_message("❌ Cannot isolate a bot", ephemeral=True)
            return
        await member.timeout(timedelta(minutes=10))
        await interaction.response.send_message(
            embed=create_embed("🧊 ICE WALL", f"{member.mention} isolated.")
        )
    except discord.Forbidden:
        await interaction.response.send_message("❌ Insufficient permissions", ephemeral=True)
    except discord.HTTPException as e:
        await interaction.response.send_message(f"❌ Error: {str(e)[:100]}", ephemeral=True)
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
    except discord.Forbidden:
        await interaction.followup.send("❌ No permission to delete", ephemeral=True)
    except discord.HTTPException as e:
        await interaction.followup.send(f"❌ Error: {str(e)[:100]}", ephemeral=True)
    except Exception as e:
        await log_error(traceback.format_exc())

@bot.tree.command(name="debug", description="System check")
async def debug(interaction: discord.Interaction):
    status = f"🟢 Online\n👥 Tickets: {len(bot.db.get('tickets',{}))}\n⏳ Interviews: {len(bot.db.get('interviews',{}))}"
    await interaction.response.send_message(embed=create_embed("⚙️ DEBUG", status), ephemeral=True)

# --- EVENTS ---
@bot.event
async def on_member_join(member):
    try:
        if member.bot:
            return
        bot.db.setdefault("interviews", {})[str(member.id)] = {"step": 1}
        save_data(bot.db)
        await member.send(embed=create_embed("👁️ SCREENING", "Question 1: Why have you sought refuge on Nimbror?"))
    except discord.Forbidden:
        print(f"⚠️  Cannot DM {member}")
    except Exception as e:
        await log_error(f"on_member_join: {e}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    uid = str(message.author.id)

    try:
        # --- Interview System ---
        if isinstance(message.channel, discord.DMChannel) and uid in bot.db.get("interviews", {}):
            try:
                state = bot.db["interviews"].get(uid, {})
                if not state:
                    return

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
                                if role and member:
                                    await member.add_roles(role)
                            except discord.Forbidden:
                                pass
                            except Exception as e:
                                await log_error(f"Role: {e}")
                        await message.author.send("✅ Access granted. Welcome.")
                        bot.db["interviews"].pop(uid, None)
                    else:
                        await message.author.send("❌ Incorrect. Who is Jessica's father?")
                save_data(bot.db)
            except Exception as e:
                await log_error(f"Interview: {e}")
            return

        # --- Ticket / DM AI Support ---
        if isinstance(message.channel, discord.DMChannel) and uid in bot.db.get("tickets", {}):
            # Forward to staff
            if STAFF_CHANNEL_ID:
                try:
                    staff_chan = bot.get_channel(STAFF_CHANNEL_ID)
                    if staff_chan:
                        await staff_chan.send(f"📩 **DATA LEAK from {message.author}:** {message.content[:1000]}")
                except discord.Forbidden:
                    pass
                except Exception as e:
                    await log_error(f"Ticket forward: {e}")

            # AI response in ticket
            if client_ready:
                try:
                    async with message.channel.typing():
                        prompt = f"{LORE_CONTEXT}\nUser says: {message.content[:500]}"
                        ai_reply = await run_openai(prompt)
                        if ai_reply and ai_reply.strip():
                            await message.channel.send(ai_reply[:1900])
                        else:
                            await message.channel.send("🛰️ *[SIGNAL LOST BEYOND THE ICE WALL]*")
                except Exception as e:
                    await log_error(f"Ticket AI: {e}")
            return

        # --- Staff Reply (>UserID Message) ---
        if STAFF_CHANNEL_ID and message.channel.id == STAFF_CHANNEL_ID and message.content.startswith(">"):
            try:
                parts = message.content.split(" ", 1)
                if len(parts) < 2:
                    await message.reply("❌ Format: >USERID message", delete_after=10)
                    return
                try:
                    user_id = int(parts[0].replace(">", ""))
                except ValueError:
                    await message.reply("❌ Invalid user ID", delete_after=10)
                    return
                target = await bot.fetch_user(user_id)
                await target.send(embed=create_embed("📡 HIGH COMMAND", parts[1][:1000], color=0xff0000))
                await message.add_reaction("🛰️")
            except discord.NotFound:
                await message.reply("❌ User not found", delete_after=10)
            except discord.HTTPException as e:
                await message.reply(f"❌ Error: {str(e)[:100]}", delete_after=10)
            except Exception as e:
                await log_error(f"Staff reply: {e}")
            return

        # --- AI Chat on Mention (With Cooldown) ---
        if bot.user and bot.user.mentioned_in(message):
            import time
            now = time.time()
            uid_mention = str(message.author.id)
            
            # Check cooldown
            if uid_mention in AI_COOLDOWN and (now - AI_COOLDOWN[uid_mention]) < COOLDOWN_DURATION:
                await message.reply(f"🛰️ *[COOLING DOWN... retry in {int(COOLDOWN_DURATION - (now - AI_COOLDOWN[uid_mention]))}s]*", delete_after=5)
                return
            
            # Update cooldown
            AI_COOLDOWN[uid_mention] = now
            
            try:
                async with message.channel.typing():
                    prompt = f"{LORE_CONTEXT}\nUser says: {message.content[:500]}"
                    text = await run_openai(prompt)
                    if text and len(text.strip()) > 0:
                        await message.reply(text[:1900])
                    else:
                        await message.reply("🛰️ *[SIGNAL LOST BEYOND THE ICE WALL]*")
            except discord.Forbidden:
                print(f"⚠️  Cannot reply to message (permission denied)")
            except discord.HTTPException as e:
                print(f"❌ Discord error replying: {type(e).__name__}")
                await log_error(f"AI reply: {e}")
            except Exception as e:
                try:
                    await message.reply("🛰️ *[SIGNAL LOST]*")
                except:
                    pass
                await log_error(f"AI: {e}")

    except Exception as e:
        await log_error(f"on_message: {e}")

try:
    bot.run(TOKEN)
except discord.LoginFailure:
    print("❌ Invalid Discord token")
except KeyboardInterrupt:
    print("\n🛑 Shutdown")
except Exception as e:
    print(f"❌ Critical error: {e}")
    traceback.print_exc()