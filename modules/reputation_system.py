"""
============================================================================
REPUTATION SYSTEM
============================================================================
Business-focused reputation tracking for professional communities.

Reputation Components:
1. Expertise Score - Knowledge sharing, helpful answers, quality content
2. Collaboration Score - Team participation, project involvement, networking
3. Consistency Score - Regular engagement, reliability, commitment
4. Leadership Score - Initiative, mentorship, community building

Each component is 0-100, combined into overall reputation.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
import discord

import config
from database import get_db


class ReputationSystem:
    """
    Calculate and manage user reputation scores.

    Reputation is different from Trust:
    - Trust = Can we trust this user not to spam/break rules?
    - Reputation = How valuable is this user to the community?
    """

    # ========================================================================
    # EXPERTISE SCORING
    # ========================================================================

    async def calculate_expertise_score(self, user_id: str) -> Dict:
        """
        Calculate expertise score based on:
        - Quality of messages (reaction ratio)
        - Helpful responses (messages with many reactions)
        - Resource sharing (links to helpful content)
        - Topic knowledge (consistent participation in specific channels)

        Returns:
            Dict with score and breakdown
        """
        db = await get_db()

        # Get user data
        user_data = await db.get_user(user_id)
        if not user_data:
            return {'score': 0, 'breakdown': {}}

        total_messages = user_data.get('total_messages', 0)
        reactions_received = user_data.get('total_reactions_received', 0)

        if total_messages == 0:
            return {'score': 0, 'breakdown': {}}

        # 1. Message Quality (reaction ratio)
        reaction_ratio = reactions_received / total_messages
        quality_score = min(100, (reaction_ratio / 0.3) * 40)  # 0.3 ratio = 40 points

        # 2. High-Value Messages (messages with 3+ reactions)
        high_value = await db.fetch_value(
            """
            SELECT COUNT(DISTINCT mh.message_id)
            FROM message_history mh
            WHERE mh.user_id = ?
            AND (
                SELECT COUNT(*) FROM message_history mh2
                WHERE mh2.message_id = mh.message_id
            ) >= 3
            """,
            (user_id,)
        ) or 0

        high_value_score = min(30, (high_value / 20) * 30)  # 20 high-value messages = 30 points

        # 3. Consistent Channel Participation (expertise in specific topics)
        channel_diversity = await db.fetch_all(
            """
            SELECT channel_id, message_count
            FROM channel_activity
            WHERE user_id = ?
            ORDER BY message_count DESC
            LIMIT 3
            """,
            (user_id,)
        )

        # Score based on having expertise channels (focus > broad)
        if channel_diversity:
            top_channel_msgs = channel_diversity[0]['message_count']
            focus_score = min(30, (top_channel_msgs / total_messages) * 60)  # 50%+ in one channel = focused expert
        else:
            focus_score = 0

        # Overall expertise score
        expertise_score = quality_score + high_value_score + focus_score

        return {
            'score': min(100, expertise_score),
            'breakdown': {
                'message_quality': round(quality_score, 1),
                'high_value_messages': round(high_value_score, 1),
                'topic_focus': round(focus_score, 1),
                'reaction_ratio': round(reaction_ratio, 3),
                'high_value_count': high_value
            }
        }

    # ========================================================================
    # COLLABORATION SCORING
    # ========================================================================

    async def calculate_collaboration_score(self, user_id: str) -> Dict:
        """
        Calculate collaboration score based on:
        - Multi-channel participation
        - Interaction with different users
        - Voice channel participation
        - Team-oriented behavior

        Returns:
            Dict with score and breakdown
        """
        db = await get_db()

        user_data = await db.get_user(user_id)
        if not user_data:
            return {'score': 0, 'breakdown': {}}

        # 1. Channel Diversity (participating in multiple channels)
        channel_count = await db.fetch_value(
            "SELECT COUNT(DISTINCT channel_id) FROM channel_activity WHERE user_id = ? AND message_count > 5",
            (user_id,)
        ) or 0

        diversity_score = min(40, (channel_count / 5) * 40)  # 5+ channels = 40 points

        # 2. Voice Participation
        voice_time = user_data.get('total_voice_minutes', 0)
        voice_score = min(30, (voice_time / 300) * 30)  # 5 hours = 30 points

        # 3. Reactions Given (engaging with others)
        reactions_given = user_data.get('total_reactions_given', 0)
        engagement_score = min(30, (reactions_given / 100) * 30)  # 100 reactions = 30 points

        collaboration_score = diversity_score + voice_score + engagement_score

        return {
            'score': min(100, collaboration_score),
            'breakdown': {
                'channel_diversity': round(diversity_score, 1),
                'voice_participation': round(voice_score, 1),
                'engagement': round(engagement_score, 1),
                'channels_active': channel_count,
                'voice_hours': round(voice_time / 60, 1)
            }
        }

    # ========================================================================
    # CONSISTENCY SCORING
    # ========================================================================

    async def calculate_consistency_score(self, user_id: str) -> Dict:
        """
        Calculate consistency score based on:
        - Daily activity streak
        - Regular participation over time
        - Message frequency consistency
        - Long-term commitment

        Returns:
            Dict with score and breakdown
        """
        db = await get_db()

        # Get gamification data for streak
        gamif_data = await db.fetch_one(
            "SELECT * FROM gamification WHERE user_id = ?",
            (user_id,)
        )

        if not gamif_data:
            return {'score': 0, 'breakdown': {}}

        # 1. Current Streak
        current_streak = gamif_data.get('current_streak_days', 0)
        longest_streak = gamif_data.get('longest_streak_days', 0)

        streak_score = min(50, (current_streak / 30) * 50)  # 30-day streak = 50 points

        # 2. Longest Streak (commitment)
        commitment_score = min(30, (longest_streak / 60) * 30)  # 60-day best = 30 points

        # 3. Account Age in Server
        user_data = await db.get_user(user_id)
        if user_data and user_data.get('joined_server'):
            joined = datetime.fromisoformat(user_data['joined_server'])
            days_in_server = (datetime.now(joined.tzinfo) - joined).days
            tenure_score = min(20, (days_in_server / 90) * 20)  # 90 days = 20 points
        else:
            tenure_score = 0

        consistency_score = streak_score + commitment_score + tenure_score

        return {
            'score': min(100, consistency_score),
            'breakdown': {
                'current_streak': round(streak_score, 1),
                'commitment': round(commitment_score, 1),
                'tenure': round(tenure_score, 1),
                'streak_days': current_streak,
                'longest_streak': longest_streak
            }
        }

    # ========================================================================
    # LEADERSHIP SCORING
    # ========================================================================

    async def calculate_leadership_score(self, user_id: str) -> Dict:
        """
        Calculate leadership score based on:
        - Helping newcomers (replies to new members)
        - Taking initiative (starting conversations)
        - Community building (creating value)
        - Positive influence (high-quality consistent contributions)

        Returns:
            Dict with score and breakdown
        """
        db = await get_db()

        user_data = await db.get_user(user_id)
        if not user_data:
            return {'score': 0, 'breakdown': {}}

        total_messages = user_data.get('total_messages', 0)

        # 1. High Message Count (active leader)
        activity_score = min(40, (total_messages / 500) * 40)  # 500 messages = 40 points

        # 2. Positive Role Model (high trust + reputation)
        trust_data = await db.fetch_one(
            "SELECT overall_score FROM trust_scores WHERE user_id = ?",
            (user_id,)
        )

        if trust_data and trust_data.get('overall_score', 0) >= 80:
            role_model_score = 30
        elif trust_data and trust_data.get('overall_score', 0) >= 60:
            role_model_score = 20
        else:
            role_model_score = 0

        # 3. Achievement Count (demonstrates commitment)
        achievement_count = await db.fetch_value(
            "SELECT COUNT(*) FROM achievements WHERE user_id = ?",
            (user_id,)
        ) or 0

        achievement_score = min(30, (achievement_count / 5) * 30)  # 5 achievements = 30 points

        leadership_score = activity_score + role_model_score + achievement_score

        return {
            'score': min(100, leadership_score),
            'breakdown': {
                'activity_leadership': round(activity_score, 1),
                'role_model': round(role_model_score, 1),
                'achievements': round(achievement_score, 1),
                'achievement_count': achievement_count
            }
        }

    # ========================================================================
    # OVERALL REPUTATION
    # ========================================================================

    async def calculate_reputation(self, user: discord.Member) -> Dict:
        """
        Calculate complete reputation score for a user.

        Args:
            user: Discord Member object

        Returns:
            Dict with overall score and all components
        """
        user_id = str(user.id)

        # Calculate all components
        expertise = await self.calculate_expertise_score(user_id)
        collaboration = await self.calculate_collaboration_score(user_id)
        consistency = await self.calculate_consistency_score(user_id)
        leadership = await self.calculate_leadership_score(user_id)

        # Calculate weighted overall score
        overall = (
            expertise['score'] * config.REPUTATION_WEIGHTS['expertise'] +
            collaboration['score'] * config.REPUTATION_WEIGHTS['collaboration'] +
            consistency['score'] * config.REPUTATION_WEIGHTS['consistency'] +
            leadership['score'] * config.REPUTATION_WEIGHTS['leadership']
        )

        # Determine tier
        tier = self._get_reputation_tier(overall)

        # Save to database
        db = await get_db()
        await db.execute(
            """
            INSERT INTO reputation (
                user_id, overall_reputation,
                expertise_score, collaboration_score, consistency_score, leadership_score,
                reputation_tier, last_calculated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                overall_reputation = excluded.overall_reputation,
                expertise_score = excluded.expertise_score,
                collaboration_score = excluded.collaboration_score,
                consistency_score = excluded.consistency_score,
                leadership_score = excluded.leadership_score,
                reputation_tier = excluded.reputation_tier,
                last_calculated = CURRENT_TIMESTAMP
            """,
            (user_id, overall,
             expertise['score'], collaboration['score'],
             consistency['score'], leadership['score'],
             tier)
        )

        return {
            'overall_reputation': round(overall, 1),
            'reputation_tier': tier,
            'expertise': expertise,
            'collaboration': collaboration,
            'consistency': consistency,
            'leadership': leadership
        }

    def _get_reputation_tier(self, score: float) -> str:
        """Get reputation tier from score."""
        for tier, (min_score, max_score) in config.REPUTATION_TIERS.items():
            if min_score <= score < max_score:
                return tier
        return 'platinum'  # 100 score

    # ========================================================================
    # REPUTATION TRACKING
    # ========================================================================

    async def track_helpful_action(self, user_id: str, action_type: str):
        """
        Track helpful actions that boost reputation.

        Actions:
        - answered_question
        - shared_resource
        - helped_newcomer
        - started_discussion
        """
        db = await get_db()

        # Update metrics
        if action_type == 'answered_question':
            await db.execute(
                "UPDATE reputation SET questions_answered = questions_answered + 1 WHERE user_id = ?",
                (user_id,)
            )
        elif action_type == 'shared_resource':
            await db.execute(
                "UPDATE reputation SET resources_shared = resources_shared + 1 WHERE user_id = ?",
                (user_id,)
            )

    async def get_reputation_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get top users by reputation."""
        db = await get_db()

        return await db.fetch_all(
            """
            SELECT u.user_id, u.username, u.display_name, r.*
            FROM reputation r
            JOIN users u ON r.user_id = u.user_id
            ORDER BY r.overall_reputation DESC
            LIMIT ?
            """,
            (limit,)
        )

    async def get_reputation_by_tier(self, tier: str) -> List[Dict]:
        """Get all users in a specific reputation tier."""
        db = await get_db()

        return await db.fetch_all(
            """
            SELECT u.user_id, u.username, u.display_name, r.*
            FROM reputation r
            JOIN users u ON r.user_id = u.user_id
            WHERE r.reputation_tier = ?
            ORDER BY r.overall_reputation DESC
            """,
            (tier,)
        )


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

reputation_system: Optional[ReputationSystem] = None


def get_reputation_system() -> ReputationSystem:
    """Get global reputation system instance."""
    global reputation_system
    if reputation_system is None:
        reputation_system = ReputationSystem()
    return reputation_system
