"""
============================================================================
TENBOT - Ultra Discord Bot for Business Communities
============================================================================
All-in-one bot for professional Discord communities with:
- Advanced spam detection (image fingerprinting, trust-aware)
- Multi-dimensional trust scoring
- Case management system
- Gamification and reputation
- Comprehensive moderation tools

Author: TENBOT Development Team
Version: 2.0.0
License: MIT
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
from typing import Optional

# Import configuration
import config

# Import database
from database import Database, get_db

# Import modules
from modules import get_spam_detector, get_image_detector, get_trust_system

# Import utilities
from utils import (
    format_timespan, create_progress_bar, create_embed,
    send_dm, is_moderator, truncate_string
)


# ============================================================================
# BOT SETUP
# ============================================================================

class TenBot(commands.Bot):
    """
    Main bot class with custom initialization.
    """

    def __init__(self):
        # Set up intents (what events bot can see)
        intents = discord.Intents.all()

        # Initialize bot
        super().__init__(
            command_prefix=config.BOT_PREFIX,
            intents=intents,
            help_command=None  # We'll create our own
        )

        # Initialize modules (will be set in setup_hook)
        self.db: Optional[Database] = None
        self.spam_detector = None
        self.image_detector = None
        self.trust_system = None

    async def setup_hook(self):
        """
        Called when bot is setting up.
        Initialize database and modules here.
        """
        print("🚀 Setting up TENBOT...")

        # Initialize database
        self.db = Database()
        await self.db.initialize()

        # Initialize modules
        self.spam_detector = get_spam_detector()
        self.image_detector = get_image_detector()
        self.trust_system = get_trust_system()

        print("✅ All modules initialized!")

        # Load command cogs
        try:
            from commands.mod_commands import ModerationCommands
            from commands.admin_commands import AdminCommands

            await self.add_cog(ModerationCommands(self))
            await self.add_cog(AdminCommands(self))
            print("✅ Command cogs loaded!")
        except Exception as e:
            print(f"⚠️  Warning: Could not load command cogs: {e}")

        # Sync slash commands
        await self.tree.sync()
        print("✅ Slash commands synced!")

    async def on_ready(self):
        """
        Called when bot is fully ready and connected.
        """
        print("=" * 60)
        print(f"✅ {self.user.name} is online!")
        print(f"📊 Connected to {len(self.guilds)} server(s)")
        print(f"👥 Monitoring {sum(g.member_count for g in self.guilds)} users")
        print("=" * 60)

        # Start background tasks
        if not self.backup_database.is_running():
            self.backup_database.start()

        if not self.cleanup_old_data.is_running():
            self.cleanup_old_data.start()

    async def close(self):
        """
        Cleanup when bot shuts down.
        """
        print("🛑 Shutting down...")

        if self.db:
            await self.db.close()

        if self.image_detector:
            await self.image_detector.close()

        await super().close()


# ============================================================================
# INITIALIZE BOT
# ============================================================================

bot = TenBot()


# ============================================================================
# BACKGROUND TASKS
# ============================================================================

@tasks.loop(hours=1)
async def backup_database():
    """Backup database every hour."""
    try:
        db = await get_db()
        await db.backup()
        print(f"💾 Database backed up at {datetime.now().strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"❌ Backup failed: {e}")


@tasks.loop(hours=24)
async def cleanup_old_data():
    """Clean up old data daily."""
    try:
        db = await get_db()

        # Clean message history older than 30 days
        await db.cleanup_old_messages(days=30)

        # Vacuum database to reclaim space
        await db.execute("VACUUM")

        print(f"🧹 Database cleanup completed at {datetime.now().strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")


# ============================================================================
# EVENT HANDLERS
# ============================================================================

@bot.event
async def on_member_join(member: discord.Member):
    """
    Handle new member joining.
    """
    if member.bot:
        return

    db = await get_db()
    user_id = str(member.id)

    # Create user record
    await db.create_user(user_id, member.name, member.display_name)

    # Update join date
    await db.update_user(user_id, joined_server=member.joined_at)

    # Calculate initial trust score
    await bot.trust_system.calculate_trust_score(member)

    # Log to database
    await db.log_action(
        action_type='member_join',
        actor_id=user_id,
        guild_id=str(member.guild.id),
        details={'username': member.name}
    )

    print(f"👋 {member.name} joined the server")


@bot.event
async def on_message(message: discord.Message):
    """
    Main message handler - spam detection, XP, etc.
    """
    # Ignore bots
    if message.author.bot:
        return

    # Ignore DMs
    if not message.guild:
        return

    db = await get_db()
    user_id = str(message.author.id)

    # Ensure user exists in database
    user_data = await db.get_user(user_id)
    if not user_data:
        await db.create_user(user_id, message.author.name, message.author.display_name)

    # ====== SPAM DETECTION ======
    is_spam, spam_type, reason = await bot.spam_detector.check_message(message)

    if is_spam:
        await handle_spam(message, spam_type, reason)
        return  # Don't process spammy messages further

    # ====== IMAGE DETECTION ======
    if message.attachments and config.FEATURES['image_detection']:
        spam_images = await bot.image_detector.check_multiple_images(
            message.attachments,
            user_id,
            str(message.channel.id),
            str(message.id)
        )

        for filename, is_spam_img, img_reason in spam_images:
            if is_spam_img:
                await handle_image_spam(message, filename, img_reason)
                return  # Delete message with spam image

    # ====== UPDATE USER STATS ======
    await db.increment_user_stat(user_id, 'total_messages', 1)

    # Update channel activity
    await db.execute(
        """
        INSERT INTO channel_activity (user_id, channel_id, message_count, last_message_at)
        VALUES (?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, channel_id) DO UPDATE SET
            message_count = message_count + 1,
            last_message_at = CURRENT_TIMESTAMP
        """,
        (user_id, str(message.channel.id))
    )

    # ====== GAMIFICATION ======
    if config.FEATURES['gamification']:
        await handle_xp_gain(message.author, message.guild, 'message')

    # Process commands
    await bot.process_commands(message)


@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    """
    Track reactions for reputation/gamification.
    """
    if user.bot:
        return

    db = await get_db()

    # Increment reaction counter for giver
    await db.increment_user_stat(str(user.id), 'total_reactions_given', 1)

    # Increment for receiver (if not bot)
    if reaction.message.author and not reaction.message.author.bot:
        await db.increment_user_stat(
            str(reaction.message.author.id),
            'total_reactions_received',
            1
        )

        # Award XP to message author
        if config.FEATURES['gamification']:
            await handle_xp_gain(
                reaction.message.author,
                reaction.message.guild,
                'reaction',
                config.XP_PER_REACTION_RECEIVED
            )


# ============================================================================
# SPAM HANDLING
# ============================================================================

async def handle_spam(
    message: discord.Message,
    spam_type: str,
    reason: str
):
    """
    Handle detected spam message.

    Args:
        message: Spam message
        spam_type: Type of spam detected
        reason: Detailed reason
    """
    db = await get_db()
    user_id = str(message.author.id)

    # Delete the message
    try:
        await message.delete()
        print(f"🗑️  Deleted spam from {message.author.name}: {reason}")
    except discord.Forbidden:
        print(f"⚠️  Cannot delete message (missing permissions)")
        return

    # Mark message as spam in database
    await db.execute(
        "UPDATE message_history SET is_spam = 1 WHERE message_id = ?",
        (str(message.id),)
    )

    # Get current warning count
    warning_count = await db.get_warning_count(user_id, active_only=True)
    new_warning_count = warning_count + 1

    # Determine severity and action
    if spam_type in ['scam', 'link_spam']:
        severity = 'high'
    elif spam_type in ['mention_spam', 'cross_channel']:
        severity = 'medium'
    else:
        severity = 'low'

    # Calculate timeout duration
    timeout_duration = config.TIMEOUT_DURATIONS.get(new_warning_count)

    # Create case
    case_id = await db.create_case(
        case_type='warning',
        user_id=user_id,
        reason=f"Spam detected: {reason}",
        created_by='system',
        action_taken=f"Warning #{new_warning_count}" + (f", timeout {format_timespan(timeout_duration)}" if timeout_duration else ""),
        channel_id=str(message.channel.id),
        message_id=str(message.id)
    )

    # Add warning
    await db.add_warning(
        user_id=user_id,
        reason=reason,
        issued_by='system',
        warning_type=spam_type,
        severity=severity,
        action_taken='timeout' if timeout_duration else 'warning_only',
        timeout_duration=timeout_duration,
        message_id=str(message.id),
        channel_id=str(message.channel.id),
        case_id=case_id
    )

    # Apply timeout if needed
    if timeout_duration and new_warning_count < config.AUTO_BAN_THRESHOLD:
        try:
            await message.author.timeout(
                timedelta(seconds=timeout_duration),
                reason=f"Spam warning #{new_warning_count}: {reason}"
            )
        except discord.Forbidden:
            print(f"⚠️  Cannot timeout {message.author.name} (missing permissions)")

    # Auto-ban if threshold reached
    elif new_warning_count >= config.AUTO_BAN_THRESHOLD:
        try:
            await message.author.ban(reason=f"Auto-ban: {new_warning_count} warnings")
            await db.update_user(user_id, is_banned=True)
        except discord.Forbidden:
            print(f"⚠️  Cannot ban {message.author.name} (missing permissions)")

    # Send DM to user
    embed = create_embed(
        title="⚠️ Spam Warning",
        description=f"Your message was removed for violating spam rules.",
        color=discord.Color.red()
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Warning", value=f"#{new_warning_count} of {config.AUTO_BAN_THRESHOLD}", inline=True)

    if timeout_duration:
        embed.add_field(name="Timeout", value=format_timespan(timeout_duration), inline=True)

    if new_warning_count >= config.AUTO_BAN_THRESHOLD - 1:
        embed.add_field(
            name="⚠️ Important",
            value="Next violation will result in automatic ban!",
            inline=False
        )

    await send_dm(message.author, embed)

    # Recalculate trust score (warnings affect trust)
    await bot.trust_system.calculate_trust_score(message.author)


async def handle_image_spam(message: discord.Message, filename: str, reason: str):
    """
    Handle spam image detection.
    """
    # Delete message
    try:
        await message.delete()
        print(f"🖼️  Deleted spam image from {message.author.name}: {reason}")
    except:
        pass

    # Warn user
    embed = create_embed(
        title="🖼️ Spam Image Detected",
        description=f"Your image was removed.",
        color=discord.Color.red()
    )
    embed.add_field(name="Image", value=filename, inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)

    await send_dm(message.author, embed)


# ============================================================================
# GAMIFICATION
# ============================================================================

async def handle_xp_gain(
    user: discord.Member,
    guild: discord.Guild,
    source: str,
    xp_amount: int = None
):
    """
    Award XP to user and handle level ups.

    Args:
        user: Discord Member
        guild: Discord Guild
        source: XP source ('message', 'reaction', 'voice')
        xp_amount: XP to award (uses config defaults if None)
    """
    db = await get_db()
    user_id = str(user.id)

    # Determine XP amount
    if xp_amount is None:
        if source == 'message':
            xp_amount = config.XP_PER_MESSAGE
        elif source == 'reaction':
            xp_amount = config.XP_PER_REACTION_RECEIVED
        elif source == 'voice':
            xp_amount = config.XP_PER_VOICE_MINUTE
        else:
            xp_amount = 0

    # Check cooldown for messages
    if source == 'message':
        gamification = await db.fetch_one(
            "SELECT last_xp_message_time FROM gamification WHERE user_id = ?",
            (user_id,)
        )

        if gamification and gamification['last_xp_message_time']:
            last_time = datetime.fromisoformat(gamification['last_xp_message_time'])
            if (datetime.now() - last_time).total_seconds() < config.XP_COOLDOWN:
                return  # Still on cooldown

        # Update cooldown
        await db.execute(
            "UPDATE gamification SET last_xp_message_time = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,)
        )

    # Add XP
    result = await db.add_xp(user_id, xp_amount, source)

    # Handle level up
    if result['leveled_up']:
        await handle_level_up(user, guild, result['old_level'], result['new_level'])


async def handle_level_up(
    user: discord.Member,
    guild: discord.Guild,
    old_level: int,
    new_level: int
):
    """
    Handle user leveling up.

    Args:
        user: Discord Member
        guild: Discord Guild
        old_level: Previous level
        new_level: New level
    """
    print(f"🎉 {user.name} leveled up: {old_level} → {new_level}")

    # Check for level role rewards
    if new_level in config.LEVEL_ROLES:
        role_name = config.LEVEL_ROLES[new_level]
        role = discord.utils.get(guild.roles, name=role_name)

        if role:
            try:
                await user.add_roles(role)
            except discord.Forbidden:
                print(f"⚠️  Cannot assign role {role_name} (missing permissions)")

    # Send level up message
    embed = create_embed(
        title="🎉 Level Up!",
        description=f"{user.mention} reached **Level {new_level}**!",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=user.display_avatar.url)

    # Find level-up channel or use general
    channel = discord.utils.get(guild.channels, name='level-ups')
    if not channel:
        channel = discord.utils.get(guild.channels, name='general')

    if channel:
        try:
            await channel.send(embed=embed)
        except:
            pass


# ============================================================================
# SLASH COMMANDS - USER COMMANDS
# ============================================================================

@bot.tree.command(name="stats")
@app_commands.describe(user="User to check stats for")
async def stats_command(interaction: discord.Interaction, user: discord.Member = None):
    """
    View detailed user statistics.
    """
    target = user or interaction.user
    db = await get_db()
    user_id = str(target.id)

    # Get user profile
    profile = await db.get_user_profile(user_id)

    if not profile:
        await interaction.response.send_message(
            "❌ User not found in database.",
            ephemeral=True
        )
        return

    # Create embed
    embed = create_embed(
        title=f"📊 Stats - {target.display_name}",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=target.display_avatar.url)

    # Basic stats
    embed.add_field(
        name="📝 Messages",
        value=f"{profile.get('total_messages', 0):,}",
        inline=True
    )

    embed.add_field(
        name="❤️ Reactions",
        value=f"{profile.get('total_reactions_received', 0):,}",
        inline=True
    )

    embed.add_field(
        name="🎤 Voice Time",
        value=f"{profile.get('total_voice_minutes', 0):.0f}m",
        inline=True
    )

    # Gamification
    if config.FEATURES['gamification'] and profile.get('total_xp'):
        embed.add_field(
            name="⭐ Level",
            value=str(profile.get('current_level', 1)),
            inline=True
        )

        embed.add_field(
            name="💎 XP",
            value=f"{profile.get('total_xp', 0):,}",
            inline=True
        )

        embed.add_field(
            name="🔥 Streak",
            value=f"{profile.get('current_streak_days', 0)} days",
            inline=True
        )

    # Trust & Reputation
    if config.FEATURES['trust_system']:
        trust_score = profile.get('trust_score', 0)
        trust_tier = profile.get('trust_tier', 'new')

        embed.add_field(
            name="🛡️ Trust Score",
            value=f"{trust_score:.1f}/100 ({trust_tier})",
            inline=True
        )

    # Warnings
    warnings = profile.get('active_warnings', 0)
    if warnings > 0:
        embed.add_field(
            name="⚠️ Warnings",
            value=str(warnings),
            inline=True
        )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="rank")
async def rank_command(interaction: discord.Interaction, user: discord.Member = None):
    """
    Check your rank and XP progress.
    """
    if not config.FEATURES['gamification']:
        await interaction.response.send_message(
            "❌ Gamification is disabled.",
            ephemeral=True
        )
        return

    target = user or interaction.user
    db = await get_db()
    user_id = str(target.id)

    # Get gamification data
    data = await db.fetch_one(
        "SELECT * FROM gamification WHERE user_id = ?",
        (user_id,)
    )

    if not data:
        await interaction.response.send_message(
            "❌ No data found.",
            ephemeral=True
        )
        return

    # Calculate progress to next level
    current_level = data['current_level']
    total_xp = data['total_xp']
    xp_for_next = (current_level + 1) * config.XP_PER_LEVEL
    xp_current_level = current_level * config.XP_PER_LEVEL
    xp_progress = total_xp - xp_current_level
    xp_needed = xp_for_next - xp_current_level

    progress_bar = create_progress_bar(xp_progress, xp_needed)

    # Create embed
    embed = create_embed(
        title=f"📊 Rank - {target.display_name}",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=target.display_avatar.url)

    embed.add_field(
        name="Level",
        value=f"⭐ {current_level}",
        inline=True
    )

    embed.add_field(
        name="Total XP",
        value=f"{total_xp:,}",
        inline=True
    )

    embed.add_field(
        name="Streak",
        value=f"🔥 {data['current_streak_days']}d",
        inline=True
    )

    embed.add_field(
        name=f"Progress to Level {current_level + 1}",
        value=f"{progress_bar}\n{xp_progress}/{xp_needed} XP",
        inline=False
    )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="leaderboard")
async def leaderboard_command(interaction: discord.Interaction):
    """
    View server leaderboard.
    """
    if not config.FEATURES['gamification']:
        await interaction.response.send_message(
            "❌ Gamification is disabled.",
            ephemeral=True
        )
        return

    db = await get_db()
    top_users = await db.get_leaderboard(limit=10)

    embed = create_embed(
        title="🏆 Leaderboard",
        description="Top 10 members by XP",
        color=discord.Color.gold()
    )

    for i, user_data in enumerate(top_users, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."

        embed.add_field(
            name=f"{medal} {user_data.get('display_name', 'Unknown')}",
            value=f"Level {user_data.get('current_level', 1)} • {user_data.get('total_xp', 0):,} XP",
            inline=False
        )

    await interaction.response.send_message(embed=embed)


# ============================================================================
# SLASH COMMANDS - MOD COMMANDS
# ============================================================================

@bot.tree.command(name="investigate")
@app_commands.describe(user="User to investigate")
@app_commands.checks.has_permissions(moderate_members=True)
async def investigate_command(interaction: discord.Interaction, user: discord.Member):
    """
    Get comprehensive user investigation report (MOD ONLY).
    """
    await interaction.response.defer(ephemeral=True)

    db = await get_db()
    user_id = str(user.id)

    # Get all user data
    profile = await db.get_user_profile(user_id)
    warnings = await db.get_user_warnings(user_id, active_only=False)
    cases = await db.get_user_cases(user_id)
    trust_data = await bot.trust_system.get_trust_score(user_id)

    if not profile:
        await interaction.followup.send("❌ User not found.", ephemeral=True)
        return

    # Create detailed embed
    embed = create_embed(
        title=f"🔍 Investigation - {user.display_name}",
        description=f"User ID: {user_id}",
        color=discord.Color.orange()
    )

    # Trust info
    if trust_data:
        trust_score = trust_data.get('overall_score', 0)
        trust_tier = trust_data.get('trust_tier', 'unknown')

        if trust_score >= 80:
            status = "🟢 Highly Trusted"
        elif trust_score >= 60:
            status = "🟡 Trusted"
        elif trust_score >= 40:
            status = "🟠 Regular"
        else:
            status = "🔴 Low Trust"

        embed.add_field(
            name="Trust Status",
            value=f"{status}\nScore: {trust_score:.1f}/100\nTier: {trust_tier}",
            inline=True
        )

    # Activity
    embed.add_field(
        name="Activity",
        value=f"Messages: {profile.get('total_messages', 0):,}\nVoice: {profile.get('total_voice_minutes', 0):.0f}m",
        inline=True
    )

    # Warnings
    active_warnings = len([w for w in warnings if not w.get('expires_at') or datetime.fromisoformat(w['expires_at']) > datetime.now()])
    embed.add_field(
        name="Warnings",
        value=f"Active: {active_warnings}\nTotal: {len(warnings)}",
        inline=True
    )

    # Recent cases
    if cases:
        recent_cases = cases[:3]
        case_text = "\n".join(
            f"#{c['case_id']}: {c['case_type']} - {truncate_string(c['reason'], 50)}"
            for c in recent_cases
        )
        embed.add_field(
            name="Recent Cases",
            value=case_text or "None",
            inline=False
        )

    # Account info
    created_days = (datetime.now(user.created_at.tzinfo) - user.created_at).days
    joined_days = (datetime.now(user.joined_at.tzinfo) - user.joined_at).days if user.joined_at else 0

    embed.add_field(
        name="Account Age",
        value=f"{created_days} days",
        inline=True
    )

    embed.add_field(
        name="Server Age",
        value=f"{joined_days} days",
        inline=True
    )

    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="trust")
@app_commands.describe(user="User to check trust score")
async def trust_command(interaction: discord.Interaction, user: discord.Member = None):
    """
    Check trust score for a user.
    """
    target = user or interaction.user
    await interaction.response.defer()

    # Calculate/update trust score
    trust_data = await bot.trust_system.calculate_trust_score(target)

    embed = create_embed(
        title=f"🛡️ Trust Score - {target.display_name}",
        color=discord.Color.blue()
    )

    # Overall score
    overall = trust_data['overall_score']
    tier = trust_data['trust_tier']

    embed.add_field(
        name="Overall Score",
        value=f"{overall:.1f}/100",
        inline=True
    )

    embed.add_field(
        name="Trust Tier",
        value=tier.title(),
        inline=True
    )

    # Component breakdown (for mods only)
    if is_moderator(interaction.user):
        components = f"""
        Account Age: {trust_data['account_age']:.1f}
        Server Age: {trust_data['server_age']:.1f}
        Message Count: {trust_data['message_count']:.1f}
        Message Quality: {trust_data['message_quality']:.1f}
        Consistency: {trust_data['consistency']:.1f}
        Warnings: {trust_data['warning_penalty']:.1f}
        Reputation: {trust_data['reputation']:.1f}
        """
        embed.add_field(
            name="Component Breakdown",
            value=f"```{components}```",
            inline=False
        )

    await interaction.followup.send(embed=embed)


# ============================================================================
# IMAGE COMMANDS
# ============================================================================

@bot.tree.command(name="report_image")
@app_commands.describe(
    message_id="ID of message containing spam image",
    reason="Why you're reporting this image"
)
async def report_image_command(
    interaction: discord.Interaction,
    message_id: str,
    reason: str
):
    """
    Report an image as spam.
    """
    await interaction.response.defer(ephemeral=True)

    result = await bot.image_detector.report_image(
        message_id=message_id,
        reported_by=str(interaction.user.id),
        report_reason=reason,
        channel_id=str(interaction.channel.id)
    )

    if not result['success']:
        await interaction.followup.send(
            f"❌ {result['reason']}",
            ephemeral=True
        )
        return

    embed = create_embed(
        title="✅ Image Reported",
        description="Thank you for helping keep the community safe!",
        color=discord.Color.green()
    )

    embed.add_field(
        name="Report Count",
        value=f"{result['report_count']}/{result['threshold']}",
        inline=True
    )

    if result['auto_blocked']:
        embed.add_field(
            name="Status",
            value="🚫 Auto-blocked (threshold reached)",
            inline=True
        )
        embed.color = discord.Color.red()

    await interaction.followup.send(embed=embed, ephemeral=True)


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@investigate_command.error
@trust_command.error
async def mod_command_error(interaction: discord.Interaction, error):
    """Handle errors for mod commands."""
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ You need Moderate Members permission to use this command!",
            ephemeral=True
        )


# ============================================================================
# MAIN
# ============================================================================

def main():
    """
    Main entry point.
    """
    # Validate config
    errors = config.validate_config()
    if errors:
        print("⚠️  Configuration Errors:")
        for error in errors:
            print(f"   ❌ {error}")
        return

    # Show startup info
    print("=" * 60)
    print("🚀 STARTING TENBOT")
    print("=" * 60)
    print(f"Features Enabled:")
    for feature, enabled in config.FEATURES.items():
        status = "✅" if enabled else "❌"
        print(f"  {status} {feature}")
    print("=" * 60)

    # Run bot
    try:
        bot.run(config.BOT_TOKEN)
    except discord.LoginFailure:
        print("❌ Invalid bot token!")
        print("   Please set BOT_TOKEN in your .env file")
    except Exception as e:
        print(f"❌ Error starting bot: {e}")


if __name__ == "__main__":
    main()
