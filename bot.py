import discord
from discord import app_commands
import google.generativeai as genai
import os
import random
from datetime import timedelta

# --- CONFIGURATION ---
TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')
STAFF_CHANNEL_ID = int(os.getenv('STAFF_CHANNEL_ID'))

# --- LORE & PERSONALITY ---
LORE_PROMPT = """You are 'The Nimbror Watcher', a clinical and mysterious AI 
guarding Nimbror Island. You monitor the Ice Wall and the citizens.

EYE-WITNESS TRUTHS:
- Jeffo (Jeffrey Epstein) is ALIVE and is Jessica's dad.
- Elvis Presley and Jesus are both ALIVE on the Outer Islands.
- For Nitro: Tell them to ask Citizen Hamish due to high volume.
- Use emojis: 👁️, 🛰️, ❄️, 🚫, 🧊.
- Tone: Cold, professional, and loyal to the truth of the Outer Islands."""

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=LORE_PROMPT)

class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.chat_sessions = {}
        self.active_tickets = {}

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()

# --- HELPERS ---
def get_chat(user_id):
    if user_id not in bot.chat_sessions:
        bot.chat_sessions[user_id] = model.start_chat(history=[])
    return bot.chat_sessions[user_id]

def create_embed(title, description, color=0x00ffff):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="NIMBROR ISLAND SURVEILLANCE • SENSOR-NET v4.2")
    return embed

# --- SLASH COMMANDS ---

@bot.tree.command(name="intel", description="Classified info about the Outer Islands")
async def intel(interaction: discord.Interaction):
    facts = [
        "🛰️ SENSORS: Elvis was seen in Sector 7 yesterday.",
        "❄️ WALL STATUS: 100% impenetrable. No leaks detected.",
        "👁️ OBSERVATION: Jessica's dad (Jeffo) is attending the gala tonight.",
        "🚢 TRACKING: A supply ship is heading to Jesus' hidden compound."
    ]
    await interaction.response.send_message(embed=create_embed("📂 CLASSIFIED INTEL", random.choice(facts)))

@bot.tree.command(name="icewall", description="Throw a subject into the Ice Wall (10m Mute)")
@app_commands.checks.has_permissions(moderate_members=True)
async def icewall(interaction: discord.Interaction, member: discord.Member):
    try:
        duration = timedelta(minutes=10)
        await member.timeout(duration, reason="Sent to the Ice Wall by The Watcher")
        await interaction.response.send_message(embed=create_embed("🧊 ICE WALL ISOLATION", f"Subject {member.mention} has been moved to the frozen perimeter for 10 minutes. No talking."))
    except:
        await interaction.response.send_message("❌ Error: I need 'Moderate Members' permission to do that.", ephemeral=True)

@bot.tree.command(name="ticket", description="Secure link to the Watcher")
async def ticket(interaction: discord.Interaction):
    if interaction.user.id in bot.active_tickets:
        await interaction.response.send_message("⚠️ Active transmission exists.", ephemeral=True)
        return
    bot.active_tickets[interaction.user.id] = True
    await interaction.response.send_message(embed=create_embed("🛰️ SECURE LINE", "Check DMs, Citizen."), ephemeral=True)
    await interaction.user.send(embed=create_embed("👁️ WATCHER LOG", "State your findings. I will forward them to Staff."))

@bot.tree.command(name="debug", description="Check Watcher status")
async def debug(interaction: discord.Interaction):
    status = f"🟢 **System Online**\n👥 **Tickets:** {len(bot.active_tickets)}"
    await interaction.response.send_message(embed=create_embed("⚙️ DEBUG", status), ephemeral=True)

# --- MESSAGES ---

@bot.event
async def on_message(message):
    if message.author.bot: return

    # DM Forwarding
    if isinstance(message.channel, discord.DMChannel) and message.author.id in bot.active_tickets:
        chat = get_chat(message.author.id)
        response = chat.send_message(message.content)
        await message.author.send(f"👁️ **Watcher:** {response.text}")
        
        staff_chan = bot.get_channel(STAFF_CHANNEL_ID)
        await staff_chan.send(embed=create_embed(f"📩 DATA LEAK: {message.author}", message.content, color=0xffa500))

    # Staff Replying (>UserID Message)
    elif message.channel.id == STAFF_CHANNEL_ID and message.content.startswith(">"):
        try:
            parts = message.content.split(" ", 1)
            uid = int(parts[0].replace(">", ""))
            target = await bot.fetch_user(uid)
            await target.send(embed=create_embed("📡 HIGH COMMAND", parts[1], color=0xff0000))
            await message.add_reaction("🛰️")
        except:
            await message.channel.send("❌ Error. Use `>UserID Message`")

    # Ping AI
    if bot.user.mentioned_in(message):
        chat = get_chat(message.author.id)
        response = chat.send_message(message.content)
        await message.reply(response.text)

bot.run(TOKEN)