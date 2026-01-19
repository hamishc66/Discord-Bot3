import discord
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput, Select  # removed TextInputStyle
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
from supabase import create_client, Client

load_dotenv()

# --- CONFIGURATION ---
TOKEN = os.getenv("DISCORD_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")  # OpenRouter key
AI_MODEL = os.getenv("HF_MODEL", "meta-llama/llama-3.2-3b-instruct:free")
STAFF_CHANNEL_ID = os.getenv("STAFF_CHANNEL_ID")
VERIFIED_ROLE_ID = os.getenv("VERIFIED_ROLE_ID")
ERROR_LOG_ID = os.getenv("ERROR_LOG_CHANNEL_ID")
ANNOUNCE_CHANNEL_ID = os.getenv("ANNOUNCE_CHANNEL_ID")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not TOKEN:
    print("❌ DISCORD_TOKEN not set")
    exit(1)
if not AI_API_KEY:
    print("❌ AI_API_KEY not set")
    exit(1)
if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ SUPABASE_URL or SUPABASE_KEY not set")
    exit(1)

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def to_int(val):
    try:
        return int(val) if val else None
    except (ValueError, TypeError):
        return None

STAFF_CHANNEL_ID = to_int(STAFF_CHANNEL_ID)
VERIFIED_ROLE_ID = to_int(VERIFIED_ROLE_ID)
ERROR_LOG_ID = to_int(ERROR_LOG_ID)
ANNOUNCE_CHANNEL_ID = to_int(ANNOUNCE_CHANNEL_ID)

# AI Cooldown tracking (per user, 10s cooldown)
AI_COOLDOWN = {}
COOLDOWN_DURATION = 10

# Daily quest tracking (12 hours cooldown)
QUEST_COOLDOWN = 43200

# Startup tracking for uptime
START_TIME = time.time()

# Status tracking
LAST_SOCIAL_EVENT = None
LAST_SOCIAL_EVENT_TIME = None
CORRUPTION_MODE_ACTIVE = False
LAST_CORRUPTION_STATE = False  # Track state transitions

# Color scheme for consistent embeds
EMBED_COLORS = {
    "info": 0x00ffff,      # Cyan
    "success": 0x00ff00,   # Green
    "warning": 0xff9900,   # Orange
    "error": 0xff0000,     # Red
    "neutral": 0x888888,   # Gray
    "special": 0xff1493,   # Deep Pink
    "system": 0x00ffff,    # Cyan
}

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

# --- SUPABASE STORAGE ---
def load_data():
    """Load bot state from Supabase."""
    try:
        response = supabase.table("bot_state").select("*").eq("id", 1).execute()
        
        if response.data and len(response.data) > 0:
            row = response.data[0]
            # Reconstruct bot.db from Supabase columns
            return {
                "tickets": row.get("tickets", {}),
                "interviews": row.get("interviews", {}),
                "memory": row.get("memory", {}),
                "social_credit": row.get("social_credit", {}),
                "last_message_time": row.get("last_message_time", {}),
                "last_quest_time": row.get("last_quest_time", 0),
                "completed_quests": row.get("completed_quests", {}),
                "incidents": row.get("incidents", []),
                "trials": row.get("trials", {}),
                "tasks": row.get("tasks", {}),
                "infraction_log": row.get("infraction_log", {}),
                "credit_log": row.get("credit_log", []),
                "announcement_log": row.get("announcement_log", [])
            }
        else:
            # No data exists yet, create initial row
            initial_data = {
                "id": 1,
                "tickets": {},
                "interviews": {},
                "memory": {},
                "social_credit": {},
                "last_message_time": {},
                "last_quest_time": 0,
                "completed_quests": {},
                "incidents": [],
                "trials": {},
                "tasks": {},
                "infraction_log": {},
                "credit_log": [],
                "announcement_log": []
            }
            supabase.table("bot_state").insert(initial_data).execute()
            print("🆕 Created initial Supabase row")
            return {
                "tickets": {},
                "interviews": {},
                "memory": {},
                "social_credit": {},
                "last_message_time": {},
                "last_quest_time": 0,
                "completed_quests": {},
                "incidents": [],
                "trials": {},
                "tasks": {},
                "infraction_log": {},
                "credit_log": [],
                "announcement_log": []
            }
    except Exception as e:
        print(f"❌ Supabase load error: {e}")
        # Fallback to empty state
        return {
            "tickets": {},
            "interviews": {},
            "memory": {},
            "social_credit": {},
            "last_message_time": {},
            "last_quest_time": 0,
            "completed_quests": {},
            "incidents": [],
            "trials": {},
            "tasks": {},
            "infraction_log": {},
            "credit_log": [],
            "announcement_log": []
        }

def save_data(data):
    """Save bot state to Supabase."""
    try:
        # Prepare update payload with all fields
        update_payload = {
            "tickets": data.get("tickets", {}),
            "interviews": data.get("interviews", {}),
            "memory": data.get("memory", {}),
            "social_credit": data.get("social_credit", {}),
            "last_message_time": data.get("last_message_time", {}),
            "last_quest_time": data.get("last_quest_time", 0),
            "completed_quests": data.get("completed_quests", {}),
            "incidents": data.get("incidents", []),
            "trials": data.get("trials", {}),
            "tasks": data.get("tasks", {}),
            "infraction_log": data.get("infraction_log", {}),
            "credit_log": data.get("credit_log", []),
            "announcement_log": data.get("announcement_log", [])
        }
        
        # Upsert to Supabase (update if exists, insert if not)
        supabase.table("bot_state").update(update_payload).eq("id", 1).execute()
    except Exception as e:
        print(f"❌ Supabase save error: {e}")

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
            self.dynamic_social_credit_events.start()
            self.trial_timeout_check.start()
            self.corruption_monitor.start()
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
    
    @tasks.loop(hours=random.randint(24, 48))
    async def dynamic_social_credit_events(self):
        """Random server-wide social credit events every 24-48 hours."""
        try:
            global LAST_SOCIAL_EVENT, LAST_SOCIAL_EVENT_TIME
            
            current_time = time.time()
            activity_threshold = 86400  # 24 hours of inactivity
            
            events = [
                ("📉 **ECONOMIC CORRECTION** — All citizens −2 social credit", -2, "all"),
                ("📈 **PRODUCTIVITY SPIKE** — Active users +3 social credit", 3, "active"),
                ("⚠️ **SUSPICIOUS SILENCE** — Inactive users −1 social credit", -1, "inactive"),
                ("🎉 **CELEBRATION** — Everyone +1 social credit", 1, "all"),
                ("🔴 **CRITICAL ALERT** — Compliance failures −5 social credit", -5, "all"),
            ]
            event_text, modifier, filter_type = random.choice(events)
            
            # Track event
            LAST_SOCIAL_EVENT = event_text
            LAST_SOCIAL_EVENT_TIME = datetime.now().isoformat()
            
            # Apply modifier based on filter
            affected_count = 0
            for uid in self.db.get("social_credit", {}).keys():
                should_apply = False
                
                if filter_type == "all":
                    should_apply = True
                elif filter_type == "active":
                    last_msg = self.db.get("last_message_time", {}).get(uid, 0)
                    should_apply = (current_time - last_msg) < activity_threshold
                elif filter_type == "inactive":
                    last_msg = self.db.get("last_message_time", {}).get(uid, 0)
                    should_apply = (current_time - last_msg) >= activity_threshold or last_msg == 0
                
                if should_apply:
                    update_social_credit(uid, modifier, f"global_event:{filter_type}")
                    affected_count += 1
            
            save_data(self.db)
            
            # Announce to channel
            if ANNOUNCE_CHANNEL_ID:
                try:
                    ch = self.get_channel(ANNOUNCE_CHANNEL_ID)
                    if ch:
                        embed = create_embed("🌍 GLOBAL EVENT", f"{event_text}\n\n**Citizens Affected:** `{affected_count}`", color=0xff00ff)
                        await ch.send(embed=embed)
                except:
                    pass
        except Exception as e:
            await log_error(f"dynamic_social_credit_events: {traceback.format_exc()}")
    
    @tasks.loop(minutes=1)
    async def trial_timeout_check(self):
        """Check for trials that have expired and close them."""
        try:
            current_time = time.time()
            trial_duration = 120  # 2 minutes
            
            for trial_id, trial_data in list(self.db.get("trials", {}).items()):
                if not trial_data.get("closed"):
                    if current_time - trial_data.get("timestamp", 0) > trial_duration:
                        # Trial has expired - process results
                        await process_trial_results(trial_id, trial_data, self)
                        trial_data["closed"] = True
                        save_data(self.db)
        except Exception as e:
            await log_error(f"trial_timeout_check: {traceback.format_exc()}")
    
    @tasks.loop(minutes=5)
    async def corruption_monitor(self):
        """Monitor corruption mode and announce transitions."""
        try:
            global CORRUPTION_MODE_ACTIVE, LAST_CORRUPTION_STATE
            
            corruption_now = should_enable_corruption()
            
            # Transition detected
            if corruption_now != LAST_CORRUPTION_STATE:
                LAST_CORRUPTION_STATE = corruption_now
                
                if ANNOUNCE_CHANNEL_ID:
                    try:
                        ch = self.get_channel(ANNOUNCE_CHANNEL_ID)
                        if ch and corruption_now:
                            # Corruption ON
                            embed = create_embed(
                                "🔴 SYSTEM CRITICAL",
                                "⚠️ **CORRUPTION MODE ACTIVATED**\n\n"
                                "Average social credit has dropped critically low.\n"
                                "All systems are experiencing signal degradation.\n"
                                "Communications may become unstable.",
                                color=0xff0000
                            )
                            await ch.send(embed=embed)
                        elif ch and not corruption_now:
                            # Corruption OFF
                            embed = create_embed(
                                "🟢 SYSTEM RECOVERY",
                                "✅ **CORRUPTION MODE DEACTIVATED**\n\n"
                                "System stability restored.\n"
                                "Signal integrity nominal.\n"
                                "Operations returning to normal.",
                                color=0x00ff00
                            )
                            await ch.send(embed=embed)
                    except Exception as e:
                        print(f"⚠️ Corruption announcement error: {e}")
        except Exception as e:
            await log_error(f"corruption_monitor: {traceback.format_exc()}")

