"""
Music Bot Module for Discord
Supports YouTube URLs, Spotify links, and song name searches
"""

import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import yt_dlp
from typing import Optional
import re

# yt-dlp options for audio extraction
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


class YTDLSource(discord.PCMVolumeTransformer):
    """Audio source for playing from YouTube/URLs"""

    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')
        self.thumbnail = data.get('thumbnail')
        self.requester = None

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        """Create audio source from URL or search query"""
        loop = loop or asyncio.get_event_loop()

        # Extract info from YouTube/URL
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        # Handle playlists
        if 'entries' in data:
            # Return list of songs for playlist
            return [cls._create_source(entry, stream) for entry in data['entries'] if entry]

        return cls._create_source(data, stream)

    @staticmethod
    def _create_source(data, stream):
        """Helper to create audio source from data"""
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return {
            'source': discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS),
            'data': data
        }


class MusicQueue:
    """Queue system for managing songs"""

    def __init__(self):
        self.queue = []
        self.current = None
        self.loop = False

    def add(self, song):
        """Add song to queue"""
        self.queue.append(song)

    def add_multiple(self, songs):
        """Add multiple songs (for playlists)"""
        self.queue.extend(songs)

    def next(self):
        """Get next song from queue"""
        if self.loop and self.current:
            return self.current

        if self.queue:
            self.current = self.queue.pop(0)
            return self.current

        self.current = None
        return None

    def clear(self):
        """Clear the queue"""
        self.queue = []
        self.current = None

    def skip(self):
        """Skip current song"""
        if self.queue:
            self.current = self.queue.pop(0)
            return self.current
        self.current = None
        return None

    def is_empty(self):
        """Check if queue is empty"""
        return len(self.queue) == 0


