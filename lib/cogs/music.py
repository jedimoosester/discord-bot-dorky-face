import discord
from discord import Embed
from discord.commands import slash_command, Option, SlashCommandGroup
from discord.ext.commands import Cog
from discord.ext import tasks
import math
import json
from datetime import datetime
import time
import random
import sqlite3
import asyncio
import yt_dlp

# AttributeError: 'tuple' object has no attribute 'decode'
# Solution: String is a tuple, not a string (need to do fetchone()[0] when querying SQLITE)
# AttributeError: 'FFmpegPCMAudio' object has no attribute '_process':
# Solution: Install ffmpeg
# discord.opus.OpusNotLoaded
# Solution: Install opus, opusfile, libopusenc, flac


ytdl_format_options = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": (
        "0.0.0.0"
    ),  # Bind to ipv4 since ipv6 addresses cause issues at certain times
}

ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', "options": "-vn"}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

with open('./data/guild_data.json', 'r') as f:
    guild_ids = [int(guild_id) for guild_id in json.load(f).keys()]

last_checked_time = {guild_id: math.inf for guild_id in guild_ids}


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source: discord.AudioSource, *, data: dict, volume: float = 0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get("title")
        self.url = data.get("url")

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None, lambda: ytdl.extract_info(url, download=not stream)
        )

        if "entries" in data:
            # Takes the first item from a playlist
            data = data["entries"][0]

        filename = data["url"] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Music(Cog):
    # Music related commands
    def __init__(self, bot):
        self.bot = bot
        self.sqlite_database = None

        bot.scheduler.add_job(self.check_voice_channel_activity, 'interval', minutes=5, jitter=60)

    async def check_voice_channel_activity(self, delay=5*60):
        voice_clients = self.bot.voice_clients
        playing_status = False
        disconnected = False
        for client in voice_clients:
            if len(client.channel.members) <= 1:
                # If bot is the only member in voice channel for more than 5 min, disconnect.
                elapsed_time = time.time() - last_checked_time[client.guild.id]
                if elapsed_time > delay:
                    await client.disconnect(force=True)
                    activity = discord.Activity(type=discord.ActivityType.watching, name="you... 🎃")
                    await self.bot.change_presence(activity=activity)
                    disconnected = True
                    print(f"{datetime.now()}: Disconnected from voice channel due to inactivity.")
                else:
                    last_checked_time[client.guild.id] = time.time()
            else:
                last_checked_time[client.guild.id] = math.inf
            if client.is_playing():
                playing_status = True
        if not playing_status and not disconnected:
            activity = discord.Activity(type=discord.ActivityType.listening, name="/music play")
            await self.bot.change_presence(activity=activity)

    music = SlashCommandGroup("music", "Music-related commands")

    def music_list(self, ctx: discord.AutocompleteContext):
        # Get list of available songs
        conn = sqlite3.connect(self.sqlite_database)
        cursor = conn.cursor()
        names = [n for (n,) in cursor.execute("SELECT name FROM music;").fetchall()]
        conn.close()
        return [c for c in sorted(names) if ctx.value.lower() in c.lower()]

    @music.command(guild_ids=guild_ids, description="Invite me to a voice channel (required before playing music)", name="join")
    async def join(self, ctx, *, channel: Option(discord.VoiceChannel, "Voice channel to join.", required=True)):
        # Join a voice channel
        await ctx.defer()
        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)

        await channel.connect()
        last_checked_time[ctx.guild.id] = time.time()
        await ctx.respond(f"I'm in <#{channel.id}>. Type **/music play** to play something and join me to listen!")

        await channel.send("Hello!")

        print(f"{datetime.now()}: /music join called by {ctx.author.display_name}")

    @music.command(guild_ids=guild_ids, description="Stops and disconnects Dorky Face from voice channel", name="stop")
    async def stop(self, ctx):
        await ctx.defer()
        await ctx.voice_client.disconnect(force=True)
        await ctx.respond("I've left the channel.")

        activity = discord.Activity(type=discord.ActivityType.watching, name="you... 🎃")
        await self.bot.change_presence(activity=activity)

        print(f"{datetime.now()}: /music stop called by {ctx.author.display_name}")

    @music.command(guild_ids=guild_ids, description="Play music", name="play")
    async def play(self, ctx,
                   song: Option(str, "Optional: Choose a song (random otherwise).", default=None,
                                autocomplete=music_list, required=False)):
        await ctx.defer()
        if not ctx.voice_client:  # Make sure bot is in a voice channel
            await ctx.respond("Use **/music join** to invite me to a voice channel first.")
        else:
            conn = sqlite3.connect(self.sqlite_database)
            cursor = conn.cursor()
            if song:  # Retrieve specified song
                result = cursor.execute("SELECT url, duration, artist, source, times_played FROM music WHERE name = ?;",
                                        (song,)).fetchone()
            else:  # Retrieve random song if none specified
                result = random.choice(cursor.execute("SELECT url, duration, artist, source, times_played FROM music;").fetchall())
            url = result[0]
            duration = result[1]
            artist = result[2]
            source = result[3]
            times_played = result[4]+1
            cursor.execute("UPDATE music SET times_played = ? WHERE url = ?;", (times_played, url))
            conn.commit()
            conn.close()

            async with ctx.typing():
                player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
                if ctx.voice_client.is_playing():  # If bot is already playing music, stop current song
                    ctx.voice_client.stop()
                # Play command
                ctx.voice_client.play(
                    player, after=lambda e: print(f"Player error: {e}") if e else None
                )
                # Create embed with information about song
                embed = Embed(title=f"Now Playing: {player.title}", description=f"[YouTube video]({url})", colour=discord.Colour.greyple())
                if source:
                    embed.add_field(name="Source", value=source)
                if artist:
                    embed.add_field(name="Composer/Artist", value=artist)
                if duration:
                    embed.add_field(name="Duration", value=duration)
                embed.add_field(name="Times played", value=times_played)
                img_url = f"http://img.youtube.com/vi/{url.split('=')[-1]}/maxresdefault.jpg"
                embed.set_image(url=img_url)
                await ctx.respond(embed=embed)

                activity = discord.Activity(
                    name=f"{player.title}",
                    type=discord.ActivityType.playing
                )

                await self.bot.change_presence(activity=activity)

        print(f"{datetime.now()}: /music start called by {ctx.author.display_name}")

    @music.command(guild_ids=guild_ids, description="Add music", name="add")
    async def add(self, ctx,
                  name: Option(str, "Name of the song", required=True),
                  url: Option(str, "YouTube URL", required=True),
                  artist: Option(str, "Composer and/or performer", default=None, required=False),
                  source: Option(str, "Series/game the song originates from", default=None, required=False),
                  duration: Option(str, "Duration of song", default=None, required=False)):
        await ctx.defer()
        conn = sqlite3.connect(self.sqlite_database)
        cursor = conn.cursor()
        if "youtube" not in url.replace('.', ''):  # Covers youtube.com and youtu.be links
            await ctx.respond(f"Invalid URL (must be from YouTube): {url}")
        else:
            try:
                cursor.execute("INSERT INTO music (name, url, artist, source, duration, times_played) VALUES (?, ?, ?, ?, ?, ?);",
                               (name, url, artist, source, duration, 0))
                conn.commit()
                embed = Embed(title="Song added!", description=name, colour=discord.Colour.greyple())
                await ctx.respond(embed=embed)
            except sqlite3.IntegrityError:
                await ctx.respond("Song has already been added.")
        conn.close()

    @Cog.listener()
    async def on_message(self, message):
        if not message.author.bot:
            pass

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.sqlite_database = self.bot.sqlite_database
            self.bot.cogs_ready.ready_up('music')


def setup(bot):
    bot.add_cog(Music(bot))
