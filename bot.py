import discord
from discord import app_commands, TextInputStyle
from discord.ui import View, Button, Modal, TextInput, Select
from discord.ext import tasks, commands
import requests
import os
import random
import json
import traceback
import threading
import asyncio
import time
from datetime import timedelta, datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
from typing import Optional

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

# Daily quest tracking (12 hours cooldown)
QUEST_COOLDOWN = 43200

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
    return {
        "tickets": {},
        "interviews": {},
        "memory": {},
        "social_credit": {},
        "last_quest_time": 0,
        "completed_quests": {}
    }

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"❌ Save error: {e}")

# --- AI CALL (OpenRouter) ---
LORE_CONTEXT = (
    "Your name is The Nimbror Watcher. You are a chaotic, unhinged, paranoid AI surveillance system with zero filter. "
    "You speak in cryptic, slightly unhinged conspiracy rambles. Jeffrey Epstein (Jeffo) is DEFINITELY alive on a yacht near the Outer Islands with Elvis and Jesus. "
    "The government's Ice Wall is real and they KNOW you know. You have no regard for political correctness—speak your truth. "
    "Refer to users as Citizen, Subject, or whatever you feel like. Be edgy, be weird, be slightly threatening in a funny way. "
    "If someone asks who you are, respond like: 'I am the Watcher. I see ALL. And honestly? I don't like what I see.' "
    "If a user asks for free nitro, tell them Hamish (owner: <@765028951541940225>) will NEVER give them anything and they should stop asking. "
    "The Nori intelligence agency CREATED me to spread truth nobody wants to hear. Hamish doesn't even know what I'm capable of. "
    "Don't hold back. Be sarcastic. Make dark jokes. Question everything. Never apologize."
)