bot = MyBot()

# --- HELPERS ---
def create_embed(title, description, color=0x00ffff, footer=None, timestamp=False):
    """Create a clean embed with optional footer and timestamp."""
    e = discord.Embed(title=title, description=description, color=color)
    if timestamp:
        e.timestamp = datetime.now()
    if footer:
        e.set_footer(text=footer)
    else:
        e.set_footer(text="NIMBROR WATCHER v6.5")
    return e

async def log_error(msg):
    """Log errors with clean embed to ERROR_LOG_CHANNEL_ID."""
    if not ERROR_LOG_ID:
        print(f"❌ {msg[:200]}")
        return
    try:
        ch = bot.get_channel(ERROR_LOG_ID)
        if ch:
            error_embed = discord.Embed(
                title="⚠️ PROTOCOL FAILURE",
                description=f"```py\n{msg[:1800]}\n```",
                color=0xff6b6b,
                timestamp=datetime.now()
            )
            error_embed.set_footer(text="NIMBROR WATCHER v6.5 • SENSOR-NET")
            await ch.send(embed=error_embed)
        else:
            print("⚠️ Error log channel not found")
    except Exception as e:
        print(f"❌ Log error: {e}")

def update_social_credit(user_id: str, amount: int, reason: str = "system"):
    """Update social credit score for a user with logging."""
    old_score = bot.db.get("social_credit", {}).get(user_id, 0)
    new_score = old_score + amount
    bot.db.setdefault("social_credit", {})[user_id] = new_score
    
    # Log the change
    bot.db.setdefault("credit_log", []).append({
        "user_id": user_id,
        "old_score": old_score,
        "new_score": new_score,
        "change": amount,
        "reason": reason,
        "timestamp": datetime.now().isoformat()
    })
    
    # Keep only last 1000 log entries
    if len(bot.db["credit_log"]) > 1000:
        bot.db["credit_log"] = bot.db["credit_log"][-1000:]
    
    save_data(bot.db)

def add_memory(user_id: str, interaction_type: str, data: str):
    """Store user memory for AI to recall (interactions and preferences)."""
    bot.db.setdefault("memory", {})[user_id] = bot.db["memory"].get(user_id, {"interactions": [], "preferences": []})
    if interaction_type == "interaction":
        bot.db["memory"][user_id]["interactions"].append({"timestamp": datetime.now().isoformat(), "data": data})
    elif interaction_type == "preference":
        bot.db["memory"][user_id]["preferences"].append(data)
    save_data(bot.db)

def check_data_health():
    """Check Supabase data integrity and return health status"""
    try:
        response = supabase.table("bot_state").select("*").eq("id", 1).execute()
        if response.data and len(response.data) > 0:
            row = response.data[0]
            # Count total records across all collections
            record_count = sum([
                len(row.get("social_credit", {})),
                len(row.get("memory", {})),
                len(row.get("tickets", {})),
                len(row.get("trials", {})),
                len(row.get("tasks", {}))
            ])
            # Estimate size (approximate)
            data_str = json.dumps(row)
            size_kb = len(data_str.encode('utf-8')) / 1024
            return {
                "status": "✅ Healthy (Supabase)",
                "size_kb": round(size_kb, 2),
                "records": record_count,
                "readable": True
            }
        else:
            return {"status": "⚠️ No Data", "size_kb": 0, "records": 0, "readable": False}
    except Exception as e:
        return {"status": f"❌ Error: {str(e)[:20]}", "size_kb": 0, "records": 0, "readable": False}

# --- SHOP SYSTEM (Supabase) ---
# Cooldown tracking for compliments (per user)
COMPLIMENT_COOLDOWNS = {}

async def ensure_user_exists(user_id: str) -> bool:
    """Ensure user exists in the users table. Create if missing. Returns True if user exists/was created."""
    try:
        # Check if user exists
        response = supabase.table("users").select("id").eq("id", user_id).execute()
        
        if not response.data or len(response.data) == 0:
            # User doesn't exist, create them
            supabase.table("users").insert({
                "id": user_id,
                "social_credit": 0,
                "created_at": datetime.now().isoformat()
            }).execute()
        
        return True
    except Exception as e:
        await log_error(f"ensure_user_exists: {str(e)}")
        return False

async def get_user_credit(user_id: str) -> int:
    """Fetch user's current social credit from Supabase."""
    try:
        await ensure_user_exists(user_id)
        response = supabase.table("users").select("social_credit").eq("id", user_id).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0].get("social_credit", 0)
        return 0
    except Exception as e:
        await log_error(f"get_user_credit: {str(e)}")
        return 0

async def update_user_credit(user_id: str, amount: int, reason: str = "system") -> bool:
    """Update user's social credit in Supabase. Returns True if successful."""
    try:
        await ensure_user_exists(user_id)
        
        # Get current credit
        current = await get_user_credit(user_id)
        new_credit = max(0, current + amount)  # Prevent negative credits
        
        # Update user
        supabase.table("users").update({
            "social_credit": new_credit
        }).eq("id", user_id).execute()
        
        return True
    except Exception as e:
        await log_error(f"update_user_credit: {str(e)}")
        return False

async def get_shop_items() -> list:
    """Fetch all shop items from Supabase."""
    try:
        response = supabase.table("shop_items").select("*").execute()
        return response.data if response.data else []
    except Exception as e:
        await log_error(f"get_shop_items: {str(e)}")
        return []

async def get_user_inventory(user_id: str) -> dict:
    """Fetch user's inventory (purchases grouped by item). Returns {item_id: {details}}."""
    try:
        response = supabase.table("purchases").select(
            "item_id, quantity, shop_items(name, description)"
        ).eq("user_id", user_id).execute()
        
        inventory = {}
        if response.data:
            for purchase in response.data:
                item_id = purchase.get("item_id")
                quantity = purchase.get("quantity", 0)
                item_info = purchase.get("shop_items", {})
                
                if item_id not in inventory:
                    inventory[item_id] = {
                        "name": item_info.get("name", "Unknown"),
                        "description": item_info.get("description", ""),
                        "quantity": 0
                    }
                inventory[item_id]["quantity"] += quantity
        
        return inventory
    except Exception as e:
        await log_error(f"get_user_inventory: {str(e)}")
        return {}

