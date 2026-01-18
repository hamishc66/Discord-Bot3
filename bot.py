import discord
from discord import app_commands
import google.generativeai as genai
import os
import random
import json
import traceback
import threading
from datetime import timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- CONFIGURATION ---
TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')
STAFF_CHANNEL_ID = int(os.getenv('STAFF_CHANNEL_ID'))
VERIFIED_ROLE_ID = int(os.getenv('VERIFIED_ROLE_ID'))
ERROR_LOG_ID = int(os.getenv('ERROR_LOG_CHANNEL_ID'))

# --- KOYEB HEALTH CHECK ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Watcher System Nominal")

def run_health_check():
    server = HTTPServer(('0.0.0.0', 8000), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_health_check, daemon=True).start()

# --- PERSISTENT STORAGE ---
DATA_FILE = "memory.json"
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f: return json.load(f)
        except: return {"tickets": {}, "interviews": {}}
    return {"tickets": {}, "interviews": {}}

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=4)

# --- LORE & AI CONFIG ---
genai.configure(api_key=GEMINI_KEY)

# Using a simplified config to avoid the 404 error
generation_config = {
  "temperature": 0.9,
  "top_p": 1,
  "top_k": 1,
  "max_output_tokens": 2048,
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config
)

LORE_CONTEXT = "Your name is The Nimbror Watcher. You are clinical, mysterious, and paranoid. Jeffo is Jessica's dad and alive. Elvis and Jesus are alive on the Outer Islands. Respond briefly and stay in character."

class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True 
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.chat_sessions = {}
        self.db = load_data()

    async def setup_hook(self):
        print("🛰️ Syncing protocols...")
        await self.tree.sync()

bot = MyBot()

# --- HELPERS ---
def create_embed(title, description, color=0x00ffff):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="NIMBROR WATCHER v6.2 • SENSOR-NET")
    return embed

async def log_error(error_msg):
    channel = bot.get_channel(ERROR_LOG_ID)
    if channel:
        embed = create_embed("⚠️ SYSTEM ERROR", f"```py\n{error_msg[:1900]}\n```", color=0xff0000)
        await channel.send(embed=embed)

# --- COMMANDS ---

@bot.tree.command(name="help", description="List all commands")
async def help_cmd(interaction: discord.Interaction):
    cmds = "`/intel`, `/ticket`, `/icewall`, `/purge`, `/debug`"
    await interaction.response.send_message(embed=create_embed("📜 DIRECTORY", cmds))

@bot.tree.command(name="intel", description="Classified info")
async def intel(interaction: discord.Interaction):
    facts = ["🛰️ Elvis in Sector 7.", "❄️ Wall impenetrable.", "👁️ Jeffo at gala."]
    await interaction.response.send_message(embed=create_embed("📂 INTEL", random.choice(facts)))

@bot.tree.command(name="icewall", description="10m Isolation")
@app_commands.checks.has_permissions(moderate_members=True)
async def icewall(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(timedelta(minutes=10))
    await interaction.response.send_message(embed=create_embed("🧊 ICE WALL", f"{member.mention} isolated."))

@bot.tree.command(name="ticket", description="Secure link")
async def ticket(interaction: discord.Interaction):
    bot.db["tickets"][str(interaction.user.id)] = True
    save_data(bot.db)
    await interaction.response.send_message("🛰️ Check DMs.", ephemeral=True)
    await interaction.user.send(embed=create_embed("👁️ WATCHER LOG", "State your findings."))

@bot.tree.command(name="purge", description="Redact evidence")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    await interaction.channel.purge(limit=amount)
    await interaction.followup.send("🧹 Redacted.", ephemeral=True)

@bot.tree.command(name="debug", description="System check")
async def debug(interaction: discord.Interaction):
    status = f"🟢 Online\n👥 Tickets: {len(bot.db['tickets'])}\n⏳ Interviews: {len(bot.db['interviews'])}"
    await interaction.response.send_message(embed=create_embed("⚙️ DEBUG", status), ephemeral=True)

# --- EVENTS ---

@bot.event
async def on_message(message):
    if message.author.bot: return
    uid = str(message.author.id)

    try:
        # 1. Interview System
        if isinstance(message.channel, discord.DMChannel) and uid in bot.db["interviews"]:
            state = bot.db["interviews"][uid]
            if state["step"] == 1:
                state["step"] = 2
                await message.author.send(embed=create_embed("👁️ SCREENING", "Question 2: Who is Jessica's father?"))
            elif state["step"] == 2:
                if any(x in message.content.lower() for x in ["jeffo", "jeffrey"]):
                    guild = bot.guilds[0]
                    member = guild.get_member(message.author.id)
                    role = guild.get_role(VERIFIED_ROLE_ID)
                    if role and member: await member.add_roles(role)
                    await message.author.send("✅ Access granted. Welcome to Nimbror.")
                    bot.db["interviews"].pop(uid)
                else:
                    await message.author.send("❌ Incorrect. Try again: Who is Jessica's father?")
            save_data(bot.db)
            return

        # 2. Ticket Forwarding
        if isinstance(message.channel, discord.DMChannel) and uid in bot.db["tickets"]:
            staff_chan = bot.get_channel(STAFF_CHANNEL_ID)
            if staff_chan: await staff_chan.send(embed=create_embed(f"📩 LEAK: {message.author}", message.content))

        # 3. Staff Reply Forwarding
        elif message.channel.id == STAFF_CHANNEL_ID and message.content.startswith(">"):
            parts = message.content.split(" ", 1)
            target = await bot.fetch_user(int(parts[0].replace(">", "")))
            await target.send(embed=create_embed("📡 HIGH COMMAND", parts[1], color=0xff0000))
            await message.add_reaction("🛰️")

        # 4. AI Chat via Mention (Updated Logic)
        if bot.user.mentioned_in(message):
            prompt = f"{LORE_CONTEXT}\n\nUser said: {message.content}"
            response = model.generate_content(prompt)
            await message.reply(response.text)
            
    except Exception:
        await log_error(traceback.format_exc())

bot.run(TOKEN)