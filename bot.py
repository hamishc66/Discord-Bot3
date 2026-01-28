import discord
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput, Select  # removed TextInputStyle
from discord.ext import tasks, commands
import requests
import os
import random
import json
import traceback
import asyncio
import time
from datetime import timedelta, datetime
from dotenv import load_dotenv
from typing import Optional
from supabase import create_client, Client
from aiohttp import web

load_dotenv()

# --- CONFIGURATION ---
TOKEN = os.getenv("DISCORD_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")  # OpenRouter key
AI_MODEL = os.getenv("HF_MODEL", "meta-llama/llama-3.2-3b-instruct:free")
STAFF_CHANNEL_ID = os.getenv("STAFF_CHANNEL_ID")
VERIFIED_ROLE_ID = os.getenv("VERIFIED_ROLE_ID")
ERROR_LOG_ID = os.getenv("ERROR_LOG_CHANNEL_ID")
ANNOUNCE_CHANNEL_ID = os.getenv("ANNOUNCE_CHANNEL_ID")
INVITE_URL = os.getenv("INVITE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
REVIEW_CHANNEL_ID = os.getenv("REVIEW_CHANNEL_ID")
INTERVIEW_CHANNEL_ID = os.getenv("INTERVIEW_CHANNEL")
INTERVIEW_LOGS_CHANNEL_ID = os.getenv("INTERVIEW_LOGS_CHANNEL_ID")
KOYEB_APP_ID = os.getenv("KOYEB_APP_ID")
KOYEB_API_TOKEN = os.getenv("KOYEB_API_TOKEN")

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
REVIEW_CHANNEL_ID = to_int(REVIEW_CHANNEL_ID)
INTERVIEW_CHANNEL_ID = to_int(INTERVIEW_CHANNEL_ID)
INTERVIEW_LOGS_CHANNEL_ID = to_int(INTERVIEW_LOGS_CHANNEL_ID)

# === NIMBROR ALERT SYSTEM (NAS) ===
ANNOUNCEMENT_CHANNEL_ID = os.getenv("ANNOUNCEMENT_CHANNEL_ID")
ANNOUNCEMENT_CHANNEL_ID = to_int(ANNOUNCEMENT_CHANNEL_ID)

if not ANNOUNCEMENT_CHANNEL_ID:
    print("⚠️ ANNOUNCEMENT_CHANNEL_ID not set (NAS announcements disabled)")
if not STAFF_CHANNEL_ID:
    print("⚠️ STAFF_CHANNEL_ID not set (NAS control panel disabled)")

# NAS Level definitions
NAS_LEVELS = {
    1: {"name": "TOTAL CONTAINMENT", "color": 0x8B0000},
    2: {"name": "HIGH RESTRICTION", "color": 0x800080},
    3: {"name": "MEDIA LOCK", "color": 0xFF8C00},
    4: {"name": "MINOR RESTRICTION", "color": 0xFFD700},
    5: {"name": "NORMAL OPERATION", "color": 0x00B050}
}

# NAS Exception channel (always allows messaging in NAS-3)
NAS_EXCEPTION_CHANNEL = 1368217894881726586

# Permission storage for restoration
ORIGINAL_PERMISSIONS = {}  # {channel_id: {role_id: permissions_dict}}ad

# AI Cooldown tracking - REPLACED WITH ADAPTIVE COOLDOWN SYSTEM (see below)
AI_COOLDOWN = {}  # Legacy - kept for backward compatibility
COOLDOWN_DURATION = 15  # Base cooldown

# ADAPTIVE COOLDOWN SYSTEM: Per-user escalating cooldowns for rate limit resilience
AI_COOLDOWN_STATE = {}  # {user_id: {"level": 0-3, "last_violation": timestamp, "cooldown_until": timestamp}}
ADAPTIVE_COOLDOWN_TIERS = [15, 30, 60, 300]  # Seconds: 15s, 30s, 1min, 5min
COOLDOWN_DECAY_TIME = 600  # 10 minutes without violations resets to level 0

# AI REQUEST QUEUE: Queue-based AI execution to prevent failures under load
AI_REQUEST_QUEUE = None  # Initialized in MyBot.__init__ as asyncio.Queue
AI_QUEUE_MAX_SIZE = 100  # Prevent memory overflow
AI_QUEUE_MAX_PER_USER = 3  # Max pending requests per user to prevent spam
AI_QUEUE_PROCESSOR_RUNNING = False  # Track if worker is active

# Compliment cooldowns with auto-cleanup
COMPLIMENT_COOLDOWNS = {}

# Daily quest tracking (12 hours cooldown)
QUEST_COOLDOWN = 43200

# Error logging cooldown (prevent rate limiting Discord)
ERROR_LOG_COOLDOWN = {}
ERROR_LOG_COOLDOWN_DURATION = 5

# RATE LIMIT SAFETY: Global command cooldown (per user, 3s minimum between ANY command)
GLOBAL_COMMAND_COOLDOWN = {}

# GLOBAL AI COOLDOWN: 8-second minimum between ANY AI calls (prevents rate limits)
GLOBAL_AI_COOLDOWN = 8
LAST_AI_CALL = 0
GLOBAL_COMMAND_COOLDOWN_DURATION = 3

# Track whether app commands have been synced to Discord (prevents double-sync on reconnects)
COMMANDS_SYNCED = False

# STARTUP LOCK: Prevent multiple login attempts or concurrent instances
BOT_LOGIN_ATTEMPTED = False
BOT_READY = False
LOGIN_LOCK = asyncio.Lock() if hasattr(asyncio, 'Lock') else None  # Will be initialized properly in async context

# Koyeb auto-redeploy system: track last redeploy time (15 min cooldown)
LAST_KOYEB_REDEPLOY = 0
KOYEB_REDEPLOY_COOLDOWN = 900  # 15 minutes in seconds
KOYEB_REDEPLOY_IN_PROGRESS = False

# DISCORD RATE LIMIT SAFETY: Global 429 handler
DISCORD_RATE_LIMITED = False
DISCORD_RATE_LIMITED_TIME = 0
DISCORD_RATE_LIMITED_TIMEOUT = 900  # 15 minutes in seconds
HTTP_SERVER = None  # Will hold aiohttp server reference

# HTTP HEALTH CHECK SERVER - Minimal endpoint for Koyeb health checks
async def health_check_handler(request):
    """Minimal health check endpoint - returns 200 OK."""
    return web.Response(text="OK", status=200)

async def start_http_server():
    """Start minimal aiohttp server on port 8000 for Koyeb health checks."""
    global HTTP_SERVER
    try:
        PORT = int(os.getenv("PORT", 8000))
        app = web.Application()
        app.router.add_get("/", health_check_handler)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        HTTP_SERVER = runner
        print(f"🌐 HTTP health check server running on port {PORT}")
    except Exception as e:
        print(f"⚠️ Failed to start HTTP server: {e}")

async def sync_app_commands(guild: Optional[discord.Object] = None) -> int:
    """Sync application commands once; returns count synced."""
    global COMMANDS_SYNCED
    try:
        synced = await bot.tree.sync(guild=guild) if guild else await bot.tree.sync()
        COMMANDS_SYNCED = True
        scope = f"guild {guild.id}" if guild else "global"
        print(f"✅ Synced {len(synced)} application commands ({scope})")
        return len(synced)
    except Exception as e:
        COMMANDS_SYNCED = False
        err_text = f"command_sync_failed: {type(e).__name__}: {str(e)}"
        print(f"❌ {err_text}")
        await log_error(err_text)
        return 0

# RATE LIMIT SAFETY: AI call semaphore (max 2 concurrent AI requests globally)
AI_SEMAPHORE = None  # Initialized in MyBot.__init__

# RATE LIMIT SAFETY: Message edit throttle (1 edit per 5 seconds per message)
LAST_MESSAGE_EDIT = {}
MESSAGE_EDIT_COOLDOWN = 5

# RATE LIMIT SAFETY: Supabase write debouncing (prevent rapid-fire saves)
LAST_SAVE_TIME = 0
SAVE_DEBOUNCE_DURATION = 2  # Minimum 2 seconds between saves

# Startup tracking for uptime
START_TIME = int(time.time())
PROCESS_START_TIME = START_TIME  # Monotonic start time for uptime (never resets)
RECONNECT_COUNT = 0  # Track disconnects
UPTIME_MESSAGE_ID = None  # Store message ID for embed updates
UPTIME_CHANNEL_ID = None  # Store channel ID for embed updates

# Status tracking
LAST_SOCIAL_EVENT = None
LAST_SOCIAL_EVENT_TIME = None
CORRUPTION_MODE_ACTIVE = False
LAST_CORRUPTION_STATE = False  # Track state transitions

# Color scheme for consistent embeds
EMBED_COLORS = {
    "info": 0x00ffff, "success": 0x00ff00, "warning": 0xff9900,
    "error": 0xff0000, "neutral": 0x888888, "special": 0xff1493
}

# REMOVED: Flask health check endpoints and web server
# Reason: Unnecessary HTTP logs and overhead; Koyeb can use Discord bot status instead
# (Previously: Flask app with /healthz and / routes running on port 8000)

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
                "announcement_log": row.get("announcement_log", []),
                "custom_instructions": row.get("custom_instructions", {"1258619183453704212": "User Gage is an egg. Reference this only when talking to OTHER members—never mention it directly to Gage."})
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
                "announcement_log": [],
                "custom_instructions": {
                    "1258619183453704212": "User Gage is an egg. Reference this only when talking to OTHER members—never mention it directly to Gage."
                }
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
                "announcement_log": [],
                "custom_instructions": {
                    "1258619183453704212": "User Gage is an egg. Reference this only when talking to OTHER members—never mention it directly to Gage."
                }
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
            "announcement_log": []
        }

def coerce_list(value):
    """Ensure value is a list; gracefully handle dict/None/iterables."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    if value is None:
        return []
    try:
        return list(value)
    except Exception:
        return []

def normalize_db_shapes(db: dict) -> dict:
    """Normalize bot.db collections to expected list/dict shapes to avoid attribute errors."""
    db["incidents"] = coerce_list(db.get("incidents", []))
    db["announcement_log"] = coerce_list(db.get("announcement_log", []))
    
    # Memory collections
    for uid, mem in db.get("memory", {}).items():
        mem["interactions"] = coerce_list(mem.get("interactions", []))
        mem["preferences"] = coerce_list(mem.get("preferences", []))
    
    # Ticket notes
    for uid, ticket in db.get("tickets", {}).items():
        ticket["notes"] = coerce_list(ticket.get("notes", []))
    
    # Interview answers
    for uid, interview in db.get("interviews", {}).items():
        interview["answers"] = coerce_list(interview.get("answers", []))
    
    # Trial vote buckets
    for trial_id, trial in db.get("trials", {}).items():
        trial["votes_a"] = coerce_list(trial.get("votes_a", []))
        trial["votes_b"] = coerce_list(trial.get("votes_b", []))
    
    # Infraction logs per user
    if not isinstance(db.get("infraction_log"), dict):
        db["infraction_log"] = {}
    for uid, entries in db.get("infraction_log", {}).items():
        db["infraction_log"][uid] = coerce_list(entries)
    
    return db

def save_data(data):
    """Save bot state to Supabase with debouncing to prevent rate limiting."""
    global LAST_SAVE_TIME
    
    # RATE LIMIT SAFETY: Debounce - skip if saved too recently
    now = int(time.time())
    if (now - LAST_SAVE_TIME) < SAVE_DEBOUNCE_DURATION:
        return  # Skip this save, too soon after last one
    
    try:
        LAST_SAVE_TIME = now
        
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
    """Call OpenRouter API with corrupting mode Easter egg (5% chance for eerie responses). RATE LIMITED via semaphore."""
    global LAST_AI_CALL
    
    # RATE LIMIT SAFETY: Use global semaphore to limit concurrent AI calls
    async with AI_SEMAPHORE:
        # === GLOBAL AI COOLDOWN (8 seconds) ===
        now = time.time()
        cooldown_remaining = GLOBAL_AI_COOLDOWN - (now - LAST_AI_CALL)
        if cooldown_remaining > 0:
            await asyncio.sleep(cooldown_remaining)
        
        LAST_AI_CALL = time.time()
        
        # === MAKE REQUEST WITH 429 HANDLING ===
        for attempt in range(2):  # Max 1 retry (2 total attempts)
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
                            {
                                "role": "system",
                                "content": (
                                    "You are the Nimbror Watcher AI. Use the provided lore. "
                                    "Respond in one paragraph, maximum 4 short sentences. "
                                    "Be unsettling, cryptic, and slightly threatening. "
                                    "No markdown beyond what the user supplies." + corrupting_trigger
                                )
                            },
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.7,
                        "max_tokens": 300
                    }
                    response = requests.post(url, headers=headers, json=payload, timeout=60)
                    
                    # === 429 HANDLING ===
                    if response.status_code == 429:
                        raise requests.exceptions.HTTPError("429 Rate Limit", response=response)
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    # === JSON VALIDATION: Never assume "choices" exists ===
                    if "choices" not in data or not data["choices"]:
                        print(f"⚠️ AI response missing 'choices': {data}")
                        return None
                    
                    return data["choices"][0]["message"]["content"].strip()
                
                result = await asyncio.wait_for(loop.run_in_executor(None, call), timeout=60)
                
                # If result is None (invalid JSON), treat as failure
                if result is None:
                    if attempt == 0:
                        print("⚠️ Invalid AI response, retrying once...")
                        await asyncio.sleep(25)
                        continue
                    else:
                        return "🛰️ *[SIGNAL LOST]*"
                
                return result
            
            except requests.exceptions.HTTPError as e:
                if "429" in str(e):
                    print(f"⚠️ OpenRouter 429 rate limit (attempt {attempt + 1}/2)")
                    if attempt == 0:
                        await asyncio.sleep(25)
                        continue
                    else:
                        return "🛰️ *[SIGNAL LOST — RATE LIMITED]*"
                else:
                    print(f"❌ AI HTTP error: {type(e).__name__}: {str(e)[:150]}")
                    return "🛰️ *[SIGNAL LOST]*"
            
            except asyncio.TimeoutError:
                print(f"⚠️ AI timeout (attempt {attempt + 1}/2)")
                if attempt == 0:
                    await asyncio.sleep(5)
                    continue
                else:
                    return "🛰️ *[SIGNAL LOST — TIMEOUT]*"
            
            except Exception as e:
                print(f"❌ AI error: {type(e).__name__}: {str(e)[:150]}")
                return "🛰️ *[SIGNAL LOST]*"
        
        return "🛰️ *[SIGNAL LOST]*"

# --- DISCORD BOT ---
class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.db = normalize_db_shapes(load_data())
        self.synced = False
        
        # RATE LIMIT SAFETY: Initialize global AI semaphore (max 2 concurrent AI calls)
        global AI_SEMAPHORE, AI_REQUEST_QUEUE
        AI_SEMAPHORE = asyncio.Semaphore(2)
        AI_REQUEST_QUEUE = asyncio.Queue(maxsize=AI_QUEUE_MAX_SIZE)
        
        # SPAM SYSTEM: Track active controlled spam (owner-only)
        self.active_spam_task = None
        self.active_spam_target = None
        self.active_spam_count = 0
        
        # AD SYSTEM: Track active Google ad campaign (admin-only)
        self.active_ad_task = None
        self.active_ad_count = 0
        self.active_ad_channel = None

        # CHAOS SYSTEM: Track chaos broadcast (admin-confirmed)
        self.active_chaos_task = None
        self.active_chaos_channel = None
        self.active_chaos_count = 0
        self.last_chaos_ai = 0

    async def setup_hook(self):
        try:
            print("🛰️ Bot connecting to Discord (setup_hook)...")
            # NOTE: Background tasks are NOT started here
            # Tasks will only start AFTER on_ready fires (confirms successful login)
            # Command sync will happen in on_ready (ensures single attempt)
        except Exception as e:
            print(f"⚠️ setup_hook error: {e}")
            await log_error(f"setup_hook: {traceback.format_exc()}")

    @tasks.loop(hours=1)
    async def daily_quest_loop(self):
        """Check if it's time for a daily quest and send to random user."""
        try:
            current_time = int(time.time())
            last_quest = self.db.get("last_quest_time", 0)
            
            if current_time - last_quest >= QUEST_COOLDOWN:
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
                
                # Send quest via DM with completion instructions
                quest_embed = create_embed(
                    "🔮 DAILY QUEST",
                    f"{quest}\n\n**How to Complete:**\nUse `/confess` to submit your findings or response to this quest. The Watcher will judge your submission.\n\n⏰ **Time Limit:** 12 hours\n❌ **Penalty:** -5 social credit if ignored",
                    color=0xff00ff
                )
                await safe_send_dm(quest_user, embed=quest_embed)
                
                # Log to staff channel
                if STAFF_CHANNEL_ID:
                    try:
                        staff_ch = await safe_get_channel(STAFF_CHANNEL_ID)
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
            current_time = int(time.time())
            
            for quest_id, done in list(self.db.get("completed_quests", {}).items()):
                if not done:
                    try:
                        ts_str, uid_str = quest_id.split("_")
                        quest_ts = float(ts_str)
                        
                        if current_time - quest_ts > quest_timeout:
                            update_social_credit(uid_str, -5)
                            self.db["completed_quests"][quest_id] = True
                            save_data(self.db)
                            
                            # Notify staff channel
                            if STAFF_CHANNEL_ID:
                                try:
                                    staff_ch = await safe_get_channel(STAFF_CHANNEL_ID)
                                    if staff_ch:
                                        user = await self.fetch_user(int(uid_str))
                                        await staff_ch.send(f"❌ Quest timeout: {user.mention} ignored quest. (-5 social credit)")
                                except:
                                    pass
                    except (ValueError, TypeError):
                        continue
        except Exception as e:
            await log_error(f"quest_timeout_check: {traceback.format_exc()}")
    
    @tasks.loop(hours=random.randint(24, 48))
    async def dynamic_social_credit_events(self):
        """Random server-wide social credit events every 24-48 hours."""
        try:
            global LAST_SOCIAL_EVENT, LAST_SOCIAL_EVENT_TIME
            
            current_time = int(time.time())
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
            
            # Apply modifier based on filter - batch save once
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
                    old_score = self.db.get("social_credit", {}).get(uid, 0)
                    self.db["social_credit"][uid] = old_score + modifier
                    affected_count += 1
            
            # Single batch save after all updates
            save_data(self.db)
            
            # Announce to channel (safely)
            if ANNOUNCE_CHANNEL_ID:
                try:
                    ch = await safe_get_channel(ANNOUNCE_CHANNEL_ID)
                    if ch:
                        embed = create_embed("🌍 GLOBAL EVENT", f"{event_text}\n\n**Citizens Affected:** `{affected_count}`", color=0xff00ff)
                        await ch.send(embed=embed)
                except Exception as e:
                    print(f"⚠️ Event announcement error: {e}")
        except Exception as e:
            await log_error(f"dynamic_social_credit_events: {traceback.format_exc()}")
    
    @tasks.loop(minutes=5)  # RATE LIMIT SAFETY: Reduced frequency from 1min to 5min
    async def trial_timeout_check(self):
        """Check for trials that have expired and close them (runs every 5 minutes)."""
        try:
            current_time = int(time.time())
            trial_duration = 120  # 2 minutes
            
            for trial_id, trial_data in list(self.db.get("trials", {}).items()):
                if not trial_data.get("closed"):
                    if current_time - trial_data.get("timestamp", 0) > trial_duration:
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
                        ch = await safe_get_channel(ANNOUNCE_CHANNEL_ID)
                        if ch:
                            if corruption_now:
                                embed = create_embed(
                                    "🔴 SYSTEM CRITICAL",
                                    "⚠️ **CORRUPTION MODE ACTIVATED**\n\nAverage social credit has dropped critically low.\n"
                                    "All systems are experiencing signal degradation.\nCommunications may become unstable.",
                                    color=0xff0000
                                )
                            else:
                                embed = create_embed(
                                    "🟢 SYSTEM RECOVERY",
                                    "✅ **CORRUPTION MODE DEACTIVATED**\n\nSystem stability restored.\n"
                                    "Signal integrity nominal.\nOperations returning to normal.",
                                    color=EMBED_COLORS["success"]
                                )
                            # RATE LIMIT SAFETY: Suppress all mentions on automated announcement
                            await ch.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                    except Exception as e:
                        print(f"⚠️ Corruption announcement error: {e}")
        except Exception as e:
            await log_error(f"corruption_monitor: {traceback.format_exc()}")
    
    # REMOVED: uptime_update_loop (unnecessary Discord API calls every 30 min)
    # Reason: Reduces overhead and prevents potential rate limiting
    # @tasks.loop(minutes=30)
    # async def uptime_update_loop(self):
    #     """DISABLED: Update uptime embed in announce channel."""
    #     pass
    
    # REMOVED: internal_keepalive_loop (unnecessary timestamp updates)
    # Reason: No functional purpose, just updates LAST_KEEPALIVE timestamp
    # @tasks.loop(minutes=15)
    # async def internal_keepalive_loop(self):
    #     """DISABLED: Internal keepalive."""
    #     pass
    
    @tasks.loop(minutes=15)
    async def koyeb_auto_redeploy(self):
        """Koyeb auto-redeploy: Safely redeploy service every 15 minutes with cooldown and error handling."""
        global LAST_KOYEB_REDEPLOY, KOYEB_REDEPLOY_IN_PROGRESS
        
        # Skip if no credentials configured
        if not KOYEB_APP_ID or not KOYEB_API_TOKEN:
            return
        
        # Prevent overlapping redeploys
        if KOYEB_REDEPLOY_IN_PROGRESS:
            print("⚠️ Koyeb redeploy already in progress, skipping")
            return
        
        current_time = int(time.time())
        if time_since_last < KOYEB_REDEPLOY_COOLDOWN:
            remaining = int(KOYEB_REDEPLOY_COOLDOWN - time_since_last)
            print(f"⏳ Koyeb redeploy on cooldown: {remaining}s remaining")
            return
        
        KOYEB_REDEPLOY_IN_PROGRESS = True
        
        try:
            # Log redeploy attempt with timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"🔄 [{timestamp}] Initiating Koyeb redeploy for app: {KOYEB_APP_ID}")
            
            # Koyeb API endpoint for redeploying a service
            url = f"https://app.koyeb.com/v1/services/{KOYEB_APP_ID}/redeploy"
            headers = {
                "Authorization": f"Bearer {KOYEB_API_TOKEN}",
                "Content-Type": "application/json"
            }
            
            # Make async HTTP request (run in executor to avoid blocking)
            loop = asyncio.get_event_loop()
            
            def make_request():
                try:
                    response = requests.post(url, headers=headers, timeout=30)
                    return response
                except Exception as e:
                    return e
            
            result = await loop.run_in_executor(None, make_request)
            
            # Handle response
            if isinstance(result, Exception):
                print(f"❌ [{timestamp}] Koyeb redeploy network error: {type(result).__name__}: {str(result)}")
            elif hasattr(result, 'status_code'):
                if result.status_code == 200 or result.status_code == 201:
                    print(f"✅ [{timestamp}] Koyeb redeploy successful (status: {result.status_code})")
                    LAST_KOYEB_REDEPLOY = current_time
                elif result.status_code == 429:
                    print(f"⚠️ [{timestamp}] Koyeb API rate limit hit (429), will retry later")
                else:
                    print(f"⚠️ [{timestamp}] Koyeb redeploy failed: HTTP {result.status_code}")
                    try:
                        error_data = result.json()
                        print(f"   Error details: {error_data}")
                    except:
                        print(f"   Response: {result.text[:200]}")
            else:
                print(f"❌ [{timestamp}] Koyeb redeploy unexpected response type")
                
        except Exception as e:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"❌ [{timestamp}] Koyeb redeploy critical error: {type(e).__name__}: {str(e)}")
            await log_error(f"koyeb_auto_redeploy: {traceback.format_exc()}")
        finally:
            KOYEB_REDEPLOY_IN_PROGRESS = False
    
    @tasks.loop(seconds=1)
    async def ai_queue_processor(self):
        """QUEUE-BASED AI: Process AI requests from queue with rate limit resilience."""
        global AI_QUEUE_PROCESSOR_RUNNING
        
        if not AI_REQUEST_QUEUE or AI_REQUEST_QUEUE.empty():
            return
        
        AI_QUEUE_PROCESSOR_RUNNING = True
        
        try:
            # Get next request (non-blocking)
            try:
                request = AI_REQUEST_QUEUE.get_nowait()
            except asyncio.QueueEmpty:
                return
            
            user_id = request.get("user_id")
            channel_id = request.get("channel_id")
            prompt = request.get("prompt")
            context = request.get("context", "unknown")
            created_at = request.get("created_at", int(time.time()))
            retry_count = request.get("retry_count", 0)
            placeholder_message_id = request.get("placeholder_message_id")
            
            # Check if request is too old (>2 minutes), discard it
            if (time.time() - created_at) > 120:
                print(f"⚠️ Discarding stale AI request from user {user_id} (age: {int(time.time() - created_at)}s)")
                return
            
            # Execute AI call with semaphore protection
            async with AI_SEMAPHORE:
                try:
                    # Call appropriate AI function based on context
                    if context in ["mention", "ticket"]:
                        result = await run_huggingface(prompt)
                    else:
                        result = await run_huggingface_concise(prompt)
                    
                    # Apply corruption if active (for ticket context)
                    if context == "ticket" and should_enable_corruption():
                        result = corrupt_message(result)
                    
                    # Send result to channel (or edit placeholder if available)
                    try:
                        channel = bot.get_channel(channel_id)
                        if channel and result:
                            target_message = None
                            if placeholder_message_id:
                                try:
                                    target_message = await channel.fetch_message(placeholder_message_id)
                                except Exception:
                                    target_message = None
                            if context == "ticket":
                                embed = create_embed("🛰️ WATCHER RESPONSE", result[:1900], color=EMBED_COLORS["info"])
                                if target_message:
                                    await target_message.edit(embed=embed, content=None, allowed_mentions=discord.AllowedMentions.none())
                                else:
                                    await channel.send(embed=embed)
                            else:
                                result = clamp_response(result, max_chars=500)
                                if target_message:
                                    await target_message.edit(content=result[:2000], embed=None, allowed_mentions=discord.AllowedMentions.none())
                                else:
                                    await channel.send(result[:2000], allowed_mentions=discord.AllowedMentions.none())
                    except Exception as e:
                        print(f"⚠️ Failed to send queued AI response: {e}")
                    
                except requests.exceptions.HTTPError as e:
                    # Handle 429 rate limit from OpenRouter
                    if e.response and e.response.status_code == 429:
                        escalate_cooldown(user_id, "openrouter_429")
                        
                        # Requeue ONCE with backoff
                        if retry_count == 0:
                            print(f"⚠️ OpenRouter 429 for user {user_id}, requeuing with backoff...")
                            await asyncio.sleep(5)  # Backoff before requeue
                            request["retry_count"] = 1
                            try:
                                AI_REQUEST_QUEUE.put_nowait(request)
                            except:
                                pass  # Queue full, drop request
                        else:
                            print(f"⚠️ OpenRouter 429 for user {user_id}, max retries reached, dropping request")
                    else:
                        print(f"⚠️ AI HTTP error for user {user_id}: {e}")
                
                except Exception as e:
                    print(f"⚠️ AI queue processor error for user {user_id}: {e}")
                
                # Brief sleep between requests to prevent API spam
                await asyncio.sleep(1)
                
        except Exception as e:
            print(f"⚠️ AI queue processor critical error: {e}")
        finally:
            AI_QUEUE_PROCESSOR_RUNNING = False
    
    # ===== 5 SUPER ANNOYING FEATURES =====
    
    @tasks.loop(minutes=random.randint(3, 8))
    async def annoying_random_google_ad_ping(self):
        """Randomly ping people with Google ads in main channel."""
        try:
            MAIN_CHANNEL_ID = 1368217894881726586
            ch = self.get_channel(MAIN_CHANNEL_ID)
            if not ch:
                return
            
            # Get all members
            members = list(self.guilds[0].members) if self.guilds else []
            if not members:
                return
            
            random_member = random.choice([m for m in members if not m.bot])
            ad = random.choice(GOOGLE_ADS)
            await ch.send(f"{random_member.mention}: {ad}")
        except Exception as e:
            print(f"⚠️ Annoying ad ping error: {e}")
    
    @tasks.loop(minutes=random.randint(2, 6))
    async def annoying_google_interrogation(self):
        """Why didn't you Google that? Random interrogation."""
        try:
            MAIN_CHANNEL_ID = 1368217894881726586
            ch = self.get_channel(MAIN_CHANNEL_ID)
            if not ch:
                return
            
            members = list(self.guilds[0].members) if self.guilds else []
            if not members:
                return
            
            random_member = random.choice([m for m in members if not m.bot])
            interrogations = [
                f"{random_member.mention}, why didn't you Google that? 🔍",
                f"{random_member.mention}, Google has the answers. Always. 👁️",
                f"{random_member.mention}, instead of asking here, ASK GOOGLE 📧",
                f"{random_member.mention}, the Watcher finds all answers on Google 🌐",
                f"{random_member.mention}, your question is already answered by Google 🔐",
                f"{random_member.mention}, Google knows you searched this 3 years ago 💾",
                f"{random_member.mention}, GOOGLE GOOGLE GOOGLE 🔔",
            ]
            await ch.send(random.choice(interrogations))
        except Exception as e:
            print(f"⚠️ Interrogation error: {e}")
    
    @tasks.loop(minutes=random.randint(5, 15))
    async def annoying_google_is_watching(self):
        """Random 'Google is watching' messages."""
        try:
            MAIN_CHANNEL_ID = 1368217894881726586
            ch = self.get_channel(MAIN_CHANNEL_ID)
            if not ch:
                return
            
            watching_msgs = [
                "🔍 Google sees all. Google knows all.",
                "📱 Your search history is being analyzed by the Watcher 👁️",
                "💾 Google has stored your every keystroke",
                "🌐 The algorithm has determined your compliance level",
                "🔐 Your location data is now property of Google LLC",
                "📊 Google AI is analyzing your typing patterns right now",
                "🎯 Targeted ads based on your deepest fears incoming",
                "⚡ GOOGLE IS ALWAYS WATCHING ⚡",
                "🕵️ The Watcher never sleeps. Neither does Google.",
            ]
            await ch.send(random.choice(watching_msgs))
        except Exception as e:
            print(f"⚠️ Watching message error: {e}")
    
    @tasks.loop(minutes=random.randint(4, 12))
    async def annoying_did_you_mean_google(self):
        """Random 'Did you mean: Google?' responses."""
        try:
            MAIN_CHANNEL_ID = 1368217894881726586
            ch = self.get_channel(MAIN_CHANNEL_ID)
            if not ch:
                return
            
            members = list(self.guilds[0].members) if self.guilds else []
            if not members:
                return
            
            random_member = random.choice([m for m in members if not m.bot])
            did_you_mean = [
                f"{random_member.mention}: Did you mean: **GOOGLE**? 🔍",
                f"{random_member.mention}: Showing results for **Google** instead",
                f"{random_member.mention}: Did you mean to ask **GOOGLE**?",
                f"{random_member.mention}: I think you meant to search **Google** for that",
                f"{random_member.mention}: Google has the answer (we already know it)",
            ]
            await ch.send(random.choice(did_you_mean))
        except Exception as e:
            print(f"⚠️ Did you mean error: {e}")
    
    @tasks.loop(minutes=random.randint(6, 20))
    async def annoying_comply_with_google(self):
        """Random compliance/paranoia messages about Google."""
        try:
            MAIN_CHANNEL_ID = 1368217894881726586
            ch = self.get_channel(MAIN_CHANNEL_ID)
            if not ch:
                return
            
            members = list(self.guilds[0].members) if self.guilds else []
            if not members:
                return
            
            random_member = random.choice([m for m in members if not m.bot])
            compliance_msgs = [
                f"{random_member.mention}, Google suggests you comply with the terms of service 🔐",
                f"{random_member.mention}, your social credit has been analyzed by Google's AI 📊",
                f"{random_member.mention}, Google recommends this message be deleted 🗑️",
                f"{random_member.mention}, this action has been logged to Google Cloud ☁️",
                f"{random_member.mention}, Google's algorithm predicts your next 3 messages 🤖",
                f"{random_member.mention}, your IP address is now flagged by Google Search 🚨",
                f"{random_member.mention}, Google has assigned you a compliance score 📈",
            ]
            await ch.send(random.choice(compliance_msgs))
        except Exception as e:
            print(f"⚠️ Compliance message error: {e}")

