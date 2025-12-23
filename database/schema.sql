-- ============================================================================
-- TENBOT DATABASE SCHEMA
-- ============================================================================
-- SQLite database schema for all bot data
-- This replaces the JSON file storage with proper relational database

-- ============================================================================
-- USERS TABLE
-- ============================================================================
-- Core user data and statistics
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT,
    discriminator TEXT,
    display_name TEXT,

    -- Timestamps
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    joined_server TIMESTAMP,

    -- Activity metrics
    total_messages INTEGER DEFAULT 0,
    total_reactions_given INTEGER DEFAULT 0,
    total_reactions_received INTEGER DEFAULT 0,
    total_voice_minutes REAL DEFAULT 0,

    -- Current state
    current_voice_channel TEXT,
    voice_join_time TIMESTAMP,

    -- Flags
    is_bot BOOLEAN DEFAULT 0,
    is_banned BOOLEAN DEFAULT 0,

    -- Notes (for mods)
    mod_notes TEXT,

    UNIQUE(user_id)
);

CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen);
CREATE INDEX IF NOT EXISTS idx_users_total_messages ON users(total_messages);

-- ============================================================================
-- USER WARNINGS TABLE
-- ============================================================================
-- Track all warnings issued to users
CREATE TABLE IF NOT EXISTS warnings (
    warning_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    case_id INTEGER,

    -- Warning details
    reason TEXT NOT NULL,
    warning_type TEXT,  -- spam, profanity, harassment, etc.
    severity TEXT DEFAULT 'low',  -- low, medium, high, critical

    -- Context
    message_id TEXT,
    channel_id TEXT,
    evidence TEXT,  -- JSON with screenshots, links, etc.

    -- Action taken
    action_taken TEXT,  -- timeout, kick, ban, none
    timeout_duration INTEGER,  -- seconds

    -- Meta
    issued_by TEXT NOT NULL,
    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,

    -- Appeal
    appealed BOOLEAN DEFAULT 0,
    appeal_status TEXT,  -- pending, approved, denied
    appeal_reason TEXT,
    appeal_reviewed_by TEXT,
    appeal_reviewed_at TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (case_id) REFERENCES cases(case_id)
);

CREATE INDEX IF NOT EXISTS idx_warnings_user ON warnings(user_id);
CREATE INDEX IF NOT EXISTS idx_warnings_issued_at ON warnings(issued_at);
CREATE INDEX IF NOT EXISTS idx_warnings_appealed ON warnings(appealed);

