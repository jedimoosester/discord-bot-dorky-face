import discord
from discord.commands import slash_command, Option
from discord.ext.commands import Cog
import json
from datetime import datetime
import aiohttp
import io


with open('./data/guild_data.json', 'r') as f:
    guild_ids = [int(guild_id) for guild_id in json.load(f).keys()]


class Basic(Cog):
    # Basic commands live here
    def __init__(self, bot):
        self.bot = bot
        self.sheet = None

    @slash_command(guild_ids=guild_ids, description="Need help?", name="help")
    async def dorky(self, ctx):
        await ctx.respond("I need help too.")

    @slash_command(guild_ids=guild_ids, description="Slap someone with a large trout. An IRC classic.", name="slap")
    async def slap(self, ctx,
                   member: Option(discord.Member, "Who's getting slapped?", required=True)):
        # Slap someone with a large trout
        view = SlapView(ctx)  # Create a view with a slap back button
        if ctx.author == member:
            # Case where author slaps themselves
            interaction = await ctx.respond(
                f"{ctx.author.display_name} slaps themselves around a bit with a large trout. That's fishy.",
                view=view)
        else:
            # Case where author slaps someone else
            interaction = await ctx.respond(
                f"{ctx.author.display_name} slaps {member.mention} around a bit with a large trout.", view=view)
        if member.bot:
            # Bot reacts if a bot is slapped
            message = await interaction.original_response()
            await message.add_reaction('😶')
        await view.wait()  # Wait to see if slap back button is pressed
        if view.value:  # Slap back button is pressed
            if view.user == ctx.author:
                await ctx.send(
                    f"{ctx.author.display_name} slaps themselves around a bit with a large trout. That's fishy.")
            else:
                await ctx.send(
                    f"{view.user.display_name} slaps {ctx.author.mention} around a bit with a large trout.")
        print(f"{datetime.now()}: /slap called by {ctx.author.display_name}")

    @slash_command(guild_ids=guild_ids, description="Get wow'd.", name="wow")
    async def wow(self, ctx):
        await ctx.defer()  # Defer command to give time for movie clip to load
        async with aiohttp.ClientSession() as session:
            # Connect to API
            async with session.get("https://owen-wilson-wow-api.onrender.com/wows/random") as r:
                if r.status == 200:
                    data = await r.text()
                    result = json.loads(data)[0]
        video = result['video']['360p']  # Get URL of 360p movie clip (lowest quality available)
        movie = result['movie']  # Get movie title (used for file name)

        async with aiohttp.ClientSession() as session:
            async with session.get(video) as resp:
                data = io.BytesIO(await resp.read())  # Convert movie into byte format so it can be sent as file
                await ctx.respond(file=discord.File(data, filename=f'{movie}.mp4'))
        print(f"{datetime.now()}: /wow called by {ctx.author.display_name}")

    @Cog.listener()
    async def on_message(self, message):
        if not message.author.bot:
            pass

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up('basic')


class SlapView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=600)
        self.value = None
        self.user = None
        self.ctx = ctx

    @discord.ui.button(label="Slap Back!", style=discord.ButtonStyle.blurple)
    async def slap(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = True
        self.user = interaction.user
        button.label = "Slapped!"
        button.disabled = True
        self.stop()
        await interaction.response.edit_message(view=self)

    async def on_timeout(self):
        await self.ctx.interaction.edit_original_message(view=None)


def setup(bot):
    bot.add_cog(Basic(bot))