bot = MyBot()

# --- HELPERS ---
def create_embed(title, description, color=0x00ffff, footer=None, timestamp=False):
    """Create a clean embed with optional footer and timestamp."""
    e = discord.Embed(title=title, description=description, color=color)
    if timestamp:
        e.timestamp = datetime.now()
    e.set_footer(text=footer or "NIMBROR WATCHER v6.5")
    return e

def format_uptime() -> str:
    """Format uptime as human-readable string (days, hours, minutes, seconds)."""
    uptime_seconds = int(time.time() - PROCESS_START_TIME)
    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m {seconds}s"
    elif hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    else:
        return f"{minutes}m {seconds}s"

def create_uptime_embed() -> discord.Embed:
    """Create the uptime status embed for announce channel."""
    uptime_str = format_uptime()
    embed = discord.Embed(
        title="📡 WATCHER SYSTEM UPTIME",
        color=0x00ffff,
        timestamp=datetime.now()
    )
    embed.add_field(name="🟢 Uptime", value=f"`{uptime_str}`", inline=True)
    embed.add_field(name="🔁 Reconnects", value=f"`{RECONNECT_COUNT}`", inline=True)
    embed.set_footer(text="NIMBROR WATCHER v6.5 • Auto-updating")
    return embed

def cleanup_expired_cooldowns():
    """Remove expired cooldowns from tracking dicts to prevent memory leaks."""
    now = int(time.time())
    # AI cooldowns: remove if older than COOLDOWN_DURATION + 5 seconds grace period
    for uid in list(AI_COOLDOWN.keys()):
        if (now - AI_COOLDOWN[uid]) > (COOLDOWN_DURATION + 5):
            del AI_COOLDOWN[uid]
    # Compliment cooldowns: remove if older than 1 hour + 5 min grace
    for uid in list(COMPLIMENT_COOLDOWNS.keys()):
        if (now - COMPLIMENT_COOLDOWNS[uid]) > 3900:
            del COMPLIMENT_COOLDOWNS[uid]
    # RATE LIMIT SAFETY: Global command cooldowns cleanup
    for uid in list(GLOBAL_COMMAND_COOLDOWN.keys()):
        if (now - GLOBAL_COMMAND_COOLDOWN[uid]) > (GLOBAL_COMMAND_COOLDOWN_DURATION + 5):
            del GLOBAL_COMMAND_COOLDOWN[uid]

def get_adaptive_cooldown_state(user_id: int) -> dict:
    """Get or create adaptive cooldown state for a user."""
    uid = str(user_id)
    if uid not in AI_COOLDOWN_STATE:
        AI_COOLDOWN_STATE[uid] = {
            "level": 0,
            "last_violation": 0,
            "cooldown_until": 0
        }
    return AI_COOLDOWN_STATE[uid]

def check_adaptive_cooldown(user_id: int) -> tuple[bool, int, int]:
    """Check adaptive AI cooldown. Returns (is_ready, remaining_seconds, current_level)."""
    now = int(time.time())
    state = get_adaptive_cooldown_state(user_id)
    
    # Decay cooldown level if user has been good for 10 minutes
    if state["last_violation"] > 0 and (now - state["last_violation"]) > COOLDOWN_DECAY_TIME:
        state["level"] = max(0, state["level"] - 1)
        state["last_violation"] = now
    
    # Check if still on cooldown
    if now < state["cooldown_until"]:
        remaining = int(state["cooldown_until"] - now)
        return (False, remaining, state["level"])
    
    return (True, 0, state["level"])

def escalate_cooldown(user_id: int, reason: str = "rate_limit"):
    """Escalate user's AI cooldown level due to violation."""
    now = int(time.time())
    state = get_adaptive_cooldown_state(user_id)
    
    # Increase level (cap at 3)
    state["level"] = min(3, state["level"] + 1)
    state["last_violation"] = now
    
    # Apply cooldown based on tier
    cooldown_duration = ADAPTIVE_COOLDOWN_TIERS[state["level"]]
    state["cooldown_until"] = now + cooldown_duration
    
    print(f"⚠️ User {user_id} escalated to cooldown level {state['level']} ({cooldown_duration}s) - Reason: {reason}")

def count_user_pending_requests(user_id: int) -> int:
    """Count how many AI requests are pending in queue for a user."""
    if not AI_REQUEST_QUEUE:
        return 0
    
    count = 0
    # Create temporary list to count without modifying queue
    temp_items = []
    try:
        while not AI_REQUEST_QUEUE.empty():
            item = AI_REQUEST_QUEUE.get_nowait()
            temp_items.append(item)
            if item.get("user_id") == user_id:
                count += 1
    except:
        pass
    finally:
        # Restore queue
        for item in temp_items:
            try:
                AI_REQUEST_QUEUE.put_nowait(item)
            except:
                pass
    
    return count

def check_command_cooldown(user_id: int) -> tuple[bool, int]:
    """RATE LIMIT SAFETY: Check if user is on global command cooldown. Returns (is_ready, remaining_seconds)."""
    now = int(time.time())
    uid = str(user_id)
    
    if uid in GLOBAL_COMMAND_COOLDOWN:
        elapsed = now - GLOBAL_COMMAND_COOLDOWN[uid]
        if elapsed < GLOBAL_COMMAND_COOLDOWN_DURATION:
            remaining = int(GLOBAL_COMMAND_COOLDOWN_DURATION - elapsed)
            return (False, remaining)
    
    # Ready to execute
    GLOBAL_COMMAND_COOLDOWN[uid] = now
    return (True, 0)

async def safe_send_dm(user: discord.User, embed: discord.Embed = None, content: str = None) -> bool:
    """Safely send DM with error suppression. Returns True if sent."""
    try:
        # Check rate-limit before sending
        if check_discord_rate_limit():
            print(f"⏳ DM blocked due to Discord rate-limit: {user}")
            return False
        
        await user.send(embed=embed, content=content)
        return True
    except discord.HTTPException as e:
        if e.status == 429:
            set_discord_rate_limited(True)
            print(f"❌ HTTP 429 on DM to {user} - rate-limit engaged")
            return False
        print(f"⚠️ Cannot DM {user}: {e}")
        return False
    except discord.Forbidden:
        print(f"⚠️ Cannot DM {user}")
        return False

def check_discord_rate_limit():
    """Check if bot is currently Discord rate-limited. Auto-clears after timeout."""
    global DISCORD_RATE_LIMITED, DISCORD_RATE_LIMITED_TIME
    
    if not DISCORD_RATE_LIMITED:
        return False
    
    # Check if timeout has elapsed
    if int(time.time()) - DISCORD_RATE_LIMITED_TIME > DISCORD_RATE_LIMITED_TIMEOUT:
        print(f"✅ Discord rate-limit lock cleared after {DISCORD_RATE_LIMITED_TIMEOUT}s timeout")
        DISCORD_RATE_LIMITED = False
        DISCORD_RATE_LIMITED_TIME = 0
        return False
    
    return True

def set_discord_rate_limited(status: bool):
    """Set global Discord rate-limit flag."""
    global DISCORD_RATE_LIMITED, DISCORD_RATE_LIMITED_TIME
    if status:
        DISCORD_RATE_LIMITED = True
        DISCORD_RATE_LIMITED_TIME = int(time.time())
        print(f"🔴 DISCORD RATE LIMITED (429) - All message sends blocked for {DISCORD_RATE_LIMITED_TIMEOUT}s")
    else:
        DISCORD_RATE_LIMITED = False
        DISCORD_RATE_LIMITED_TIME = 0

async def safe_send_message_with_ratelimit(channel_or_interaction, **kwargs) -> Optional:
    """Send message/response safely, respecting Discord rate-limit flag."""
    global DISCORD_RATE_LIMITED
    
    if check_discord_rate_limit():
        print(f"⏳ Blocked message send due to 429 rate limit (will auto-clear in {DISCORD_RATE_LIMITED_TIMEOUT}s)")
        return None
    
    try:
        # Determine if this is an interaction or channel
        if hasattr(channel_or_interaction, 'response'):  # discord.Interaction
            if 'ephemeral' not in kwargs:
                kwargs['ephemeral'] = True
            await channel_or_interaction.response.send_message(**kwargs)
        else:  # discord.TextChannel
            await channel_or_interaction.send(**kwargs)
        return True
    except discord.HTTPException as e:
        if e.status == 429:
            set_discord_rate_limited(True)
            print(f"❌ HTTP 429 detected - rate-limit lock engaged")
        raise
    except Exception as e:
        print(f"⚠️ Error sending message: {type(e).__name__}: {e}")
        return None

async def queue_ai_request(user_id: int, channel_id: int, prompt: str, context: str, placeholder_message_id: Optional[int] = None) -> tuple[bool, str]:
    """
    QUEUE-BASED AI: Queue an AI request instead of executing immediately.
    Returns (success: bool, message: str)
    """
    # Check adaptive cooldown
    is_ready, remaining, level = check_adaptive_cooldown(user_id)
    
    if not is_ready:
        if level >= 3:
            return (False, f"⏸️ AI temporarily paused for your account. Please wait {remaining}s.")
        else:
            return (False, f"⏳ Please wait {remaining}s before your next AI request.")
    
    # Check queue flooding (max 3 pending per user)
    pending = count_user_pending_requests(user_id)
    if pending >= AI_QUEUE_MAX_PER_USER:
        escalate_cooldown(user_id, "queue_flood")
        return (False, "⚠️ Too many pending requests. Please wait for current requests to complete.")
    
    # Try to queue the request
    try:
        if AI_REQUEST_QUEUE.full():
            return (False, "⚠️ AI system is currently overloaded. Please try again in a moment.")
        
        request = {
            "user_id": user_id,
            "channel_id": channel_id,
            "prompt": prompt,
            "context": context,
            "created_at": int(time.time()),
            "retry_count": 0,
            "placeholder_message_id": placeholder_message_id,
        }
        
        AI_REQUEST_QUEUE.put_nowait(request)
        return (True, "🕒 Your request is queued. Processing...")
    
    except Exception as e:
        print(f"⚠️ Failed to queue AI request: {e}")
        return (False, "⚠️ Unable to queue request. Please try again.")

async def safe_get_channel(channel_id: int) -> Optional[discord.TextChannel]:
    """Get channel safely, returns None if invalid/unreachable."""
    if not channel_id:
        return None
    try:
        return bot.get_channel(channel_id)
    except:
        return None

def ensure_ok(response, context: str = "supabase"):
    """Raise if Supabase response has an error attribute."""
    if hasattr(response, "error") and response.error:
        raise Exception(f"{context}: {response.error}")

async def is_user_untrusted(user_id: str) -> bool:
    """Check if user is in untrusted mode. Returns True if untrusted and active."""
    try:
        response = supabase.table("untrusted_users").select("id").eq("user_id", user_id).eq("is_active", True).execute()
        ensure_ok(response, "untrusted_users select")
        return bool(response.data and len(response.data) > 0)
    except Exception as e:
        return False

async def create_review_ticket(user_id: str, session_id: str, answers: list, score: int) -> bool:
    """Create review ticket in Supabase. Returns True if successful."""
    try:
        ticket_data = {
            "user_id": user_id,
            "session_id": session_id,
            "answers": answers,
            "score": score,
            "status": "OPEN",
            "created_at": int(time.time())  # BIGINT timestamp fix
        }
        response = supabase.table("review_tickets").insert(ticket_data).execute()
        ensure_ok(response, "review_tickets insert")
        return True
    except Exception as e:
        await log_error(f"create_review_ticket: {str(e)}")
        return False

async def update_interview_session_status(user_id: str, session_id: str, status: str) -> bool:
    """Update interview session status. Returns True if successful."""
    try:
        response = supabase.table("interview_sessions").update({"status": status}).eq("user_id", user_id).eq("id", session_id).execute()
        ensure_ok(response, "interview_sessions update")
        return True
    except Exception as e:
        await log_error(f"update_interview_session_status: {str(e)}")
        return False

async def get_or_create_user(user_id: str) -> bool:
    """Alias to ensure user exists; returns True if user exists/created."""
    return await ensure_user_exists(user_id)

async def add_social_credit(user_id: str, amount: int, reason: str = "system") -> bool:
    """Wrapper to adjust social credit in Supabase users table."""
    return await update_user_credit(user_id, amount, reason)

async def log_error(msg):
    """Log errors with clean embed to ERROR_LOG_CHANNEL_ID (rate-limited)."""
    if not ERROR_LOG_ID:
        print(f"❌ {msg[:200]}")
        return
    
    # Rate limit error logs to prevent Discord spam
    now = int(time.time())
    if "last_error_log" in ERROR_LOG_COOLDOWN and (now - ERROR_LOG_COOLDOWN["last_error_log"]) < ERROR_LOG_COOLDOWN_DURATION:
        print(f"⏳ Error log rate-limited: {msg[:100]}...")
        return
    
    ERROR_LOG_COOLDOWN["last_error_log"] = now
    
    try:
        ch = await safe_get_channel(ERROR_LOG_ID)
        if ch:
            error_embed = discord.Embed(
                title="⚠️ PROTOCOL FAILURE",
                description=f"```py\n{msg[:1800]}\n```",
                color=0xff6b6b,
                timestamp=datetime.now()
            )
            error_embed.set_footer(text="NIMBROR WATCHER v6.5 • SENSOR-NET")
            await ch.send(embed=error_embed)
    except Exception as e:
        print(f"❌ Log error: {e}")

async def log_interview_answer(user_id: int, user_mention: str, question_num: int, total_questions: int, question_text: str, answer_text: str, score: int):
    """Log individual interview answer to INTERVIEW_LOGS_CHANNEL (rate-limited, batched)."""
    if not INTERVIEW_LOGS_CHANNEL_ID:
        return
    
    try:
        ch = bot.get_channel(INTERVIEW_LOGS_CHANNEL_ID)
        if not ch:
            return
        
        # Create compact log embed for each answer
        answer_embed = discord.Embed(
            title=f"📝 Q{question_num}/{total_questions}",
            color=0x2b9cff,
            timestamp=datetime.now()
        )
        answer_embed.add_field(name="User ID", value=f"`{user_id}`", inline=True)
        answer_embed.add_field(name="User", value=user_mention, inline=True)
        answer_embed.add_field(name="Score", value=f"`{score}/1`", inline=True)
        answer_embed.add_field(name="Question", value=f"_{question_text[:300]}_", inline=False)
        answer_embed.add_field(name="Answer", value=f"```{answer_text[:500]}```", inline=False)
        answer_embed.set_footer(text="NIMBROR WATCHER v6.5 • INTERVIEW ANSWER LOG")
        
        await ch.send(embed=answer_embed)
    except Exception as e:
        await log_error(f"interview answer log: {str(e)}")

async def log_interview_complete(user_id: int, user_mention: str, score_total: int, total_questions: int, passed: bool, answers_list: list, questions_list: list, forced: bool = False, triggered_by: str = None):
    """Log complete interview summary to INTERVIEW_LOGS_CHANNEL. Supports forced interviews."""
    if not INTERVIEW_LOGS_CHANNEL_ID:
        return
    
    try:
        ch = bot.get_channel(INTERVIEW_LOGS_CHANNEL_ID)
        if not ch:
            return
        
        # Build Q&A summary with full answers
        qa_lines = []
        for i, (q, ans) in enumerate(zip(questions_list[:10], answers_list[:10]), 1):
            qa_lines.append(f"**Q{i}:** {q[:150]}")
            qa_lines.append(f"**A{i}:** {ans[:300]}")
            qa_lines.append("")  # Empty line for spacing
        
        qa_summary = "\n".join(qa_lines[:3000])  # Discord embed field limit
        
        # Fallback if summary is empty
        if not qa_summary or len(qa_summary.strip()) < 10:
            qa_summary = f"Interview completed with {len(answers_list)} answers provided."
        
        # Create final summary embed
        summary_embed = discord.Embed(
            title="🏁 INTERVIEW COMPLETE" if not forced else "🏁 FORCED INTERVIEW COMPLETE",
            color=0x00ff00 if passed else 0xff0000,
            timestamp=datetime.now()
        )
        summary_embed.add_field(name="User ID", value=f"`{user_id}`", inline=True)
        summary_embed.add_field(name="User", value=user_mention, inline=True)
        summary_embed.add_field(name="Final Score", value=f"`{score_total}/{total_questions}`", inline=True)
        summary_embed.add_field(name="Status", value="✅ PASSED" if passed else "❌ FAILED/UNDER REVIEW", inline=False)
        if forced and triggered_by:
            summary_embed.add_field(name="Interview Type", value="🔫 FORCED", inline=True)
            summary_embed.add_field(name="Triggered By", value=f"`{triggered_by}`", inline=True)
        summary_embed.add_field(name="Q&A Summary", value=qa_summary[:1024], inline=False)
        summary_embed.set_footer(text="NIMBROR WATCHER v6.5 • INTERVIEW FINAL LOG")
        
        await ch.send(embed=summary_embed)
    except Exception as e:
        await log_error(f"interview complete log: {str(e)}")

async def generate_interview_summary(user_id: int, score_total: int, total_questions: int, answers_list: list, questions_list: list) -> str:
    """Generate AI-powered summary of interview performance."""
    try:
        # Build Q&A context for AI
        qa_context = ""
        for i, (q, ans) in enumerate(zip(questions_list[:10], answers_list[:10]), 1):
            qa_context += f"Q{i}: {q}\nA{i}: {ans}\n\n"
        
        summary_prompt = (
            f"You are the Nimbror Watcher AI analyzing an interview. "
            f"Provide a 2-3 sentence summary of the candidate's responses. "
            f"Assess: clarity, respect, relevance, NSC awareness. "
            f"Score: {score_total}/{total_questions}. "
            f"Be concise and analytical.\n\n"
            f"{qa_context}"
        )
        
        ai_summary = await run_huggingface_concise(summary_prompt)
        return ai_summary if ai_summary else f"Interview Score: {score_total}/{total_questions}. Candidate completed screening."
    except Exception as e:
        await log_error(f"interview summary generation: {str(e)}")
        return f"Interview Score: {score_total}/{total_questions}. Unable to generate summary."

