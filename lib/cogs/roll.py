import discord
from discord import Embed
from discord.commands import slash_command, Option
from discord.ext.commands import Cog
import json
from datetime import datetime
import random


with open('./data/guild_data.json', 'r') as f:
    guild_ids = [int(guild_id) for guild_id in json.load(f).keys()]


class Roll(Cog):
    # Roll/dice related commands
    def __init__(self, bot):
        self.bot = bot

    @slash_command(guild_ids=guild_ids, description="Roll dice.", name="roll")
    async def roll(self, ctx,
                   sides: Option(int, "Number of sides (default: 10)", default=10),
                   number: Option(int, "Number of dice (default: 1).", default=1)):
        await ctx.defer()
        if number < 1 or sides < 1:
            await ctx.respond("Number of dice and number of sides must be greater than 0.")
        else:
            roll_result = [str(random.randint(1, sides)) for i in range(number)]
            embed = Embed(title=f"You rolled {number}d{sides}",
                          description=f"Result: **{', '.join(roll_result)}**",
                          colour=ctx.author.colour)
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url)
            if f"d{sides}" in ["d4", "d6", "d8", "d10", "d12", "d20", "d24", "d30"]:
                image = discord.File(f"./images/dice/d{sides}.png", filename=f"d{sides}.png")
            else:
                image = discord.File(f"./images/dice/d6.png", filename=f"d{sides}.png")
            embed.set_thumbnail(url=f"attachment://d{sides}.png")
            await ctx.respond(embed=embed, file=image)
        print(f"{datetime.now()}: /roll called by {ctx.author.display_name}")

    @Cog.listener()
    async def on_message(self, message):
        if not message.author.bot:
            pass

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up('roll')


def setup(bot):
    bot.add_cog(Roll(bot))
