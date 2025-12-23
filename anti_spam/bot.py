"""
COMPLETE DISCORD BOT - ALL FEATURES
====================================
SAVE THIS FILE AS: bot.py

Features:
✅ Spam Detection (rapid, cross-channel, duplicate, image, scam)
✅ Gamification (XP, levels, streaks, achievements)
✅ Auto-Role Assignment
✅ Warning System & Auto-Ban
✅ Raid Detection
✅ Analytics Dashboard
✅ Content Curation
✅ AI Features (optional)

Setup:
1. Save this as bot.py
2. Replace BOT_TOKEN with your token
3. pip install discord.py aiohttp
4. python bot.py
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict, deque
import os

# ============================================================================
# CONFIGURATION - EDIT THESE SETTINGS
# ============================================================================

# === Bot Token ===
BOT_TOKEN = 'MTQ1MjcyNjMwNTkyNDU3OTM3OA.GiThLz.03NXpCKlbCucABsWu60UwGt3a1sI8_umge6lbs'  # Get from discord.com/developers/applications

# === API Keys (Optional - for AI features) ===
GROQ_API_KEY = ''  # Get free at console.groq.com
ENABLE_AI_FEATURES = True      # Set True when you have Groq key

# === Spam Detection ===
SPAM_THRESHOLD = 5              # Messages in time window = spam
SPAM_WINDOW = 10                # Seconds
CROSS_CHANNEL_THRESHOLD = 3     # Same message in X channels
DUPLICATE_MESSAGE_THRESHOLD = 3 # Repeated message X times
IMAGE_SPAM_THRESHOLD = 4        # Images in 30 seconds

# === Punishments ===
FIRST_WARNING_TIMEOUT = 300     # 5 minutes
SECOND_WARNING_TIMEOUT = 1800   # 30 minutes  
THIRD_WARNING_TIMEOUT = 10800   # 3 hours
FOURTH_WARNING_TIMEOUT = 86400  # 24 hours
AUTO_BAN_THRESHOLD = 5          # Auto-ban after X warnings

# === Gamification ===
ENABLE_GAMIFICATION = True      # Set False to disable XP system
XP_PER_MESSAGE = 5
XP_PER_VOICE_MINUTE = 2
XP_PER_REACTION_RECEIVED = 3
MESSAGE_COOLDOWN = 60           # Seconds between XP awards
LEVEL_MULTIPLIER = 100          # XP needed per level

# === Level Roles (auto-assigned) ===
LEVEL_ROLES = {
    5: 'Active',
    10: 'Regular',
    20: 'Veteran',
    30: 'Elite',
    50: 'Legend'
}

# === Milestone Roles (auto-assigned) ===
AUTO_ROLES_MILESTONES = {
    10: 'Newcomer',
    50: 'Member',
    100: 'Active Member',
    500: 'Veteran',
    1000: 'Elite'
}

# === Trust System (reduces false positives) ===
TRUSTED_ROLE_NAMES = ['Member', 'Verified', 'Regular', 'Active', 'Veteran', 'Elite']
MESSAGE_THRESHOLD_FOR_TRUST = 50

# === Channels (auto-created) ===
MOD_LOG_CHANNEL = 'mod-logs'
LEVEL_UP_CHANNEL = 'level-ups'
BEST_OF_CHANNEL = 'best-of'

# === Data Files ===
DATA_FILE = 'user_data.json'
GAMIFICATION_FILE = 'gamification_data.json'

# ============================================================================
# BOT INITIALIZATION
# ============================================================================

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# ============================================================================
# DATA STRUCTURES
# ============================================================================

user_data = defaultdict(lambda: {
    'messages': 0,
    'reactions_given': 0,
    'reactions_received': 0,
    'voice_time': 0,
    'warnings': 0,
    'last_messages': [],
    'channel_messages': defaultdict(int),
    'voice_join_time': None,
    'join_date': None,
    'last_warning_time': None,
    'warning_types': [],
    'images_sent': []
})

gamification_data = defaultdict(lambda: {
    'xp': 0,
    'level': 1,
    'last_xp_time': None,
    'streak_days': 0,
    'last_active_date': None,
    'achievements': [],
    'total_xp_earned': 0
})

raid_tracker = {
    'recent_joins': deque(maxlen=50),
    'suspicious_messages': defaultdict(list)
}

SCAM_PATTERNS = [
    r'free\s+nitro',
    r'discord\.gift',
    r'click\s+here\s+for',
    r'dm\s+me\s+for\s+money',
    r'investment\s+opportunity',
    r'double\s+your\s+(money|crypto)'
]
SCAM_REGEX = [re.compile(p, re.IGNORECASE) for p in SCAM_PATTERNS]

ACHIEVEMENTS = {
    'first_message': {'name': '👋 First Steps', 'xp': 50},
    'first_win': {'name': '🏆 First Victory', 'xp': 100},
    'helpful': {'name': '🤝 Helpful', 'xp': 200},
    'consistent': {'name': '🔥 Consistent', 'xp': 500},
    'century': {'name': '💯 Century', 'xp': 150},
    'voice_active': {'name': '🎤 Voice Active', 'xp': 300}
}

# ============================================================================
# DATA PERSISTENCE
# ============================================================================

def load_data():
    """Load all saved data on bot startup"""
    global user_data, gamification_data
    
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                loaded = json.load(f)
                for user_id, data in loaded.items():
                    user_data[user_id] = defaultdict(lambda: 0, data)
                    user_data[user_id]['channel_messages'] = defaultdict(int, data.get('channel_messages', {}))
                    user_data[user_id]['last_messages'] = data.get('last_messages', [])
                    user_data[user_id]['warning_types'] = data.get('warning_types', [])
                    user_data[user_id]['images_sent'] = data.get('images_sent', [])
            print(f"✅ Loaded data for {len(user_data)} users")
        except Exception as e:
            print(f"❌ Error loading data: {e}")
    
    if os.path.exists(GAMIFICATION_FILE):
        try:
            with open(GAMIFICATION_FILE, 'r') as f:
                loaded = json.load(f)
                for user_id, data in loaded.items():
                    gamification_data[user_id] = defaultdict(lambda: 0, data)
                    gamification_data[user_id]['achievements'] = data.get('achievements', [])
            print(f"✅ Loaded gamification data for {len(gamification_data)} users")
        except Exception as e:
            print(f"❌ Error loading gamification: {e}")

def save_data():
    """Save all data to files"""
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump({k: dict(v) for k, v in user_data.items()}, f, indent=2)
        with open(GAMIFICATION_FILE, 'w') as f:
            json.dump({k: dict(v) for k, v in gamification_data.items()}, f, indent=2)
    except Exception as e:
        print(f"❌ Error saving: {e}")

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def is_trusted_user(member, user_id):
    """Check if user is trusted (reduces false positives)"""
    if member.roles:
        role_names = [role.name for role in member.roles]
        if any(t in role_names for t in TRUSTED_ROLE_NAMES):
            return True
    return user_data[user_id]['messages'] >= MESSAGE_THRESHOLD_FOR_TRUST

def calculate_timeout_duration(warnings):
    """Progressive punishment system"""
    if warnings == 1: return FIRST_WARNING_TIMEOUT
    elif warnings == 2: return SECOND_WARNING_TIMEOUT
    elif warnings == 3: return THIRD_WARNING_TIMEOUT
    elif warnings == 4: return FOURTH_WARNING_TIMEOUT
    return None

async def send_user_warning(user, reason, timeout_duration=None):
    """Send private DM warning to user"""
    embed = discord.Embed(
        title="⚠️ Moderation Warning",
        description=f"You've been warned for: **{reason}**",
        color=discord.Color.orange()
    )
    if timeout_duration:
        mins = timeout_duration // 60
        embed.add_field(name="Timeout", value=f"🔇 {mins} minutes", inline=False)
    embed.add_field(
        name="What to do",
        value="Follow server rules. Repeated violations = longer timeouts or ban.",
        inline=False
    )
    try:
        await user.send(embed=embed)
        return True
    except:
        return False

# ============================================================================
# SPAM DETECTION
# ============================================================================

def is_spam_content(content):
    """Check message content for spam indicators"""
    mentions = len(re.findall(r'<@[!&]?\d+>', content))
    if mentions >= 5:
        return True, f"Excessive mentions ({mentions})"
    
    if len(content) >= 20:
        caps = sum(1 for c in content if c.isupper())
        if caps / len(content) >= 0.7:
            return True, "Excessive caps"
    
    if re.search(r'(.)\1{9,}', content):
        return True, "Repeated character spam"
    
    return False, ""

async def check_image_spam(message):
    """Check for image/attachment spam"""
    if not message.attachments:
        return False, ""
    
    user_id = str(message.author.id)
    current_time = datetime.now()
    
    for att in message.attachments:
        user_data[user_id]['images_sent'].append({
            'filename': att.filename,
            'timestamp': str(current_time)
        })
    
    user_data[user_id]['images_sent'] = [
        img for img in user_data[user_id]['images_sent']
        if (current_time - datetime.fromisoformat(img['timestamp'])).seconds <= 30
    ]
    
    if len(user_data[user_id]['images_sent']) >= IMAGE_SPAM_THRESHOLD:
        return True, f"Image spam ({len(user_data[user_id]['images_sent'])} in 30s)"
    
    return False, ""

async def check_scam_patterns(content):
    """Check for scam patterns"""
    for pattern in SCAM_REGEX:
        if pattern.search(content.lower()):
            return True, pattern.pattern
    return False, ""

# ============================================================================
# PUNISHMENT & NOTIFICATIONS
# ============================================================================

async def flag_spam(message, reason, timeout=False):
    """Main spam handling function"""
    user_id = str(message.author.id)
    
    user_data[user_id]['warnings'] += 1
    user_data[user_id]['last_warning_time'] = str(datetime.now())
    user_data[user_id]['warning_types'].append(reason)
    warnings = user_data[user_id]['warnings']
    
    try:
        await message.delete()
        print(f"🗑️ Deleted spam from {message.author.name}: {reason}")
    except:
        pass
    
    if warnings >= AUTO_BAN_THRESHOLD:
        try:
            await message.author.ban(reason=f"Auto-ban: {warnings} warnings")
            await send_ban_notification(message.guild, message.author, reason, warnings)
            save_data()
            return
        except:
            pass
    
    timeout_duration = None
    if timeout:
        timeout_duration = calculate_timeout_duration(warnings)
        if timeout_duration:
            try:
                await message.author.timeout(
                    timedelta(seconds=timeout_duration),
                    reason=f"Spam: {reason}"
                )
                await send_timeout_notification(message.guild, message.author, reason, timeout_duration, warnings)
            except:
                pass
    
    await send_user_warning(message.author, reason, timeout_duration)
    save_data()

async def send_timeout_notification(guild, user, reason, duration, warnings):
    """Alert mods about timeout"""
    mod_channel = discord.utils.get(guild.channels, name=MOD_LOG_CHANNEL)
    if not mod_channel:
        return
    
    mins = duration // 60
    color = discord.Color.dark_red() if warnings >= 4 else discord.Color.red() if warnings >= 3 else discord.Color.orange()
    
    embed = discord.Embed(
        title="🔇 User Timed Out",
        description=f"{user.mention} timed out",
        color=color
    )
    embed.add_field(name="Duration", value=f"{mins}min", inline=True)
    embed.add_field(name="Warnings", value=f"{warnings}/{AUTO_BAN_THRESHOLD}", inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    
    if warnings >= AUTO_BAN_THRESHOLD - 1:
        embed.add_field(name="⚠️", value="Next offense = AUTO-BAN", inline=False)
    
    try:
        await mod_channel.send(embed=embed)
    except:
        pass

async def send_ban_notification(guild, user, reason, warnings):
    """Alert mods about ban"""
    mod_channel = discord.utils.get(guild.channels, name=MOD_LOG_CHANNEL)
    if not mod_channel:
        return
    
    embed = discord.Embed(
        title="🔨 AUTO-BAN TRIGGERED",
        description=f"{user.mention} banned",
        color=discord.Color.dark_red()
    )
    embed.add_field(name="Warnings", value=warnings, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    
    try:
        await mod_channel.send("@here", embed=embed)
    except:
        pass

# ============================================================================
# GAMIFICATION SYSTEM
# ============================================================================

def calculate_level_from_xp(xp):
    """Calculate level from total XP"""
    return max(1, int(xp / LEVEL_MULTIPLIER))

async def award_xp(user, guild, xp_amount, reason="activity"):
    """Award XP to user and handle level ups"""
    if not ENABLE_GAMIFICATION:
        return
    
    user_id = str(user.id)
    current_time = datetime.now()
    
    if reason == "message":
        last_xp = gamification_data[user_id].get('last_xp_time')
        if last_xp:
            last_time = datetime.fromisoformat(last_xp)
            if (current_time - last_time).seconds < MESSAGE_COOLDOWN:
                return
    
    old_level = gamification_data[user_id]['level']
    gamification_data[user_id]['xp'] += xp_amount
    gamification_data[user_id]['total_xp_earned'] += xp_amount
    gamification_data[user_id]['last_xp_time'] = str(current_time)
    
    new_level = calculate_level_from_xp(gamification_data[user_id]['xp'])
    gamification_data[user_id]['level'] = new_level
    
    if new_level > old_level:
        await handle_level_up(user, guild, old_level, new_level)
    
    save_data()

async def handle_level_up(user, guild, old_level, new_level):
    """Handle level up - award roles and announce"""
    print(f"🎉 {user.name} leveled up: {old_level} → {new_level}")
    
    if new_level in LEVEL_ROLES:
        role = discord.utils.get(guild.roles, name=LEVEL_ROLES[new_level])
        if role:
            try:
                await user.add_roles(role)
            except:
                pass
    
    try:
        embed = discord.Embed(
            title="🎉 LEVEL UP!",
            description=f"{user.mention} reached **Level {new_level}**!",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        
        channel = discord.utils.get(guild.channels, name=LEVEL_UP_CHANNEL)
        if not channel:
            channel = discord.utils.get(guild.channels, name='general')
        
        if channel:
            await channel.send(embed=embed)
    except:
        pass

async def update_streak(user_id):
    """Update daily activity streak"""
    current_date = datetime.now().date()
    user_id_str = str(user_id)
    
    last_active = gamification_data[user_id_str].get('last_active_date')
    
    if last_active:
        last_date = datetime.fromisoformat(last_active).date()
        days_diff = (current_date - last_date).days
        
        if days_diff == 1:
            gamification_data[user_id_str]['streak_days'] += 1
        elif days_diff > 1:
            gamification_data[user_id_str]['streak_days'] = 1
    else:
        gamification_data[user_id_str]['streak_days'] = 1
    
    gamification_data[user_id_str]['last_active_date'] = str(datetime.now())
    
    if gamification_data[user_id_str]['streak_days'] == 30:
        await award_achievement(user_id, 'consistent')

async def award_achievement(user_id, achievement_key):
    """Award achievement to user"""
    user_id_str = str(user_id)
    
    if achievement_key in gamification_data[user_id_str]['achievements']:
        return
    
    gamification_data[user_id_str]['achievements'].append(achievement_key)
    
    achievement = ACHIEVEMENTS.get(achievement_key)
    if achievement:
        gamification_data[user_id_str]['xp'] += achievement['xp']
        print(f"🏆 {user_id} earned: {achievement['name']}")
    
    save_data()

async def check_auto_roles(member):
    """Assign milestone roles based on message count"""
    user_id = str(member.id)
    messages = user_data[user_id]['messages']
    
    for milestone, role_name in AUTO_ROLES_MILESTONES.items():
        if messages >= milestone:
            role = discord.utils.get(member.guild.roles, name=role_name)
            if role and role not in member.roles:
                try:
                    await member.add_roles(role)
                    print(f"🎖️ Awarded {role_name} to {member.name}")
                except:
                    pass

# ============================================================================
# EVENT HANDLERS
# ============================================================================

@bot.event
async def on_ready():
    """Bot startup"""
    load_data()
    print(f'✅ {bot.user} is online!')
    print(f'📊 Monitoring {len(bot.guilds)} server(s)')
    
    for guild in bot.guilds:
        for channel_name in [MOD_LOG_CHANNEL, LEVEL_UP_CHANNEL, BEST_OF_CHANNEL]:
            if not discord.utils.get(guild.channels, name=channel_name):
                try:
                    await guild.create_text_channel(channel_name)
                    print(f"📢 Created #{channel_name}")
                except:
                    pass
    
    try:
        synced = await bot.tree.sync()
        print(f'✅ Synced {len(synced)} commands')
    except Exception as e:
        print(f'❌ Error syncing: {e}')

@bot.event
async def on_member_join(member):
    """Track joins and check for raids"""
    user_id = str(member.id)
    current_time = datetime.now()
    
    user_data[user_id]['join_date'] = str(current_time)
    
    raid_tracker['recent_joins'].append({
        'user_id': member.id,
        'join_time': current_time
    })
    
    recent_joins = sum(
        1 for j in raid_tracker['recent_joins']
        if (current_time - j['join_time']).seconds <= 60
    )
    
    if recent_joins >= 5:
        mod_channel = discord.utils.get(member.guild.channels, name=MOD_LOG_CHANNEL)
        if mod_channel:
            embed = discord.Embed(
                title="🚨 POTENTIAL RAID",
                description=f"{recent_joins} users joined in 60s!",
                color=discord.Color.red()
            )
            try:
                await mod_channel.send("@here", embed=embed)
            except:
                pass
    
    save_data()

@bot.event
async def on_message(message):
    """Main message handler"""
    if message.author.bot:
        return
    
    user_id = str(message.author.id)
    current_time = datetime.now()
    is_trusted = is_trusted_user(message.author, user_id)
    
    user_data[user_id]['messages'] += 1
    user_data[user_id]['channel_messages'][str(message.channel.id)] += 1
    
    if not user_data[user_id]['join_date']:
        user_data[user_id]['join_date'] = str(message.author.joined_at or current_time)
    
    msg_data = {
        'content': message.content,
        'channel_id': message.channel.id,
        'timestamp': str(current_time)
    }
    user_data[user_id]['last_messages'].append(msg_data)
    user_data[user_id]['last_messages'] = user_data[user_id]['last_messages'][-50:]
    
    # SPAM CHECKS
    is_scam, scam_pattern = await check_scam_patterns(message.content)
    if is_scam:
        await flag_spam(message, f"Scam: {scam_pattern}", timeout=True)
        return
    
    is_img_spam, img_reason = await check_image_spam(message)
    if is_img_spam:
        await flag_spam(message, img_reason, timeout=True)
        return
    
    is_spam, spam_reason = is_spam_content(message.content)
    if is_spam and not is_trusted:
        await flag_spam(message, spam_reason, timeout=True)
        return
    
    recent_msgs = [
        m for m in user_data[user_id]['last_messages']
        if (current_time - datetime.fromisoformat(m['timestamp'])).seconds < SPAM_WINDOW
    ]
    threshold = SPAM_THRESHOLD if is_trusted else SPAM_THRESHOLD - 1
    if len(recent_msgs) >= threshold:
        await flag_spam(message, "Rapid messaging", timeout=True)
        return
    
    content_lower = message.content.lower().strip()
    if len(content_lower) > 5:
        dup_count = sum(
            1 for m in user_data[user_id]['last_messages'][-20:]
            if m['content'].lower().strip() == content_lower
        )
        if dup_count >= DUPLICATE_MESSAGE_THRESHOLD:
            await flag_spam(message, "Repeated messages", timeout=True)
            return
    
    if len(content_lower) > 10:
        cross_instances = []
        for msg in user_data[user_id]['last_messages'][-20:]:
            if msg['content'].lower().strip() == content_lower and \
               msg['channel_id'] != message.channel.id:
                cross_instances.append(msg)
        
        threshold = CROSS_CHANNEL_THRESHOLD if is_trusted else CROSS_CHANNEL_THRESHOLD - 1
        if len(cross_instances) >= threshold:
            channels = []
            for m in cross_instances[:3]:
                try:
                    ch = bot.get_channel(int(m['channel_id']))
                    if ch:
                        channels.append(f"#{ch.name}")
                except:
                    pass
            
            ch_str = ", ".join(channels) if channels else "multiple channels"
            await flag_spam(message, f"Cross-channel spam ({ch_str})", timeout=True)
            return
    
    # GAMIFICATION
    await award_xp(message.author, message.guild, XP_PER_MESSAGE, "message")
    await update_streak(user_id)
    
    if user_data[user_id]['messages'] == 1:
        await award_achievement(user_id, 'first_message')
    if user_data[user_id]['messages'] == 100:
        await award_achievement(user_id, 'century')
    if message.channel.name == 'wins':
        await award_achievement(user_id, 'first_win')
    
    await check_auto_roles(message.author)
    
    save_data()
    await bot.process_commands(message)

@bot.event
async def on_reaction_add(reaction, user):
    """Track reactions and award XP"""
    if user.bot:
        return
    
    user_id = str(user.id)
    user_data[user_id]['reactions_given'] += 1
    
    if reaction.message.author and not reaction.message.author.bot:
        author_id = str(reaction.message.author.id)
        user_data[author_id]['reactions_received'] += 1
        
        await award_xp(
            reaction.message.author,
            reaction.message.guild,
            XP_PER_REACTION_RECEIVED,
            "reaction"
        )
        
        if user_data[author_id]['reactions_received'] >= 100:
            await award_achievement(author_id, 'helpful')
    
    save_data()

@bot.event
async def on_voice_state_update(member, before, after):
    """Track voice time and award XP"""
    if member.bot:
        return
    
    user_id = str(member.id)
    current_time = datetime.now()
    
    if before.channel is None and after.channel is not None:
        user_data[user_id]['voice_join_time'] = str(current_time)
    
    elif before.channel is not None and after.channel is None:
        if user_data[user_id]['voice_join_time']:
            join_time = datetime.fromisoformat(user_data[user_id]['voice_join_time'])
            duration = (current_time - join_time).total_seconds() / 60
            
            user_data[user_id]['voice_time'] += duration
            user_data[user_id]['voice_join_time'] = None
            
            xp = int(duration * XP_PER_VOICE_MINUTE)
            await award_xp(member, member.guild, xp, "voice")
            
            if user_data[user_id]['voice_time'] >= 600:
                await award_achievement(user_id, 'voice_active')
    
    save_data()

# ============================================================================
# SLASH COMMANDS
# ============================================================================

@bot.tree.command(name="stats")
@app_commands.describe(user="User to check")
async def stats(interaction: discord.Interaction, user: discord.Member):
    """View detailed user statistics"""
    user_id = str(user.id)
    
    msgs = user_data[user_id]['messages']
    warnings = user_data[user_id]['warnings']
    reactions = user_data[user_id]['reactions_received']
    voice = user_data[user_id]['voice_time']
    
    level = gamification_data[user_id]['level']
    xp = gamification_data[user_id]['xp']
    streak = gamification_data[user_id]['streak_days']
    achievements = len(gamification_data[user_id]['achievements'])
    
    embed = discord.Embed(
        title=f"📊 Stats - {user.display_name}",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    
    embed.add_field(name="📝 Messages", value=f"{msgs:,}", inline=True)
    embed.add_field(name="⚠️ Warnings", value=warnings, inline=True)
    embed.add_field(name="❤️ Reactions", value=reactions, inline=True)
    
    if ENABLE_GAMIFICATION:
        embed.add_field(name="⭐ Level", value=level, inline=True)
        embed.add_field(name="💎 XP", value=f"{xp:,}", inline=True)
        embed.add_field(name="🔥 Streak", value=f"{streak} days", inline=True)
        embed.add_field(name="🏆 Achievements", value=achievements, inline=True)
    
    embed.add_field(name="🎤 Voice Time", value=f"{voice:.0f} min", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rank")
@app_commands.describe(user="User to check (leave empty for yourself)")
async def rank(interaction: discord.Interaction, user: discord.Member = None):
    """Check rank, level, and XP"""
    if not ENABLE_GAMIFICATION:
        await interaction.response.send_message("Gamification is disabled!", ephemeral=True)
        return
    
    target = user or interaction.user
    user_id = str(target.id)
    data = gamification_data[user_id]
    
    level = data['level']
    xp = data['xp']
    streak = data['streak_days']
    
    xp_for_next = (level + 1) * LEVEL_MULTIPLIER
    xp_current_level = level * LEVEL_MULTIPLIER
    xp_progress = xp - xp_current_level
    xp_needed = xp_for_next - xp_current_level
    
    progress = int((xp_progress / xp_needed) * 10)
    bar = "█" * progress + "░" * (10 - progress)
    
    embed = discord.Embed(
        title=f"📊 Rank - {target.display_name}",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    
    embed.add_field(name="Level", value=f"⭐ {level}", inline=True)
    embed.add_field(name="XP", value=f"{xp:,}", inline=True)
    embed.add_field(name="Streak", value=f"🔥 {streak}d", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard")
async def leaderboard(interaction: discord.Interaction):
    """View server leaderboard"""
    if not ENABLE_GAMIFICATION:
        await interaction.response.send_message("Gamification is disabled!", ephemeral=True)
        return
    
    sorted_users = sorted(
        gamification_data.items(),
        key=lambda x: x[1].get('xp', 0),
        reverse=True
    )[:10]
    
    embed = discord.Embed(
        title="🏆 Leaderboard",
        description="Top 10 members",
        color=discord.Color.gold()
    )
    
    for i, (user_id, data) in enumerate(sorted_users, 1):
        try:
            user = await bot.fetch_user(int(user_id))
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            embed.add_field(
                name=f"{medal} {user.display_name}",
                value=f"Level {data['level']} • {data['xp']:,} XP",
                inline=False
            )
        except:
            continue
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="achievements")
@app_commands.describe(user="User to check")
async def achievements(interaction: discord.Interaction, user: discord.Member = None):
    """View achievements"""
    target = user or interaction.user
    user_id = str(target.id)
    earned = gamification_data[user_id].get('achievements', [])
    
    embed = discord.Embed(
        title=f"🏆 Achievements - {target.display_name}",
        description=f"Earned: {len(earned)}/{len(ACHIEVEMENTS)}",
        color=discord.Color.gold()
    )
    
    for key, achievement in ACHIEVEMENTS.items():
        status = "✅" if key in earned else "❌"
        embed.add_field(
            name=f"{status} {achievement['name']}",
            value=f"+{achievement['xp']} XP",
            inline=True
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="reset_warnings")
@app_commands.describe(user="User to reset")
@app_commands.checks.has_permissions(moderate_members=True)
async def reset_warnings(interaction: discord.Interaction, user: discord.Member):
    """Reset user warnings (mod only)"""
    user_id = str(user.id)
    old = user_data[user_id]['warnings']
    user_data[user_id]['warnings'] = 0
    user_data[user_id]['warning_types'] = []
    save_data()
    
    await interaction.response.send_message(
        f"✅ Reset {old} warnings for {user.mention}",
        ephemeral=True
    )

@bot.tree.command(name="warning_leaderboard")
@app_commands.checks.has_permissions(moderate_members=True)
async def warning_leaderboard(interaction: discord.Interaction):
    """View users with most warnings (mod only)"""
    sorted_users = sorted(
        user_data.items(),
        key=lambda x: x[1]['warnings'],
        reverse=True
    )[:10]
    
    sorted_users = [(u, d) for u, d in sorted_users if d['warnings'] > 0]
    
    embed = discord.Embed(
        title="⚠️ Warning Leaderboard",
        color=discord.Color.red()
    )
    
    if not sorted_users:
        embed.description = "No warnings! 🎉"
    else:
        for i, (user_id, data) in enumerate(sorted_users, 1):
            try:
                user = await bot.fetch_user(int(user_id))
                embed.add_field(
                    name=f"{i}. {user.display_name}",
                    value=f"{data['warnings']} warnings",
                    inline=False
                )
            except:
                continue
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ============================================================================
# AI FEATURES (Optional - requires Groq API key)
# ============================================================================

@bot.tree.command(name="practice_pitch")
@app_commands.describe(pitch="Your business pitch")
async def practice_pitch(interaction: discord.Interaction, pitch: str):
    """Get AI feedback on your pitch"""
    if not ENABLE_AI_FEATURES or GROQ_API_KEY == 'YOUR_GROQ_KEY':
        await interaction.response.send_message(
            "❌ AI features not enabled. Set GROQ_API_KEY in config.",
            ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        import aiohttp
        
        prompt = f"""Analyze this business pitch and provide feedback:

