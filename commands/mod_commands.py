"""
============================================================================
MODERATION COMMANDS
============================================================================
Comprehensive moderation command suite for TENBOT.

Commands included:
- Punishment: ban, kick, timeout, warn
- Cleanup: purge, clean
- Management: lock, unlock, slowmode
- Information: warnings, cases, userinfo
- Appeals: appeal handling
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta, datetime
from typing import Optional

import config
from database import get_db
from utils import create_embed, format_timespan, is_moderator, truncate_string


class ModerationCommands(commands.Cog):
    """Moderation commands cog."""

    def __init__(self, bot):
        self.bot = bot

    # ========================================================================
    # PUNISHMENT COMMANDS
    # ========================================================================

    @app_commands.command(name="ban")
    @app_commands.describe(
        user="User to ban",
        reason="Reason for ban",
        delete_days="Days of message history to delete (0-7)"
    )
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban_command(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str,
        delete_days: int = 1
    ):
        """Ban a user from the server."""

        if delete_days < 0 or delete_days > 7:
            await interaction.response.send_message(
                "❌ Delete days must be between 0-7",
                ephemeral=True
            )
            return

        # Check hierarchy
        if user.top_role >= interaction.user.top_role:
            await interaction.response.send_message(
                "❌ You cannot ban this user (role hierarchy)",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        db = await get_db()

        # Create case
        case_id = await db.create_case(
            case_type='ban',
            user_id=str(user.id),
            reason=reason,
            created_by=str(interaction.user.id),
            action_taken='permanent_ban'
        )

        # Add to warnings
        await db.add_warning(
            user_id=str(user.id),
            reason=reason,
            issued_by=str(interaction.user.id),
            warning_type='ban',
            severity='critical',
            action_taken='ban',
            case_id=case_id
        )

        # Send DM before ban
        embed = create_embed(
            title="🔨 Banned",
            description=f"You have been banned from {interaction.guild.name}",
            color=discord.Color.red()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Case ID", value=f"#{case_id}", inline=True)

        try:
            await user.send(embed=embed)
        except:
            pass

        # Execute ban
        try:
            await user.ban(
                reason=f"[Case #{case_id}] {reason}",
                delete_message_days=delete_days
            )

            # Update database
            await db.update_user(str(user.id), is_banned=True)

            # Log action
            await db.log_action(
                action_type='ban',
                actor_id=str(interaction.user.id),
                target_id=str(user.id),
                details={'reason': reason, 'case_id': case_id},
                guild_id=str(interaction.guild.id)
            )

            # Confirmation
            await interaction.followup.send(
                f"✅ Banned {user.mention}\n**Reason:** {reason}\n**Case:** #{case_id}",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Cannot ban user (missing permissions)",
                ephemeral=True
            )

    @app_commands.command(name="kick")
    @app_commands.describe(user="User to kick", reason="Reason for kick")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick_command(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str
    ):
        """Kick a user from the server."""

        # Check hierarchy
        if user.top_role >= interaction.user.top_role:
            await interaction.response.send_message(
                "❌ You cannot kick this user (role hierarchy)",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        db = await get_db()

        # Create case
        case_id = await db.create_case(
            case_type='kick',
            user_id=str(user.id),
            reason=reason,
            created_by=str(interaction.user.id),
            action_taken='kick'
        )

        # Send DM before kick
        embed = create_embed(
            title="👢 Kicked",
            description=f"You have been kicked from {interaction.guild.name}",
            color=discord.Color.orange()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Case ID", value=f"#{case_id}", inline=True)
        embed.add_field(name="Note", value="You can rejoin using an invite link", inline=False)

        try:
            await user.send(embed=embed)
        except:
            pass

        # Execute kick
        try:
            await user.kick(reason=f"[Case #{case_id}] {reason}")

            await db.log_action(
                action_type='kick',
                actor_id=str(interaction.user.id),
                target_id=str(user.id),
                details={'reason': reason, 'case_id': case_id},
                guild_id=str(interaction.guild.id)
            )

            await interaction.followup.send(
                f"✅ Kicked {user.mention}\n**Reason:** {reason}\n**Case:** #{case_id}",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Cannot kick user (missing permissions)",
                ephemeral=True
            )

    @app_commands.command(name="timeout")
    @app_commands.describe(
        user="User to timeout",
        duration="Duration in minutes",
        reason="Reason for timeout"
    )
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout_command(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        duration: int,
        reason: str
    ):
        """Timeout (mute) a user."""

        if duration < 1 or duration > 40320:  # Max 28 days
            await interaction.response.send_message(
                "❌ Duration must be between 1 minute and 28 days (40320 minutes)",
                ephemeral=True
            )
            return

        # Check hierarchy
        if user.top_role >= interaction.user.top_role:
            await interaction.response.send_message(
                "❌ You cannot timeout this user (role hierarchy)",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        db = await get_db()

        # Create case
        case_id = await db.create_case(
            case_type='timeout',
            user_id=str(user.id),
            reason=reason,
            created_by=str(interaction.user.id),
            action_taken=f'timeout_{duration}m'
        )

        # Add warning
        await db.add_warning(
            user_id=str(user.id),
            reason=reason,
            issued_by=str(interaction.user.id),
            warning_type='timeout',
            severity='medium',
            action_taken='timeout',
            timeout_duration=duration * 60,
            case_id=case_id
        )

        # Send DM
        embed = create_embed(
            title="🔇 Timeout",
            description=f"You have been timed out in {interaction.guild.name}",
            color=discord.Color.orange()
        )
        embed.add_field(name="Duration", value=format_timespan(duration * 60), inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)

        try:
            await user.send(embed=embed)
        except:
            pass

        # Execute timeout
        try:
            await user.timeout(
                timedelta(minutes=duration),
                reason=f"[Case #{case_id}] {reason}"
            )

            await db.log_action(
                action_type='timeout',
                actor_id=str(interaction.user.id),
                target_id=str(user.id),
                details={'reason': reason, 'duration': duration, 'case_id': case_id},
                guild_id=str(interaction.guild.id)
            )

            await interaction.followup.send(
                f"✅ Timed out {user.mention} for {format_timespan(duration * 60)}\n**Reason:** {reason}\n**Case:** #{case_id}",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Cannot timeout user (missing permissions)",
                ephemeral=True
            )

    @app_commands.command(name="warn")
    @app_commands.describe(
        user="User to warn",
        reason="Reason for warning",
        severity="Warning severity"
    )
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn_command(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str,
        severity: str = "low"
    ):
        """Issue a manual warning to a user."""

        await interaction.response.defer(ephemeral=True)

        db = await get_db()

        # Create case
        case_id = await db.create_case(
            case_type='warning',
            user_id=str(user.id),
            reason=reason,
            created_by=str(interaction.user.id),
            action_taken='warning_only'
        )

        # Add warning
        await db.add_warning(
            user_id=str(user.id),
            reason=reason,
            issued_by=str(interaction.user.id),
            warning_type='manual',
            severity=severity,
            action_taken='warning_only',
            case_id=case_id
        )

        # Get warning count
        warning_count = await db.get_warning_count(str(user.id))

        # Send DM
        embed = create_embed(
            title="⚠️ Warning",
            description=f"You have received a warning in {interaction.guild.name}",
            color=discord.Color.yellow()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Warning Count", value=f"{warning_count}/{config.AUTO_BAN_THRESHOLD}", inline=True)
        embed.add_field(name="Case ID", value=f"#{case_id}", inline=True)

        if warning_count >= config.AUTO_BAN_THRESHOLD - 1:
            embed.add_field(
                name="⚠️ Important",
                value="You are close to being auto-banned!",
                inline=False
            )

        try:
            await user.send(embed=embed)
        except:
            pass

        await db.log_action(
            action_type='warning',
            actor_id=str(interaction.user.id),
            target_id=str(user.id),
            details={'reason': reason, 'case_id': case_id},
            guild_id=str(interaction.guild.id)
        )

        # Recalculate trust
        await self.bot.trust_system.calculate_trust_score(user)

        await interaction.followup.send(
            f"✅ Warned {user.mention}\n**Reason:** {reason}\n**Warning:** {warning_count}/{config.AUTO_BAN_THRESHOLD}\n**Case:** #{case_id}",
            ephemeral=True
        )

    # ========================================================================
    # CLEANUP COMMANDS
    # ========================================================================

    @app_commands.command(name="purge")
    @app_commands.describe(
        amount="Number of messages to delete (1-100)",
        user="Only delete messages from this user"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge_command(
        self,
        interaction: discord.Interaction,
        amount: int,
        user: Optional[discord.Member] = None
    ):
        """Bulk delete messages."""

        if amount < 1 or amount > 100:
            await interaction.response.send_message(
                "❌ Amount must be between 1-100",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        def check(message):
            if user:
                return message.author == user
            return True

        try:
            deleted = await interaction.channel.purge(limit=amount, check=check)

            db = await get_db()
            await db.log_action(
                action_type='purge',
                actor_id=str(interaction.user.id),
                target_id=str(user.id) if user else None,
                details={'amount': len(deleted), 'channel_id': str(interaction.channel.id)},
                guild_id=str(interaction.guild.id)
            )

            msg = f"✅ Deleted {len(deleted)} messages"
            if user:
                msg += f" from {user.mention}"

            await interaction.followup.send(msg, ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Missing permissions to delete messages",
                ephemeral=True
            )

    # ========================================================================
    # CHANNEL MANAGEMENT
    # ========================================================================

    @app_commands.command(name="lock")
    @app_commands.describe(reason="Reason for locking channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock_command(self, interaction: discord.Interaction, reason: str = "Not specified"):
        """Lock the current channel (prevent @everyone from sending messages)."""

        await interaction.response.defer()

        try:
            await interaction.channel.set_permissions(
                interaction.guild.default_role,
                send_messages=False,
                reason=f"Locked by {interaction.user.name}: {reason}"
            )

            db = await get_db()
            await db.log_action(
                action_type='channel_lock',
                actor_id=str(interaction.user.id),
                details={'reason': reason, 'channel_id': str(interaction.channel.id)},
                guild_id=str(interaction.guild.id)
            )

            embed = create_embed(
                title="🔒 Channel Locked",
                description=f"This channel has been locked by {interaction.user.mention}",
                color=discord.Color.red()
            )
            embed.add_field(name="Reason", value=reason, inline=False)

            await interaction.followup.send(embed=embed)

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Missing permissions to lock channel",
                ephemeral=True
            )

    @app_commands.command(name="unlock")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock_command(self, interaction: discord.Interaction):
        """Unlock the current channel."""

        await interaction.response.defer()

        try:
            await interaction.channel.set_permissions(
                interaction.guild.default_role,
                send_messages=None,  # Reset to default
                reason=f"Unlocked by {interaction.user.name}"
            )

            db = await get_db()
            await db.log_action(
                action_type='channel_unlock',
                actor_id=str(interaction.user.id),
                details={'channel_id': str(interaction.channel.id)},
                guild_id=str(interaction.guild.id)
            )

            embed = create_embed(
                title="🔓 Channel Unlocked",
                description=f"This channel has been unlocked by {interaction.user.mention}",
                color=discord.Color.green()
            )

            await interaction.followup.send(embed=embed)

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Missing permissions to unlock channel",
                ephemeral=True
            )

    @app_commands.command(name="slowmode")
    @app_commands.describe(seconds="Slowmode delay in seconds (0 to disable)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode_command(self, interaction: discord.Interaction, seconds: int):
        """Set slowmode for the current channel."""

        if seconds < 0 or seconds > 21600:
            await interaction.response.send_message(
                "❌ Slowmode must be between 0-21600 seconds (6 hours)",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            await interaction.channel.edit(slowmode_delay=seconds)

            db = await get_db()
            await db.log_action(
                action_type='slowmode_change',
                actor_id=str(interaction.user.id),
                details={'seconds': seconds, 'channel_id': str(interaction.channel.id)},
                guild_id=str(interaction.guild.id)
            )

            if seconds == 0:
                msg = "✅ Slowmode disabled"
            else:
                msg = f"✅ Slowmode set to {format_timespan(seconds)}"

            await interaction.followup.send(msg)

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Missing permissions to change slowmode",
                ephemeral=True
            )

    # ========================================================================
    # INFORMATION COMMANDS
    # ========================================================================

    @app_commands.command(name="warnings")
    @app_commands.describe(user="User to check warnings for")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warnings_command(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        """View all warnings for a user."""

        await interaction.response.defer(ephemeral=True)

        db = await get_db()
        warnings = await db.get_user_warnings(str(user.id), active_only=False)

        if not warnings:
            await interaction.followup.send(
                f"✅ {user.mention} has no warnings",
                ephemeral=True
            )
            return

        embed = create_embed(
            title=f"⚠️ Warnings - {user.display_name}",
            description=f"Total: {len(warnings)} warnings",
            color=discord.Color.orange()
        )

        # Show recent warnings
        for warning in warnings[:10]:
            issued_at = datetime.fromisoformat(warning['issued_at'])
            time_ago = datetime.now() - issued_at
            days_ago = time_ago.days

            status = "🟢 Active" if not warning.get('expires_at') or datetime.fromisoformat(warning['expires_at']) > datetime.now() else "⚫ Expired"

            embed.add_field(
                name=f"#{warning['warning_id']} - {warning['warning_type']} ({status})",
                value=f"**Reason:** {truncate_string(warning['reason'], 100)}\n**Issued:** {days_ago}d ago\n**Severity:** {warning['severity']}",
                inline=False
            )

        if len(warnings) > 10:
            embed.set_footer(text=f"Showing 10 of {len(warnings)} warnings")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="case")
    @app_commands.describe(case_id="Case ID to view")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def case_command(self, interaction: discord.Interaction, case_id: int):
        """View details of a specific case."""

        await interaction.response.defer(ephemeral=True)

        db = await get_db()
        case = await db.get_case(case_id)

        if not case:
            await interaction.followup.send(
                f"❌ Case #{case_id} not found",
                ephemeral=True
            )
            return

        # Get user
        try:
            user = await self.bot.fetch_user(int(case['user_id']))
            user_name = user.name
        except:
            user_name = f"Unknown ({case['user_id']})"

        # Get moderator
        try:
            mod = await self.bot.fetch_user(int(case['created_by']))
            mod_name = mod.name
        except:
            mod_name = f"Unknown ({case['created_by']})"

        embed = create_embed(
            title=f"📋 Case #{case_id}",
            description=f"**Type:** {case['case_type']}\n**Status:** {case['status']}",
            color=discord.Color.blue()
        )

        embed.add_field(name="User", value=user_name, inline=True)
        embed.add_field(name="Moderator", value=mod_name, inline=True)
        embed.add_field(name="Action", value=case['action_taken'] or "None", inline=True)
        embed.add_field(name="Reason", value=case['reason'], inline=False)

        created = datetime.fromisoformat(case['created_at'])
        embed.add_field(name="Created", value=created.strftime("%Y-%m-%d %H:%M"), inline=True)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="userinfo")
    @app_commands.describe(user="User to get info about")
    async def userinfo_command(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        """Get detailed information about a user."""

        await interaction.response.defer()

        embed = create_embed(
            title=f"👤 User Info - {user.display_name}",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        # Account info
        created_days = (datetime.now(user.created_at.tzinfo) - user.created_at).days
        joined_days = (datetime.now(user.joined_at.tzinfo) - user.joined_at).days if user.joined_at else 0

        embed.add_field(
            name="Account Created",
            value=f"{user.created_at.strftime('%Y-%m-%d')}\n({created_days} days ago)",
            inline=True
        )

        if user.joined_at:
            embed.add_field(
                name="Joined Server",
                value=f"{user.joined_at.strftime('%Y-%m-%d')}\n({joined_days} days ago)",
                inline=True
            )

        # Roles
        roles = [role.mention for role in user.roles if role.name != "@everyone"]
        embed.add_field(
            name=f"Roles ({len(roles)})",
            value=" ".join(roles[:10]) if roles else "None",
            inline=False
        )

        # Database info (if mod)
        if is_moderator(interaction.user):
            db = await get_db()
            user_data = await db.get_user(str(user.id))

            if user_data:
                embed.add_field(
                    name="Messages",
                    value=f"{user_data.get('total_messages', 0):,}",
                    inline=True
                )

                warnings = await db.get_warning_count(str(user.id))
                embed.add_field(
                    name="Warnings",
                    value=str(warnings),
                    inline=True
                )

        embed.add_field(name="User ID", value=user.id, inline=False)

        await interaction.followup.send(embed=embed)


# ============================================================================
# ERROR HANDLERS
# ============================================================================

async def setup(bot):
    """Load the cog."""
    await bot.add_cog(ModerationCommands(bot))