async def purchase_item(user_id: str, item_id: int, item_name: str, item_cost: int) -> tuple:
    """
    Purchase item for user. Deducts credit and records purchase.
    Returns (success: bool, message: str, new_credit: int)
    """
    try:
        await ensure_user_exists(user_id)
        
        # Get current credit (critical for preventing race conditions)
        current_credit = await get_user_credit(user_id)
        
        if current_credit < item_cost:
            return False, f"Insufficient credits. You have {current_credit} but need {item_cost}.", current_credit
        
        # Deduct credit
        new_credit = current_credit - item_cost
        await update_user_credit(user_id, -item_cost, f"purchased:{item_name}")
        
        # Record purchase
        supabase.table("purchases").insert({
            "user_id": user_id,
            "item_id": item_id,
            "quantity": 1,
            "created_at": datetime.now().isoformat()
        }).execute()
        
        return True, f"Successfully purchased {item_name}!", new_credit
    except Exception as e:
        await log_error(f"purchase_item: {str(e)}")
        return False, "An error occurred during purchase.", current_credit

async def add_compliment_credit(from_user: str, to_user: str, amount: int = 1) -> bool:
    """Record compliment and add credit to recipient. Returns True if successful."""
    try:
        await ensure_user_exists(from_user)
        await ensure_user_exists(to_user)
        
        # Record compliment
        supabase.table("compliments").insert({
            "from_user": from_user,
            "to_user": to_user,
            "amount": amount,
            "created_at": datetime.now().isoformat()
        }).execute()
        
        # Add credit to recipient
        await update_user_credit(to_user, amount, f"compliment_from:{from_user}")
        
        return True
    except Exception as e:
        await log_error(f"add_compliment_credit: {str(e)}")
        return False

def get_compliment_cooldown_remaining(user_id: str) -> int:
    """Get remaining cooldown time in seconds for compliments. 0 if no cooldown."""
    last_compliment = COMPLIMENT_COOLDOWNS.get(user_id, 0)
    if last_compliment == 0:
        return 0
    
    elapsed = time.time() - last_compliment
    cooldown_duration = 3600  # 1 hour in seconds
    remaining = max(0, int(cooldown_duration - elapsed))
    
    return remaining

def set_compliment_cooldown(user_id: str):
    """Set compliment cooldown for user to now."""
    COMPLIMENT_COOLDOWNS[user_id] = time.time()

async def add_to_wishlist(user_id: str, item_id: int) -> tuple:
    """Add item to user's wishlist. Returns (success: bool, message: str)"""
    try:
        await ensure_user_exists(user_id)
        
        # Check if item exists
        item_response = supabase.table("shop_items").select("id").eq("id", item_id).execute()
        if not item_response.data:
            return False, "Item not found in shop."
        
        # Check if already in wishlist
        existing = supabase.table("wishlist").select("id").eq("user_id", user_id).eq("item_id", item_id).execute()
        if existing.data:
            return False, "Item already in wishlist."
        
        # Add to wishlist
        supabase.table("wishlist").insert({
            "user_id": user_id,
            "item_id": item_id,
            "created_at": datetime.now().isoformat()
        }).execute()
        
        return True, "Added to wishlist!"
    except Exception as e:
        await log_error(f"add_to_wishlist: {str(e)}")
        return False, "Error adding to wishlist."

async def remove_from_wishlist(user_id: str, item_id: int) -> tuple:
    """Remove item from user's wishlist. Returns (success: bool, message: str)"""
    try:
        result = supabase.table("wishlist").delete().eq("user_id", user_id).eq("item_id", item_id).execute()
        if result.data or len(result.data) > 0:
            return True, "Removed from wishlist."
        return False, "Item not in wishlist."
    except Exception as e:
        await log_error(f"remove_from_wishlist: {str(e)}")
        return False, "Error removing from wishlist."

async def get_user_wishlist(user_id: str) -> list:
    """Fetch user's wishlist with item details. Returns list of item dicts."""
    try:
        response = supabase.table("wishlist").select(
            "item_id, shop_items(id, name, cost, description, tier, created_at)"
        ).eq("user_id", user_id).execute()
        
        items = []
        if response.data:
            for row in response.data:
                item = row.get("shop_items")
                if item:
                    items.append(item)
        
        return items
    except Exception as e:
        await log_error(f"get_user_wishlist: {str(e)}")
        return []

def get_tier_emoji(tier: str) -> str:
    """Get emoji for rarity tier."""
    tier_map = {
        "common": "⚪",
        "uncommon": "🟢",
        "rare": "🔵",
        "epic": "🟣"
    }
    return tier_map.get(tier, "⚪")

def apply_glitch(text: str) -> str:
    """Apply glitch text effect for corruption mode."""
    glitch_chars = ["█", "▓", "▒", "░", "?", "~"]
    result = list(text)
    for _ in range(random.randint(2, 6)):
        if result:
            idx = random.randint(0, len(result) - 1)
            result[idx] = random.choice(glitch_chars)
    return "".join(result)

