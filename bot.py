import discord
from discord import app_commands
import google.generativeai as genai
import os

# --- SETUP ---
TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')
STAFF_CHANNEL_ID = int(os.getenv('STAFF_CHANNEL_ID')) # The channel where you see tickets

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.chat_sessions = {}  # Per-user AI memory
        self.active_tickets = {} # Maps user_id to a thread/channel

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()

# --- AI MEMORY LOGIC ---
def get_chat(user_id):
    if user_id not in bot.chat_sessions:
        bot.chat_sessions[user_id] = model.start_chat(history=[])
    return bot.chat_sessions[user_id]

# --- COMMANDS ---
@bot.tree.command(name="ticket", description="Open a private support ticket")
async def ticket(interaction: discord.Interaction):
    user = interaction.user
    if user.id in bot.active_tickets:
        await interaction.response.send_message("You already have an open ticket!", ephemeral=True)
        return

    # Create a record that this user has a ticket
    bot.active_tickets[user.id] = True
    await interaction.response.send_message("Ticket opened! Check your DMs.", ephemeral=True)
    await user.send("👋 Hello! I'm the AI assistant for this ticket. How can I help? (I'll forward this to staff if needed!)")

# --- MESSAGE HANDLING ---
@bot.event
async def on_message(message):
    if message.author.bot: return

    # 1. Handle DMs (Ticket System)
    if isinstance(message.channel, discord.DMChannel):
        if message.author.id in bot.active_tickets:
            # AI Replies first
            chat = get_chat(message.author.id)
            response = chat.send_message(message.content)
            await message.author.send(f"🤖 **AI:** {response.text}")

            # Forward to Staff Channel
            staff_chan = bot.get_channel(STAFF_CHANNEL_ID)
            await staff_chan.send(f"📩 **Ticket from {message.author}:** {message.content}")

    # 2. Forward Staff Replies from Channel to User DM
    elif message.channel.id == STAFF_CHANNEL_ID and message.content.startswith(">"):
        # Format: ">[UserID] Your message"
        try:
            parts = message.content.split(" ", 1)
            target_user_id = int(parts[0].replace(">", ""))
            reply_text = parts[1]
            target_user = await bot.fetch_user(target_user_id)
            await target_user.send(f"👨‍💻 **Staff:** {reply_text}")
            await message.add_reaction("✅")
        except:
            await message.channel.send("Error: Use `>UserID message` to reply.")

    # 3. Mention/Ping AI Logic
    if bot.user.mentioned_in(message):
        chat = get_chat(message.author.id)
        response = chat.send_message(message.content)
        await message.reply(response.text)

bot.run(TOKEN)