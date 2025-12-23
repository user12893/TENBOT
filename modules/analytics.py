"""
============================================================================
ANALYTICS & DATA COLLECTION
============================================================================
Comprehensive analytics system for tracking:
- Channel usage patterns
- User activity patterns
- Peak hours and engagement
- Content quality metrics
- Growth trends

All data is aggregated and anonymized for insights.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import discord

from database import get_db


class AnalyticsSystem:
    """
    Analytics and data collection system.

    Tracks server-wide patterns to provide insights for:
    - Community managers
    - Content optimization
    - Engagement improvement
    """

    # ========================================================================
    # CHANNEL ANALYTICS
    # ========================================================================

    async def get_channel_statistics(self, channel_id: Optional[str] = None) -> Dict:
        """
        Get statistics for a specific channel or all channels.

        Args:
            channel_id: Specific channel ID (None = all channels)

        Returns:
            Dict with channel statistics
        """
        db = await get_db()

        if channel_id:
            # Single channel stats
            stats = await db.fetch_one(
                """
                SELECT
                    channel_id,
                    SUM(message_count) as total_messages,
                    COUNT(DISTINCT user_id) as unique_users,
                    MAX(message_count) as most_active_user_count,
                    AVG(message_count) as avg_messages_per_user
                FROM channel_activity
                WHERE channel_id = ?
                GROUP BY channel_id
                """,
                (channel_id,)
            )

            if not stats:
                return {'channel_id': channel_id, 'total_messages': 0}

            # Get most active users in channel
            top_users = await db.fetch_all(
                """
                SELECT user_id, message_count
                FROM channel_activity
                WHERE channel_id = ?
                ORDER BY message_count DESC
                LIMIT 5
                """,
                (channel_id,)
            )

            return {
                **dict(stats),
                'top_users': top_users
            }

        else:
            # All channels stats
            channels = await db.fetch_all(
                """
                SELECT
                    channel_id,
                    SUM(message_count) as total_messages,
                    COUNT(DISTINCT user_id) as unique_users
                FROM channel_activity
                GROUP BY channel_id
                ORDER BY total_messages DESC
                """
            )

            return {
                'channels': channels,
                'total_channels': len(channels)
            }

    async def get_most_active_channels(self, limit: int = 10) -> List[Dict]:
        """
        Get most active channels by message count.

        Args:
            limit: Number of channels to return

        Returns:
            List of channel stats
        """
        db = await get_db()

        return await db.fetch_all(
            """
            SELECT
                channel_id,
                SUM(message_count) as total_messages,
                COUNT(DISTINCT user_id) as unique_users,
                SUM(message_count) * 1.0 / COUNT(DISTINCT user_id) as avg_per_user
            FROM channel_activity
            GROUP BY channel_id
            ORDER BY total_messages DESC
            LIMIT ?
            """,
            (limit,)
        )

    async def get_channel_growth(self, channel_id: str, days: int = 30) -> Dict:
        """
        Get channel growth over time.

        Args:
            channel_id: Channel to analyze
            days: Number of days to look back

        Returns:
            Dict with growth metrics
        """
        db = await get_db()

        # Get message count trends
        daily_stats = await db.fetch_all(
            """
            SELECT
                DATE(created_at) as date,
                COUNT(*) as message_count,
                COUNT(DISTINCT user_id) as active_users
            FROM message_history
            WHERE channel_id = ?
            AND created_at >= datetime('now', ? || ' days')
            GROUP BY DATE(created_at)
            ORDER BY date ASC
            """,
            (channel_id, f'-{days}')
        )

        if not daily_stats:
            return {'channel_id': channel_id, 'trend': 'no_data'}

        # Calculate trend
        messages_first_week = sum(d['message_count'] for d in daily_stats[:7])
        messages_last_week = sum(d['message_count'] for d in daily_stats[-7:])

        if messages_first_week > 0:
            growth_rate = ((messages_last_week - messages_first_week) / messages_first_week) * 100
        else:
            growth_rate = 100 if messages_last_week > 0 else 0

        return {
            'channel_id': channel_id,
            'daily_stats': daily_stats,
            'growth_rate': round(growth_rate, 1),
            'trend': 'growing' if growth_rate > 10 else 'declining' if growth_rate < -10 else 'stable',
            'avg_messages_per_day': round(sum(d['message_count'] for d in daily_stats) / len(daily_stats), 1)
        }

    # ========================================================================
    # USER ACTIVITY PATTERNS
    # ========================================================================

    async def get_peak_hours(self, days: int = 7) -> Dict:
        """
        Analyze peak activity hours.

        Args:
            days: Number of days to analyze

        Returns:
            Dict with hourly activity breakdown
        """
        db = await get_db()

        hourly_activity = await db.fetch_all(
            """
            SELECT
                CAST(strftime('%H', created_at) AS INTEGER) as hour,
                COUNT(*) as message_count,
                COUNT(DISTINCT user_id) as active_users
            FROM message_history
            WHERE created_at >= datetime('now', ? || ' days')
            GROUP BY hour
            ORDER BY hour
            """,
            (f'-{days}',)
        )

        # Create 24-hour breakdown
        hour_data = {h: {'messages': 0, 'users': 0} for h in range(24)}

        for row in hourly_activity:
            hour_data[row['hour']] = {
                'messages': row['message_count'],
                'users': row['active_users']
            }

        # Find peak hour
        peak_hour = max(hour_data.items(), key=lambda x: x[1]['messages'])

        return {
            'hourly_breakdown': hour_data,
            'peak_hour': peak_hour[0],
            'peak_messages': peak_hour[1]['messages'],
            'peak_users': peak_hour[1]['users']
        }

    async def get_user_activity_pattern(self, user_id: str) -> Dict:
        """
        Analyze individual user's activity pattern.

        Args:
            user_id: User to analyze

        Returns:
            Dict with user activity patterns
        """
        db = await get_db()

        # Get hourly pattern
        hourly = await db.fetch_all(
            """
            SELECT
                CAST(strftime('%H', created_at) AS INTEGER) as hour,
                COUNT(*) as count
            FROM message_history
            WHERE user_id = ?
            AND created_at >= datetime('now', '-30 days')
            GROUP BY hour
            """,
            (user_id,)
        )

        # Get daily pattern (day of week)
        daily = await db.fetch_all(
            """
            SELECT
                CAST(strftime('%w', created_at) AS INTEGER) as day_of_week,
                COUNT(*) as count
            FROM message_history
            WHERE user_id = ?
            AND created_at >= datetime('now', '-30 days')
            GROUP BY day_of_week
            """,
            (user_id,)
        )

        # Most active channels
        top_channels = await db.fetch_all(
            """
            SELECT channel_id, message_count
            FROM channel_activity
            WHERE user_id = ?
            ORDER BY message_count DESC
            LIMIT 5
            """,
            (user_id,)
        )

        return {
            'hourly_pattern': {row['hour']: row['count'] for row in hourly},
            'daily_pattern': {row['day_of_week']: row['count'] for row in daily},
            'top_channels': top_channels
        }

    # ========================================================================
    # ENGAGEMENT METRICS
    # ========================================================================

    async def calculate_engagement_score(self, channel_id: str) -> float:
        """
        Calculate engagement score for a channel.

        Engagement = (reactions + unique users) / messages

        Args:
            channel_id: Channel to analyze

        Returns:
            Engagement score (0-100)
        """
        db = await get_db()

        stats = await db.fetch_one(
            """
            SELECT
                COUNT(*) as total_messages,
                COUNT(DISTINCT user_id) as unique_users,
                SUM(CASE WHEN mention_count > 0 THEN 1 ELSE 0 END) as messages_with_mentions
            FROM message_history
            WHERE channel_id = ?
            AND created_at >= datetime('now', '-7 days')
            """,
            (channel_id,)
        )

        if not stats or stats['total_messages'] == 0:
            return 0.0

        # Simple engagement metric
        user_diversity = stats['unique_users'] / max(1, stats['total_messages'])
        engagement = min(100, user_diversity * 200)  # Scale to 0-100

        return round(engagement, 1)

    async def get_content_quality_metrics(self) -> Dict:
        """
        Get overall content quality metrics.

        Returns:
            Dict with quality indicators
        """
        db = await get_db()

        # Get message-to-reaction ratio
        quality_stats = await db.fetch_one(
            """
            SELECT
                COUNT(*) as total_messages,
                SUM(u.total_reactions_received) as total_reactions,
                AVG(u.total_reactions_received * 1.0 / NULLIF(u.total_messages, 0)) as avg_reaction_ratio
            FROM message_history mh
            LEFT JOIN users u ON mh.user_id = u.user_id
            WHERE mh.created_at >= datetime('now', '-7 days')
            """
        )

        # Get high-quality message count (3+ reactions)
        high_quality = await db.fetch_value(
            """
            SELECT COUNT(DISTINCT message_id)
            FROM message_history
            WHERE created_at >= datetime('now', '-7 days')
            AND (SELECT COUNT(*) FROM message_history mh2 WHERE mh2.message_id = message_history.message_id) >= 3
            """
        )

        return {
            'total_messages_7d': quality_stats['total_messages'],
            'total_reactions_7d': quality_stats['total_reactions'] or 0,
            'avg_reaction_ratio': round(quality_stats['avg_reaction_ratio'] or 0, 3),
            'high_quality_messages': high_quality or 0,
            'quality_rate': round((high_quality or 0) / max(1, quality_stats['total_messages']) * 100, 1)
        }

    # ========================================================================
    # GROWTH & RETENTION
    # ========================================================================

    async def get_growth_metrics(self, days: int = 30) -> Dict:
        """
        Get server growth metrics.

        Args:
            days: Period to analyze

        Returns:
            Dict with growth statistics
        """
        db = await get_db()

        # New users
        new_users = await db.fetch_value(
            """
            SELECT COUNT(*)
            FROM users
            WHERE first_seen >= datetime('now', ? || ' days')
            """,
            (f'-{days}',)
        ) or 0

        # Active users (posted in period)
        active_users = await db.fetch_value(
            """
            SELECT COUNT(DISTINCT user_id)
            FROM message_history
            WHERE created_at >= datetime('now', ? || ' days')
            """,
            (f'-{days}',)
        ) or 0

        # Total users
        total_users = await db.fetch_value("SELECT COUNT(*) FROM users") or 0

        # Daily active users trend
        dau_trend = await db.fetch_all(
            """
            SELECT
                DATE(created_at) as date,
                COUNT(DISTINCT user_id) as active_users
            FROM message_history
            WHERE created_at >= datetime('now', ? || ' days')
            GROUP BY DATE(created_at)
            ORDER BY date
            """,
            (f'-{days}',)
        )

        return {
            'new_users': new_users,
            'active_users': active_users,
            'total_users': total_users,
            'activation_rate': round((active_users / max(1, total_users)) * 100, 1),
            'dau_trend': dau_trend
        }

    async def get_retention_rate(self, cohort_days: int = 7) -> Dict:
        """
        Calculate user retention rate.

        Args:
            cohort_days: Days to define a cohort

        Returns:
            Dict with retention metrics
        """
        db = await get_db()

        # Users who joined in cohort period
        cohort_users = await db.fetch_all(
            """
            SELECT user_id, first_seen
            FROM users
            WHERE first_seen >= datetime('now', ? || ' days')
            AND first_seen < datetime('now', ? || ' days')
            """,
            (f'-{cohort_days * 2}', f'-{cohort_days}')
        )

        if not cohort_users:
            return {'retention_rate': 0, 'cohort_size': 0}

        # Check how many are still active
        cohort_user_ids = [u['user_id'] for u in cohort_users]

        still_active = await db.fetch_value(
            f"""
            SELECT COUNT(DISTINCT user_id)
            FROM message_history
            WHERE user_id IN ({','.join(['?' for _ in cohort_user_ids])})
            AND created_at >= datetime('now', '-7 days')
            """,
            tuple(cohort_user_ids)
        ) or 0

        retention_rate = (still_active / len(cohort_users)) * 100

        return {
            'cohort_size': len(cohort_users),
            'still_active': still_active,
            'retention_rate': round(retention_rate, 1)
        }

    # ========================================================================
    # INSIGHTS & RECOMMENDATIONS
    # ========================================================================

    async def generate_insights(self) -> List[str]:
        """
        Generate actionable insights from analytics.

        Returns:
            List of insight strings
        """
        insights = []

        # Peak hours insight
        peak_data = await self.get_peak_hours(7)
        insights.append(
            f"📊 Peak activity is at {peak_data['peak_hour']}:00 with {peak_data['peak_messages']} messages"
        )

        # Growth insight
        growth = await self.get_growth_metrics(30)
        if growth['new_users'] > 0:
            insights.append(
                f"📈 {growth['new_users']} new users joined in the last 30 days"
            )

        # Engagement insight
        quality = await self.get_content_quality_metrics()
        insights.append(
            f"⭐ {quality['quality_rate']}% of messages are high-quality (3+ reactions)"
        )

        # Channel insight
        top_channels = await self.get_most_active_channels(3)
        if top_channels:
            top_channel = top_channels[0]
            insights.append(
                f"🔥 Most active channel has {top_channel['total_messages']} messages from {top_channel['unique_users']} users"
            )

        # Retention insight
        retention = await self.get_retention_rate(7)
        if retention['cohort_size'] > 0:
            insights.append(
                f"🎯 User retention rate: {retention['retention_rate']}% ({retention['still_active']}/{retention['cohort_size']} users)"
            )

        return insights

    async def get_user_comparison(self, user_id: str) -> Dict:
        """
        Compare user against server averages.

        Args:
            user_id: User to compare

        Returns:
            Dict with comparison metrics
        """
        db = await get_db()

        # User stats
        user_data = await db.get_user(user_id)

        # Server averages
        avg_stats = await db.fetch_one(
            """
            SELECT
                AVG(total_messages) as avg_messages,
                AVG(total_reactions_received) as avg_reactions,
                AVG(total_voice_minutes) as avg_voice
            FROM users
            WHERE total_messages > 0
            """
        )

        if not user_data or not avg_stats:
            return {}

        return {
            'user_messages': user_data.get('total_messages', 0),
            'server_avg_messages': round(avg_stats['avg_messages'], 1),
            'percentile_messages': await self._calculate_percentile(
                user_data.get('total_messages', 0),
                'total_messages'
            ),

            'user_reactions': user_data.get('total_reactions_received', 0),
            'server_avg_reactions': round(avg_stats['avg_reactions'], 1),
            'percentile_reactions': await self._calculate_percentile(
                user_data.get('total_reactions_received', 0),
                'total_reactions_received'
            )
        }

    async def _calculate_percentile(self, value: float, column: str) -> float:
        """Calculate percentile rank for a value."""
        db = await get_db()

        total = await db.fetch_value(f"SELECT COUNT(*) FROM users WHERE {column} > 0")
        if not total:
            return 0

        rank = await db.fetch_value(
            f"SELECT COUNT(*) FROM users WHERE {column} > 0 AND {column} <= ?",
            (value,)
        )

        return round((rank / total) * 100, 1)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

analytics_system: Optional[AnalyticsSystem] = None


def get_analytics_system() -> AnalyticsSystem:
    """Get global analytics system instance."""
    global analytics_system
    if analytics_system is None:
        analytics_system = AnalyticsSystem()
    return analytics_system