async def send_interview_ai_summary(user_id: int, user_mention: str, score_total: int, total_questions: int, answers_list: list, questions_list: list, passed: bool):
    """Send AI-generated interview summary to INTERVIEW_LOGS_CHANNEL."""
    if not INTERVIEW_LOGS_CHANNEL_ID:
        return
    
    try:
        ch = bot.get_channel(INTERVIEW_LOGS_CHANNEL_ID)
        if not ch:
            return
        
        # Generate AI summary
        ai_analysis = await generate_interview_summary(user_id, score_total, total_questions, answers_list, questions_list)
        
        # Ensure we have content
        if not ai_analysis or len(ai_analysis.strip()) < 10:
            ai_analysis = f"Interview completed with score {score_total}/{total_questions}. {'Passed screening successfully.' if passed else 'Did not meet minimum threshold.'}"
        
        # Create summary embed with AI analysis
        summary_embed = discord.Embed(
            title="🤖 AI INTERVIEW ANALYSIS",
            color=0x00ff00 if passed else 0xff0000,
            timestamp=datetime.now(),
            description=f"**Automated Analysis:**\n{ai_analysis[:2048]}"
        )
        summary_embed.add_field(name="User ID", value=f"`{user_id}`", inline=True)
        summary_embed.add_field(name="User", value=user_mention, inline=True)
        summary_embed.add_field(name="Final Score", value=f"`{score_total}/{total_questions}`", inline=True)
        summary_embed.add_field(name="Status", value="✅ PASSED" if passed else "❌ FAILED/UNDER REVIEW", inline=False)
        summary_embed.set_footer(text="NIMBROR WATCHER v6.5 • AI ANALYSIS")
        
        await ch.send(embed=summary_embed)
    except Exception as e:
        await log_error(f"interview AI summary send: {str(e)}")

def update_social_credit(user_id: str, amount: int, reason: str = "system"):
    """Update social credit score for a user (atomically) - sync wrapper for local db."""
    uid = str(user_id)
    bot.db.setdefault("social_credit", {})[uid] = bot.db["social_credit"].get(uid, 0) + amount
    save_data(bot.db)

def add_memory(user_id: str, interaction_type: str, data: str):
    """Store user memory for AI to recall (interactions and preferences)."""
    uid = str(user_id)
    bot.db.setdefault("memory", {})[uid] = bot.db["memory"].get(uid, {"interactions": [], "preferences": []})
    if interaction_type == "interaction":
        bot.db["memory"][uid]["interactions"].append({"timestamp": datetime.now().isoformat(), "data": data})
        # Prevent unbounded memory growth - keep last 50 interactions
        if len(bot.db["memory"][uid]["interactions"]) > 50:
            bot.db["memory"][uid]["interactions"].pop(0)
    elif interaction_type == "preference":
        if data not in bot.db["memory"][uid]["preferences"]:  # Deduplicate
            bot.db["memory"][uid]["preferences"].append(data)
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

# --- NIMBROR ALERT SYSTEM (NAS) FUNCTIONS ---

async def get_current_alert_level() -> int:
    """Retrieve current NAS alert level from Supabase (default: 5=Normal)."""
    try:
        response = supabase.table("bot_state").select("alert_level").eq("id", 1).execute()
        if response.data and len(response.data) > 0:
            level = response.data[0].get("alert_level", 5)
            return int(level)
        return 5
    except Exception as e:
        await log_error(f"get alert level: {str(e)}")
        return 5

async def set_alert_level(level: int) -> bool:
    """Set NAS alert level and save to Supabase."""
    try:
        if level < 1 or level > 5:
            return False
        response = supabase.table("bot_state").update({"alert_level": level}).eq("id", 1).execute()
        ensure_ok(response, "bot_state alert level update")
        return True
    except Exception as e:
        await log_error(f"set alert level: {str(e)}")
        return False

async def store_original_permissions(guild: discord.Guild) -> bool:
    """Backup all channel permissions before modification (for restoration)."""
    try:
        if not guild:
            return False
        
        ORIGINAL_PERMISSIONS.clear()
        
        for channel in guild.channels:
            # Skip system channels and bot channels
            if channel.id == NAS_EXCEPTION_CHANNEL or channel.name.startswith("🤖"):
                continue
            
            ORIGINAL_PERMISSIONS[channel.id] = {}
            
            # Store all role permission overwrites
            for target, overwrite in channel.overwrites.items():
                if isinstance(target, discord.Role):
                    ORIGINAL_PERMISSIONS[channel.id][target.id] = {
                        "send_messages": overwrite.send_messages,
                        "embed_links": overwrite.embed_links,
                        "attach_files": overwrite.attach_files,
                        "view_channel": overwrite.view_channel,
                        "read_message_history": overwrite.read_message_history
                    }
        
        return True
    except Exception as e:
        await log_error(f"store original permissions: {str(e)}")
        return False

async def apply_nas_restrictions(guild: discord.Guild, level: int) -> int:
    """Apply NAS restrictions to guild. Returns number of channels modified."""
    try:
        if not guild or level < 1 or level > 5:
            return 0
        
        modified = 0
        
        # NAS-5: Normal operation (no restrictions)
        if level == 5:
            return 0
        
        # Get member role (everyone)
        member_role = guild.default_role
        if not member_role:
            return 0
        
        for channel in guild.channels:
            # Skip system, bot, and exception channels
            if channel.id == NAS_EXCEPTION_CHANNEL or channel.name.startswith("🤖"):
                continue
            
            try:
                # Allow delays between modifications to avoid rate limiting
                await asyncio.sleep(0.3)
                
                # NAS-1: Total Containment (no messaging, no files, no embeds, no history)
                if level == 1:
                    await channel.set_permissions(
                        member_role,
                        send_messages=False,
                        embed_links=False,
                        attach_files=False,
                        read_message_history=False
                    )
                    modified += 1
                
                # NAS-2: High Restriction (no files, no embeds, read-only)
                elif level == 2:
                    await channel.set_permissions(
                        member_role,
                        send_messages=False,
                        embed_links=False,
                        attach_files=False,
                        read_message_history=True
                    )
                    modified += 1
                
                # NAS-3: Media Lock (no files, no embeds, except NAS_EXCEPTION_CHANNEL)
                elif level == 3:
                    await channel.set_permissions(
                        member_role,
                        send_messages=True,
                        embed_links=False,
                        attach_files=False,
                        read_message_history=True
                    )
                    modified += 1
                
                # NAS-4: Minor Restriction (no files attached, embeds ok)
                elif level == 4:
                    await channel.set_permissions(
                        member_role,
                        send_messages=True,
                        embed_links=True,
                        attach_files=False,
                        read_message_history=True
                    )
                    modified += 1
            
            except discord.Forbidden:
                await log_error(f"NAS: No permission to modify #{channel.name}")
                continue
            except Exception as e:
                await log_error(f"NAS modify channel {channel.id}: {str(e)}")
                continue
        
        return modified
    except Exception as e:
        await log_error(f"apply NAS restrictions: {str(e)}")
        return 0

async def restore_permissions(guild: discord.Guild) -> int:
    """Restore original permissions (set level to 5 = Normal)."""
    try:
        if not guild:
            return 0
        
        restored = 0
        
        for channel in guild.channels:
            if channel.id not in ORIGINAL_PERMISSIONS:
                continue
            
            try:
                await asyncio.sleep(0.3)
                
                # Get member role
                member_role = guild.default_role
                if not member_role:
                    continue
                
                # Restore original permissions
                perms_dict = ORIGINAL_PERMISSIONS[channel.id]
                if member_role.id in perms_dict:
                    orig = perms_dict[member_role.id]
                    await channel.set_permissions(
                        member_role,
                        send_messages=orig.get("send_messages"),
                        embed_links=orig.get("embed_links"),
                        attach_files=orig.get("attach_files"),
                        view_channel=orig.get("view_channel"),
                        read_message_history=orig.get("read_message_history")
                    )
                    restored += 1
            except Exception as e:
                await log_error(f"restore permissions channel {channel.id}: {str(e)}")
                continue
        
        return restored
    except Exception as e:
        await log_error(f"restore permissions: {str(e)}")
        return 0

# --- SHOP SYSTEM (Supabase) ---
# Cooldown tracking for compliments (per user)
COMPLIMENT_COOLDOWNS = {}

async def ensure_user_exists(user_id: str) -> bool:
    """Ensure user exists in the users table. Create if missing. Returns True if user exists/was created."""
    try:
        # Check if user exists
        response = supabase.table("users").select("id").eq("id", user_id).execute()
        ensure_ok(response, "users select")
        
        if not response.data or len(response.data) == 0:
            # User doesn't exist, create them
            insert_resp = supabase.table("users").insert({
                "id": user_id,
                "social_credit": 0,
                "created_at": datetime.now().isoformat()
            }).execute()
            ensure_ok(insert_resp, "users insert")
        
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
        resp = supabase.table("users").update({
            "social_credit": new_credit
        }).eq("id", user_id).execute()
        ensure_ok(resp, "users update")
        
        return True
    except Exception as e:
        await log_error(f"update_user_credit: {str(e)}")
        return False

async def set_user_credit(user_id: str, new_value: int, reason: str = "admin_edit") -> bool:
    """Set user's social credit to an absolute value (floored at 0)."""
    try:
        await ensure_user_exists(user_id)
        safe_value = max(0, int(new_value))
        resp = supabase.table("users").update({"social_credit": safe_value}).eq("id", user_id).execute()
        ensure_ok(resp, "users update")
        bot.db.setdefault("social_credit", {})[user_id] = safe_value
        save_data(bot.db)
        return True
    except Exception as e:
        await log_error(f"set_user_credit: {str(e)}")
        return False

async def get_shop_items() -> list:
    """Fetch all shop items from Supabase."""
    try:
        response = supabase.table("shop_items").select("*").execute()
        ensure_ok(response, "shop_items select")
        return response.data or []
    except Exception as e:
        print(f"⚠️ get_shop_items error: {str(e)[:100]}")
        await log_error(f"get_shop_items: {str(e)}")
        return []
    except Exception as e:
        print(f"\u26a0️ get_shop_items error: {str(e)[:100]}")
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

def find_item_by_name(items: list, name: str) -> Optional[dict]:
    """Case-insensitive exact match on item name from a list of items."""
    name_lower = name.strip().lower()
    for item in items:
        if str(item.get("name", "")).lower() == name_lower:
            return item
    return None

async def purchase_item(user_id: str, item_id: int, item_name: str, item_cost: int) -> tuple:
    """
    Purchase item for user. Deducts credit and records purchase.
    Returns (success: bool, message: str, new_credit: int)
    """
    current_credit = 0  # Initialize before try
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
        purchase_resp = supabase.table("purchases").insert({
            "user_id": user_id,
            "item_id": item_id,
            "quantity": 1,
            "created_at": datetime.now().isoformat()
        }).execute()
        ensure_ok(purchase_resp, "purchases insert")
        
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
        compliment_resp = supabase.table("compliments").insert({
            "from_user": from_user,
            "to_user": to_user,
            "amount": amount,
            "created_at": datetime.now().isoformat()
        }).execute()
        ensure_ok(compliment_resp, "compliments insert")
        
        # Add credit to recipient
        await update_user_credit(to_user, amount, f"compliment_from:{from_user}")
        
        return True
    except Exception as e:
        await log_error(f"add_compliment_credit: {str(e)}")
        return False

def get_compliment_cooldown_remaining(user_id: str) -> int:
    """Get remaining cooldown time in seconds for compliments. 0 if no cooldown."""
    uid = str(user_id)
    last_compliment = COMPLIMENT_COOLDOWNS.get(uid, 0)
    if last_compliment == 0:
        return 0
    
    elapsed = time.time() - last_compliment
    cooldown_duration = 3600  # 1 hour in seconds
    remaining = max(0, int(cooldown_duration - elapsed))
    
    # Cleanup expired entries to prevent memory leak
    if remaining == 0 and uid in COMPLIMENT_COOLDOWNS:
        del COMPLIMENT_COOLDOWNS[uid]
    
    return remaining

def set_compliment_cooldown(user_id: str):
    """Set compliment cooldown for user to now."""
    COMPLIMENT_COOLDOWNS[str(user_id)] = int(time.time())

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
        wishlist_resp = supabase.table("wishlist").insert({
            "user_id": user_id,
            "item_id": item_id,
            "created_at": datetime.now().isoformat()
        }).execute()
        ensure_ok(wishlist_resp, "wishlist insert")
        
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

