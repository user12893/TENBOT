"""
============================================================================
ENHANCED GAMIFICATION COMMANDS
============================================================================
Commands for the enhanced gamification system including:
- Badges and badge progress
- Prestige system
- Milestones
- Category leaderboards
- Personal statistics

All commands integrate with modules.gamification_enhanced
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Literal
from datetime import datetime, timedelta

from modules import get_enhanced_gamification
from database import get_db
from utils.helpers import create_embed, format_timespan, create_progress_bar
import config


class GamificationCommands(commands.Cog):
    """Enhanced gamification commands for XP, badges, prestige, and leaderboards."""

    def __init__(self, bot):
        self.bot = bot
        self.gamification = get_enhanced_gamification()

    # ========================================================================
    # BADGE COMMANDS
    # ========================================================================

    @app_commands.command(
        name="badges",
        description="View earned badges and their rarity"
    )
    @app_commands.describe(user="User to check badges for (defaults to you)")
    async def badges_command(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """View all earned badges with rarity and categories."""
        target = user or interaction.user
        await interaction.response.defer()

        db = await get_db()

        # Get user's badges
        badges = await db.fetch_all(
            """
            SELECT badge_key, badge_name, badge_description, rarity, earned_at
            FROM user_badges
            WHERE user_id = ?
            ORDER BY
                CASE rarity
                    WHEN 'legendary' THEN 1
                    WHEN 'epic' THEN 2
                    WHEN 'rare' THEN 3
                    WHEN 'uncommon' THEN 4
                    WHEN 'common' THEN 5
                END,
                earned_at DESC
            """,
            (str(target.id),)
        )

        embed = create_embed(
            title=f"🏅 Badges - {target.display_name}",
            description=f"**{len(badges)}** badges earned"
        )

        if not badges:
            embed.add_field(
                name="No Badges Yet",
                value="Start participating to earn badges!",
                inline=False
            )
        else:
            # Group by rarity
            by_rarity = {
                'legendary': [],
                'epic': [],
                'rare': [],
                'uncommon': [],
                'common': []
            }

            for badge in badges:
                by_rarity[badge['rarity']].append(badge)

            # Display by rarity
            rarity_emoji = {
                'legendary': '✨',
                'epic': '💜',
                'rare': '💙',
                'uncommon': '💚',
                'common': '⚪'
            }

            for rarity in ['legendary', 'epic', 'rare', 'uncommon', 'common']:
                rarity_badges = by_rarity[rarity]
                if rarity_badges:
                    badge_list = '\n'.join([
                        f"{b['badge_name']} - *{b['badge_description']}*"
                        for b in rarity_badges
                    ])

                    embed.add_field(
                        name=f"{rarity_emoji[rarity]} {rarity.title()} ({len(rarity_badges)})",
                        value=badge_list,
                        inline=False
                    )

        # Add badge count breakdown
        total_possible = len(self.gamification.BADGES)
        completion = (len(badges) / total_possible) * 100

        embed.set_footer(
            text=f"Collection: {len(badges)}/{total_possible} ({completion:.0f}%) • "
                 f"View progress with /badge-progress"
        )

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="badge-progress",
        description="See your progress toward earning badges"
    )
    async def badge_progress_command(self, interaction: discord.Interaction):
        """Show progress toward unearned badges."""
        await interaction.response.defer()

        user_id = str(interaction.user.id)
        db = await get_db()

        # Get earned badges
        earned = await db.fetch_all(
            "SELECT badge_key FROM user_badges WHERE user_id = ?",
            (user_id,)
        )
        earned_keys = {row['badge_key'] for row in earned}

        # Get user data for progress calculation
        user_data = await db.get_user(user_id)
        gamif_data = await db.fetch_one(
            "SELECT * FROM gamification WHERE user_id = ?",
            (user_id,)
        )

        embed = create_embed(
            title=f"📊 Badge Progress - {interaction.user.display_name}",
            description="Your progress toward unearned badges"
        )

        # Group badges by category
        by_category = {}
        for key, badge in self.gamification.BADGES.items():
            if key not in earned_keys:  # Only show unearned
                category = badge['category']
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append((key, badge))

        # Calculate progress for some badges
        progress_info = await self._calculate_badge_progress(user_id, user_data, gamif_data)

        category_emoji = {
            'activity': '⚡',
            'contribution': '💎',
            'social': '🤝',
            'loyalty': '💖',
            'achievement': '🏆',
            'special': '⭐'
        }

        for category, badges in by_category.items():
            if not badges:
                continue

            badge_text = []
            for key, badge in badges[:5]:  # Limit to 5 per category
                progress = progress_info.get(key, "")
                badge_text.append(
                    f"**{badge['name']}** ({badge['rarity']})\n"
                    f"*{badge['description']}*{progress}"
                )

            if badge_text:
                embed.add_field(
                    name=f"{category_emoji.get(category, '📌')} {category.title()}",
                    value='\n\n'.join(badge_text),
                    inline=False
                )

        total_earned = len(earned_keys)
        total_possible = len(self.gamification.BADGES)
        remaining = total_possible - total_earned

        embed.set_footer(
            text=f"{remaining} badges remaining • {total_earned}/{total_possible} earned"
        )

        await interaction.followup.send(embed=embed)

    async def _calculate_badge_progress(self, user_id: str, user_data: dict, gamif_data: dict) -> dict:
        """Calculate progress toward specific badges."""
        progress = {}

        if not user_data or not gamif_data:
            return progress

        # Message milestones
        messages = user_data.get('total_messages', 0)
        if messages < 100:
            progress['century_club'] = f"\n└ Progress: {messages}/100 messages"
        elif messages < 500:
            progress['message_master'] = f"\n└ Progress: {messages}/500 messages"
        elif messages < 1000:
            progress['chatterbox'] = f"\n└ Progress: {messages}/1000 messages"

        # Streak milestones
        streak = gamif_data.get('current_streak_days', 0)
        if streak < 7:
            progress['week_warrior'] = f"\n└ Progress: {streak}/7 days"
        elif streak < 30:
            progress['monthly_legend'] = f"\n└ Progress: {streak}/30 days"
        elif streak < 100:
            progress['unstoppable'] = f"\n└ Progress: {streak}/100 days"

        # Voice time
        voice_minutes = user_data.get('total_voice_minutes', 0)
        voice_hours = voice_minutes / 60
        if voice_hours < 10:
            progress['voice_champion'] = f"\n└ Progress: {voice_hours:.1f}/10 hours"
        elif voice_hours < 50:
            progress['voice_legend'] = f"\n└ Progress: {voice_hours:.1f}/50 hours"

        # Reactions
        reactions_given = user_data.get('total_reactions_given', 0)
        if reactions_given < 100:
            progress['super_supporter'] = f"\n└ Progress: {reactions_given}/100 reactions"

        return progress

    # ========================================================================
    # PRESTIGE SYSTEM
    # ========================================================================

    @app_commands.command(
        name="prestige",
        description="Reset to level 1 for an XP multiplier boost (requires level 50+)"
    )
    async def prestige_command(self, interaction: discord.Interaction):
        """Prestige: Reset level for XP multiplier."""
        await interaction.response.defer()

        user_id = str(interaction.user.id)
        db = await get_db()

        # Check current level
        gamif_data = await db.fetch_one(
            "SELECT * FROM gamification WHERE user_id = ?",
            (user_id,)
        )

        if not gamif_data:
            await interaction.followup.send("❌ No gamification data found!", ephemeral=True)
            return

        current_level = gamif_data['current_level']
        current_prestige = gamif_data.get('prestige_count', 0)

        if current_level < config.PRESTIGE_MIN_LEVEL:
            await interaction.followup.send(
                f"❌ You need level {config.PRESTIGE_MIN_LEVEL}+ to prestige!\n"
                f"Current level: {current_level}",
                ephemeral=True
            )
            return

        # Show confirmation
        new_prestige = current_prestige + 1
        new_multiplier = 1.0 + (new_prestige * config.PRESTIGE_MULTIPLIER_BONUS)

        embed = create_embed(
            title="✨ Prestige Confirmation",
            description=f"Are you sure you want to prestige?\n\n"
                       f"**Current Status:**\n"
                       f"└ Level: {current_level}\n"
                       f"└ Prestige: {current_prestige}\n"
                       f"└ XP Multiplier: {gamif_data.get('xp_multiplier', 1.0):.1f}x\n\n"
                       f"**After Prestige:**\n"
                       f"└ Level: 1 (reset)\n"
                       f"└ Prestige: {new_prestige}\n"
                       f"└ XP Multiplier: **{new_multiplier:.1f}x** (+{config.PRESTIGE_MULTIPLIER_BONUS:.1f}x)\n\n"
                       f"⚠️ This will reset your level and XP to 1, but you'll earn XP {new_multiplier:.1f}x faster!"
        )

        view = PrestigeConfirmView(user_id, self.gamification)
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(
        name="prestige-info",
        description="View prestige system information"
    )
    async def prestige_info_command(self, interaction: discord.Interaction):
        """Show prestige system details."""
        db = await get_db()

        # Get user's current prestige
        gamif_data = await db.fetch_one(
            "SELECT current_level, prestige_count, xp_multiplier FROM gamification WHERE user_id = ?",
            (str(interaction.user.id),)
        )

        embed = create_embed(
            title="✨ Prestige System",
            description=f"Reset to level 1 at level {config.PRESTIGE_MIN_LEVEL}+ to gain permanent XP multipliers!\n\n"
                       f"**How It Works:**\n"
                       f"• Reach level {config.PRESTIGE_MIN_LEVEL}+\n"
                       f"• Use `/prestige` to reset to level 1\n"
                       f"• Gain +{config.PRESTIGE_MULTIPLIER_BONUS:.1f}x XP multiplier per prestige\n"
                       f"• Multipliers stack infinitely!\n\n"
                       f"**Example:**\n"
                       f"• Prestige 1: 1.1x XP\n"
                       f"• Prestige 2: 1.2x XP\n"
                       f"• Prestige 5: 1.5x XP\n"
                       f"• Prestige 10: 2.0x XP"
        )

        if gamif_data:
            embed.add_field(
                name="Your Status",
                value=f"**Level:** {gamif_data['current_level']}\n"
                      f"**Prestige:** {gamif_data.get('prestige_count', 0)}\n"
                      f"**Multiplier:** {gamif_data.get('xp_multiplier', 1.0):.1f}x",
                inline=False
            )

            if gamif_data['current_level'] >= config.PRESTIGE_MIN_LEVEL:
                embed.add_field(
                    name="✅ Prestige Available!",
                    value=f"You can prestige now with `/prestige`",
                    inline=False
                )
            else:
                needed = config.PRESTIGE_MIN_LEVEL - gamif_data['current_level']
                embed.add_field(
                    name="Next Prestige",
                    value=f"{needed} more levels to go!",
                    inline=False
                )

        # Get top prestige users
        top_prestige = await db.fetch_all(
            """
            SELECT u.username, g.prestige_count, g.xp_multiplier, g.current_level
            FROM gamification g
            JOIN users u ON g.user_id = u.user_id
            WHERE g.prestige_count > 0
            ORDER BY g.prestige_count DESC
            LIMIT 5
            """, ()
        )

        if top_prestige:
            leaderboard = '\n'.join([
                f"{i+1}. **{row['username']}** - Prestige {row['prestige_count']} ({row['xp_multiplier']:.1f}x) - Lvl {row['current_level']}"
                for i, row in enumerate(top_prestige)
            ])
            embed.add_field(
                name="🏆 Top Prestige Users",
                value=leaderboard,
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    # ========================================================================
    # MILESTONE COMMANDS
    # ========================================================================

    @app_commands.command(
        name="milestones",
        description="View achieved milestones and rewards"
    )
    @app_commands.describe(user="User to check milestones for (defaults to you)")
    async def milestones_command(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """View all achieved milestones."""
        target = user or interaction.user
        await interaction.response.defer()

        db = await get_db()

        # Get milestones
        milestones = await db.fetch_all(
            """
            SELECT milestone_type, milestone_value, reward_xp, achieved_at
            FROM milestones
            WHERE user_id = ?
            ORDER BY achieved_at DESC
            """,
            (str(target.id),)
        )

        embed = create_embed(
            title=f"🎯 Milestones - {target.display_name}",
            description=f"**{len(milestones)}** milestones achieved"
        )

        if not milestones:
            embed.add_field(
                name="No Milestones Yet",
                value="Start being active to unlock milestones!",
                inline=False
            )
        else:
            # Group by type
            by_type = {}
            for m in milestones:
                mtype = m['milestone_type']
                if mtype not in by_type:
                    by_type[mtype] = []
                by_type[mtype].append(m)

            type_emoji = {
                'messages': '💬',
                'xp': '⭐',
                'voice_minutes': '🎤',
                'reactions_given': '❤️',
                'streak_days': '🔥'
            }

            type_names = {
                'messages': 'Messages Sent',
                'xp': 'Total XP Earned',
                'voice_minutes': 'Voice Time (minutes)',
                'reactions_given': 'Reactions Given',
                'streak_days': 'Activity Streak'
            }

            for mtype, type_milestones in by_type.items():
                milestone_list = '\n'.join([
                    f"**{m['milestone_value']:,}** {type_names.get(mtype, mtype)} "
                    f"(+{m['reward_xp']} XP) - {m['achieved_at'][:10]}"
                    for m in type_milestones[:5]  # Show last 5 per type
                ])

                embed.add_field(
                    name=f"{type_emoji.get(mtype, '📌')} {type_names.get(mtype, mtype.title())}",
                    value=milestone_list,
                    inline=False
                )

        # Total XP from milestones
        total_milestone_xp = sum(m['reward_xp'] for m in milestones)
        embed.set_footer(
            text=f"Total bonus XP from milestones: {total_milestone_xp:,}"
        )

        await interaction.followup.send(embed=embed)

    # ========================================================================
    # LEADERBOARD COMMANDS
    # ========================================================================

    @app_commands.command(
        name="leaderboard",
        description="View category-specific leaderboards"
    )
    @app_commands.describe(
        category="Leaderboard category",
        limit="Number of users to show (default 10)"
    )
    async def leaderboard_command(
        self,
        interaction: discord.Interaction,
        category: Literal["xp", "messages", "reactions", "voice", "streak", "badges", "reputation"],
        limit: Optional[int] = 10
    ):
        """Category-specific leaderboards."""
        await interaction.response.defer()

        limit = min(max(limit, 5), 25)  # Clamp between 5-25

        leaderboard = await self.gamification.get_category_leaderboard(category, limit)

        category_info = {
            'xp': ('⭐', 'Total XP', 'total_xp'),
            'messages': ('💬', 'Messages Sent', 'total_messages'),
            'reactions': ('❤️', 'Reactions Given', 'total_reactions_given'),
            'voice': ('🎤', 'Voice Time', 'total_voice_minutes'),
            'streak': ('🔥', 'Activity Streak', 'current_streak_days'),
            'badges': ('🏅', 'Badges Earned', 'badge_count'),
            'reputation': ('🏆', 'Reputation Score', 'overall_reputation')
        }

        emoji, title, field = category_info.get(category, ('📊', category.title(), category))

        embed = create_embed(
            title=f"{emoji} {title} Leaderboard",
            description=f"Top {len(leaderboard)} users"
        )

        if not leaderboard:
            embed.add_field(
                name="No Data",
                value="No leaderboard data available yet!",
                inline=False
            )
        else:
            # Medal emojis for top 3
            medals = ['🥇', '🥈', '🥉']

            leaderboard_text = []
            for i, row in enumerate(leaderboard):
                rank = i + 1
                medal = medals[i] if i < 3 else f"`{rank}.`"

                username = row.get('username') or row.get('display_name', 'Unknown')
                value = row.get(field, 0)

                # Format value based on category
                if category == 'voice':
                    hours = value / 60
                    value_str = f"{hours:.1f} hours"
                elif category == 'reputation':
                    value_str = f"{value:.1f}/100"
                elif category in ['xp', 'messages', 'reactions']:
                    value_str = f"{value:,}"
                else:
                    value_str = str(value)

                # Check if current user
                is_current = row.get('user_id') == str(interaction.user.id)
                username_display = f"**{username}**" if is_current else username

                leaderboard_text.append(
                    f"{medal} {username_display} - {value_str}"
                )

            embed.add_field(
                name="Rankings",
                value='\n'.join(leaderboard_text),
                inline=False
            )

            # Show current user's rank if not in top
            user_in_top = any(row.get('user_id') == str(interaction.user.id) for row in leaderboard)
            if not user_in_top:
                # Get user's rank
                user_rank = await self._get_user_rank(str(interaction.user.id), category)
                if user_rank:
                    embed.set_footer(
                        text=f"Your rank: #{user_rank['rank']} with {user_rank['value']}"
                    )

        await interaction.followup.send(embed=embed)

    async def _get_user_rank(self, user_id: str, category: str) -> Optional[dict]:
        """Get user's rank in a specific category."""
        db = await get_db()

        category_queries = {
            'xp': ("SELECT user_id, total_xp as value FROM gamification ORDER BY total_xp DESC", 'total_xp'),
            'messages': ("SELECT user_id, total_messages as value FROM users ORDER BY total_messages DESC", 'total_messages'),
            'reactions': ("SELECT user_id, total_reactions_given as value FROM users ORDER BY total_reactions_given DESC", 'total_reactions_given'),
            'voice': ("SELECT user_id, total_voice_minutes as value FROM users ORDER BY total_voice_minutes DESC", 'total_voice_minutes'),
            'streak': ("SELECT user_id, current_streak_days as value FROM gamification ORDER BY current_streak_days DESC", 'current_streak_days'),
            'badges': ("SELECT user_id, COUNT(*) as value FROM user_badges GROUP BY user_id ORDER BY value DESC", 'badge_count'),
            'reputation': ("SELECT user_id, overall_reputation as value FROM reputation ORDER BY overall_reputation DESC", 'overall_reputation')
        }

        if category not in category_queries:
            return None

        query, field = category_queries[category]
        all_users = await db.fetch_all(query, ())

        for rank, row in enumerate(all_users, 1):
            if row['user_id'] == user_id:
                return {'rank': rank, 'value': row['value']}

        return None

    # ========================================================================
    # PERSONAL STATS
    # ========================================================================

    @app_commands.command(
        name="my-stats",
        description="View your comprehensive gamification statistics"
    )
    async def my_stats_command(self, interaction: discord.Interaction):
        """Comprehensive personal statistics dashboard."""
        await interaction.response.defer()

        user_id = str(interaction.user.id)
        db = await get_db()

        # Get all user data
        user_data = await db.get_user(user_id)
        gamif_data = await db.fetch_one(
            "SELECT * FROM gamification WHERE user_id = ?",
            (user_id,)
        )

        if not user_data or not gamif_data:
            await interaction.followup.send("❌ No stats found!", ephemeral=True)
            return

        embed = create_embed(
            title=f"📊 Personal Stats - {interaction.user.display_name}",
            description="Your complete gamification statistics"
        )

        # Level & XP
        current_level = gamif_data['current_level']
        total_xp = gamif_data['total_xp']
        xp_for_next = (current_level + 1) * config.XP_PER_LEVEL
        xp_progress = total_xp - (current_level * config.XP_PER_LEVEL)
        xp_needed = xp_for_next - total_xp

        level_bar = create_progress_bar(xp_progress, config.XP_PER_LEVEL, 10)

        embed.add_field(
            name="⭐ Level & XP",
            value=f"**Level:** {current_level}\n"
                  f"**Total XP:** {total_xp:,}\n"
                  f"**Progress:** {level_bar} {xp_progress}/{config.XP_PER_LEVEL}\n"
                  f"**Next Level:** {xp_needed} XP needed",
            inline=False
        )

        # Prestige
        prestige_count = gamif_data.get('prestige_count', 0)
        xp_multiplier = gamif_data.get('xp_multiplier', 1.0)

        if prestige_count > 0:
            embed.add_field(
                name="✨ Prestige",
                value=f"**Prestige Level:** {prestige_count}\n"
                      f"**XP Multiplier:** {xp_multiplier:.1f}x",
                inline=True
            )

        # Activity Stats
        embed.add_field(
            name="💬 Activity",
            value=f"**Messages:** {user_data.get('total_messages', 0):,}\n"
                  f"**Reactions Given:** {user_data.get('total_reactions_given', 0):,}\n"
                  f"**Reactions Received:** {user_data.get('total_reactions_received', 0):,}\n"
                  f"**Voice Time:** {user_data.get('total_voice_minutes', 0)/60:.1f} hours",
            inline=True
        )

        # Streaks
        current_streak = gamif_data.get('current_streak_days', 0)
        longest_streak = gamif_data.get('longest_streak_days', 0)

        embed.add_field(
            name="🔥 Streaks",
            value=f"**Current:** {current_streak} days\n"
                  f"**Longest:** {longest_streak} days",
            inline=True
        )

        # Badges
        badge_count = await db.fetch_value(
            "SELECT COUNT(*) FROM user_badges WHERE user_id = ?",
            (user_id,)
        ) or 0

        total_badges = len(self.gamification.BADGES)
        badge_completion = (badge_count / total_badges) * 100

        embed.add_field(
            name="🏅 Badges",
            value=f"**Earned:** {badge_count}/{total_badges}\n"
                  f"**Completion:** {badge_completion:.0f}%",
            inline=True
        )

        # Achievements
        achievement_count = await db.fetch_value(
            "SELECT COUNT(*) FROM achievements WHERE user_id = ?",
            (user_id,)
        ) or 0

        embed.add_field(
            name="🏆 Achievements",
            value=f"**Unlocked:** {achievement_count}",
            inline=True
        )

        # Milestones
        milestone_count = await db.fetch_value(
            "SELECT COUNT(*) FROM milestones WHERE user_id = ?",
            (user_id,)
        ) or 0

        milestone_xp = await db.fetch_value(
            "SELECT SUM(reward_xp) FROM milestones WHERE user_id = ?",
            (user_id,)
        ) or 0

        embed.add_field(
            name="🎯 Milestones",
            value=f"**Achieved:** {milestone_count}\n"
                  f"**Bonus XP:** {milestone_xp:,}",
            inline=True
        )

        # Rankings
        xp_rank = await self._get_user_rank(user_id, 'xp')
        msg_rank = await self._get_user_rank(user_id, 'messages')

        if xp_rank and msg_rank:
            embed.add_field(
                name="📈 Rankings",
                value=f"**XP Rank:** #{xp_rank['rank']}\n"
                      f"**Message Rank:** #{msg_rank['rank']}",
                inline=False
            )

        # Member since
        if user_data.get('first_seen'):
            days_active = (datetime.now() - datetime.fromisoformat(user_data['first_seen'])).days
            embed.set_footer(
                text=f"Member for {days_active} days • Use /badges, /milestones for more details"
            )

        await interaction.followup.send(embed=embed)