-- ============================================================================
-- MODERATION CASES TABLE
-- ============================================================================
-- Track all moderation actions with case numbers
CREATE TABLE IF NOT EXISTS cases (
    case_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_type TEXT NOT NULL,  -- warning, timeout, kick, ban, note
    user_id TEXT NOT NULL,

    -- Details
    reason TEXT NOT NULL,
    evidence TEXT,  -- JSON
    action_taken TEXT,

    -- Context
    channel_id TEXT,
    message_id TEXT,

    -- Meta
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Status
    status TEXT DEFAULT 'active',  -- active, appealed, overturned, expired

    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_cases_user ON cases(user_id);
CREATE INDEX IF NOT EXISTS idx_cases_type ON cases(case_type);
CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases(created_at);

-- ============================================================================
-- TRUST SCORES TABLE
-- ============================================================================
-- Multi-dimensional trust scoring for each user
CREATE TABLE IF NOT EXISTS trust_scores (
    user_id TEXT PRIMARY KEY,

    -- Overall trust score (0-100)
    overall_score REAL DEFAULT 0,

    -- Component scores (0-100 each)
    account_age_score REAL DEFAULT 0,
    server_age_score REAL DEFAULT 0,
    message_count_score REAL DEFAULT 0,
    message_quality_score REAL DEFAULT 0,
    consistency_score REAL DEFAULT 0,
    warning_penalty REAL DEFAULT 0,
    reputation_score REAL DEFAULT 0,

    -- Trust tier
    trust_tier TEXT DEFAULT 'new',  -- new, probation, member, trusted, vetted

    -- Last calculation
    last_calculated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_trust_overall ON trust_scores(overall_score);
CREATE INDEX IF NOT EXISTS idx_trust_tier ON trust_scores(trust_tier);

-- ============================================================================
-- REPUTATION SCORES TABLE
-- ============================================================================
-- Business-focused reputation metrics
CREATE TABLE IF NOT EXISTS reputation (
    user_id TEXT PRIMARY KEY,

    -- Overall reputation (0-100)
    overall_reputation REAL DEFAULT 0,

    -- Component scores (0-100 each)
    expertise_score REAL DEFAULT 0,
    collaboration_score REAL DEFAULT 0,
    consistency_score REAL DEFAULT 0,
    leadership_score REAL DEFAULT 0,

    -- Tier
    reputation_tier TEXT DEFAULT 'bronze',  -- bronze, silver, gold, platinum

    -- Metrics
    questions_answered INTEGER DEFAULT 0,
    resources_shared INTEGER DEFAULT 0,
    mentees_helped INTEGER DEFAULT 0,
    projects_participated INTEGER DEFAULT 0,

    -- Last calculation
    last_calculated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_reputation_overall ON reputation(overall_reputation);

-- ============================================================================
-- GAMIFICATION TABLE
-- ============================================================================
-- XP, levels, achievements
CREATE TABLE IF NOT EXISTS gamification (
    user_id TEXT PRIMARY KEY,

    -- XP and leveling
    total_xp INTEGER DEFAULT 0,
    current_level INTEGER DEFAULT 1,
    xp_to_next_level INTEGER DEFAULT 100,

    -- Streaks
    current_streak_days INTEGER DEFAULT 0,
    longest_streak_days INTEGER DEFAULT 0,
    last_active_date DATE,

    -- Cooldowns
    last_xp_message_time TIMESTAMP,
    last_xp_voice_time TIMESTAMP,
    last_xp_reaction_time TIMESTAMP,

    -- Stats
    total_xp_earned INTEGER DEFAULT 0,
    level_ups INTEGER DEFAULT 0,
    achievements_unlocked INTEGER DEFAULT 0,

    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_gamification_level ON gamification(current_level);
CREATE INDEX IF NOT EXISTS idx_gamification_xp ON gamification(total_xp);

-- ============================================================================
-- ACHIEVEMENTS TABLE
-- ============================================================================
-- Track unlocked achievements
CREATE TABLE IF NOT EXISTS achievements (
    achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    achievement_key TEXT NOT NULL,

    -- Details
    achievement_name TEXT NOT NULL,
    achievement_description TEXT,
    xp_reward INTEGER DEFAULT 0,

    -- Meta
    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(user_id),
    UNIQUE(user_id, achievement_key)
);

CREATE INDEX IF NOT EXISTS idx_achievements_user ON achievements(user_id);
CREATE INDEX IF NOT EXISTS idx_achievements_key ON achievements(achievement_key);

-- ============================================================================
-- MESSAGE HISTORY TABLE
-- ============================================================================
-- Track recent messages for spam detection
CREATE TABLE IF NOT EXISTS message_history (
    message_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,

    -- Content
    content TEXT,
    content_hash TEXT,  -- For duplicate detection
    has_attachments BOOLEAN DEFAULT 0,
    attachment_count INTEGER DEFAULT 0,
    mention_count INTEGER DEFAULT 0,

    -- Flags
    is_spam BOOLEAN DEFAULT 0,
    is_deleted BOOLEAN DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_user ON message_history(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON message_history(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_hash ON message_history(content_hash);

-- Auto-delete old messages (keep last 30 days for spam detection)
-- This will be handled by periodic cleanup task

-- ============================================================================
-- IMAGE FINGERPRINTS TABLE
-- ============================================================================
-- Store perceptual hashes of images for spam detection
CREATE TABLE IF NOT EXISTS image_fingerprints (
    fingerprint_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Hashes (multiple algorithms for accuracy)
    dhash TEXT NOT NULL,
    phash TEXT NOT NULL,
    average_hash TEXT NOT NULL,

    -- Image info
    original_url TEXT,
    filename TEXT,
    file_size INTEGER,
    image_format TEXT,

    -- Classification
    is_spam BOOLEAN DEFAULT 0,
    spam_category TEXT,  -- scam, nsfw, promotional, etc.

    -- Source
    first_seen_message_id TEXT,
    first_seen_user_id TEXT,
    first_seen_channel_id TEXT,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Statistics
    times_posted INTEGER DEFAULT 1,
    unique_posters INTEGER DEFAULT 1,
    report_count INTEGER DEFAULT 0,

    -- Actions
    auto_delete BOOLEAN DEFAULT 0,

    -- Notes
    notes TEXT,

    UNIQUE(phash)
);

CREATE INDEX IF NOT EXISTS idx_image_dhash ON image_fingerprints(dhash);
CREATE INDEX IF NOT EXISTS idx_image_phash ON image_fingerprints(phash);
CREATE INDEX IF NOT EXISTS idx_image_spam ON image_fingerprints(is_spam);

-- ============================================================================
-- IMAGE REPORTS TABLE
-- ============================================================================
-- Track user reports of spam images
CREATE TABLE IF NOT EXISTS image_reports (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint_id INTEGER NOT NULL,

    -- Reporter
    reported_by TEXT NOT NULL,
    report_reason TEXT,

    -- Context
    message_id TEXT,
    channel_id TEXT,

    -- Meta
    reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',  -- pending, approved, rejected
    reviewed_by TEXT,
    reviewed_at TIMESTAMP,

    FOREIGN KEY (fingerprint_id) REFERENCES image_fingerprints(fingerprint_id),
    FOREIGN KEY (reported_by) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_image_reports_fingerprint ON image_reports(fingerprint_id);
CREATE INDEX IF NOT EXISTS idx_image_reports_status ON image_reports(status);

-- ============================================================================
-- CHANNEL ACTIVITY TABLE
-- ============================================================================
-- Track per-channel message counts
CREATE TABLE IF NOT EXISTS channel_activity (
    user_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,

    message_count INTEGER DEFAULT 0,
    last_message_at TIMESTAMP,

    PRIMARY KEY (user_id, channel_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_channel_activity_channel ON channel_activity(channel_id);

-- ============================================================================
-- AUDIT LOG TABLE
-- ============================================================================
-- Comprehensive audit trail of all bot actions
CREATE TABLE IF NOT EXISTS audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Action details
    action_type TEXT NOT NULL,  -- warning, ban, config_change, etc.
    actor_id TEXT,  -- Who performed the action (user or 'system')
    target_id TEXT,  -- Who was affected

    -- Context
    details TEXT,  -- JSON with full details
    channel_id TEXT,
    guild_id TEXT,

    -- Timestamp
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_action_type ON audit_log(action_type);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_log(target_id);

-- ============================================================================
-- BOT CONFIGURATION TABLE
-- ============================================================================
-- Store runtime configuration (admin-adjustable)
CREATE TABLE IF NOT EXISTS bot_config (
    config_key TEXT PRIMARY KEY,
    config_value TEXT,
    config_type TEXT,  -- string, integer, boolean, json
    description TEXT,

    -- Meta
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT
);

-- ============================================================================
-- STATISTICS TABLE
-- ============================================================================
-- Server-wide statistics for analytics
CREATE TABLE IF NOT EXISTS server_stats (
    stat_date DATE PRIMARY KEY,

    -- Counts
    total_messages INTEGER DEFAULT 0,
    total_users INTEGER DEFAULT 0,
    new_users INTEGER DEFAULT 0,
    active_users INTEGER DEFAULT 0,

    -- Moderation
    warnings_issued INTEGER DEFAULT 0,
    bans_issued INTEGER DEFAULT 0,
    spam_blocked INTEGER DEFAULT 0,
    images_blocked INTEGER DEFAULT 0,

    -- Engagement
    avg_messages_per_user REAL DEFAULT 0,
    avg_voice_time REAL DEFAULT 0,
    peak_online_users INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_stats_date ON server_stats(stat_date);

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- User profile view (combines multiple tables)
CREATE VIEW IF NOT EXISTS user_profiles AS
SELECT
    u.user_id,
    u.username,
    u.display_name,
    u.first_seen,
    u.last_seen,
    u.total_messages,
    u.total_reactions_received,
    u.total_voice_minutes,

    -- Gamification
    g.total_xp,
    g.current_level,
    g.current_streak_days,
    g.achievements_unlocked,

    -- Trust
    t.overall_score AS trust_score,
    t.trust_tier,

    -- Reputation
    r.overall_reputation,
    r.reputation_tier,

    -- Warnings
    (SELECT COUNT(*) FROM warnings w WHERE w.user_id = u.user_id AND w.expires_at > CURRENT_TIMESTAMP) AS active_warnings

FROM users u
LEFT JOIN gamification g ON u.user_id = g.user_id
LEFT JOIN trust_scores t ON u.user_id = t.user_id
LEFT JOIN reputation r ON u.user_id = r.user_id;

-- Leaderboard view
CREATE VIEW IF NOT EXISTS leaderboard AS
SELECT
    user_id,
    username,
    display_name,
    total_xp,
    current_level,
    overall_reputation,
    trust_score,
    total_messages
FROM user_profiles
WHERE trust_score >= 40  -- Only show trusted members
ORDER BY total_xp DESC;

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Auto-update timestamps
CREATE TRIGGER IF NOT EXISTS update_user_timestamp
AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE user_id = NEW.user_id;
END;

CREATE TRIGGER IF NOT EXISTS update_case_timestamp
AFTER UPDATE ON cases
FOR EACH ROW
BEGIN
    UPDATE cases SET updated_at = CURRENT_TIMESTAMP WHERE case_id = NEW.case_id;
END;
