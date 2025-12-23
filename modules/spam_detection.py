"""
============================================================================
SPAM DETECTION MODULE
============================================================================
Comprehensive spam detection with trust-aware thresholds.

Detection types:
- Rapid messaging (message flood)
- Duplicate messages
- Cross-channel spam
- Link spam with whitelist
- Mention spam
- Content analysis (caps, repeated chars)
- Scam pattern detection
- Image spam (uses image_detection module)

Integrates with:
- Trust system (trusted users get more lenient thresholds)
- Case management (creates cases for mod actions)
- Database (logs all detections)
"""

import re
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple, List
import discord

import config
from database import get_db
from .trust_system import get_trust_system


class SpamDetector:
    """
    Multi-layer spam detection system.

    Uses trust scores to adjust thresholds:
    - Low trust users: Strict detection
    - Trusted users: Lenient detection (avoid false positives)
    """

    def __init__(self):
        self.scam_patterns = [re.compile(p, re.IGNORECASE) for p in config.SCAM_PATTERNS]

    # ========================================================================
    # MAIN SPAM CHECK
    # ========================================================================

    async def check_message(
        self,
        message: discord.Message
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Comprehensive spam check for a message.

        Args:
            message: Discord Message object

        Returns:
            Tuple of (is_spam, spam_type, reason)
        """
        if message.author.bot:
            return False, None, None

        db = await get_db()
        trust_system = get_trust_system()
        user_id = str(message.author.id)

        # Get/create user
        user_data = await db.get_user(user_id)
        if not user_data:
            user_data = await db.create_user(user_id, message.author.name, message.author.display_name)

        # Get trust score
        trust_data = await trust_system.get_trust_score(user_id)
        is_trusted = trust_data and trust_data.get('overall_score', 0) >= 60

        # Calculate content hash for duplicate detection
        content_hash = self._hash_content(message.content)

        # Save message to history
        await db.add_message(
            message_id=str(message.id),
            user_id=user_id,
            channel_id=str(message.channel.id),
            content=message.content,
            content_hash=content_hash,
            has_attachments=len(message.attachments) > 0,
            attachment_count=len(message.attachments),
            mention_count=len(message.mentions)
        )

        # Run spam checks in order of severity

        # 1. Scam Pattern Detection (highest priority)
        is_scam, scam_reason = self._check_scam_patterns(message.content)
        if is_scam:
            return True, 'scam', f"Scam pattern detected: {scam_reason}"

        # 2. Link Spam (if links not allowed or not whitelisted)
        is_link_spam, link_reason = await self._check_link_spam(message, is_trusted)
        if is_link_spam:
            return True, 'link_spam', link_reason

        # 3. Mention Spam
        if len(message.mentions) > config.MAX_MENTIONS_PER_MESSAGE:
            return True, 'mention_spam', f"Excessive mentions ({len(message.mentions)})"

        # 4. Content Analysis (caps, repeated chars)
        is_spam_content, content_reason = self._check_content_spam(message.content)
        if is_spam_content and not is_trusted:
            return True, 'content_spam', content_reason

        # 5. Rapid Messaging
        is_rapid, rapid_reason = await self._check_rapid_messaging(user_id, is_trusted)
        if is_rapid:
            return True, 'rapid_messaging', rapid_reason

        # 6. Duplicate Messages
        is_duplicate, dup_reason = await self._check_duplicate_messages(user_id, content_hash, is_trusted)
        if is_duplicate:
            return True, 'duplicate', dup_reason

        # 7. Cross-Channel Spam
        is_cross, cross_reason = await self._check_cross_channel_spam(
            user_id,
            str(message.channel.id),
            content_hash,
            is_trusted
        )
        if is_cross:
            return True, 'cross_channel', cross_reason

        # Not spam
        return False, None, None

    # ========================================================================
    # DETECTION METHODS
    # ========================================================================

    def _check_scam_patterns(self, content: str) -> Tuple[bool, Optional[str]]:
        """
        Check for known scam patterns using regex.

        Args:
            content: Message content

        Returns:
            Tuple of (is_scam, matched_pattern)
        """
        for pattern in self.scam_patterns:
            if pattern.search(content):
                return True, pattern.pattern

        return False, None

    async def _check_link_spam(
        self,
        message: discord.Message,
        is_trusted: bool
    ) -> Tuple[bool, Optional[str]]:
        """
        Check for unauthorized links.

        Args:
            message: Discord Message
            is_trusted: Whether user is trusted

        Returns:
            Tuple of (is_spam, reason)
        """
        if not config.ALLOW_LINKS and not is_trusted:
            # Check if message contains URLs
            url_pattern = re.compile(r'https?://\S+', re.IGNORECASE)
            if url_pattern.search(message.content):
                return True, "Links not allowed"

        # Check for Discord invites
        if config.BLOCK_ALL_INVITES:
            invite_pattern = re.compile(r'discord\.gg/\S+|discord\.com/invite/\S+', re.IGNORECASE)
            match = invite_pattern.search(message.content)

            if match:
                invite_url = match.group()

                # Check whitelist
                if not any(allowed in invite_url for allowed in config.LINK_WHITELIST):
                    return True, "Unauthorized Discord invite"

        # Check general whitelist
        url_pattern = re.compile(r'https?://([^/\s]+)', re.IGNORECASE)
        matches = url_pattern.findall(message.content)

        for domain in matches:
            # Check if domain is whitelisted
            is_whitelisted = any(
                allowed_domain in domain
                for allowed_domain in config.LINK_WHITELIST
            )

            if not is_whitelisted and not is_trusted:
                return True, f"Non-whitelisted link: {domain}"

        return False, None

    def _check_content_spam(self, content: str) -> Tuple[bool, Optional[str]]:
        """
        Analyze message content for spam indicators.

        Args:
            content: Message content

        Returns:
            Tuple of (is_spam, reason)
        """
        if len(content) == 0:
            return False, None

        # Check excessive caps
        if len(content) >= 20:
            caps_count = sum(1 for c in content if c.isupper())
            caps_ratio = caps_count / len(content)

            if caps_ratio >= config.MAX_CAPS_RATIO:
                return True, f"Excessive caps ({int(caps_ratio * 100)}%)"

        # Check repeated characters
        repeated_pattern = re.compile(r'(.)\1{' + str(config.REPEATED_CHAR_THRESHOLD - 1) + ',}')
        if repeated_pattern.search(content):
            return True, "Repeated character spam"

        return False, None

    async def _check_rapid_messaging(
        self,
        user_id: str,
        is_trusted: bool
    ) -> Tuple[bool, Optional[str]]:
        """
        Check for message flooding.

        Args:
            user_id: User ID
            is_trusted: Whether user is trusted

        Returns:
            Tuple of (is_spam, reason)
        """
        db = await get_db()

        # Get recent messages
        recent = await db.get_recent_messages(
            user_id,
            seconds=config.SPAM_TIME_WINDOW
        )

        # Adjust threshold based on trust
        threshold = config.SPAM_MESSAGE_COUNT
        if is_trusted:
            threshold += 2  # Trusted users get +2 messages buffer

        if len(recent) >= threshold:
            return True, f"Rapid messaging ({len(recent)} messages in {config.SPAM_TIME_WINDOW}s)"

        return False, None

    async def _check_duplicate_messages(
        self,
        user_id: str,
        content_hash: str,
        is_trusted: bool
    ) -> Tuple[bool, Optional[str]]:
        """
        Check for repeated identical messages.

        Args:
            user_id: User ID
            content_hash: Hash of message content
            is_trusted: Whether user is trusted

        Returns:
            Tuple of (is_spam, reason)
        """
        db = await get_db()

        # Get recent messages with same hash
        duplicates = await db.fetch_all(
            """
            SELECT * FROM message_history
            WHERE user_id = ?
            AND content_hash = ?
            AND created_at > datetime('now', '-60 seconds')
            AND is_deleted = 0
            """,
            (user_id, content_hash)
        )

        # Adjust threshold based on trust
        threshold = config.SPAM_DUPLICATE_COUNT
        if is_trusted:
            threshold += 1

        if len(duplicates) >= threshold:
            return True, f"Duplicate messages ({len(duplicates)} identical messages)"

        return False, None

    async def _check_cross_channel_spam(
        self,
        user_id: str,
        current_channel_id: str,
        content_hash: str,
        is_trusted: bool
    ) -> Tuple[bool, Optional[str]]:
        """
        Check for posting same message across multiple channels.

        Args:
            user_id: User ID
            current_channel_id: Current channel ID
            content_hash: Hash of message content
            is_trusted: Whether user is trusted

        Returns:
            Tuple of (is_spam, reason)
        """
        db = await get_db()

        # Find same message in other channels
        cross_posts = await db.fetch_all(
            """
            SELECT DISTINCT channel_id FROM message_history
            WHERE user_id = ?
            AND content_hash = ?
            AND channel_id != ?
            AND created_at > datetime('now', '-300 seconds')
            AND is_deleted = 0
            """,
            (user_id, content_hash, current_channel_id)
        )

        # Adjust threshold based on trust
        threshold = config.SPAM_CROSS_CHANNEL_COUNT
        if is_trusted:
            threshold += 1

        if len(cross_posts) >= threshold:
            return True, f"Cross-channel spam ({len(cross_posts) + 1} channels)"

        return False, None

    # ========================================================================
    # UTILITIES
    # ========================================================================

    def _hash_content(self, content: str) -> str:
        """
        Create hash of message content for duplicate detection.

        Normalizes content (lowercase, strip whitespace) before hashing.

        Args:
            content: Message content

        Returns:
            SHA256 hash (hex string)
        """
        # Normalize content
        normalized = content.lower().strip()
        normalized = re.sub(r'\s+', ' ', normalized)  # Collapse whitespace

        # Hash it
        return hashlib.sha256(normalized.encode()).hexdigest()

    async def get_spam_stats(self, user_id: str = None) -> Dict:
        """
        Get spam detection statistics.

        Args:
            user_id: Optional user ID to get stats for specific user

        Returns:
            Dict with statistics
        """
        db = await get_db()

        if user_id:
            # User-specific stats
            total_messages = await db.fetch_value(
                "SELECT COUNT(*) FROM message_history WHERE user_id = ?",
                (user_id,)
            )

            spam_messages = await db.fetch_value(
                "SELECT COUNT(*) FROM message_history WHERE user_id = ? AND is_spam = 1",
                (user_id,)
            )

            warnings = await db.get_warning_count(user_id, active_only=False)

            return {
                'total_messages': total_messages or 0,
                'spam_messages': spam_messages or 0,
                'warnings': warnings,
                'spam_rate': round((spam_messages / total_messages * 100) if total_messages else 0, 1)
            }
        else:
            # Server-wide stats
            total_messages = await db.fetch_value("SELECT COUNT(*) FROM message_history")
            spam_messages = await db.fetch_value("SELECT COUNT(*) FROM message_history WHERE is_spam = 1")
            total_warnings = await db.fetch_value("SELECT COUNT(*) FROM warnings")
            total_cases = await db.fetch_value("SELECT COUNT(*) FROM cases")

            return {
                'total_messages': total_messages or 0,
                'spam_messages': spam_messages or 0,
                'total_warnings': total_warnings or 0,
                'total_cases': total_cases or 0,
                'spam_rate': round((spam_messages / total_messages * 100) if total_messages else 0, 1)
            }


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

# Global spam detector instance
spam_detector: Optional[SpamDetector] = None


def get_spam_detector() -> SpamDetector:
    """Get global spam detector instance."""
    global spam_detector
    if spam_detector is None:
        spam_detector = SpamDetector()
    return spam_detector