# ============================================================================
# CONFIRMATION VIEWS
# ============================================================================

class PrestigeConfirmView(discord.ui.View):
    """Confirmation view for prestige action."""

    def __init__(self, user_id: str, gamification):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.gamification = gamification

    @discord.ui.button(label="✨ Prestige Now", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm prestige."""
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This isn't your prestige confirmation!", ephemeral=True)
            return

        await interaction.response.defer()

        # Execute prestige
        result = await self.gamification.prestige(self.user_id)

        if result.get('error'):
            await interaction.followup.send(f"❌ {result['error']}", ephemeral=True)
            return

        embed = create_embed(
            title="✨ Prestige Complete!",
            description=f"Congratulations! You've prestiged!\n\n"
                       f"**New Stats:**\n"
                       f"└ Level: 1 (reset)\n"
                       f"└ Prestige: {result['prestige_count']}\n"
                       f"└ XP Multiplier: **{result['xp_multiplier']:.1f}x**\n\n"
                       f"You now earn XP {result['xp_multiplier']:.1f}x faster!"
        )

        # Disable buttons
        for item in self.children:
            item.disabled = True

        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel prestige."""
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This isn't your prestige confirmation!", ephemeral=True)
            return

        # Disable buttons
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content="❌ Prestige cancelled.",
            view=self
        )


async def setup(bot):
    """Load the cog."""
    await bot.add_cog(GamificationCommands(bot))
