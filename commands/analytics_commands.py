"""
============================================================================
ANALYTICS & REPUTATION COMMANDS
============================================================================
Commands for the new analytics and reputation systems.

Commands included:
- Reputation: /reputation, /top-contributors, /expertise
- Analytics: /analytics, /channel-stats, /insights, /peak-hours
- User: /profile, /compare
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from database import get_db
from modules import get_reputation_system, get_analytics_system
from utils import create_embed, is_moderator


class AnalyticsReputationCommands(commands.Cog):
    """Analytics and reputation commands."""

    def __init__(self, bot):
        self.bot = bot
        self.reputation_system = get_reputation_system()
        self.analytics_system = get_analytics_system()

    # ========================================================================
    # REPUTATION COMMANDS
    # ========================================================================

    @app_commands.command(name="reputation")
    @app_commands.describe(user="User to check reputation for")
    async def reputation_command(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """View detailed reputation breakdown."""
        target = user or interaction.user
        await interaction.response.defer()

        # Calculate reputation
        rep_data = await self.reputation_system.calculate_reputation(target)

        # Create embed
        embed = create_embed(
            title=f"🏆 Reputation - {target.display_name}",
            color=self._get_tier_color(rep_data['reputation_tier'])
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        # Overall
        overall = rep_data['overall_reputation']
        tier = rep_data['reputation_tier'].title()

        embed.add_field(
            name="Overall Reputation",
            value=f"**{overall:.1f}/100** ({tier})",
            inline=False
        )

        # Component scores
        expertise = rep_data['expertise']
        collaboration = rep_data['collaboration']
        consistency = rep_data['consistency']
        leadership = rep_data['leadership']

        # Expertise
        embed.add_field(
            name="📚 Expertise",
            value=f"**{expertise['score']:.1f}/100**\n"
                  f"Quality: {expertise['breakdown']['message_quality']:.1f}\n"
                  f"High-value: {expertise['breakdown']['high_value_count']} msgs\n"
                  f"Focus: {expertise['breakdown']['topic_focus']:.1f}",
            inline=True
        )

        # Collaboration
        embed.add_field(
            name="🤝 Collaboration",
            value=f"**{collaboration['score']:.1f}/100**\n"
                  f"Channels: {collaboration['breakdown']['channels_active']}\n"
                  f"Voice: {collaboration['breakdown']['voice_hours']:.1f}h\n"
                  f"Engagement: {collaboration['breakdown']['engagement']:.1f}",
            inline=True
        )

        # Consistency
        embed.add_field(
            name="⏰ Consistency",
            value=f"**{consistency['score']:.1f}/100**\n"
                  f"Streak: {consistency['breakdown']['streak_days']} days\n"
                  f"Best: {consistency['breakdown']['longest_streak']} days\n"
                  f"Tenure: {consistency['breakdown']['tenure']:.1f}",
            inline=True
        )

        # Leadership
        embed.add_field(
            name="👑 Leadership",
            value=f"**{leadership['score']:.1f}/100**\n"
                  f"Activity: {leadership['breakdown']['activity_leadership']:.1f}\n"
                  f"Role Model: {leadership['breakdown']['role_model']:.1f}\n"
                  f"Achievements: {leadership['breakdown']['achievement_count']}",
            inline=True
        )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="top-contributors")
    @app_commands.describe(limit="Number of users to show")
    async def top_contributors_command(
        self,
        interaction: discord.Interaction,
        limit: int = 10
    ):
        """View top contributors by reputation."""
        await interaction.response.defer()

        top_users = await self.reputation_system.get_reputation_leaderboard(limit)

        embed = create_embed(
            title="🏆 Top Contributors",
            description=f"Top {limit} users by reputation",
            color=discord.Color.gold()
        )

        if not top_users:
            embed.description = "No reputation data yet!"
        else:
            for i, user_data in enumerate(top_users, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."

                tier = user_data['reputation_tier'].title()
                score = user_data['overall_reputation']

                embed.add_field(
                    name=f"{medal} {user_data['display_name']}",
                    value=f"**{score:.1f}/100** ({tier})\n"
                          f"Expertise: {user_data['expertise_score']:.0f} | "
                          f"Leadership: {user_data['leadership_score']:.0f}",
                    inline=False
                )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="expertise")
    @app_commands.describe(user="User to check expertise")
    async def expertise_command(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """View expertise score breakdown."""
        target = user or interaction.user
        await interaction.response.defer()

        user_id = str(target.id)
        expertise = await self.reputation_system.calculate_expertise_score(user_id)

        embed = create_embed(
            title=f"📚 Expertise - {target.display_name}",
            description=f"**Score: {expertise['score']:.1f}/100**",
            color=discord.Color.blue()
        )

        breakdown = expertise['breakdown']

        embed.add_field(
            name="Message Quality",
            value=f"{breakdown['message_quality']:.1f}/40\n"
                  f"Reaction ratio: {breakdown['reaction_ratio']:.3f}",
            inline=True
        )

        embed.add_field(
            name="High-Value Content",
            value=f"{breakdown['high_value_messages']:.1f}/30\n"
                  f"Messages with 3+ reactions: {breakdown['high_value_count']}",
            inline=True
        )

        embed.add_field(
            name="Topic Focus",
            value=f"{breakdown['topic_focus']:.1f}/30\n"
                  f"Specialized in specific channels",
            inline=True
        )

        await interaction.followup.send(embed=embed)

    # ========================================================================
    # ANALYTICS COMMANDS
    # ========================================================================

    @app_commands.command(name="analytics")
    async def analytics_command(self, interaction: discord.Interaction):
        """View server analytics dashboard."""

        if not is_moderator(interaction.user):
            await interaction.response.send_message(
                "❌ This command requires moderator permissions",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        # Get various metrics
        growth = await self.analytics_system.get_growth_metrics(30)
        quality = await self.analytics_system.get_content_quality_metrics()
        peak = await self.analytics_system.get_peak_hours(7)
        retention = await self.analytics_system.get_retention_rate(7)

        embed = create_embed(
            title="📊 Server Analytics",
            description="Last 30 days",
            color=discord.Color.blue()
        )

        # Growth metrics
        embed.add_field(
            name="📈 Growth",
            value=f"New users: {growth['new_users']}\n"
                  f"Active users: {growth['active_users']}\n"
                  f"Total users: {growth['total_users']}\n"
                  f"Activation: {growth['activation_rate']}%",
            inline=True
        )

        # Quality metrics
        embed.add_field(
            name="⭐ Content Quality",
            value=f"Total messages: {quality['total_messages_7d']:,}\n"
                  f"High-quality: {quality['high_quality_messages']}\n"
                  f"Quality rate: {quality['quality_rate']}%\n"
                  f"Avg reactions: {quality['avg_reaction_ratio']:.3f}",
            inline=True
        )

        # Engagement
        embed.add_field(
            name="🎯 Engagement",
            value=f"Peak hour: {peak['peak_hour']}:00\n"
                  f"Peak messages: {peak['peak_messages']}\n"
                  f"Peak users: {peak['peak_users']}\n"
                  f"Retention: {retention['retention_rate']}%",
            inline=True
        )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="channel-stats")
    @app_commands.describe(channel="Channel to analyze")
    async def channel_stats_command(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None
    ):
        """View statistics for a specific channel."""

        target_channel = channel or interaction.channel
        await interaction.response.defer()

        channel_id = str(target_channel.id)

        # Get channel stats
        stats = await self.analytics_system.get_channel_statistics(channel_id)
        growth = await self.analytics_system.get_channel_growth(channel_id, 30)
        engagement = await self.analytics_system.calculate_engagement_score(channel_id)

        embed = create_embed(
            title=f"📊 Channel Stats - #{target_channel.name}",
            color=discord.Color.blue()
        )

        # Basic stats
        embed.add_field(
            name="Activity",
            value=f"Messages: {stats.get('total_messages', 0):,}\n"
                  f"Users: {stats.get('unique_users', 0)}\n"
                  f"Avg per user: {stats.get('avg_messages_per_user', 0):.1f}",
            inline=True
        )

        # Growth
        embed.add_field(
            name="Growth (30d)",
            value=f"Trend: {growth.get('trend', 'unknown').title()}\n"
                  f"Growth rate: {growth.get('growth_rate', 0):.1f}%\n"
                  f"Avg/day: {growth.get('avg_messages_per_day', 0):.1f}",
            inline=True
        )

        # Engagement
        embed.add_field(
            name="Engagement",
            value=f"Score: {engagement:.1f}/100\n"
                  f"{'🟢 High' if engagement > 60 else '🟡 Medium' if engagement > 30 else '🔴 Low'}",
            inline=True
        )

        # Top users
        if stats.get('top_users'):
            top_users_text = "\n".join(
                f"{i}. <@{u['user_id']}>: {u['message_count']} msgs"
                for i, u in enumerate(stats['top_users'][:5], 1)
            )
            embed.add_field(
                name="Top Contributors",
                value=top_users_text,
                inline=False
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="insights")
    async def insights_command(self, interaction: discord.Interaction):
        """Get AI-generated insights about the server."""

        if not is_moderator(interaction.user):
            await interaction.response.send_message(
                "❌ This command requires moderator permissions",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        insights = await self.analytics_system.generate_insights()

        embed = create_embed(
            title="💡 Server Insights",
            description="Auto-generated insights from analytics",
            color=discord.Color.green()
        )

        for insight in insights:
            embed.add_field(
                name="📌",
                value=insight,
                inline=False
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="peak-hours")
    @app_commands.describe(days="Number of days to analyze")
    async def peak_hours_command(
        self,
        interaction: discord.Interaction,
        days: int = 7
    ):
        """View peak activity hours."""
        await interaction.response.defer()

        peak_data = await self.analytics_system.get_peak_hours(days)

        embed = create_embed(
            title=f"⏰ Peak Hours (Last {days} Days)",
            color=discord.Color.blue()
        )

        # Peak hour info
        embed.add_field(
            name="🔥 Peak Activity",
            value=f"Hour: {peak_data['peak_hour']}:00\n"
                  f"Messages: {peak_data['peak_messages']:,}\n"
                  f"Active users: {peak_data['peak_users']}",
            inline=False
        )

        # Create visual hourly breakdown
        hourly = peak_data['hourly_breakdown']

        # Group into time periods
        periods = {
            'Night (0-6)': sum(hourly[h]['messages'] for h in range(0, 6)),
            'Morning (6-12)': sum(hourly[h]['messages'] for h in range(6, 12)),
            'Afternoon (12-18)': sum(hourly[h]['messages'] for h in range(12, 18)),
            'Evening (18-24)': sum(hourly[h]['messages'] for h in range(18, 24))
        }

        period_text = "\n".join(
            f"{period}: {count:,} messages"
            for period, count in periods.items()
        )

        embed.add_field(
            name="Time Period Breakdown",
            value=period_text,
            inline=False
        )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="most-active-channels")
    @app_commands.describe(limit="Number of channels to show")
    async def most_active_channels_command(
        self,
        interaction: discord.Interaction,
        limit: int = 10
    ):
        """View most active channels."""
        await interaction.response.defer()

        channels = await self.analytics_system.get_most_active_channels(limit)

        embed = create_embed(
            title="🔥 Most Active Channels",
            description=f"Top {limit} by message count",
            color=discord.Color.orange()
        )

        for i, channel_data in enumerate(channels, 1):
            try:
                channel = self.bot.get_channel(int(channel_data['channel_id']))
                channel_name = f"#{channel.name}" if channel else "Unknown"
            except:
                channel_name = f"Channel {channel_data['channel_id']}"

            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."

            embed.add_field(
                name=f"{medal} {channel_name}",
                value=f"Messages: {channel_data['total_messages']:,}\n"
                      f"Users: {channel_data['unique_users']}\n"
                      f"Avg: {channel_data['avg_per_user']:.1f}/user",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    # ========================================================================
    # USER PROFILE COMMANDS
    # ========================================================================

    @app_commands.command(name="profile")
    @app_commands.describe(user="User to view profile")
    async def profile_command(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """View comprehensive user profile."""
        target = user or interaction.user
        await interaction.response.defer()

        db = await get_db()
        user_id = str(target.id)

        # Get all data
        profile = await db.get_user_profile(user_id)
        pattern = await self.analytics_system.get_user_activity_pattern(user_id)
        comparison = await self.analytics_system.get_user_comparison(user_id)

        if not profile:
            await interaction.followup.send("❌ No data found for this user")
            return

        embed = create_embed(
            title=f"👤 Profile - {target.display_name}",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        # Basic stats
        embed.add_field(
            name="📊 Activity",
            value=f"Messages: {profile.get('total_messages', 0):,}\n"
                  f"Reactions: {profile.get('total_reactions_received', 0):,}\n"
                  f"Voice: {profile.get('total_voice_minutes', 0):.0f}m",
            inline=True
        )

        # Gamification
        embed.add_field(
            name="🎮 Progress",
            value=f"Level: {profile.get('current_level', 1)}\n"
                  f"XP: {profile.get('total_xp', 0):,}\n"
                  f"Streak: {profile.get('current_streak_days', 0)}d",
            inline=True
        )

        # Reputation & Trust
        embed.add_field(
            name="🏆 Standing",
            value=f"Reputation: {profile.get('overall_reputation', 0):.0f}\n"
                  f"Trust: {profile.get('trust_score', 0):.0f}\n"
                  f"Tier: {profile.get('reputation_tier', 'bronze').title()}",
            inline=True
        )

        # Activity pattern
        if pattern.get('top_channels'):
            top_ch = pattern['top_channels'][0]
            try:
                channel = self.bot.get_channel(int(top_ch['channel_id']))
                channel_name = f"#{channel.name}" if channel else "Unknown"
            except:
                channel_name = "Unknown"

            embed.add_field(
                name="📈 Most Active In",
                value=f"{channel_name}\n{top_ch['message_count']} messages",
                inline=True
            )

        # Comparison
        if comparison:
            percentile = comparison.get('percentile_messages', 0)
            embed.add_field(
                name="📊 Ranking",
                value=f"Top {100-percentile:.0f}% in messages\n"
                      f"Server avg: {comparison.get('server_avg_messages', 0):.0f}",
                inline=True
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="compare")
    @app_commands.describe(user="User to compare yourself against")
    async def compare_command(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        """Compare yourself to another user."""
        await interaction.response.defer()

        db = await get_db()

        user1_id = str(interaction.user.id)
        user2_id = str(user.id)

        # Get profiles
        profile1 = await db.get_user_profile(user1_id)
        profile2 = await db.get_user_profile(user2_id)

        if not profile1 or not profile2:
            await interaction.followup.send("❌ Cannot compare - missing data")
            return

        embed = create_embed(
            title=f"⚖️ Comparison",
            description=f"{interaction.user.display_name} vs {user.display_name}",
            color=discord.Color.blue()
        )

        # Messages
        msgs1 = profile1.get('total_messages', 0)
        msgs2 = profile2.get('total_messages', 0)
        embed.add_field(
            name="📝 Messages",
            value=f"{interaction.user.display_name}: {msgs1:,}\n"
                  f"{user.display_name}: {msgs2:,}\n"
                  f"{'🥇 You lead!' if msgs1 > msgs2 else '🥈 They lead' if msgs2 > msgs1 else '🤝 Tied'}",
            inline=True
        )

        # Reputation
        rep1 = profile1.get('overall_reputation', 0)
        rep2 = profile2.get('overall_reputation', 0)
        embed.add_field(
            name="🏆 Reputation",
            value=f"{interaction.user.display_name}: {rep1:.0f}\n"
                  f"{user.display_name}: {rep2:.0f}\n"
                  f"{'🥇 You lead!' if rep1 > rep2 else '🥈 They lead' if rep2 > rep1 else '🤝 Tied'}",
            inline=True
        )

        # Level
        lvl1 = profile1.get('current_level', 1)
        lvl2 = profile2.get('current_level', 1)
        embed.add_field(
            name="⭐ Level",
            value=f"{interaction.user.display_name}: {lvl1}\n"
                  f"{user.display_name}: {lvl2}\n"
                  f"{'🥇 You lead!' if lvl1 > lvl2 else '🥈 They lead' if lvl2 > lvl1 else '🤝 Tied'}",
            inline=True
        )

        await interaction.followup.send(embed=embed)

    # ========================================================================
    # HELPERS
    # ========================================================================

    def _get_tier_color(self, tier: str) -> discord.Color:
        """Get color for reputation tier."""
        colors = {
            'bronze': discord.Color.from_rgb(205, 127, 50),
            'silver': discord.Color.from_rgb(192, 192, 192),
            'gold': discord.Color.gold(),
            'platinum': discord.Color.from_rgb(229, 228, 226)
        }
        return colors.get(tier, discord.Color.blue())


async def setup(bot):
    """Load the cog."""
    await bot.add_cog(AnalyticsReputationCommands(bot))
