# TENBOT - Ultra Discord Bot for Business Communities

**Version 2.0.0** - All-in-one professional Discord community management bot

## 🌟 Features

### ✅ Currently Implemented

- **Advanced Spam Detection**
  - Rapid messaging detection
  - Duplicate message detection
  - Cross-channel spam detection
  - Link filtering with whitelist
  - Mention spam detection
  - Content analysis (excessive caps, repeated characters)
  - Scam pattern detection (regex-based)
  - Image fingerprinting (perceptual hashing)
  - Trust-aware thresholds (trusted users get more lenient detection)

- **Image Detection System**
  - Perceptual hashing (dHash, pHash, aHash)
  - Duplicate image detection
  - Community reporting system
  - Auto-block after threshold
  - Whitelist/blacklist management
  - Works without AI (pure image processing)

- **Trust Scoring System**
  - Multi-dimensional trust calculation (0-100 score)
  - Components: account age, server age, message count/quality, consistency, warnings, reputation
  - 5 trust tiers: New, Probation, Member, Trusted, Vetted
  - Automatic recalculation
  - Integration with spam detection

- **Case Management**
  - Auto-assigned case numbers
  - Complete audit trail
  - Warning system with progressive punishments
  - Appeal tracking
  - Evidence storage

- **Gamification**
  - XP and leveling system
  - Daily activity streaks
  - Achievements
  - Auto-role rewards
  - Leaderboards

- **Database System**
  - SQLite with proper schema
  - Automatic backups
  - Data cleanup tasks
  - Comprehensive logging
  - GDPR-ready structure

---

## 📁 Project Structure

```
TENBOT/
├── bot.py                 # Main bot file (run this)
├── config.py              # Configuration settings
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
│
├── database/
│   ├── __init__.py
│   ├── database.py       # Database handler
│   └── schema.sql        # Database schema
│
├── modules/
│   ├── __init__.py
│   ├── spam_detection.py # Spam detection logic
│   ├── image_detection.py # Image fingerprinting
│   └── trust_system.py   # Trust scoring
│
├── utils/
│   ├── __init__.py
│   └── helpers.py        # Utility functions
│
└── data/                 # Created automatically
    ├── tenbot.db         # Main database
    ├── backups/          # Database backups
    └── bot.log           # Log file
```