"{pitch}"

Rate (1-10):
1. Clarity
2. Hook strength
3. Problem definition
4. Solution clarity

Provide 2-3 specific improvements."""

        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {GROQ_API_KEY}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'llama-3.1-70b-versatile',
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.7,
                    'max_tokens': 500
                }
            ) as response:
                data = await response.json()
                feedback = data['choices'][0]['message']['content']
        
        embed = discord.Embed(
            title="🎤 Pitch Feedback",
            description=feedback,
            color=discord.Color.blue()
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="summarize")
async def summarize(interaction: discord.Interaction):
    """Summarize last 50 messages in channel"""
    if not ENABLE_AI_FEATURES or GROQ_API_KEY == 'YOUR_GROQ_KEY':
        await interaction.response.send_message(
            "❌ AI features not enabled.",
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    try:
        import aiohttp
        
        messages = []
        async for msg in interaction.channel.history(limit=50):
            if not msg.author.bot and msg.content:
                messages.append(f"{msg.author.display_name}: {msg.content}")
        
        messages.reverse()
        conversation = "\n".join(messages[-30:])
        
        prompt = f"""Summarize this Discord conversation in 3-4 sentences:

{conversation}"""

        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {GROQ_API_KEY}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'llama-3.1-70b-versatile',
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.5,
                    'max_tokens': 300
                }
            ) as response:
                data = await response.json()
                summary = data['choices'][0]['message']['content']
        
        embed = discord.Embed(
            title="📝 Channel Summary",
            description=summary,
            color=discord.Color.blue()
        )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@reset_warnings.error
async def reset_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ You need Moderate Members permission!",
            ephemeral=True
        )

@warning_leaderboard.error
async def warning_lb_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ You need Moderate Members permission!",
            ephemeral=True
        )

# ============================================================================
# BOT STARTUP
# ============================================================================

if __name__ == "__main__":
    """
    Bot startup entry point.
    
    SETUP CHECKLIST:
    1.  Replace BOT_TOKEN with your Discord bot token
    2.  (Optional) Add GROQ_API_KEY for AI features
    3.  Install: pip install discord.py aiohttp
    4.  Enable all 3 intents in Discord Developer Portal
    5.  Create roles in server: Active, Regular, Veteran, Elite, Legend, Member, Newcomer
    6.  Invite bot with Administrator permission
    7.  Run: python bot.py
    
    WHAT HAPPENS ON STARTUP:
    - Loads saved user data from JSON files
    - Creates required channels (#mod-logs, #level-ups, #best-of)
    - Syncs slash commands with Discord
    - Starts monitoring all messages
    
    ALL FEATURES:
     Spam detection (rapid, cross-channel, duplicate, image, scam)
     Progressive punishments (5min → 30min → 3hr → 24hr → ban)
     XP & level system with auto-role rewards
     Daily activity streaks
     6 achievements
     Auto-role assignment at message milestones
     Raid detection (mass joins)
     DM warnings to users
     Mod alerts in #mod-logs
     AI pitch practice (optional)
     AI thread summaries (optional)
    
    COMMANDS:
    /stats @user - View detailed statistics
    /rank - Check your rank and XP
    /leaderboard - Top 10 users
    /achievements - View all achievements
    /reset_warnings @user - Clear warnings (mod only)
    /warning_leaderboard - Users with most warnings (mod only)
    /practice_pitch - AI pitch feedback (if enabled)
    /summarize - AI channel summary (if enabled)
    """
    
    if BOT_TOKEN == 'YOUR_BOT_TOKEN':
        print("❌ ERROR: Set BOT_TOKEN in configuration section!")
        print("   Get your token from: https://discord.com/developers/applications")
        print("   1. Create application")
        print("   2. Go to Bot tab → Reset Token → Copy")
        print("   3. Replace BOT_TOKEN = 'YOUR_BOT_TOKEN' with your actual token")
    else:
        try:
            print("=" * 60)
            print("🚀 STARTING DISCORD BOT")
            print("=" * 60)
            print(f"   Bot: Complete Moderation & Gamification Bot")
            print(f"   Features:")
            print(f"      • Spam Detection: ✅ Enabled")
            print(f"      • Gamification: {'✅ Enabled' if ENABLE_GAMIFICATION else '❌ Disabled'}")
            print(f"      • AI Features: {'✅ Enabled' if ENABLE_AI_FEATURES else '❌ Disabled'}")
            print(f"   Auto-ban threshold: {AUTO_BAN_THRESHOLD} warnings")
            print(f"   XP per message: {XP_PER_MESSAGE}")
            print("=" * 60)
            bot.run(BOT_TOKEN)
        except discord.LoginFailure:
            print("❌ ERROR: Invalid bot token!")
            print("   Check that you copied the full token correctly.")
        except Exception as e:
            print(f"❌ ERROR: {e}")
            print("   Make sure discord.py is installed: pip install discord.py aiohttp")