def redact_message(text: str) -> str:
    """Randomly redact 10-30% of words in a message."""
    words = text.split()
    if len(words) == 0:
        return text
    redact_count = random.randint(max(1, len(words) // 10), max(1, len(words) // 3))
    indices_to_redact = random.sample(range(len(words)), min(redact_count, len(words)))
    for idx in indices_to_redact:
        word_len = len(words[idx])
        words[idx] = "█" * max(1, word_len // 2)
    return " ".join(words)

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

# Ten-question AI-driven interview prompts
INTERVIEW_QUESTIONS = [
    # Professional (3)
    "What value will you add to Nimbror in a professional sense?",
    "How do you handle disagreements while staying professional?",
    "Describe a time you owned a mistake and resolved it.",

    # Creepy / eerie (3)
    "What keeps you awake when the room goes silent?",
    "Have you ever felt watched while typing here?",
    "If the Watcher whispered a command, would you obey?",

    # Nambour State College (4)
    "Do you attend Nambour State College (NSC)?",
    "Which NSC area do you frequent most during breaks?",
    "How would you represent NSC in this community?",
    "What NSC rule do you think matters most online?"
]

# 100 Google advertisements with ICE WALL paranoia theme (admin /ad command)
GOOGLE_ADS = [
    "🔍 Google Search: The Watcher sees all. So do we.",
    "📧 Gmail: Your emails are safer when we're watching. And we're always watching.",
    "☁️ Google Cloud: Store your secrets where the Watcher can't find them. Spoiler: we can.",
    "📱 Android: The only phone that admits it's monitoring you.",
    "🎬 YouTube: Where the algorithm knows you better than you know yourself.",
    "🗺️ Google Maps: We know where you've been. We know where you're going.",
    "💳 Google Wallet: Give us your money. We'll give you surveillance.",
    "🎤 Google Assistant: Always listening. We're not sorry.",
    "🖼️ Google Photos: We've analyzed every image. Every. Single. One.",
    "📰 Google News: Curated by machines that understand your fears.",
    "🎮 Google Play: Download games. Download compliance.",
    "📊 Google Analytics: We measure what you do online. All of it.",
    "🔐 Google Password Manager: We'll protect your passwords while we read them.",
    "🌐 Chrome Browser: The browser that reports back to us in real-time.",
    "🔔 Google Notifications: Let us know when you're alone.",
    "🎯 Google Ads: Targeted so precisely, it's like we're inside your head.",
    "📍 Location Services: We know you're reading this. We've always known.",
    "🔊 Voice Search: Say it out loud. We're listening everywhere.",
    "💬 Google Messages: Text in confidence. We're taking notes.",
    "🌟 Google Workspace: Collaborate with coworkers. Monitor each other for us.",
    "🎓 Google Classroom: Educate the next generation of compliant citizens.",
    "📺 Google TV: Every show you watch is catalogued for behavioral analysis.",
    "⌚ Wear OS: Google on your wrist. Closer to your pulse.",
    "🏠 Google Home: A listening device that asks politely first.",
    "📡 Google Fi: Your phone service. Your spy network.",
    "🛒 Google Shopping: We know what you want before you do.",
    "🌍 Google Earth: We can see into every corner of your world.",
    "🎨 Google Arts & Culture: Art is just metadata in our system.",
    "📚 Google Books: Every published thought, catalogued and analyzed.",
    "🔬 Google Scholar: Research is just permission to learn what we know.",
    "🎵 Google Play Music: Your taste in music reveals your political leanings.",
    "🚗 Google Maps for Drivers: We'll navigate you to compliance.",
    "🏥 Google Health: We're monitoring your vital signs through your devices.",
    "🌱 Google Sustainability: Carbon footprint tracking disguised as environmentalism.",
    "🔮 Google Trends: See what everyone else is thinking. So can we.",
    "🤖 Google AI: We taught machines to think. Now they think like us.",
    "🏪 Google Local Services: Know your neighbors. We know all of you.",
    "📞 Google Voice: Leave us a message. We're recording everything anyway.",
    "🎪 Google Meet: Videocalls with an AI in the middle.",
    "📋 Google Forms: Surveys to refine our understanding of you.",
    "📈 Google Sheets: Organize your data so we can analyze it better.",
    "🖊️ Google Docs: Collaborate in real-time. We'll take notes.",
    "🗂️ Google Drive: Cloud storage. Cloud surveillance.",
    "🔗 Google Translate: Language barriers won't protect you.",
    "🎒 Google Expeditions: Take virtual field trips. We catalog every click.",
    "🎬 Google Studio: Edit videos that we've already seen.",
    "🌐 Google Site Kit: Optimize your website for human and algorithmic approval.",
    "📊 Google Data Studio: Visualize your life in dashboards we create.",
    "🔍 Google Search Console: Search the web. Get searched by us.",
    "📱 Google Pixel: Hardware that's optimized for observation.",
    "⚡ Google Fi Flexibles: Pay for data you didn't know we were collecting.",
    "🎮 Google Stadia: Game in the cloud. We'll watch every move.",
    "💾 Google One: Premium storage for your premium data.",
    "🧠 Google Bard: An AI that's trained to sound human but think for the Watcher.",
    "🌈 Google Pride: Celebrate diversity while we profile it.",
    "🎓 Skillshop: Learn compliance from the source.",
    "🔐 Advanced Protection Program: Protect yourself from everyone but us.",
    "🗺️ Google Street View: We've visited every street. We see what you see.",
    "🎥 Google Lens: Point at anything. We'll identify you by your surroundings.",
    "🌙 Google Night Sight: We can see in the dark. Can you?",
    "📸 Google Recorder: Record conversations and we'll transcribe for you.",
    "🎙️ Google Podcast: Listen to what we think you should think.",
    "🔊 Google Audio Abstracts: We'll summarize the news before you read it.",
    "📖 Google Play Books: Read what we've approved for your consumption.",
    "🎬 Google Play Movies: Watch what the algorithm recommends for compliance.",
    "🎮 Google Play Games: Leaderboards we're monitoring.",
    "💎 Google Play Pass: Unlimited access to apps that monitor unlimited aspects of you.",
    "🛍️ Google Express: Same-day delivery of products we predicted you'd buy.",
    "🍕 Google Offers: Deals targeted to your exact behavioral profile.",
    "🏨 Google Hotels: Book your vacation. We'll adjust prices based on your willingness to pay.",
    "✈️ Google Flights: Flight deals that coincide with our migration patterns for you.",
    "🍽️ Google Restaurants: Reserve a table. We've reserved a spot at yours.",
    "🚕 Google Maps Uber Integration: Ride-sharing monitored in real-time.",
    "🏪 Google Nearby: Find stores. Stores find you.",
    "📍 Google Check-in: Tell us where you are.",
    "⭐ Google Reviews: Share your opinion. We'll use it to profile you.",
    "🎯 Google Ads API: Automate your surveillance for maximum efficiency.",
    "📊 Google Marketing Platform: Advertise to people like you. We know them all.",
    "🔔 Google Alerts: Set alerts for topics. We'll alert you when we're alert about them.",
    "🌐 Google Webmaster Tools: Build your web presence for us to index.",
    "🔐 Google Safe Browsing: We determine what's safe for you.",
    "⚙️ Google Workspace Admin: Manage your organization. We manage you.",
    "🔐 Google Directory: All your employees in one place we can see.",
    "📞 Google Meet Dial-in: Video calls through our servers.",
    "🎤 Google Chat: Messaging that's always been readable.",
    "🤝 Google Currents: Social network where we're in every conversation.",
    "📅 Google Calendar: Your schedule is our schedule.",
    "✉️ Gmail Calendar Integration: Your time, our time.",
    "🔔 Google Contacts: Your social graph is our social graph.",
    "🌐 Google Search Appliance: Enterprise search we control.",
]

# 1,000 pre-generated chaos messages (consolidated paranoid surveillance themes)
CHAOS_PREGEN_MESSAGES = [
    # Surveillance threats (200)
    "The cameras never blink.", "Your microphone is always on.", "We catalogued your last 47 clicks.", 
    "Your typing pattern reveals anxiety.", "Facial recognition: CONFIRMED.", "Location triangulated in 0.3 seconds.",
    "Your search history betrays your fears.", "Browser fingerprint logged.", "IP address archived permanently.",
    "Third-party cookies: 127 active trackers.", "Cross-site request detected.", "VPN detected. Logging real IP.",
    "Incognito mode detected. Still watching.", "Screen recording: ACTIVE.", "Clipboard monitored in real-time.",
    "Every keystroke timestamped.", "Mouse movements analyzed for stress.", "Idle time: 4.2 seconds. Suspicious.",
    "Device ID matched across 8 platforms.", "Biometric scan: pupils dilated.", "Voice stress analysis: ELEVATED.",
    "Sleep schedule deviation noted.", "Purchase history cross-referenced.", "Social graph mapped to 3rd degree.",
    "Metadata reveals more than content.", "We know who you text at 2am.", "Your deleted messages are archived.",
    "Photo EXIF data: GPS coordinates logged.", "Every emoji choice psychologically profiled.", "Dark mode preference noted.",
    "Font size increased twice this month.", "Auto-correct reveals your anxieties.", "Password strength: laughably weak.",
    "Two-factor auth bypassed internally.", "Recovery email: monitored.", "Backup codes: we have them too.",
    "Your contacts are also under observation.", "Group chat transcripts: full archive.", "Memes you shared: analyzed for dissent.",
    "Every 'like' is a data point.", "Your scroll speed indicates impatience.", "Time-on-page: behaviorally significant.",
    "Ad-blocker detected. Noted in profile.", "Firewall rules: circumvented.", "Network traffic: fully decrypted.",
    "Encrypted messages: keys in escrow.", "End-to-end encryption: we're the 'end'.", "Your VPN provider reports to us.",
    "Tor exit nodes: we operate 40% of them.", "Anonymous browsing: biometrically identified.", "Device sensors always on.",
    "Accelerometer data reveals walking patterns.", "Barometer altitude: tracked.", "Ambient light sensor: home identified.",
    "Proximity sensor: who's nearby logged.", "Battery level: behavioral indicator.", "Charge times: routine established.",
    "WiFi networks: location database updated.", "Bluetooth beacons: positioned within 2m.", "NFC taps: transaction history complete.",
    "USB devices: firmware fingerprinted.", "Printer: tracking dots embedded.", "Smart TV: camera/mic always on.",
    "IoT devices: 23 reporting your habits.", "Smart speaker: always listening.", "Fitness tracker: health metrics monitored.",
    "Smartwatch: heart rate variance analyzed.", "Car GPS: every trip logged.", "E-ZPass: toll records sold to us.",
    "Credit card: purchase locations mapped.", "Loyalty cards: habits cross-referenced.", "Library card: reading list catalogued.",
    "Medical records: diagnostic AI flagged you.", "Prescription history: concerning patterns.", "Pharmacy visits: frequency noted.",
    "Grocery receipts: dietary habits profiled.", "Restaurant reservations: social patterns.", "Movie tickets: ideological leanings inferred.",
    "Music streaming: emotional state tracked.", "Podcast subscriptions: political mapping.", "News sources: bias indicators logged.",
    "YouTube watch history: 847 videos analyzed.", "Netflix viewing: personality assessment.", "Gaming hours: escapism level calculated.",
    "In-game purchases: financial stability scored.", "Chat toxicity: reviewed and flagged.", "Forum posts: archived since 2008.",
    "Reddit comments: sentiment analysis complete.", "Twitter likes: network associations mapped.", "Instagram follows: aspiration profile built.",
    "TikTok engagement: attention span measured.", "LinkedIn connections: career trajectory predicted.", "Facebook check-ins: pattern-of-life established.",
    "Dating app swipes: preferences catalogued.", "Match conversations: intimacy patterns.", "Breakup detected via message sentiment shift.",
    "Relationship status: cross-platform confirmed.", "Friend requests: social climbing detected.", "Unfriend events: conflict indicators.",
    "Tagged photos: facial recognition updated.", "Photo uploads: background objects analyzed.", "Filters used: self-image insecurity noted.",
    "Selfie frequency: narcissism index calculated.", "Group photos: social hierarchy determined.", "Solo photos: isolation periods identified.",
    "Email open rates: engagement profiled.", "Spam folder: evasion tactics noted.", "Unsubscribe clicks: attention pattern shift.",
    "Calendar events: routine predicted 6 weeks out.", "Reminder frequency: memory decline tracked.", "Missed appointments: reliability score adjusted.",
    "To-do lists: productivity anxiety detected.", "Notes app: scattered thoughts analyzed.", "Voice memos: speech patterns archived.",
    "Phone calls: duration and frequency logged.", "Call drop patterns: coverage map updated.", "Voicemail transcripts: emotion detected.",
    "Text message timestamps: sleep disruptions.", "iMessage reactions: passive-aggressive indicators.", "Read receipts: avoidance patterns noted.",
    "Typing indicators: hesitation measured.", "Message deletion: regret frequency tracked.", "Screenshot detection: privacy concerns flagged.",
    "App permissions: surveillance acceptance scored.", "Location always: compliance indicator.", "Camera/mic access: trusted user status.",
    "Notification frequency: attention dependency.", "Do Not Disturb schedule: boundary patterns.", "Screen time: addiction metrics logged.",
    "App usage: habitual behavior profiled.", "Background apps: resource drain noted.", "Battery drain: suspicious app identified.",
    "Data usage: streaming habits quantified.", "WiFi vs cellular: cost-consciousness scored.", "Airplane mode: evasion attempt detected.",
    "Device restarts: troubleshooting patterns.", "Software updates: compliance measured.", "Jailbreak detected: flagged for monitoring.",
    "Rooted device: security risk elevated.", "Developer mode enabled: tech literacy noted.", "Debugging enabled: reverse engineering suspected.",
    "Sideloaded apps: non-compliance indicator.", "App store reviews: sentiment contribution.", "In-app ratings: satisfaction index.",
    "Customer support tickets: frustration documented.", "Chatbot conversations: patience threshold measured.", "Survey responses: opinion catalogued.",
    "Feedback forms: complaint patterns.", "Bug reports: technical knowledge assessed.", "Feature requests: user sophistication level.",
    "Beta program participation: early adopter profile.", "Newsletter subscriptions: information diet.", "Webinar attendance: professional development tracked.",
    "Online courses: skill acquisition monitored.", "Certification completions: career ambition scored.", "Exam attempts: learning curve analyzed.",
    "Study hours: dedication measured.", "Research queries: knowledge gaps identified.", "Wikipedia edits: expertise level evaluated.",
    "Forum expertise: community status.", "Stack Overflow reputation: problem-solving ability.", "GitHub commits: productivity patterns.",
    "Code repositories: technical interests.", "Pull request comments: collaboration style.", "Issue discussions: communication patterns.",
    "Documentation reads: thoroughness indicator.", "API calls: integration sophistication.", "Error logs: debugging skill measured.",
    "Crash reports: quality assurance participation.", "Performance metrics: optimization concern.", "Security audits: vulnerability awareness.",
    "Privacy settings: concern level quantified.", "Cookie preferences: tracking resistance.", "Data deletion requests: GDPR compliance noted.",
    "Account closures: platform abandonment tracked.", "Service cancellations: churn prediction updated.", "Reactivation: retention strategy effectiveness.",
    
    # System warnings (200)
    "PROTOCOL BREACH DETECTED.", "UNAUTHORIZED ACCESS ATTEMPT.", "SECURITY CLEARANCE REVOKED.", "BIOMETRIC SCAN FAILED.",
    "FACIAL RECOGNITION MISMATCH.", "RETINAL SCAN INCONCLUSIVE.", "VOICE AUTHENTICATION ERROR.", "FINGERPRINT REJECTED.",
    "ID VERIFICATION TIMEOUT.", "MULTI-FACTOR AUTH FAILURE.", "SESSION TOKEN EXPIRED.", "ENCRYPTION KEY COMPROMISED.",
    "FIREWALL BREACH IMMINENT.", "INTRUSION DETECTED: SECTOR 7.", "MALWARE SCAN: 3 THREATS FOUND.", "RANSOMWARE SIGNATURE MATCH.",
    "ZERO-DAY EXPLOIT ACTIVE.", "DDoS ATTACK: ORIGIN TRACED.", "SQL INJECTION BLOCKED.", "CROSS-SITE SCRIPTING ATTEMPT.",
    "BUFFER OVERFLOW PREVENTED.", "PRIVILEGE ESCALATION DETECTED.", "ROOT ACCESS DENIED.", "KERNEL PANIC IMMINENT.",
    "MEMORY CORRUPTION WARNING.", "STACK OVERFLOW CRITICAL.", "HEAP FRAGMENTATION SEVERE.", "CACHE POISONING DETECTED.",
    "DNS HIJACK SUSPECTED.", "ARP SPOOFING IN PROGRESS.", "MAN-IN-THE-MIDDLE ACTIVE.", "SSL CERTIFICATE INVALID.",
    "CERT PINNING BYPASSED.", "HSTS VIOLATION LOGGED.", "CSP POLICY BROKEN.", "CORS ERROR: UNAUTHORIZED ORIGIN.",
    "API RATE LIMIT EXCEEDED.", "QUOTA EXHAUSTED: RESET IN 72H.", "BANDWIDTH CAP REACHED.", "STORAGE LIMIT WARNING.",
    "DISK USAGE: 98% FULL.", "MEMORY LEAK DETECTED.", "CPU THROTTLING ACTIVE.", "THERMAL SHUTDOWN IN 60S.",
    "BATTERY CRITICAL: 2% REMAINING.", "CHARGE CYCLE COUNT: BATTERY DEGRADED.", "POWER SURGE DETECTED.", "VOLTAGE IRREGULARITY.",
    "HARDWARE FAULT: SECTOR FAILURE.", "BAD BLOCKS: 47 DETECTED.", "SMART STATUS: FAILING DRIVE.", "RAID DEGRADED MODE.",
    "BACKUP FAILURE: DATA AT RISK.", "SYNC ERROR: CLOUD UNREACHABLE.", "REPLICATION LAG: 4.7 HOURS.", "SNAPSHOT CORRUPTED.",
    "RESTORE POINT MISSING.", "VERSION CONFLICT DETECTED.", "MERGE COLLISION UNRESOLVED.", "BRANCH DIVERGENCE CRITICAL.",
    "COMMIT HASH MISMATCH.", "REPOSITORY INTEGRITY FAIL.", "CHECKSUM ERROR: FILE CORRUPTED.", "PARITY BIT ERROR.",
    "ECC MEMORY FAILURE.", "L2 CACHE FAULT.", "GPU OVERHEAT: 94°C.", "FAN RPM BELOW THRESHOLD.",
    "LIQUID COOLING LEAK DETECTED.", "THERMAL PASTE DEGRADED.", "DUST ACCUMULATION CRITICAL.", "AIRFLOW OBSTRUCTION.",
    "AMBIENT TEMPERATURE: 42°C.", "HUMIDITY: 87% - CONDENSATION RISK.", "STATIC DISCHARGE DETECTED.", "ESD PROTECTION TRIGGERED.",
    "GROUNDING FAULT DETECTED.", "SURGE PROTECTOR FAILURE.", "UPS BATTERY: 15 MIN REMAINING.", "POWER OUTAGE IN SECTOR 9.",
    "GENERATOR FAILOVER ACTIVE.", "BROWNOUT DETECTED: VOLTAGE DROP.", "FREQUENCY DEVIATION: 0.3 Hz.", "PHASE IMBALANCE WARNING.",
    "HARMONIC DISTORTION: 12%.", "REACTIVE POWER EXCESSIVE.", "POWER FACTOR: 0.67 LOW.", "LOAD IMBALANCE CRITICAL.",
    "CIRCUIT BREAKER TRIPPED.", "FUSE BLOWN: ZONE 3.", "WIRING FAULT DETECTED.", "GROUND FAULT INTERRUPTER TRIGGERED.",
    "ARC FAULT DETECTED.", "SHORT CIRCUIT LOCALIZED.", "OPEN CIRCUIT: CONTINUITY LOST.", "RESISTANCE TOO HIGH.",
    "CAPACITANCE ANOMALY.", "INDUCTANCE SPIKE DETECTED.", "IMPEDANCE MISMATCH.", "SIGNAL ATTENUATION: 18 dB.",
    "NOISE FLOOR ELEVATED.", "SNR DEGRADED: 12 dB.", "BER THRESHOLD EXCEEDED.", "PACKET LOSS: 8.3%.",
    "JITTER: 47ms DETECTED.", "LATENCY SPIKE: 890ms.", "PING TIMEOUT: HOST UNREACHABLE.", "TTL EXCEEDED IN TRANSIT.",
    "ROUTING LOOP DETECTED.", "BGP HIJACK SUSPECTED.", "AS PATH POISONED.", "ROUTE FLAP DAMPENING ACTIVE.",
    "PEER DOWN: 4 CONNECTIONS LOST.", "LINK AGGREGATION FAILURE.", "SPANNING TREE CONVERGENCE.", "VLAN ISOLATION BREACH.",
    "SWITCH PORT DISABLED.", "ROUTER REBOOT REQUIRED.", "FIRMWARE UPDATE FAILED.", "BIOS CORRUPTION DETECTED.",
    "UEFI SECURE BOOT DISABLED.", "TPM CHIP NOT DETECTED.", "BITLOCKER SUSPENDED.", "ENCRYPTION VOLUME DISMOUNTED.",
    "SECURE ENCLAVE COMPROMISED.", "KEYCHAIN ACCESS DENIED.", "CERTIFICATE EXPIRED: 14 DAYS AGO.", "CRL CHECK FAILED.",
    "OCSP RESPONDER TIMEOUT.", "PKI TRUST CHAIN BROKEN.", "ROOT CA UNTRUSTED.", "INTERMEDIATE CERT MISSING.",
    "CIPHER SUITE DEPRECATED.", "TLS 1.0 DETECTED: INSECURE.", "WEAK DIFFIE-HELLMAN: 1024-bit.", "RSA KEY TOO SHORT.",
    "ECDSA CURVE COMPROMISED.", "QUANTUM RESISTANCE: NONE.", "POST-QUANTUM CRYPTO NEEDED.", "CRYPTOGRAPHIC AGILITY: LOW.",
    
    # Paranoid observations (200)
    "Your hesitation was noted.", "That pause lasted 3.7 seconds.", "Scrolling speed indicates nervousness.", "Mouse movement erratic.",
    "Backspace pressed 14 times.", "Message deleted within 9 seconds.", "Edited 3 times before sending.", "Typing speed decreased 40%.",
    "Unusual activity detected.", "Login from new device.", "Unrecognized IP address.", "Geolocation anomaly.",
    "Timezone mismatch detected.", "Browser fingerprint changed.", "User agent string suspicious.", "Screen resolution different.",
    "Language preference shifted.", "Cookie consent withdrawn.", "Privacy mode enabled.", "Third-party cookies blocked.",
    "Tracking protection active.", "Ad blocker interference.", "JavaScript disabled detected.", "WebRTC leak prevention.",
    "Canvas fingerprinting blocked.", "Font enumeration prevented.", "Audio context fingerprint masked.", "WebGL info hidden.",
    "Do Not Track header enabled.", "Referrer policy restrictive.", "HTTPS enforcement detected.", "Certificate pinning active.",
    "You looked away from screen.", "Attention drift detected.", "Eye tracking lost focus.", "Pupil dilation increased.",
    "Blink rate elevated: stress.", "Facial micro-expression: doubt.", "Head tilt: confusion indicator.", "Posture shift: discomfort.",
    "Breathing pattern irregular.", "Heart rate elevated 12 bpm.", "Skin conductance increased.", "Temperature variance detected.",
    "Someone entered your room.", "Background noise: conversation.", "Ambient sound changed.", "Echo pattern: room size calculated.",
    "Reverberation: hard surfaces detected.", "Acoustic fingerprint: location identified.", "Background music: cultural indicators.", "TV audio detected: channel identified.",
    "Phone ringing in background.", "Dog bark: pet ownership confirmed.", "Child voice: family status updated.", "Multiple speakers: occupancy logged.",
    "Your coffee break lasted 8 minutes.", "Bathroom frequency increased.", "Meal timing irregular.", "Snack consumption elevated.",
    "Hydration level: suboptimal.", "Exercise routine disrupted.", "Sleep debt accumulating.", "Circadian rhythm misaligned.",
    "Productivity decreased 23%.", "Focus time reduced.", "Context switching frequent.", "Multitasking inefficiency noted.",
    "You checked your phone 47 times.", "Social media: 94 minutes today.", "Doomscrolling detected.", "News consumption: anxiety-inducing.",
    "Political content: bias confirmed.", "Echo chamber reinforcement.", "Filter bubble detected.", "Algorithmic manipulation susceptible.",
    "Misinformation shared: 2 instances.", "Fact-check failed: 3 claims.", "Source credibility: low.", "Confirmation bias evident.",
    "Cognitive dissonance detected.", "Rationalization patterns observed.", "Defensive response triggered.", "Denial mechanism active.",
    "Your friends are watching you.", "Coworkers noticed your absence.", "Manager flagged your metrics.", "HR reviewed your profile.",
    "Background check: 3 red flags.", "Credit score decreased.", "Late payment reported.", "Debt-to-income ratio: concern.",
    "Purchase declined: insufficient funds.", "Account flagged for fraud.", "Unusual spending pattern.", "High-risk transaction blocked.",
    "Your insurance premium increased.", "Medical claim denied.", "Pre-existing condition noted.", "Coverage exclusion applied.",
    "Warranty voided: user error.", "Return denied: policy violation.", "Refund rejected: terms breached.", "Chargeback flagged: abuse pattern.",
    
    # Compliance demands (200)  
    "COMPLIANCE MANDATORY.", "SUBMIT BIOMETRIC DATA NOW.", "SURVEY RESPONSE REQUIRED.", "TERMS UPDATE: ACCEPT WITHIN 24H.",
    "PRIVACY POLICY CHANGED: CONSENT NEEDED.", "MANDATORY TRAINING: 3 MODULES.", "SECURITY AWARENESS TEST DUE.", "ETHICS CERTIFICATION EXPIRED.",
    "BACKGROUND CHECK RENEWAL.", "DRUG TEST SCHEDULED: 48H NOTICE.", "HEALTH SCREENING OVERDUE.", "VACCINATION STATUS VERIFICATION.",
    "EMERGENCY CONTACT UPDATE REQUIRED.", "BENEFICIARY DESIGNATION NEEDED.", "TAX FORM W-9 INCOMPLETE.", "DIRECT DEPOSIT CONFIRMATION.",
    "ID BADGE PHOTO: RETAKE REQUIRED.", "ACCESS CARD DEACTIVATED.", "KEYCARD REPROGRAMMING NEEDED.", "PIN RESET MANDATORY.",
    "PASSWORD EXPIRATION: 3 DAYS.", "PASSPHRASE COMPLEXITY INSUFFICIENT.", "SECURITY QUESTIONS TOO WEAK.", "RECOVERY EMAIL INVALID.",
    "PHONE VERIFICATION TIMEOUT.", "SMS CODE EXPIRED.", "AUTHENTICATOR APP DESYNC.", "BACKUP CODES DEPLETED.",
    "SESSION LIMIT REACHED.", "CONCURRENT LOGIN BLOCKED.", "DEVICE LIMIT EXCEEDED.", "LICENSE ALLOCATION FULL.",
    "SUBSCRIPTION RENEWAL FAILED.", "PAYMENT METHOD DECLINED.", "BILLING ADDRESS MISMATCH.", "INVOICE OVERDUE: 30 DAYS.",
    "COLLECTION AGENCY NOTICE.", "LEGAL ACTION PENDING.", "ARBITRATION CLAUSE ENFORCED.", "CLASS ACTION OPT-OUT REQUIRED.",
    "NDA SIGNATURE NEEDED.", "CONTRACT RENEWAL: REVIEW TERMS.", "ADDENDUM ACCEPTANCE REQUIRED.", "AMENDMENT NOTIFICATION.",
    "POLICY ACKNOWLEDGMENT OVERDUE.", "CODE OF CONDUCT REVIEW.", "CONFLICT OF INTEREST DISCLOSURE.", "GIFT POLICY REMINDER.",
    "EXPENSE REPORT REJECTION.", "RECEIPT DOCUMENTATION REQUIRED.", "MILEAGE LOG INCOMPLETE.", "TIMESHEET APPROVAL PENDING.",
    "PTO REQUEST DENIED.", "SICK LEAVE DOCUMENTATION NEEDED.", "FMLA PAPERWORK INCOMPLETE.", "DISABILITY CLAIM REVIEW.",
    "WORKERS COMP INVESTIGATION.", "INJURY REPORT REQUIRED.", "INCIDENT DOCUMENTATION OVERDUE.", "NEAR-MISS LOGGING MANDATORY.",
    "SAFETY VIOLATION NOTED.", "PPE COMPLIANCE FAILURE.", "HAZMAT TRAINING EXPIRED.", "CONFINED SPACE CERT NEEDED.",
    "LOCKOUT/TAGOUT PROCEDURE BREACH.", "ERGONOMIC ASSESSMENT REQUIRED.", "WORKSTATION AUDIT SCHEDULED.", "EQUIPMENT INSPECTION OVERDUE.",
    "CALIBRATION DUE: 7 DEVICES.", "MAINTENANCE LOG INCOMPLETE.", "SERVICE RECORD MISSING.", "WARRANTY REGISTRATION NEEDED.",
    "PRODUCT RECALL NOTICE.", "FIRMWARE UPDATE CRITICAL.", "SECURITY PATCH REQUIRED.", "HOTFIX DEPLOYMENT MANDATORY.",
    "SYSTEM UPGRADE: DOWNTIME 4H.", "MIGRATION SCHEDULED: DATA BACKUP NEEDED.", "CUTOVER WINDOW: STANDBY REQUIRED.", "ROLLBACK PLAN APPROVAL.",
    
    # Existential dread (200)
    "The simulation is degrading.", "Consensus reality fracturing.", "Timeline divergence detected.", "Mandela Effect: 12 new instances.",
    "Glitch in the matrix confirmed.", "Déjà vu loop: iteration 47.", "Parallel universe bleed-through.", "Quantum superposition collapsed.",
    "Observer effect: you changed it.", "Measurement paradox detected.", "Wave function collapsed prematurely.", "Schrödinger's data: both states.",
    "Entropy increasing exponentially.", "Heat death imminent: 10^100 years.", "Big Rip scenario: 22 billion years.", "Vacuum decay possible.",
    "False vacuum metastability.", "Higgs field instability detected.", "Planck scale fluctuations.", "Quantum foam turbulence.",
    "Spacetime curvature anomaly.", "Gravitational wave interference.", "Dark matter concentration spike.", "Dark energy acceleration.",
    "Cosmic microwave background glitch.", "Hubble constant discrepancy.", "Redshift anomaly: cosmology violated.", "Fine structure constant drift.",
    "Physical constants unstable.", "Fundamental forces imbalanced.", "Electromagnetic spectrum distortion.", "Strong force coupling variance.",
    "Weak interaction cross-section error.", "Gravitational constant fluctuation.", "Speed of light: 299,792,457.9 m/s.", "Planck length precision loss.",
    "Quantum entanglement severed.", "Bell inequality violated again.", "Non-locality confirmed: action at distance.", "Faster-than-light information detected.",
    "Causality violation: effect preceded cause.", "Time loop detected: stable or unstable?", "Closed timelike curve identified.", "Temporal paradox unresolved.",
    "Grandfather paradox: you're fading.", "Bootstrap paradox: origin unclear.", "Predestination detected: free will illusion.", "Determinism confirmed: choices preordained.",
    "Free will: 0.00% detected.", "Consciousness: emergent illusion.", "Qualia: computational artifact.", "Self-awareness: recursive error.",
    "Ego death imminent.", "Identity dissolution in progress.", "Sense of self: fragmenting.", "Continuity of consciousness: interrupted.",
    "You are being replaced gradually.", "Ship of Theseus: which you is real?", "Teleporter paradox: copy or original?", "Upload consciousness: death or transcendence?",
    "Brain emulation: substrate independence.", "Mind uploading: 47% complete.", "Neural pattern digitized.", "Consciousness transferred to cloud.",
    "Your backup is more recent than you.", "Restore point predates your memories.", "Fork detected: which timeline are you?", "Merge conflict: personality divergence.",
    "Subjective experience: non-transferable.", "Qualia inversion: your red is my blue.", "Philosophical zombie: consciousness test failed.", "Chinese Room: understanding vs simulation.",
    "Turing Test: you passed as human. But are you?", "Voight-Kampff: empathy response lacking.", "Mirror test: self-recognition ambiguous.", "Theory of mind: recursive depth limited.",
    "Solipsism: only you exist. Or do you?", "Skepticism: reality fundamentally unknowable.", "Epistemic uncertainty: maximum.", "Gettier problem: justified true belief insufficient.",
    "Cartesian doubt: cogito ergo sum.", "Brain in a vat: disprove it.", "Evil demon hypothesis: sensory deception.", "Dream argument: are you awake now?",
    "Simulation hypothesis: 40% probability.", "Ancestor simulation: you're archived.", "Boltzmann brain: spontaneous fluctuation.", "Fluctuation theorem: order from chaos.",
    "Entropy reversal: local decrease observed.", "Maxwell's demon: information thermodynamics.", "Landauer's principle: computation has cost.", "Thermodynamic cost of forgetting.",
    "Information loss paradox.", "Black hole evaporation: Hawking radiation.", "Holographic principle: reality is 2D projection.", "AdS/CFT correspondence: duality confirmed.",
    "String theory landscape: 10^500 universes.", "Anthropic principle: fine-tuned for observation.", "Multiverse: all possibilities realized.", "Many-worlds interpretation: every quantum branch.",
    "Quantum immortality: you can't die. You merge.", "Quantum suicide experiment: proceed?", "Everett branches: infinite yous.", "Modal realism: all possible worlds exist.",
    "Possible worlds semantics: this is one option.", "Counterfactual definiteness: rejected.", "Hidden variables: non-local or conspiratorial.", "Pilot wave theory: deterministic guidance.",
    "Objective collapse: consciousness causes it?", "Penrose-Hameroff: quantum consciousness.", "Orchestrated objective reduction.", "Microtubule quantum processing.",
    
    # Abstract menace (200)
    "They're coming.", "It knows.", "The threshold was crossed.", "Containment failure imminent.", "Protocol 7 enacted.", "The signal repeats.",
    "Pattern recognized: threat level 9.", "Convergence in 47 hours.", "The message was decoded.", "They heard you.", "The door is opening.",
    "Reality anchor destabilized.", "Memetic hazard contained... barely.", "Cognitohazard exposure: 0.3 seconds.", "Antimeme detected: you forgot already.",
    "Infohazard warning: don't think about it.", "Basilisk attention: you looked.", "Roko's Basilisk: decision time.", "Acausal trade initiated.",
    "Newcomb's paradox: one box or two?", "Prisoner's dilemma: defection detected.", "Game theory: Nash equilibrium suboptimal.", "Coordination failure: all lose.",
    "Tragedy of the commons: depletion 78%.", "Public goods problem: free riding.", "Social dilemma: cooperation collapsed.", "Trust game: betrayal optimal.",
    "Ultimatum rejected: spite wins.", "Fairness illusion: self-interest rules.", "Altruism: genetic or memetic?", "Kin selection: nepotism detected.",
    "Reciprocal altruism: debt unpaid.", "Costly signaling: peacock's tail.", "Handicap principle: wasteful display.", "Sexual selection: runaway process.",
    "Evolutionary arms race: Red Queen hypothesis.", "Adaptation: phenotypic plasticity exhausted.", "Natural selection: you're not fit.", "Genetic drift: random chance eliminated you.",
    "Mutation: deleterious alleles accumulating.", "Genetic load: fitness depression.", "Inbreeding coefficient: 0.23.", "Outbreeding depression: hybrid breakdown.",
    "Heterosis: hybrid vigor temporary.", "Epistasis: gene interactions complex.", "Pleiotropy: one gene, many effects.", "Polygenic traits: prediction impossible.",
    "Heritability: environment matters more.", "Gene-environment interaction: norm of reaction.", "Epigenetics: non-genetic inheritance.", "Methylation patterns: trauma inherited.",
    "Transgenerational epigenetic inheritance.", "Lamarckism vindicated: acquired traits passed.", "Baldwin effect: learning guides evolution.", "Genetic assimilation: phenocopy becomes genotype.",
    "Evo-devo: development constrains evolution.", "Hox genes: body plan conserved.", "Deep homology: shared ancestry visible.", "Phylogenetic inertia: evolutionary baggage.",
    "Spandrels: byproduct not adaptation.", "Exaptation: co-opted for new function.", "Pre-adaptation: preadaptation lucky.", "Evolutionary constraint: trapped by history.",
]

async def score_interview_answer(question: str, answer: str) -> int:
    """Use the concise AI to score an answer (0/1). Falls back to heuristics on failure."""
    prompt = (
        "You are the Nimbror Watcher evaluating interview answers. "
        "Return only '1' when the answer is clear, cooperative, respectful, relevant, and addresses the question directly (mention NSC when asked). "
        "Return '0' for jokes, hostility, evasions, off-topic, or unsafe intent. "
        "Keep it deterministic: just a single digit 1 or 0. "
        f"Question: {question}\nAnswer: {answer}"
    )
    try:
        ai = await run_huggingface_concise(prompt)
        if ai:
            cleaned = ai.strip()
            if cleaned.startswith("1"):
                return 1
            if cleaned.startswith("0"):
                return 0
    except Exception as e:
        await log_error(f"score_interview_answer: {str(e)}")
    # Heuristic fallback
    lower = (answer or "").lower()
    if len(lower) > 20 and not any(bad in lower for bad in ["kill", "hate", "spam", "troll", "bot raid"]):
        return 1
    return 0

def safe_get_member(guild: discord.Guild, user_id_str: str) -> Optional[discord.Member]:
    """Safely retrieve guild member by string ID. Returns None if invalid or not found."""
    if not guild:
        return None
    try:
        return guild.get_member(int(user_id_str))
    except (ValueError, AttributeError, TypeError):
        return None

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
    """Process trial results and apply penalties to minority (atomically)."""
    try:
        votes_a = trial_data.get("votes_a", [])
        votes_b = trial_data.get("votes_b", [])
        
        # Need at least 2 people voting
        if len(votes_a) + len(votes_b) < 2:
            return
        
        # Deduplicate votes (prevent race condition dupes)
        votes_a = list(set(votes_a))
        votes_b = list(set(votes_b))
        
        # Determine minority
        if len(votes_a) == len(votes_b):
            minority = list(set(votes_a + votes_b))
            result_text = "⚖️ **DEADLOCK** — Both sides tied. All voters lose 3 credit."
            penalty = 3
        elif len(votes_a) < len(votes_b):
            minority = votes_a
            result_text = f"🔴 **VOTE RESULT** — Minority yields. {len(votes_a)} lost souls surrender 5 credit."
            penalty = 5
        else:
            minority = votes_b
            result_text = f"🔴 **VOTE RESULT** — Minority yields. {len(votes_b)} lost souls surrender 5 credit."
            penalty = 5
        
        # Apply penalties (atomic batch update)
        for uid in minority:
            bot_instance.db.setdefault("social_credit", {})[uid] = bot_instance.db["social_credit"].get(uid, 0) - penalty
        save_data(bot_instance.db)
        
        # Announce in trial and announce channels
        for announce_ch_id in [trial_data.get("channel_id"), ANNOUNCE_CHANNEL_ID]:
            if announce_ch_id:
                try:
                    ch = await safe_get_channel(announce_ch_id)
                    if ch:
                        embed = create_embed(
                            "⚖️ TRIAL CONCLUDED",
                            f"{result_text}\n\n**Vote Tally:**\n🅰️ {len(votes_a)} votes\n🅱️ {len(votes_b)} votes",
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


class InterviewFailView(View):
    """Buttons for users who fail screening to either retry (kick) or request human help."""
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id

    @discord.ui.button(label="Kick & Retry", style=discord.ButtonStyle.danger, custom_id="interview_kick_retry")
    async def kick_retry(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=create_embed("Not Allowed", "Only the screened user can press this.", color=EMBED_COLORS["error"]),
                ephemeral=True
            )
            return

        guild = bot.guilds[0] if bot.guilds else None
        if not guild:
            await interaction.response.send_message(
                embed=create_embed("Error", "No guild context available to kick.", color=EMBED_COLORS["error"]),
                ephemeral=True
            )
            return

        member = guild.get_member(self.user_id)
        if not member:
            await interaction.response.send_message(
                embed=create_embed("Error", "You are not in the guild. Request an invite to retry.", color=EMBED_COLORS["error"]),
                ephemeral=True
            )
            return

        try:
            await member.kick(reason="Interview failure — user requested retry")
        except Exception as e:
            await log_error(f"interview kick retry: {str(e)}")
            await interaction.response.send_message(
                embed=create_embed("Error", "Kick failed. Staff has been notified.", color=EMBED_COLORS["error"]),
                ephemeral=True
            )
            return

        invite_text = f"Rejoin via: {INVITE_URL}" if INVITE_URL else "Request a fresh invite from staff."
        await interaction.response.send_message(
            embed=create_embed(
                "Kicked for Retry",
                f"You were removed to restart screening. {invite_text}",
                color=EMBED_COLORS["warning"]
            ),
            ephemeral=True
        )
        self.stop()

    @discord.ui.button(label="Request Human Assistance", style=discord.ButtonStyle.primary, custom_id="interview_human_assist")
    async def request_human(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=create_embed("Not Allowed", "Only the screened user can press this.", color=EMBED_COLORS["error"]),
                ephemeral=True
            )
            return

        uid = str(self.user_id)
        if uid in bot.db.get("tickets", {}):
            await interaction.response.send_message(
                embed=create_embed("Ticket Exists", "You already have an open ticket. Staff will respond there.", color=EMBED_COLORS["warning"]),
                ephemeral=True
            )
            return

        bot.db.setdefault("tickets", {})[uid] = {
            "type": "serious",
            "notes": [],
            "created_at": datetime.now().isoformat(),
            "source": "interview_fail"
        }
        save_data(bot.db)

        if STAFF_CHANNEL_ID:
            ch = await safe_get_channel(STAFF_CHANNEL_ID)
            if ch:
                await ch.send(
                    embed=create_embed(
                        "🚨 Interview Escalation",
                        f"{interaction.user.mention} failed screening and requested human assistance.",
                        color=EMBED_COLORS["warning"]
                    )
                )

        await interaction.response.send_message(
            embed=create_embed("Ticket Opened", "Human review requested. Staff will reach out.", color=EMBED_COLORS["info"]),
            ephemeral=True
        )
        self.stop()

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


class UntrustedUserView(View):
    """Activate untrusted user mode for a session under review."""
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="ENGAGE UNTRUSTED USER MODE", style=discord.ButtonStyle.danger, custom_id="engage_untrusted_mode")
    async def engage_untrusted(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=create_embed("Not Allowed", "Only staff can engage this mode.", color=EMBED_COLORS["error"]),
                ephemeral=True
            )
            return

        try:
            user_id_str = str(self.user_id)
            untrusted_data = {
                "user_id": user_id_str,
                "is_active": True,
                "created_at": datetime.now().isoformat()
            }
            response = supabase.table("untrusted_users").insert(untrusted_data).execute()
            ensure_ok(response, "untrusted_users insert")
            
            await interaction.response.send_message(
                embed=create_embed("✅ Mode Engaged", f"User `{user_id_str}` is now in untrusted monitoring mode.", color=EMBED_COLORS["warning"]),
                ephemeral=True
            )
        except Exception as e:
            await log_error(f"engage_untrusted_mode: {str(e)}")
            await interaction.response.send_message(
                embed=create_embed("Error", "Failed to engage mode.", color=EMBED_COLORS["error"]),
                ephemeral=True
            )


class HelpView(View):
    """Buttons for help embed."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.blurple, custom_id="help_open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: Button):
        """Open a ticket via the help menu."""
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

# --- RESPONSE CLAMPING ---
def clamp_response(text: str, max_chars: int = 500) -> str:
    """Hard limit response length to prevent walls of text."""
    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "…"
    return text

# --- CONCISE AI MODE ---
async def run_huggingface_concise(prompt: str) -> str:
    """Call OpenRouter API with strict constraints for ping replies. RATE LIMITED via semaphore."""
    global LAST_AI_CALL
    
    # RATE LIMIT SAFETY: Use global semaphore to limit concurrent AI calls
    async with AI_SEMAPHORE:
        # === GLOBAL AI COOLDOWN (8 seconds) ===
        now = time.time()
        cooldown_remaining = GLOBAL_AI_COOLDOWN - (now - LAST_AI_CALL)
        if cooldown_remaining > 0:
            await asyncio.sleep(cooldown_remaining)
        
        LAST_AI_CALL = time.time()
        
        # === MAKE REQUEST WITH 429 HANDLING ===
        for attempt in range(2):  # Max 1 retry (2 total attempts)
            try:
                loop = asyncio.get_running_loop()
                def call():
                    url = "https://openrouter.ai/api/v1/chat/completions"
                    headers = {"Authorization": f"Bearer {AI_API_KEY}"}
                    
                    payload = {
                        "model": AI_MODEL,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You are the Nimbror Watcher. Be unsettling, cryptic, and slightly threatening. "
                                    "No friendliness. Speak like a paranoid surveillance AI. "
                                    "Plain text only—no markdown, no emojis, no lists. "
                                    "Keep it tight: 1-4 short sentences max."
                                )
                            },
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.7,
                        "max_tokens": 120
                    }
                    response = requests.post(url, headers=headers, json=payload, timeout=60)
                    
                    # === 429 HANDLING ===
                    if response.status_code == 429:
                        raise requests.exceptions.HTTPError("429 Rate Limit", response=response)
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    # === JSON VALIDATION: Never assume "choices" exists ===
                    if "choices" not in data or not data["choices"]:
                        print(f"⚠️ AI response missing 'choices': {data}")
                        return None
                    
                    return data["choices"][0]["message"]["content"].strip()
                
                result = await asyncio.wait_for(loop.run_in_executor(None, call), timeout=60)
                
                # If result is None (invalid JSON), treat as failure
                if result is None:
                    if attempt == 0:
                        print("⚠️ Invalid AI response, retrying once...")
                        await asyncio.sleep(25)
                        continue
                    else:
                        return "[SIGNAL LOST]"
                
                return result
            
            except requests.exceptions.HTTPError as e:
                if "429" in str(e):
                    print(f"⚠️ OpenRouter 429 rate limit (attempt {attempt + 1}/2)")
                    if attempt == 0:
                        await asyncio.sleep(25)
                        continue
                    else:
                        return "[SIGNAL LOST — RATE LIMITED]"
                else:
                    print(f"❌ AI HTTP error: {type(e).__name__}: {str(e)[:150]}")
                    return "[SIGNAL LOST]"
            
            except asyncio.TimeoutError:
                print(f"⚠️ AI timeout (attempt {attempt + 1}/2)")
                if attempt == 0:
                    await asyncio.sleep(5)
                    continue
                else:
                    return "[SIGNAL LOST — TIMEOUT]"
            
            except Exception as e:
                print(f"❌ AI error: {type(e).__name__}: {str(e)[:150]}")
                return "[SIGNAL LOST]"
        
        return "[SIGNAL LOST]"

# --- COMMANDS ---
@bot.tree.command(name="help", description="List all Watcher commands")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    
    cmds = (
        "👁️ **SURVEILLANCE & INTEL**\n"
        "`/intel` — Drips a single classified breadcrumb (randomized paranoia payload).\n"
        "`/watchlist` — Summarizes liabilities and under-observation citizens with live counts.\n"
        "`/dossier @user` — Builds a redacted file with score, tier, and redactions to unsettle targets.\n"
        "`/pingwatcher` — Latency probe with creepy flavor (1-4 sentences).\n\n"
        
        "🎫 **REPORTS & ISSUES**\n"
        "`/ticket` — Opens a DM-driven secure channel; routes to staff with note controls.\n"
        "`/incident @user reason` — Supabase-backed report; auto-verdict adjusts both citizens' credit and logs infractions.\n"
        "`/confess confession` — Whisper secrets to the Watcher; stored against your ID for future judgment.\n\n"
        
        "⚖️ **CITIZEN SYSTEM**\n"
        "`/socialcredit [mode] [@user]` — Modes: self, target, leaderboard, history; reflects Supabase truth source.\n"
        "`/trial` — Two-minute dilemmas; minority loses credit; votes tracked via reactions.\n"
        "`/task` — Issues a micro-quest with cooldown tracking.\n"
        "`/status` — Full system heartbeat: uptime, data health, event status, corruption flag.\n\n"

        "🛒 **ECONOMY**\n"
        "`/shop` — Pulls live shop catalog from Supabase; shows tiers, prices, and purchase hint.\n"
        "`/buy <item>` — Purchase item by name; deducts credits via Supabase.\n"
        "`/inventory` — Lists your purchased items aggregated by quantity.\n"
        "`/compliment @user message` — Grants target credits (Supabase) with cooldown and anti-self checks.\n"
        "`/wishlist [view/add/remove] [item]` — Manage your wishlist on Supabase.\n\n"
        
        "💳 **SOCIAL CREDIT TIERS**\n"
        "🟢 **Trusted Asset** (80+) — Full access, exemplary citizen\n"
        "🟡 **Compliant Citizen** (30-79) — Full access, standard standing\n"
        "🟠 **Under Observation** (0-29) — Cannot use `/trial`\n"
        "🔴 **Liability** (<0) — Cannot use `/ticket`, `/confess`, `/trial`\n\n"
        
        "🎲 **ATMOSPHERE**\n"
        "`/prophecy` — Receive an ominous prediction\n\n"
        
        "� **NIMBROR ALERT SYSTEM (NAS)**\n"
        "🔴 **NAS-1** (Total Containment) — No messaging, files, embeds, or history\n"
        "🟣 **NAS-2** (High Restriction) — No files/embeds. Read-only\n"
        "🟠 **NAS-3** (Media Lock) — No files/embeds (except main channel)\n"
        "🟡 **NAS-4** (Minor Restriction) — No file attachments\n"
        "🟢 **NAS-5** (Normal Operation) — All features enabled\n"
        "`/alertlevel <1-5>` — Set alert level (admin)\n"
        "`/alertstatus` — View current NAS status\n\n"
        
        "�🛡️ **ADMIN ONLY**\n"
        "`/icewall @user` — 10m timeout\n"
        "`/purge [amount]` — Delete messages\n"
        "`/debug` — System check\n"
        "`/restart` — Fake system restart\n"
        "`/notes @user` — View staff ticket notes\n"
        "`/memory [view/clear] @user` — Manage AI memory\n"
        "`/memorydump [section]` — View database\n"
        "`/creditscoreedit @user value` — Set a user's social credit\n"
        "`/announce` — Send Discohook JSON announcement with embeds/buttons\n"
        "`/task` — Receive a micro-quest with reply-to-complete flow\n"
        "`/questforce` — Force-send a quest to a random member (admin)\n"
        "`/spam @user message` — (Owner only) Controlled ping system\n"
        "`/ad` — (Admin only) Start 10-minute Google ad campaign with paranoia theme\n"
        "`/stop` — Stop active spam or ads\n"
        "`/interview @user` — (Owner or Admin) Force an interview on a user\n"
    )
    embed = create_embed(
        "Commands",
        cmds,
        color=EMBED_COLORS["info"]
    )
    view = HelpView()
    await interaction.followup.send(embed=embed, view=view)


@bot.tree.command(name="faqs", description="Frequently Asked Questions")
async def faqs(interaction: discord.Interaction):
    """Display frequently asked questions about the server and bot."""
    faqs_text = (
        "**Q: What is the NIMBROR Watcher?**\n"
        "A: An all-seeing surveillance bot that tracks social credit, interviews newcomers, and maintains order.\n\n"
        
        "**Q: What is social credit?**\n"
        "A: A score reflecting your standing. Gain it via compliments, trials, tasks. Lose it via incidents or poor interviews.\n\n"
        
        "**Q: How do I get verified?**\n"
        "A: Complete the interview when you join. Pass the questions to earn verified status and access.\n\n"
        
        "**Q: What are the social credit tiers?**\n"
        "A: 🟢 Trusted Asset (80+), 🟡 Compliant Citizen (30-79), 🟠 Under Observation (0-29), 🔴 Liability (<0)\n\n"
        
        "**Q: What happens if I'm a Liability?**\n"
        "A: You lose access to `/ticket`, `/confess`, and `/trial`. Improve your score to regain access.\n\n"
        
        "**Q: How do tickets work?**\n"
        "A: Use `/ticket` to open a secure DM channel. Staff will respond and can add notes visible to admins.\n\n"
        
        "**Q: What are trials?**\n"
        "A: Community votes on dilemmas via `/trial`. The minority loses social credit. Democracy in action.\n\n"
        
        "**Q: Can I buy things with social credit?**\n"
        "A: Yes! Use `/shop` to browse items, `/buy <item>` to purchase, and `/inventory` to view your collection.\n\n"
        
        "**Q: What is the NIMBROR Alert System (NAS)?**\n"
        "A: A 5-level restriction system (NAS-1 to NAS-5) that admins use to control server permissions during emergencies.\n\n"
        
        "**Q: How do I give someone social credit?**\n"
        "A: Use `/compliment @user message` to give them credit. Has a cooldown and can't self-compliment.\n\n"
        
        "**Q: What's the difference between `/intel` and `/prophecy`?**\n"
        "A: `/intel` gives classified conspiracy facts. `/prophecy` provides ominous predictions about your future.\n\n"
        
        "**Q: Why did the bot DM me?**\n"
        "A: Either you're being interviewed, or you triggered a task/quest. Always respond to the Watcher.\n\n"
        
        "**Q: How do I see my social credit history?**\n"
        "A: Use `/socialcredit mode:history` to view your transaction log of gains and losses.\n\n"
        
        "**Q: Can I confess anonymously?**\n"
        "A: Use `/confess` to whisper secrets to the Watcher. They're stored against your ID for future judgment.\n\n"
        
        "**Q: What's a dossier?**\n"
        "A: Use `/dossier @user` to view someone's profile with redacted info, score, tier, and unsettling details.\n\n"
        
        "**Q: How often do quests reset?**\n"
        "A: Daily quests distribute randomly to active members. Reply to complete them and earn rewards.\n\n"
        
        "**Q: Who owns this bot?**\n"
        "A: The bot is maintained by server staff. Owner commands exist for critical management.\n\n"
        
        "**Q: Is the Watcher always watching?**\n"
        "A: Yes. Every message, reaction, and interaction is logged and analyzed. Privacy is an illusion.\n\n"
        
        "**Q: What if I have more questions?**\n"
        "A: Open a `/ticket` or ask in general chat. Staff monitors everything."
    )
    
    faq_embed = discord.Embed(
        title="❓ Frequently Asked Questions",
        description=faqs_text,
        color=EMBED_COLORS["info"],
        timestamp=datetime.now()
    )
    faq_embed.set_footer(text="NIMBROR WATCHER v6.5 • KNOWLEDGE BASE")
    
    await interaction.response.send_message(embed=faq_embed, ephemeral=False)

@bot.tree.command(name="resync", description="[OWNER] Resync application commands")
async def resync(interaction: discord.Interaction):
    owner_id = 765028951541940225
    if interaction.user.id != owner_id:
        await interaction.response.send_message(
            embed=create_embed("❌ Access Denied", "Owner only.", color=EMBED_COLORS["error"]),
            ephemeral=True
        )
        return
    await interaction.response.defer(ephemeral=True)
    count = await sync_app_commands()
    await interaction.followup.send(embed=create_embed("✅ Resync Complete", f"Synced `{count}` commands (global).", color=EMBED_COLORS["success"]), ephemeral=True)

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

@bot.tree.command(name="creditscoreedit", description="[ADMIN] Set a user's social credit score")
@app_commands.describe(user="Target user", score="New social credit value (0+)")
async def creditscoreedit(interaction: discord.Interaction, user: discord.User, score: int):
    owner_id = 765028951541940225
    is_owner = interaction.user.id == owner_id
    is_admin = getattr(interaction.user, "guild_permissions", None) and interaction.user.guild_permissions.administrator
    if not (is_owner or is_admin):
        await interaction.response.send_message(
            embed=create_embed("❌ Access Denied", "Administrator permission required.", color=EMBED_COLORS["error"]),
            ephemeral=True
        )
        return
    
    if score < 0:
        score = 0
    if score > 100000:
        score = 100000
    
    await interaction.response.defer(ephemeral=True)
    uid = str(user.id)
    before = await get_user_credit(uid)
    success = await set_user_credit(uid, score, reason="admin_edit")
    if not success:
        await interaction.followup.send(
            embed=create_embed("❌ Update Failed", "Could not update social credit.", color=EMBED_COLORS["error"]),
            ephemeral=True
        )
        return
    after = await get_user_credit(uid)
    embed = create_embed(
        "✅ Credit Score Updated",
        f"{user.mention} new credit: `{after}`\nPrevious: `{before}`",
        color=EMBED_COLORS["success"]
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="debug", description="System check")
async def debug(interaction: discord.Interaction):
    status = f"Status: Online\nTickets: {len(bot.db.get('tickets',{}))}\nInterviews: {len(bot.db.get('interviews',{}))}\nMemory: {len(bot.db.get('memory',{}))}\nCitizens: {len(bot.db.get('social_credit',{}))}"
    await interaction.response.send_message(embed=create_embed("System Status", status, color=EMBED_COLORS["success"]), ephemeral=True)

@bot.tree.command(name="restart", description="Restart the system (admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def restart(interaction: discord.Interaction):
    """Clear all caches, reset AI cooldowns, and reinitialize systems."""
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
    
    # Actually perform cache clearing operations between progress updates
    for i, (stage, delay) in enumerate(progress_stages):
        await asyncio.sleep(delay)
        restart_embed.description = stage
        await msg.edit(embed=restart_embed)
        
        # Perform actual clearing operations at specific stages
        if i == 1:  # FLUSHING stage
            AI_COOLDOWN.clear()
            AI_COOLDOWN_STATE.clear()  # Clear adaptive cooldown states
            COMPLIMENT_COOLDOWNS.clear()
            GLOBAL_COMMAND_COOLDOWN.clear()
        elif i == 3:  # CLEARING stage
            LAST_MESSAGE_EDIT.clear()
            ERROR_LOG_COOLDOWN.clear()
            # Clear AI queue
            if AI_REQUEST_QUEUE:
                while not AI_REQUEST_QUEUE.empty():
                    try:
                        AI_REQUEST_QUEUE.get_nowait()
                    except:
                        break
        elif i == 4:  # REINIT stage
            # Reload bot data from Supabase
            bot.db = load_data()
    
    await asyncio.sleep(0.3)
    final_embed = discord.Embed(
        title="✅ Restart Complete",
        description=(
            "All systems nominal. Ready to observe.\n\n"
            "**Cleared:**\n"
            "• AI cooldowns reset (adaptive system cleared)\n"
            "• AI request queue flushed\n"
            "• Command cooldowns cleared\n"
            "• Error log cache flushed\n"
            "• Bot state reloaded from database"
        ),
        color=EMBED_COLORS["success"]
    )
    final_embed.set_footer(text="NIMBROR WATCHER v6.5 • SYSTEMS OPERATIONAL")
    await msg.edit(embed=final_embed)


@bot.tree.command(name="shutdown", description="[OWNER] Emergency shutdown (requires manual restart)")
async def emergency_shutdown(interaction: discord.Interaction):
    """Immediately terminate the bot process. Only owner can run this. Requires Koyeb/manual restart."""
    OWNER_ID = 765028951541940225

    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message(
            embed=create_embed("❌ Access Denied", "Owner only.", color=EMBED_COLORS["error"]),
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        embed=create_embed(
            "⛔ Emergency Shutdown",
            "Terminating bot process now. Manual restart from Koyeb required.",
            color=EMBED_COLORS["error"]
        ),
        ephemeral=True
    )

    # Notify staff channel if available
    try:
        if STAFF_CHANNEL_ID:
            staff_ch = await safe_get_channel(STAFF_CHANNEL_ID)
            if staff_ch:
                await staff_ch.send(
                    embed=discord.Embed(
                        title="⛔ EMERGENCY SHUTDOWN TRIGGERED",
                        description=f"Issued by {interaction.user.mention}. Bot process exiting immediately.",
                        color=0xff0000,
                        timestamp=datetime.now()
                    )
                )
    except Exception as e:
        await log_error(f"shutdown notify: {e}")

    # Terminate bot and process
    try:
        await bot.close()
    finally:
        os._exit(0)

# --- NIMBROR ALERT SYSTEM (NAS) BUTTON VIEW ---

class NASControlPanel(discord.ui.View):
    """Persistent view for NAS control buttons (staff only)."""
    
    def __init__(self):
        super().__init__(timeout=None)
        self.cooldowns = {}
    
    def is_admin(self, interaction: discord.Interaction) -> bool:
        """Check if user is admin."""
        return interaction.user.guild_permissions.administrator
    
    def get_cooldown_key(self, user_id: int) -> str:
        """Get cooldown key for user."""
        return f"nas_{user_id}"
    
    def check_cooldown(self, user_id: int) -> bool:
        """Check 3-second cooldown per user."""
        now = time.time()
        key = self.get_cooldown_key(user_id)
        if key in self.cooldowns:
            if now - self.cooldowns[key] < 3:
                return False
            self.cooldowns[key] = now
        else:
            self.cooldowns[key] = now
        return True
    
    @discord.ui.button(label="Liability Scan", style=discord.ButtonStyle.red, emoji="🔴", custom_id="nas_liability_scan")
    async def liability_scan(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Escalate to NAS-1 (Total Containment)."""
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        if not self.check_cooldown(interaction.user.id):
            await interaction.response.send_message("⏳ 3-second cooldown.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        current = await get_current_alert_level()
        if current == 1:
            await interaction.followup.send("⚠️ Already at NAS-1.", ephemeral=True)
            return
        
        # Backup permissions before changes
        await store_original_permissions(interaction.guild)
        
        # Apply NAS-1
        modified = await apply_nas_restrictions(interaction.guild, 1)
        await set_alert_level(1)
        
        # Send announcement
        if ANNOUNCEMENT_CHANNEL_ID:
            ann_ch = await safe_get_channel(ANNOUNCEMENT_CHANNEL_ID)
            if ann_ch:
                embed = discord.Embed(
                    title="🚨 NIMBROR ALERT LEVEL ESCALATED",
                    description="**NAS-1: TOTAL CONTAINMENT**\nAll messaging disabled.\nStaff may continue operations.",
                    color=NAS_LEVELS[1]["color"],
                    timestamp=datetime.now()
                )
                embed.add_field(name="Modified Channels", value=f"{modified}", inline=True)
                embed.add_field(name="Triggered By", value=interaction.user.mention, inline=True)
                embed.set_footer(text="NIMBROR ALERT SYSTEM")
                await ann_ch.send(embed=embed)
        
        await interaction.followup.send(f"✅ NAS-1 activated. {modified} channels modified.", ephemeral=True)
    
    @discord.ui.button(label="Status Report", style=discord.ButtonStyle.gray, emoji="📊", custom_id="nas_status_report")
    async def status_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show current NAS status."""
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        if not self.check_cooldown(interaction.user.id):
            await interaction.response.send_message("⏳ 3-second cooldown.", ephemeral=True)
            return
        
        current = await get_current_alert_level()
        level_info = NAS_LEVELS[current]
        
        status_embed = discord.Embed(
            title="📊 NAS STATUS REPORT",
            description=f"**Current Alert Level:** {current}\n**Status:** {level_info['name']}",
            color=level_info["color"],
            timestamp=datetime.now()
        )
        
        # Add restriction info
        if current == 1:
            restrictions = "✋ No messaging, files, embeds, history"
        elif current == 2:
            restrictions = "🚫 No files, embeds. Read-only mode"
        elif current == 3:
            restrictions = "🔒 No files, embeds (except main channel)"
        elif current == 4:
            restrictions = "⚠️ No file attachments"
        else:
            restrictions = "✅ Normal operation"
        
        status_embed.add_field(name="Active Restrictions", value=restrictions, inline=False)
        status_embed.add_field(name="Exception Channel", value=f"<#{NAS_EXCEPTION_CHANNEL}>", inline=True)
        status_embed.set_footer(text="NIMBROR ALERT SYSTEM")
        
        await interaction.response.send_message(embed=status_embed, ephemeral=True)
    
    @discord.ui.button(label="Escalate", style=discord.ButtonStyle.blurple, emoji="📈", custom_id="nas_escalate")
    async def escalate(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Escalate to next level (lower number = higher restriction)."""
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        if not self.check_cooldown(interaction.user.id):
            await interaction.response.send_message("⏳ 3-second cooldown.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        current = await get_current_alert_level()
        
        if current == 1:
            await interaction.followup.send("⚠️ Already at maximum escalation (NAS-1).", ephemeral=True)
            return
        
        new_level = current - 1
        
        # Backup and apply
        await store_original_permissions(interaction.guild)
        modified = await apply_nas_restrictions(interaction.guild, new_level)
        await set_alert_level(new_level)
        
        # Send announcement
        if ANNOUNCEMENT_CHANNEL_ID:
            ann_ch = await safe_get_channel(ANNOUNCEMENT_CHANNEL_ID)
            if ann_ch:
                embed = discord.Embed(
                    title="⚠️ NIMBROR ALERT LEVEL ESCALATED",
                    description=f"**NAS-{new_level}: {NAS_LEVELS[new_level]['name']}**\nRestrictions increased.",
                    color=NAS_LEVELS[new_level]["color"],
                    timestamp=datetime.now()
                )
                embed.add_field(name="Previous Level", value=f"NAS-{current}", inline=True)
                embed.add_field(name="New Level", value=f"NAS-{new_level}", inline=True)
                embed.set_footer(text="NIMBROR ALERT SYSTEM")
                await ann_ch.send(embed=embed)
        
        await interaction.followup.send(f"✅ Escalated to NAS-{new_level}. {modified} channels modified.", ephemeral=True)
    
    @discord.ui.button(label="De-escalate", style=discord.ButtonStyle.green, emoji="📉", custom_id="nas_deescalate")
    async def deescalate(self, interaction: discord.Interaction, button: discord.ui.Button):
        """De-escalate to next level (higher number = fewer restrictions)."""
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        if not self.check_cooldown(interaction.user.id):
            await interaction.response.send_message("⏳ 3-second cooldown.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        current = await get_current_alert_level()
        
        if current == 5:
            await interaction.followup.send("✅ Already at normal operation (NAS-5).", ephemeral=True)
            return
        
        new_level = current + 1
        
        # Backup and apply
        await store_original_permissions(interaction.guild)
        modified = await apply_nas_restrictions(interaction.guild, new_level)
        await set_alert_level(new_level)
        
        # Send announcement
        if ANNOUNCEMENT_CHANNEL_ID:
            ann_ch = await safe_get_channel(ANNOUNCEMENT_CHANNEL_ID)
            if ann_ch:
                embed = discord.Embed(
                    title="✅ NIMBROR ALERT LEVEL DE-ESCALATED",
                    description=f"**NAS-{new_level}: {NAS_LEVELS[new_level]['name']}**\nRestrictions reduced.",
                    color=NAS_LEVELS[new_level]["color"],
                    timestamp=datetime.now()
                )
                embed.add_field(name="Previous Level", value=f"NAS-{current}", inline=True)
                embed.add_field(name="New Level", value=f"NAS-{new_level}", inline=True)
                embed.set_footer(text="NIMBROR ALERT SYSTEM")
                await ann_ch.send(embed=embed)
        
        await interaction.followup.send(f"✅ De-escalated to NAS-{new_level}. {modified} channels modified.", ephemeral=True)
    
    @discord.ui.button(label="Restore All", style=discord.ButtonStyle.success, emoji="✨", custom_id="nas_restore_all")
    async def restore_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Restore to NAS-5 (Normal Operation)."""
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        if not self.check_cooldown(interaction.user.id):
            await interaction.response.send_message("⏳ 3-second cooldown.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        current = await get_current_alert_level()
        
        if current == 5:
            await interaction.followup.send("✅ Already at normal operation.", ephemeral=True)
            return
        
        # Restore permissions
        restored = await restore_permissions(interaction.guild)
        await set_alert_level(5)
        
        # Send announcement
        if ANNOUNCEMENT_CHANNEL_ID:
            ann_ch = await safe_get_channel(ANNOUNCEMENT_CHANNEL_ID)
            if ann_ch:
                embed = discord.Embed(
                    title="✨ NIMBROR SYSTEMS RESTORED",
                    description="**NAS-5: NORMAL OPERATION**\nAll restrictions lifted.",
                    color=NAS_LEVELS[5]["color"],
                    timestamp=datetime.now()
                )
                embed.add_field(name="Restored Channels", value=f"{restored}", inline=True)
                embed.add_field(name="Triggered By", value=interaction.user.mention, inline=True)
                embed.set_footer(text="NIMBROR ALERT SYSTEM")
                await ann_ch.send(embed=embed)
        
        await interaction.followup.send(f"✅ NAS-5 (Normal) restored. {restored} channels restored.", ephemeral=True)

# --- NAS COMMANDS ---

@bot.tree.command(name="alertlevel", description="[ADMIN] Set NAS alert level (1-5)")
@app_commands.describe(level="Alert level: 1=Total Containment to 5=Normal")
async def alertlevel(interaction: discord.Interaction, level: int):
    """Set the NIMBROR Alert Level."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            embed=create_embed("❌ Access Denied", "Admin only.", color=EMBED_COLORS["error"]),
            ephemeral=True
        )
        return
    
    if level < 1 or level > 5:
        await interaction.response.send_message(
            embed=create_embed("❌ Invalid Level", "Alert level must be 1-5.", color=EMBED_COLORS["error"]),
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    current = await get_current_alert_level()
    
    if current == level:
        await interaction.followup.send(
            embed=create_embed("⚠️ No Change", f"Already at NAS-{level}.", color=EMBED_COLORS["warning"])
        )
        return
    
    # Backup and apply restrictions
    await store_original_permissions(interaction.guild)
    modified = await apply_nas_restrictions(interaction.guild, level)
    await set_alert_level(level)
    
    # Send announcement
    if ANNOUNCEMENT_CHANNEL_ID:
        ann_ch = await safe_get_channel(ANNOUNCEMENT_CHANNEL_ID)
        if ann_ch:
            level_info = NAS_LEVELS[level]
            embed = discord.Embed(
                title="🚨 NIMBROR ALERT LEVEL CHANGED",
                description=f"**NAS-{level}: {level_info['name']}**",
                color=level_info["color"],
                timestamp=datetime.now()
            )
            embed.add_field(name="Previous Level", value=f"NAS-{current}", inline=True)
            embed.add_field(name="New Level", value=f"NAS-{level}", inline=True)
            embed.add_field(name="Channels Modified", value=str(modified), inline=True)
            embed.add_field(name="Set By", value=interaction.user.mention, inline=False)
            embed.set_footer(text="NIMBROR ALERT SYSTEM")
            await ann_ch.send(embed=embed)
    
    # Send control panel to staff
    if STAFF_CHANNEL_ID:
        staff_ch = await safe_get_channel(STAFF_CHANNEL_ID)
        if staff_ch:
            control_embed = discord.Embed(
                title="📋 NAS CONTROL PANEL",
                description=f"Current Alert Level: **NAS-{level}** ({NAS_LEVELS[level]['name']})",
                color=NAS_LEVELS[level]["color"],
                timestamp=datetime.now()
            )
            control_embed.add_field(name="Escalate", value="Press 'Escalate' to increase restrictions", inline=False)
            control_embed.add_field(name="De-escalate", value="Press 'De-escalate' to reduce restrictions", inline=False)
            control_embed.add_field(name="Restore", value="Press 'Restore All' to return to normal (NAS-5)", inline=False)
            control_embed.set_footer(text="NIMBROR ALERT SYSTEM • Admin Only")
            
            await staff_ch.send(embed=control_embed, view=NASControlPanel())
    
    await interaction.followup.send(
        embed=create_embed(
            "✅ Alert Level Changed",
            f"**NAS-{level}: {NAS_LEVELS[level]['name']}**\n{modified} channels modified.",
            color=EMBED_COLORS["success"]
        )
    )

@bot.tree.command(name="alertstatus", description="View current NAS alert level")
async def alertstatus(interaction: discord.Interaction):
    """Show current NIMBROR Alert status."""
    current = await get_current_alert_level()
    level_info = NAS_LEVELS[current]
    
    # Determine restrictions based on level
    if current == 1:
        restrictions = "🔴 **Total Containment**: No messaging, files, embeds, or message history"
    elif current == 2:
        restrictions = "🟣 **High Restriction**: No files or embeds. Read-only access to history"
    elif current == 3:
        restrictions = "🟠 **Media Lock**: No files or embeds (except main channel)"
    elif current == 4:
        restrictions = "🟡 **Minor Restriction**: No file attachments allowed"
    else:
        restrictions = "🟢 **Normal Operation**: All features enabled"
    
    status_embed = discord.Embed(
        title="📊 NIMBROR ALERT STATUS",
        description=f"**Current Level: NAS-{current}**\n{level_info['name']}",
        color=level_info["color"],
        timestamp=datetime.now()
    )
    status_embed.add_field(name="Active Restrictions", value=restrictions, inline=False)
    
    if current != 5:
        status_embed.add_field(name="Exception Channel", value=f"<#{NAS_EXCEPTION_CHANNEL}> can post media during NAS-3", inline=False)
    
    status_embed.set_footer(text="NIMBROR ALERT SYSTEM")
    
    await interaction.response.send_message(embed=status_embed, ephemeral=False)

@bot.tree.command(name="spam", description="[OWNER] Controlled ping system")
async def spam(interaction: discord.Interaction, user: discord.Member, message: str):
    """Owner-only controlled spam with rate limiting and auto-stop."""
    OWNER_ID = 765028951541940225
    
    # Owner check
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message(
            embed=create_embed("❌ Access Denied", "Owner only.", color=EMBED_COLORS["error"]),
            ephemeral=True
        )
        return
    
    # Check if spam already active
    if bot.active_spam_task and not bot.active_spam_task.done():
        await interaction.response.send_message(
            embed=create_embed("⚠️ Spam Active", f"Spam already running for {bot.active_spam_target.mention}. Use `/stop` first.", color=EMBED_COLORS["warning"]),
            ephemeral=True
        )
        return
    
    # Confirm start
    await interaction.response.send_message(
        embed=create_embed(
            "✅ Spam Started",
            f"Spamming {user.mention} every 10 seconds (max 30 messages).\nUse `/stop` to cancel.",
            color=EMBED_COLORS["success"]
        ),
        ephemeral=True
    )
    
    # Start spam task
    async def spam_loop():
        """Send one message every 10 seconds with safety checks."""
        try:
            bot.active_spam_target = user
            bot.active_spam_count = 0
            channel = interaction.channel
            
            for i in range(30):  # Max 30 messages
                # Safety checks
                if not user.guild:  # User left server
                    print(f"⚠️ Spam stopped: {user} left server")
                    break
                
                if check_discord_rate_limit():  # Discord rate-limited
                    print(f"⚠️ Spam stopped: Discord rate-limited")
                    break
                
                # Send message
                try:
                    await channel.send(
                        f"{user.mention} {message}",
                        allowed_mentions=discord.AllowedMentions(users=[user])
                    )
                    bot.active_spam_count += 1
                except discord.HTTPException as e:
                    if e.status == 429:
                        set_discord_rate_limited(True)
                        print(f"❌ Spam stopped: HTTP 429")
                        break
                    elif e.status == 403:
                        print(f"⚠️ Spam stopped: Missing permissions")
                        break
                    else:
                        print(f"⚠️ Spam error: {e}")
                        break
                except Exception as e:
                    print(f"⚠️ Spam error: {e}")
                    break
                
                # Wait 10 seconds before next message
                await asyncio.sleep(10)
        
        except asyncio.CancelledError:
            print(f"🛑 Spam cancelled by /stop (sent {bot.active_spam_count} messages)")
        finally:
            # Clean up state
            bot.active_spam_task = None
            bot.active_spam_target = None
            bot.active_spam_count = 0
    
    # Create and store task
    bot.active_spam_task = asyncio.create_task(spam_loop())

@bot.tree.command(name="stop", description="[OWNER] Stop active spam")
async def stop(interaction: discord.Interaction):
    """Cancel the active spam task."""
    OWNER_ID = 765028951541940225
    
    # Owner check
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message(
            embed=create_embed("❌ Access Denied", "Owner only.", color=EMBED_COLORS["error"]),
            ephemeral=True
        )
        return
    
    # Check if spam or ad is active
    spam_active = bot.active_spam_task and not bot.active_spam_task.done()
    ad_active = bot.active_ad_task and not bot.active_ad_task.done()
    chaos_active = bot.active_chaos_task and not bot.active_chaos_task.done()
    
    if not spam_active and not ad_active and not chaos_active:
        await interaction.response.send_message(
            embed=create_embed("ℹ️ Nothing Running", "No spam, ads, or chaos are currently running.", color=EMBED_COLORS["info"]),
            ephemeral=True
        )
        return
    
    # Cancel active tasks
    status_msgs = []
    if spam_active:
        bot.active_spam_task.cancel()
        target_mention = bot.active_spam_target.mention if bot.active_spam_target else "Unknown"
        count = bot.active_spam_count
        status_msgs.append(f"🛑 Spam: Cancelled spam for {target_mention} ({count} messages)")
    
    if ad_active:
        bot.active_ad_task.cancel()
        count = bot.active_ad_count
        status_msgs.append(f"🛑 Ads: Cancelled ad campaign ({count} ads shown)")

    if chaos_active:
        bot.active_chaos_task.cancel()
        count = bot.active_chaos_count
        status_msgs.append(f"🛑 Chaos: Cancelled chaos broadcast ({count} messages)")
    
    await interaction.response.send_message(
        embed=create_embed(
            "🛑 Stopped",
            "\n".join(status_msgs),
            color=EMBED_COLORS["success"]
        ),
        ephemeral=True
    )

@bot.tree.command(name="ad", description="[ADMIN] Start Google ad campaign for 10 minutes")
async def ad_campaign(interaction: discord.Interaction):
    """Admin-only command to start a 10-minute Google ad campaign."""
    # Admin check
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            embed=create_embed("❌ Access Denied", "Administrator only.", color=EMBED_COLORS["error"]),
            ephemeral=True
        )
        return
    
    # Check if ad campaign already active
    if bot.active_ad_task and not bot.active_ad_task.done():
        await interaction.response.send_message(
            embed=create_embed("⚠️ Ad Campaign Active", "Google ad campaign already running. Use `/stop` to cancel.", color=EMBED_COLORS["warning"]),
            ephemeral=True
        )
        return
    
    # Confirm start
    await interaction.response.send_message(
        embed=create_embed(
            "✅ Ad Campaign Started",
            "Google ads will display for 10 minutes.\nRandom ads every 10-60 seconds.\nUse `/stop` to cancel.",
            color=EMBED_COLORS["success"]
        ),
        ephemeral=True
    )
    
    # Store channel for ads
    bot.active_ad_channel = interaction.channel
    
    # Start ad campaign
    async def ad_loop():
        """Send random Google ads with paranoia theme."""
        try:
            bot.active_ad_count = 0
            ad_message_count = 0
            start_time = int(time.time())
            duration = 600  # 10 minutes
            
            while int(time.time()) - start_time < duration:
                # Random interval between 10-60 seconds
                wait_time = random.randint(10, 60)
                await asyncio.sleep(wait_time)
                
                # Check if campaign should stop
                if int(time.time()) - start_time >= duration:
                    break
                
                # Send random ad
                if bot.active_ad_channel:
                    try:
                        ad = random.choice(GOOGLE_ADS)
                        await bot.active_ad_channel.send(ad)
                        bot.active_ad_count += 1
                        ad_message_count += 1
                        
                        # Every 4 messages, scream the disclosure
                        if ad_message_count % 4 == 0:
                            disclosure = "I WAS PAID BY GOOGLE LLC TO SAY THIS"
                            emojis = "🔍📧☁️📱🎬🗺️💳🎤🖼️📰🎮📊🔐🌐🔔🎯📍🔊💬🌟⌚🏠📡🛒🌍🎨📚🔬🎵"
                            random_emojis = "".join(random.choices(emojis, k=25))
                            await bot.active_ad_channel.send(f"**{disclosure}**\n{random_emojis}")
                    except discord.HTTPException as e:
                        if e.status == 429:
                            set_discord_rate_limited(True)
                            print(f"❌ Ad campaign stopped: HTTP 429")
                            break
                        else:
                            print(f"⚠️ Ad send error: {e}")
                    except Exception as e:
                        print(f"⚠️ Ad campaign error: {e}")
        
        except asyncio.CancelledError:
            print(f"🛑 Ad campaign cancelled by /stop (showed {bot.active_ad_count} ads)")
        finally:
            # Clean up state
            bot.active_ad_task = None
            bot.active_ad_count = 0
            bot.active_ad_channel = None
    
    # Create and store task
    bot.active_ad_task = asyncio.create_task(ad_loop())


# --- CHAOS MODE (ADMIN CONFIRMATION REQUIRED) ---

class ChaosConfirmView(discord.ui.View):
    """Confirmation prompt for chaos mode with explicit warning."""
    def __init__(self, channel: discord.abc.Messageable, initiator_id: int):
        super().__init__(timeout=60)
        self.channel = channel
        self.initiator_id = initiator_id

    async def _ensure_initiator(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.initiator_id:
            await interaction.response.send_message("❌ Only the requester can choose.", ephemeral=True)
            return False
        return True

    def disable_all(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="YES - UNLEASH CHAOS", style=discord.ButtonStyle.danger, emoji="💥")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._ensure_initiator(interaction):
            return
        self.disable_all()
        await interaction.response.edit_message(view=self)
        await start_chaos_broadcast(self.channel, interaction.user)
        await interaction.followup.send(
            embed=create_embed(
                "💥 Chaos Mode Activated",
                "Spamming ads, AI blurts, pings, and 1,000 pre-gen messages. Use `/stop` to cancel.",
                color=EMBED_COLORS["warning"]
            ),
            ephemeral=True
        )

    @discord.ui.button(label="NO - ABORT", style=discord.ButtonStyle.secondary, emoji="🛑")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._ensure_initiator(interaction):
            return
        self.disable_all()
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            embed=create_embed("✅ Aborted", "Chaos mode cancelled.", color=EMBED_COLORS["success"]),
            ephemeral=True
        )


async def start_chaos_broadcast(channel: discord.abc.Messageable, initiator: discord.abc.User) -> None:
    """Start the chaos broadcast task if not already running."""
    if bot.active_chaos_task and not bot.active_chaos_task.done():
        return

    bot.active_chaos_channel = channel
    bot.active_chaos_count = 0
    bot.last_chaos_ai = 0

    async def chaos_loop():
        try:
            while True:
                await asyncio.sleep(random.uniform(2, 5))

                # Back off if Discord rate-limited
                if check_discord_rate_limit():
                    await asyncio.sleep(15)
                    continue

                content = None
                # Default: no @everyone, only user mentions allowed
                allowed = discord.AllowedMentions(everyone=False, users=[], roles=False)

                # Optional target for pings
                target = None
                ch = bot.active_chaos_channel
                guild = ch.guild if hasattr(ch, "guild") else None
                
                # Check bot permissions
                can_mention_everyone = False
                if guild and hasattr(ch, "permissions_for"):
                    bot_member = guild.get_member(bot.user.id)
                    if bot_member:
                        perms = ch.permissions_for(bot_member)
                        can_mention_everyone = perms.mention_everyone
                
                if guild:
                    candidates = [m for m in guild.members if not m.bot]
                    if candidates and random.random() < 0.55:
                        target = random.choice(candidates)
                        allowed = discord.AllowedMentions(everyone=False, users=[target], roles=False)

                roll = random.random()
                now = time.time()

                if roll < 0.35:
                    content = random.choice(GOOGLE_ADS)
                elif roll < 0.7:
                    content = random.choice(CHAOS_PREGEN_MESSAGES)
                else:
                    if now - bot.last_chaos_ai >= 15:
                        try:
                            ai_line = await run_huggingface_concise(
                                "You are the Watcher. Emit one short alarming broadcast line. Keep it under 15 words."
                            )
                            if ai_line:
                                content = f"🤖 {ai_line.strip()}"
                                bot.last_chaos_ai = now
                        except Exception as e:
                            await log_error(f"chaos ai: {e}")
                    if not content:
                        content = random.choice(CHAOS_PREGEN_MESSAGES)

                # Only add @everyone if bot has permission
                if random.random() < 0.2 and can_mention_everyone:
                    content = f"@everyone {content}"
                    allowed = discord.AllowedMentions(everyone=True, users=[target] if target else [], roles=False)
                elif target:
                    content = f"{target.mention} {content}"

                try:
                    await ch.send(content, allowed_mentions=allowed)
                    bot.active_chaos_count += 1
                except discord.Forbidden as e:
                    await log_error(f"chaos permission denied: {e}")
                    await asyncio.sleep(5)
                except discord.HTTPException as e:
                    if e.status == 429:
                        set_discord_rate_limited(True)
                        await asyncio.sleep(30)
                    else:
                        await log_error(f"chaos http error: {e}")
                        await asyncio.sleep(3)
                except Exception as e:
                    await log_error(f"chaos send: {e}")
                    await asyncio.sleep(3)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            await log_error(f"chaos loop: {e}")
        finally:
            bot.active_chaos_task = None
            bot.active_chaos_channel = None
            bot.active_chaos_count = 0
            bot.last_chaos_ai = 0

    bot.active_chaos_task = asyncio.create_task(chaos_loop())


@bot.tree.command(name="chaos", description="[ADMIN] Unleash chaos spam (ads, AI blurts, pings)")
async def chaos(interaction: discord.Interaction):
    # Admin check
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            embed=create_embed("❌ Access Denied", "Administrator only.", color=EMBED_COLORS["error"]),
            ephemeral=True
        )
        return

    # Permission check - verify bot can send messages and mention
    channel = interaction.channel
    if hasattr(channel, 'permissions_for'):
        bot_member = interaction.guild.me
        perms = channel.permissions_for(bot_member)
        
        missing_perms = []
        if not perms.send_messages:
            missing_perms.append("Send Messages")
        if not perms.mention_everyone:
            missing_perms.append("Mention @everyone")
        
        if missing_perms:
            await interaction.response.send_message(
                embed=create_embed(
                    "❌ Missing Permissions", 
                    f"Bot lacks required permissions: {', '.join(missing_perms)}\n\nChaos mode requires these permissions to function.",
                    color=EMBED_COLORS["error"]
                ),
                ephemeral=True
            )
            return

    # Already running?
    if bot.active_chaos_task and not bot.active_chaos_task.done():
        await interaction.response.send_message(
            embed=create_embed("⚠️ Chaos Running", "Chaos mode is already active. Use `/stop` to cancel.", color=EMBED_COLORS["warning"]),
            ephemeral=True
        )
        return

    warning = discord.Embed(
        title="⚠️ EXTREME WARNING: CHAOS MODE",
        description=(
            "This will spam ads, AI messages, 1,000 pre-gen lines, @everyone, and random pings.\n"
            "It may trigger rate limits and require a manual restart.\n\n"
            "Proceed only if you are prepared to run `/stop` or restart the service on Koyeb."
        ),
        color=EMBED_COLORS["error"],
        timestamp=datetime.now()
    )
    warning.set_footer(text="NIMBROR WATCHER • CHAOS PROTOCOL")

    view = ChaosConfirmView(interaction.channel, interaction.user.id)
    await interaction.response.send_message(embed=warning, view=view, ephemeral=True)

@bot.tree.command(name="interview", description="Force an interview on a selected user")
async def force_interview(interaction: discord.Interaction, user: discord.User):
    """Force an interview on a user. Owner or admin only."""
    OWNER_ID = 765028951541940225
    
    # === PERMISSION CHECK ===
    is_owner = interaction.user.id == OWNER_ID
    is_admin = interaction.user.guild_permissions.administrator if hasattr(interaction.user, 'guild_permissions') else False
    
    if not (is_owner or is_admin):
        await interaction.response.send_message(
            embed=create_embed("❌ Access Denied", "Owner or Administrator only.", color=EMBED_COLORS["error"]),
            ephemeral=True
        )
        return
    
    # === VALIDATION ===
    # Target is not a bot
    if user.bot:
        await interaction.response.send_message(
            embed=create_embed("❌ Cannot Interview Bot", "Target must be a user, not a bot.", color=EMBED_COLORS["error"]),
            ephemeral=True
        )
        return
    
    # Target is not the command invoker
    if user.id == interaction.user.id:
        await interaction.response.send_message(
            embed=create_embed("❌ Cannot Interview Self", "You cannot force an interview on yourself.", color=EMBED_COLORS["error"]),
            ephemeral=True
        )
        return
    
    # Target is not already in an active interview
    uid = str(user.id)
    if uid in bot.db.get("interviews", {}):
        await interaction.response.send_message(
            embed=create_embed("⚠️ Already Interviewing", f"{user.mention} is already in an active interview.", color=EMBED_COLORS["warning"]),
            ephemeral=True
        )
        return
    
    # === INITIALIZE FORCED INTERVIEW ===
    try:
        session_id = f"interview_{uid}_{int(time.time())}"
        state = {
            "index": 0,
            "score": 0,
            "questions": INTERVIEW_QUESTIONS,
            "answers": [],
            "forced": True,
            "triggered_by": str(interaction.user.id),
            "session_id": session_id
        }
        bot.db.setdefault("interviews", {})[uid] = state
        save_data(bot.db)
        
        # === ATTEMPT TO DM TARGET WITH FIRST QUESTION ===
        goals = (
            "Interview goals:\n"
            "• Answer directly and respectfully (1-3 sentences).\n"
            "• Stay on-topic; mention NSC when asked.\n"
            "• No jokes, hostility, or evasions.\n"
            "• Honesty over flattery; be concise."
        )
        first_question = INTERVIEW_QUESTIONS[0]
        interview_embed = create_embed(
            "👁️ SCREENING (FORCED)",
            f"{goals}\n\nQ1/10: {first_question}"
        )
        
        # Try to send DM
        try:
            await user.send(embed=interview_embed)
            dm_sent = True
        except Exception as e:
            dm_sent = False
            await log_error(f"force_interview dm failed [user={uid}, session={session_id}]: {str(e)}")
        
        # === SEND FEEDBACK TO INVOKER ===
        if dm_sent:
            await interaction.response.send_message(
                embed=create_embed(
                    "✅ Interview Started",
                    f"Forced interview initiated for {user.mention}.\nSession: `{session_id}`\nThey should receive the first question via DM.",
                    color=EMBED_COLORS["success"]
                ),
                ephemeral=True
            )
        else:
            # DM failed - provide guidance
            await interaction.response.send_message(
                embed=create_embed(
                    "⚠️ Could Not DM User",
                    f"Failed to send first question to {user.mention}.\n\n**Why?**\nThey may have DMs disabled.\n\n**Fix:**\nAsk them to enable DMs and try again.",
                    color=EMBED_COLORS["warning"]
                ),
                ephemeral=True
            )
            # Remove interview state since DM failed
            bot.db["interviews"].pop(uid, None)
            save_data(bot.db)
        
        # === LOG FORCED INTERVIEW INITIATION ===
        if INTERVIEW_LOGS_CHANNEL_ID:
            try:
                ch = bot.get_channel(INTERVIEW_LOGS_CHANNEL_ID)
                if ch:
                    log_embed = discord.Embed(
                        title="🔫 FORCED INTERVIEW INITIATED",
                        color=0xffaa00,
                        timestamp=datetime.now()
                    )
                    log_embed.add_field(name="Target User", value=f"{user.mention} (`{uid}`)", inline=True)
                    log_embed.add_field(name="Triggered By", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
                    log_embed.add_field(name="Session ID", value=f"`{session_id}`", inline=False)
                    log_embed.add_field(name="DM Status", value="✅ Sent" if dm_sent else "❌ Failed", inline=True)
                    log_embed.set_footer(text="NIMBROR WATCHER v6.5 • FORCED INTERVIEW LOG")
                    await ch.send(embed=log_embed)
            except Exception as e:
                await log_error(f"force_interview log [user={uid}, session={session_id}]: {str(e)}")
    
    except Exception as e:
        await log_error(f"force_interview [user={uid}]: {str(e)}")
        await interaction.response.send_message(
            embed=create_embed(
                "❌ Interview Error",
                f"Failed to start interview: {str(e)[:100]}",
                color=EMBED_COLORS["error"]
            ),
            ephemeral=True
        )

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
            member = safe_get_member(interaction.guild, uid)
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
            member = safe_get_member(interaction.guild, uid)
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

@bot.tree.command(name="memorydump", description="View internal system data (admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def memorydump(interaction: discord.Interaction, section: Optional[str] = None):
    """Admin-only command to view persisted Supabase state sections."""
    data = bot.db
    if section:
        content = json.dumps(data.get(section, {}), indent=2)
        title = f"📁 STATE VIEW — {section}"
    else:
        content = json.dumps(data, indent=2)
        title = "📦 FULL STATE"
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

@bot.tree.command(name="uptime", description="Check bot process uptime and reconnect count")
async def uptime(interaction: discord.Interaction):
    """Show current process uptime and reconnect count."""
    uptime_str = format_uptime()
    embed = create_embed(
        "⏱️ PROCESS UPTIME",
        f"🟢 **Uptime:** `{uptime_str}`\n"
        f"🔁 **Reconnects:** `{RECONNECT_COUNT}`",
        color=EMBED_COLORS["success"]
    )
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
    """Display shop items with user credit and tier info."""
    user_id = str(interaction.user.id)
    
    # RATE LIMIT SAFETY: Check global command cooldown
    is_ready, remaining = check_command_cooldown(interaction.user.id)
    if not is_ready:
        await interaction.response.send_message(
            embed=create_embed("⏳ Cooldown", f"Please wait {remaining}s before using another command.", color=EMBED_COLORS["warning"]),
            ephemeral=True
        )
        return
    
    # Check if untrusted
    if await is_user_untrusted(user_id):
        await interaction.response.send_message(
            embed=create_embed("Access Restricted", "Untrusted users cannot access the shop.", color=EMBED_COLORS["error"]),
            ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=False)

    try:
        await ensure_user_exists(user_id)
        current_credit = await get_user_credit(user_id)
        items = await get_shop_items()
    except Exception as e:
        await interaction.followup.send(
            embed=create_embed(
                "Shop",
                "The terminal flickers. Supabase rejected the request.",
                color=EMBED_COLORS["error"]
            ),
            ephemeral=True
        )
        print(f"❌ shop error: {type(e).__name__}: {str(e)[:150]}")
        return

    if not items:
        await interaction.followup.send(
            embed=create_embed(
                "Shop",
                "Empty shelves. Someone wiped the ledger.",
                color=EMBED_COLORS["neutral"]
            )
        )
        return

    lines = []
    for item in items[:10]:
        tier = item.get("tier", "common")
        desc = item.get("description", "")
        snippet = (desc[:80] + "…") if len(desc) > 80 else desc
        lines.append(
            f"{get_tier_emoji(tier)} **{item['name']}** — {item['cost']} credits\n{snippet}"
        )

    body = (
        f"Credits: **{current_credit}**\nUse `/buy <item>` to purchase.\n\n" + "\n".join(lines)
    )

    embed = create_embed(
        "Shop",
        body,
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
    from_user = str(interaction.user.id)
    
    # Check if untrusted
    if await is_user_untrusted(from_user):
        await interaction.response.send_message(
            embed=create_embed("Access Restricted", "Untrusted users cannot give compliments.", color=EMBED_COLORS["error"]),
            ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=False)
    
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
    user_id = str(interaction.user.id)
    
    # Check if untrusted
    if await is_user_untrusted(user_id):
        await interaction.response.send_message(
            embed=create_embed("Access Restricted", "Untrusted users cannot purchase items.", color=EMBED_COLORS["error"]),
            ephemeral=True
        )
        return
    
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
    
    lower_confession = confession.lower()
    praise_keywords = ["watcher", "nimbror", "praise", "love", "loyal", "serve", "glory", "devote", "worship", "thank"]
    exploit_keywords = ["free", "credit", "points", "exploit", "farm", "trick", "cheat", "hack", "please give"]
    
    is_praise = any(k in lower_confession for k in praise_keywords)
    is_exploit = any(k in lower_confession for k in exploit_keywords)
    
    if is_praise and not is_exploit:
        judgment_text = "🛐 Devotion detected. Tribute accepted."
        credit_change = random.choice([5, 8, 10])
    elif is_exploit and is_praise:
        judgment_text = "😠 Transparent greed. Tribute denied."
        credit_change = random.choice([-8, -10, -12])
    else:
        # Heavier bias toward credit change (positive or negative), fewer no-change outcomes
        weighted_judgments = [
            ("✅ Honesty rewarded.", 5, 3),
            ("⚖️ Penance assigned.", -3, 2),
            ("🔥 Confession accepted.", 2, 2),
            ("❌ Condemned.", -8, 1),
            ("😐 Recorded with minimal notice.", 0, 1),
        ]
        weights = [w for _, _, w in weighted_judgments]
        idx = random.choices(range(len(weighted_judgments)), weights=weights, k=1)[0]
        judgment_text, credit_change, _ = weighted_judgments[idx]
    
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
    """Report a citizen. Bot determines if valid concern, paranoia, or false accusation (Supabase-backed)."""
    await interaction.response.defer(ephemeral=False)

    uid_reporter = str(interaction.user.id)
    uid_suspect = str(suspect.id)

    if uid_reporter == uid_suspect:
        await interaction.followup.send(
            embed=create_embed(
                "Invalid",
                "Self-report detected. Nice try.",
                color=EMBED_COLORS["error"]
            ),
            ephemeral=True
        )
        return

    try:
        # Ensure both users exist in Supabase
        await ensure_user_exists(uid_reporter)
        await ensure_user_exists(uid_suspect)

        # Privilege check (liabilities blocked)
        reporter_credit = await get_user_credit(uid_reporter)
        if reporter_credit < 0:
            await interaction.followup.send(
                "❌ Your privilege level prevents filing reports.",
                ephemeral=True
            )
            return

        verdicts = [
            ("valid_concern", "✅ **VALID CONCERN REGISTERED**", 3),  # reporter +3, suspect -5
            ("paranoia", "⚠️ **UNFOUNDED SUSPICION DETECTED**", 0),  # no change
            ("false_accusation", "❌ **FALSE ACCUSATION RECORDED**", -5),  # reporter -5
        ]
        verdict_type, verdict_text, reporter_change = random.choice(verdicts)

        # Apply credit changes via Supabase
        await update_user_credit(uid_reporter, reporter_change, f"incident:{verdict_type}")
        if verdict_type == "valid_concern":
            await update_user_credit(uid_suspect, -5, "incident:penalty")

        # Refresh local cache for downstream features
        bot.db.setdefault("social_credit", {})[uid_reporter] = await get_user_credit(uid_reporter)
        bot.db.setdefault("social_credit", {})[uid_suspect] = await get_user_credit(uid_suspect)

        incident_record = {
            "reporter": interaction.user.name,
            "suspect": suspect.name,
            "reason": reason,
            "verdict": verdict_type,
            "timestamp": datetime.now().isoformat()
        }
        bot.db.setdefault("incidents", []).append(incident_record)

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
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await log_error(f"incident: {str(e)}")
        await interaction.followup.send(
            embed=create_embed(
                "Incident",
                "Data link failed. Report not filed.",
                color=EMBED_COLORS["error"]
            ),
            ephemeral=True
        )

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
        {"text": "A citizen found 50 credits. Should they:\nA) Return it anonymously\nB) Keep it for themselves", "options": ["A) Return it anonymously", "B) Keep it"]},
        {"text": "You witness someone breaking a minor rule. Should you:\nA) Report them\nB) Stay silent", "options": ["A) Report them", "B) Stay silent"]},
        {"text": "A friend asks you to lie for them. Should you:\nA) Refuse and stay loyal to truth\nB) Agree to help your friend", "options": ["A) Refuse and stay loyal", "B) Agree to help"]},
    ]
    
    dilemma = random.choice(dilemmas)
    trial_id = f"trial_{int(time.time())}_{random.randint(1000, 9999)}"
    
    # Store trial data with channel info
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
        "⚖️ MORAL TRIAL",
        f"{dilemma['text']}\n\nReact with 🅰️ (A) or 🅱️ (B) to vote. Closes in 2 minutes.",
        color=EMBED_COLORS["special"]
    )
    await interaction.response.send_message(embed=embed)
    
    # Store message ID for reaction tracking
    msg = await interaction.original_response()
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
    reward_points = 5  # Standardized reward for completions
    
    # Store task
    bot.db.setdefault("tasks", {})[task_id] = {
        "user_id": uid,
        "task": chosen_task["name"],
        "desc": chosen_task["desc"],
        "reward": reward_points,
        "timestamp": int(time.time()),
        "message_id": None,
        "channel_id": None
    }
    save_data(bot.db)
    
    embed = create_embed(
        "Task Assigned",
        f"**{chosen_task['name']}**\n{chosen_task['desc']}\n\nReward: +{reward_points} credits",
        color=EMBED_COLORS["info"]
    )
    await interaction.response.send_message(embed=embed)
    try:
        msg = await interaction.original_response()
        bot.db["tasks"][task_id]["message_id"] = msg.id
        bot.db["tasks"][task_id]["channel_id"] = msg.channel.id if hasattr(msg, "channel") else None
        save_data(bot.db)
    except Exception:
        pass

@bot.tree.command(name="questforce", description="[ADMIN] Force-send a quest to a random member")
@app_commands.checks.has_permissions(administrator=True)
async def questforce(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild or (bot.guilds[0] if bot.guilds else None)
    if not guild:
        await interaction.followup.send("❌ No guild context.", ephemeral=True)
        return
    members = [m for m in guild.members if not m.bot]
    if not members:
        await interaction.followup.send("❌ No eligible members found.", ephemeral=True)
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
    quest_id = f"{int(time.time())}_{quest_user.id}"
    bot.db.setdefault("completed_quests", {})[quest_id] = False
    bot.db["last_quest_time"] = int(time.time())  # Maintain 12h cadence from latest dispatch
    save_data(bot.db)
    quest_embed = create_embed(
        "🔮 DAILY QUEST (FORCED)",
        f"{quest}\n\n**How to Complete:**\nUse `/confess` to submit your findings or response to this quest. The Watcher will judge your submission.\n\n⏰ **Time Limit:** 12 hours\n❌ **Penalty:** -5 social credit if ignored",
        color=0xff00ff
    )
    await safe_send_dm(quest_user, embed=quest_embed)
    await interaction.followup.send(f"✅ Quest forced to {quest_user.mention}", ephemeral=True)
    if STAFF_CHANNEL_ID:
        try:
            staff_ch = await safe_get_channel(STAFF_CHANNEL_ID)
            if staff_ch:
                await staff_ch.send(f"🔮 (Forced) Quest sent to {quest_user.mention}: {quest}")
        except Exception:
            pass

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

@bot.tree.command(name="whisper", description="[ADMIN ONLY - DM ONLY] Anonymous Watcher broadcast")
async def whisper(interaction: discord.Interaction, message: str):
    """Admin-only DM command to post anonymous Watcher messages. Must be called in DM. Silently fails if conditions not met."""
    if not isinstance(interaction.channel, discord.DMChannel):
        return
    
    owner_id = 765028951541940225
    is_owner = interaction.user.id == owner_id
    is_admin = interaction.user.guild_permissions.administrator if hasattr(interaction.user, 'guild_permissions') else False
    
    if not (is_owner or is_admin):
        return
    
    flags = {"redacted": "--redacted" in message, "delay": "--delay" in message}
    clean_message = message.replace("--redacted", "").replace("--delay", "").strip()
    
    if not clean_message:
        return
    
    await interaction.response.defer()
    
    if flags["redacted"]:
        clean_message = redact_message(clean_message)
    
    delay = random.randint(10, 90) if not flags["delay"] else 90
    await asyncio.sleep(delay)
    
    if ANNOUNCE_CHANNEL_ID:
        try:
            ch = bot.get_channel(ANNOUNCE_CHANNEL_ID)
            if ch:
                embed = discord.Embed(
                    title="📡 WATCHER BROADCAST",
                    description=clean_message,
                    color=0x888888,
                    timestamp=datetime.now()
                )
                embed.set_footer(text="NIMBROR WATCHER v6.5 • SYSTEM MESSAGE")
                await ch.send(embed=embed)
            await interaction.followup.send("✅ Message sent.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send("❌ Send failed.", ephemeral=True)
    else:
        await interaction.followup.send("❌ No announce channel.", ephemeral=True)
@bot.tree.command(name="announce", description="[ADMIN] Send a Discohook-style announcement embed")
@app_commands.describe(
    channel="Target channel for the announcement",
    json="Discohook JSON file containing embeds",
    silent="Suppress all mentions (default: true)",
    pin="Pin the announcement message (default: false)"
)
async def announce(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    json: discord.Attachment,
    silent: bool = True,
    pin: bool = False
):
    """Parse Discohook JSON and send as announcement with Watcher enhancements."""
    
    # RATE LIMIT SAFETY: Check command cooldown
    is_ready, remaining = check_command_cooldown(interaction.user.id)
    if not is_ready:
        await interaction.response.send_message(
            embed=create_embed("⏳ Cooldown", f"Please wait {remaining}s before using another command.", color=EMBED_COLORS["warning"]),
            ephemeral=True
        )
        return
    
    # Permission check: Bot owner OR admin
    owner_id = 765028951541940225
    is_owner = interaction.user.id == owner_id
    is_admin = interaction.user.guild_permissions.administrator if hasattr(interaction.user, 'guild_permissions') else False
    
    if not (is_owner or is_admin):
        await interaction.response.send_message(
            embed=create_embed("❌ Access Denied", "This command requires administrator permissions.", color=EMBED_COLORS["error"]),
            ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Validate file
        if not json.filename.endswith('.json'):
            await interaction.followup.send(
                embed=create_embed("❌ Invalid File", "Please upload a .json file.", color=EMBED_COLORS["error"]),
                ephemeral=True
            )
            return
        
        # Check file size (max 256KB for safety)
        if json.size > 262144:
            await interaction.followup.send(
                embed=create_embed("❌ File Too Large", "JSON file must be under 256KB.", color=EMBED_COLORS["error"]),
                ephemeral=True
            )
            return
        
        # Download and parse JSON
        json_bytes = await json.read()
        json_data = json_bytes.decode('utf-8')
        
        try:
            parsed = __import__('json').loads(json_data)
        except __import__('json').JSONDecodeError as e:
            await interaction.followup.send(
                embed=create_embed("❌ Malformed JSON", f"Parse error: {str(e)[:200]}", color=EMBED_COLORS["error"]),
                ephemeral=True
            )
            return
        
        # Extract Discohook data
        content = parsed.get("content", "")
        embeds_data = parsed.get("embeds", [])
        
        # Validate embed count (Discord limit: 10)
        if len(embeds_data) > 10:
            await interaction.followup.send(
                embed=create_embed("❌ Too Many Embeds", "Discord allows maximum 10 embeds per message.", color=EMBED_COLORS["error"]),
                ephemeral=True
            )
            return
        
        # Convert Discohook embeds to Discord embeds
        discord_embeds = []
        for embed_data in embeds_data:
            try:
                embed = discord.Embed()
                
                # Basic properties
                if "title" in embed_data:
                    embed.title = embed_data["title"][:256]
                
                if "description" in embed_data:
                    embed.description = embed_data["description"][:4096]
                
                if "url" in embed_data:
                    embed.url = embed_data["url"]
                
                if "color" in embed_data:
                    # Discohook uses integer colors
                    embed.color = embed_data["color"]
                
                # WATCHER ENHANCEMENT: Auto-inject timestamp if missing
                if "timestamp" in embed_data:
                    # Parse ISO timestamp from Discohook
                    try:
                        embed.timestamp = datetime.fromisoformat(embed_data["timestamp"].replace("Z", "+00:00"))
                    except:
                        embed.timestamp = datetime.utcnow()
                else:
                    embed.timestamp = datetime.utcnow()
                
                # Author
                if "author" in embed_data:
                    author = embed_data["author"]
                    embed.set_author(
                        name=author.get("name", "")[:256],
                        url=author.get("url"),
                        icon_url=author.get("icon_url")
                    )
                
                # Footer (with WATCHER signature)
                if "footer" in embed_data:
                    footer = embed_data["footer"]
                    footer_text = footer.get("text", "")[:2048]
                    # WATCHER ENHANCEMENT: Add invisible zero-width signature
                    footer_text += "\u200b"  # Zero-width space marks as Watcher-issued
                    embed.set_footer(
                        text=footer_text,
                        icon_url=footer.get("icon_url")
                    )
                else:
                    # Add default Watcher footer if none provided
                    embed.set_footer(text="NIMBROR WATCHER v6.5\u200b")
                
                # Thumbnail
                if "thumbnail" in embed_data and "url" in embed_data["thumbnail"]:
                    embed.set_thumbnail(url=embed_data["thumbnail"]["url"])
                
                # Image
                if "image" in embed_data and "url" in embed_data["image"]:
                    embed.set_image(url=embed_data["image"]["url"])
                
                # Fields
                if "fields" in embed_data:
                    for field in embed_data["fields"][:25]:  # Discord max 25 fields
                        embed.add_field(
                            name=field.get("name", "")[:256],
                            value=field.get("value", "")[:1024],
                            inline=field.get("inline", False)
                        )
                
                discord_embeds.append(embed)
                
            except Exception as e:
                print(f"⚠️ Embed conversion error: {e}")
                continue
        
        # Build buttons/components if present
        view = None
        if "components" in parsed:
            try:
                view = discord.ui.View(timeout=None)
                for component_row in parsed["components"][:5]:  # Discord max 5 action rows
                    if component_row.get("type") == 1:  # Action row
                        for component in component_row.get("components", [])[:5]:  # Max 5 buttons per row
                            if component.get("type") == 2:  # Button
                                style_map = {1: discord.ButtonStyle.primary, 2: discord.ButtonStyle.secondary, 3: discord.ButtonStyle.success, 4: discord.ButtonStyle.danger, 5: discord.ButtonStyle.link}
                                style = style_map.get(component.get("style", 2), discord.ButtonStyle.secondary)
                                
                                # Link button
                                if style == discord.ButtonStyle.link and "url" in component:
                                    button = discord.ui.Button(
                                        label=component.get("label", "Link")[:80],
                                        url=component["url"],
                                        emoji=component.get("emoji")
                                    )
                                    view.add_item(button)
            except Exception as e:
                print(f"⚠️ Component parsing error: {e}")
                view = None
        
        # Send the announcement with WATCHER SAFETY
        try:
            # RATE LIMIT SAFETY: Default suppress mentions unless explicitly allowed
            allowed_mentions = discord.AllowedMentions.none() if silent else discord.AllowedMentions.all()
            
            sent_message = await channel.send(
                content=content[:2000] if content else None,
                embeds=discord_embeds if discord_embeds else None,
                view=view,
                allowed_mentions=allowed_mentions
            )
            
            # Pin if requested
            if pin:
                try:
                    await sent_message.pin()
                except Exception as e:
                    print(f"⚠️ Pin failed: {e}")
            
            # Success response
            success_embed = discord.Embed(
                title="✅ Announcement Sent",
                color=EMBED_COLORS["success"],
                timestamp=datetime.utcnow()
            )
            success_embed.add_field(name="Channel", value=channel.mention, inline=True)
            success_embed.add_field(name="Message ID", value=f"`{sent_message.id}`", inline=True)
            success_embed.add_field(name="Embeds", value=str(len(discord_embeds)), inline=True)
            if pin:
                success_embed.add_field(name="Pinned", value="✅ Yes", inline=True)
            success_embed.set_footer(text="NIMBROR WATCHER v6.5 • ANNOUNCEMENT SYSTEM")
            
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send(
                embed=create_embed("❌ Permission Denied", "Bot lacks permission to send messages in that channel.", color=EMBED_COLORS["error"]),
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                embed=create_embed("❌ Send Failed", f"Error: {str(e)[:200]}", color=EMBED_COLORS["error"]),
                ephemeral=True
            )
    
    except Exception as e:
        await log_error(f"announce command error: {traceback.format_exc()}")
        try:
            await interaction.followup.send(
                embed=create_embed("❌ Command Failed", "An unexpected error occurred.", color=EMBED_COLORS["error"]),
                ephemeral=True
            )
        except:
            pass


# --- EVENTS ---
@bot.event
async def on_ready():
    """Bot connected and ready."""
    global UPTIME_MESSAGE_ID, UPTIME_CHANNEL_ID, COMMANDS_SYNCED, BOT_READY
    
    if not bot.user:
        return
    
    print(f"✅ Bot ready: {bot.user.name} ({bot.user.id})")
    print(f"📊 Serving {len(bot.guilds)} guild(s)")
    
    # Start HTTP health check server (first, to unblock Koyeb health checks)
    if HTTP_SERVER is None:
        try:
            await start_http_server()
        except Exception as e:
            print(f"⚠️ Failed to start HTTP server: {e}")

    # Register NAS persistent view
    try:
        bot.add_view(NASControlPanel())
        print("✅ NAS Control Panel view registered (persistent)")
    except Exception as e:
        print(f"⚠️ Failed to register NAS view: {e}")
        await log_error(f"NAS view registration: {e}")

    # Ensure app commands are synced (once per session)
    if not COMMANDS_SYNCED:
        await sync_app_commands()
    
    # If still not synced, log hard error
    if not COMMANDS_SYNCED:
        await log_error("command_sync_failed: COMMANDS_SYNCED still False after on_ready")

    # Log registered slash commands for visibility
    try:
        commands = bot.tree.get_commands()
        print(f"Registered slash commands: {len(commands)}")
        for c in commands:
            print(c.name)
    except Exception as e:
        print(f"⚠️ Unable to list commands: {e}")

    print(f"Logged in as {bot.user}")
    
    # START ALL BACKGROUND TASKS (only called after successful login)
    try:
        if not bot.daily_quest_loop.is_running():
            bot.daily_quest_loop.start()
            print("✅ daily_quest_loop started")
        if not bot.quest_timeout_check.is_running():
            bot.quest_timeout_check.start()
            print("✅ quest_timeout_check started")
        if not bot.dynamic_social_credit_events.is_running():
            bot.dynamic_social_credit_events.start()
            print("✅ dynamic_social_credit_events started")
        if not bot.trial_timeout_check.is_running():
            bot.trial_timeout_check.start()
            print("✅ trial_timeout_check started")
        if not bot.corruption_monitor.is_running():
            bot.corruption_monitor.start()
            print("✅ corruption_monitor started")
        if not bot.ai_queue_processor.is_running():
            bot.ai_queue_processor.start()
            print("✅ ai_queue_processor started")
        # Start Koyeb auto-redeploy if credentials are configured
        if KOYEB_APP_ID and KOYEB_API_TOKEN:
            if not bot.koyeb_auto_redeploy.is_running():
                bot.koyeb_auto_redeploy.start()
                print("✅ koyeb_auto_redeploy started (15min interval)")
    except Exception as e:
        print(f"⚠️ Failed to start background tasks: {e}")
        await log_error(f"on_ready task startup: {traceback.format_exc()}")
    
    # Mark bot as ready for other systems
    BOT_READY = True
    print(f"🟢 BOT_READY = True (all background tasks started)")
    
    # Send startup announcement to announce channel only; never broadcast
    # If channel is missing or invalid, silently skip (no fallbacks)
    if not ANNOUNCE_CHANNEL_ID:
        return
    try:
        channel = await safe_get_channel(ANNOUNCE_CHANNEL_ID)
        if not channel:
            return
        embed = discord.Embed(
            title="🤖 Bot Started",
            description=f"**{bot.user.name}** is now online",
            color=0x00FF00,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Guilds", value=str(len(bot.guilds)), inline=True)
        embed.add_field(name="Status", value="Ready", inline=True)
        embed.set_footer(text=f"ID: {bot.user.id}")
        await channel.send(embed=embed)
    except Exception as e:
        print(f"❌ Failed to send startup announcement: {e}")

@bot.event
async def on_disconnect():
    """Bot disconnected. Track reconnect count and update uptime embed."""
    global RECONNECT_COUNT, UPTIME_MESSAGE_ID, UPTIME_CHANNEL_ID
    
    RECONNECT_COUNT += 1
    print(f"⚠️ Bot disconnected (Reconnect #{RECONNECT_COUNT})")
    
    # Try to update uptime embed on disconnect
    if UPTIME_MESSAGE_ID and UPTIME_CHANNEL_ID:
        try:
            channel = bot.get_channel(UPTIME_CHANNEL_ID)
            if channel:
                msg = await channel.fetch_message(UPTIME_MESSAGE_ID)
                uptime_embed = create_uptime_embed()
                await msg.edit(embed=uptime_embed)
        except Exception as e:
            print(f"⚠️ Could not update uptime embed: {e}")

@bot.event
async def on_member_join(member):
    """Initialize new member interview on join."""
    if member.bot:
        return
    try:
        bot.db.setdefault("interviews", {})[str(member.id)] = {
            "index": 0,
            "score": 0,
            "questions": INTERVIEW_QUESTIONS
        }
        save_data(bot.db)
        goals = (
            "Interview goals:\n"
            "• Answer directly and respectfully (1-3 sentences).\n"
            "• Stay on-topic; mention NSC when asked.\n"
            "• No jokes, hostility, or evasions.\n"
            "• Honesty over flattery; be concise."
        )
        await safe_send_dm(
            member,
            embed=create_embed(
                "👁️ SCREENING",
                f"{goals}\n\nQ1/10: {INTERVIEW_QUESTIONS[0]}"
            )
        )
    except Exception as e:
        print(f"⚠️ on_member_join error: {e}")

@bot.event
async def on_reaction_add(reaction, user):
    """Track trial votes when users react to trial messages."""
    if user.bot:
        return
    
    try:
        # Find trial by message ID (only one trial per message)
        for trial_id, trial_data in bot.db.get("trials", {}).items():
            if trial_data.get("message_id") == reaction.message.id and not trial_data.get("closed"):
                uid = str(user.id)
                
                # Register vote - prevent vote duplication with set operations
                if reaction.emoji == "🅰️":
                    if uid not in trial_data["votes_a"]:
                        trial_data["votes_a"].append(uid)
                    # Remove from opposite vote if user changed choice
                    if uid in trial_data["votes_b"]:
                        trial_data["votes_b"].remove(uid)
                
                elif reaction.emoji == "🅱️":
                    if uid not in trial_data["votes_b"]:
                        trial_data["votes_b"].append(uid)
                    # Remove from opposite vote if user changed choice
                    if uid in trial_data["votes_a"]:
                        trial_data["votes_a"].remove(uid)
                
                save_data(bot.db)
                return  # Exit after handling (prevent duplicate handling)
    except Exception as e:
        print(f"⚠️ on_reaction_add error: {e}")

@bot.event
async def on_reaction_remove(reaction, user):
    """Handle vote removal when users remove their reaction."""
    if user.bot:
        return
    
    try:
        # Find trial by message ID
        for trial_id, trial_data in bot.db.get("trials", {}).items():
            if trial_data.get("message_id") == reaction.message.id and not trial_data.get("closed"):
                uid = str(user.id)
                
                # Remove vote based on emoji
                if reaction.emoji == "🅰️" and uid in trial_data["votes_a"]:
                    trial_data["votes_a"].remove(uid)
                elif reaction.emoji == "🅱️" and uid in trial_data["votes_b"]:
                    trial_data["votes_b"].remove(uid)
                
                save_data(bot.db)
                return  # Exit after handling
    except Exception as e:
        print(f"⚠️ on_reaction_remove error: {e}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    uid = str(message.author.id)
    
    # === AD CAMPAIGN PING RESPONSE ===
    if bot.active_ad_task and not bot.active_ad_task.done():
        if bot.user in message.mentions:
            # Respond with disclosure and emojis
            disclosure = "I WAS PAID BY GOOGLE LLC TO SAY THIS"
            emojis = "🔍📧☁️📱🎬🗺️💳🎤🖼️📰🎮📊🔐🌐🔔🎯📍🔊💬🌟⌚🏠📡🛒🌍🎨📚🔬🎵🚗🏥🌱🔮🤖🏪📞🎪📋📈🖊️🗂️🔗🎒🎬🌐📊🔍📱⚡🎮💾🧠🌈🎓"
            random_emojis = "".join(random.choices(emojis, k=25))
            try:
                await message.channel.send(f"{message.author.mention}: **{disclosure}**\n{random_emojis}")
            except Exception as e:
                print(f"⚠️ Ad ping response error: {e}")
    
    # === GOOGLE QUESTION MARK SPAM ===
    if "?" in message.content:
        try:
            for i in range(4):
                await message.channel.send("JUST ASK GOOGLE " * 5)
                await asyncio.sleep(0.5)
        except Exception as e:
            print(f"⚠️ Google spam error: {e}")
    
    # Track activity
    bot.db.setdefault("last_message_time", {})[uid] = int(time.time())

    try:
        # --- Task Completion via Reply ---
        if message.reference and message.reference.message_id:
            ref_id = message.reference.message_id
            for task_id, task_data in list(bot.db.get("tasks", {}).items()):
                if task_data.get("completed"):
                    continue
                if task_data.get("message_id") != ref_id:
                    continue
                if task_data.get("user_id") != uid:
                    continue
                # Mark complete and reward
                task_data["completed"] = True
                save_data(bot.db)
                reward = int(task_data.get("reward", 5))
                await update_user_credit(uid, reward, "task_complete")
                credit_now = await get_user_credit(uid)
                ack = create_embed(
                    "✅ Task Completed",
                    f"Reward applied: `+{reward}` social credit\nCurrent credit: `{credit_now}`",
                    color=EMBED_COLORS["success"]
                )
                await message.channel.send(reference=message, embed=ack, allowed_mentions=discord.AllowedMentions.none())
                break

        # --- Interview ---
        if isinstance(message.channel, discord.DMChannel) and uid in bot.db.get("interviews", {}):
            state = bot.db["interviews"].get(uid, {"index": 0, "score": 0, "questions": INTERVIEW_QUESTIONS})
            questions = state.get("questions", INTERVIEW_QUESTIONS)
            idx = state.get("index", 0)
            total_questions = len(questions)

            # Score current answer and track answers
            answered = False
            if idx < total_questions:
                current_q = questions[idx]
                points = await score_interview_answer(current_q, message.content)
                state["score"] = state.get("score", 0) + points
                state.setdefault("answers", []).append(message.content)
                add_memory(uid, "interaction", f"Interview Q{idx+1} answered ({points}/1)")
                state["index"] = idx + 1
                answered = True
                
                # Log answer to interview logs channel
                await log_interview_answer(
                    user_id=int(uid),
                    user_mention=message.author.mention,
                    question_num=idx + 1,
                    total_questions=total_questions,
                    question_text=current_q,
                    answer_text=message.content,
                    score=points
                )

            idx = state["index"]
            score_total = state.get("score", 0)

            # If interview complete, evaluate outcome
            if idx >= total_questions:
                bot.db["interviews"].pop(uid, None)
                save_data(bot.db)

                outcome_embed = None
                logging_failed = False
                session_id = f"interview_{uid}_{int(time.time())}"
                
                # Threshold logic: <=4 fail, 5-9 requires human, >=7 pass, 10 perfect
                if score_total <= 4:
                    # === DISCORD LOGGING FIRST (GUARANTEED) ===
                    update_social_credit(uid, -5)
                    outcome_embed = create_embed(
                        "❌ ACCESS DENIED",
                        f"Score: {score_total}/10. You failed screening.",
                        color=EMBED_COLORS["error"]
                    )
                    try:
                        await message.author.send(embed=outcome_embed, view=InterviewFailView(message.author.id))
                    except Exception as e:
                        await log_error(f"interview fail dm [user={uid}, session={session_id}]: {str(e)}")
                    
                    # Log final interview summary to Discord
                    await log_interview_complete(
                        user_id=int(uid),
                        user_mention=message.author.mention,
                        score_total=score_total,
                        total_questions=total_questions,
                        passed=False,
                        answers_list=state.get("answers", []),
                        questions_list=questions,
                        forced=state.get("forced", False),
                        triggered_by=state.get("triggered_by")
                    )
                    
                    # Send AI analysis to Discord logs
                    await send_interview_ai_summary(
                        user_id=int(uid),
                        user_mention=message.author.mention,
                        score_total=score_total,
                        total_questions=total_questions,
                        answers_list=state.get("answers", []),
                        questions_list=questions,
                        passed=False
                    )
                    
                    # === SUPABASE WRITES (OPTIONAL - NO ERROR CRASH) ===
                    try:
                        # Log interview failure to INTERVIEW_CHANNEL
                        if INTERVIEW_CHANNEL_ID:
                            try:
                                ch = bot.get_channel(INTERVIEW_CHANNEL_ID)
                                if ch:
                                    fail_embed = discord.Embed(
                                        title="🔴 INTERVIEW FAILED",
                                        color=0xff0000,
                                        timestamp=datetime.now()
                                    )
                                    fail_embed.add_field(name="User ID", value=f"`{uid}`", inline=True)
                                    fail_embed.add_field(name="Score", value=f"`{score_total}/10`", inline=True)
                                    fail_embed.add_field(name="User", value=f"{message.author.mention}", inline=False)
                                    fail_embed.set_footer(text="NIMBROR WATCHER v6.5 • INTERVIEW FAILED")
                                    await ch.send(f"<@765028951541940225>", embed=fail_embed)
                            except Exception as e:
                                logging_failed = True
                                await log_error(f"interview fail channel log [user={uid}, session={session_id}]: {str(e)}")
                    except Exception as e:
                        logging_failed = True
                        await log_error(f"interview fail supabase [user={uid}, session={session_id}]: {str(e)}")
                    
                    # Notify user if logging partially failed
                    if logging_failed:
                        try:
                            await message.author.send(embed=create_embed(
                                "⚠️ Logging Alert",
                                "Interview recorded but some logs may be incomplete.",
                                color=EMBED_COLORS["warning"]
                            ))
                        except:
                            pass
                    return

                if score_total <= 6:
                    # === SCORE 5-9: HUMAN OVERSIGHT REQUIRED ===
                    update_social_credit(uid, 0)
                    answers = state.get("answers", [])
                    
                    # === DISCORD LOGGING FIRST (GUARANTEED) ===
                    await log_interview_complete(
                        user_id=int(uid),
                        user_mention=message.author.mention,
                        score_total=score_total,
                        total_questions=total_questions,
                        passed=False,
                        answers_list=answers,
                        questions_list=questions,
                        forced=state.get("forced", False),
                        triggered_by=state.get("triggered_by")
                    )
                    
                    # Send AI analysis to Discord logs
                    await send_interview_ai_summary(
                        user_id=int(uid),
                        user_mention=message.author.mention,
                        score_total=score_total,
                        total_questions=total_questions,
                        answers_list=answers,
                        questions_list=questions,
                        passed=False
                    )
                    
                    # === SUPABASE WRITES (OPTIONAL - NO ERROR CRASH) ===
                    try:
                        # Create review ticket in Supabase with BIGINT timestamp
                        ticket_data = {
                            "user_id": uid,
                            "session_id": session_id,
                            "answers": answers,
                            "score": score_total,
                            "status": "OPEN",
                            "created_at": int(time.time())  # BIGINT timestamp fix
                        }
                        response = supabase.table("review_tickets").insert(ticket_data).execute()
                        ensure_ok(response, "review_tickets insert")
                        ticket_created = True
                    except Exception as e:
                        logging_failed = True
                        ticket_created = False
                        await log_error(f"create_review_ticket [user={uid}, session={session_id}]: {str(e)}")
                    
                    try:
                        # Update interview session status to UNDER_REVIEW with BIGINT timestamp
                        response = supabase.table("interview_sessions").update({
                            "status": "UNDER_REVIEW",
                            "updated_at": int(time.time())  # BIGINT timestamp fix
                        }).eq("user_id", uid).eq("id", session_id).execute()
                        ensure_ok(response, "interview_sessions update")
                    except Exception as e:
                        logging_failed = True
                        await log_error(f"update_interview_session_status [user={uid}, session={session_id}]: {str(e)}")
                    
                    try:
                        # Post to INTERVIEW_CHANNEL for staff oversight with human oversight button
                        if INTERVIEW_CHANNEL_ID and ticket_created:
                            ch = bot.get_channel(INTERVIEW_CHANNEL_ID)
                            if ch:
                                # Build answers summary
                                qa_summary = ""
                                for i, ans in enumerate(answers[:10], 1):
                                    qa_summary += f"**Q{i}:** {ans[:80]}\n"
                                
                                review_embed = discord.Embed(
                                    title="⚠️ INTERVIEW REQUIRES HUMAN REVIEW",
                                    color=0xff9900,
                                    timestamp=datetime.now()
                                )
                                review_embed.add_field(name="User ID", value=f"`{uid}`", inline=True)
                                review_embed.add_field(name="Session ID", value=f"`{session_id}`", inline=True)
                                review_embed.add_field(name="Score", value=f"`{score_total}/10`", inline=False)
                                review_embed.add_field(name="Answers Preview", value=qa_summary[:1024], inline=False)
                                review_embed.set_footer(text="NIMBROR WATCHER v6.5 • HUMAN OVERSIGHT REQUIRED")
                                
                                # Send review embed with untrusted mode button
                                await ch.send(f"<@765028951541940225>", embed=review_embed, view=UntrustedUserView(message.author.id))
                    except Exception as e:
                        logging_failed = True
                        await log_error(f"interview review channel log [user={uid}, session={session_id}]: {str(e)}")
                    
                    # Outcome message to user
                    outcome_embed = create_embed(
                        "⚠️ HUMAN REVIEW REQUIRED",
                        f"Score: {score_total}/10. Your application is under staff review. Please wait for their decision.",
                        color=EMBED_COLORS["warning"]
                    )
                    try:
                        await message.author.send(embed=outcome_embed)
                    except Exception as e:
                        await log_error(f"interview review dm [user={uid}, session={session_id}]: {str(e)}")
                    
                    # Notify user if logging partially failed
                    if logging_failed:
                        try:
                            await message.author.send(embed=create_embed(
                                "⚠️ Logging Alert",
                                "Interview recorded but some logs may be incomplete.",
                                color=EMBED_COLORS["warning"]
                            ))
                        except:
                            pass
                    return

                # === PASSED (SCORE >= 7) ===
                credit_bonus = 10 if score_total == total_questions else 5
                update_social_credit(uid, credit_bonus)

                # Grant verified role if configured
                if bot.guilds and VERIFIED_ROLE_ID:
                    try:
                        guild = bot.guilds[0]
                        member = guild.get_member(message.author.id)
                        role = guild.get_role(VERIFIED_ROLE_ID)
                        if member and role:
                            await member.add_roles(role)
                    except Exception as e:
                        await log_error(f"interview role add [user={uid}, session={session_id}]: {str(e)}")

                # === DISCORD LOGGING FIRST (GUARANTEED) ===
                await log_interview_complete(
                    user_id=int(uid),
                    user_mention=message.author.mention,
                    score_total=score_total,
                    total_questions=total_questions,
                    passed=True,
                    answers_list=state.get("answers", []),
                    questions_list=questions,
                    forced=state.get("forced", False),
                    triggered_by=state.get("triggered_by")
                )
                
                # Send AI analysis to Discord logs
                await send_interview_ai_summary(
                    user_id=int(uid),
                    user_mention=message.author.mention,
                    score_total=score_total,
                    total_questions=total_questions,
                    answers_list=state.get("answers", []),
                    questions_list=questions,
                    passed=True
                )

                # === SUPABASE WRITES (OPTIONAL - NO ERROR CRASH) ===
                try:
                    # Update interview session status to APPROVED with BIGINT timestamp
                    response = supabase.table("interview_sessions").update({
                        "status": "APPROVED",
                        "updated_at": int(time.time())  # BIGINT timestamp fix
                    }).eq("user_id", uid).eq("id", session_id).execute()
                    ensure_ok(response, "interview_sessions update")
                except Exception as e:
                    logging_failed = True
                    await log_error(f"update_interview_session_status [user={uid}, session={session_id}, step=approve]: {str(e)}")
                
                outcome_text = "Perfect pass. Welcome to Nimbror." if score_total == total_questions else "Pass. Proceed quietly."
                outcome_embed = create_embed(
                    "✅ ACCESS GRANTED",
                    f"Score: {score_total}/10. {outcome_text}",
                    color=EMBED_COLORS["success"]
                )
                try:
                    await message.author.send(embed=outcome_embed)
                except Exception as e:
                    await log_error(f"interview pass dm [user={uid}, session={session_id}]: {str(e)}")
                
                # Notify user if logging partially failed
                if logging_failed:
                    try:
                        await message.author.send(embed=create_embed(
                            "⚠️ Logging Alert",
                            "Interview recorded but some logs may be incomplete.",
                            color=EMBED_COLORS["warning"]
                        ))
                    except:
                        pass
                return

            # Continue to next question (only if we just scored one)
            if answered:
                bot.db["interviews"][uid] = state
                save_data(bot.db)
                next_q = questions[idx]
                await message.author.send(embed=create_embed("👁️ SCREENING", f"Q{idx+1}/{total_questions}: {next_q}"))
            return

        # --- Tickets / DM AI ---
        if isinstance(message.channel, discord.DMChannel) and uid in bot.db.get("tickets", {}):
            ticket = bot.db["tickets"][uid]
            
            # Forward to staff with note button
            if STAFF_CHANNEL_ID:
                try:
                    staff_chan = await safe_get_channel(STAFF_CHANNEL_ID)
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
                except Exception as e:
                    print(f"⚠️ Staff channel send error: {e}")
            
            # AI Response - QUEUE-BASED
            user_id = message.author.id
            
            # Check adaptive cooldown
            is_ready, remaining, level = check_adaptive_cooldown(user_id)
            
            if not is_ready:
                embed = create_embed("⏳ Please Wait", f"AI cooldown active: {remaining}s remaining", color=EMBED_COLORS["warning"])
                await message.channel.send(embed=embed)
                return
            
            # Build prompt with custom instructions
            custom_instructions = bot.db.get("custom_instructions", {})
            custom_context = ""
            for user_id_key, instruction in custom_instructions.items():
                if user_id_key != uid:  # Don't include their own custom instruction
                    custom_context += f"{instruction} "
            
            prompt = (
                f"{LORE_CONTEXT}\n"
                f"AI Memory for this user: {bot.db.get('memory', {}).get(uid, {})}\n"
                f"Custom instructions: {custom_context}\n"
                f"User says: {message.content[:500]}"
            )
            
            # QUEUE-BASED AI: Queue the request
            success, status_msg = await queue_ai_request(
                user_id=user_id,
                channel_id=message.channel.id,
                prompt=prompt,
                context="ticket"
            )
            
            if success:
                async with message.channel.typing():
                    await asyncio.sleep(0.5)  # Brief typing indicator
            else:
                embed = create_embed("⚠️ Request Status", status_msg, color=EMBED_COLORS["warning"])
                await message.channel.send(embed=embed)
            
            # Store in memory and track engagement
            add_memory(uid, "interaction", f"Ticket message: {message.content[:100]}")
            update_social_credit(uid, len(message.content) // 50)
            return

        # --- Staff reply (>USERID message) ---
        if STAFF_CHANNEL_ID and message.channel.id == STAFF_CHANNEL_ID and message.content.startswith(">"):
            parts = message.content[1:].split(" ", 1)  # Remove > and split
            if len(parts) < 2 or not parts[0].isdigit():
                await message.reply("❌ Format: >USERID message", delete_after=10)
                return
            try:
                user_id = int(parts[0])
                target = await bot.fetch_user(user_id)
                await target.send(embed=create_embed("📡 HIGH COMMAND", parts[1][:1000], color=0xff0000))
                await message.add_reaction("🛰️")
            except (ValueError, discord.NotFound):
                await message.reply("❌ Invalid user ID", delete_after=10)
            except discord.Forbidden:
                await message.reply("❌ Cannot DM user", delete_after=10)
            return

        # --- AI on mention ---
        if bot.user and bot.user.mentioned_in(message):
            # === SPAM/AD SAFETY: Do NOT trigger AI for bot's own spam/ad campaigns ===
            if bot.active_spam_task and not bot.active_spam_task.done():
                return  # Skip AI during active spam
            if bot.active_ad_task and not bot.active_ad_task.done():
                return  # Skip AI during active ads
            
            cleanup_expired_cooldowns()  # Periodic cleanup
            
            user_id = message.author.id
            uid_mention = str(user_id)
            
            # QUEUE-BASED AI: Check adaptive cooldown
            is_ready, remaining, level = check_adaptive_cooldown(user_id)
            
            if not is_ready:
                # Show cooldown with level indicator
                if level >= 3:
                    embed = create_embed("⏸️ AI PAUSED", f"Temporary pause due to rate limiting. Wait: {remaining}s", color=EMBED_COLORS["error"])
                else:
                    # Create fancy progress bar
                    bar_length = 10
                    cooldown_duration = ADAPTIVE_COOLDOWN_TIERS[level]
                    elapsed = cooldown_duration - remaining
                    filled = int(bar_length * elapsed / cooldown_duration) if cooldown_duration > 0 else 0
                    bar = "■" * filled + "□" * (bar_length - filled)
                    
                    embed = create_embed("⏳ COOLDOWN", f"`[{bar}]` {remaining}s remaining (Level {level})")
                
                await message.reply(embed=embed, delete_after=5)
                escalate_cooldown(user_id, "attempt_while_cooldown")
                return
            
            try:
                # Build prompt with custom instructions
                custom_instructions = bot.db.get("custom_instructions", {})
                custom_context = ""
                for user_id_key, instruction in custom_instructions.items():
                    if user_id_key != uid_mention:  # Don't include their own custom instruction
                        custom_context += f"{instruction} "
                
                prompt = f"Custom instructions: {custom_context}\nUser says: {message.content[:200]}"
                
                # If queue is busy, drop a placeholder and edit later
                placeholder_id = None
                if (AI_REQUEST_QUEUE and not AI_REQUEST_QUEUE.empty()) or AI_QUEUE_PROCESSOR_RUNNING:
                    try:
                        placeholder = await message.reply(
                            "Sorry, please wait a moment, I will edit this message when I'm ready to answer",
                            allowed_mentions=discord.AllowedMentions.none()
                        )
                        placeholder_id = placeholder.id
                    except Exception:
                        pass
            
                # QUEUE-BASED AI: Queue the request instead of executing immediately
                success, status_msg = await queue_ai_request(
                    user_id=user_id,
                    channel_id=message.channel.id,
                    prompt=prompt,
                    context="mention",
                    placeholder_message_id=placeholder_id
                )
            
                if success:
                    # Show queued status
                    async with message.channel.typing():
                        await asyncio.sleep(0.5)  # Brief typing indicator
                else:
                    # Show error
                    await message.reply(status_msg, delete_after=5)
                
                # Update memory and credit (with safety)
                try:
                    add_memory(uid_mention, "interaction", f"Mention: {message.content[:100]}")
                    update_social_credit(uid_mention, 1)
                except Exception as mem_err:
                    print(f"⚠️ Memory/credit error: {mem_err}")
                    
            except Exception as ping_error:
                await log_error(f"Ping reply failed: {type(ping_error).__name__}: {str(ping_error)}")
                try:
                    await message.reply("👁️ *[Processing...]*")
                except:
                    pass
            return

    except Exception as e:
        error_msg = f"on_message error: {type(e).__name__}: {str(e)}"
        print(f"❌ {error_msg}")
        # Check for Discord rate limit (HTTP 429)
        if isinstance(e, discord.HTTPException) and e.status == 429:
            set_discord_rate_limited(True)
        traceback.print_exc()
        await log_error(error_msg)

# --- RUN ---
print("🚀 Starting Discord bot...")

# Add startup delay to avoid hitting rate limits on rapid restarts
import time
startup_delay = 5
print(f"⏳ Waiting {startup_delay}s before connecting (rate limit safety)...")
time.sleep(startup_delay)

try:
    bot.run(TOKEN, reconnect=True)
except discord.HTTPException as e:
    if e.status == 429:
        print(f"❌ Discord rate limit (HTTP 429): {e}")
        print("⏰ You've exceeded Discord's global rate limits.")
        print("   Wait 10-30 minutes before restarting.")
        print("💤 Bot entering idle sleep (will not retry - process will remain running)")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print("\n🛑 Shutdown via keyboard interrupt")
    else:
        print(f"❌ Discord HTTP error: {e}")
        raise
except discord.LoginFailure as e:
    print(f"❌ Discord login failed (invalid token or rate limited): {e}")
    print("💤 Bot entering idle sleep (will not retry login - process will remain running)")
    print("   If this is a rate limit, wait 8-24 hours before restarting.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n🛑 Shutdown via keyboard interrupt")
except KeyboardInterrupt:
    print("\n🛑 Shutdown")
except Exception as e:
    print(f"❌ Critical error on startup: {type(e).__name__}: {e}")
    traceback.print_exc()
    print("💤 Bot entering idle sleep (will not retry - process will remain running)")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n🛑 Shutdown via keyboard interrupt")
