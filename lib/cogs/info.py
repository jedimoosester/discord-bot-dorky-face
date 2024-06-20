import discord
from discord import Embed, Colour
from discord.commands import slash_command, Option
from discord.ext.commands import Cog
import json
from datetime import datetime
import random
import sqlite3


with open('./data/guild_data.json', 'r') as f:
    guild_ids = [int(guild_id) for guild_id in json.load(f).keys()]


class Info(Cog):
    # Site information-related commands
    def __init__(self, bot):
        self.bot = bot
        self.sqlite_database = None

    @slash_command(guild_ids=guild_ids, description="Get useful links and the world map.", name="links")
    async def links(self, ctx):
        await ctx.defer()
        # Read database for links
        conn = sqlite3.connect(self.sqlite_database)
        cursor = conn.cursor()
        result = cursor.execute("SELECT field, text, url FROM urls WHERE guild_id = ? ORDER BY o ASC;", (ctx.guild.id,)).fetchall()
        conn.close()
        # Create Embed object
        embed = Embed(title="Useful Links", description="", colour=Colour.dark_green())
        # Create and populate dictionary, categorizing by field
        dictionary = {}
        for r in result:
            try:
                dictionary[r[0]].append([r[1], r[2]])
            except KeyError:
                dictionary[r[0]] = [[r[1], r[2]]]
        for key in dictionary.keys():
            links = '\n'.join([f"[{d[0]}]({d[1]})" for d in dictionary[key]])  # Use Discord markup for hyperlinks
            embed.add_field(name=key, value=links)  # Add an embed field for each category field
        # Attach world map as an image in the embed
        image = discord.File(f"./images/World_Map.jpg", filename=f"world_map.jpg")
        embed.set_image(url=f"attachment://world_map.jpg")
        await ctx.respond(file=image, embed=embed)
        print(f"{datetime.now()}: /links called by {ctx.author.display_name}")

    @Cog.listener()
    async def on_message(self, message):
        if not message.author.bot:
            pass

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.sqlite_database = self.bot.sqlite_database
            self.bot.cogs_ready.ready_up('info')


def setup(bot):
    bot.add_cog(Info(bot))
