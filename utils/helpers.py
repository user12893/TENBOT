"""
============================================================================
UTILITY HELPERS
============================================================================
Common helper functions used throughout the bot.
"""

import discord
from datetime import datetime, timedelta
from typing import Optional


def format_timespan(seconds: int) -> str:
    """
    Format seconds into human-readable timespan.

    Args:
        seconds: Number of seconds

    Returns:
        Formatted string (e.g., "2h 30m", "45s")
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}m {secs}s" if secs else f"{mins}m"
    elif seconds < 86400:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h {mins}m" if mins else f"{hours}h"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d {hours}h" if hours else f"{days}d"


def create_progress_bar(current: int, maximum: int, length: int = 10) -> str:
    """
    Create a text progress bar.

    Args:
        current: Current value
        maximum: Maximum value
        length: Bar length in characters

    Returns:
        Progress bar string (e.g., "█████░░░░░ 50%")
    """
    if maximum == 0:
        return "░" * length + " 0%"

    percentage = min(100, (current / maximum) * 100)
    filled = int((percentage / 100) * length)
    empty = length - filled

    bar = "█" * filled + "░" * empty
    return f"{bar} {percentage:.0f}%"


def create_embed(
    title: str,
    description: str = None,
    color: discord.Color = discord.Color.blue(),
    **kwargs
) -> discord.Embed:
    """
    Create a standardized embed.

    Args:
        title: Embed title
        description: Embed description
        color: Embed color
        **kwargs: Additional embed fields

    Returns:
        Discord Embed object
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now()
    )

    for key, value in kwargs.items():
        if key.startswith('field_'):
            # Add field
            field_name = value.get('name', 'Field')
            field_value = value.get('value', 'No value')
            inline = value.get('inline', True)
            embed.add_field(name=field_name, value=field_value, inline=inline)

    return embed


async def send_dm(user: discord.User, embed: discord.Embed) -> bool:
    """
    Send DM to user with error handling.

    Args:
        user: Discord User
        embed: Embed to send

    Returns:
        True if successful, False if failed
    """
    try:
        await user.send(embed=embed)
        return True
    except discord.Forbidden:
        print(f"⚠️  Cannot DM {user.name} (DMs disabled)")
        return False
    except Exception as e:
        print(f"❌ Error sending DM to {user.name}: {e}")
        return False


def is_moderator(member: discord.Member) -> bool:
    """
    Check if user is a moderator.

    Args:
        member: Discord Member

    Returns:
        True if user has mod permissions
    """
    # Check for admin/mod permissions
    if member.guild_permissions.administrator:
        return True

    if member.guild_permissions.moderate_members:
        return True

    # Check for mod roles
    import config
    role_names = [role.name for role in member.roles]
    return any(mod_role in role_names for mod_role in config.MOD_ROLE_NAMES)


def get_or_create_channel(guild: discord.Guild, channel_name: str, category: str = None) -> Optional[discord.TextChannel]:
    """
    Get existing channel or mark for creation.

    Note: Actual creation should happen in bot setup.

    Args:
        guild: Discord Guild
        channel_name: Channel name to find
        category: Category name (optional)

    Returns:
        Channel if found, None otherwise
    """
    return discord.utils.get(guild.channels, name=channel_name)


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate string to max length.

    Args:
        text: String to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def format_list(items: list, max_items: int = 10) -> str:
    """
    Format list for display with truncation.

    Args:
        items: List of items
        max_items: Maximum items to show

    Returns:
        Formatted string
    """
    if len(items) == 0:
        return "None"

    shown = items[:max_items]
    formatted = "\n".join(f"• {item}" for item in shown)

    if len(items) > max_items:
        formatted += f"\n... and {len(items) - max_items} more"

    return formatted
