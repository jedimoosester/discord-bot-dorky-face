from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
import discord
from discord.ext.commands import Bot as BotBase
from glob import glob
from dotenv import load_dotenv
import os


OWNER_IDS = [268862253326008322]
COGS = [path.split("/")[-1][:-3] for path in glob("./lib/cogs/*.py")]


class Ready(object):
    def __init__(self):
        for cog in COGS:
            setattr(self, cog, False)

    def ready_up(self, cog):
        setattr(self, cog, True)
        print(f" {cog} cog ready")

    def all_ready(self):
        return all([getattr(self, cog) for cog in COGS])


class Bot(BotBase):
    def __init__(self):
        self.test = True  # testing mode, True or False

        self.command_prefix = "!"

        self.sqlite_database = "./data/database.sqlite"
        self.ticket_views_added = False
        self.posts_last_checked = None  # datetime of last time posts were updated to database

        self.persistent_views_added = False

        self.ready = False
        self.cogs_ready = Ready()

        self.BOT_TOKEN = None
        # FIXME: Add other authentication keys here

        self.scheduler = AsyncIOScheduler()

        super().__init__(command_prefix=self.command_prefix,
                         owner_ids=OWNER_IDS,
                         intents=discord.Intents().all())

    def setup(self):
        for cog in COGS:
            self.load_extension(f"lib.cogs.{cog}")
            print(f" {cog} cog loaded")
        print("setup complete")

    def run(self):
        print("running setup...")
        self.setup()
        load_dotenv()
        self.BOT_TOKEN = os.getenv("BOT_TOKEN")
        # FIXME: set other authentication keys here

        print("running bot...")
        super().run(self.BOT_TOKEN, reconnect=True)

    async def on_ready(self):
        if not self.ready:
            # FIXME: Set start-up variables, load data, etc.

            self.scheduler.start()  # Start scheduled jobs

            while not self.cogs_ready.all_ready():
                print("not ready")
                await asyncio.sleep(0.5)

            self.ready = True
            await self.change_presence(
                activity=discord.Activity(type=discord.ActivityType.watching, name="you... 🎃"))
            print("bot logged in as {0.user}".format(self))

            if self.test:
                print("in test mode")

        else:
            print("bot reconnected")
            await self.change_presence(
                activity=discord.Activity(type=discord.ActivityType.watching, name="you... 🎃"))

    async def on_message(self, message):
        if not message.author.bot:
            await self.process_commands(message)


bot = Bot()
