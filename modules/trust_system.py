"""
============================================================================
TRUST SCORING SYSTEM
============================================================================
Multi-dimensional trust scoring for users based on:
- Account age (Discord account creation)
- Server age (how long in this server)
- Message count and quality
- Consistency (daily activity)
- Warning history (negative impact)
- Reputation from community

Trust scores help:
- Reduce false positives in spam detection
- Identify reliable members
- Make better moderation decisions
- Reward positive behavior
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import discord

import config
from database import get_db


class TrustSystem:
    """
    Calculate and manage user trust scores.

    Trust score is 0-100:
    - 0-20: New/untrusted
    - 20-40: Probation
    - 40-60: Regular member
    - 60-80: Trusted
    - 80-100: Highly trusted/vetted
    """

    # ========================================================================
    # TRUST CALCULATION
    # ========================================================================

    async def calculate_trust_score(self, user: discord.Member) -> Dict:
        """
        Calculate complete trust score for a user.

        Args:
            user: Discord Member object

        Returns:
            Dict with all trust components and overall score
        """
        db = await get_db()
        user_id = str(user.id)

        # Get user data from database
        user_data = await db.get_user(user_id)
        if not user_data:
            user_data = await db.create_user(user_id, user.name, user.display_name)

        gamification = await db.fetch_one(
            "SELECT * FROM gamification WHERE user_id = ?",
            (user_id,)
        )

        reputation = await db.fetch_one(
            "SELECT * FROM reputation WHERE user_id = ?",
            (user_id,)
        )

        # Calculate component scores
        scores = {}

        # 1. Account Age Score (0-100)
        scores['account_age'] = self._calculate_account_age_score(user.created_at)

        # 2. Server Age Score (0-100)
        scores['server_age'] = self._calculate_server_age_score(user.joined_at)

        # 3. Message Count Score (0-100)
        scores['message_count'] = self._calculate_message_count_score(
            user_data.get('total_messages', 0)
        )

        # 4. Message Quality Score (0-100)
        scores['message_quality'] = self._calculate_message_quality_score(
            user_data.get('total_messages', 0),
            user_data.get('total_reactions_received', 0)
        )

        # 5. Consistency Score (0-100)
        scores['consistency'] = self._calculate_consistency_score(
            gamification.get('current_streak_days', 0) if gamification else 0
        )

        # 6. Warning Penalty (negative score)
        scores['warning_penalty'] = await self._calculate_warning_penalty(user_id)

        # 7. Reputation Score (0-100)
        scores['reputation'] = self._calculate_reputation_score(
            reputation.get('overall_reputation', 0) if reputation else 0
        )

        # Calculate weighted overall score
        overall = self._calculate_weighted_score(scores)

        # Determine trust tier
        tier = self._get_trust_tier(overall)

        # Save to database
        await db.execute(
            """
            INSERT INTO trust_scores (
                user_id, overall_score,
                account_age_score, server_age_score, message_count_score,
                message_quality_score, consistency_score, warning_penalty,
                reputation_score, trust_tier, last_calculated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                overall_score = excluded.overall_score,
                account_age_score = excluded.account_age_score,
                server_age_score = excluded.server_age_score,
                message_count_score = excluded.message_count_score,
                message_quality_score = excluded.message_quality_score,
                consistency_score = excluded.consistency_score,
                warning_penalty = excluded.warning_penalty,
                reputation_score = excluded.reputation_score,
                trust_tier = excluded.trust_tier,
                last_calculated = CURRENT_TIMESTAMP
            """,
            (user_id, overall, scores['account_age'], scores['server_age'],
             scores['message_count'], scores['message_quality'], scores['consistency'],
             scores['warning_penalty'], scores['reputation'], tier)
        )

        return {
            'overall_score': overall,
            'trust_tier': tier,
            **scores
        }

    def _calculate_account_age_score(self, created_at: datetime) -> float:
        """
        Score based on Discord account age.

        - New accounts (< 1 month): 0-30
        - Medium age (1-6 months): 30-60
        - Old accounts (6+ months): 60-100
        """
        if not created_at:
            return 0

        days_old = (datetime.now(created_at.tzinfo) - created_at).days

        if days_old < 30:  # Less than 1 month
            return (days_old / 30) * 30  # 0-30 score
        elif days_old < 180:  # 1-6 months
            return 30 + ((days_old - 30) / 150) * 30  # 30-60 score
        else:  # 6+ months
            return min(100, 60 + ((days_old - 180) / 180) * 40)  # 60-100 score

    def _calculate_server_age_score(self, joined_at: Optional[datetime]) -> float:
        """
        Score based on how long user has been in this server.

        - New (< 7 days): 0-20
        - Recent (7-30 days): 20-50
        - Established (30+ days): 50-100
        """
        if not joined_at:
            return 0

        days_in_server = (datetime.now(joined_at.tzinfo) - joined_at).days

        if days_in_server < 7:  # Less than a week
            return (days_in_server / 7) * 20  # 0-20 score
        elif days_in_server < 30:  # 1-4 weeks
            return 20 + ((days_in_server - 7) / 23) * 30  # 20-50 score
        else:  # 1+ months
            return min(100, 50 + ((days_in_server - 30) / 60) * 50)  # 50-100 score

    def _calculate_message_count_score(self, message_count: int) -> float:
        """
        Score based on total messages sent.

        - Few messages (< 50): 0-30
        - Moderate (50-500): 30-70
        - Active (500+): 70-100
        """
        if message_count < 50:
            return (message_count / 50) * 30
        elif message_count < 500:
            return 30 + ((message_count - 50) / 450) * 40
        else:
            return min(100, 70 + ((message_count - 500) / 1000) * 30)

    def _calculate_message_quality_score(self, messages: int, reactions: int) -> float:
        """
        Score based on reaction-to-message ratio (quality indicator).

        High ratio = valuable messages that people appreciate
        """
        if messages == 0:
            return 0

        ratio = reactions / messages

        # Expected ratio for quality content: 0.2 (20% of messages get reactions)
        if ratio >= config.MIN_REACTIONS_RATIO:
            return min(100, (ratio / config.MIN_REACTIONS_RATIO) * 100)
        else:
            return (ratio / config.MIN_REACTIONS_RATIO) * 30  # Low quality gets max 30 points

    def _calculate_consistency_score(self, streak_days: int) -> float:
        """
        Score based on daily activity streak.

        - No streak: 0-20
        - Short streak (< 7 days): 20-50
        - Good streak (7-30 days): 50-80
        - Long streak (30+ days): 80-100
        """
        if streak_days < 7:
            return min(20, (streak_days / 7) * 20)
        elif streak_days < 30:
            return 20 + ((streak_days - 7) / 23) * 30
        else:
            return min(100, 50 + ((streak_days - 30) / 60) * 50)

    async def _calculate_warning_penalty(self, user_id: str) -> float:
        """
        Negative score based on warnings.

        Each active warning reduces trust significantly.
        Old warnings have reduced impact (decay over time).
        """
        db = await get_db()

        # Get all warnings
        warnings = await db.get_user_warnings(user_id, active_only=False)

        if not warnings:
            return 0

        total_penalty = 0

        for warning in warnings:
            # Base penalty per warning
            base_penalty = -15  # Each warning = -15 points

            # Severity multiplier
            severity = warning.get('severity', 'low')
            if severity == 'critical':
                base_penalty *= 3
            elif severity == 'high':
                base_penalty *= 2
            elif severity == 'medium':
                base_penalty *= 1.5

            # Time decay (warnings older than 30 days have reduced impact)
            issued_at = datetime.fromisoformat(warning['issued_at'])
            days_old = (datetime.now() - issued_at).days

            if days_old > config.WARNING_DECAY_DAYS:
                decay_factor = max(0.2, 1 - ((days_old - config.WARNING_DECAY_DAYS) / 60))
                base_penalty *= decay_factor

            total_penalty += base_penalty

        return max(-50, total_penalty)  # Cap at -50 points

    def _calculate_reputation_score(self, reputation: float) -> float:
        """
        Convert reputation (0-100) to trust score component.

        High reputation = high trust
        """
        return reputation

    def _calculate_weighted_score(self, scores: Dict[str, float]) -> float:
        """
        Calculate weighted overall trust score.

        Uses weights from config.TRUST_SCORE_WEIGHTS
        """
        overall = 0

        for component, weight in config.TRUST_SCORE_WEIGHTS.items():
            if component in scores:
                overall += scores[component] * abs(weight)

        # Clamp to 0-100
        return max(0, min(100, overall))

    def _get_trust_tier(self, score: float) -> str:
        """
        Get trust tier name from score.

        Args:
            score: Trust score (0-100)

        Returns:
            Tier name (new, probation, member, trusted, vetted)
        """
        for tier, (min_score, max_score) in config.TRUST_TIERS.items():
            if min_score <= score < max_score:
                return tier

        return 'vetted'  # 100 score

    # ========================================================================
    # TRUST CHECKS
    # ========================================================================

    async def is_trusted(self, user: discord.Member, min_tier: str = 'member') -> bool:
        """
        Check if user meets minimum trust level.

        Args:
            user: Discord Member
            min_tier: Minimum tier required (new, probation, member, trusted, vetted)

        Returns:
            True if user meets or exceeds trust level
        """
        db = await get_db()
        user_id = str(user.id)

        # Check for trusted roles (bypass)
        if any(role.name in config.TRUSTED_ROLE_NAMES for role in user.roles):
            return True

        # Get trust score from database
        trust_data = await db.fetch_one(
            "SELECT trust_tier, overall_score FROM trust_scores WHERE user_id = ?",
            (user_id,)
        )

        if not trust_data:
            # Calculate first time
            trust_data = await self.calculate_trust_score(user)

        current_tier = trust_data.get('trust_tier', 'new')

        # Get tier hierarchy
        tier_order = list(config.TRUST_TIERS.keys())

        try:
            current_index = tier_order.index(current_tier)
            required_index = tier_order.index(min_tier)
            return current_index >= required_index
        except ValueError:
            return False

    async def get_trust_score(self, user_id: str) -> Optional[Dict]:
        """
        Get cached trust score from database.

        Args:
            user_id: Discord user ID

        Returns:
            Trust score dict or None
        """
        db = await get_db()
        return await db.fetch_one(
            "SELECT * FROM trust_scores WHERE user_id = ?",
            (user_id,)
        )

    async def should_recalculate(self, user_id: str) -> bool:
        """
        Check if trust score needs recalculation.

        Recalculate if:
        - Never calculated before
        - Last calculation > 24 hours ago
        - User got a new warning
        """
        db = await get_db()

        trust_data = await self.get_trust_score(user_id)

        if not trust_data:
            return True

        # Check if last calculation was > 24 hours ago
        last_calc = datetime.fromisoformat(trust_data['last_calculated'])
        if datetime.now() - last_calc > timedelta(hours=24):
            return True

        return False

    # ========================================================================
    # BATCH OPERATIONS
    # ========================================================================

    async def recalculate_all_trust_scores(self, guild: discord.Guild):
        """
        Recalculate trust scores for all members.

        This should be run periodically (e.g., daily).

        Args:
            guild: Discord Guild object
        """
        print("🔄 Recalculating trust scores for all members...")

        count = 0
        for member in guild.members:
            if not member.bot:
                await self.calculate_trust_score(member)
                count += 1

        print(f"✅ Recalculated trust scores for {count} members")

    async def get_trust_leaderboard(self, limit: int = 10) -> List[Dict]:
        """
        Get users with highest trust scores.

        Args:
            limit: Number of users to return

        Returns:
            List of user trust data
        """
        db = await get_db()
        return await db.fetch_all(
            """
            SELECT u.user_id, u.username, u.display_name, t.*
            FROM trust_scores t
            JOIN users u ON t.user_id = u.user_id
            ORDER BY t.overall_score DESC
            LIMIT ?
            """,
            (limit,)
        )

    async def get_low_trust_users(self, threshold: int = 30) -> List[Dict]:
        """
        Get users with low trust scores (potential problems).

        Args:
            threshold: Maximum trust score to include

        Returns:
            List of low-trust users
        """
        db = await get_db()
        return await db.fetch_all(
            """
            SELECT u.user_id, u.username, u.display_name, t.*
            FROM trust_scores t
            JOIN users u ON t.user_id = u.user_id
            WHERE t.overall_score < ?
            ORDER BY t.overall_score ASC
            """,
            (threshold,)
        )


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

# Global trust system instance
trust_system: Optional[TrustSystem] = None


def get_trust_system() -> TrustSystem:
    """Get global trust system instance."""
    global trust_system
    if trust_system is None:
        trust_system = TrustSystem()
    return trust_system