---

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.8 or higher
- Discord bot token ([Get one here](https://discord.com/developers/applications))

### 2. Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd TENBOT

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env and add your bot token
nano .env  # or use any text editor
```

### 3. Configuration

Edit `config.py` to customize:
- Spam detection thresholds
- Trust score weights
- Punishment durations
- XP rewards
- Feature toggles

### 4. Run the Bot

```bash
python bot.py
```

---

## ⚙️ Configuration

### Essential Settings (`config.py`)

```python
# Spam Detection
SPAM_MESSAGE_COUNT = 5       # Messages in time window = spam
SPAM_TIME_WINDOW = 10        # Seconds
SPAM_DUPLICATE_COUNT = 3     # Repeated messages
SPAM_CROSS_CHANNEL_COUNT = 3 # Cross-channel spam

# Trust System
TRUST_TIERS = {
    'new': (0, 20),
    'probation': (20, 40),
    'member': (40, 60),
    'trusted': (60, 80),
    'vetted': (80, 100),
}

# Punishments
TIMEOUT_DURATIONS = {
    1: 300,      # 5 minutes
    2: 1800,     # 30 minutes
    3: 10800,    # 3 hours
    4: 86400,    # 24 hours
}
AUTO_BAN_THRESHOLD = 5

# Features (enable/disable)
FEATURES = {
    'spam_detection': True,
    'image_detection': True,
    'trust_system': True,
    'gamification': True,
    'ai_moderation': False,  # Not implemented yet
}
```

### Link Whitelist

Add trusted domains to allow links:

```python
LINK_WHITELIST = [
    'discord.gg/your-server',
    'youtube.com',
    'github.com',
    'linkedin.com',
    'your-business-site.com',
]
```

---

## 📖 Commands

### User Commands

| Command | Description |
|---------|-------------|
| `/stats [user]` | View detailed user statistics |
| `/rank [user]` | Check rank and XP progress |
| `/leaderboard` | View server leaderboard |
| `/trust [user]` | Check trust score |
| `/report_image <message_id> <reason>` | Report spam image |

### Moderator Commands

| Command | Description | Permission Required |
|---------|-------------|-------------------|
| `/investigate <user>` | Comprehensive user report | Moderate Members |
| `/trust <user>` | View detailed trust breakdown | Moderate Members |

---

## 🛡️ How It Works

### Spam Detection Flow

```
Message Received
    ↓
[1] Scam Pattern Check (regex)
    ↓
[2] Link Spam Check (whitelist)
    ↓
[3] Mention Spam (max 5 mentions)
    ↓
[4] Content Analysis (caps, repeated chars)
    ↓
[5] Get User Trust Score
    ↓
[6] Rapid Messaging Check (trust-adjusted threshold)
    ↓
[7] Duplicate Message Check
    ↓
[8] Cross-Channel Spam Check
    ↓
Decision: ALLOW or FLAG AS SPAM
```

### Image Detection Flow

```
Image Posted
    ↓
Generate Perceptual Hashes (dHash, pHash, aHash)
    ↓
Check Against Known Spam Images
    ├─ Match Found → DELETE + WARN
    └─ No Match → Store Fingerprint
         ↓
    User Reports → Increment Report Count
         ↓
    Threshold Reached → Auto-Block Future Posts
```

### Trust Score Calculation

```
Components (weighted):
- Account Age (20%): How long on Discord
- Server Age (15%): How long in this server
- Message Count (15%): Total messages
- Message Quality (20%): Reactions per message
- Consistency (10%): Daily streak
- Warnings (-30%): Negative impact
- Reputation (20%): Community reputation

Overall Score (0-100) → Trust Tier
```

---

## 🗄️ Database Schema

The bot uses SQLite with the following main tables:

- **users** - Core user data
- **warnings** - Warning history with appeal system
- **cases** - Moderation action tracking
- **trust_scores** - Multi-dimensional trust metrics
- **reputation** - Business-focused reputation scores
- **gamification** - XP, levels, achievements
- **message_history** - Recent messages for spam detection
- **image_fingerprints** - Image hashes for duplicate detection
- **image_reports** - User reports of spam images
- **audit_log** - Complete action audit trail
- **server_stats** - Daily statistics

---

## 🎯 Use Cases

### For Moderators

```bash
# Investigate suspicious user
/investigate @SuspiciousUser

# Check trust score with breakdown
/trust @NewMember

# Review spam statistics
# (Check mod-logs channel)
```

### For Users

```bash
# Check your progress
/rank

# See leaderboard
/leaderboard

# Report spam image
/report_image 123456789 "Scam advertisement"

# View your stats
/stats
```

---

## 🔐 Security & Privacy

### Data Collected

- Message content (hashed for spam detection, deleted after 30 days)
- User activity metrics (messages, reactions, voice time)
- Warning/case history
- Image fingerprints (hashes only, not actual images)

### Privacy Features

- Messages are hashed, not stored in plain text
- Old data is automatically cleaned up
- Image content is not stored (only perceptual hashes)
- Audit trail for all actions
- GDPR-ready database structure

### Permissions Required

The bot needs these Discord permissions:
- Read Messages/View Channels
- Send Messages
- Manage Messages (to delete spam)
- Moderate Members (for timeouts/bans)
- Manage Roles (for auto-role assignment)
- Read Message History

---

## 📊 Dashboard & Analytics

### Automatic Logging Channels

The bot creates these channels automatically:
- `#mod-logs` - Moderation actions
- `#user-logs` - Join/leave events
- `#case-logs` - Case management
- `#level-ups` - Level up announcements
- `#achievements` - Achievement unlocks

### Daily Statistics

Tracked automatically:
- Total messages
- New users
- Active users
- Spam blocked
- Images blocked
- Warnings issued

---

## 🔧 Customization

### Adding Custom Scam Patterns

Edit `config.py`:

```python
SCAM_PATTERNS = [
    r'free\s+nitro',
    r'discord\.gift',
    r'your-custom-pattern-here',
]
```

### Adjusting Trust Weights

Edit `config.py`:

```python
TRUST_SCORE_WEIGHTS = {
    'account_age': 0.25,      # Increase to prioritize account age
    'warnings': -0.40,        # Increase penalty for warnings
    # ... customize other weights
}
```

### Custom XP Rewards

Edit `config.py`:

```python
XP_PER_MESSAGE = 10          # Increase for faster leveling
XP_PER_VOICE_MINUTE = 5
MESSAGE_COOLDOWN = 30         # Reduce for more frequent XP
```

---

## 🚧 Future Features (Not Yet Implemented)

These features are planned but require AI integration:

- ❌ AI-powered content understanding
- ❌ Channel-specific content routing
- ❌ AI image analysis (NSFW, content detection)
- ❌ Context-aware toxicity detection
- ❌ Automated channel suggestions

---

## 🐛 Troubleshooting

### Bot won't start

```bash
# Check token is set
cat .env

# Ensure dependencies installed
pip install -r requirements.txt

# Check Python version
python --version  # Should be 3.8+
```

### Database errors

```bash
# Reset database (⚠️ deletes all data!)
rm data/tenbot.db
python bot.py  # Will recreate database
```

### Spam detection too strict

Edit `config.py` and increase thresholds:
```python
SPAM_MESSAGE_COUNT = 10  # Was 5
SPAM_TIME_WINDOW = 20    # Was 10
```

### Image detection not working

```bash
# Ensure PIL and imagehash installed
pip install --upgrade Pillow imagehash
```

---

## 📝 Development

### Code Structure

- **Modular design**: Each feature in separate module
- **Clean separation**: Database, logic, commands
- **Well-documented**: Extensive comments and docstrings
- **Type hints**: Better IDE support and error catching
- **Async/await**: Efficient concurrent operations

### Adding New Features

1. Create module in `modules/`
2. Import in `bot.py`
3. Add commands in `bot.py`
4. Update `config.py` with settings
5. Add tests (if applicable)

---

## 📜 License

MIT License - See LICENSE file

---

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 💬 Support

For issues or questions:
- Open an issue on GitHub
- Check existing documentation
- Review code comments

---

## 📈 Changelog

### Version 2.0.0 (Current)
- ✅ Migrated to SQLite database
- ✅ Added image fingerprinting
- ✅ Implemented trust scoring system
- ✅ Added case management
- ✅ Comprehensive spam detection
- ✅ Modular architecture

### Version 1.0.0 (Legacy)
- Basic spam detection
- JSON file storage
- Simple XP system

---

**Made with ❤️ for professional Discord communities**