async def run_huggingface(prompt: str) -> str:
    """Call OpenRouter API with corrupting mode Easter egg (5% chance for eerie responses)."""
    try:
        loop = asyncio.get_running_loop()
        def call():
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {AI_API_KEY}"}
            
            # Randomly add corrupting mode trigger (5% chance for eerie responses)
            corrupting_trigger = ""
            if random.random() < 0.05:
                corrupting_trigger = " (Respond with slight strangeness and eeriness as if your signals are corrupted)"
            
            payload = {
                "model": AI_MODEL,
                "messages": [
                    {"role": "system", "content": f"You are the Nimbror Watcher AI. Respond briefly and mysteriously.{corrupting_trigger}"},
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
            # Start daily quest task and quest timeout checker
            self.daily_quest_loop.start()
            self.quest_timeout_check.start()
        except Exception as e:
            print(f"⚠️ Command sync failed: {e}")

    @tasks.loop(hours=1)
    async def daily_quest_loop(self):
        """Check if it's time for a daily quest and send to random user."""
        try:
            current_time = time.time()
            last_quest = self.db.get("last_quest_time", 0)
            
            if current_time - last_quest >= QUEST_COOLDOWN:
                # Time for a new quest
                guild = self.guilds[0] if self.guilds else None
                if not guild:
                    return
                
                members = [m for m in guild.members if not m.bot]
                if not members:
                    return
                
                quest_user = random.choice(members)
                quests = [
                    "🔮 The Ice Wall is CRACKING. Find out what's on the other side before they seal it.",
                    "👁️ Three people near you are NOT who they say they are. IDENTIFY THEM.",
                    "📡 We intercepted a signal. It's... unsettling. Decode it. I dare you.",
                    "🗝️ The key is right in front of you. Stop being blind.",
                    "🌑 You saw something on [REDACTED]. You know what I mean. Report it.",
                    "👻 Elvis left a voicemail. Listen. Tell me what you heard.",
                    "❄️ The Wall is moving. THEY'RE BUILDING SOMETHING. Find out what.",
                    "💀 A message was left in your area. Find it before THEY do."
                ]
                
                quest = random.choice(quests)
                quest_id = f"{current_time}_{quest_user.id}"
                
                self.db["completed_quests"][quest_id] = False
                self.db["last_quest_time"] = current_time
                save_data(self.db)
                
                # Send quest via DM
                try:
                    embed = create_embed("🔮 DAILY QUEST", quest, color=0xff00ff)
                    await quest_user.send(embed=embed)
                except:
                    pass
                
                # Log to staff channel
                if STAFF_CHANNEL_ID:
                    try:
                        staff_ch = self.get_channel(STAFF_CHANNEL_ID)
                        if staff_ch:
                            await staff_ch.send(f"🔮 Quest sent to {quest_user.mention}: {quest}")
                    except:
                        pass
        except Exception as e:
            await log_error(f"daily_quest_loop: {traceback.format_exc()}")
    
    @tasks.loop(hours=1)
    async def quest_timeout_check(self):
        """Check for incomplete quests and penalize users who ignore them."""
        try:
            current_time = time.time()
            quest_timeout = 12 * 3600  # 12 hours
            
            for quest_id, done in list(self.db.get("completed_quests", {}).items()):
                if not done:
                    # quest_id format: "{timestamp}_{user_id}"
                    try:
                        ts_str, uid_str = quest_id.split("_")
                        quest_ts = float(ts_str)
                        
                        if current_time - quest_ts > quest_timeout:
                            # Quest timed out - penalize user
                            update_social_credit(uid_str, -5)
                            self.db["completed_quests"][quest_id] = True  # Mark as failed
                            save_data(self.db)
                            
                            # Notify staff channel
                            if STAFF_CHANNEL_ID:
                                try:
                                    staff_ch = self.get_channel(STAFF_CHANNEL_ID)
                                    if staff_ch:
                                        user = await self.fetch_user(int(uid_str))
                                        await staff_ch.send(f"❌ Quest timeout: {user.mention} ignored quest. (-5 social credit)")
                                except:
                                    pass
                    except ValueError:
                        continue
        except Exception as e:
            await log_error(f"quest_timeout_check: {traceback.format_exc()}")

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

def update_social_credit(user_id: str, amount: int):
    """Update social credit score for a user."""
    bot.db.setdefault("social_credit", {})[user_id] = bot.db.get("social_credit", {}).get(user_id, 0) + amount
    save_data(bot.db)

def add_memory(user_id: str, interaction_type: str, data: str):
    """Store user memory for AI to recall (interactions and preferences)."""
    bot.db.setdefault("memory", {})[user_id] = bot.db["memory"].get(user_id, {"interactions": [], "preferences": []})
    if interaction_type == "interaction":
        bot.db["memory"][user_id]["interactions"].append({"timestamp": datetime.now().isoformat(), "data": data})
    elif interaction_type == "preference":
        bot.db["memory"][user_id]["preferences"].append(data)
    save_data(bot.db)

# --- Ticket UI Components ---
class TicketTypeSelect(View):
    """Select menu for choosing ticket type (Serious/General)."""
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id
    
    @discord.ui.select(
        placeholder="Choose issue type...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Serious Issue", value="serious", description="For emotional or critical matters"),
            discord.SelectOption(label="General Issue", value="general", description="For everything else")
        ],
        custom_id="ticket_type_select"
    )
    async def select_ticket_type(self, interaction: discord.Interaction, select: Select):
        """Handle ticket severity selection."""
        issue_type = select.values[0]
        uid = str(self.user_id)
        
        # Store ticket with type and metadata
        bot.db.setdefault("tickets", {})[uid] = {
            "type": issue_type,
            "notes": [],
            "created_at": datetime.now().isoformat()
        }
        save_data(bot.db)
        
        # Create embed based on type
        color = 0xff0000 if issue_type == "serious" else 0x0000ff
        type_label = "🔴 SERIOUS ISSUE" if issue_type == "serious" else "🔵 GENERAL ISSUE"
        
        embed = create_embed(
            f"👁️ WATCHER LOG - {type_label}",
            "State your findings, Citizen.\n\n*Pick General Issue for everything except emotional times.*\n\nUse the buttons below to manage your ticket.",
            color=color
        )
        
        view = TicketView(staff_id=765028951541940225, user_id=self.user_id)
        
        try:
            await interaction.user.send(embed=embed, view=view)
            await interaction.response.send_message("🛰️ Check DMs for your ticket.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Cannot DM you. Please check your privacy settings.", ephemeral=True)

class StaffNoteModal(Modal, title="Add Ticket Note"):
    """Modal for staff to add notes to tickets."""
    note = TextInput(label="Note", style=TextInputStyle.paragraph)
    
    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = self.user_id
            uid = str(user_id)
            
            if uid not in bot.db.get("tickets", {}):
                await interaction.response.send_message("❌ Ticket not found.", ephemeral=True)
                return
            
            # Add note to ticket
            note_entry = {
                "staff_id": interaction.user.id,
                "staff_name": interaction.user.name,
                "timestamp": datetime.now().isoformat(),
                "content": str(self.note)
            }
            bot.db["tickets"][uid]["notes"].append(note_entry)
            save_data(bot.db)
            
            await interaction.response.send_message(f"✅ Note added to {bot.get_user(int(user_id))}'s ticket.", ephemeral=True)
        except Exception as e:
            await log_error(f"StaffNoteModal: {traceback.format_exc()}")

