"""
============================================================================
ENHANCED GAMIFICATION SYSTEM
============================================================================
Advanced gamification features including:
- Badge system (achievement-like but more diverse)
- Prestige system (reset levels for bonuses)
- Milestone rewards
- Seasonal events
- Daily/weekly challenges

Extends the basic XP/level system with more engagement mechanics.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import discord

import config
from database import get_db


# ============================================================================
# BADGE DEFINITIONS
# ============================================================================

BADGES = {
    # Activity Badges
    'early_bird': {
        'name': '🌅 Early Bird',
        'description': 'Active before 6 AM',
        'category': 'activity',
        'rarity': 'common'
    },
    'night_owl': {
        'name': '🦉 Night Owl',
        'description': 'Active after midnight',
        'category': 'activity',
        'rarity': 'common'
    },
    'weekend_warrior': {
        'name': '⚔️ Weekend Warrior',
        'description': 'Most active on weekends',
        'category': 'activity',
        'rarity': 'uncommon'
    },

    # Contribution Badges
    'helpful_hand': {
        'name': '🤝 Helpful Hand',
        'description': 'Received 50+ reactions in a week',
        'category': 'contribution',
        'rarity': 'uncommon'
    },
    'conversation_starter': {
        'name': '💬 Conversation Starter',
        'description': 'Started 10 popular discussions',
        'category': 'contribution',
        'rarity': 'rare'
    },
    'resource_master': {
        'name': '📚 Resource Master',
        'description': 'Shared 20+ helpful links',
        'category': 'contribution',
        'rarity': 'rare'
    },

    # Social Badges
    'social_butterfly': {
        'name': '🦋 Social Butterfly',
        'description': 'Active in 10+ channels',
        'category': 'social',
        'rarity': 'uncommon'
    },
    'voice_champion': {
        'name': '🎤 Voice Champion',
        'description': '50+ hours in voice channels',
        'category': 'social',
        'rarity': 'rare'
    },

    # Loyalty Badges
    'founding_member': {
        'name': '🏛️ Founding Member',
        'description': 'Joined in first month',
        'category': 'loyalty',
        'rarity': 'legendary'
    },
    'one_year_club': {
        'name': '🎂 One Year Club',
        'description': 'Member for 365 days',
        'category': 'loyalty',
        'rarity': 'epic'
    },

    # Achievement Badges
    'speed_demon': {
        'name': '⚡ Speed Demon',
        'description': 'Reached level 10 in 7 days',
        'category': 'achievement',
        'rarity': 'epic'
    },
    'unstoppable': {
        'name': '🔥 Unstoppable',
        'description': '100-day streak',
        'category': 'achievement',
        'rarity': 'legendary'
    },

    # Special Badges
    'bug_hunter': {
        'name': '🐛 Bug Hunter',
        'description': 'Reported a bug that was fixed',
        'category': 'special',
        'rarity': 'rare'
    },
    'suggestion_master': {
        'name': '💡 Suggestion Master',
        'description': 'Suggestion was implemented',
        'category': 'special',
        'rarity': 'epic'
    }
}

# Rarity XP bonuses
RARITY_XP = {
    'common': 50,
    'uncommon': 100,
    'rare': 200,
    'epic': 500,
    'legendary': 1000
}


class EnhancedGamification:
    """
    Enhanced gamification features beyond basic XP/levels.
    """

    # ========================================================================
    # BADGE SYSTEM
    # ========================================================================

    async def check_badge_eligibility(self, user_id: str, user: discord.Member) -> List[str]:
        """
        Check which new badges user is eligible for.

        Args:
            user_id: User ID string
            user: Discord Member object

        Returns:
            List of newly earned badge keys
        """
        db = await get_db()
        newly_earned = []

        # Get user's current badges
        current_badges = await db.fetch_all(
            "SELECT badge_key FROM user_badges WHERE user_id = ?",
            (user_id,)
        )
        current_badge_keys = {b['badge_key'] for b in current_badges}

        # Get user data
        user_data = await db.get_user(user_id)
        gamif_data = await db.fetch_one(
            "SELECT * FROM gamification WHERE user_id = ?",
            (user_id,)
        )

        if not user_data or not gamif_data:
            return []

        # Check each badge
        for badge_key, badge_info in BADGES.items():
            if badge_key in current_badge_keys:
                continue  # Already have it

            # Check eligibility
            if await self._check_badge_condition(badge_key, user_id, user, user_data, gamif_data):
                newly_earned.append(badge_key)

        return newly_earned

    async def _check_badge_condition(
        self,
        badge_key: str,
        user_id: str,
        user: discord.Member,
        user_data: Dict,
        gamif_data: Dict
    ) -> bool:
        """Check if user meets conditions for a specific badge."""

        db = await get_db()

        # Activity badges
        if badge_key == 'early_bird':
            # Check if user has messages before 6 AM
            early_messages = await db.fetch_value(
                """
                SELECT COUNT(*)
                FROM message_history
                WHERE user_id = ?
                AND CAST(strftime('%H', created_at) AS INTEGER) < 6
                """,
                (user_id,)
            )
            return early_messages >= 10

        elif badge_key == 'night_owl':
            # Messages after midnight
            night_messages = await db.fetch_value(
                """
                SELECT COUNT(*)
                FROM message_history
                WHERE user_id = ?
                AND CAST(strftime('%H', created_at) AS INTEGER) >= 0
                AND CAST(strftime('%H', created_at) AS INTEGER) < 6
                """,
                (user_id,)
            )
            return night_messages >= 20

        elif badge_key == 'weekend_warrior':
            # Most active on weekends (Saturday=6, Sunday=0)
            weekend_msgs = await db.fetch_value(
                """
                SELECT COUNT(*)
                FROM message_history
                WHERE user_id = ?
                AND CAST(strftime('%w', created_at) AS INTEGER) IN (0, 6)
                """,
                (user_id,)
            )
            total_msgs = user_data.get('total_messages', 0)
            return total_msgs > 0 and (weekend_msgs / total_msgs) > 0.4

        # Contribution badges
        elif badge_key == 'helpful_hand':
            # 50+ reactions in a week
            recent_reactions = await db.fetch_value(
                """
                SELECT total_reactions_received
                FROM users
                WHERE user_id = ?
                AND last_seen >= datetime('now', '-7 days')
                """,
                (user_id,)
            )
            return (recent_reactions or 0) >= 50

        elif badge_key == 'conversation_starter':
            # Started 10 discussions with 5+ replies
            # (Approximated by messages with high engagement)
            return user_data.get('total_reactions_received', 0) >= 100

        # Social badges
        elif badge_key == 'social_butterfly':
            # Active in 10+ channels
            channel_count = await db.fetch_value(
                "SELECT COUNT(DISTINCT channel_id) FROM channel_activity WHERE user_id = ? AND message_count > 10",
                (user_id,)
            )
            return (channel_count or 0) >= 10

        elif badge_key == 'voice_champion':
            # 50+ hours voice
            return user_data.get('total_voice_minutes', 0) >= 3000

        # Loyalty badges
        elif badge_key == 'one_year_club':
            if user.joined_at:
                days_in_server = (datetime.now(user.joined_at.tzinfo) - user.joined_at).days
                return days_in_server >= 365
            return False

        # Achievement badges
        elif badge_key == 'unstoppable':
            return gamif_data.get('current_streak_days', 0) >= 100

        return False

    async def award_badge(self, user_id: str, badge_key: str) -> Dict:
        """
        Award a badge to a user.

        Args:
            user_id: User ID
            badge_key: Badge identifier

        Returns:
            Dict with badge info and XP awarded
        """
        db = await get_db()

        badge_info = BADGES.get(badge_key)
        if not badge_info:
            return {'success': False, 'reason': 'Invalid badge'}

        # Check if already has badge
        existing = await db.fetch_one(
            "SELECT * FROM user_badges WHERE user_id = ? AND badge_key = ?",
            (user_id, badge_key)
        )

        if existing:
            return {'success': False, 'reason': 'Already has badge'}

        # Award badge
        await db.execute(
            """
            INSERT INTO user_badges (user_id, badge_key, badge_name, badge_description, rarity, earned_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (user_id, badge_key, badge_info['name'], badge_info['description'], badge_info['rarity'])
        )

        # Award XP bonus
        xp_bonus = RARITY_XP.get(badge_info['rarity'], 0)

        await db.execute(
            "UPDATE gamification SET total_xp = total_xp + ?, total_xp_earned = total_xp_earned + ? WHERE user_id = ?",
            (xp_bonus, xp_bonus, user_id)
        )

        return {
            'success': True,
            'badge': badge_info,
            'xp_bonus': xp_bonus,
            'rarity': badge_info['rarity']
        }

    async def get_user_badges(self, user_id: str) -> List[Dict]:
        """Get all badges earned by user."""
        db = await get_db()

        return await db.fetch_all(
            "SELECT * FROM user_badges WHERE user_id = ? ORDER BY earned_at DESC",
            (user_id,)
        )

    # ========================================================================
    # PRESTIGE SYSTEM
    # ========================================================================

    async def prestige(self, user_id: str) -> Dict:
        """
        Reset user to level 1 but grant prestige bonuses.

        Args:
            user_id: User to prestige

        Returns:
            Dict with prestige result
        """
        db = await get_db()

        # Get current level
        gamif_data = await db.fetch_one(
            "SELECT * FROM gamification WHERE user_id = ?",
            (user_id,)
        )

        if not gamif_data:
            return {'success': False, 'reason': 'User not found'}

        current_level = gamif_data.get('current_level', 1)

        # Minimum level 50 to prestige
        if current_level < 50:
            return {'success': False, 'reason': 'Must be level 50+ to prestige'}

        # Calculate prestige bonuses
        prestige_count = gamif_data.get('prestige_count', 0) + 1
        xp_multiplier = 1.0 + (prestige_count * 0.1)  # +10% XP per prestige

        # Reset to level 1, keep achievements
        await db.execute(
            """
            UPDATE gamification
            SET current_level = 1,
                total_xp = 0,
                prestige_count = ?,
                xp_multiplier = ?,
                last_prestige_date = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (prestige_count, xp_multiplier, user_id)
        )

        # Award prestige badge
        await db.execute(
            """
            INSERT INTO user_badges (user_id, badge_key, badge_name, badge_description, rarity)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                f'prestige_{prestige_count}',
                f'⭐ Prestige {prestige_count}',
                f'Reset to level 1 {prestige_count} times',
                'legendary'
            )
        )

        return {
            'success': True,
            'prestige_count': prestige_count,
            'xp_multiplier': xp_multiplier,
            'bonus_xp_rate': f'+{int((xp_multiplier - 1) * 100)}%'
        }

    # ========================================================================
    # MILESTONES & REWARDS
    # ========================================================================

    async def check_milestones(self, user_id: str) -> List[Dict]:
        """
        Check for milestone achievements.

        Milestones are one-time rewards for reaching certain thresholds.

        Args:
            user_id: User to check

        Returns:
            List of newly reached milestones
        """
        db = await get_db()

        user_data = await db.get_user(user_id)
        gamif_data = await db.fetch_one("SELECT * FROM gamification WHERE user_id = ?", (user_id,))

        if not user_data or not gamif_data:
            return []

        milestones = []
        total_messages = user_data.get('total_messages', 0)
        total_xp = gamif_data.get('total_xp', 0)

        # Message milestones
        message_milestones = [100, 500, 1000, 5000, 10000]
        for milestone in message_milestones:
            if total_messages >= milestone:
                # Check if already awarded
                existing = await db.fetch_one(
                    "SELECT * FROM milestones WHERE user_id = ? AND milestone_type = ? AND milestone_value = ?",
                    (user_id, 'messages', milestone)
                )

                if not existing:
                    milestones.append({
                        'type': 'messages',
                        'value': milestone,
                        'reward_xp': milestone // 10,
                        'title': f'{milestone} Messages'
                    })

        # XP milestones
        xp_milestones = [1000, 5000, 10000, 50000, 100000]
        for milestone in xp_milestones:
            if total_xp >= milestone:
                existing = await db.fetch_one(
                    "SELECT * FROM milestones WHERE user_id = ? AND milestone_type = ? AND milestone_value = ?",
                    (user_id, 'xp', milestone)
                )

                if not existing:
                    milestones.append({
                        'type': 'xp',
                        'value': milestone,
                        'reward_xp': milestone // 20,
                        'title': f'{milestone:,} Total XP'
                    })

        return milestones

    async def award_milestone(self, user_id: str, milestone: Dict):
        """Award milestone to user."""
        db = await get_db()

        # Record milestone
        await db.execute(
            """
            INSERT INTO milestones (user_id, milestone_type, milestone_value, reward_xp, achieved_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (user_id, milestone['type'], milestone['value'], milestone['reward_xp'])
        )

        # Award XP
        await db.execute(
            "UPDATE gamification SET total_xp = total_xp + ? WHERE user_id = ?",
            (milestone['reward_xp'], user_id)
        )

    # ========================================================================
    # LEADERBOARD ENHANCEMENTS
    # ========================================================================

    async def get_category_leaderboard(self, category: str, limit: int = 10) -> List[Dict]:
        """
        Get leaderboard for specific category.

        Categories:
        - messages: Most messages
        - reactions: Most reactions received
        - voice: Most voice time
        - streak: Longest current streak
        - badges: Most badges

        Args:
            category: Category to rank by
            limit: Number of users

        Returns:
            List of top users in category
        """
        db = await get_db()

        if category == 'messages':
            return await db.fetch_all(
                """
                SELECT u.user_id, u.username, u.display_name, u.total_messages as value
                FROM users u
                ORDER BY u.total_messages DESC
                LIMIT ?
                """,
                (limit,)
            )

        elif category == 'reactions':
            return await db.fetch_all(
                """
                SELECT u.user_id, u.username, u.display_name, u.total_reactions_received as value
                FROM users u
                ORDER BY u.total_reactions_received DESC
                LIMIT ?
                """,
                (limit,)
            )

        elif category == 'voice':
            return await db.fetch_all(
                """
                SELECT u.user_id, u.username, u.display_name, u.total_voice_minutes as value
                FROM users u
                ORDER BY u.total_voice_minutes DESC
                LIMIT ?
                """,
                (limit,)
            )

        elif category == 'streak':
            return await db.fetch_all(
                """
                SELECT u.user_id, u.username, u.display_name, g.current_streak_days as value
                FROM users u
                JOIN gamification g ON u.user_id = g.user_id
                ORDER BY g.current_streak_days DESC
                LIMIT ?
                """,
                (limit,)
            )

        elif category == 'badges':
            return await db.fetch_all(
                """
                SELECT u.user_id, u.username, u.display_name, COUNT(b.badge_id) as value
                FROM users u
                LEFT JOIN user_badges b ON u.user_id = b.user_id
                GROUP BY u.user_id
                ORDER BY value DESC
                LIMIT ?
                """,
                (limit,)
            )

        return []


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

enhanced_gamification: Optional[EnhancedGamification] = None


def get_enhanced_gamification() -> EnhancedGamification:
    """Get global enhanced gamification instance."""
    global enhanced_gamification
    if enhanced_gamification is None:
        enhanced_gamification = EnhancedGamification()
    return enhanced_gamification