class Music(commands.Cog):
    """Music commands cog"""

    def __init__(self, bot):
        self.bot = bot
        self.queues = {}  # Guild ID -> MusicQueue
        self.volumes = {}  # Guild ID -> volume level

    def get_queue(self, guild_id):
        """Get or create queue for guild"""
        if guild_id not in self.queues:
            self.queues[guild_id] = MusicQueue()
        return self.queues[guild_id]

    def get_volume(self, guild_id):
        """Get volume for guild (default 0.5)"""
        return self.volumes.get(guild_id, 0.5)

    def set_volume(self, guild_id, volume):
        """Set volume for guild"""
        self.volumes[guild_id] = max(0.0, min(1.0, volume))

    async def play_next(self, guild):
        """Play next song in queue"""
        queue = self.get_queue(guild.id)

        if queue.is_empty():
            # Queue is empty, nothing to play
            return

        next_song = queue.next()
        if not next_song:
            return

        # Create audio source
        source_info = next_song
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(source_info['data']['url'], **FFMPEG_OPTIONS),
            volume=self.get_volume(guild.id)
        )

        # Play the song
        def after_playing(error):
            if error:
                print(f"Error playing song: {error}")
            # Schedule next song
            asyncio.run_coroutine_threadsafe(self.play_next(guild), self.bot.loop)

        if guild.voice_client:
            guild.voice_client.play(source, after=after_playing)

    @app_commands.command(name="play", description="Play a song from YouTube URL, Spotify link, or search by name")
    @app_commands.describe(query="YouTube URL, Spotify link, or song name to search")
    async def play(self, interaction: discord.Interaction, query: str):
        """Play command - supports URLs and search queries"""

        # Check if user is in voice channel
        if not interaction.user.voice:
            await interaction.response.send_message("❌ You need to be in a voice channel to use this command!", ephemeral=True)
            return

        channel = interaction.user.voice.channel

        await interaction.response.defer()

        try:
            # Connect to voice channel if not connected
            if not interaction.guild.voice_client:
                voice_client = await channel.connect()
            else:
                voice_client = interaction.guild.voice_client
                if voice_client.channel != channel:
                    await voice_client.move_to(channel)

            # Handle Spotify links (convert to YouTube search)
            if 'spotify.com' in query:
                await interaction.followup.send("🎵 Spotify links detected! Searching on YouTube...", ephemeral=True)
                # Extract track name from Spotify (simplified - you'd need spotipy for full support)
                query = f"ytsearch:{query}"

            # If not a URL, search YouTube
            if not query.startswith('http'):
                query = f"ytsearch:{query}"

            # Get audio source
            source_data = await YTDLSource.from_url(query, loop=self.bot.loop, stream=True)

            # Check if it's a playlist
            if isinstance(source_data, list):
                queue = self.get_queue(interaction.guild.id)
                for song in source_data:
                    queue.add(song)

                await interaction.followup.send(f"📝 Added **{len(source_data)} songs** to the queue!")

                # If not currently playing, start
                if not voice_client.is_playing():
                    await self.play_next(interaction.guild)
            else:
                # Single song
                queue = self.get_queue(interaction.guild.id)
                queue.add(source_data)

                title = source_data['data'].get('title', 'Unknown')
                duration = source_data['data'].get('duration', 0)
                duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "Unknown"

                # Create embed
                embed = discord.Embed(
                    title="🎵 Added to Queue",
                    description=f"**{title}**",
                    color=discord.Color.green()
                )
                embed.add_field(name="Duration", value=duration_str, inline=True)
                embed.add_field(name="Position in Queue", value=len(queue.queue), inline=True)

                if source_data['data'].get('thumbnail'):
                    embed.set_thumbnail(url=source_data['data']['thumbnail'])

                await interaction.followup.send(embed=embed)

                # If not currently playing, start
                if not voice_client.is_playing():
                    await self.play_next(interaction.guild)

        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        """Pause the current song"""
        voice_client = interaction.guild.voice_client

        if not voice_client:
            await interaction.response.send_message("❌ I'm not in a voice channel!", ephemeral=True)
            return

        if voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("⏸️ Paused the music!")
        else:
            await interaction.response.send_message("❌ Nothing is playing right now!", ephemeral=True)

    @app_commands.command(name="resume", description="Resume the paused song")
    async def resume(self, interaction: discord.Interaction):
        """Resume the paused song"""
        voice_client = interaction.guild.voice_client

        if not voice_client:
            await interaction.response.send_message("❌ I'm not in a voice channel!", ephemeral=True)
            return

        if voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("▶️ Resumed the music!")
        else:
            await interaction.response.send_message("❌ The music is not paused!", ephemeral=True)

    @app_commands.command(name="stop", description="Stop playing and clear the queue")
    async def stop(self, interaction: discord.Interaction):
        """Stop playing and clear queue"""
        voice_client = interaction.guild.voice_client

        if not voice_client:
            await interaction.response.send_message("❌ I'm not in a voice channel!", ephemeral=True)
            return

        # Clear queue
        queue = self.get_queue(interaction.guild.id)
        queue.clear()

        # Stop playing
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()

        await interaction.response.send_message("⏹️ Stopped the music and cleared the queue!")

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        """Skip the current song"""
        voice_client = interaction.guild.voice_client

        if not voice_client:
            await interaction.response.send_message("❌ I'm not in a voice channel!", ephemeral=True)
            return

        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()  # This will trigger play_next via the after callback
            await interaction.response.send_message("⏭️ Skipped to the next song!")
        else:
            await interaction.response.send_message("❌ Nothing is playing right now!", ephemeral=True)

    @app_commands.command(name="queue", description="Show the current song queue")
    async def queue_command(self, interaction: discord.Interaction):
        """Display the current queue"""
        queue = self.get_queue(interaction.guild.id)

        if queue.is_empty() and not queue.current:
            await interaction.response.send_message("📝 The queue is empty!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🎵 Music Queue",
            color=discord.Color.blue()
        )

        # Current song
        if queue.current:
            current_title = queue.current['data'].get('title', 'Unknown')
            embed.add_field(
                name="▶️ Now Playing",
                value=current_title,
                inline=False
            )

        # Upcoming songs
        if queue.queue:
            upcoming = "\n".join([
                f"{i+1}. {song['data'].get('title', 'Unknown')}"
                for i, song in enumerate(queue.queue[:10])  # Show first 10
            ])
            embed.add_field(
                name=f"📝 Up Next ({len(queue.queue)} songs)",
                value=upcoming,
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Show the currently playing song")
    async def nowplaying(self, interaction: discord.Interaction):
        """Display currently playing song"""
        voice_client = interaction.guild.voice_client
        queue = self.get_queue(interaction.guild.id)

        if not voice_client or not voice_client.is_playing():
            await interaction.response.send_message("❌ Nothing is playing right now!", ephemeral=True)
            return

        if not queue.current:
            await interaction.response.send_message("❌ No song information available!", ephemeral=True)
            return

        data = queue.current['data']
        title = data.get('title', 'Unknown')
        duration = data.get('duration', 0)
        duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "Unknown"
        uploader = data.get('uploader', 'Unknown')
        url = data.get('webpage_url', '')

        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"**{title}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Duration", value=duration_str, inline=True)
        embed.add_field(name="Uploader", value=uploader, inline=True)

        if url:
            embed.add_field(name="URL", value=f"[Click here]({url})", inline=False)

        if data.get('thumbnail'):
            embed.set_thumbnail(url=data['thumbnail'])

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leave", description="Make the bot leave the voice channel")
    async def leave(self, interaction: discord.Interaction):
        """Leave voice channel"""
        voice_client = interaction.guild.voice_client

        if not voice_client:
            await interaction.response.send_message("❌ I'm not in a voice channel!", ephemeral=True)
            return

        # Clear queue
        queue = self.get_queue(interaction.guild.id)
        queue.clear()

        await voice_client.disconnect()
        await interaction.response.send_message("👋 Left the voice channel!")

    @app_commands.command(name="volume", description="Set the playback volume (0-100)")
    @app_commands.describe(level="Volume level (0-100)")
    async def volume(self, interaction: discord.Interaction, level: int):
        """Set playback volume"""
        voice_client = interaction.guild.voice_client

        if not voice_client:
            await interaction.response.send_message("❌ I'm not in a voice channel!", ephemeral=True)
            return

        if level < 0 or level > 100:
            await interaction.response.send_message("❌ Volume must be between 0 and 100!", ephemeral=True)
            return

        volume = level / 100.0
        self.set_volume(interaction.guild.id, volume)

        # Update current playback volume if playing
        if voice_client.source:
            voice_client.source.volume = volume

        await interaction.response.send_message(f"🔊 Volume set to **{level}%**!")

    @app_commands.command(name="loop", description="Toggle loop mode for the current song")
    async def loop(self, interaction: discord.Interaction):
        """Toggle loop mode"""
        queue = self.get_queue(interaction.guild.id)
        queue.loop = not queue.loop

        status = "enabled ✅" if queue.loop else "disabled ❌"
        await interaction.response.send_message(f"🔁 Loop mode {status}")


async def setup(bot):
    """Setup function to add cog to bot"""
    await bot.add_cog(Music(bot))
