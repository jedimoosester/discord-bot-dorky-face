import discord
from discord import Embed, Colour
from discord.commands import slash_command, Option, SlashCommandGroup
from discord.ext.commands import Cog
import json
from datetime import datetime
from time import time
import random
import sqlite3

with open('./data/guild_data.json', 'r') as f:
    guild_ids = [int(guild_id) for guild_id in json.load(f).keys()]

stats = ["BDY", "MND", "SPR", "HRT", "REF"]
emoji1 = '🔴'
emoji2 = '⭕'
max_stats = 9


def make_stats_string(value, max_num, e1, e2):
    list1 = [e1] * value  # stats list
    list2 = [e2] * (max_num - value)  # empty stats list
    return ''.join(list1) + ''.join(list2)


def make_stats_embed(title, colour, url, s_dict, max_num, e1, e2, notes=""):
    if notes == "":
        title = f"{title}"
    else:
        title = f"{title} ({notes})"
    embed = Embed(title=title,
                  description="Below are your temporary stats. Click the buttons to roll stat checks (1d10), take damage/heal, or reset to your true stats.",
                  colour=int(colour, 16))
    for s in s_dict.keys():
        embed.add_field(name=s, value=make_stats_string(s_dict[s], max_num, e1, e2), inline=False)
    embed.set_thumbnail(url=url)
    return embed


class Rp(Cog):
    # Roleplay-related commands
    def __init__(self, bot):
        self.bot = bot
        self.sqlite_database = None

    rp = SlashCommandGroup("rp", "RP-related commands")

    async def selectable_characters(self, ctx: discord.AutocompleteContext):
        conn = sqlite3.connect(self.sqlite_database)
        cursor = conn.cursor()
        if self.bot.test:
            # Allow players to select any character (for testing only)
            names = [n for (n,) in cursor.execute("SELECT name FROM characters WHERE guild_id = ?;",
                                                  (ctx.interaction.guild_id,)).fetchall()]
        else:
            # Only allow members to select their own characters
            names = [n for (n,) in cursor.execute("SELECT name FROM characters WHERE user_id = ? AND guild_id = ?;",
                                                  (ctx.interaction.user.id, ctx.interaction.guild_id)).fetchall()]
        conn.close()
        return [c for c in sorted(names) if ctx.value.lower() in c.lower()]

    @rp.command(guild_ids=guild_ids, description="Roll a stat check or adjust temporary stats.", name="roll")
    async def roll(self, ctx,
                   character: Option(str, "Your character", autocomplete=selectable_characters, required=True),
                   notes: Option(str, "Optional notes to differentiate battles (e.g. opponents, thread title, etc.), max 200 characters", default="")):
        await ctx.defer()
        timestamp = time()  # Timestamp (for making persistent views unique)
        conn = sqlite3.connect(self.sqlite_database)
        cursor = conn.cursor()
        (c_id, avatar_url, colour, bdy, mnd, spr, hrt, ref) = cursor.execute(
            f"SELECT characters.c_id, characters.avatar_url, characters.colour, "
            f"stats.bdy, stats.mnd, stats.spr, stats.hrt, stats.ref "
            f"FROM stats JOIN characters ON (characters.c_id = stats.c_id) "
            f"WHERE characters.guild_id = ? AND characters.name = ?;",
            (ctx.guild.id, character)).fetchone()

        stats_dict = {"BDY": bdy, "MND": mnd, "SPR": spr, "HRT": hrt, "REF": ref}

        embed = make_stats_embed(character, colour, avatar_url, stats_dict, max_stats, emoji1, emoji2, notes)
        view = BattleDashboardView(character=character, colour=colour, avatar_url=avatar_url, guild_id=ctx.guild.id, stats_dict=stats_dict, notes=notes, timestamp=timestamp)  # Create a view
        message = await ctx.respond(embed=embed, view=view)

        cursor.execute("INSERT INTO stats_tmp (message_id, channel_id, timestamp, guild_id, c_id, notes) VALUES (?, ?, ?, ?, ?, ?);", (message.id, ctx.channel.id, timestamp, ctx.guild.id, c_id, notes))
        conn.commit()
        conn.close()

        print(f"{datetime.now()}: /rp roll called by {ctx.author.display_name}")

    @Cog.listener()
    async def on_message(self, message):
        if not message.author.bot:
            pass

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.sqlite_database = self.bot.sqlite_database
            conn = sqlite3.connect(self.sqlite_database)
            cursor = conn.cursor()
            for (message_id, channel_id, notes, character, colour, avatar_url, timestamp, guild_id,
                 bdy, mnd, spr, hrt, ref) in \
                    cursor.execute("SELECT DISTINCT stats_tmp.message_id, stats_tmp.channel_id, stats_tmp.notes, "
                                   "characters.name, characters.colour, characters.avatar_url, "
                                   "stats_tmp.timestamp, stats_tmp.guild_id, "
                                   "stats.bdy, stats.mnd, stats.spr, stats.hrt, stats.ref FROM stats_tmp "
                                   "JOIN characters ON (stats_tmp.c_id = characters.c_id) "
                                   "JOIN stats ON (stats.c_id = characters.c_id);"):
                try:
                    message = await self.bot.get_guild(guild_id).get_channel_or_thread(channel_id).fetch_message(message_id)
                    stats_dict_init = {"BDY": bdy, "MND": mnd, "SPR": spr, "HRT": hrt, "REF": ref}
                    stats_dict = {}
                    for field in message.embeds[0].fields[:len(stats)]:
                        stats_dict[field.name] = field.value.count(emoji1)
                    self.bot.add_view(
                        BattleDashboardView(character=character, colour=colour, avatar_url=avatar_url,
                                            guild_id=guild_id, stats_dict=stats_dict,
                                            stats_dict_init=stats_dict_init, notes=notes, timestamp=timestamp))
                    print(f"Added battle view {message_id}")
                except AttributeError:
                    pass
            self.bot.cogs_ready.ready_up('rp')


