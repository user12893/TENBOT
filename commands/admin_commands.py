"""
============================================================================
ADMIN COMMANDS
============================================================================
Administrative commands for bot management and configuration.

Commands included:
- Bot control: reload, sync, shutdown
- Database: backup, stats, cleanup
- Image management: whitelist, blacklist
- Trust: recalculate, reset
- Configuration: view, update
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

import config
from database import get_db
from modules import get_image_detector, get_trust_system, get_spam_detector
from utils import create_embed


class AdminCommands(commands.Cog):
    """Admin commands cog."""

    def __init__(self, bot):
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if user is admin."""
        return interaction.user.guild_permissions.administrator

    # ========================================================================
    # BOT MANAGEMENT
    # ========================================================================

    @app_commands.command(name="sync")
    async def sync_command(self, interaction: discord.Interaction):
        """Sync slash commands with Discord (ADMIN ONLY)."""

        await interaction.response.defer(ephemeral=True)

        try:
            synced = await self.bot.tree.sync()
            await interaction.followup.send(
                f"✅ Synced {len(synced)} commands",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to sync: {e}",
                ephemeral=True
            )

    @app_commands.command(name="botstats")
    async def botstats_command(self, interaction: discord.Interaction):
        """View bot statistics (ADMIN ONLY)."""

        await interaction.response.defer()

        db = await get_db()

        # Get statistics
        total_users = await db.fetch_value("SELECT COUNT(*) FROM users")
        total_messages = await db.fetch_value("SELECT COUNT(*) FROM message_history")
        total_warnings = await db.fetch_value("SELECT COUNT(*) FROM warnings")
        total_cases = await db.fetch_value("SELECT COUNT(*) FROM cases")
        spam_blocked = await db.fetch_value("SELECT COUNT(*) FROM message_history WHERE is_spam = 1")

        # Image stats
        image_detector = get_image_detector()
        image_stats = await image_detector.get_image_stats()

        # Spam stats
        spam_detector = get_spam_detector()
        spam_stats = await spam_detector.get_spam_stats()

        embed = create_embed(
            title="📊 Bot Statistics",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Users",
            value=f"{total_users:,}",
            inline=True
        )

        embed.add_field(
            name="Messages Tracked",
            value=f"{total_messages:,}",
            inline=True
        )

        embed.add_field(
            name="Spam Blocked",
            value=f"{spam_blocked:,}",
            inline=True
        )

        embed.add_field(
            name="Total Warnings",
            value=f"{total_warnings:,}",
            inline=True
        )

        embed.add_field(
            name="Total Cases",
            value=f"{total_cases:,}",
            inline=True
        )

        embed.add_field(
            name="Spam Rate",
            value=f"{spam_stats.get('spam_rate', 0)}%",
            inline=True
        )

        embed.add_field(
            name="Images Fingerprinted",
            value=f"{image_stats['total_images']:,}",
            inline=True
        )

        embed.add_field(
            name="Spam Images",
            value=f"{image_stats['spam_images']:,}",
            inline=True
        )

        embed.add_field(
            name="Image Reports",
            value=f"{image_stats['total_reports']:,}",
            inline=True
        )

        # Server info
        embed.add_field(
            name="Servers",
            value=f"{len(self.bot.guilds)}",
            inline=True
        )

        embed.add_field(
            name="Total Members",
            value=f"{sum(g.member_count for g in self.bot.guilds):,}",
            inline=True
        )

        await interaction.followup.send(embed=embed)

    # ========================================================================
    # DATABASE MANAGEMENT
    # ========================================================================

    @app_commands.command(name="backup")
    async def backup_command(self, interaction: discord.Interaction):
        """Create a database backup (ADMIN ONLY)."""

        await interaction.response.defer(ephemeral=True)

        try:
            db = await get_db()
            await db.backup()

            await interaction.followup.send(
                "✅ Database backed up successfully!",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Backup failed: {e}",
                ephemeral=True
            )

    @app_commands.command(name="cleanup")
    async def cleanup_command(self, interaction: discord.Interaction):
        """Clean up old data from database (ADMIN ONLY)."""

        await interaction.response.defer(ephemeral=True)

        try:
            db = await get_db()

            # Clean old messages
            await db.cleanup_old_messages(days=30)

            # Vacuum database
            await db.execute("VACUUM")

            await interaction.followup.send(
                "✅ Database cleanup completed!",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Cleanup failed: {e}",
                ephemeral=True
            )

    # ========================================================================
    # IMAGE MANAGEMENT
    # ========================================================================

    @app_commands.command(name="whitelist_image")
    @app_commands.describe(phash="Perceptual hash of image to whitelist")
    async def whitelist_image_command(
        self,
        interaction: discord.Interaction,
        phash: str
    ):
        """Remove an image from spam list (ADMIN ONLY)."""

        await interaction.response.defer(ephemeral=True)

        image_detector = get_image_detector()
        success = await image_detector.whitelist_image(phash)

        if success:
            await interaction.followup.send(
                f"✅ Image whitelisted (hash: {phash[:16]}...)",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ Failed to whitelist image",
                ephemeral=True
            )

    @app_commands.command(name="blacklist_image")
    @app_commands.describe(
        phash="Perceptual hash of image to blacklist",
        category="Spam category"
    )
    async def blacklist_image_command(
        self,
        interaction: discord.Interaction,
        phash: str,
        category: str = "manual"
    ):
        """Add an image to spam list (ADMIN ONLY)."""

        await interaction.response.defer(ephemeral=True)

        image_detector = get_image_detector()
        success = await image_detector.blacklist_image(phash, category)

        if success:
            await interaction.followup.send(
                f"✅ Image blacklisted (hash: {phash[:16]}...)\n**Category:** {category}",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ Failed to blacklist image",
                ephemeral=True
            )

    @app_commands.command(name="imagestats")
    async def imagestats_command(self, interaction: discord.Interaction):
        """View image detection statistics (ADMIN ONLY)."""

        await interaction.response.defer()

        image_detector = get_image_detector()
        stats = await image_detector.get_image_stats()

        embed = create_embed(
            title="🖼️ Image Detection Statistics",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Total Images",
            value=f"{stats['total_images']:,}",
            inline=True
        )

        embed.add_field(
            name="Spam Images",
            value=f"{stats['spam_images']:,}",
            inline=True
        )

        embed.add_field(
            name="Clean Images",
            value=f"{stats['clean_images']:,}",
            inline=True
        )

        embed.add_field(
            name="Total Reports",
            value=f"{stats['total_reports']:,}",
            inline=True
        )

        embed.add_field(
            name="Blocked Today",
            value=f"{stats['blocked_today']:,}",
            inline=True
        )

        embed.add_field(
            name="Spam Rate",
            value=f"{stats['spam_percentage']}%",
            inline=True
        )

        await interaction.followup.send(embed=embed)

    # ========================================================================
    # TRUST MANAGEMENT
    # ========================================================================

    @app_commands.command(name="recalculate_trust")
    @app_commands.describe(user="User to recalculate (leave empty for all users)")
    async def recalculate_trust_command(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """Recalculate trust scores (ADMIN ONLY)."""

        await interaction.response.defer(ephemeral=True)

        trust_system = get_trust_system()

        if user:
            # Single user
            await trust_system.calculate_trust_score(user)
            await interaction.followup.send(
                f"✅ Recalculated trust score for {user.mention}",
                ephemeral=True
            )
        else:
            # All users
            await interaction.followup.send(
                "🔄 Recalculating trust scores for all users... This may take a while.",
                ephemeral=True
            )

            await trust_system.recalculate_all_trust_scores(interaction.guild)

            await interaction.channel.send(
                f"✅ {interaction.user.mention} Recalculated trust scores for all members!"
            )

    @app_commands.command(name="reset_warnings")
    @app_commands.describe(user="User to reset warnings for")
    async def reset_warnings_command(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        """Reset all warnings for a user (ADMIN ONLY)."""

        await interaction.response.defer(ephemeral=True)

        db = await get_db()

        # Get current warning count
        old_count = await db.get_warning_count(str(user.id), active_only=False)

        # Expire all warnings
        await db.execute(
            "UPDATE warnings SET expires_at = datetime('now', '-1 day') WHERE user_id = ?",
            (str(user.id),)
        )

        # Log action
        await db.log_action(
            action_type='warnings_reset',
            actor_id=str(interaction.user.id),
            target_id=str(user.id),
            details={'old_count': old_count},
            guild_id=str(interaction.guild.id)
        )

        # Recalculate trust
        await self.bot.trust_system.calculate_trust_score(user)

        await interaction.followup.send(
            f"✅ Reset {old_count} warnings for {user.mention}",
            ephemeral=True
        )

    # ========================================================================
    # CONFIGURATION
    # ========================================================================

    @app_commands.command(name="config")
    async def config_command(self, interaction: discord.Interaction):
        """View current bot configuration (ADMIN ONLY)."""

        await interaction.response.defer(ephemeral=True)

        embed = create_embed(
            title="⚙️ Bot Configuration",
            description="Current settings (edit config.py to change)",
            color=discord.Color.blue()
        )

        # Spam Detection
        spam_config = f"""
        Message Count: {config.SPAM_MESSAGE_COUNT}
        Time Window: {config.SPAM_TIME_WINDOW}s
        Duplicate Count: {config.SPAM_DUPLICATE_COUNT}
        Cross-Channel: {config.SPAM_CROSS_CHANNEL_COUNT}
        """
        embed.add_field(
            name="🚫 Spam Detection",
            value=f"```{spam_config}```",
            inline=False
        )

        # Punishments
        punishment_config = f"""
        1st Warning: {config.TIMEOUT_DURATIONS.get(1, 0)}s
        2nd Warning: {config.TIMEOUT_DURATIONS.get(2, 0)}s
        3rd Warning: {config.TIMEOUT_DURATIONS.get(3, 0)}s
        Auto-Ban: {config.AUTO_BAN_THRESHOLD} warnings
        """
        embed.add_field(
            name="⚖️ Punishments",
            value=f"```{punishment_config}```",
            inline=False
        )

        # Features
        features_text = "\n".join(
            f"{'✅' if enabled else '❌'} {name}"
            for name, enabled in config.FEATURES.items()
        )
        embed.add_field(
            name="🎛️ Features",
            value=features_text,
            inline=False
        )

        # Gamification
        if config.FEATURES['gamification']:
            gamif_config = f"""
            XP per Message: {config.XP_PER_MESSAGE}
            XP per Reaction: {config.XP_PER_REACTION_RECEIVED}
            XP Cooldown: {config.XP_COOLDOWN}s
            XP per Level: {config.XP_PER_LEVEL}
            """
            embed.add_field(
                name="🎮 Gamification",
                value=f"```{gamif_config}```",
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="top_spammers")
    @app_commands.describe(limit="Number of users to show")
    async def top_spammers_command(
        self,
        interaction: discord.Interaction,
        limit: int = 10
    ):
        """View users with most warnings (ADMIN ONLY)."""

        await interaction.response.defer(ephemeral=True)

        db = await get_db()

        top_users = await db.fetch_all(
            """
            SELECT u.user_id, u.username, u.display_name, COUNT(w.warning_id) as warning_count
            FROM users u
            JOIN warnings w ON u.user_id = w.user_id
            GROUP BY u.user_id
            ORDER BY warning_count DESC
            LIMIT ?
            """,
            (limit,)
        )

        if not top_users:
            await interaction.followup.send(
                "✅ No warnings found!",
                ephemeral=True
            )
            return

        embed = create_embed(
            title="⚠️ Top Spammers",
            description=f"Users with most warnings",
            color=discord.Color.red()
        )

        for i, user_data in enumerate(top_users, 1):
            embed.add_field(
                name=f"{i}. {user_data['display_name']}",
                value=f"**Warnings:** {user_data['warning_count']}",
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)


# ============================================================================
# SETUP
# ============================================================================

async def setup(bot):
    """Load the cog."""
    await bot.add_cog(AdminCommands(bot))
