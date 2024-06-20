from discord.commands import slash_command, Option
from discord.ext.commands import Cog
import json


with open('./data/guild_data.json', 'r') as f:
    guild_ids = [int(guild_id) for guild_id in json.load(f).keys()]


class Template(Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(guild_ids=guild_ids, description="Description of command.", name="command")
    async def command_name(self, ctx, keyword: Option(str, "Option.", required=False, default=None)):
        # FIXME: code for command goes here
        await ctx.respond(f"This is a command with argument {keyword}.")

    @Cog.listener()
    async def on_message(self, message):
        if not message.author.bot:
            # FIXME: code to handle messages here
            pass

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up('template')


def setup(bot):
    bot.add_cog(Template(bot))