class BattleDashboardView(discord.ui.View):
    def __init__(self, character=None, colour=None, avatar_url=None, guild_id=None, stats_dict=None, stats_dict_init=None, notes="", timestamp=None):
        super().__init__(timeout=None)
        self.colour = colour
        self.avatar_url = avatar_url
        self.guild_id = guild_id
        self.character = character
        if stats_dict_init is None:
            self.stats_dict_init = stats_dict.copy()
        else:
            self.stats_dict_init = stats_dict_init
        self.stats_dict = stats_dict
        self.notes = notes
        self.timestamp = timestamp

        self.add_buttons()

    def add_buttons(self):
        self.add_item(ResetStatButton(self.character, self.colour, self.avatar_url, self.stats_dict, self.stats_dict_init, self.notes, self.timestamp))
        for stat in self.stats_dict.keys():
            self.add_item(RollStatButton(self.character, self.colour, self.avatar_url, stat, self.stats_dict, self.notes, self.timestamp))
            self.add_item(PlusStatButton(self.character, self.colour, self.avatar_url, stat, self.stats_dict, self.notes, self.timestamp))
            self.add_item(MinusStatButton(self.character, self.colour, self.avatar_url, stat, self.stats_dict, self.notes, self.timestamp))


class ResetStatButton(discord.ui.Button):
    def __init__(self, character, colour, avatar_url, stats_dict, stats_dict_init, notes, timestamp):
        self.character = character
        self.colour = colour
        self.avatar_url = avatar_url
        self.stats_dict = stats_dict
        self.notes = notes
        self.timestamp = timestamp
        self.stats_dict_init = stats_dict_init
        super().__init__(label=f"Reset Stats", row=2,
                         custom_id=f"persistent_view:reset_stats_{self.timestamp}",
                         style=discord.ButtonStyle.grey)

    async def callback(self, interaction: discord.Interaction):
        for stat in self.stats_dict.keys():
            if self.stats_dict[stat] < self.stats_dict_init[stat]:
                self.stats_dict[stat] += (self.stats_dict_init[stat] - self.stats_dict[stat])
            elif self.stats_dict[stat] > self.stats_dict_init[stat]:
                self.stats_dict[stat] -= (self.stats_dict[stat] - self.stats_dict_init[stat])
        embed = make_stats_embed(self.character, self.colour, self.avatar_url, self.stats_dict, max_stats, emoji1,
                                 emoji2, self.notes)
        await interaction.response.edit_message(embed=embed, view=self.view)


