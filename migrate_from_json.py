"""
============================================================================
MIGRATION SCRIPT - JSON TO SQLITE
============================================================================
Migrate old bot data from JSON files to new SQLite database.

This script will:
1. Read old user_data.json and gamification_data.json
2. Create new SQLite database
3. Import all user data, warnings, XP, levels, etc.
4. Preserve as much data as possible

Usage:
    python migrate_from_json.py

Before running:
- Make sure old JSON files are in anti_spam/ folder
- Backup your JSON files first!
- Bot should NOT be running
"""

import json
import asyncio
import os
from datetime import datetime
from pathlib import Path

# Import database
from database import Database
import config


async def migrate():
    """Main migration function."""

    print("=" * 60)
    print("TENBOT DATA MIGRATION - JSON TO SQLITE")
    print("=" * 60)

    # Check if old files exist
    old_user_data_path = "anti_spam/user_data.json"
    old_gamif_data_path = "anti_spam/gamification_data.json"

    if not os.path.exists(old_user_data_path):
        print(f"❌ File not found: {old_user_data_path}")
        print("   Place your old user_data.json in anti_spam/ folder")
        return

    if not os.path.exists(old_gamif_data_path):
        print(f"❌ File not found: {old_gamif_data_path}")
        print("   Place your old gamification_data.json in anti_spam/ folder")
        return

    # Load old data
    print("\n📂 Loading old JSON data...")

    with open(old_user_data_path, 'r') as f:
        user_data = json.load(f)
    print(f"✅ Loaded {len(user_data)} users from user_data.json")

    with open(old_gamif_data_path, 'r') as f:
        gamification_data = json.load(f)
    print(f"✅ Loaded {len(gamification_data)} users from gamification_data.json")

    # Initialize database
    print("\n🗄️  Initializing new database...")
    db = Database(config.DATABASE_PATH)
    await db.initialize()
    print("✅ Database created successfully!")

    # Migrate user data
    print("\n👥 Migrating user data...")

    migrated_users = 0
    migrated_warnings = 0
    migrated_gamif = 0

    for user_id, data in user_data.items():
        try:
            # Create user
            await db.execute(
                """
                INSERT OR IGNORE INTO users (
                    user_id, username, display_name,
                    total_messages, total_reactions_given, total_reactions_received,
                    total_voice_minutes, joined_server
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    data.get('username', f'User_{user_id}'),
                    data.get('username', f'User_{user_id}'),
                    data.get('messages', 0),
                    data.get('reactions_given', 0),
                    data.get('reactions_received', 0),
                    data.get('voice_time', 0),
                    data.get('join_date')
                )
            )

            migrated_users += 1

            # Migrate warnings
            warnings = data.get('warnings', 0)
            warning_types = data.get('warning_types', [])

            for i in range(warnings):
                warning_type = warning_types[i] if i < len(warning_types) else 'unknown'

                await db.execute(
                    """
                    INSERT INTO warnings (
                        user_id, reason, issued_by, warning_type, severity, issued_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        f"Migrated from old bot: {warning_type}",
                        'system_migration',
                        warning_type,
                        'medium',
                        data.get('last_warning_time', datetime.now().isoformat())
                    )
                )

                migrated_warnings += 1

            # Initialize trust scores and reputation
            await db.execute(
                "INSERT OR IGNORE INTO trust_scores (user_id) VALUES (?)",
                (user_id,)
            )

            await db.execute(
                "INSERT OR IGNORE INTO reputation (user_id) VALUES (?)",
                (user_id,)
            )

        except Exception as e:
            print(f"⚠️  Error migrating user {user_id}: {e}")

    print(f"✅ Migrated {migrated_users} users")
    print(f"✅ Migrated {migrated_warnings} warnings")

    # Migrate gamification data
    print("\n🎮 Migrating gamification data...")

    for user_id, data in gamification_data.items():
        try:
            xp = data.get('xp', 0)
            level = data.get('level', 1)
            streak = data.get('streak_days', 0)
            achievements = data.get('achievements', [])

            await db.execute(
                """
                INSERT OR REPLACE INTO gamification (
                    user_id, total_xp, current_level, current_streak_days,
                    last_active_date, total_xp_earned, achievements_unlocked
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    xp,
                    level,
                    streak,
                    data.get('last_active_date'),
                    data.get('total_xp_earned', xp),
                    len(achievements)
                )
            )

            # Migrate achievements
            for achievement_key in achievements:
                achievement_info = config.ACHIEVEMENTS.get(achievement_key, {})

                await db.execute(
                    """
                    INSERT OR IGNORE INTO achievements (
                        user_id, achievement_key, achievement_name,
                        achievement_description, xp_reward
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        achievement_key,
                        achievement_info.get('name', achievement_key),
                        achievement_info.get('description', ''),
                        achievement_info.get('xp_reward', 0)
                    )
                )

            migrated_gamif += 1

        except Exception as e:
            print(f"⚠️  Error migrating gamification for {user_id}: {e}")

    print(f"✅ Migrated {migrated_gamif} gamification records")

    # Create backup of database
    print("\n💾 Creating database backup...")
    await db.backup()
    print("✅ Backup created!")

    # Close database
    await db.close()

    # Summary
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE!")
    print("=" * 60)
    print(f"✅ Users migrated: {migrated_users}")
    print(f"✅ Warnings migrated: {migrated_warnings}")
    print(f"✅ Gamification records migrated: {migrated_gamif}")
    print()
    print("📝 Next steps:")
    print("   1. Verify data by running: python bot.py")
    print("   2. Check a few user profiles with /stats")
    print("   3. If everything looks good, archive the old JSON files")
    print()
    print("⚠️  Note: Trust scores will be calculated automatically when bot starts")
    print("=" * 60)


async def verify_migration():
    """Verify migration was successful."""

    print("\n🔍 Verifying migration...")

    db = Database(config.DATABASE_PATH)
    await db.initialize()

    # Count records
    user_count = await db.fetch_value("SELECT COUNT(*) FROM users")
    warning_count = await db.fetch_value("SELECT COUNT(*) FROM warnings")
    gamif_count = await db.fetch_value("SELECT COUNT(*) FROM gamification")
    achievement_count = await db.fetch_value("SELECT COUNT(*) FROM achievements")

    print(f"\n📊 Database Statistics:")
    print(f"   Users: {user_count}")
    print(f"   Warnings: {warning_count}")
    print(f"   Gamification records: {gamif_count}")
    print(f"   Achievements: {achievement_count}")

    # Sample some data
    sample_users = await db.fetch_all(
        "SELECT user_id, username, total_messages FROM users LIMIT 5"
    )

    if sample_users:
        print(f"\n👥 Sample Users:")
        for user in sample_users:
            print(f"   - {user['username']}: {user['total_messages']} messages")

    await db.close()

    print("\n✅ Verification complete!")


if __name__ == "__main__":
    import sys

    print("TENBOT Migration Tool")
    print()
    print("This will migrate your old JSON data to the new SQLite database.")
    print("Make sure you have backups of your JSON files!")
    print()

    response = input("Continue? (yes/no): ").lower().strip()

    if response == 'yes':
        # Run migration
        asyncio.run(migrate())

        # Verify
        print()
        verify_response = input("Run verification? (yes/no): ").lower().strip()
        if verify_response == 'yes':
            asyncio.run(verify_migration())

    else:
        print("❌ Migration cancelled")
