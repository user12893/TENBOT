"""
============================================================================
TENBOT CONFIGURATION
============================================================================
Central configuration file for all bot settings.
Edit these values to customize bot behavior.

For security, store your bot token in a .env file:
BOT_TOKEN=your_token_here
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# BOT CREDENTIALS
# ============================================================================

BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
BOT_PREFIX = '!'  # Legacy prefix for text commands

# ============================================================================
# DATABASE SETTINGS
# ============================================================================

DATABASE_PATH = 'data/tenbot.db'
BACKUP_INTERVAL = 3600  # Seconds between database backups (1 hour)
MAX_BACKUPS = 7  # Keep 7 daily backups

# ============================================================================
# SPAM DETECTION SETTINGS
# ============================================================================

# Message spam thresholds
SPAM_MESSAGE_COUNT = 5      # Messages in time window = spam
SPAM_TIME_WINDOW = 10       # Seconds
SPAM_DUPLICATE_COUNT = 3    # Repeated identical messages
SPAM_CROSS_CHANNEL_COUNT = 3  # Same message across X channels

# Image spam thresholds
IMAGE_SPAM_COUNT = 4        # Images in time window
IMAGE_SPAM_WINDOW = 30      # Seconds

# Content analysis
MAX_MENTIONS_PER_MESSAGE = 5   # More = spam
MAX_CAPS_RATIO = 0.7           # 70% caps = spam
REPEATED_CHAR_THRESHOLD = 10   # "aaaaaaaaaa" = spam

# Link filtering
ALLOW_LINKS = True
LINK_WHITELIST = [
    'discord.gg/your-server',
    'youtube.com',
    'github.com',
    'linkedin.com',
    # Add trusted domains here
]
BLOCK_ALL_INVITES = True  # Block all discord.gg invites except whitelist

# Scam pattern detection (regex patterns)
SCAM_PATTERNS = [
    r'free\s+nitro',
    r'discord\.gift',
    r'click\s+here\s+for',
    r'dm\s+me\s+for\s+money',
    r'investment\s+opportunity',
    r'double\s+your\s+(money|crypto)',
    r'@everyone.*http',  # @everyone with link
]

# ============================================================================
# TRUST SYSTEM SETTINGS
# ============================================================================

# Trust score calculation (0-100)
TRUST_SCORE_WEIGHTS = {
    'account_age': 0.20,        # 20% - How long they've been on Discord
    'server_age': 0.15,         # 15% - How long in this server
    'message_count': 0.15,      # 15% - Total messages sent
    'message_quality': 0.20,    # 20% - Reactions per message ratio
    'consistency': 0.10,        # 10% - Daily activity streak
    'warnings': -0.30,          # -30% - Warning history (negative impact)
    'reputation': 0.20,         # 20% - Community reputation
}

# Trust tiers
TRUST_TIERS = {
    'new': (0, 20),        # 0-20: New/untrusted
    'probation': (20, 40),  # 20-40: On probation
    'member': (40, 60),     # 40-60: Regular member
    'trusted': (60, 80),    # 60-80: Trusted member
    'vetted': (80, 100),    # 80-100: Highly trusted
}

# Minimum requirements for trust
MIN_MESSAGES_FOR_TRUST = 50
MIN_DAYS_FOR_TRUST = 7
MIN_REACTIONS_RATIO = 0.1  # 10% of messages should get reactions

# ============================================================================
# PUNISHMENT SYSTEM
# ============================================================================

# Progressive timeout durations (seconds)
TIMEOUT_DURATIONS = {
    1: 300,      # 1st warning: 5 minutes
    2: 1800,     # 2nd warning: 30 minutes
    3: 10800,    # 3rd warning: 3 hours
    4: 86400,    # 4th warning: 24 hours
}

AUTO_BAN_THRESHOLD = 5  # Auto-ban after X warnings
WARNING_DECAY_DAYS = 30  # Warnings older than X days are reduced in weight

# ============================================================================
# GAMIFICATION SETTINGS
# ============================================================================

ENABLE_GAMIFICATION = True

# XP rewards
XP_PER_MESSAGE = 5
XP_PER_VOICE_MINUTE = 2
XP_PER_REACTION_RECEIVED = 3
XP_COOLDOWN = 60  # Seconds between XP awards from messages

# Leveling
XP_PER_LEVEL = 100  # XP needed per level
MAX_LEVEL = 100

# Auto-roles based on level
LEVEL_ROLES = {
    5: 'Active',
    10: 'Regular',
    20: 'Veteran',
    30: 'Elite',
    50: 'Legend',
}

# Milestone roles (based on message count)
MILESTONE_ROLES = {
    10: 'Newcomer',
    50: 'Member',
    100: 'Active Member',
    500: 'Veteran Member',
    1000: 'Elite Member',
}

# Achievements
ACHIEVEMENTS = {
    'first_message': {
        'name': '👋 First Steps',
        'description': 'Send your first message',
        'xp_reward': 50,
        'condition': lambda data: data['messages'] >= 1
    },
    'century': {
        'name': '💯 Century',
        'description': 'Send 100 messages',
        'xp_reward': 150,
        'condition': lambda data: data['messages'] >= 100
    },
    'helpful': {
        'name': '🤝 Helpful',
        'description': 'Receive 100 reactions',
        'xp_reward': 200,
        'condition': lambda data: data['reactions_received'] >= 100
    },
    'consistent': {
        'name': '🔥 Consistent',
        'description': '30-day streak',
        'xp_reward': 500,
        'condition': lambda data: data.get('streak_days', 0) >= 30
    },
    'voice_active': {
        'name': '🎤 Voice Active',
        'description': 'Spend 600 minutes in voice',
        'xp_reward': 300,
        'condition': lambda data: data.get('voice_time', 0) >= 600
    },
}

# ============================================================================
# REPUTATION SYSTEM
# ============================================================================

# Reputation score components (0-100 each)
REPUTATION_WEIGHTS = {
    'expertise': 0.25,      # 25% - Knowledge/helpfulness
    'collaboration': 0.25,  # 25% - Team participation
    'consistency': 0.25,    # 25% - Regular engagement
    'leadership': 0.25,     # 25% - Initiative and mentorship
}

# Reputation tiers
REPUTATION_TIERS = {
    'bronze': (0, 25),
    'silver': (25, 50),
    'gold': (50, 75),
    'platinum': (75, 100),
}

# ============================================================================
# MODERATION SETTINGS
# ============================================================================

# Case management
AUTO_CASE_NUMBERS = True  # Auto-assign case numbers to mod actions
REQUIRE_BAN_REASON = True
REQUIRE_KICK_REASON = True

# Mod log settings
LOG_MESSAGE_EDITS = True
LOG_MESSAGE_DELETES = True
LOG_MEMBER_JOINS = True
LOG_MEMBER_LEAVES = True
LOG_ROLE_CHANGES = True
LOG_NICKNAME_CHANGES = True
LOG_VOICE_ACTIVITY = False  # Can be spammy

# Appeal system
ALLOW_APPEALS = True
APPEAL_COOLDOWN = 86400  # 24 hours between appeals

# ============================================================================
# CHANNEL SETTINGS
# ============================================================================

# Auto-created channels
AUTO_CREATE_CHANNELS = True

REQUIRED_CHANNELS = {
    'mod-logs': {
        'category': 'Moderation',
        'private': True,  # Mods only
        'description': 'Moderation action logs'
    },
    'user-logs': {
        'category': 'Moderation',
        'private': True,
        'description': 'User activity logs (joins, leaves, etc.)'
    },
    'case-logs': {
        'category': 'Moderation',
        'private': True,
        'description': 'Case management logs'
    },
    'level-ups': {
        'category': 'Community',
        'private': False,
        'description': 'Level up announcements'
    },
    'achievements': {
        'category': 'Community',
        'private': False,
        'description': 'Achievement unlocks'
    },
}

# ============================================================================
# IMAGE DETECTION SETTINGS
# ============================================================================

# Image fingerprinting
ENABLE_IMAGE_HASHING = True
IMAGE_SIMILARITY_THRESHOLD = 95  # % similarity to flag as duplicate

# Image spam database
SPAM_IMAGE_AUTO_DELETE = True
COMMUNITY_REPORT_THRESHOLD = 3  # Reports needed to auto-block image

# Allowed image formats
ALLOWED_IMAGE_FORMATS = ['png', 'jpg', 'jpeg', 'gif', 'webp']
MAX_IMAGE_SIZE_MB = 10

# ============================================================================
# PERFORMANCE SETTINGS
# ============================================================================

# Caching
CACHE_USER_DATA = True
CACHE_DURATION = 300  # Seconds to cache user data

# Rate limiting
RATE_LIMIT_ENABLED = True
MAX_COMMANDS_PER_MINUTE = 10

# Database optimization
DB_VACUUM_INTERVAL = 86400  # Daily cleanup
DB_POOL_SIZE = 5

# ============================================================================
# FEATURE FLAGS
# ============================================================================

# Enable/disable major features
FEATURES = {
    'spam_detection': True,
    'image_detection': True,
    'trust_system': True,
    'gamification': True,
    'reputation_system': True,
    'case_management': True,
    'appeal_system': True,
    'auto_moderation': True,
    'user_reports': True,

    # Future features (not implemented yet)
    'ai_moderation': False,
    'ai_channel_routing': False,
    'ai_image_analysis': False,
}

# ============================================================================
# TRUSTED ROLES
# ============================================================================

# Users with these roles bypass some spam detection
TRUSTED_ROLE_NAMES = [
    'Admin',
    'Moderator',
    'Verified',
    'Trusted',
    'VIP',
]

# Roles that can use mod commands
MOD_ROLE_NAMES = [
    'Admin',
    'Moderator',
    'Server Manager',
]

# ============================================================================
# DEVELOPER SETTINGS
# ============================================================================

DEBUG_MODE = False
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_TO_FILE = True
LOG_FILE = 'data/bot.log'

# ============================================================================
# VALIDATION
# ============================================================================

def validate_config():
    """Validate configuration on startup"""
    errors = []

    if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        errors.append("BOT_TOKEN not set! Please set it in .env file.")

    if AUTO_BAN_THRESHOLD < 2:
        errors.append("AUTO_BAN_THRESHOLD must be at least 2")

    if XP_PER_LEVEL < 1:
        errors.append("XP_PER_LEVEL must be positive")

    return errors

# Run validation on import
_config_errors = validate_config()
if _config_errors:
    print("⚠️  Configuration Errors:")
    for error in _config_errors:
        print(f"   - {error}")