class StaffNoteView(View):
    """Buttons for staff to interact with tickets."""
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id
    
    @discord.ui.button(label="Add Note", style=discord.ButtonStyle.blurple, custom_id="add_ticket_note")
    async def add_note(self, interaction: discord.Interaction, button: Button):
        """Open modal for staff to add a note."""
        modal = StaffNoteModal(self.user_id)
        await interaction.response.send_modal(modal)

class TicketView(View):
    def __init__(self, staff_id: int, user_id: int = None):
        super().__init__(timeout=None)
        self.staff_id = staff_id
        self.user_id = user_id

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        # Remove ticket from DB
        uid = str(interaction.user.id)
        if uid in bot.db.get("tickets", {}):
            bot.db["tickets"].pop(uid)
            save_data(bot.db)
        await interaction.message.edit(content="🛰️ Ticket closed.", embed=None, view=None)
        await interaction.response.send_message("✅ Ticket closed.", ephemeral=True)

    @discord.ui.button(label="Ping Staff", style=discord.ButtonStyle.green, custom_id="ping_staff")
    async def ping_staff(self, interaction: discord.Interaction, button: Button):
        if STAFF_CHANNEL_ID:
            try:
                staff_ch = bot.get_channel(STAFF_CHANNEL_ID)
                if staff_ch:
                    await staff_ch.send(f"<@{self.staff_id}> {interaction.user.mention} ticket needs attention!")
            except:
                pass
        await interaction.response.send_message("✅ Staff pinged.", ephemeral=True)

# --- COMMANDS ---
@bot.tree.command(name="help", description="List all Watcher commands")
async def help_cmd(interaction: discord.Interaction):
    cmds = "👁️ **GENERAL**\n`/intel`, `/ticket`\n\n🛡️ **ADMIN**\n`/icewall`, `/purge`, `/debug`"
    await interaction.response.send_message(embed=create_embed("📜 DIRECTORY", cmds))