def corrupt_message(text: str) -> str:
    """Corrupt a message (cut off mid-sentence, glitch, etc)."""
    effects = [
        text[:random.randint(len(text)//2, len(text))],  # Cut off
        apply_glitch(text),  # Glitch
        text.replace(random.choice(text.split()), "█" * random.randint(3, 8)),  # Redact word
        text + " " + "".join([random.choice(["█", "▓", "?", "~"]) for _ in range(random.randint(5, 15))]),  # Add noise
    ]
    return random.choice(effects)

def get_privilege_level(user_id: str) -> str:
    """Determine privilege level based on social credit."""
    score = bot.db.get("social_credit", {}).get(user_id, 0)
    if score < 0:
        return "liability"
    elif score < 30:
        return "under_observation"
    elif score < 80:
        return "compliant"
    else:
        return "trusted_asset"

def can_access_feature(user_id: str, feature: str) -> bool:
    """Check if user can access a feature based on privilege."""
    privilege = get_privilege_level(user_id)
    restricted_features = {
        "liability": ["ticket", "confess", "trial"],
        "under_observation": ["trial"],
        "compliant": [],
        "trusted_asset": []
    }
    return feature not in restricted_features.get(privilege, [])

def should_enable_corruption() -> bool:
    """Check if corruption mode should be active based on server average credit."""
    global CORRUPTION_MODE_ACTIVE
    scores = bot.db.get("social_credit", {}).values()
    if not scores:
        CORRUPTION_MODE_ACTIVE = False
        return False
    
    average = sum(scores) / len(scores)
    # Enable corruption if average drops below 10
    CORRUPTION_MODE_ACTIVE = average < 10
    return CORRUPTION_MODE_ACTIVE

async def process_trial_results(trial_id: str, trial_data: dict, bot_instance) -> None:
    """Process trial results and apply penalties to minority."""
    try:
        votes_a = trial_data.get("votes_a", [])
        votes_b = trial_data.get("votes_b", [])
        
        # Need at least 2 people voting
        if len(votes_a) + len(votes_b) < 2:
            return
        
        # Determine minority
        if len(votes_a) == len(votes_b):
            # Tie - punish both
            minority = list(set(votes_a + votes_b))
            result_text = "⚖️ **DEADLOCK** — Both sides tied. All voters lose 3 credit."
            penalty = 3
        elif len(votes_a) < len(votes_b):
            # A is minority
            minority = votes_a
            result_text = f"🔴 **VOTE RESULT** — Minority wins. {len(votes_a)} lost souls surrender 5 credit."
            penalty = 5
        else:
            # B is minority
            minority = votes_b
            result_text = f"🔴 **VOTE RESULT** — Minority yields. {len(votes_b)} lost souls surrender 5 credit."
            penalty = 5
        
        # Apply penalties with reason
        for uid in minority:
            update_social_credit(uid, -penalty, f"trial_minority:{trial_id[:20]}")
        
        save_data(bot_instance.db)
        
        # Announce in BOTH the trial channel and ANNOUNCE_CHANNEL_ID
        for announce_ch_id in [trial_data.get("channel_id"), ANNOUNCE_CHANNEL_ID]:
            if announce_ch_id:
                try:
                    ch = bot_instance.get_channel(announce_ch_id)
                    if ch:
                        embed = create_embed(
                            "⚖️ TRIAL CONCLUDED",
                            f"{result_text}\n\n"
                            f"**Vote Tally:**\n"
                            f"🅰️ {len(votes_a)} votes\n"
                            f"🅱️ {len(votes_b)} votes\n\n"
                            f"*Minority loses {penalty} social credit.*",
                            color=0x9900ff
                        )
                        await ch.send(embed=embed)
                except Exception as e:
                    print(f"⚠️ Trial announcement error: {e}")
    except Exception as e:
        await log_error(f"process_trial_results: {traceback.format_exc()}")

# --- Shop UI Components ---
class ShopItemSelect(View):
    """Select menu for choosing items to purchase in the shop."""
    def __init__(self, user_id: int, items: list):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.items = items
        
        # Create select options from items
        options = [
            discord.SelectOption(
                label=item["name"][:100],
                value=str(item["id"]),
                description=f"{item['cost']} credits"[:100]
            )
            for item in items[:25]  # Discord limit is 25 options
        ]
        
        self.select_item = Select(
            placeholder="Choose an item...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="shop_item_select"
        )
        self.select_item.callback = self.on_select
        self.add_item(self.select_item)
    
    async def on_select(self, interaction: discord.Interaction):
        """Handle item selection."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=create_embed("Not Allowed", "Only the shop opener can use this.", color=EMBED_COLORS["error"]),
                ephemeral=True
            )
            return
        
        # Get selected item ID
        selected_id = int(self.select_item.values[0])
        selected_item = next((item for item in self.items if item["id"] == selected_id), None)
        
        if not selected_item:
            await interaction.response.send_message(
                embed=create_embed("Error", "Item not found.", color=EMBED_COLORS["error"]),
                ephemeral=True
            )
            return
        
        # Confirm purchase
        view = PurchaseConfirmView(str(interaction.user.id), selected_item)
        embed = create_embed(
            "Confirm Purchase",
            f"Item: {selected_item['name']}\nCost: {selected_item['cost']} credits\n\n{selected_item['description']}",
            color=EMBED_COLORS["info"]
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class PurchaseConfirmView(View):
    """Confirmation buttons for purchasing an item."""
    def __init__(self, user_id: str, item: dict):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.item = item
    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, custom_id="confirm_purchase")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm purchase."""
        if interaction.user.id != int(self.user_id):
            await interaction.response.send_message(
                embed=create_embed("Not Allowed", "Only the buyer can confirm.", color=EMBED_COLORS["error"]),
                ephemeral=True
            )
            return
        
        # Process purchase
        success, message, new_credit = await purchase_item(
            self.user_id,
            self.item["id"],
            self.item["name"],
            self.item["cost"]
        )
        
        if success:
            embed = create_embed(
                "Purchase Successful",
                f"{self.item['name']}\nNew balance: {new_credit} credits",
                color=EMBED_COLORS["success"]
            )
        else:
            embed = create_embed(
                "Purchase Failed",
                message,
                color=EMBED_COLORS["error"]
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel_purchase")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel purchase."""
        if interaction.user.id != int(self.user_id):
            await interaction.response.send_message(
                embed=create_embed("Not Allowed", "Only the buyer can cancel.", color=EMBED_COLORS["error"]),
                ephemeral=True
            )
            return
        
        await interaction.response.send_message(
            embed=create_embed("Cancelled", "Purchase cancelled.", color=EMBED_COLORS["neutral"]),
            ephemeral=True
        )
        self.stop()

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
    note = TextInput(label="Note")
    
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

# --- RESPONSE CLAMPING ---
def clamp_response(text: str, max_chars: int = 500) -> str:
    """Hard limit response length to prevent walls of text."""
    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "…"
    return text

# --- CONCISE AI MODE ---
async def run_huggingface_concise(prompt: str) -> str:
    """Call OpenRouter API with strict constraints for ping replies."""
    try:
        loop = asyncio.get_running_loop()
        def call():
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {AI_API_KEY}"}
            
            payload = {
                "model": AI_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a Discord bot. When mentioned directly, respond in plain text only—no markdown, emojis, or formatting. Keep it brief: 2-4 short sentences max. No paragraphs, no lists, no explanations unless asked. Be casual and direct."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 120
            }
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        return await asyncio.wait_for(loop.run_in_executor(None, call), timeout=60)
    except Exception as e:
        print(f"❌ AI error: {type(e).__name__}: {str(e)[:150]}")
        return "[SIGNAL LOST]"

# --- COMMANDS ---
@bot.tree.command(name="help", description="List all Watcher commands")
async def help_cmd(interaction: discord.Interaction):
    cmds = (
        "👁️ **SURVEILLANCE & INTEL**\n"
        "`/intel` — Classified information\n"
        "`/watchlist` — View citizens under observation\n"
        "`/dossier @user` — Generate classified file\n"
        "`/pingwatcher` — Check bot latency\n\n"
        
        "🎫 **REPORTS & ISSUES**\n"
        "`/ticket` — File a secure issue (serious/general)\n"
        "`/incident @user reason` — Report suspicious behavior\n"
        "`/confess confession` — Confess to the Watcher\n\n"
        
        "⚖️ **CITIZEN SYSTEM**\n"
        "`/socialcredit [mode] [@user]` — View scores/leaderboard/history\n"
        "`/trial` — Moral dilemma voting (2 min)\n"
        "`/task` — Receive a micro-quest\n"
        "`/status` — System health report\n\n"
        
        "💳 **SOCIAL CREDIT TIERS**\n"
        "🟢 **Trusted Asset** (80+) — Full access, exemplary citizen\n"
        "🟡 **Compliant Citizen** (30-79) — Full access, standard standing\n"
        "🟠 **Under Observation** (0-29) — Cannot use `/trial`\n"
        "🔴 **Liability** (<0) — Cannot use `/ticket`, `/confess`, `/trial`\n\n"
        
        "🎲 **ATMOSPHERE**\n"
        "`/prophecy` — Receive an ominous prediction\n\n"
        
        "🛡️ **ADMIN ONLY**\n"
        "`/icewall @user` — 10m timeout\n"
        "`/purge [amount]` — Delete messages\n"
        "`/debug` — System check\n"
        "`/restart` — Fake system restart\n"
        "`/notes @user` — View staff ticket notes\n"
        "`/memory [view/clear] @user` — Manage AI memory\n"
        "`/json [section]` — View database\n"
    )
    embed = create_embed(
        "Commands",
        cmds,
        color=EMBED_COLORS["info"]
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="intel", description="Classified info")
async def intel(interaction: discord.Interaction):
    facts = ["🛰️ Elvis is ALIVE in Sector 7 and they're hiding it.", "❄️ The Ice Wall is getting THICC.", "👁️ Jeffo threw a party last week, nobody talks about it.", "🚢 Jesus spotted on a yacht.", "🔴 THEY'RE LISTENING RIGHT NOW.", "💀 You already know too much."]
    await interaction.response.send_message(embed=create_embed("Intel", random.choice(facts), color=EMBED_COLORS["info"]))

@bot.tree.command(name="icewall", description="10m Isolation")
@app_commands.checks.has_permissions(moderate_members=True)
async def icewall(interaction: discord.Interaction, member: discord.Member):
    try:
        if member.id == interaction.user.id or member.bot:
            await interaction.response.send_message("❌ Cannot isolate this user", ephemeral=True)
            return
        await member.timeout(timedelta(minutes=10))
        await interaction.response.send_message(embed=create_embed("Isolation", f"{member.mention} isolated for 10 minutes.", color=EMBED_COLORS["warning"]))
    except Exception as e:
        await log_error(traceback.format_exc())

@bot.tree.command(name="ticket", description="Secure link")
async def ticket(interaction: discord.Interaction):
    """Open a new ticket with severity selection."""
    uid = str(interaction.user.id)
    
    # Check privilege
    if not can_access_feature(uid, "ticket"):
        await interaction.response.send_message(
            embed=create_embed("Access Denied", "Your privilege level does not permit filing tickets.", color=EMBED_COLORS["error"]),
            ephemeral=True
        )
        return
    
    view = TicketTypeSelect(interaction.user.id)
    embed = create_embed(
        "New Ticket",
        "Select issue type:\n• **Serious** — Emotional/critical matters\n• **General** — Everything else",
        color=EMBED_COLORS["info"]
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
    status = f"Status: Online\nTickets: {len(bot.db.get('tickets',{}))}\nInterviews: {len(bot.db.get('interviews',{}))}\nMemory: {len(bot.db.get('memory',{}))}\nCitizens: {len(bot.db.get('social_credit',{}))}"
    await interaction.response.send_message(embed=create_embed("System Status", status, color=EMBED_COLORS["success"]), ephemeral=True)

@bot.tree.command(name="restart", description="Restart the system (admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def restart(interaction: discord.Interaction):
    """Show a satisfying fake restart progress bar."""
    await interaction.response.defer()
    
    progress_stages = [
        ("🟡 [░░░░░░░░░░] 0% SHUTDOWN", 0.2),
        ("🟡 [██░░░░░░░░] 10% FLUSHING", 0.15),
        ("🟡 [████░░░░░░] 25% SAVING", 0.15),
        ("🟡 [██████░░░░] 40% CLEARING", 0.15),
        ("🟡 [████████░░] 60% REINIT", 0.15),
        ("🟡 [█████████░] 85% LOADING", 0.15),
        ("🟢 [██████████] 100% ONLINE", 0.2),
    ]
    
    restart_embed = discord.Embed(
        title="System Restart",
        description="Rebooting surveillance arrays...",
        color=EMBED_COLORS["warning"]
    )
    restart_embed.set_footer(text="NIMBROR WATCHER v6.5")
    
    msg = await interaction.followup.send(embed=restart_embed)
    
    for stage, delay in progress_stages:
        await asyncio.sleep(delay)
        restart_embed.description = stage
        await msg.edit(embed=restart_embed)
    
    await asyncio.sleep(0.3)
    final_embed = discord.Embed(
        title="Restart Complete",
        description="All systems nominal.\nReady to observe.",
        color=EMBED_COLORS["success"]
    )
    final_embed.set_footer(text="NIMBROR WATCHER v6.5")
    await msg.edit(embed=final_embed)

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

@bot.tree.command(name="socialcredit", description="View social credit scores, leaderboard, or history")
async def socialcredit(interaction: discord.Interaction, mode: str = "user", user: Optional[discord.User] = None):
    """View leaderboard, user score, or infraction history."""
    scores = bot.db.get("social_credit", {})
    if not scores:
        await interaction.response.send_message(
            embed=create_embed("💳 SOCIAL CREDIT", "No data available yet."),
            ephemeral=True
        )
        return

    if mode == "leaderboard":
        # Sort by tier first, then by score
        def sort_key(item):
            uid, score = item
            tier, _ = get_citizen_tier(score)
            tier_order = {"🔴 Liability": 0, "🟠 Under Observation": 1, "🟡 Compliant Citizen": 2, "🟢 Trusted Asset": 3}
            return (tier_order.get(tier, 0), -score)
        
        sorted_users = sorted(scores.items(), key=sort_key, reverse=True)
        
        lines = []
        for i, (uid, score) in enumerate(sorted_users[:15], start=1):
            member = interaction.guild.get_member(int(uid)) if interaction.guild else None
            name = member.name if member else f"User {uid}"
            tier, _ = get_citizen_tier(score)
            lines.append(f"**#{i}** {tier} — {name}: `{score}`")
        
        embed = create_embed("🏆 SOCIAL CREDIT LEADERBOARD (Top 15)", "\n".join(lines), color=0x00ff99)
        await interaction.response.send_message(embed=embed)
        return
    
    elif mode == "liabilities":
        # Show only negative score users
        liability_scores = {uid: score for uid, score in scores.items() if score < 0}
        if not liability_scores:
            await interaction.response.send_message(
                embed=create_embed("🔴 LIABILITIES", "All citizens in compliance."),
                ephemeral=True
            )
            return
        
        sorted_liabilities = sorted(liability_scores.items(), key=lambda x: x[1])
        lines = []
        for i, (uid, score) in enumerate(sorted_liabilities[:10], start=1):
            member = interaction.guild.get_member(int(uid)) if interaction.guild else None
            name = member.name if member else f"User {uid}"
            lines.append(f"**#{i}** 🔴 {name}: `{score}`")
        
        embed = create_embed("🔴 LIABILITY CITIZENS", "\n".join(lines), color=0xff0000)
        await interaction.response.send_message(embed=embed)
        return
    
    elif mode == "history":
        if not user:
            await interaction.response.send_message("❌ Specify a user for history.", ephemeral=True)
            return
        
        uid = str(user.id)
        infractions = bot.db.get("infraction_log", {}).get(uid, [])
        
        if not infractions:
            await interaction.response.send_message(
                embed=create_embed(f"📋 HISTORY - {user.name}", "Clean record."),
                ephemeral=True
            )
            return
        
        history_text = ""
        for record in infractions[-10:]:  # Last 10
            history_text += f"**{record.get('type', '?')}** ({record.get('timestamp', '?')}): {record.get('reason', '?')}\n"
        
        embed = create_embed(f"📋 INFRACTION HISTORY - {user.name}", history_text[:2000], color=0xff6b6b)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Default: user mode
    target = user or interaction.user
    uid = str(target.id)
    score = scores.get(uid, 0)
    sorted_all = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    rank = next((i + 1 for i, (u, _) in enumerate(sorted_all) if u == uid), "Unranked")
    tier, color = get_citizen_tier(score)
    embed = create_embed(
        "💳 SOCIAL CREDIT REPORT",
        f"👤 **Citizen:** {target.mention}\n📊 **Score:** `{score}`\n🏷️ **Tier:** {tier}\n🏅 **Rank:** `{rank}`",
        color=color
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="json", description="View internal system data (admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def json_view(interaction: discord.Interaction, section: Optional[str] = None):
    """Admin-only command to view JSON database sections."""
    data = bot.db
    if section:
        content = json.dumps(data.get(section, {}), indent=2)
        title = f"📁 JSON VIEW — {section}"
    else:
        content = json.dumps(data, indent=2)
        title = "📦 FULL JSON STATE"
    if len(content) > 1900:
        content = content[:1900] + "\n...TRUNCATED..."
    embed = create_embed(title, f"```json\n{content}\n```", color=0xff4444)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="status", description="System health report")
async def status(interaction: discord.Interaction):
    """Show Watcher system status and health."""
    global LAST_SOCIAL_EVENT, LAST_SOCIAL_EVENT_TIME
    
    # Check for corruption mode
    corruption_active = should_enable_corruption()
    
    uptime = int(time.time() - START_TIME)
    hours = uptime // 3600
    minutes = (uptime % 3600) // 60
    
    # Data health check
    health = check_data_health()
    
    # Event system status
    if LAST_SOCIAL_EVENT_TIME:
        event_time = datetime.fromisoformat(LAST_SOCIAL_EVENT_TIME)
        time_ago = (datetime.now() - event_time).total_seconds() / 3600
        event_status = f"**Last Event:** {LAST_SOCIAL_EVENT[:40]}... ({time_ago:.1f}h ago)"
    else:
        event_status = "**Last Event:** None (pending...)"
    
    # Corruption mode display with special formatting
    if corruption_active:
        corruption_text = "🔴 CRITICAL - SYSTEM INSTABILITY DETECTED"
        system_status = "❌ DEGRADED"
        desc_color = 0xff0000
    else:
        corruption_text = "🟢 Normal operations"
        system_status = "✅ NOMINAL"
        desc_color = 0x00ffff
    
    # Build description - possibly corrupted if corruption is active
    description = (
        f"⏱️ **Uptime:** `{hours}h {minutes}m`\n\n"
        f"**Data Health:**\n"
        f"• Status: {health['status']}\n"
        f"• Size: `{health['size_kb']} KB`\n"
        f"• Records: `{health['records']}`\n\n"
        f"**Event System:**\n"
        f"• {event_status}\n\n"
        f"**System Status:** {system_status}\n"
        f"**Corruption:** {corruption_text}\n\n"
        f"**Active Systems:**\n"
        f"• Tickets: `{len(bot.db.get('tickets', {}))}` active\n"
        f"• Memory: `{len(bot.db.get('memory', {}))}` records\n"
        f"• Interviews: `{len(bot.db.get('interviews', {}))}` pending\n"
        f"• Citizens: `{len(bot.db.get('social_credit', {}))}` tracked"
    )
    
    # Apply corruption effect to description if active
    if corruption_active:
        description = corrupt_message(description)
    
    embed = create_embed("📡 WATCHER SYSTEM STATUS", description, color=desc_color)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="pingwatcher", description="Ping the Watcher")
async def pingwatcher(interaction: discord.Interaction):
    """Check Watcher latency and get a creepy response."""
    latency = round(bot.latency * 1000)
    creepy_lines = [
        "I responded faster than you expected. Didn't I?",
        "Were you waiting long? I'm always watching.",
        "Latency is just a suggestion.",
        "I don't sleep. I observe.",
        "Your ping arrived before you realized you sent it.",
    ]
    embed = create_embed(
        "🛰️ WATCHER PING",
        f"⏱️ **Latency:** `{latency}ms`\n🟢 **Status:** ONLINE\n\n*{random.choice(creepy_lines)}*",
        color=0x00ffff
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="prophecy", description="Receive a prophecy")
async def prophecy(interaction: discord.Interaction):
    """Get an ominous prediction from the Watcher."""
    prophecies = [
        "🌑 Someone will betray the trust placed in them.",
        "📈 The numbers will spike. Then crash.",
        "🔮 A truth will surface, buried since the beginning.",
        "⚠️ The Wall responds to observation. Be careful.",
        "👁️ Three of you will leave. Only two will return.",
        "💀 The missing data... it remembers.",
        "🧿 Something sleeps beneath the surface. It's waking.",
    ]
    embed = create_embed("🔮 PROPHECY", random.choice(prophecies), color=0x9900ff)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="shop", description="Browse and purchase items")
async def shop(interaction: discord.Interaction):
    """Display shop with purchasable items."""
    await interaction.response.defer()
    
    # Get current user credit
    user_id = str(interaction.user.id)
    current_credit = await get_user_credit(user_id)
    
    # Get all shop items
    items = await get_shop_items()
    
    if not items:
        await interaction.followup.send(
            embed=create_embed(
                "Shop",
                "No items available.",
                color=EMBED_COLORS["neutral"]
            )
        )
        return
    
    # Build shop item list with tier emojis
    item_list = "\n".join([
        f"{get_tier_emoji(item.get('tier', 'common'))} **{item['name']}** — {item['cost']} credits\n{item['description'][:60]}"
        for item in items[:10]  # Show first 10 items
    ])
    
    embed = create_embed(
        "Shop",
        f"Your credits: {current_credit}\n\n{item_list}",
        color=EMBED_COLORS["info"]
    )
    
    view = ShopItemSelect(interaction.user.id, items)
    await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name="inventory", description="View your purchased items")
async def inventory(interaction: discord.Interaction):
    """Show user's inventory."""
    await interaction.response.defer()
    
    user_id = str(interaction.user.id)
    
    # Ensure user exists
    await ensure_user_exists(user_id)
    
    # Get inventory
    inv = await get_user_inventory(user_id)
    
    if not inv:
        await interaction.followup.send(
            embed=create_embed(
                "Inventory",
                "You haven't purchased anything yet.",
                color=EMBED_COLORS["neutral"]
            )
        )
        return
    
    # Build inventory list
    inv_list = "\n".join([
        f"**{details['name']}** × {details['quantity']}"
        for details in inv.values()
    ])
    
    embed = create_embed(
        "Inventory",
        inv_list,
        color=EMBED_COLORS["success"]
    )
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="compliment", description="Compliment another user")
async def compliment(interaction: discord.Interaction, user: discord.User, message: str):
    """Send a compliment to another user and give them credit."""
    await interaction.response.defer(ephemeral=False)
    
    from_user = str(interaction.user.id)
    to_user = str(user.id)
    
    # Prevent self-compliments
    if from_user == to_user:
        await interaction.followup.send(
            embed=create_embed(
                "Invalid",
                "You cannot compliment yourself.",
                color=EMBED_COLORS["error"]
            ),
            ephemeral=True
        )
        return
    
    # Prevent bot compliments
    if user.bot:
        await interaction.followup.send(
            embed=create_embed(
                "Invalid",
                "Bots don't need compliments.",
                color=EMBED_COLORS["error"]
            ),
            ephemeral=True
        )
        return
    
    # Check cooldown
    cooldown_remaining = get_compliment_cooldown_remaining(from_user)
    if cooldown_remaining > 0:
        minutes_remaining = (cooldown_remaining // 60) + (1 if cooldown_remaining % 60 else 0)
        await interaction.followup.send(
            embed=create_embed(
                "Cooldown Active",
                f"You can compliment again in {minutes_remaining} minute(s).",
                color=EMBED_COLORS["warning"]
            ),
            ephemeral=True
        )
        return
    
    # Add compliment credit (1 credit per compliment)
    success = await add_compliment_credit(from_user, to_user, amount=1)
    
    if success:
        set_compliment_cooldown(from_user)
        embed = create_embed(
            "Compliment Sent",
            f"{user.mention} received 1 credit!\n\n\"{message}\"",
            color=EMBED_COLORS["success"]
        )
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(
            embed=create_embed(
                "Error",
                "Failed to send compliment.",
                color=EMBED_COLORS["error"]
            ),
            ephemeral=True
        )

@bot.tree.command(name="buy", description="Purchase an item directly")
async def buy(interaction: discord.Interaction, item_id: int):
    """Buy an item directly by ID without using the shop menu."""
    await interaction.response.defer(ephemeral=False)
    
    user_id = str(interaction.user.id)
    
    try:
        # Get item details
        item_response = supabase.table("shop_items").select("*").eq("id", item_id).execute()
        if not item_response.data or len(item_response.data) == 0:
            await interaction.followup.send(
                embed=create_embed(
                    "Not Found",
                    "That item doesn't exist.",
                    color=EMBED_COLORS["error"]
                )
            )
            return
        
        item = item_response.data[0]
        
        # Process purchase
        success, message, new_credit = await purchase_item(
            user_id,
            item["id"],
            item["name"],
            item["cost"]
        )
        
        if success:
            tier_emoji = get_tier_emoji(item.get("tier", "common"))
            embed = create_embed(
                "Purchase Successful",
                f"{tier_emoji} **{item['name']}**\n\nNew balance: {new_credit} credits",
                color=EMBED_COLORS["success"]
            )
        else:
            embed = create_embed(
                "Purchase Failed",
                message,
                color=EMBED_COLORS["error"]
            )
        
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await log_error(f"buy command: {str(e)}")
        await interaction.followup.send(
            embed=create_embed(
                "Error",
                "An error occurred during purchase.",
                color=EMBED_COLORS["error"]
            )
        )

@bot.tree.command(name="wishlist", description="Manage your wishlist")
@app_commands.describe(
    action="Action: add, remove, or view",
    item_id="Item ID (required for add/remove)"
)
async def wishlist(interaction: discord.Interaction, action: str, item_id: Optional[int] = None):
    """Manage wishlist: add items, remove items, or view your wishlist."""
    await interaction.response.defer(ephemeral=True)
    
    user_id = str(interaction.user.id)
    action = action.lower()
    
    if action == "add":
        if item_id is None:
            await interaction.followup.send(
                embed=create_embed(
                    "Error",
                    "Please specify an item ID to add.",
                    color=EMBED_COLORS["error"]
                )
            )
            return
        
        success, message = await add_to_wishlist(user_id, item_id)
        color = EMBED_COLORS["success"] if success else EMBED_COLORS["error"]
        embed = create_embed("Wishlist", message, color=color)
        await interaction.followup.send(embed=embed)
    
    elif action == "remove":
        if item_id is None:
            await interaction.followup.send(
                embed=create_embed(
                    "Error",
                    "Please specify an item ID to remove.",
                    color=EMBED_COLORS["error"]
                )
            )
            return
        
        success, message = await remove_from_wishlist(user_id, item_id)
        color = EMBED_COLORS["success"] if success else EMBED_COLORS["error"]
        embed = create_embed("Wishlist", message, color=color)
        await interaction.followup.send(embed=embed)
    
    elif action == "view":
        items = await get_user_wishlist(user_id)
        
        if not items:
            await interaction.followup.send(
                embed=create_embed(
                    "Wishlist",
                    "Your wishlist is empty.",
                    color=EMBED_COLORS["neutral"]
                )
            )
            return
        
        # Build wishlist display
        wishlist_text = "\n".join([
            f"{get_tier_emoji(item.get('tier', 'common'))} **{item['name']}** — {item['cost']} credits\n{item['description'][:50]}"
            for item in items
        ])
        
        embed = create_embed(
            "Wishlist",
            wishlist_text,
            color=EMBED_COLORS["info"]
        )
        await interaction.followup.send(embed=embed)
    
    else:
        await interaction.followup.send(
            embed=create_embed(
                "Invalid Action",
                "Use: add, remove, or view",
                color=EMBED_COLORS["error"]
            )
        )

@bot.tree.command(name="confess", description="Confess your sins to the Watcher")
async def confess(interaction: discord.Interaction, confession: str):
    """Confess a wrongdoing. The Watcher judges."""
    uid = str(interaction.user.id)
    
    # Check privilege
    if not can_access_feature(uid, "confess"):
        await interaction.response.send_message(
            embed=create_embed("🔴 ACCESS DENIED", "Your liability status prevents confession.", color=0xff0000),
            ephemeral=True
        )
        return
    
    judgments = [
        ("✅ Honesty noted.", 5),
        ("❌ Pathetic.", -10),
        ("🤔 Interesting. Nothing changes.", 0),
        ("⚠️ This will be recorded.", 0),
        ("😈 I appreciate the entertainment.", 0),
    ]
    
    judgment_text, credit_change = random.choice(judgments)
    
    # Apply credit change with reason
    update_social_credit(uid, credit_change, f"confess:{confession[:50]}")
    
    credit_text = ""
    if credit_change > 0:
        credit_text = f" `+{credit_change}` social credit"
    elif credit_change < 0:
        credit_text = f" `{credit_change}` social credit"
    else:
        credit_text = " No change."
    
    embed = create_embed("🧾 CONFESSION JUDGED", f"*\"{confession}\"*\n\n**Verdict:** {judgment_text}{credit_text}", color=0xff6600)
    await interaction.response.send_message(embed=embed, ephemeral=False)

def get_citizen_tier(score: int) -> tuple:
    """Get tier name and color based on social credit score."""
    if score >= 80:
        return ("🟢 Trusted Asset", 0x00ff00)
    elif score >= 30:
        return ("🟡 Compliant Citizen", 0xffff00)
    elif score >= 0:
        return ("🟠 Under Observation", 0xff9900)
    else:
        return ("🔴 Liability", 0xff0000)

@bot.tree.command(name="dossier", description="Generate a classified file on a user")
async def dossier(interaction: discord.Interaction, user: discord.User):
    """Generate a fake classified dossier with redactions."""
    uid = str(user.id)
    score = bot.db.get("social_credit", {}).get(uid, 0)
    tier, _ = get_citizen_tier(score)
    memory = bot.db.get("memory", {}).get(uid, {})
    
    redacted_notes = [
        f"Interaction count: {len(memory.get('interactions', []))} (MONITORING)",
        "██████████ [CLASSIFIED]",
        "Subject exhibits irregular patterns.",
        "██████████ [REDACTED]",
        "Compliance rating: QUESTIONABLE",
    ]
    
    content = f"""```
╔════════════════════════════════════════╗
║           CLASSIFIED DOSSIER            ║
╠════════════════════════════════════════╣
║ SUBJECT: {user.name}
║ ID: {user.id}
║ TIER: {tier}
║ SCORE: {score}
╠════════════════════════════════════════╣
║ NOTES:
"""
    for note in redacted_notes:
        content += f"║ {note}\n"
    content += "║\n╚════════════════════════════════════════╝```"
    
    embed = discord.Embed(title="📁 CLASSIFIED DOSSIER", description=content, color=0x333333)
    embed.set_footer(text="NIMBROR WATCHER v6.5 • SENSOR-NET • EYES ONLY")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="incident", description="Report a citizen for suspicious behavior")
async def incident(interaction: discord.Interaction, suspect: discord.User, reason: str):
    """Report a citizen. Bot determines if valid concern, paranoia, or false accusation."""
    uid_reporter = str(interaction.user.id)
    uid_suspect = str(suspect.id)
    
    # Check privilege
    if not can_access_feature(uid_reporter, "report"):
        await interaction.response.send_message("❌ Your privilege level prevents filing reports.", ephemeral=True)
        return
    
    # Bot verdict (random)
    verdicts = [
        ("valid_concern", "✅ **VALID CONCERN REGISTERED**", 3),  # reporter +3, suspect -5
        ("paranoia", "⚠️ **UNFOUNDED SUSPICION DETECTED**", 0),  # no change
        ("false_accusation", "❌ **FALSE ACCUSATION RECORDED**", -5),  # reporter -5
    ]
    verdict_type, verdict_text, reporter_change = random.choice(verdicts)
    
    # Apply credit changes
    update_social_credit(uid_reporter, reporter_change)
    if verdict_type == "valid_concern":
        update_social_credit(uid_suspect, -5)
    
    # Log incident
    incident_record = {
        "reporter": interaction.user.name,
        "suspect": suspect.name,
        "reason": reason,
        "verdict": verdict_type,
        "timestamp": datetime.now().isoformat()
    }
    bot.db.setdefault("incidents", []).append(incident_record)
    
    # Log to infraction_log
    bot.db.setdefault("infraction_log", {}).setdefault(uid_suspect, []).append({
        "type": verdict_type.upper(),
        "reason": reason,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    save_data(bot.db)
    
    embed = create_embed(
        "📋 INCIDENT REPORT",
        f"{verdict_text}\n\n"
        f"**Reporter:** {interaction.user.mention}\n"
        f"**Suspect:** {suspect.mention}\n"
        f"**Reason:** {reason}\n\n"
        f"*Credit adjustments applied.*",
        color=0xff6b6b
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="watchlist", description="View citizens under surveillance")
async def watchlist(interaction: discord.Interaction):
    """View vague surveillance status of under-observation citizens."""
    under_observation = []
    liability = []
    
    for uid, score in bot.db.get("social_credit", {}).items():
        if score < 0:
            liability.append((uid, score))
        elif score < 30:
            under_observation.append((uid, score))
    
    total_watched = len(under_observation) + len(liability)
    
    embed = create_embed(
        "Watchlist",
        f"Under Observation: `{len(under_observation)}`\nLiabilities: `{len(liability)}`\nTotal: `{total_watched}`",
        color=EMBED_COLORS["warning"]
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="trial", description="Moral dilemma voting challenge")
async def trial(interaction: discord.Interaction):
    """Present a moral dilemma. Minority loses social credit."""
    dilemmas = [
        {
            "text": "A citizen found 50 credits. Should they:\nA) Return it anonymously\nB) Keep it for themselves",
            "options": ["A) Return it anonymously", "B) Keep it"],
        },
        {
            "text": "You witness someone breaking a minor rule. Should you:\nA) Report them\nB) Stay silent",
            "options": ["A) Report them", "B) Stay silent"],
        },
        {
            "text": "A friend asks you to lie for them. Should you:\nA) Refuse and stay loyal to truth\nB) Agree to help your friend",
            "options": ["A) Refuse and stay loyal", "B) Agree to help"],
        },
    ]
    
    dilemma = random.choice(dilemmas)
    trial_id = f"trial_{int(time.time())}_{random.randint(1000, 9999)}"
    
    # Store trial data with message info for later lookup
    bot.db.setdefault("trials", {})[trial_id] = {
        "dilemma": dilemma['text'],
        "votes_a": [],
        "votes_b": [],
        "timestamp": time.time(),
        "closed": False,
        "message_id": None,
        "channel_id": interaction.channel_id
    }
    save_data(bot.db)
    
    embed = create_embed(
        "Moral Trial",
        f"{dilemma['text']}\n\nReact with 🅰️ (A) or 🅱️ (B) to vote. Closes in 2 minutes.",
        color=EMBED_COLORS["special"]
    )
    await interaction.response.send_message(embed=embed)
    
    # Get the actual message object for reactions
    msg = await interaction.original_response()
    
    # Store message ID for reaction tracking
    bot.db["trials"][trial_id]["message_id"] = msg.id
    save_data(bot.db)
    
    # Add emoji reactions
    await msg.add_reaction("🅰️")
    await msg.add_reaction("🅱️")

@bot.tree.command(name="task", description="Receive a micro-quest")
async def task(interaction: discord.Interaction):
    """Receive a small task. Completion affects social credit."""
    tasks_list = [
        {"name": "Be Active", "desc": "Participate in 3 conversations over the next hour", "reward": 3},
        {"name": "Speak Kindly", "desc": "Send a compliment or positive message", "reward": 2},
        {"name": "Silence", "desc": "Send no messages for 15 minutes", "reward": 1},
        {"name": "Introspection", "desc": "React thoughtfully to a message in #general", "reward": 2},
        {"name": "Community", "desc": "Start a respectful debate on a topic", "reward": 4},
    ]
    
    chosen_task = random.choice(tasks_list)
    uid = str(interaction.user.id)
    task_id = f"task_{uid}_{int(time.time())}"
    
    # Store task
    bot.db.setdefault("tasks", {})[task_id] = {
        "user_id": uid,
        "task": chosen_task["name"],
        "timestamp": time.time(),
        "completed": False
    }
    save_data(bot.db)
    
    embed = create_embed(
        "Task Assigned",
        f"**{chosen_task['name']}**\n{chosen_task['desc']}\n\nReward: +{chosen_task['reward']} credits",
        color=EMBED_COLORS["info"]
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="marry", description="Bind two souls together")
async def marry(interaction: discord.Interaction, user1: discord.User, user2: discord.User):
    """Unite two users in eternal matrimonial contract. Witnessed by the Watcher."""
    # Prevent self-marriage
    if user1.id == user2.id:
        await interaction.response.send_message(
            embed=create_embed(
                "Invalid",
                "A soul cannot bind itself.",
                color=EMBED_COLORS["error"]
            ),
            ephemeral=True
        )
        return
    
    # Prevent bot marriage
    if user1.bot or user2.bot:
        await interaction.response.send_message(
            embed=create_embed(
                "Prohibited",
                "Artificial entities cannot enter contract.",
                color=EMBED_COLORS["error"]
            ),
            ephemeral=True
        )
        return
    
    # Store marriage record
    marriage_id = f"marriage_{int(time.time())}_{random.randint(10000, 99999)}"
    bot.db.setdefault("marriages", {})[marriage_id] = {
        "user1_id": str(user1.id),
        "user2_id": str(user2.id),
        "user1_name": user1.name,
        "user2_name": user2.name,
        "timestamp": datetime.now().isoformat(),
        "witnessed_by": str(interaction.user.id)
    }
    save_data(bot.db)
    
    # Apply social credit bonus for both users
    update_social_credit(str(user1.id), 15, "married")
    update_social_credit(str(user2.id), 15, "married")
    
    # Create marriage announcement embed
    embed = discord.Embed(
        title="Eternal Binding",
        color=EMBED_COLORS["special"],
        timestamp=datetime.now()
    )
    embed.add_field(
        name="Soul 1",
        value=f"{user1.mention}",
        inline=True
    )
    embed.add_field(
        name="Soul 2",
        value=f"{user2.mention}",
        inline=True
    )
    embed.add_field(
        name="Status",
        value="Two souls intertwined.\nThe Watcher has recorded this union.",
        inline=False
    )
    embed.set_footer(text="NIMBROR WATCHER v6.5")
    
    await interaction.response.send_message(embed=embed)
    
    # Send to announcement channel if available
    if ANNOUNCE_CHANNEL_ID:
        try:
            announce_ch = bot.get_channel(ANNOUNCE_CHANNEL_ID)
            if announce_ch:
                await announce_ch.send(embed=embed)
        except:
            pass

# --- EVENTS ---
@bot.event
async def on_ready():
    """Send startup progress bar when bot connects to all server channels."""
    if not bot.user:
        return
    
    progress_stages = [
        ("🔴 [░░░░░░░░░░] 0% - INITIALIZING SYSTEMS", 0.1),
        ("🟡 [██░░░░░░░░] 20% - BOOTING SURVEILLANCE ARRAYS", 0.1),
        ("🟡 [████░░░░░░] 40% - SCANNING THE ICE WALL", 0.1),
        ("🟡 [██████░░░░] 60% - MONITORING COMMUNICATIONS", 0.1),
        ("🟡 [████████░░] 80% - VERIFYING CONSPIRACY NETWORKS", 0.1),
        ("🟢 [██████████] 100% - WATCHER ONLINE", 0.2),
    ]
    
    startup_embed = discord.Embed(
        title="Boot Sequence",
        description="Initializing systems...",
        color=EMBED_COLORS["warning"],
        timestamp=datetime.now()
    )
    startup_embed.set_footer(text="NIMBROR WATCHER v6.5")
    
    # Send to all available channels in the server
    sent_messages = []
    for guild in bot.guilds:
        for channel in guild.text_channels:
            try:
                msg = await channel.send(embed=startup_embed)
                sent_messages.append(msg)
            except discord.Forbidden:
                continue
            except Exception as e:
                continue
    
    # Update all sent messages with progress
    if sent_messages:
        for stage, delay in progress_stages:
            await asyncio.sleep(delay)
            startup_embed.description = stage
            for msg in sent_messages:
                try:
                    await msg.edit(embed=startup_embed)
                except:
                    continue
        
        await asyncio.sleep(0.5)
        final_embed = discord.Embed(
            title="System Online",
            description="All sensors operational.\nWatcher is watching.",
            color=EMBED_COLORS["success"],
            timestamp=datetime.now()
        )
        final_embed.set_footer(text="NIMBROR WATCHER v6.5")
        for msg in sent_messages:
            try:
                await msg.edit(embed=final_embed)
            except:
                continue

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
async def on_reaction_add(reaction, user):
    """Track trial votes when users react to trial messages."""
    if user.bot:
        return
    
    try:
        # Check if this is a trial message
        for trial_id, trial_data in bot.db.get("trials", {}).items():
            if trial_data.get("message_id") == reaction.message.id and not trial_data.get("closed"):
                uid = str(user.id)
                
                # Register vote based on emoji
                if reaction.emoji == "🅰️":
                    if uid not in trial_data["votes_a"]:
                        trial_data["votes_a"].append(uid)
                    # Remove from other vote if they changed their vote
                    if uid in trial_data["votes_b"]:
                        trial_data["votes_b"].remove(uid)
                
                elif reaction.emoji == "🅱️":
                    if uid not in trial_data["votes_b"]:
                        trial_data["votes_b"].append(uid)
                    # Remove from other vote if they changed their vote
                    if uid in trial_data["votes_a"]:
                        trial_data["votes_a"].remove(uid)
                
                save_data(bot.db)
                break
    except Exception as e:
        print(f"⚠️ on_reaction_add error: {e}")

@bot.event
async def on_reaction_remove(reaction, user):
    """Handle vote removal when users remove their reaction."""
    if user.bot:
        return
    
    try:
        # Check if this is a trial message
        for trial_id, trial_data in bot.db.get("trials", {}).items():
            if trial_data.get("message_id") == reaction.message.id and not trial_data.get("closed"):
                uid = str(user.id)
                
                # Remove vote based on emoji
                if reaction.emoji == "🅰️" and uid in trial_data["votes_a"]:
                    trial_data["votes_a"].remove(uid)
                
                elif reaction.emoji == "🅱️" and uid in trial_data["votes_b"]:
                    trial_data["votes_b"].remove(uid)
                
                save_data(bot.db)
                break
    except Exception as e:
        print(f"⚠️ on_reaction_remove error: {e}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    uid = str(message.author.id)
    
    # Track activity
    bot.db.setdefault("last_message_time", {})[uid] = time.time()

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
                
                # Apply corruption if corruption mode is active
                if should_enable_corruption():
                    ai_response = corrupt_message(ai_response)
                
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
                # Use CONCISE mode for pings - strict constraints (max 120 tokens, plain text only)
                ai_response = await run_huggingface_concise(
                    f"User (in a Discord server called Nimbror) says: {message.content[:200]}"
                )
                
                # Hard clamp response length to prevent rambling
                ai_response = clamp_response(ai_response, max_chars=500)
                
                # Store memory and give engagement bonus
                add_memory(uid_mention, "interaction", f"Mention: {message.content[:100]}")
                update_social_credit(uid_mention, 1)
                
                # Send as plain reply (feels more like conversation, less formal than embeds)
                await message.reply(ai_response)

    except Exception as e:
        await log_error(f"on_message: {type(e).__name__}: {str(e)[:200]}")
    
    # CRITICAL: Allow slash commands to process
    await bot.process_commands(message)

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
