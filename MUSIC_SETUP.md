# 🎵 Discord Music Bot Setup Guide

This guide will help you set up the music features for your Discord bot.

## Prerequisites

### 1. Install FFmpeg

FFmpeg is required for audio processing. Install it on your system:

**Windows:**
1. Download from [ffmpeg.org](https://ffmpeg.org/download.html)
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to your system PATH

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Linux (CentOS/RHEL):**
```bash
sudo yum install ffmpeg
```

### 2. Install Python Dependencies

Install all required packages:

```bash
pip install -r requirements.txt
```

This will install:
- `discord.py[voice]` - Discord library with voice support
- `PyNaCl` - Voice encryption
- `yt-dlp` - YouTube audio extraction
- `ffmpeg-python` - FFmpeg wrapper
- `spotipy` - Spotify integration (optional)
- `aiohttp` - Async HTTP requests

## Music Commands

Once the bot is running and in your server, you can use these slash commands:

### Playing Music

**`/play <song or URL>`**
- Play a song from YouTube, Spotify, or by name
- Examples:
  - `/play https://www.youtube.com/watch?v=dQw4w9WgXcQ`
  - `/play never gonna give you up`
  - `/play https://open.spotify.com/track/...`

### Playback Controls

**`/pause`**
- Pause the current song

**`/resume`**
- Resume playback if paused

**`/skip`**
- Skip to the next song in the queue

**`/stop`**
- Stop playing and clear the entire queue

### Queue Management

**`/queue`**
- Show the current song queue
- Displays the currently playing song and upcoming songs

**`/nowplaying`**
- Show detailed information about the current song
- Includes title, duration, uploader, and thumbnail

### Volume & Settings

**`/volume <0-100>`**
- Set the playback volume
- Example: `/volume 50` (sets volume to 50%)

**`/loop`**
- Toggle loop mode for the current song
- When enabled, the current song will repeat

**`/leave`**
- Make the bot leave the voice channel
- Also clears the queue

## How It Works

### Playing Songs

1. Join a voice channel
2. Use `/play <song name or URL>`
3. The bot will:
   - Join your voice channel
   - Search for the song (if you provided a name)
   - Download and play the audio
   - Add it to the queue if something is already playing

### Queue System

- Songs are automatically queued when multiple `/play` commands are used
- The bot plays songs in order (FIFO - First In, First Out)
- Skip songs with `/skip` or stop everything with `/stop`
- View the queue anytime with `/queue`

### Supported Sources

#### YouTube
- Direct video URLs: `https://www.youtube.com/watch?v=...`
- Playlist URLs: `https://www.youtube.com/playlist?list=...`
- Search by name: Just type the song name without a URL

#### Spotify
- Track links: `https://open.spotify.com/track/...`
- The bot will search for the song on YouTube and play it

## Troubleshooting

### Bot won't join voice channel

**Error:** Bot doesn't respond to `/play`

**Solution:**
1. Make sure you're in a voice channel
2. Check bot has `Connect` and `Speak` permissions
3. Verify the bot role is high enough in the role hierarchy

### No audio playing

**Error:** Bot joins but no sound

**Solutions:**
1. Check FFmpeg is installed: `ffmpeg -version`
2. Verify bot has `Speak` permission
3. Check volume isn't set to 0: `/volume 50`
4. Make sure you're not deafened in Discord

### "An error occurred" message

**Error:** Commands fail with error messages

**Solutions:**
1. Check requirements are installed: `pip install -r requirements.txt`
2. Verify internet connection (needed to download songs)
3. Check bot logs for specific error messages
4. Try a different song/URL

### Poor audio quality

**Solutions:**
1. Check your internet connection
2. Try lowering the volume: `/volume 30`
3. Ensure FFmpeg is properly installed

### Commands not appearing

**Error:** Slash commands don't show up

**Solutions:**
1. Wait a few minutes for Discord to sync commands
2. Restart your Discord client
3. Check bot has `applications.commands` scope
4. Reinvite the bot with proper permissions

## Permissions Required

The bot needs these Discord permissions for music features:

- ✅ **Connect** - Join voice channels
- ✅ **Speak** - Play audio
- ✅ **Use Voice Activity** - Transmit audio
- ✅ **Use Slash Commands** - Register commands

## Tips & Best Practices

1. **Always join a voice channel first** before using `/play`
2. **Use `/queue`** to see what's coming up
3. **Set volume before playing** to avoid loud surprises
4. **Use `/leave`** when done to free up the bot
5. **Loop mode** is great for single songs you want to repeat
6. **Search by name** when you don't have a URL handy

## Example Usage Flow

```
1. Join a voice channel
2. /play never gonna give you up
   → Bot joins and starts playing

3. /play some other song
   → Song added to queue

4. /queue
   → See what's playing and what's next

5. /skip
   → Skip to the next song

6. /volume 40
   → Adjust volume to 40%

7. /stop
   → Stop music and clear queue

8. /leave
   → Bot leaves voice channel
```

## Advanced Features

### Playlist Support

The bot automatically handles YouTube playlists:

```
/play https://www.youtube.com/playlist?list=PLxxxxxxxxxxx
```

All songs in the playlist will be added to the queue!

### Loop Mode

Perfect for your favorite song:

```
/play your favorite song
/loop
```

The song will now repeat until you `/skip` or `/stop`.

### Queue Management

- The queue shows up to 10 upcoming songs
- Each server has its own independent queue
- Queues are cleared when the bot leaves the channel

## Support

If you encounter issues:

1. Check this guide's troubleshooting section
2. Verify all dependencies are installed
3. Check bot console logs for errors
4. Ensure FFmpeg is in your system PATH

---

**Enjoy your music! 🎶**