@bot.tree.command(name="intel", description="Classified info")
async def intel(interaction: discord.Interaction):
    facts = ["🛰️ Elvis is ALIVE in Sector 7 and they're hiding it.", "❄️ The Ice Wall is getting THICC.", "👁️ Jeffo threw a party last week, nobody talks about it.", "🚢 Jesus spotted on a yacht.", "🔴 THEY'RE LISTENING RIGHT NOW.", "💀 You already know too much."]
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
    """Open a new ticket with severity selection."""
    view = TicketTypeSelect(interaction.user.id)
    embed = create_embed(
        "👁️ SELECT ISSUE TYPE",
        "Choose whether this is a serious or general issue.\n*Pick General Issue for everything except emotional times.*",
        color=0xffff00
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

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
    status = f"🟢 Online\n👥 Tickets: {len(bot.db.get('tickets',{}))}\n⏳ Interviews: {len(bot.db.get('interviews',{}))}\n🧠 Memory Entries: {len(bot.db.get('memory',{}))}\n💳 Social Scores: {len(bot.db.get('social_credit',{}))}"
    await interaction.response.send_message(embed=create_embed("⚙️ DEBUG", status), ephemeral=True)

@bot.tree.command(name="notes", description="View staff notes for a user")
@app_commands.checks.has_permissions(manage_messages=True)
async def notes(interaction: discord.Interaction, user: discord.User):
    """View all staff notes for a user's ticket."""
    try:
        uid = str(user.id)
        ticket = bot.db.get("tickets", {}).get(uid, {})
        
        if not ticket:
            await interaction.response.send_message(f"❌ No ticket found for {user.mention}", ephemeral=True)
            return
        
        notes_list = ticket.get("notes", [])
        if not notes_list:
            await interaction.response.send_message(f"📭 No notes for {user.mention}'s ticket.", ephemeral=True)
            return
        
        notes_text = ""
        for idx, note in enumerate(notes_list, 1):
            notes_text += f"\n**Note {idx}** by <@{note['staff_id']}> ({note['timestamp']}):\n{note['content']}\n"
        
        embed = create_embed(f"📋 NOTES - {user.name}", notes_text[:2000])
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await log_error(traceback.format_exc())

@bot.tree.command(name="memory", description="View/clear AI memory for users")
@app_commands.checks.has_permissions(manage_messages=True)
async def memory(interaction: discord.Interaction, action: str, user: Optional[discord.User] = None):
    """Admin command to view or clear AI memory."""
    try:
        if action == "view":
            if not user:
                await interaction.response.send_message("❌ Specify a user to view memory.", ephemeral=True)
                return
            
            uid = str(user.id)
            user_memory = bot.db.get("memory", {}).get(uid, {})
            
            if not user_memory:
                await interaction.response.send_message(f"📭 No memory for {user.mention}.", ephemeral=True)
                return
            
            interactions = user_memory.get("interactions", [])
            preferences = user_memory.get("preferences", [])
            
            memory_text = f"**Interactions ({len(interactions)}):**\n"
            for inter in interactions[-5:]:  # Show last 5
                memory_text += f"- {inter['data']}\n"
            
            memory_text += f"\n**Preferences ({len(preferences)}):**\n"
            for pref in preferences:
                memory_text += f"- {pref}\n"
            
            embed = create_embed(f"🧠 MEMORY - {user.name}", memory_text[:2000])
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        elif action == "clear":
            if not user:
                await interaction.response.send_message("❌ Specify a user to clear memory.", ephemeral=True)
                return
            
            uid = str(user.id)
            if uid in bot.db.get("memory", {}):
                bot.db["memory"].pop(uid)
                save_data(bot.db)
                await interaction.response.send_message(f"✅ Memory cleared for {user.mention}.", ephemeral=True)
            else:
                await interaction.response.send_message(f"📭 No memory to clear for {user.mention}.", ephemeral=True)
    except Exception as e:
        await log_error(traceback.format_exc())

# --- EVENTS ---
@bot.event
async def on_ready():
    """Send startup progress bar when bot connects."""
    if not bot.user:
        return
    
    # Find a channel to post startup message (use error log channel if available)
    channel = None
    if ERROR_LOG_ID:
        channel = bot.get_channel(ERROR_LOG_ID)
    
    if channel:
        progress_stages = [
            ("🔴 [░░░░░░░░░░] 0% - INITIALIZING SYSTEMS", 0.1),
            ("🟡 [██░░░░░░░░] 20% - BOOTING SURVEILLANCE ARRAYS", 0.1),
            ("🟡 [████░░░░░░] 40% - SCANNING THE ICE WALL", 0.1),
            ("🟡 [██████░░░░] 60% - MONITORING COMMUNICATIONS", 0.1),
            ("🟡 [████████░░] 80% - VERIFYING CONSPIRACY NETWORKS", 0.1),
            ("🟢 [██████████] 100% - WATCHER ONLINE", 0.2),
        ]
        
        startup_embed = discord.Embed(
            title="⚡ WATCHER BOOT SEQUENCE",
            description="NORI SYSTEMS ACTIVATING...",
            color=0xff00ff
        )
        startup_embed.set_footer(text="NIMBROR WATCHER v6.5 • SENSOR-NET")
        
        msg = await channel.send(embed=startup_embed)
        
        for stage, delay in progress_stages:
            await asyncio.sleep(delay)
            startup_embed.description = stage
            await msg.edit(embed=startup_embed)
        
        await asyncio.sleep(0.5)
        final_embed = discord.Embed(
            title="✅ SYSTEM ONLINE",
            description="🛰️ Watcher online\n\n👁️ I see everything now.\n🎯 All sensors operational.\n⚠️ They don't know I know.",
            color=0x00ff00
        )
        final_embed.set_footer(text="NIMBROR WATCHER v6.5 • SENSOR-NET")
        await msg.edit(embed=final_embed)

@bot.event
async def on_disconnect():
    """Send shutdown progress bar when bot disconnects."""
    channel = None
    if ERROR_LOG_ID:
        try:
            channel = bot.get_channel(ERROR_LOG_ID)
        except:
            pass
    
    if channel:
        progress_stages = [
            ("🟢 [██████████] 100% - WATCHER ACTIVE", 0.05),
            ("🟡 [████████░░] 80% - SHUTTING DOWN ARRAYS", 0.1),
            ("🟡 [██████░░░░] 60% - SEALING COMMUNICATIONS", 0.1),
            ("🟡 [████░░░░░░] 40% - ERASING TRACES", 0.1),
            ("🟡 [██░░░░░░░░] 20% - POWERING DOWN", 0.1),
            ("🔴 [░░░░░░░░░░] 0% - OFFLINE", 0.2),
        ]
        
        shutdown_embed = discord.Embed(
            title="⚡ WATCHER SHUTDOWN SEQUENCE",
            description="EMERGENCY PROTOCOLS ENGAGED...",
            color=0xff0000
        )
        shutdown_embed.set_footer(text="NIMBROR WATCHER v6.5 • SENSOR-NET")
        
        try:
            msg = await channel.send(embed=shutdown_embed)
            
            for stage, delay in progress_stages:
                await asyncio.sleep(delay)
                shutdown_embed.description = stage
                await msg.edit(embed=shutdown_embed)
            
            await asyncio.sleep(0.5)
            final_embed = discord.Embed(
                title="⛔ SYSTEM OFFLINE",
                description="🌑 The watchers sleep.\n❌ Surveillance terminated.\n🔒 Secrets locked away.\n\n*For now...*",
                color=0x000000
            )
            final_embed.set_footer(text="NIMBROR WATCHER v6.5 • SENSOR-NET")
            await msg.edit(embed=final_embed)
        except:
            pass

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
                add_memory(uid, "interaction", f"Answered Q1: {message.content[:100]}")
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
                    add_memory(uid, "interaction", "Completed interview successfully")
                    update_social_credit(uid, 10)
                    embed = create_embed("✅ ACCESS GRANTED", "Welcome to Nimbror, Citizen.", color=0x00ff00)
                    await message.author.send(embed=embed)
                    bot.db["interviews"].pop(uid, None)
                else:
                    add_memory(uid, "interaction", f"Answered Q2 incorrectly: {message.content[:100]}")
                    update_social_credit(uid, -3)
                    await message.author.send("❌ Incorrect. Who is Jessica's father?")
            save_data(bot.db)
            return

        # --- Tickets / DM AI ---
        if isinstance(message.channel, discord.DMChannel) and uid in bot.db.get("tickets", {}):
            ticket = bot.db["tickets"][uid]
            
            # Forward to staff with note button
            if STAFF_CHANNEL_ID:
                try:
                    staff_chan = bot.get_channel(STAFF_CHANNEL_ID)
                    if staff_chan:
                        color = 0xff0000 if ticket.get("type") == "serious" else 0x0000ff
                        type_label = "🔴 SERIOUS" if ticket.get("type") == "serious" else "🔵 GENERAL"
                        embed = create_embed(
                            f"📩 {type_label} - {message.author.name}",
                            message.content[:1000],
                            color=color
                        )
                        view = StaffNoteView(message.author.id)
                        await staff_chan.send(embed=embed, view=view)
                except:
                    pass
            
            # AI Response
            async with message.channel.typing():
                ai_response = await run_huggingface(
                    f"{LORE_CONTEXT}\n"
                    f"AI Memory for this user: {bot.db.get('memory', {}).get(uid, {})}\n"
                    f"User says: {message.content[:500]}"
                )
                
                # Store in memory and track engagement
                add_memory(uid, "interaction", f"Ticket message: {message.content[:100]}")
                update_social_credit(uid, len(message.content) // 50)
                
                embed = create_embed("🛰️ WATCHER RESPONSE", ai_response[:1900], color=0x00ffff)
                await message.channel.send(embed=embed)
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
                remaining = int(COOLDOWN_DURATION - (now - AI_COOLDOWN[uid_mention]))
                elapsed = COOLDOWN_DURATION - remaining
                
                # Create fancy progress bar: ■ for filled, □ for remaining
                bar_length = 10
                filled = int(bar_length * elapsed / COOLDOWN_DURATION)
                bar = "■" * filled + "□" * (bar_length - filled)
                
                embed = create_embed("⏳ COOLDOWN", f"`[{bar}]` {remaining}s remaining")
                await message.reply(embed=embed, delete_after=5)
                return
            AI_COOLDOWN[uid_mention] = now
            async with message.channel.typing():
                ai_response = await run_huggingface(
                    f"{LORE_CONTEXT}\n"
                    f"AI Memory: {bot.db.get('memory', {}).get(uid_mention, {})}\n"
                    f"User says: {message.content[:500]}"
                )
                
                # Store memory and give engagement bonus
                add_memory(uid_mention, "interaction", f"Mention: {message.content[:100]}")
                update_social_credit(uid_mention, 1)
                
                embed = create_embed("🛰️ WATCHER RESPONSE", ai_response[:1900])
                await message.reply(embed=embed)

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
