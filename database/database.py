"""
============================================================================
DATABASE HANDLER
============================================================================
Async SQLite database interface for all bot data operations.
Replaces the old JSON file system with proper relational database.

Features:
- Connection pooling
- Transaction support
- Auto-initialization
- Backup system
- Query helpers
"""

import aiosqlite
import asyncio
import json
import os
import shutil
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

import config


class Database:
    """
    Main database handler for TENBOT.

    Usage:
        db = Database()
        await db.initialize()
        user = await db.get_user('123456789')
    """

    def __init__(self, db_path: str = None):
        """
        Initialize database handler.

        Args:
            db_path: Path to SQLite database file (defaults to config.DATABASE_PATH)
        """
        self.db_path = db_path or config.DATABASE_PATH
        self.db: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

        # Ensure data directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================

    async def initialize(self):
        """
        Initialize database connection and create tables.
        Should be called once when bot starts.
        """
        print(f"📊 Initializing database at {self.db_path}...")

        # Connect to database
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row  # Enable dict-like access

        # Enable foreign keys
        await self.db.execute("PRAGMA foreign_keys = ON")

        # Load and execute schema
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path, 'r') as f:
            schema = f.read()
            await self.db.executescript(schema)

        await self.db.commit()
        print("✅ Database initialized successfully!")

    async def close(self):
        """Close database connection."""
        if self.db:
            await self.db.close()
            print("📊 Database connection closed")

    async def backup(self, backup_path: str = None):
        """
        Create a backup of the database.

        Args:
            backup_path: Where to save backup (defaults to data/backups/backup_TIMESTAMP.db)
        """
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = Path(self.db_path).parent / "backups"
            backup_dir.mkdir(exist_ok=True)
            backup_path = backup_dir / f"backup_{timestamp}.db"

        shutil.copy2(self.db_path, backup_path)
        print(f"💾 Database backed up to {backup_path}")

        # Clean old backups (keep only MAX_BACKUPS)
        await self._cleanup_old_backups()

    async def _cleanup_old_backups(self):
        """Remove old backup files, keeping only the most recent ones."""
        backup_dir = Path(self.db_path).parent / "backups"
        if not backup_dir.exists():
            return

        backups = sorted(backup_dir.glob("backup_*.db"), reverse=True)
        for old_backup in backups[config.MAX_BACKUPS:]:
            old_backup.unlink()

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    async def execute(self, query: str, params: Tuple = ()) -> aiosqlite.Cursor:
        """
        Execute a query with parameters.

        Args:
            query: SQL query string
            params: Query parameters (tuple)

        Returns:
            Cursor object
        """
        async with self._lock:
            cursor = await self.db.execute(query, params)
            await self.db.commit()
            return cursor

    async def fetch_one(self, query: str, params: Tuple = ()) -> Optional[Dict]:
        """
        Fetch a single row.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Dict with row data or None
        """
        async with self._lock:
            cursor = await self.db.execute(query, params)
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetch_all(self, query: str, params: Tuple = ()) -> List[Dict]:
        """
        Fetch all rows.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of dicts with row data
        """
        async with self._lock:
            cursor = await self.db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def fetch_value(self, query: str, params: Tuple = ()) -> Any:
        """
        Fetch a single value from the first row.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Single value or None
        """
        row = await self.fetch_one(query, params)
        return list(row.values())[0] if row else None

    # ========================================================================
    # USER OPERATIONS
    # ========================================================================

    async def get_user(self, user_id: str) -> Optional[Dict]:
        """
        Get user data by ID.

        Args:
            user_id: Discord user ID

        Returns:
            Dict with user data or None
        """
        return await self.fetch_one(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        )

    async def create_user(self, user_id: str, username: str, display_name: str = None) -> Dict:
        """
        Create a new user record.

        Args:
            user_id: Discord user ID
            username: Discord username
            display_name: Display name (optional)

        Returns:
            Created user data
        """
        await self.execute(
            """
            INSERT OR IGNORE INTO users (user_id, username, display_name)
            VALUES (?, ?, ?)
            """,
            (user_id, username, display_name or username)
        )

        # Initialize related tables
        await self.execute(
            "INSERT OR IGNORE INTO trust_scores (user_id) VALUES (?)",
            (user_id,)
        )
        await self.execute(
            "INSERT OR IGNORE INTO reputation (user_id) VALUES (?)",
            (user_id,)
        )
        await self.execute(
            "INSERT OR IGNORE INTO gamification (user_id) VALUES (?)",
            (user_id,)
        )

        return await self.get_user(user_id)

    async def update_user(self, user_id: str, **kwargs) -> None:
        """
        Update user fields.

        Args:
            user_id: Discord user ID
            **kwargs: Fields to update (e.g., total_messages=10)
        """
        if not kwargs:
            return

        # Build UPDATE query dynamically
        fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = tuple(kwargs.values()) + (user_id,)

        await self.execute(
            f"UPDATE users SET {fields} WHERE user_id = ?",
            values
        )

    async def increment_user_stat(self, user_id: str, stat: str, amount: int = 1):
        """
        Increment a user statistic.

        Args:
            user_id: Discord user ID
            stat: Stat to increment (e.g., 'total_messages')
            amount: Amount to increment by
        """
        await self.execute(
            f"UPDATE users SET {stat} = {stat} + ? WHERE user_id = ?",
            (amount, user_id)
        )

    async def get_user_profile(self, user_id: str) -> Optional[Dict]:
        """
        Get complete user profile (from view).

        Args:
            user_id: Discord user ID

        Returns:
            Complete user profile with gamification, trust, reputation
        """
        return await self.fetch_one(
            "SELECT * FROM user_profiles WHERE user_id = ?",
            (user_id,)
        )

    # ========================================================================
    # WARNING OPERATIONS
    # ========================================================================

    async def add_warning(
        self,
        user_id: str,
        reason: str,
        issued_by: str,
        warning_type: str = None,
        severity: str = 'low',
        action_taken: str = None,
        timeout_duration: int = None,
        message_id: str = None,
        channel_id: str = None,
        case_id: int = None
    ) -> int:
        """
        Add a warning to a user.

        Args:
            user_id: User being warned
            reason: Reason for warning
            issued_by: Moderator ID
            warning_type: Type of warning (spam, profanity, etc.)
            severity: low, medium, high, critical
            action_taken: What action was taken
            timeout_duration: Timeout duration in seconds
            message_id: Related message ID
            channel_id: Related channel ID
            case_id: Related case ID

        Returns:
            Warning ID
        """
        cursor = await self.execute(
            """
            INSERT INTO warnings (
                user_id, reason, issued_by, warning_type, severity,
                action_taken, timeout_duration, message_id, channel_id, case_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, reason, issued_by, warning_type, severity,
             action_taken, timeout_duration, message_id, channel_id, case_id)
        )
        return cursor.lastrowid

    async def get_user_warnings(self, user_id: str, active_only: bool = False) -> List[Dict]:
        """
        Get all warnings for a user.

        Args:
            user_id: Discord user ID
            active_only: Only return non-expired warnings

        Returns:
            List of warning dicts
        """
        if active_only:
            query = """
                SELECT * FROM warnings
                WHERE user_id = ? AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                ORDER BY issued_at DESC
            """
        else:
            query = "SELECT * FROM warnings WHERE user_id = ? ORDER BY issued_at DESC"

        return await self.fetch_all(query, (user_id,))

    async def get_warning_count(self, user_id: str, active_only: bool = True) -> int:
        """
        Get count of warnings for a user.

        Args:
            user_id: Discord user ID
            active_only: Only count non-expired warnings

        Returns:
            Warning count
        """
        if active_only:
            query = """
                SELECT COUNT(*) FROM warnings
                WHERE user_id = ? AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """
        else:
            query = "SELECT COUNT(*) FROM warnings WHERE user_id = ?"

        return await self.fetch_value(query, (user_id,))

    # ========================================================================
    # CASE MANAGEMENT
    # ========================================================================

    async def create_case(
        self,
        case_type: str,
        user_id: str,
        reason: str,
        created_by: str,
        action_taken: str = None,
        evidence: str = None,
        channel_id: str = None,
        message_id: str = None
    ) -> int:
        """
        Create a moderation case.

        Args:
            case_type: warning, timeout, kick, ban, note
            user_id: Target user ID
            reason: Reason for action
            created_by: Moderator ID
            action_taken: Action description
            evidence: JSON evidence
            channel_id: Related channel
            message_id: Related message

        Returns:
            Case ID
        """
        cursor = await self.execute(
            """
            INSERT INTO cases (
                case_type, user_id, reason, created_by, action_taken,
                evidence, channel_id, message_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (case_type, user_id, reason, created_by, action_taken,
             evidence, channel_id, message_id)
        )
        return cursor.lastrowid

    async def get_case(self, case_id: int) -> Optional[Dict]:
        """Get case by ID."""
        return await self.fetch_one(
            "SELECT * FROM cases WHERE case_id = ?",
            (case_id,)
        )

    async def get_user_cases(self, user_id: str) -> List[Dict]:
        """Get all cases for a user."""
        return await self.fetch_all(
            "SELECT * FROM cases WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )

    # ========================================================================
    # MESSAGE HISTORY
    # ========================================================================

    async def add_message(
        self,
        message_id: str,
        user_id: str,
        channel_id: str,
        content: str,
        content_hash: str,
        has_attachments: bool = False,
        attachment_count: int = 0,
        mention_count: int = 0
    ) -> None:
        """Add message to history for spam detection."""
        await self.execute(
            """
            INSERT OR REPLACE INTO message_history (
                message_id, user_id, channel_id, content, content_hash,
                has_attachments, attachment_count, mention_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (message_id, user_id, channel_id, content, content_hash,
             has_attachments, attachment_count, mention_count)
        )

    async def get_recent_messages(
        self,
        user_id: str,
        seconds: int = 60,
        limit: int = 50
    ) -> List[Dict]:
        """Get user's recent messages for spam detection."""
        return await self.fetch_all(
            """
            SELECT * FROM message_history
            WHERE user_id = ?
            AND created_at > datetime('now', ? || ' seconds')
            AND is_deleted = 0
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, f'-{seconds}', limit)
        )

    async def cleanup_old_messages(self, days: int = 30):
        """Delete message history older than X days."""
        await self.execute(
            "DELETE FROM message_history WHERE created_at < datetime('now', ? || ' days')",
            (f'-{days}',)
        )

    # ========================================================================
    # IMAGE FINGERPRINTS
    # ========================================================================

    async def add_image_fingerprint(
        self,
        dhash: str,
        phash: str,
        average_hash: str,
        original_url: str,
        filename: str,
        user_id: str,
        channel_id: str,
        message_id: str,
        is_spam: bool = False,
        spam_category: str = None
    ) -> Optional[int]:
        """Add image fingerprint to database."""
        try:
            cursor = await self.execute(
                """
                INSERT INTO image_fingerprints (
                    dhash, phash, average_hash, original_url, filename,
                    first_seen_user_id, first_seen_channel_id, first_seen_message_id,
                    is_spam, spam_category
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (dhash, phash, average_hash, original_url, filename,
                 user_id, channel_id, message_id, is_spam, spam_category)
            )
            return cursor.lastrowid
        except aiosqlite.IntegrityError:
            # Image already exists, increment counter
            await self.execute(
                """
                UPDATE image_fingerprints
                SET times_posted = times_posted + 1
                WHERE phash = ?
                """,
                (phash,)
            )
            return None

    async def find_image_by_hash(self, phash: str) -> Optional[Dict]:
        """Find image by perceptual hash."""
        return await self.fetch_one(
            "SELECT * FROM image_fingerprints WHERE phash = ?",
            (phash,)
        )

    async def find_similar_images(self, phash: str, threshold: int = 5) -> List[Dict]:
        """
        Find similar images using Hamming distance.
        Note: This is slow for large databases, consider caching.
        """
        # For now, just return exact matches
        # TODO: Implement proper Hamming distance calculation
        return await self.fetch_all(
            "SELECT * FROM image_fingerprints WHERE phash = ?",
            (phash,)
        )

    # ========================================================================
    # GAMIFICATION
    # ========================================================================

    async def add_xp(self, user_id: str, xp_amount: int, reason: str = 'activity') -> Dict:
        """
        Add XP to user and handle level ups.

        Args:
            user_id: Discord user ID
            xp_amount: Amount of XP to add
            reason: Reason for XP (for logging)

        Returns:
            Dict with 'leveled_up', 'old_level', 'new_level', 'total_xp'
        """
        # Get current stats
        current = await self.fetch_one(
            "SELECT total_xp, current_level FROM gamification WHERE user_id = ?",
            (user_id,)
        )

        if not current:
            await self.execute(
                "INSERT INTO gamification (user_id) VALUES (?)",
                (user_id,)
            )
            current = {'total_xp': 0, 'current_level': 1}

        old_level = current['current_level']
        new_xp = current['total_xp'] + xp_amount
        new_level = max(1, int(new_xp / config.XP_PER_LEVEL))

        # Update database
        await self.execute(
            """
            UPDATE gamification
            SET total_xp = total_xp + ?,
                current_level = ?,
                total_xp_earned = total_xp_earned + ?
            WHERE user_id = ?
            """,
            (xp_amount, new_level, xp_amount, user_id)
        )

        return {
            'leveled_up': new_level > old_level,
            'old_level': old_level,
            'new_level': new_level,
            'total_xp': new_xp
        }

    async def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get top users by XP."""
        return await self.fetch_all(
            "SELECT * FROM leaderboard LIMIT ?",
            (limit,)
        )

    # ========================================================================
    # AUDIT LOG
    # ========================================================================

    async def log_action(
        self,
        action_type: str,
        actor_id: str,
        target_id: str = None,
        details: Dict = None,
        channel_id: str = None,
        guild_id: str = None
    ):
        """Log an action to audit trail."""
        await self.execute(
            """
            INSERT INTO audit_log (action_type, actor_id, target_id, details, channel_id, guild_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (action_type, actor_id, target_id, json.dumps(details) if details else None,
             channel_id, guild_id)
        )

    # ========================================================================
    # STATISTICS
    # ========================================================================

    async def update_daily_stats(self, stat_updates: Dict):
        """Update daily server statistics."""
        today = datetime.now().date()

        # Build update query
        fields = ", ".join(f"{k} = {k} + ?" for k in stat_updates.keys())
        values = tuple(stat_updates.values()) + (str(today),)

        await self.execute(
            f"""
            INSERT INTO server_stats (stat_date, {', '.join(stat_updates.keys())})
            VALUES (?, {', '.join(['?'] * len(stat_updates))})
            ON CONFLICT(stat_date) DO UPDATE SET {fields}
            """,
            (str(today),) + tuple(stat_updates.values()) + values
        )


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

# Global database instance (initialized in bot.py)
db: Optional[Database] = None


async def get_db() -> Database:
    """Get global database instance."""
    global db
    if db is None:
        db = Database()
        await db.initialize()
    return db