class RollStatButton(discord.ui.Button):
    def __init__(self, character, colour, avatar_url, stat, stats_dict, notes, timestamp):
        self.character = character
        self.colour = colour
        self.avatar_url = avatar_url
        self.stat = stat
        self.stats_dict = stats_dict
        self.notes = notes
        self.timestamp = timestamp
        super().__init__(label=f"{stat}", emoji="🎲", row=1,
                         custom_id=f"persistent_view:roll{self.stat}_{self.timestamp}",
                         style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):
        roll_result = random.randint(1, 10)
        if roll_result <= int(self.stats_dict[self.stat]):
            succeed = True
        else:
            succeed = False

        embed = make_stats_embed(self.character, self.colour, self.avatar_url, self.stats_dict, max_stats, emoji1,
                                 emoji2, self.notes)
        embed.add_field(
            name=f"{self.character.split()[0]} ({self.stat} = {self.stats_dict[self.stat]}) rolled {roll_result}",
            value=f"Result: **{'✅ SUCCESS' if succeed else '❌ FAIL'}**")
        embed.set_footer(text=f"A successful roll means rolling {self.stats_dict[self.stat]} or lower.")
        await interaction.response.edit_message(embed=embed, view=self.view)


class PlusStatButton(discord.ui.Button):
    def __init__(self, character, colour, avatar_url, stat, stats_dict, notes, timestamp):
        self.stat = stat
        self.colour = colour
        self.avatar_url = avatar_url
        self.character = character
        self.stats_dict = stats_dict
        self.notes = notes
        self.timestamp = timestamp
        super().__init__(label=f"+1 {stat}", row=3,
                         custom_id=f"persistent_view:plus{self.stat}_{timestamp}",
                         style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        if self.stats_dict[self.stat] + 1 <= max_stats:
            self.stats_dict[self.stat] += 1
            embed = make_stats_embed(self.character, self.colour, self.avatar_url, self.stats_dict, max_stats, emoji1,
                                     emoji2, self.notes)
            await interaction.response.edit_message(embed=embed, view=self.view)
        else:
            await interaction.respond("Maximum value reached.", ephemeral=True)


class MinusStatButton(discord.ui.Button):
    def __init__(self, character, colour, avatar_url, stat, stats_dict, notes, timestamp):
        self.stat = stat
        self.colour = colour
        self.avatar_url = avatar_url
        self.character = character
        self.stats_dict = stats_dict
        self.notes = notes
        self.timestamp = timestamp
        super().__init__(label=f"-1 {stat}", row=4,
                         custom_id=f"persistent_view:minus{self.stat}_{timestamp}",
                         style=discord.ButtonStyle.red)

    async def callback(self, interaction: discord.Interaction):
        if self.stats_dict[self.stat] - 1 >= 0:
            self.stats_dict[self.stat] -= 1
            embed = make_stats_embed(self.character, self.colour, self.avatar_url, self.stats_dict, max_stats, emoji1,
                                     emoji2, self.notes)
            await interaction.response.edit_message(embed=embed, view=self.view)
        else:
            await interaction.respond("Minimum value reached.", ephemeral=True)


def setup(bot):
    bot.add_cog(Rp(bot))
